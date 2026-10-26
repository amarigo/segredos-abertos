"""Monta a página: junta os dados oficiais e a análise e põe tudo dentro do modelo (site/)."""
import json
import os
import shutil

AQUI = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(AQUI, '..', '..', 'site')

LEIA_ME_PLANILHAS = """Planilhas com todas as urnas da eleição para presidente de 2026, um arquivo por estado e turno
(2turno_SP.csv, 1turno_MG.csv...). Uma linha por urna. Separador: ponto e vírgula. Codificação: UTF-8.
Fonte: boletins de urna oficiais do TSE. Código: https://github.com/amarigo/segredos-abertos/tree/main/eleicao2026
Colunas:
UF  sigla do estado (ZZ = exterior)
Municipio  nome da cidade
Cod_municipio_TSE  código da cidade no TSE
Zona, Secao  número da zona e da seção eleitoral
Abertura_hora_local  hora em que a urna foi aberta, no relógio local
Encerramento_hora_local  hora em que a urna foi encerrada, no relógio local
Encerramento_horario_Brasilia  a mesma hora, convertida para Brasília (no exterior, fica a hora do país)
Eleitores_aptos  eleitores que podiam votar nessa seção
Comparecimento  eleitores que votaram
Votos_13_Lula, Votos_22_Flavio  votos de cada candidato
Brancos, Nulos  votos em branco e nulos
"""


def titulo(n):
    pequenas = {'DA', 'DE', 'DO', 'DAS', 'DOS', 'E'}
    return ' '.join(w.capitalize() if w not in pequenas else w.lower() for w in n.split())


def dados_site(oficial, resumos, noites=None):
    """O objeto D usado pela página. `noites`: a apuração ao longo da noite, por turno (noite.apuracao)."""
    D = {'cand': {}, 'r': {}, 'h': {}, 'noite': {r: n for r, n in (noites or {}).items() if n}}
    for e, r in (('6257', '1'), ('6258', '2')):
        D['r'][r] = {}
        for uf, rec in oficial[e].items():
            D['r'][r][uf] = {'v': {k: c['v'] for k, c in rec['cand'].items()}, 'apt': rec['aptos'],
                             'ai': rec['aptos_inst'], 'comp': rec['comp'],
                             'abst': rec['abst'], 'br': rec['brancos'], 'nu': rec['nulos'], 'val': rec['validos'],
                             'sec': rec['secoes'], 'atual': rec['atual']}
            for k, c in rec['cand'].items():
                D['cand'][k] = {'nm': titulo(c['nm']), 'sg': c['sg']}
    D['cand']['13']['nm'] = 'Lula'
    D['cand']['22']['nm'] = 'Flávio Bolsonaro'
    for r, s in resumos.items():
        D['h'][r] = {
            'hist': {int(k): v for k, v in s['hist'].items()},
            'cut': {int(c): {uf: [x.get('n', 0), x.get('13', 0), x.get('22', 0), x.get('val', 0), x.get('comp', 0)]
                             for uf, x in v.items()} for c, v in s['cut'].items()},
            'n': s['n_uf'], 'missing': s['missing'],
            'tot': {k: s['tot'].get(k, 0) for k in ('13', '22', '95', '96', 'comp')},
        }
    # JSON ida e volta: chaves numéricas viram texto, igual ao que a página espera
    return json.loads(json.dumps(D))


def pagina(D):
    with open(os.path.join(SITE, 'cabecalho.html'), encoding='utf-8') as f:
        cab = f.read()
    with open(os.path.join(SITE, 'corpo.html'), encoding='utf-8') as f:
        corpo = f.read()
    with open(os.path.join(SITE, 'mapa.json'), encoding='utf-8') as f:
        mapa = f.read()
    corpo = corpo.replace('/*DATA*/', json.dumps(D, ensure_ascii=False, separators=(',', ':'))).replace('/*MAP*/', mapa)
    return ('<!doctype html>\n<html lang="pt-BR">\n<head>\n' + cab + '\n</head>\n<body>\n' + corpo
            + '\n</body>\n</html>\n')


def gravar(saida, D, oficial):
    os.makedirs(os.path.join(saida, 'dados', 'urnas'), exist_ok=True)
    with open(os.path.join(saida, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(pagina(D))
    with open(os.path.join(saida, 'dados', 'numeros_do_site.json'), 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(saida, 'dados', 'resultados_oficiais.json'), 'w', encoding='utf-8') as f:
        json.dump(oficial, f, ensure_ascii=False)
    with open(os.path.join(saida, 'dados', 'urnas', 'LEIA-ME.txt'), 'w', encoding='utf-8') as f:
        f.write(LEIA_ME_PLANILHAS)
    shutil.copy(os.path.join(SITE, 'icone.svg'), os.path.join(saida, 'icone.svg'))
    shutil.copytree(os.path.join(SITE, 'fotos'), os.path.join(saida, 'fotos'), dirs_exist_ok=True)
