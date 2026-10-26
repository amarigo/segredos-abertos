"""Hora de cada voto, lida do registro (log) de cada urna publicado pelo TSE.

Cada urna grava um registro de tudo o que acontece nela. Quando um eleitor termina de votar, a urna
anota a linha "O voto do eleitor foi computado", com data e hora (hora local da urna). O registro não diz
em quem foi o voto: o voto é secreto. Assim conseguimos contar, urna por urna, quantos votos foram
registrados depois das 17h, mas não para quem foram.

Arquivos: resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{pleito}/dados/{uf}/{mun}/{zona}/{secao}/{hash}/...-log.jez
(um .zip com um ou mais logd.dat; mais de um quando a urna foi trocada durante o dia).

Conferência: o total de votos do registro, no dia da eleição, tem que ser igual ao comparecimento do boletim.
"""
import collections
import concurrent.futures as cf
import gzip
import io
import json
import os
import re
import sys
import time
import zipfile

from . import analisar
from .turno2 import Cliente

PLEITO = {'1': 3220, '2': 3221}
DIA = {'1': '04/10/2026', '2': '25/10/2026'}
VOTO = 'O voto do eleitor foi computado'


def votos_do_log(raw, dia):
    """Horas (minutos desde 0h, hora local da urna) de cada voto computado no dia."""
    out = []
    _ler_zip(raw, dia, out)
    out.sort()
    return out


def _ler_zip(raw, dia, out):
    """Quando a urna foi trocada no dia, o registro da urna antiga vem dentro, como outro .zip (.jez)."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for info in z.infolist():
            b = z.read(info)
            if b[:4] == b'PK\x03\x04':
                _ler_zip(b, dia, out)
                continue
            for m in _padrao(dia).finditer(b):
                h = m.group(1)
                out.append(int(h[0:2]) * 60 + int(h[3:5]) + int(h[6:8]) / 60)


_PADRAO = {}


def _padrao(dia):
    """Linha do registro: data e hora, nível, código da urna, programa, mensagem e assinatura, separados por tab."""
    if dia not in _PADRAO:
        _PADRAO[dia] = re.compile(rb'^' + re.escape(dia.encode()) + rb' (\d\d:\d\d:\d\d)\t[^\t\n]*\t[^\t\n]*\t[^\t\n]*\t'
                                  + re.escape(VOTO.encode()) + rb'\t', re.MULTILINE)
    return _PADRAO[dia]


def resumo_urna(horas, fuso, fecha=analisar.FECHA):
    """Votos depois das 17h de Brasília (no exterior, 17h locais), por minuto depois das 17h."""
    hb = [h - fuso * 60 for h in horas]
    depois = [h for h in hb if h >= fecha]
    por_min = collections.Counter(int(h - fecha) for h in depois)
    return {'n': len(hb), 'd17': len(depois), 'ult': round(hb[-1], 2) if hb else None,
            'pm': {str(k): v for k, v in sorted(por_min.items())}}


def secao(cli, turno, d, fuso):
    u, mun, z, s = d['uf'].lower(), d['mun'].zfill(5), d['z'].zfill(4), d['s'].zfill(4)  # o 1º turno (bweb) vem sem zeros
    p = PLEITO[turno]
    base = f'https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{p}/dados/{u}/{mun}/{z}/{s}'
    rec = {'uf': d['uf'], 'mun': d['mun'], 'z': d['z'], 's': d['s']}
    aux = cli.get(f'{base}/p00{p}-{u}-m{mun}-z{z}-s{s}-aux.json')
    if aux is None:
        rec['err'] = 'noaux'
        return rec
    h = None
    for hh in aux.get('hashes', []):  # o mesmo pacote de arquivos usado para o boletim
        if hh.get('st') in ('Totalizado', 'Recebido'):
            h = hh
    nomes = [a['nm'] for a in (h or {}).get('arq', []) if a['tp'] == 'log']
    if not nomes:
        rec['err'] = 'nolog'
        return rec
    raw = cli.get(f"{base}/{h['hash']}/{nomes[0]}", 'bin')
    if raw is None:
        rec['err'] = 'nolog'
        return rec
    try:
        rec.update(resumo_urna(votos_do_log(raw, DIA[turno]), fuso))
    except zipfile.BadZipFile:
        rec['err'] = 'badzip'
    return rec


def _ler_estado(cli, turno, uf, ds, fz, fios):
    """Lê o registro de cada urna do estado; o que o servidor não respondeu é tentado de novo no fim."""
    feitos = [0]

    def uma(d):
        feitos[0] += 1
        if feitos[0] % 5000 == 0:
            print(uf, feitos[0], len(ds), time.strftime('%H:%M:%S'), file=sys.stderr, flush=True)
        try:
            return secao(cli, turno, d, 0 if uf == 'ZZ' else fz.get((uf, d['mun']), analisar.FUSO.get(uf, 0)))
        except RuntimeError:
            return {'uf': d['uf'], 'mun': d['mun'], 'z': d['z'], 's': d['s'], 'err': 'falhou'}

    with cf.ThreadPoolExecutor(fios) as ex:
        res = list(ex.map(uma, ds))
        for _ in range(5):
            falhas = [i for i, r in enumerate(res) if r.get('err') == 'falhou']
            if not falhas:
                break
            time.sleep(30)
            for i, r in zip(falhas, ex.map(uma, [ds[i] for i in falhas]), strict=True):
                res[i] = r
    return res


def coletar(turno, brutos, saida, ufs=None, fios=32, limite=None):
    """Lê o registro de todas as urnas com votos de cada estado e grava `saida/UF.jsonl.gz`."""
    secs = analisar.ler_brutos(brutos)
    fz = analisar.fusos(secs)
    cli = Cliente()
    os.makedirs(saida, exist_ok=True)
    por = collections.defaultdict(list)
    for d in secs:
        if d.get('v') and d.get('tipo_dados', 'secao') == 'secao':
            por[d['uf']].append(d)
    for uf in sorted(ufs or por):
        alvo = os.path.join(saida, f'{uf}.jsonl.gz')
        if os.path.exists(alvo):
            continue
        res = _ler_estado(cli, turno, uf, por[uf][:limite] if limite else por[uf], fz, fios)
        tmp = alvo + '.tmp'
        with gzip.GzipFile(tmp, 'wb', mtime=0) as fo:
            for r in res:
                fo.write((json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n').encode())
        os.replace(tmp, alvo)
        print(uf, len(res), sum(r.get('d17', 0) for r in res), file=sys.stderr, flush=True)


if __name__ == '__main__':
    t = sys.argv[1]
    coletar(t, f'../dados/brutos/{t}turno', f'../dados/brutos/{t}turno_log', sys.argv[2:] or None)
