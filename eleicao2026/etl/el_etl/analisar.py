"""Hora de fechamento de cada urna e votos das urnas que fecharam depois de cada horário de corte.

Entrada: os boletins lidos (dados/brutos/<turno>turno/UF.jsonl.gz) e os resultados oficiais.
Saída: um resumo por turno, a planilha de todas as urnas e a lista de urnas usada no site.
"""
import collections
import csv
import glob
import gzip
import json
import os
import statistics

FECHA = 17 * 60  # a votação termina às 17h de Brasília (no exterior, 17h da hora local)
CORTES = [FECHA, FECHA + 5, FECHA + 10, FECHA + 15, FECHA + 30, FECHA + 60, FECHA + 90, FECHA + 120, FECHA + 180]
# Diferença de cada estado para Brasília, em horas (hora local − hora de Brasília).
FUSO = {'AC': -2, 'AM': -1, 'RO': -1, 'RR': -1, 'MT': -1, 'MS': -1}
CABECALHO = ['UF', 'Municipio', 'Cod_municipio_TSE', 'Zona', 'Secao', 'Abertura_hora_local', 'Encerramento_hora_local',
             'Encerramento_horario_Brasilia', 'Eleitores_aptos', 'Comparecimento', 'Votos_13_Lula', 'Votos_22_Flavio',
             'Brancos', 'Nulos', 'Votos_depois_17h']


def minutos(ts):
    """'2026-10-04 15:01:05' (bweb) ou '20261025T150035' (boletim .bu) -> minutos desde 0h."""
    if not ts or ts.startswith('#'):
        return None
    if 'T' in ts:
        return int(ts[9:11]) * 60 + int(ts[11:13]) + int(ts[13:15]) / 60
    return int(ts[11:13]) * 60 + int(ts[14:16]) + int(ts[17:19]) / 60


def relogio(ts):
    if not ts or ts.startswith('#'):
        return ''
    if 'T' in ts:
        return ts[9:11] + ':' + ts[11:13] + ':' + ts[13:15]
    return ts[11:19]


def hms(m):
    x = int(round(m * 60))
    return '%02d:%02d:%02d' % (x // 3600, x // 60 % 60, x % 60)


def ler_brutos(pasta):
    secs = []
    for f in sorted(glob.glob(os.path.join(pasta, '*.jsonl.gz'))):
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for linha in fh:
                d = json.loads(linha)
                if d.get('err') == 'noaux':
                    d['agregada'] = True
                secs.append(d)
    return secs


def fusos(secs):
    """Fuso de cada cidade.

    A votação abre às 8h da hora local. Pela mediana da hora de abertura das urnas da cidade, sabemos o fuso.
    Só o oeste do Amazonas (hora do Acre) e Fernando de Noronha (PE, +1h) fogem do padrão do estado.
    """
    ab = collections.defaultdict(list)
    for d in secs:
        m = minutos(d.get('ab'))
        if m is not None:
            ab[(d['uf'], d['mun'])].append(m)
    out = {}
    for k, v in ab.items():
        est = round((statistics.median(v) - 480) / 60)
        base = FUSO.get(k[0], 0)
        out[k] = est if (k[0] == 'AM' and est in (-1, -2)) or (k[0] == 'PE' and est == 1) else base
    return out


def analisar(secs, validos):
    """Devolve (resumo, urnas com horário em ordem do fechamento mais tardio)."""
    fz = fusos(secs)
    hist = collections.Counter()
    tot = collections.Counter()
    corte = {c: collections.defaultdict(collections.Counter) for c in CORTES}
    n_uf = collections.Counter()
    falta = collections.Counter()
    urnas = []
    for d in secs:
        v = d.get('v')
        if not v:
            falta['sem_votos_' + ('agregada' if d.get('agregada') else str(d.get('err') or d.get('tipo_dados')))] += 1
            continue
        n_uf[d['uf']] += 1
        n_uf['BR'] += 1
        for k, x in v.items():
            tot[k] += x
        tot['comp'] += d.get('comp', 0)
        tot['apt'] += d.get('apt', 0)
        m = minutos(d.get('en'))
        if m is None:
            falta['sem_horario'] += 1
            continue
        o = 0 if d['uf'] == 'ZZ' else fz.get((d['uf'], d['mun']), FUSO.get(d['uf'], 0))
        mb = m - o * 60  # hora de Brasília (no exterior, hora local)
        d['enb'] = mb
        hist[int(mb // 5) * 5] += 1
        urnas.append(d)
        val = sum(x for k, x in v.items() if k in validos)
        for c in CORTES:
            if mb >= c:
                for u in (d['uf'], 'BR'):
                    cc = corte[c][u]
                    cc['n'] += 1
                    cc['13'] += v.get('13', 0)
                    cc['22'] += v.get('22', 0)
                    cc['val'] += val
                    cc['comp'] += d.get('comp', 0)
    urnas.sort(key=lambda d: -d['enb'])
    resumo = {'n_secoes_arquivos': len(secs), 'tot': tot, 'missing': falta, 'hist': hist,
              'cut': {c: corte[c] for c in CORTES}, 'n_uf': n_uf,
              'fusos': dict(collections.Counter(f'{k[0]}:{o}' for k, o in fz.items()))}
    return resumo, urnas


def linha_csv(d):
    return [d['uf'], d['nm'], d['mun'], d['z'], d['s'], relogio(d.get('ab')), relogio(d.get('en')),
            hms(d['enb']) if d['uf'] != 'ZZ' else hms(d['enb']) + ' (local)',
            d.get('apt'), d.get('comp'), d['v'].get('13', 0), d['v'].get('22', 0), d['v'].get('95', 0), d['v'].get('96', 0),
            d.get('d17', '')]


def gravar_planilhas(turno, urnas, pasta):
    """Uma planilha por estado (e o exterior), na ordem do fechamento mais tardio."""
    os.makedirs(pasta, exist_ok=True)
    por = collections.defaultdict(list)
    for d in urnas:
        por[d['uf']].append(d)
    for uf, ds in por.items():
        with open(os.path.join(pasta, f'{turno}turno_{uf}.csv'), 'w', newline='', encoding='utf-8') as fo:
            w = csv.writer(fo, delimiter=';', lineterminator='\n')
            w.writerow(CABECALHO)
            for d in ds:
                w.writerow(linha_csv(d))


def gravar_lista_site(turno, urnas, validos, pasta):
    """Lista compacta por estado usada na seção 4 do site."""
    os.makedirs(pasta, exist_ok=True)
    por = collections.defaultdict(lambda: {'mun': [], 'cod': [], 'r': []})
    idx = collections.defaultdict(dict)
    for d in urnas:
        P = por[d['uf']]
        if d['nm'] not in idx[d['uf']]:
            idx[d['uf']][d['nm']] = len(P['mun'])
            P['mun'].append(d['nm'])
            P['cod'].append(str(d['mun']).zfill(5))
        P['r'].append([idx[d['uf']][d['nm']], int(d['z']), int(d['s']), int(round(d['enb'] * 60)), d.get('apt', 0),
                       d.get('comp', 0), d['v'].get('13', 0), d['v'].get('22', 0),
                       sum(x for k, x in d['v'].items() if k in validos), d.get('d17', -1),
                       int(round(d['ult'] * 60)) if d.get('ult') is not None else -1])  # -1: registro não lido
    for uf, P in por.items():
        P['r'].sort(key=lambda r: -r[3])
        with open(os.path.join(pasta, f'{turno}_{uf}.json'), 'w', encoding='utf-8') as f:
            json.dump(P, f, ensure_ascii=False, separators=(',', ':'))
