"""Resultados oficiais do TSE (Brasil, cada estado e exterior), nos dois turnos.

Baixa os arquivos "-u.json" do site de resultados (resultados.tse.jus.br) e junta tudo em um só arquivo,
oficial.json, que é a referência para todas as conferências.
"""
import json
import os
import time

import requests

# 6257 = presidente, 1º turno (4/10/2026). 6258 = presidente, 2º turno (25/10/2026).
ELEICOES = {'1': '6257', '2': '6258'}
UFS = ('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ').split()
URL = 'https://resultados.tse.jus.br/oficial/ele2026/{e}/dados/{u}/{u}-c0001-e00{e}-u.json'


def url(eleicao, uf):
    u = uf.lower()
    return URL.format(e=eleicao, u=u)


def baixar(pasta):
    """Baixa os 58 arquivos oficiais (Brasil + 27 UFs + exterior, dois turnos) para `pasta`."""
    os.makedirs(pasta, exist_ok=True)
    s = requests.Session()
    for e in ELEICOES.values():
        for uf in ('BR',) + UFS:
            for i in range(5):
                try:
                    r = s.get(url(e, uf), timeout=30)
                    r.raise_for_status()
                    break
                except requests.RequestException:
                    if i == 4:
                        raise
                    time.sleep(2 ** i)
            with open(os.path.join(pasta, f'{uf.lower()}-{e}.json'), 'wb') as f:
                f.write(r.content)


def ler(d):
    """Lê um arquivo -u.json do TSE e devolve só o que usamos."""
    cand = {}
    for agr in d['carg'][0]['agr']:
        for p in agr['par']:
            for c in p['cand']:
                cand[c['n']] = {'nm': c['nmu'], 'sg': p['sg'], 'v': int(c['vap'])}
    return {
        'cand': cand, 'aptos': int(d['e']['te']), 'comp': int(d['e']['c']), 'abst': int(d['e']['a']),
        'brancos': int(d['v']['vb']), 'nulos': int(d['v']['tvn']), 'validos': int(d['v']['vv']),
        'secoes': int(d['s']['ts']), 'sec_tot': int(d['s']['st']), 'pst': d['s']['pst'],
        'atual': d['dg'] + ' ' + d['hg'],
    }


def juntar(pasta):
    """Junta os arquivos baixados em {eleição: {UF: resultado}}."""
    out = {}
    for nome in sorted(os.listdir(pasta)):
        if not nome.endswith('.json'):
            continue
        uf, e = nome[:-5].split('-')
        with open(os.path.join(pasta, nome), encoding='utf-8') as f:
            out.setdefault(e, {})[uf.upper()] = ler(json.load(f))
    return out
