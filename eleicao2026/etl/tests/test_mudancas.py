"""O que mudou do 1º para o 2º turno: somas por cidade e local, e os testes estatísticos."""
import random

from el_etl import mudancas


def test_p_qui2_valores_conhecidos():
    # tabela da qui-quadrado com 9 graus de liberdade: 16,92 -> 5%; 21,67 -> 1%; 8,34 -> ~50%
    assert abs(mudancas.p_qui2(16.919, 9) - 0.05) < 1e-3
    assert abs(mudancas.p_qui2(21.666, 9) - 0.01) < 1e-3
    assert abs(mudancas.p_qui2(8.343, 9) - 0.5) < 1e-3


def test_ultimo_digito_natural_passa_e_inventado_falha():
    rnd = random.Random(7)
    naturais = [rnd.randint(100, 400) for _ in range(50000)]
    assert mudancas.ultimo_digito(naturais)['p'] > 0.01
    # números "redondos" demais: um quarto termina em 0
    inventados = [x - x % 10 if i % 4 == 0 else x for i, x in enumerate(naturais)]
    assert mudancas.ultimo_digito(inventados)['p'] < 0.001


def test_ultimo_digito_corrige_inclinacao():
    # mais urnas pequenas que grandes: o final 0 aparece mais, sem fraude; o teste não pode acusar
    rnd = random.Random(3)
    v = [int(40 + rnd.expovariate(1 / 90)) for _ in range(300000)]
    assert mudancas.ultimo_digito(v)['p'] > 0.01


def _sec(mun, z, s, apt, comp, lula, flavio, outros=0, br=0):
    v = {'13': lula, '22': flavio, '95': br}
    if outros:
        v['15'] = outros
    return {'uf': 'SP', 'mun': mun, 'nm': 'CIDADE ' + mun, 'z': z, 's': s, 'apt': apt, 'comp': comp, 'v': v}


def test_soma_por_cidade_e_local_e_urna_fora_do_padrao():
    rnd = random.Random(1)
    s1, s2, locs = [], [], []
    for i in range(400):
        l1 = rnd.randint(60, 140)
        s1.append(_sec('00001', '0001', f'{i:04d}', 300, l1 + 100 + 20, l1, 100, outros=20))
        l2 = l1 + 8 + rnd.randint(-3, 3)
        s2.append(_sec('00001', '0001', f'{i:04d}', 300, l2 + 110, l2, 110))
    s2[5]['v']['13'], s2[5]['v']['22'] = 10, 250  # uma urna que muda muito
    s2[5]['comp'] = 260
    for j in range(4):
        locs.append({'uf': 'SP', 'mun': '00001', 'z': '0001', 'l': str(1000 + j), 'nm': f'ESCOLA {j}', 'br': 'CENTRO',
                     'lat': -23.5, 'lon': -46.6, 's1': [f'{i:04d}' for i in range(j, 400, 4)],
                     's2': [f'{i:04d}' for i in range(j, 400, 4)], 'i': j})
    sl = {t: {('SP', '00001', '0001', s): x for x in locs for s in x['s' + t]} for t in '12'}
    res, cid, porlocal = mudancas.calcular(s1, s2, {'13', '22', '15'}, {'13', '22'}, locs, sl)
    assert len(cid) == 1
    c = cid[0]
    assert c[8] == sum(d['v']['13'] for d in s1) and c[14] == sum(d['v']['22'] for d in s2)
    assert c[7] == sum(d['v']['13'] + 100 + 20 for d in s1)  # válidos do 1º turno incluem os outros candidatos
    assert c[3] is not None  # tem ponto no mapa
    assert sum(r[7] for r in porlocal['SP']) == c[8]  # a soma dos locais dá a cidade
    assert res['imp'] == {'1': 0, '2': 0}
    assert res['cons']['k'] == 1 and res['cons']['kF'] == 1 and res['cons']['fora'][0][3] == 5
    assert sum(res['sc']) == res['cons']['n'] == 400


def test_numero_impossivel_e_contado():
    a = _sec('00001', '0001', '0001', 100, 120, 60, 60)  # mais gente que eleitores
    b = _sec('00001', '0001', '0001', 100, 90, 50, 30)  # soma dos votos (80) diferente de quem votou (90)
    res, _c, _l = mudancas.calcular([a], [b], {'13', '22'}, {'13', '22'}, [], {'1': {}, '2': {}})
    assert res['imp'] == {'1': 1, '2': 1}


def test_conferir_com_o_oficial():
    cid = [['SP', '00001', 'X', 1, 1, 10, 8, 8, 5, 3, 10, 9, 9, 6, 3]]
    of = {'6257': {'BR': {'comp': 8, 'cand': {'13': {'v': 5}, '22': {'v': 3}}}},
          '6258': {'BR': {'comp': 9, 'cand': {'13': {'v': 6}, '22': {'v': 3}}}}}
    assert mudancas.conferir(cid, of) == []
    of['6258']['BR']['cand']['13']['v'] = 7
    assert mudancas.conferir(cid, of) == ['2º turno, cidades: Lula soma 6, oficial 7']
