"""2º turno: conferência com o arquivo oficial "Boletim de Urna" (bweb) do Portal de Dados Abertos do TSE.

O TSE publicou o bweb do 2º turno em 27/10/2026 (arquivos gerados em 26/10/2026, 07h42), um .zip por estado e um
para o exterior, cada um com o seu .sha512. A API do portal (CKAN) só lista os arquivos; os boletins vêm nos .zip,
por isso baixamos os arquivos (não há API com os boletins de cada seção).

Antes, o site usava o boletim de urna digital de cada seção (turno2.py). Aqui:
1. conferimos o SHA-512 de cada .zip;
2. comparamos seção por seção com o que o site já tinha: votos de cada número, comparecimento, aptos, hora de
   abertura e de encerramento. Se qualquer coisa for diferente, nada é gravado;
3. a hora em que o TSE recebeu cada boletim passa a ser a do bweb (DT_BU_RECEBIDO), a mesma fonte do 1º turno.
   A hora antiga, do arquivo "-aux.json" da seção, fica guardada em `rec_aux`.
"""
import collections
import glob
import gzip
import hashlib
import json
import os
import re
import sys

import requests

from . import oficial, turno1

URL = 'https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_2t_{uf}_261020260742.zip'


def baixar(pasta):
    os.makedirs(pasta, exist_ok=True)
    for uf in oficial.UFS:
        for suf in ('', '.sha512'):
            alvo = os.path.join(pasta, f'bweb_2t_{uf}.zip{suf}')
            if os.path.exists(alvo):
                continue
            r = requests.get(URL.format(uf=uf) + suf, timeout=600)
            r.raise_for_status()
            with open(alvo + '.tmp', 'wb') as f:
                f.write(r.content)
            os.replace(alvo + '.tmp', alvo)


def conferir_hash(zp):
    with open(zp + '.sha512', encoding='ascii') as f:
        esperado = f.read().split()[0].lower()
    h = hashlib.sha512()
    with open(zp, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest() == esperado


def _k(d):
    return d['uf'], str(d['mun']).zfill(5), str(d['z']).zfill(4), str(d['s']).zfill(4)


def _dig(t):
    return re.sub(r'\D', '', t or '')[:14]


def comparar(site, bweb):
    """Diferenças entre os registros do site e do bweb (dicionários por seção)."""
    dif = collections.Counter()
    exemplos = []
    for k in site.keys() | bweb.keys():
        a, b = site.get(k), bweb.get(k)
        if a is None or b is None:
            dif['so_no_' + ('bweb' if a is None else 'site')] += 1
            exemplos.append((k, 'seção só em um dos dois'))
            continue
        for campo, x, y in (('votos', a['v'], b['v']), ('comparecimento', a['comp'], b['comp']),
                            ('aptos', a['apt'], b['apt']), ('abertura', _dig(a.get('ab')), _dig(b.get('ab'))),
                            ('encerramento', _dig(a.get('en')), _dig(b.get('en')))):
            if x != y:
                dif[campo] += 1
                exemplos.append((k, campo, x, y))
    return dif, exemplos[:20]


def atualizar(brutos, zips):
    """Confere tudo e, se bater, grava a hora de recebimento do bweb nos boletins do 2º turno. Devolve o resumo."""
    hashes = {uf: conferir_hash(os.path.join(zips, f'bweb_2t_{uf}.zip')) for uf in oficial.UFS}
    if not all(hashes.values()):
        raise SystemExit(f'SHA-512 diferente: {[u for u, ok in hashes.items() if not ok]}')
    bweb = {}
    for uf in oficial.UFS:
        for d in turno1.ler_zip(os.path.join(zips, f'bweb_2t_{uf}.zip')):
            bweb[_k(d)] = d
    arquivos = {}
    site = {}
    for f in sorted(glob.glob(os.path.join(brutos, '*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            linhas = [json.loads(x) for x in fh]
        arquivos[f] = linhas
        for d in linhas:
            if d.get('v'):
                site[_k(d)] = d
    dif, ex = comparar(site, bweb)
    if dif:
        raise SystemExit(f'O bweb não bate com os boletins do site: {dict(dif)} {ex}')
    mudou = 0
    for k, d in site.items():
        novo = bweb[k]['rec']
        if d.get('rec') != novo:
            mudou += 1
            d['rec_aux'] = d.get('rec')
            d['rec'] = novo
    for f, linhas in arquivos.items():
        with gzip.GzipFile(f + '.tmp', 'wb', mtime=0) as o:
            for d in linhas:
                o.write((json.dumps(d, ensure_ascii=False) + '\n').encode())
        os.replace(f + '.tmp', f)
    return {'arquivos': len(hashes), 'secoes': len(bweb), 'iguais': len(site), 'hora_recebimento_mudou': mudou}


if __name__ == '__main__':
    aqui = os.path.dirname(os.path.abspath(__file__))
    z = sys.argv[1] if len(sys.argv) > 1 else os.path.join(aqui, '..', '.cache', 'bweb2')
    baixar(z)
    print(atualizar(os.path.join(aqui, '..', '..', 'dados', 'brutos', '2turno'), z))
