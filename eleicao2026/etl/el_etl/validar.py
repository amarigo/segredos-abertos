"""Conferência antes de publicar. Se algo não bater, não publica.

1. A soma dos votos de todas as urnas tem que ser igual ao total oficial do TSE, voto por voto: cada candidato,
   brancos, nulos e comparecimento, no Brasil, em cada estado e no exterior.
2. Nenhuma seção repetida.
3. Horários de fechamento possíveis (entre 8h e 24h de Brasília) e o gráfico de horários soma o número de urnas.
"""
import collections

from .analisar import CORTES, FECHA


def conferir(turno, secs, oficial_turno, resumo):
    """Devolve a lista de problemas (vazia = tudo certo)."""
    erros = []
    vistos = set()
    soma = collections.defaultdict(collections.Counter)
    for d in secs:
        k = (d['uf'], str(d['mun']), str(d['z']), str(d['s']))
        if k in vistos:
            erros.append(f'{turno}º turno: seção repetida {k}')
        vistos.add(k)
        if not d.get('v'):
            continue
        for u in (d['uf'], 'BR'):
            for c, x in d['v'].items():
                soma[u][c] += x
            soma[u]['comp'] += d.get('comp', 0)
    for uf, of in oficial_turno.items():
        s = soma.get(uf, collections.Counter())
        cands = set(of['cand'])
        for c, info in of['cand'].items():
            if s[c] != info['v']:
                erros.append(f'{turno}º turno, {uf}: candidato {c} soma {s[c]} nas urnas e {info["v"]} no oficial')
        if s['95'] != of['brancos']:
            erros.append(f'{turno}º turno, {uf}: brancos {s["95"]} nas urnas e {of["brancos"]} no oficial')
        # O TSE conta como nulo o voto em número que não é de candidato válido (ex.: candidatura indeferida).
        nulos = sum(x for c, x in s.items() if c not in cands and c not in ('95', 'comp'))
        if nulos != of['nulos']:
            erros.append(f'{turno}º turno, {uf}: nulos {nulos} nas urnas e {of["nulos"]} no oficial')
        if s['comp'] != of['comp']:
            erros.append(f'{turno}º turno, {uf}: comparecimento {s["comp"]} nas urnas e {of["comp"]} no oficial')
        if of['pst'] != '100,00':
            erros.append(f'{turno}º turno, {uf}: apuração oficial em {of["pst"]}%, não 100%')
    for uf in soma:
        if uf not in oficial_turno:
            erros.append(f'{turno}º turno: estado {uf} nas urnas e não no oficial')
    n_hora = sum(resumo['hist'].values())
    if n_hora != resumo['cut'][CORTES[0]].get('BR', {}).get('n', 0) + sum(v for m, v in resumo['hist'].items() if m < FECHA):
        erros.append(f'{turno}º turno: gráfico de horários não soma o número de urnas')
    for m in resumo['hist']:
        if not 8 * 60 <= m < 24 * 60:
            erros.append(f'{turno}º turno: urna fechando em horário impossível ({m // 60}h{m % 60:02d})')
    return erros
