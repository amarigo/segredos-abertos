"""Do boletim ao site: monta tudo a partir de dados pequenos e confere o que sai."""
import argparse
import gzip
import json
import os

from el_etl import build


def resultado_tse(e, votos, brancos, nulos, comp, secoes):
    """Arquivo -u.json no formato do TSE, só com os campos que usamos."""
    return {'dg': '25/10/2026', 'hg': '23:27:02',
            'carg': [{'agr': [{'par': [{'sg': 'PT', 'cand': [{'n': '13', 'nmu': 'LULA', 'vap': str(votos['13'])}]},
                                       {'sg': 'PL', 'cand': [{'n': '22', 'nmu': 'FLÁVIO BOLSONARO',
                                                              'vap': str(votos['22'])}]}]}]}],
            'e': {'te': '1000', 'c': str(comp), 'a': str(1000 - comp)},
            'v': {'vb': str(brancos), 'tvn': str(nulos), 'vv': str(votos['13'] + votos['22'])},
            's': {'ts': str(secoes), 'st': str(secoes), 'pst': '100,00'}}


def registros(pasta, regs):
    os.makedirs(os.path.join(pasta, 'brutos', '2turno_log'), exist_ok=True)
    with gzip.open(os.path.join(pasta, 'brutos', '2turno_log', 'SP.jsonl.gz'), 'wt', encoding='utf-8') as f:
        for r in regs:
            f.write(json.dumps(r) + '\n')


REGS = [{'uf': 'SP', 'mun': '71072', 'z': '0001', 's': '0001', 'n': 200, 'd17': 3, 'ult': 1020.9, 'pm': {'0': 3}},
        {'uf': 'SP', 'mun': '71072', 'z': '0001', 's': '0002', 'n': 150, 'd17': 40, 'ult': 1144.5,
         'pm': {'0': 10, '30': 20, '124': 10}}]


def preparar(pasta, mexer=None):
    secs = [
        {'uf': 'SP', 'mun': '71072', 'nm': 'SÃO PAULO', 'z': '0001', 's': '0001', 'ab': '20261025T080000',
         'en': '20261025T170100', 'apt': 300, 'comp': 200, 'v': {'13': 100, '22': 90, '95': 4, '96': 6}},
        {'uf': 'SP', 'mun': '71072', 'nm': 'SÃO PAULO', 'z': '0001', 's': '0002', 'ab': '20261025T080000',
         'en': '20261025T190500', 'apt': 300, 'comp': 150, 'v': {'13': 60, '22': 80, '95': 3, '96': 7}},
    ]
    if mexer:
        mexer(secs)
    os.makedirs(os.path.join(pasta, 'tse'))
    for t, e in (('1', '6257'), ('2', '6258')):
        os.makedirs(os.path.join(pasta, 'brutos', f'{t}turno'))
        with gzip.open(os.path.join(pasta, 'brutos', f'{t}turno', 'SP.jsonl.gz'), 'wt', encoding='utf-8') as f:
            for i, s in enumerate(secs):
                if t == '2':  # hora em que o TSE recebeu o boletim
                    s = dict(s, rec=f'2026-10-25 {18 + i}:00:00')
                f.write(json.dumps(s, ensure_ascii=False) + '\n')
        for uf in ('br', 'sp'):
            with open(os.path.join(pasta, 'tse', f'{uf}-{e}.json'), 'w', encoding='utf-8') as f:
                json.dump(resultado_tse(e, {'13': 160, '22': 170}, 7, 13, 350, 2), f)


def montar(dados, saida):
    a = argparse.Namespace(saida=str(saida), resumo=None)
    return build.cmd_montar(a, dados=str(dados))


def test_site_completo(tmp_path):
    preparar(tmp_path / 'dados')
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 0
    html = (tmp_path / 'site' / 'index.html').read_text(encoding='utf-8')
    assert html.startswith('<!doctype html>') and '/*DATA*/' not in html and '/*MAP*/' not in html
    D = json.loads((tmp_path / 'site' / 'dados' / 'numeros_do_site.json').read_text(encoding='utf-8'))
    assert D['r']['2']['BR']['v'] == {'13': 160, '22': 170}
    assert D['h']['2']['cut'][str(17 * 60 + 15)]['SP'][:3] == [1, 60, 80]  # a urna das 19h05
    planilha = (tmp_path / 'site' / 'dados' / 'urnas' / '2turno_SP.csv').read_text(encoding='utf-8').splitlines()
    assert planilha[1].startswith('SP;SÃO PAULO;71072;0001;0002;08:00:00;19:05:00;19:05:00;300;150;60;80;3;7')
    lista = json.loads((tmp_path / 'site' / 'urnas' / '2_SP.json').read_text(encoding='utf-8'))
    assert lista['cod'] == ['71072'] and lista['r'][0][3] == 19 * 3600 + 5 * 60
    n = D['noite']['2']
    i18, i19 = n['t'].index(18 * 60), n['t'].index(19 * 60)
    assert (n['n'][i18], n['13'][i18], n['22'][i18]) == (1, 100, 90)
    assert (n['n'][i19], n['13'][i19], n['22'][i19]) == (2, 160, 170)  # virada: Flávio passa à frente
    assert '1' not in D['noite']  # 1º turno sem hora de chegada: a página avisa
    assert (tmp_path / 'site' / 'fotos' / '13.jpeg').stat().st_size > 1000
    assert (tmp_path / 'site' / 'fotos' / '22.jpeg').stat().st_size > 1000
    assert 'd17' not in D or '2' not in D['d17']  # sem registros das urnas: a página avisa


def test_votos_depois_das_17h(tmp_path):
    preparar(tmp_path / 'dados')
    registros(tmp_path / 'dados', REGS)
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 0
    D = json.loads((tmp_path / 'site' / 'dados' / 'numeros_do_site.json').read_text(encoding='utf-8'))
    t = D['d17']['2']
    # urnas lidas, com voto depois das 17h, votos depois das 17h, votos nas urnas lidas, Lula, Flávio, válidos
    assert t['uf']['SP'] == [2, 2, 43, 350, 160, 170, 330] and t['uf']['BR'] == t['uf']['SP']
    assert t['conf'] == {'urnas': 2, 'bate': 2} and t['ult'][:4] == ['SP', 'SÃO PAULO', 1, 2]
    assert t['pm']['SP'] == [[0, 13], [30, 20], [124, 10]]
    assert t['top']['SP'][0][4] == 40 and '1' not in D['d17']
    planilha = (tmp_path / 'site' / 'dados' / 'urnas' / '2turno_SP.csv').read_text(encoding='utf-8').splitlines()
    assert planilha[0].endswith(';Votos_depois_17h') and planilha[1].endswith(';40') and planilha[2].endswith(';3')
    lista = json.loads((tmp_path / 'site' / 'urnas' / '2_SP.json').read_text(encoding='utf-8'))
    assert lista['r'][0][9] == 40 and lista['r'][0][10] == round(1144.5 * 60)


def test_registro_diferente_do_boletim_fica_de_fora(tmp_path):
    preparar(tmp_path / 'dados')
    registros(tmp_path / 'dados', [REGS[0], dict(REGS[1], n=149)])
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 0
    t = json.loads((tmp_path / 'site' / 'dados' / 'numeros_do_site.json').read_text(encoding='utf-8'))['d17']['2']
    assert t['conf'] == {'urnas': 2, 'bate': 1, 'diferente': 1} and t['uf']['SP'][:3] == [1, 1, 3]
    assert t['dif'] == [['SP', 'SÃO PAULO', '0001', '0002', 149, 150]]


def test_nao_publica_se_faltar_registro(tmp_path, capsys):
    preparar(tmp_path / 'dados')
    registros(tmp_path / 'dados', REGS[:1])
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 1
    assert 'sem registro lido' in capsys.readouterr().out


def test_nao_publica_se_nao_bater(tmp_path, capsys):
    def um_voto_a_mais(secs):
        secs[0]['v']['22'] += 1
    preparar(tmp_path / 'dados', um_voto_a_mais)
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 1
    assert not (tmp_path / 'site').exists()
    assert 'A CONFERÊNCIA FALHOU' in capsys.readouterr().out


def test_versao_anterior_fica_se_nao_bater(tmp_path):
    preparar(tmp_path / 'dados')
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 0
    antes = (tmp_path / 'site' / 'index.html').read_text(encoding='utf-8')
    with gzip.open(tmp_path / 'dados' / 'brutos' / '2turno' / 'SP.jsonl.gz', 'at', encoding='utf-8') as f:
        f.write(json.dumps({'uf': 'SP', 'mun': '71072', 'nm': 'X', 'z': '0001', 's': '0001',
                            'v': {'13': 1}, 'comp': 1}) + '\n')  # seção repetida
    assert montar(tmp_path / 'dados', tmp_path / 'site') == 1
    assert (tmp_path / 'site' / 'index.html').read_text(encoding='utf-8') == antes
