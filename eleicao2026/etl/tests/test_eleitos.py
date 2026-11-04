"""Eleitos de 2026: leitura do resultado do TSE, conferência com as vagas e com o arquivo de candidatos, ligação com
quem já tem mandato e a página. Tudo com um TSE de mentira, no mesmo formato dos arquivos oficiais."""
import csv
import gzip
import hashlib
import json
import os

import pytest

from el_etl import build, eleitos, pagina_eleitos

VAGAS = {'3': 1, '5': 2, '6': 2, '7': 3, '8': 3}


def cand(sq, n, nm, st, v, dt='01/01/1970', vs=()):
    return {'n': n, 'sqcand': sq, 'nm': nm, 'nmu': nm.split()[0] + ' ' + nm.split()[-1], 'dt': dt, 'dvt': 'Válido',
            'seq': '1', 'e': 's' if st != 'Não eleito' else 'n', 'st': st, 'vap': str(v), 'pvap': '10,00', 'vs': list(vs)}


def arquivo(uf, cargo, e, cands, pst='100,00'):
    return {'ele': e, 'dg': '05/10/2026', 'hg': '12:00:00', 's': {'pst': pst},
            'carg': [{'cd': cargo, 'nmn': eleitos.CARGOS[cargo], 'nv': str(VAGAS[cargo]),
                      'fed': [{'n': '901', 'sg': 'FED X', 'nm': 'FEDERAÇÃO X'}],
                      'agr': [{'n': '1', 'nm': 'JUNTOS', 'tp': 'c', 'com': 'AAA/BBB',
                               'par': [{'n': '10', 'sg': 'AAA', 'nfed': '901', 'cand': cands}]}]}]}


def nome(uf, c, i):
    """Um nome diferente para cada candidato (a comparação de nomes ignora números)."""
    h = hashlib.md5(f'{uf}{c}{i}'.encode()).hexdigest()
    cod = ''.join(chr(65 + int(x, 16)) for x in h)
    return f'ANA {cod[:8]} {cod[8:16]} SOUZA'


def tse_de_mentira(pasta, mudar=None):
    """27 estados; em SP o governador vai ao 2º turno. Devolve as linhas do arquivo de candidatos."""
    res = os.path.join(pasta, 'resultados')
    os.makedirs(res)
    linhas, vagas = [], []
    for uf in eleitos.UFS:
        for c in eleitos.cargos_da_uf(uf):
            cs = []
            for i in range(VAGAS[c] + 1):
                sq = f'{uf}{c}{i:03d}'
                st = ('2º turno' if (uf == 'SP' and c == '3' and i < 2) else
                      'Eleito por QP' if i < VAGAS[c] else 'Não eleito')
                cs.append(cand(sq, f'{c}{i}', nome(uf, c, i), st, 1000 - i,
                               vs=[{'tp': 'v', 'nm': 'VICE', 'nmu': 'VICE FULANO', 'sgp': 'AAA'}] if c == '3' else []))
                linhas.append({'SQ_CANDIDATO': sq, 'SG_UF': uf, 'CD_CARGO': c, 'NR_TURNO': '1',
                               'NM_URNA_CANDIDATO': 'x', 'DS_SIT_TOT_TURNO': st.upper(),
                               'ST_REELEICAO': 'S' if i == 0 else 'N', 'DS_GENERO': 'FEMININO', 'DS_OCUPACAO': 'MÉDICO'})
            if mudar:
                mudar(uf, c, cs)
            with gzip.open(os.path.join(res, f'{uf.lower()}-c{c}-e{eleitos.E1}.json.gz'), 'wt', encoding='utf-8') as f:
                json.dump(arquivo(uf, c, eleitos.E1, cs), f)
            vagas.append({'SG_UF': uf, 'CD_CARGO': c, 'QT_VAGA': str(VAGAS[c])})
    # 2º turno de governador em SP: ganha o SP3001
    with gzip.open(os.path.join(res, f'sp-c3-e{eleitos.E2}.json.gz'), 'wt', encoding='utf-8') as f:
        json.dump(arquivo('SP', '3', eleitos.E2, [cand('SP3000', '30', nome('SP', '3', 0), 'Não eleito', 900),
                                                   cand('SP3001', '31', nome('SP', '3', 1), 'Eleito', 1100)]), f)
    for x in list(linhas):
        if x['SQ_CANDIDATO'] in ('SP3000', 'SP3001'):
            linhas.append({**x, 'NR_TURNO': '2', 'DS_SIT_TOT_TURNO': 'ELEITO' if x['SQ_CANDIDATO'] == 'SP3001' else 'NÃO ELEITO'})
    gravar_csv(pasta, linhas, vagas)
    with open(os.path.join(pasta, 'camara.json'), 'w', encoding='utf-8') as f:
        json.dump([{'id': '204554', 'nome': 'Pessoa Mg', 'nome_civil': nome('MG', '6', 0), 'uf': 'MG',
                    'partido': 'AAA', 'nascimento': '1970-01-01', 'leg': [57]}], f)
    with open(os.path.join(pasta, 'senado.json'), 'w', encoding='utf-8') as f:
        json.dump([{'id': '5672', 'nome': 'Fica', 'nome_civil': 'FICA ATE 2031', 'uf': 'AC', 'partido': 'BBB',
                    'nascimento': '1960-02-02', 'participacao': 'Titular', 'fim_mandato': '2031-01-31'}], f)
    with open(os.path.join(pasta, 'coleta.json'), 'w', encoding='utf-8') as f:
        json.dump({'coletado_em': '2026-11-04 14:00', 'fontes': {}}, f)
    return linhas


def gravar_csv(pasta, linhas, vagas):
    with gzip.open(os.path.join(pasta, 'candidatos.csv.gz'), 'wt', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=eleitos.COLUNAS, delimiter=';', restval='')
        w.writeheader()
        w.writerows(linhas)
    with open(os.path.join(pasta, 'vagas.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=('SG_UF', 'CD_CARGO', 'QT_VAGA'), delimiter=';')
        w.writeheader()
        w.writerows(vagas)


def test_tudo_certo(tmp_path):
    tse_de_mentira(str(tmp_path))
    D, erros = eleitos.montar_eleitos(str(tmp_path))
    assert erros == []
    esperado = sum(VAGAS[c] for uf in eleitos.UFS for c in eleitos.cargos_da_uf(uf))
    assert len(D['eleitos']) == esperado
    gov_sp = [x for x in D['eleitos'] if x['uf'] == 'SP' and x['c'] == '3']
    assert [x['sq'] for x in gov_sp] == ['SP3001'] and gov_sp[0]['e'] == eleitos.E2  # do 2º turno
    gov_mg = next(x for x in D['eleitos'] if x['uf'] == 'MG' and x['c'] == '3')
    assert gov_mg['vs'] == [{'nm': 'Vice Fulano', 'p': 'AAA', 'tp': 'v'}]
    assert D['reeleitos']['6'] == 27 and D['tentaram_e_perderam'] == {'3': 1}  # SP3000 tentou e perdeu no 2º turno
    x = next(x for x in D['eleitos'] if x['sq'] == 'MG6000')
    assert x['hoje']['id'] == 'dep-204554' and x['hoje']['url'].endswith('/204554')
    assert x['col'] == 'JUNTOS' and x['fed'] == 'FED X' and x['foto'].endswith('/6259/fotos/mg/MG6000.jpeg')
    assert [s['id'] for s in D['senado_continua']] == ['sen-5672']
    assert D['vagas']['6'] == 27 * 2


def test_falta_um_eleito_bloqueia(tmp_path):
    def tira(uf, c, cs):
        if uf == 'BA' and c == '6':
            cs[0]['st'] = 'Suplente'
    tse_de_mentira(str(tmp_path), tira)
    _, erros = eleitos.montar_eleitos(str(tmp_path))
    assert any('BA Deputado Federal: 1 eleitos no resultado, 2 vagas' in e for e in erros)
    assert any('eleito no arquivo de candidatos, não no resultado' in e for e in erros)


def test_apuracao_incompleta_bloqueia(tmp_path):
    tse_de_mentira(str(tmp_path))
    p = os.path.join(str(tmp_path), 'resultados', f'rj-c7-e{eleitos.E1}.json.gz')
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        d = json.load(f)
    d['s']['pst'] = '99,80'
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        json.dump(d, f)
    _, erros = eleitos.montar_eleitos(str(tmp_path))
    assert any('RJ cargo 7' in e and '99,80' in e for e in erros)


def test_arquivo_de_candidatos_sem_resultado_bloqueia(tmp_path):
    linhas = tse_de_mentira(str(tmp_path))
    vagas = eleitos.ler_csv(os.path.join(str(tmp_path), 'vagas.csv'))
    gravar_csv(str(tmp_path), [{**x, 'DS_SIT_TOT_TURNO': '#NULO#'} for x in linhas], vagas)
    _, erros = eleitos.montar_eleitos(str(tmp_path))
    assert any('ainda não traz quem foi eleito' in e for e in erros)


def test_falta_um_estado_bloqueia(tmp_path):
    tse_de_mentira(str(tmp_path))
    os.remove(os.path.join(str(tmp_path), 'resultados', f'to-c5-e{eleitos.E1}.json.gz'))
    _, erros = eleitos.montar_eleitos(str(tmp_path))
    assert 'TO: falta o resultado de Senador' in erros


@pytest.mark.parametrize('tse,casa,igual', [
    ('JOSE ABILIO SILVA DE SANTANA', 'JOSÉ ABÍLIO SILVA DE SANTANA', True),
    ('JOSE ABILIO SILVA DE SANTANA', 'JOSE ABILIO SANTANA', True),   # Câmara encurta o nome civil
    ('JOSE ABILIO SILVA DE SANTANA', 'JOSE CARLOS SILVA', False),
    ('MARIA DA SILVA', 'MARIA DA SILVA', True),
    ('OMAR JOSE ABDELAZIZ', 'Omar José Abdel Aziz', True),            # sobrenome junto ou separado
    ('PEDRO HENRIQUE DE ANDRADE LIMA CARNEIRO CAMPOS', 'PEDRO HENRIQUE DE A. L. C. CAMPOS', True),  # abreviado
    ('CÁSSIO MURILLO GALDINO DE ARAÚJO', 'CÁSSIO MURILO GALDINO DE ARAÚJO', True),  # uma letra a mais
    ('ANDERSON FERREIRA RODRIGUES', 'ANDRÉ FERREIRA RODRIGUES', False),  # irmãos gêmeos: outro primeiro nome
    ('FABRICIO BEVILACQUA FURLAN', 'CRISTIANO BEVILACQUA FURLAN', False),
    ('ERIKA HILTON', 'ERIKA SANTOS SILVA', False),  # nome social: sem como confirmar, não liga
])
def test_mesma_pessoa(tse, casa, igual):
    assert eleitos.mesma_pessoa(tse, '13/02/1965', casa, '1965-02-13') is igual
    assert eleitos.mesma_pessoa(tse, '14/02/1965', casa, '1965-02-13') is False  # outro dia de nascimento


def test_pagina(tmp_path):
    tse_de_mentira(str(tmp_path / 'el'))
    D, _ = eleitos.montar_eleitos(str(tmp_path / 'el'))
    pagina_eleitos.gravar(str(tmp_path / 'site'), D, [])
    html = (tmp_path / 'site' / 'eleitos' / 'index.html').read_text(encoding='utf-8')
    assert '<title>Quem assume em 2027' in html and '"sq":"MG6000"' in html and '/*DATA*/' not in html
    linhas = (tmp_path / 'site' / 'eleitos' / 'dados' / 'eleitos.csv').read_text(encoding='utf-8').splitlines()
    assert len(linhas) == len(D['eleitos']) + 1 and linhas[0].startswith('cargo;uf;numero')
    assert any('Deputado federal (AAA-MG)' in x for x in linhas)


def test_pagina_em_conferencia_sem_numeros(tmp_path):
    def tira(uf, c, cs):
        if uf == 'BA' and c == '6':
            cs[0]['st'] = 'Suplente'
    tse_de_mentira(str(tmp_path / 'el'), tira)
    assert build.montar_eleitos(str(tmp_path / 'el'), str(tmp_path / 'site')) is False
    html = (tmp_path / 'site' / 'eleitos' / 'index.html').read_text(encoding='utf-8')
    assert 'JSON.parse' in html and '>null</script>' in html
    assert not (tmp_path / 'site' / 'eleitos' / 'dados' / 'eleitos.json').exists()


def test_reeleicao_sem_o_campo_do_tse_usa_camara_e_senado(tmp_path):
    """Em 2026 o TSE publicou ST_REELEICAO vazio ('#NE'): vale quem está no exercício do mesmo cargo hoje."""
    linhas = tse_de_mentira(str(tmp_path))
    vagas = eleitos.ler_csv(os.path.join(str(tmp_path), 'vagas.csv'))
    gravar_csv(str(tmp_path), [{**x, 'ST_REELEICAO': '#NE'} for x in linhas], vagas)
    with open(os.path.join(str(tmp_path), 'camara.json'), 'w', encoding='utf-8') as f:
        json.dump([{'id': '1', 'nome': 'A', 'nome_civil': nome('MG', '6', 0), 'uf': 'MG', 'partido': 'AAA',
                    'nascimento': '1970-01-01', 'leg': [57], 'em_exercicio': True},
                   {'id': '2', 'nome': 'B', 'nome_civil': nome('SP', '6', 1), 'uf': 'SP', 'partido': 'AAA',
                    'nascimento': '1970-01-01', 'leg': [57]},  # foi suplente e saiu: não é reeleito
                   {'id': '3', 'nome': 'C', 'nome_civil': 'QUEM NAO VOLTA', 'uf': 'RJ', 'partido': 'AAA',
                    'nascimento': '1980-01-01', 'leg': [57], 'em_exercicio': True}], f)
    D, erros = eleitos.montar_eleitos(str(tmp_path))
    assert erros == [] and D['fonte_reeleicao'] == 'camara_senado'
    re = {x['sq']: x['re'] for x in D['eleitos']}
    assert re['MG6000'] == 'S' and re['SP6001'] == 'N' and re['BA6000'] == 'N'
    assert re['MG3000'] == '' and re['MG7000'] == ''  # governador e estadual: sem fonte oficial, sem marca
    assert D['reeleitos'] == {'6': 1} and D['nao_voltam']['6'] == 1  # o deputado 3 está no cargo e não foi eleito
