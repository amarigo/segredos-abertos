"""Conferência do 2º turno com o arquivo oficial (bweb)."""
from el_etl import bweb2


def _d(**kw):
    d = {'uf': 'AC', 'mun': '01074', 'z': '0004', 's': '0001', 'apt': 262, 'comp': 202,
         'v': {'13': 68, '22': 127, '95': 3, '96': 4}, 'ab': '20261025T060001', 'en': '20261025T150152'}
    d.update(kw)
    return d


def test_igual_mesmo_com_formato_de_hora_diferente():
    a = _d()
    b = _d(mun='1074', z='4', s='1', ab='2026-10-25 06:00:01', en='2026-10-25 15:01:52')
    dif, _ = bweb2.comparar({bweb2._k(a): a}, {bweb2._k(b): b})
    assert not dif


def test_qualquer_voto_diferente_aparece():
    a, b = _d(), _d(v={'13': 69, '22': 127, '95': 3, '96': 4})
    dif, ex = bweb2.comparar({bweb2._k(a): a}, {bweb2._k(b): b})
    assert dif == {'votos': 1} and ex[0][1] == 'votos'


def test_secao_que_falta_aparece():
    a = _d()
    dif, _ = bweb2.comparar({bweb2._k(a): a}, {})
    assert dif == {'so_no_site': 1}
