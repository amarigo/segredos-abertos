"""Fuso de cada cidade, hora de Brasília e contas com e sem as urnas que fecharam tarde."""
import random

from el_etl import analisar
from el_etl.analisar import FECHA


def urna(uf, mun, ab, en, v, s='1', comp=None):
    return {'uf': uf, 'mun': mun, 'nm': f'CIDADE {mun}', 'z': '1', 's': s, 'ab': ab, 'en': en, 'v': v,
            'apt': 300, 'comp': comp if comp is not None else sum(v.values())}


def t2(h, m=0, s=0):
    return f'20261025T{h:02d}{m:02d}{s:02d}'


def test_minutos_nos_dois_formatos():
    assert analisar.minutos('2026-10-04 17:15:30') == 17 * 60 + 15.5
    assert analisar.minutos('20261025T171530') == 17 * 60 + 15.5
    assert analisar.minutos('#NULO#') is None and analisar.minutos(None) is None


def test_fuso_padrao_do_estado_e_excecoes():
    secs = [
        urna('SP', '1', t2(8), t2(17), {'13': 1}),
        urna('MT', '2', t2(7), t2(16), {'13': 1}),
        urna('AC', '3', t2(6), t2(15), {'13': 1}),
        urna('AM', '4', t2(7), t2(16), {'13': 1}),   # Manaus: -1h
        urna('AM', '5', t2(6), t2(15), {'13': 1}),   # oeste do Amazonas: hora do Acre, -2h
        urna('PE', '6', t2(9), t2(18), {'13': 1}),   # Fernando de Noronha: +1h
        urna('PE', '7', t2(8), t2(17), {'13': 1}),   # Recife
        urna('MT', '8', t2(6), t2(15), {'13': 1}),   # MT não tem exceção: abertura estranha não muda o fuso
    ]
    f = analisar.fusos(secs)
    assert f[('SP', '1')] == 0 and f[('MT', '2')] == -1 and f[('AC', '3')] == -2
    assert f[('AM', '4')] == -1 and f[('AM', '5')] == -2
    assert f[('PE', '6')] == 1 and f[('PE', '7')] == 0
    assert f[('MT', '8')] == -1


def test_todas_fecham_as_17h_de_brasilia_em_qualquer_fuso():
    secs = [urna('SP', '1', t2(8), t2(17), {'13': 1}), urna('AC', '3', t2(6), t2(15), {'13': 1}),
            urna('AM', '5', t2(6), t2(15), {'22': 1}), urna('PE', '6', t2(9), t2(18), {'22': 1})]
    resumo, urnas = analisar.analisar(secs, {'13', '22'})
    assert {d['enb'] for d in urnas} == {FECHA}
    assert resumo['cut'][FECHA]['BR']['n'] == 4
    assert resumo['cut'][FECHA + 5].get('BR', {}).get('n', 0) == 0


def test_exterior_fica_na_hora_local():
    secs = [urna('ZZ', '99', t2(3), t2(17, 30), {'13': 2})]
    _, [d] = analisar.analisar(secs, {'13', '22'})
    assert d['enb'] == FECHA + 30


def test_cortes_somam_votos_das_urnas_tardias():
    secs = [urna('RJ', '1', t2(8), t2(17, 2), {'13': 10, '22': 20}, s='1'),
            urna('RJ', '1', t2(8), t2(19, 5), {'13': 7, '22': 3, '95': 1}, s='2'),
            urna('RJ', '1', t2(8), t2(17, 20), {'13': 4, '22': 6, '96': 2}, s='3')]
    resumo, urnas = analisar.analisar(secs, {'13', '22'})
    c = resumo['cut'][FECHA + 15]['RJ']
    assert (c['n'], c['13'], c['22'], c['val']) == (2, 11, 9, 20)
    assert resumo['cut'][FECHA + 120]['BR']['n'] == 1
    assert [d['s'] for d in urnas] == ['2', '3', '1']  # mais tarde primeiro


def test_secao_agregada_e_sem_horario_ficam_de_fora_das_contas_de_horario():
    secs = [urna('BA', '1', t2(8), t2(17), {'13': 5}),
            {'uf': 'BA', 'mun': '1', 'nm': 'X', 'z': '1', 's': '9', 'agregada': True},
            urna('BA', '1', None, None, {'13': 3}, s='8')]
    resumo, urnas = analisar.analisar(secs, {'13', '22'})
    assert len(urnas) == 1
    assert resumo['tot']['13'] == 8  # os votos sem horário continuam no total
    assert resumo['missing']['sem_horario'] == 1


def test_propriedade_cortes_nunca_crescem_com_o_horario():
    rnd = random.Random(7)
    secs = [urna(rnd.choice(['SP', 'MG', 'AC']), str(rnd.randint(1, 5)), t2(8),
                 t2(17 + rnd.randint(0, 3), rnd.randint(0, 59)), {'13': rnd.randint(0, 50), '22': rnd.randint(0, 50)},
                 s=str(i)) for i in range(300)]
    resumo, _ = analisar.analisar(secs, {'13', '22'})
    anterior = None
    for c in analisar.CORTES:
        x = resumo['cut'][c].get('BR', {})
        atual = (x.get('n', 0), x.get('13', 0), x.get('22', 0))
        if anterior:
            assert all(a <= b for a, b in zip(atual, anterior))
        anterior = atual
