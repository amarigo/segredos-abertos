"""A conferência bloqueia a publicação quando a soma das urnas não bate com o oficial."""
import copy

from el_etl import analisar, validar


def oficial(cands, brancos, nulos, comp):
    return {'cand': {c: {'nm': c, 'sg': 'X', 'v': v} for c, v in cands.items()}, 'brancos': brancos,
            'nulos': nulos, 'comp': comp, 'pst': '100,00'}


SECS = [
    {'uf': 'GO', 'mun': '1', 'nm': 'A', 'z': '1', 's': '1', 'ab': '20261025T070000', 'en': '20261025T160200',
     'apt': 100, 'comp': 90, 'v': {'13': 40, '22': 45, '95': 2, '96': 3}},
    {'uf': 'GO', 'mun': '1', 'nm': 'A', 'z': '1', 's': '2', 'ab': '20261025T070000', 'en': '20261025T163000',
     'apt': 100, 'comp': 80, 'v': {'13': 50, '22': 25, '95': 1, '96': 2, '28': 2}},  # 28: conta como nulo
    {'uf': 'GO', 'mun': '1', 'nm': 'A', 'z': '1', 's': '3', 'agregada': True},
]
OF = {'GO': oficial({'13': 90, '22': 70}, 3, 7, 170), 'BR': oficial({'13': 90, '22': 70}, 3, 7, 170)}


def conferir(secs, of):
    resumo, _ = analisar.analisar(copy.deepcopy(secs), {'13', '22'})
    return validar.conferir('2', secs, of, resumo)


def test_tudo_certo():
    assert conferir(SECS, OF) == []


def test_um_voto_a_mais_bloqueia():
    secs = copy.deepcopy(SECS)
    secs[0]['v']['13'] += 1
    erros = conferir(secs, OF)
    assert any('candidato 13' in e and 'GO' in e for e in erros)
    assert any('candidato 13' in e and 'BR' in e for e in erros)


def test_secao_repetida_bloqueia():
    erros = conferir(SECS + [copy.deepcopy(SECS[0])], OF)
    assert any('repetida' in e for e in erros)


def test_brancos_nulos_e_comparecimento_conferidos():
    of = copy.deepcopy(OF)
    of['GO']['brancos'] += 1
    of['GO']['nulos'] -= 2
    of['GO']['comp'] += 5
    erros = conferir(SECS, of)
    assert any('brancos' in e for e in erros)
    assert any('nulos' in e for e in erros)
    assert any('comparecimento' in e for e in erros)


def test_apuracao_incompleta_bloqueia():
    of = copy.deepcopy(OF)
    of['BR']['pst'] = '99,98'
    assert any('99,98' in e for e in conferir(SECS, of))


def test_estado_que_nao_existe_no_oficial_bloqueia():
    secs = copy.deepcopy(SECS)
    secs[1]['uf'] = 'XX'
    assert any('XX' in e for e in conferir(secs, OF))
