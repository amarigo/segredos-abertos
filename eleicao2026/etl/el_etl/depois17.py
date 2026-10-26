"""Votos registrados depois das 17h, urna por urna, a partir do registro (log) de cada urna (logs.py).

O registro diz a hora de cada voto, mas não em quem foi (o voto é secreto). Por isso, para cada urna
guardamos quantos votos vieram depois das 17h e o resultado completo da urna (do boletim).

Conferência: em cada urna, o total de votos do registro tem que ser igual ao comparecimento do boletim.
"""
import collections
import glob
import gzip
import json
import os

TOPO = 40  # urnas com mais votos depois das 17h guardadas dentro da página, por estado
# grupos pela hora em que a urna foi encerrada (Brasília), iguais aos da seção 5
GRUPOS = [(0, 1035), (1035, 1080), (1080, 1140), (1140, 10 ** 6)]


def ler(pasta):
    out = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for linha in fh:
                r = json.loads(linha)
                out[(r['uf'], r['mun'], r['z'], r['s'])] = r
    return out


def resumo(secs, regs, validos):
    """Junta boletins (secs) e registros (regs). Grava d17/ult em cada seção lida e devolve o resumo da página.

    uf: [urnas lidas, urnas com voto depois das 17h, votos depois das 17h, votos nas urnas lidas,
         Lula, Flávio e válidos nas urnas com voto depois das 17h]
    """
    if not regs:
        return None
    uf = collections.defaultdict(lambda: [0] * 7)
    pm = collections.defaultdict(collections.Counter)
    conf = collections.Counter()
    dif = []
    top = collections.defaultdict(list)
    grp = [[0, 0, 0] for _ in GRUPOS]  # urnas, urnas com voto depois das 17h, votos depois das 17h
    ult = None  # o último voto computado depois das 17h no Brasil (fora o exterior, que usa a hora local)
    for d in secs:
        v = d.get('v')
        if not v or d.get('tipo_dados', 'secao') != 'secao':
            continue
        conf['urnas'] += 1
        r = regs.get((d['uf'], d['mun'], d['z'], d['s']))
        if r is None or r.get('err'):
            conf['sem_registro_' + (r.get('err') if r else 'nao_lido')] += 1
            continue
        if r['n'] != d.get('comp'):
            conf['diferente'] += 1
            dif.append([d['uf'], d['nm'], d['z'], d['s'], r['n'], d.get('comp')])
            continue  # só entram as urnas em que o registro bate com o boletim
        conf['bate'] += 1
        d['d17'], d['ult'] = r['d17'], r['ult']
        val = sum(x for k, x in v.items() if k in validos)
        if d.get('enb') is not None:
            g = grp[next(i for i, (a, b) in enumerate(GRUPOS) if a <= d['enb'] < b)]
            g[0] += 1
            g[1] += 1 if r['d17'] else 0
            g[2] += r['d17']
        for u in (d['uf'], 'BR'):
            a = uf[u]
            a[0] += 1
            a[3] += d['comp']
            if r['d17']:
                a[1] += 1
                a[2] += r['d17']
                a[4] += v.get('13', 0)
                a[5] += v.get('22', 0)
                a[6] += val
            for m, q in r['pm'].items():
                pm[u][int(m)] += q
        if r['d17'] and d['uf'] != 'ZZ' and (ult is None or r['ult'] > ult[4]):
            ult = [d['uf'], d['nm'], int(d['z']), int(d['s']), r['ult']]
        if r['d17']:
            top[d['uf']].append([d['nm'], str(d['mun']).zfill(5), int(d['z']), int(d['s']), r['d17'], d['comp'],
                                 v.get('13', 0), v.get('22', 0), round(r['ult'] * 60),
                                 round(d['enb'] * 60) if d.get('enb') is not None else -1])
    for u in top:
        top[u].sort(key=lambda x: (-x[4], -x[8]))
        top[u] = top[u][:TOPO]
    return {'uf': dict(uf), 'pm': {u: [[m, q] for m, q in sorted(c.items())] for u, c in pm.items()},
            'top': dict(top), 'ult': ult, 'grp': grp, 'conf': dict(conf), 'dif': dif[:200], 'ndif': len(dif)}


def conferir(t, res):
    """Erros que impedem a publicação: urnas sem registro lido (o download precisa ser refeito)."""
    if res is None:
        return []
    falta = sum(v for k, v in res['conf'].items() if k.startswith('sem_registro_') and k != 'sem_registro_nolog')
    return [f'{t}º turno: {falta} urnas sem registro lido (rode de novo o logs.py)'] if falta else []
