"""O que mudou do 1º para o 2º turno, cidade por cidade e local por local, e testes estatísticos nas urnas.

Tudo sai dos boletins de urna (os mesmos já conferidos voto a voto com o total oficial) e da lista oficial de locais
de votação do TSE (locais.py), que diz em que escola fica cada seção e a latitude e longitude da escola.

Testes (cada um procura um sinal que fraudes conhecidas costumam deixar; nenhum prova sozinho que não houve fraude):
  - valores impossíveis: mais gente votando que eleitores, ou soma de votos diferente de quem votou;
  - consistência urna a urna: a mesma urna, nos dois turnos, tem que ter votado parecido;
  - último dígito (Beber e Scacco, 2012): em números escritos por pessoas, alguns finais aparecem demais;
  - "impressão digital" (Klimek e outros, PNAS 2012): enchimento de urna junta seções com quase 100% de
    comparecimento e quase 100% para um só candidato.
"""
import collections
import json
import math
import os

L, F = '13', '22'
# Projeção (Mercator) dos pontos de latitude e longitude no desenho do mapa do site (site/mapa.json).
# Os números foram ajustados para que os locais de votação caiam dentro do próprio estado no desenho (98% caem).
LON0, SX, YTOP, SY = -74.0025, 15.612, 5.30245, 15.49875
LONGE = 1.5  # graus: local com coordenada mais longe que isso do centro da cidade é tratado como erro de cadastro
N_SC = 50  # quadradinhos de cada lado nos gráficos de calor
LIMITE_DESVIO = 5  # urnas fora do padrão: mais de 5 desvios-padrão da reta que liga os dois turnos
MIN_VOTOS = 20  # urnas com menos de 20 votos nos dois candidatos variam demais por acaso


def chave(d):
    return d['uf'], str(d['mun']).zfill(5), str(d['z']).zfill(4), str(d['s']).zfill(4)


def projetar(lat, lon):
    y = math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))
    return round((lon - LON0) * SX, 1), round((YTOP - y) * SY, 1)


def _gamma_q(a, x):
    """Probabilidade de cauda da qui-quadrado: Q(a, x), gama incompleta regularizada (Numerical Recipes)."""
    if x <= 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        s = t = 1 / a
        ap = a
        for _ in range(500):
            ap += 1
            t *= x / ap
            s += t
            if abs(t) < abs(s) * 1e-15:
                break
        return 1 - s * math.exp(-x + a * math.log(x) - gln)
    b = x + 1 - a
    c = 1 / 1e-300
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def p_qui2(x, gl):
    return _gamma_q(gl / 2, x / 2)


def ultimo_digito(contagens, minimo=100):
    """Teste do último dígito. O esperado de cada final sai da própria distribuição, suavizada de 10 em 10.

    Por que suavizar: urnas têm tamanho limitado (até ~500 eleitores), então há mais urnas com 120 votos que com 129.
    Isso faz o final 0 aparecer um pouco mais que o 9 sem nenhuma fraude. O esperado corrige esse efeito.
    """
    h = collections.Counter(c for c in contagens if c >= minimo - 5)
    if not h:
        return None
    obs, esp = [0] * 10, [0.0] * 10
    for v in range(minimo, max(h) + 1):
        obs[v % 10] += h[v]
        esp[v % 10] += sum(h[u] for u in range(v - 5, v + 5)) / 10
    n, e = sum(obs), sum(esp)
    if not n:
        return None
    esp = [x * n / e for x in esp]
    q = sum((o - x) ** 2 / x for o, x in zip(obs, esp, strict=True) if x)
    return {'n': n, 'obs': obs, 'esp': [round(x, 1) for x in esp], 'qui2': round(q, 2), 'p': round(p_qui2(q, 9), 4)}


def _validos(v, validos):
    return sum(x for k, x in v.items() if k in validos)


def _soma(secs, validos):
    """{chave: [aptos, comparecimento, válidos, Lula, Flávio]} das seções com votos (inclui as de cédula no exterior)."""
    out = {}
    for d in secs:
        v = d.get('v')
        if not v:
            continue
        out[chave(d)] = (d, [d.get('apt', 0), d.get('comp', 0), _validos(v, validos), v.get(L, 0), v.get(F, 0)])
    return out


def _bin(x, n=N_SC):
    return min(n - 1, max(0, int(x * n)))


def calcular(secs1, secs2, validos1, validos2, locs, secao_local):
    """Devolve (resumo para a página, lista de cidades, locais por estado)."""
    s1, s2 = _soma(secs1, validos1), _soma(secs2, validos2)
    nomes = {}
    cid = collections.defaultdict(lambda: [0] * 10)
    for t, ss in (('1', s1), ('2', s2)):
        o = 0 if t == '1' else 5
        for k, (d, x) in ss.items():
            nomes[k[:2]] = d.get('nm', '')
            c = cid[k[:2]]
            for i in range(5):
                c[o + i] += x[i]

    # cada local de votação: as seções dele em cada turno
    loc_tot = collections.defaultdict(lambda: [0] * 10)
    for t, ss in (('1', s1), ('2', s2)):
        o = 0 if t == '1' else 5
        for k, (_d, x) in ss.items():
            loc = secao_local[t].get(k)
            if loc is None:
                continue
            a = loc_tot[loc['i']]
            for i in range(5):
                a[o + i] += x[i]

    # ponto de cada cidade no mapa: média das escolas, pesada pelo número de eleitores; coordenadas erradas ficam de fora
    por_cid = collections.defaultdict(list)
    for loc in locs:
        if loc['lat'] is not None and loc['lon'] is not None and loc['uf'] != 'ZZ':
            por_cid[(loc['uf'], loc['mun'])].append(loc)
    ponto, descartados = {}, 0
    for k, ls in por_cid.items():
        mla = sorted(x['lat'] for x in ls)[len(ls) // 2]
        mlo = sorted(x['lon'] for x in ls)[len(ls) // 2]
        bons = [x for x in ls if abs(x['lat'] - mla) <= LONGE and abs(x['lon'] - mlo) <= LONGE]
        descartados += len(ls) - len(bons)
        w = [max(1, loc_tot[x['i']][5] or loc_tot[x['i']][0]) for x in bons]
        sw = sum(w)
        ponto[k] = projetar(sum(x['lat'] * p for x, p in zip(bons, w, strict=True)) / sw,
                            sum(x['lon'] * p for x, p in zip(bons, w, strict=True)) / sw)

    cidades = []
    for k in sorted(cid):
        x, y = ponto.get(k, (None, None))
        cidades.append([k[0], k[1], nomes.get(k, ''), x, y] + cid[k])

    locais = collections.defaultdict(list)
    for loc in locs:
        a = loc_tot.get(loc['i'])
        if not a:
            continue
        locais[loc['uf']].append([loc['mun'], loc['nm'], loc['br'], int(loc['z'])] + a)

    return _testes(s1, s2, secao_local, nomes) | {
        'cid_sem_ponto': sum(1 for c in cidades if c[3] is None and c[0] != 'ZZ'),
        'coord_descartadas': descartados}, cidades, dict(locais)


def _testes(s1, s2, secao_local, nomes):
    res = {}
    # 1) valores impossíveis
    res['imp'] = {t: sum(1 for d, x in ss.values()
                         if x[1] > x[0] or sum(d['v'].values()) != x[1] or min(d['v'].values()) < 0)
                  for t, ss in (('1', s1), ('2', s2))}
    res['n'] = {'1': len(s1), '2': len(s2)}

    # 2) a mesma urna nos dois turnos: parte de Lula entre os dois no 1º turno × parte de Lula no 2º turno
    pares = []
    for k in s1.keys() & s2.keys():
        a, b = s1[k][1], s2[k][1]
        if a[3] + a[4] >= MIN_VOTOS and b[3] + b[4] >= MIN_VOTOS:
            pares.append((k, a[3] / (a[3] + a[4]), b[3] / (b[3] + b[4]), a, b))
    pares.sort()
    n = len(pares) or 1
    mx = sum(p[1] for p in pares) / n
    my = sum(p[2] for p in pares) / n
    sxy = sum((p[1] - mx) * (p[2] - my) for p in pares)
    sxx = sum((p[1] - mx) ** 2 for p in pares)
    syy = sum((p[2] - my) ** 2 for p in pares)
    b_ = sxy / sxx if sxx else 1.0
    a_ = my - b_ * mx
    resid = [p[2] - (a_ + b_ * p[1]) for p in pares]
    dp = math.sqrt(sum(r * r for r in resid) / n) or 1.0
    sc = [0] * (N_SC * N_SC)
    sw = collections.Counter()
    fora = []
    for p, r in zip(pares, resid, strict=True):
        sc[_bin(p[2]) * N_SC + _bin(p[1])] += 1
        sw[max(-40, min(40, math.floor((p[2] - p[1]) * 100)))] += 1
        if abs(r) > LIMITE_DESVIO * dp:
            k, a, b = p[0], p[3], p[4]
            loc = secao_local['2'].get(k) or secao_local['1'].get(k)
            fora.append([k[0], nomes.get(k[:2], ''), int(k[2]), int(k[3]), loc['nm'] if loc else '',
                         a[3], a[4], b[3], b[4], round(r / dp, 1)])
    fora.sort(key=lambda x: -abs(x[9]))
    res['cons'] = {'n': len(pares), 'r': round(sxy / math.sqrt(sxx * syy), 4) if sxx and syy else 0, 'a': round(a_, 4), 'b': round(b_, 4),
                   'dp': round(dp * 100, 2), 'lim': LIMITE_DESVIO, 'min': MIN_VOTOS,
                   'k': len(fora), 'kL': sum(1 for x in fora if x[9] > 0), 'kF': sum(1 for x in fora if x[9] < 0),
                   'kv': sum(x[7] + x[8] for x in fora), 'fora': fora[:200],
                   'dentro3': round(sum(1 for r in resid if abs(r) <= 3 * dp) / n, 6)}
    res['sc'] = sc
    res['sw'] = sorted(sw.items())

    # 3) último dígito dos votos de cada candidato, em cada turno
    res['dig'] = {t: {c: ultimo_digito([d['v'].get(c, 0) for d, _x in ss.values()]) for c in (L, F)}
                  for t, ss in (('1', s1), ('2', s2))}

    # 4) impressão digital: comparecimento × parte de Lula nos votos válidos, seção por seção
    res['fp'], res['fpc'] = {}, {}
    for t, ss in (('1', s1), ('2', s2)):
        g = [0] * (N_SC * N_SC)
        canto = []
        for k, (_d, x) in ss.items():
            if not x[0] or not x[2]:
                continue
            tc, pl = x[1] / x[0], x[3] / x[2]
            g[_bin(pl) * N_SC + _bin(tc)] += 1
            if tc >= .95 and (x[3] >= .95 * x[2] or x[4] >= .95 * x[2]):
                loc = secao_local[t].get(k)
                canto.append([k[0], nomes.get(k[:2], ''), int(k[2]), int(k[3]), loc['nm'] if loc else '',
                              x[0], x[1], x[3], x[4], x[2]])
        res['fp'][t] = g
        canto.sort(key=lambda c: (c[0], c[1], c[2], c[3]))
        res['fpc'][t] = {'k': len(canto), 'v': sum(c[9] for c in canto), 'lista': canto[:150]}
    return res


def gravar(pasta, cidades, locais):
    """Arquivos que a página baixa quando precisa: cidades (para o mapa) e locais de votação de cada estado."""
    os.makedirs(os.path.join(pasta, 'mudancas'), exist_ok=True)
    with open(os.path.join(pasta, 'mudancas', 'cidades.json'), 'w', encoding='utf-8') as f:
        json.dump(cidades, f, ensure_ascii=False, separators=(',', ':'))
    for uf, ls in locais.items():
        with open(os.path.join(pasta, 'mudancas', f'locais_{uf}.json'), 'w', encoding='utf-8') as f:
            json.dump(ls, f, ensure_ascii=False, separators=(',', ':'))


def conferir(cidades, oficial):
    """A soma das cidades tem que dar o total oficial de cada turno (comparecimento, Lula e Flávio)."""
    erros = []
    for t, e, o in (('1', '6257', 5 * 0), ('2', '6258', 5)):
        br = oficial[e]['BR']
        soma = [sum(c[5 + o + i] for c in cidades) for i in range(5)]
        for nome, i, ref in (('comparecimento', 1, br['comp']), ('Lula', 3, br['cand'][L]['v']),
                             ('Flávio', 4, br['cand'][F]['v'])):
            if soma[i] != ref:
                erros.append(f'{t}º turno, cidades: {nome} soma {soma[i]}, oficial {ref}')
    return erros
