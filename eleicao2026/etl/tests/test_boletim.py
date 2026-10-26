"""Leitura do boletim de urna (.bu, formato ASN.1/BER) e do arquivo bweb do 1º turno."""
import csv
import io
import os
import zipfile

from el_etl import ber, turno1, turno2

AMOSTRAS = os.path.join(os.path.dirname(__file__), 'amostras')


def test_boletim_real_do_tse():
    # Boletim de urna verdadeiro do 2º turno, baixado do site de resultados do TSE.
    with open(os.path.join(AMOSTRAS, 'boletim_2turno.bu'), 'rb') as f:
        r = turno2.ler_bu(f.read())
    assert r['tipo_dados'] == 'secao'
    assert r['ab'] == '20261025T060259' and r['en'] == '20261025T150035'
    assert r['apt'] == 289 and r['comp'] == 194
    assert r['v'] == {'13': 94, '22': 91, '95': 1, '96': 8}
    # quem votou = votos em candidatos + brancos + nulos
    assert sum(r['v'].values()) == r['comp']


def _tlv(tag, valor):
    n = len(valor)
    if n < 128:
        return bytes([tag, n]) + valor
    b = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return bytes([tag, 0x80 | len(b)]) + b + valor


def test_ber_tamanho_longo_e_estrutura():
    texto = b'x' * 300  # tamanho em mais de um byte
    blob = _tlv(0x30, _tlv(0x02, b'\x01\x2c') + _tlv(0x1b, texto))
    [(cls, cons, tag, filhos)] = ber.parse(blob)
    assert (cls, cons, tag) == (0, True, 16)
    assert int.from_bytes(filhos[0][3], 'big') == 300
    assert filhos[1][3] == texto


def test_ber_tag_de_varios_bytes():
    blob = bytes([0x9f, 0x81, 0x01, 0x01, 0x07])  # contexto, tag 129
    [(cls, cons, tag, v)] = ber.parse(blob)
    assert (cls, cons, tag, v) == (2, False, 129, b'\x07')


def _bweb(linhas):
    cab = ['SG_UF', 'CD_MUNICIPIO', 'NM_MUNICIPIO', 'NR_ZONA', 'NR_SECAO', 'CD_CARGO_PERGUNTA', 'NR_VOTAVEL',
           'QT_VOTOS', 'QT_APTOS', 'QT_COMPARECIMENTO', 'CD_TIPO_URNA', 'DT_ABERTURA', 'DT_ENCERRAMENTO',
           'DT_BU_RECEBIDO', 'DS_SECOES_AGREGADAS']
    s = io.StringIO()
    w = csv.writer(s, delimiter=';')
    w.writerow(cab)
    for l in linhas:
        w.writerow([l.get(c, '') for c in cab])
    z = io.BytesIO()
    with zipfile.ZipFile(z, 'w') as zf:
        zf.writestr('bweb.csv', s.getvalue().encode('latin-1'))
    z.seek(0)
    return z


def test_bweb_junta_uma_secao_e_ignora_outros_cargos():
    base = {'SG_UF': 'MG', 'CD_MUNICIPIO': '41238', 'NM_MUNICIPIO': 'BELO HORIZONTE', 'NR_ZONA': '26',
            'NR_SECAO': '10', 'QT_APTOS': '300', 'QT_COMPARECIMENTO': '250', 'CD_TIPO_URNA': '1',
            'DT_ABERTURA': '2026-10-04 08:00:01', 'DT_ENCERRAMENTO': '2026-10-04 17:02:00',
            'DT_BU_RECEBIDO': '2026-10-04 17:30:00', 'DS_SECOES_AGREGADAS': '#NULO#'}
    z = _bweb([dict(base, CD_CARGO_PERGUNTA='1', NR_VOTAVEL='13', QT_VOTOS='120'),
               dict(base, CD_CARGO_PERGUNTA='1', NR_VOTAVEL='22', QT_VOTOS='110'),
               dict(base, CD_CARGO_PERGUNTA='1', NR_VOTAVEL='95', QT_VOTOS='5'),
               dict(base, CD_CARGO_PERGUNTA='3', NR_VOTAVEL='1234', QT_VOTOS='99')])  # governador: fora
    [s] = turno1.ler_zip(z)
    assert s['v'] == {'13': 120, '22': 110, '95': 5}
    assert s['en'] == '2026-10-04 17:02:00' and s['apt'] == 300
