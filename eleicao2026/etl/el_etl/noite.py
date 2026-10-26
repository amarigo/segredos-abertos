"""A apuração ao longo da noite.

Cada boletim de urna tem a hora em que o TSE o recebeu ("rec", horário de Brasília). Somando os boletins na ordem em
que chegaram, refazemos a parcial da noite: quantas urnas já estavam apuradas, quanto cada candidato tinha e quanto
de cada estado já tinha chegado. Isso mostra por que a liderança pode virar durante a apuração: os estados não chegam
todos na mesma velocidade.
"""
import collections
import datetime

PASSO = 5  # minutos
DIAS = {'1': datetime.date(2026, 10, 4), '2': datetime.date(2026, 10, 25)}


def minuto_da_noite(rec, dia):
    """'2026-10-25 20:31:31' -> minutos desde 0h do dia da eleição (passa de 1440 depois da meia-noite)."""
    if not rec or rec.startswith('#'):
        return None
    d = datetime.datetime.strptime(rec[:19], '%Y-%m-%d %H:%M:%S')
    return (d - datetime.datetime.combine(dia, datetime.time())).total_seconds() / 60


def apuracao(secs, validos, dia, inicio=17 * 60):
    """Parcial acumulada a cada PASSO minutos, a partir de `inicio` (17h)."""
    chegadas = []
    total_uf = collections.Counter()
    for d in secs:
        v = d.get('v')
        if not v:
            continue
        total_uf[d['uf']] += 1
        m = minuto_da_noite(d.get('rec'), dia)
        if m is None:
            continue
        chegadas.append((m, d['uf'], v.get('13', 0), v.get('22', 0), sum(x for k, x in v.items() if k in validos)))
    chegadas.sort()
    if not chegadas:
        return None
    fim = max(inicio, int(chegadas[-1][0] // PASSO + 1) * PASSO)
    t = list(range(inicio, fim + PASSO, PASSO))
    n, v13, v22, val = [], [], [], []
    uf = {u: [] for u in total_uf}
    acc = collections.Counter()
    acc_uf = collections.Counter()
    i = 0
    for marco in t:
        while i < len(chegadas) and chegadas[i][0] <= marco:
            m, u, a, b, c = chegadas[i]
            acc['n'] += 1
            acc['13'] += a
            acc['22'] += b
            acc['val'] += c
            acc_uf[u] += 1
            i += 1
        n.append(acc['n'])
        v13.append(acc['13'])
        v22.append(acc['22'])
        val.append(acc['val'])
        for u in uf:
            uf[u].append(acc_uf[u])
    return {'passo': PASSO, 't': t, 'n': n, '13': v13, '22': v22, 'val': val, 'uf': uf,
            'tot_uf': dict(total_uf), 'tot': sum(total_uf.values()), 'sem_hora': sum(total_uf.values()) - len(chegadas)}
