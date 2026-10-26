"""Apuração ao longo da noite: a parcial de cada horário sai da hora em que o TSE recebeu cada boletim."""
import datetime

from el_etl import noite

DIA = datetime.date(2026, 10, 25)


def secao(uf, rec, l, f, outros=0):
    return {'uf': uf, 'rec': rec, 'v': {'13': l, '22': f, '95': 1, '96': 2, '99': outros}}


def test_parcial_acumulada_e_virada():
    secs = [
        secao('SP', '2026-10-25 17:02:00', 10, 30),
        secao('SP', '2026-10-25 17:04:59', 10, 30),
        secao('BA', '2026-10-25 17:12:00', 50, 5),
        secao('BA', '2026-10-26 00:03:00', 40, 5),  # depois da meia-noite
        {'uf': 'BA', 'mun': 'x'},  # seção agregada: sem votos, fica de fora
    ]
    n = noite.apuracao(secs, {'13', '22'}, DIA)
    assert n['t'][0] == 17 * 60 and n['t'][-1] >= 24 * 60 + 3
    assert n['n'][:4] == [0, 2, 2, 3]  # 17h00, 17h05, 17h10, 17h15
    assert n['13'][1] == 20 and n['22'][1] == 60  # Flávio na frente às 17h05
    assert n['13'][3] == 70 and n['22'][3] == 65  # Lula na frente às 17h15: virada
    assert n['val'][-1] == 180  # votos válidos = só candidatos (brancos e nulos fora)
    assert n['uf'] == {'SP': n['uf']['SP'], 'BA': n['uf']['BA']} and n['uf']['BA'][-1] == 2
    assert n['tot_uf'] == {'SP': 2, 'BA': 2} and n['tot'] == 4 and n['sem_hora'] == 0


def test_soma_final_bate_com_as_urnas():
    secs = [secao('MG', f'2026-10-25 {18 + i % 5}:{i % 60:02d}:00', i, 2 * i) for i in range(1, 200)]
    n = noite.apuracao(secs, {'13', '22'}, DIA)
    assert n['13'][-1] == sum(range(1, 200)) and n['22'][-1] == 2 * sum(range(1, 200))
    assert all(a <= b for a, b in zip(n['n'], n['n'][1:]))  # só cresce


def test_secao_sem_hora_fica_fora_e_e_contada():
    secs = [secao('RJ', '2026-10-25 19:00:00', 5, 5), secao('RJ', None, 7, 7), secao('RJ', '#NULO#', 1, 1)]
    n = noite.apuracao(secs, {'13', '22'}, DIA)
    assert n['sem_hora'] == 2 and n['tot'] == 3 and n['13'][-1] == 5


def test_chegada_antes_das_17h_entra_no_primeiro_ponto():
    # exterior: urnas que fecham cedo pelo horário de Brasília
    n = noite.apuracao([secao('ZZ', '2026-10-25 09:30:00', 3, 4)], {'13', '22'}, DIA)
    assert n['t'][0] == 17 * 60 and n['n'][0] == 1
