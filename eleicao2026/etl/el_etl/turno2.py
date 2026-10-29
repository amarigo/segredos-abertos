"""2º turno: boletim de urna digital de cada seção, no site de resultados do TSE.

Quando fizemos a coleta, o arquivo bweb do 2º turno ainda não tinha saído. Então, para cada seção:
1. a lista de seções do estado ("-cs.json") dá cidade, zona e seção;
2. o arquivo "-aux.json" da seção dá a pasta (hash) onde estão os arquivos da urna;
3. o boletim de urna (.bu) é lido com `ber.py`: hora de abertura, hora de encerramento e votos.
Se a seção não tem "-aux.json", ela foi agregada a outra (votou na mesma urna).
"""
import gzip
import json
import os
import queue
import threading
import time

import requests

from . import ber

B = 'https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221'
ELEICAO = 6258


def _i(v):
    return int.from_bytes(v, 'big', signed=True)


def ler_bu(raw):
    """Lê um boletim de urna (.bu) e devolve horários e votos para presidente.

    Votos: chave = número do candidato; '95' = brancos; '96' = nulos (mesma convenção do bweb).
    """
    env = ber.parse(raw)[0][3]
    bu = ber.parse(env[-1][3])[0][3]
    res = {'ab': None, 'en': None, 'tipo_dados': None}
    for cls, cons, tag, v in bu:
        # dadosSecaoSA: [0] dados da seção (abertura, encerramento) ou [1] dados de seção de apuração
        if cls == 2 and tag in (0, 1) and cons and v and v[0][2] == 27 and len(v) <= 3:
            res['tipo_dados'] = 'secao' if tag == 0 else 'SA'
            if tag == 0:
                res['ab'] = v[0][3].decode()
                res['en'] = v[1][3].decode()
        # resultadosVotacaoPorEleicao
        if cls == 0 and tag == 16 and cons and v and v[0][1] and v[0][3] and v[0][3][0][2] == 2 and len(v[0][3]) >= 5:
            for ele in v:
                f = ele[3]
                if _i(f[0][3]) != ELEICAO:
                    continue
                res['apt'] = _i(f[1][3])
                for rv in f[4][3]:
                    rvf = rv[3]
                    res['comp'] = _i(rvf[1][3])
                    for tvc in rvf[2][3]:
                        t = tvc[3]
                        if _i(t[0][3]) != 1:  # 1 = cargo presidente
                            continue
                        votos = {}
                        for vv in t[2][3]:
                            x = vv[3]
                            tipo, q = _i(x[0][3]), _i(x[1][3])
                            if tipo == 1:  # nominal
                                k = str(_i(x[2][3][1][3]))
                            else:
                                k = {2: '95', 3: '96'}.get(tipo, 't%d' % tipo)
                            votos[k] = votos.get(k, 0) + q
                        res['v'] = votos
    return res


class Cliente:
    def __init__(self, tentativas=6):
        self.t = tentativas
        self.local = threading.local()

    def get(self, url, tipo='json'):
        if not hasattr(self.local, 's'):
            self.local.s = requests.Session()
        for i in range(self.t):
            try:
                r = self.local.s.get(url, timeout=30)
                if r.status_code == 200:
                    return r.json() if tipo == 'json' else r.content
                if r.status_code == 404:
                    return None
            except requests.RequestException:
                pass
            time.sleep(1.5 ** i)
        raise RuntimeError('falhou ' + url)


def secao(cli, uf, mun, nm, z, s):
    u = uf.lower()
    rec = {'uf': uf, 'mun': mun, 'nm': nm, 'z': z, 's': s}
    aux = cli.get(f'{B}/dados/{u}/{mun}/{z}/{s}/p003221-{u}-m{mun}-z{z}-s{s}-aux.json')
    if aux is None:
        rec['err'] = 'noaux'  # seção agregada
        return rec
    rec['st'] = aux.get('st')
    hs = aux.get('hashes', [])
    rec['nh'] = len(hs)
    h = None
    for hh in hs:
        if hh.get('st') in ('Totalizado', 'Recebido'):
            h = hh
    h = h or (hs[-1] if hs else None)
    if h:
        rec['hst'] = h.get('st')
        if h.get('dr') and h.get('hr'):  # hora em que o TSE recebeu o boletim (Brasília); bweb2.py troca pela do bweb
            dr = h['dr']
            rec['rec'] = f'{dr[6:10]}-{dr[3:5]}-{dr[0:2]} {h["hr"]}'
        nomes = [a['nm'] for a in h['arq'] if a['tp'] in ('bu', 'busa')]
        rec['arq'] = [a['tp'] for a in h['arq']]
        if nomes:
            raw = cli.get(f"{B}/dados/{u}/{mun}/{z}/{s}/{h['hash']}/{nomes[0]}", 'bin')
            if raw:
                rec.update(ler_bu(raw))
            else:
                rec['err'] = 'nobu'
        else:
            rec['err'] = 'nobufile'  # seção não instalada ou voto em cédula
    return rec


def coletar(uf, saida, fios=48):
    """Baixa e lê todas as seções de um estado e grava `saida/UF.jsonl.gz`."""
    cli = Cliente()
    u = uf.lower()
    cs = cli.get(f'{B}/config/{u}/{u}-p003221-cs.json')
    itens = [(m['cd'], m['nm'], zz['cd'], sec['ns'])
             for a in cs['abr'] for m in a['mu'] for zz in m['zon'] for sec in zz['sec']]
    q, res, trava = queue.Queue(), [], threading.Lock()

    def trabalhar():
        while True:
            it = q.get()
            if it is None:
                return
            try:
                r = secao(cli, uf, *it)
            except Exception as e:  # anotado e conferido depois por validar.py
                r = {'uf': uf, 'mun': it[0], 'nm': it[1], 'z': it[2], 's': it[3], 'err': repr(e)[:200]}
            with trava:
                res.append(r)

    ths = [threading.Thread(target=trabalhar, daemon=True) for _ in range(fios)]
    for t in ths:
        t.start()
    for it in itens:
        q.put(it)
    for _ in ths:
        q.put(None)
    for t in ths:
        t.join()
    res.sort(key=lambda r: (r['mun'], r['z'], r['s']))
    os.makedirs(saida, exist_ok=True)
    with gzip.open(os.path.join(saida, f'{uf}.jsonl.gz'), 'wt', encoding='utf-8') as o:
        for r in res:
            o.write(json.dumps(r, ensure_ascii=False) + '\n')
    return len(res)
