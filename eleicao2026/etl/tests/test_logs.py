"""Registro (log) da urna: hora de cada voto computado, e votos depois das 17h."""
import io
import zipfile

from el_etl import logs


def _zip(arquivos):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return b.getvalue()


def _linha(quando, msg):
    return f'{quando}\tINFO\t02260684\tVOTA\t{msg}\tABCDEF0123456789'


def test_conta_so_votos_computados_do_dia():
    log = '\n'.join([
        _linha('04/10/2026 16:59:59', logs.VOTO),  # outro dia (1º turno): fica de fora
        _linha('25/10/2026 08:00:10', 'Eleitor foi habilitado'),
        _linha('25/10/2026 08:01:00', logs.VOTO),
        _linha('25/10/2026 16:59:59', logs.VOTO),
        _linha('25/10/2026 17:00:00', logs.VOTO),
        _linha('25/10/2026 17:12:30', logs.VOTO),
    ])
    h = logs.votos_do_log(_zip({'logd.dat': log}), '25/10/2026')
    assert h == [8 * 60 + 1, 16 * 60 + 59 + 59 / 60, 17 * 60, 17 * 60 + 12.5]
    r = logs.resumo_urna(h, 0)
    assert r['n'] == 4 and r['d17'] == 2 and r['pm'] == {'0': 1, '12': 1} and r['ult'] == 1032.5


def test_urna_trocada_no_dia_soma_o_registro_da_urna_antiga():
    antiga = _zip({'logd.dat': _linha('25/10/2026 09:00:00', logs.VOTO)})
    nova = '\n'.join([_linha('25/10/2026 13:40:00', logs.VOTO), _linha('25/10/2026 17:01:00', logs.VOTO)])
    h = logs.votos_do_log(_zip({'0227604025102026133917-01.jez': antiga, 'logd.dat': nova}), '25/10/2026')
    assert len(h) == 3


def test_fuso_converte_para_brasilia():
    # Acre: 15h01 locais = 17h01 de Brasília
    r = logs.resumo_urna([15 * 60 + 1, 14 * 60 + 59], -2)
    assert r['d17'] == 1 and r['pm'] == {'1': 1}
