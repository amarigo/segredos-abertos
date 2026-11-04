"""Quem foi eleito em 2026 para o mandato que começa em 2027: governadores, senadores, deputados federais, estaduais e
distritais, com partido, coligação, votos, foto e link para o original.

De onde vem cada dado (API primeiro):
1. Resultado de cada cargo em cada estado: arquivos JSON do site de resultados do TSE (resultados.tse.jus.br), os
   mesmos que o aplicativo oficial de resultados lê, e os mesmos que o site da eleição para presidente já usa. A
   eleição estadual de 2026 é a 6259 (1º turno) e a 6260 (2º turno de governador), conforme a lista oficial de
   eleições do site (comum/config/ele-c.json). A API do DivulgaCandContas (divulgacandcontas.tse.jus.br/divulga/rest)
   recusa acesso automático (HTTP 403 "Access Denied", conferido do GitHub Actions em 04/11/2026), por isso não é usada.
2. Segunda fonte, para conferir: arquivos de dados abertos do TSE, achados pela API do Portal de Dados Abertos
   (CKAN, dadosabertos.tse.jus.br/api/3): "Candidatos" (situação final de cada candidato e se ele concorreu à
   reeleição, campo ST_REELEICAO) e "Vagas" (quantas cadeiras cada cargo tem em cada estado). Não há API com esses
   campos: o portal só publica os arquivos CSV dentro de ZIP.
3. Quem já tem mandato hoje: API da Câmara (/deputados, /deputados/{id}) e API do Senado (/senador/lista/atual,
   /senador/{codigo}). Liga o eleito ao que o site já mostra de gastos e votos desta legislatura.

Nada aqui guarda CPF, e-mail ou título de eleitor: do arquivo de candidatos ficam só as colunas abaixo (COLUNAS).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import tempfile
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict

import requests

E1, E2 = '6259', '6260'  # eleição estadual de 2026: 1º turno (4/10) e 2º turno de governador (25/10)
UFS = ('AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO').split()
CARGOS = {'3': 'Governador', '5': 'Senador', '6': 'Deputado Federal', '7': 'Deputado Estadual', '8': 'Deputado Distrital'}
ORDEM = ('3', '5', '6', '7', '8')

RES = 'https://resultados.tse.jus.br/oficial/ele2026/{e}/dados/{u}/{u}-c{c:0>4}-e{e:0>6}-u.json'
FOTO = 'https://resultados.tse.jus.br/oficial/ele2026/{e}/fotos/{u}/{sq}.jpeg'
APP_TSE = 'https://resultados.tse.jus.br/oficial/app/index.html#/eleicao;e=e{e};uf={u};ufbu={u}/resultados/cargo/{c}'
CKAN = 'https://dadosabertos.tse.jus.br/api/3/action/package_show?id={id}'
PACOTE_CAND = 'candidatos-2026'
ARQ_CAND = 'consulta_cand_2026.zip'
ARQ_VAGAS = 'consulta_vagas_2026.zip'
# endereços conhecidos, usados só se a API do portal não responder
RESERVA = {ARQ_CAND: 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip',
           ARQ_VAGAS: 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2026.zip'}
PAGINA_CAND = 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026'

CAMARA = 'https://dadosabertos.camara.leg.br/api/v2'
SENADO = 'https://legis.senado.leg.br/dadosabertos'
PERFIL_CAMARA = 'https://www.camara.leg.br/deputados/{id}'
PERFIL_SENADO = 'https://www25.senado.leg.br/web/senadores/senador/-/perfil/{id}'

# colunas que guardamos do arquivo de candidatos (sem CPF, e-mail, título de eleitor)
COLUNAS = ('SQ_CANDIDATO', 'SG_UF', 'CD_CARGO', 'NR_TURNO', 'NM_CANDIDATO', 'NM_URNA_CANDIDATO', 'SG_PARTIDO',
           'SG_FEDERACAO', 'NM_COLIGACAO', 'DS_COMPOSICAO_COLIGACAO', 'DT_NASCIMENTO', 'DS_GENERO', 'DS_GRAU_INSTRUCAO',
           'DS_OCUPACAO', 'DS_SITUACAO_CANDIDATURA', 'DS_SIT_TOT_TURNO', 'ST_REELEICAO')

S = requests.Session()
S.headers['User-Agent'] = 'segredos-abertos/1.0 (portal de transparencia; github.com/amarigo/segredos-abertos)'


# ------------------------------------------------------------------ baixar (só no GitHub Actions: precisa do TSE)

def _get(url, ok404=False, tentativas=5, **kw):
    for i in range(tentativas):
        try:
            r = S.get(url, timeout=kw.pop('timeout', 60), **kw)
            if ok404 and r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(2 ** i)


def cargos_da_uf(uf):
    return ('3', '5', '6', '8' if uf == 'DF' else '7')


def baixar_resultados(pasta):
    """Resultado de cada cargo em cada estado (1º turno) e o 2º turno de governador onde houve. Guarda como veio, em .gz."""
    os.makedirs(pasta, exist_ok=True)
    n = 0
    for uf in UFS:
        for e, cargos in ((E1, cargos_da_uf(uf)), (E2, ('3',))):
            for c in cargos:
                r = _get(RES.format(e=e, u=uf.lower(), c=c), ok404=(e == E2))
                if r is None:
                    continue  # sem 2º turno neste estado
                with gzip.open(os.path.join(pasta, f'{uf.lower()}-c{c}-e{e}.json.gz'), 'wb', compresslevel=9) as f:
                    f.write(r.content)
                n += 1
    return n


def url_arquivo(nome):
    """Endereço oficial do arquivo, achado pela API do Portal de Dados Abertos do TSE (CKAN)."""
    try:
        for res in _get(CKAN.format(id=PACOTE_CAND), tentativas=3).json()['result']['resources']:
            if (res.get('url') or '').endswith('/' + nome):
                return res['url']
    except (requests.RequestException, KeyError, ValueError):
        pass
    return RESERVA[nome]


def _csvs_do_zip(conteudo, prefixo):
    """Linhas dos CSV do ZIP do TSE (latin-1, ';'). Usa o arquivo _BRASIL quando existe; senão, junta os estados."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = [n for n in z.namelist() if n.lower().endswith('.csv') and os.path.basename(n).startswith(prefixo)]
    br = [n for n in nomes if 'BRASIL' in n.upper()]
    for nome in br or nomes:
        with z.open(nome) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding='latin-1', newline=''), delimiter=';')


def baixar_candidatos(pasta):
    """Do arquivo de candidatos, guarda só os cargos estaduais e federais (sem presidente) e só as COLUNAS."""
    url = url_arquivo(ARQ_CAND)
    r = _get(url, timeout=600)
    linhas = []
    for row in _csvs_do_zip(r.content, 'consulta_cand_2026'):
        if row.get('CD_CARGO') in CARGOS:
            linhas.append({k: (row.get(k) or '').strip() for k in COLUNAS})
    if not linhas:
        raise RuntimeError('arquivo de candidatos sem nenhuma linha de governador, senador ou deputado')
    with gzip.open(os.path.join(pasta, 'candidatos.csv.gz'), 'wt', encoding='utf-8', newline='', compresslevel=9) as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=';')
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda x: (x['SG_UF'], x['CD_CARGO'], x['SQ_CANDIDATO'], x['NR_TURNO'])))
    return url, r.headers.get('last-modified', ''), len(linhas)


def baixar_vagas(pasta):
    url = url_arquivo(ARQ_VAGAS)
    r = _get(url, timeout=120)
    out = []
    for row in _csvs_do_zip(r.content, 'consulta_vagas_2026'):
        if row.get('CD_CARGO') in CARGOS:
            qt = row.get('QT_VAGA') or row.get('QT_VAGAS') or ''
            out.append({'SG_UF': row['SG_UF'].strip(), 'CD_CARGO': row['CD_CARGO'].strip(), 'QT_VAGA': qt.strip()})
    if not out:
        raise RuntimeError('arquivo de vagas sem cargos estaduais e federais')
    with open(os.path.join(pasta, 'vagas.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=('SG_UF', 'CD_CARGO', 'QT_VAGA'), delimiter=';')
        w.writeheader()
        w.writerows(sorted(out, key=lambda x: (x['SG_UF'], x['CD_CARGO'])))
    return url, r.headers.get('last-modified', ''), len(out)


def baixar_camara(pasta, legislaturas=(57, 58)):
    """Deputados federais das legislaturas (a 58ª só existe a partir de fevereiro de 2027), com nome civil e nascimento."""
    vistos = {}
    for leg in legislaturas:
        url = f'{CAMARA}/deputados?idLegislatura={leg}&itens=100&ordem=ASC&ordenarPor=nome'
        while url:
            try:
                d = _get(url, tentativas=6 if leg == legislaturas[0] else 2, headers={'Accept': 'application/json'}).json()
            except requests.RequestException:
                if leg == legislaturas[0]:
                    raise
                break  # legislatura que ainda não começou (a API responde erro ou lista vazia)
            for x in d['dados']:
                vistos.setdefault(str(x['id']), {'id': str(x['id']), 'nome': x['nome'], 'uf': x['siglaUf'],
                                                 'partido': x['siglaPartido'], 'leg': [] })['leg'].append(leg)
            url = next((ln['href'] for ln in d.get('links', []) if ln.get('rel') == 'next'), None)
    for i, dep in vistos.items():
        det = _get(f'{CAMARA}/deputados/{i}', headers={'Accept': 'application/json'}).json()['dados']
        dep['nome_civil'] = det.get('nomeCivil') or ''
        dep['nascimento'] = det.get('dataNascimento') or ''
        dep['situacao'] = (det.get('ultimoStatus') or {}).get('situacao') or ''
    lista = sorted(vistos.values(), key=lambda x: x['id'])
    with open(os.path.join(pasta, 'camara.json'), 'w', encoding='utf-8') as f:
        json.dump(lista, f, ensure_ascii=False, indent=0)
    return len(lista)


def baixar_senado(pasta):
    """Senadores em exercício hoje, com nome completo, nascimento e até quando vai o mandato."""
    d = _get(f'{SENADO}/senador/lista/atual.json', headers={'Accept': 'application/json'}).json()
    out = []
    for p in d['ListaParlamentarEmExercicio']['Parlamentares']['Parlamentar']:
        ide, man = p['IdentificacaoParlamentar'], p.get('Mandato') or {}
        cod = ide['CodigoParlamentar']
        det = _get(f'{SENADO}/senador/{cod}.json', headers={'Accept': 'application/json'}).json()
        basico = det['DetalheParlamentar']['Parlamentar'].get('DadosBasicosParlamentar') or {}
        fim = (man.get('SegundaLegislaturaDoMandato') or {}).get('DataFim') or ''
        out.append({'id': cod, 'nome': ide['NomeParlamentar'], 'nome_civil': ide.get('NomeCompletoParlamentar') or '',
                    'uf': ide.get('UfParlamentar') or man.get('UfParlamentar') or '',
                    'partido': ide.get('SiglaPartidoParlamentar') or '', 'nascimento': basico.get('DataNascimento') or '',
                    'participacao': man.get('DescricaoParticipacao') or '', 'fim_mandato': fim})
    out.sort(key=lambda x: x['id'])
    with open(os.path.join(pasta, 'senado.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    return len(out)


def baixar(pasta):
    """Baixa tudo para `pasta` (eleicao2026/dados/eleitos). Grava o que veio de cada fonte em coleta.json."""
    os.makedirs(pasta, exist_ok=True)
    agora = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=-3)))
    info = {'coletado_em': agora.strftime('%Y-%m-%d %H:%M'), 'fontes': {}}
    info['fontes']['resultados'] = {'url': 'https://resultados.tse.jus.br/oficial/app/index.html',
                                    'arquivos': baixar_resultados(os.path.join(pasta, 'resultados'))}
    print('resultados oficiais: ok', flush=True)
    u, lm, n = baixar_candidatos(pasta)
    info['fontes']['candidatos'] = {'url': u, 'pagina': PAGINA_CAND, 'publicado': lm, 'linhas': n}
    print(f'candidatos: {n} linhas ({lm})', flush=True)
    u, lm, n = baixar_vagas(pasta)
    info['fontes']['vagas'] = {'url': u, 'pagina': PAGINA_CAND, 'publicado': lm, 'linhas': n}
    print(f'vagas: {n} linhas', flush=True)
    # Câmara e Senado só servem para ligar o eleito ao mandato de hoje: se a API cair, fica a última cópia baixada
    for nome, fn, url in (('camara', baixar_camara, CAMARA + '/deputados'), ('senado', baixar_senado, SENADO + '/senador/lista/atual')):
        try:
            info['fontes'][nome] = {'url': url, 'n': fn(pasta)}
            print(f'{nome}: ok ({info["fontes"][nome]["n"]})', flush=True)
        except (requests.RequestException, KeyError, ValueError) as e:
            if not os.path.exists(os.path.join(pasta, nome + '.json')):
                raise
            anterior = json.load(open(os.path.join(pasta, 'coleta.json'), encoding='utf-8')) \
                if os.path.exists(os.path.join(pasta, 'coleta.json')) else {}
            info['fontes'][nome] = {**anterior.get('fontes', {}).get(nome, {'url': url}), 'aviso': f'API fora do ar em '
                                    f"{info['coletado_em']}; usada a cópia anterior"}
            print(f'::warning title=Eleitos 2026::{nome}: {e}; usada a última cópia baixada', flush=True)
    with open(os.path.join(pasta, 'coleta.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


# ------------------------------------------------------------------ ler (sem internet)

def eleito(st):
    """Situação do TSE: 'Eleito', 'Eleito por QP', 'Eleito por média' são eleitos; '2º turno', 'Suplente' não."""
    return (st or '').strip().lower().startswith('eleito')


def titulo(n):
    pequenas = {'DA', 'DE', 'DO', 'DAS', 'DOS', 'E', 'D'}
    return ' '.join(w.capitalize() if w not in pequenas else w.lower() for w in (n or '').split())


def ler_resultado(d, e, uf):
    """De um arquivo -u.json do TSE: um item por candidato, com o que a página usa, e o resumo da apuração."""
    carg = d['carg'][0]
    feds = {f['n']: f for f in carg.get('fed', [])}
    cands = []
    for agr in carg.get('agr', []):
        coligacao = agr.get('nm', '') if agr.get('tp') == 'c' else ''
        for p in agr.get('par', []):
            fed = feds.get(p.get('nfed') or '')
            for c in p.get('cand', []):
                cands.append({
                    'sq': c['sqcand'], 'n': c['n'], 'nm': c.get('nm', ''), 'nmu': c.get('nmu', ''), 'dt': c.get('dt', ''),
                    'p': p.get('sg', ''), 'fed': (fed or {}).get('sg', ''), 'col': coligacao, 'comp': agr.get('com', ''),
                    'v': int(c.get('vap') or 0), 'pv': c.get('pvap', ''), 'st': c.get('st', ''), 'dvt': c.get('dvt', ''),
                    'vs': [{'nm': titulo(x.get('nmu') or x.get('nm')), 'p': x.get('sgp', ''), 'tp': x.get('tp', '')}
                           for x in c.get('vs', [])],
                    'e': e, 'uf': uf, 'c': str(int(carg['cd'])),
                })
    apur = {'pst': d.get('s', {}).get('pst', ''), 'dg': f"{d.get('dg', '')} {d.get('hg', '')}".strip(),
            'cargo': str(int(carg['cd'])), 'vagas_arq': carg.get('nv', ''), 'e': e, 'uf': uf}
    return cands, apur


def ler_resultados(pasta):
    """Todos os candidatos dos arquivos baixados e o resumo de cada arquivo."""
    todos, apur = [], []
    for nome in sorted(os.listdir(pasta)):
        m = re.match(r'([a-z]{2})-c(\d+)-e(\d+)\.json\.gz$', nome)
        if not m:
            continue
        with gzip.open(os.path.join(pasta, nome), 'rt', encoding='utf-8') as f:
            c, a = ler_resultado(json.load(f), m.group(3), m.group(1).upper())
        todos += c
        apur.append(a)
    return todos, apur


def ler_csv(caminho):
    abrir = gzip.open if caminho.endswith('.gz') else open
    with abrir(caminho, 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def normal(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().upper()
    return ' '.join(re.sub(r'[^A-Z ]', ' ', s).split())


def _data_iso(s):
    """'30/04/1981' ou '1981-04-30' -> '1981-04-30'."""
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', s or '')
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else (s or '')[:10]


def mesma_pessoa(nome_tse, nasc_tse, nome_casa, nasc_casa):
    """Mesmo dia de nascimento e o mesmo nome civil (ou o mesmo primeiro nome e pelo menos mais dois nomes iguais:
    a Câmara às vezes encurta o nome civil)."""
    if not nasc_tse or _data_iso(nasc_tse) != _data_iso(nasc_casa):
        return False
    a, b = normal(nome_tse).split(), normal(nome_casa).split()
    if not a or not b:
        return False
    if a == b:
        return True
    return a[0] == b[0] and len(set(a) & set(b)) >= 3


def ligar(eleitos, camara, senado):
    """Para cada eleito, quem ele é hoje no Congresso (se já tem mandato): casa, id do site, link do perfil oficial."""
    por_nasc = defaultdict(list)
    for d in camara:
        por_nasc[_data_iso(d.get('nascimento'))].append(('camara', d))
    for s in senado:
        por_nasc[_data_iso(s.get('nascimento'))].append(('senado', s))
    for el in eleitos:
        achados = [(casa, x) for casa, x in por_nasc.get(_data_iso(el['dt']), [])
                   if mesma_pessoa(el['nm'], el['dt'], x.get('nome_civil') or x['nome'], x.get('nascimento'))]
        if len(achados) == 1:
            casa, x = achados[0]
            el['hoje'] = {'casa': casa, 'id': ('dep-' if casa == 'camara' else 'sen-') + x['id'], 'nome': x['nome'],
                          'partido': x.get('partido', ''), 'uf': x.get('uf', ''),
                          'url': (PERFIL_CAMARA if casa == 'camara' else PERFIL_SENADO).format(id=x['id']),
                          **({'leg': x['leg']} if 'leg' in x else {}),
                          **({'fim': x['fim_mandato']} if x.get('fim_mandato') else {})}
    return eleitos


def montar_eleitos(pasta):
    """Lê tudo o que foi baixado e devolve (dados da página, erros da conferência)."""
    cands, apur = ler_resultados(os.path.join(pasta, 'resultados'))
    cand_csv = ler_csv(os.path.join(pasta, 'candidatos.csv.gz'))
    vagas = ler_csv(os.path.join(pasta, 'vagas.csv'))
    with open(os.path.join(pasta, 'camara.json'), encoding='utf-8') as f:
        camara = json.load(f)
    with open(os.path.join(pasta, 'senado.json'), encoding='utf-8') as f:
        senado = json.load(f)
    with open(os.path.join(pasta, 'coleta.json'), encoding='utf-8') as f:
        coleta = json.load(f)

    # governador: quem foi ao 2º turno sai do arquivo do 2º turno (6260)
    tem_2t = {c['uf'] for c in cands if c['e'] == E2}
    eleitos = [c for c in cands if eleito(c['st']) and not (c['c'] == '3' and c['e'] == E1 and c['uf'] in tem_2t)]
    eleitos += [c for c in cands if c['c'] == '3' and c['e'] == E2 and eleito(c['st'])
                and not any(x['c'] == '3' and x['uf'] == c['uf'] and x['sq'] == c['sq'] for x in eleitos)]
    erros = conferir(eleitos, cands, apur, cand_csv, vagas)

    info_csv = {r['SQ_CANDIDATO']: r for r in cand_csv}
    ligar(eleitos, camara, senado)
    lista = []
    for el in sorted(eleitos, key=lambda x: (ORDEM.index(x['c']), x['uf'], -x['v'])):
        r = info_csv.get(el['sq'], {})
        item = {'sq': el['sq'], 'c': el['c'], 'uf': el['uf'], 'n': el['n'], 'nm': titulo(el['nmu']),
                'nc': titulo(el['nm']), 'p': el['p'], 'fed': el['fed'], 'col': el['col'], 'comp': el['comp'],
                'v': el['v'], 'pv': el['pv'], 'st': el['st'], 'e': el['e'],
                'foto': FOTO.format(e=el['e'], u=el['uf'].lower(), sq=el['sq']),
                'tse': APP_TSE.format(e=el['e'], u=el['uf'].lower(), c=el['c']),
                're': r.get('ST_REELEICAO', ''), 'g': titulo(r.get('DS_GENERO', '')),
                'oc': r.get('DS_OCUPACAO', '').capitalize(), 'gi': r.get('DS_GRAU_INSTRUCAO', '').capitalize()}
        if el['dvt'] and not el['dvt'].lower().startswith('válido'):
            item['dvt'] = el['dvt']  # votos ainda sub judice ou anulados: a página avisa
        if el['vs']:
            item['vs'] = el['vs']
        if el.get('hoje'):
            item['hoje'] = el['hoje']
        lista.append(item)

    # Senado de 2027: os 54 eleitos agora e os 27 eleitos em 2022, cujo mandato vai até janeiro de 2031
    continuam = [{'id': 'sen-' + s['id'], 'nm': s['nome'], 'p': s['partido'], 'uf': s['uf'], 'fim': s['fim_mandato'],
                  'part': s['participacao'], 'url': PERFIL_SENADO.format(id=s['id'])}
                 for s in senado if s.get('fim_mandato', '')[:4] == '2031']
    # quem tentou a reeleição (ST_REELEICAO = S) e não se elegeu, por cargo: só a contagem
    sq_eleitos = {x['sq'] for x in lista}
    tentou = Counter(r['CD_CARGO'] for r in {r['SQ_CANDIDATO']: r for r in cand_csv}.values()
                     if r.get('ST_REELEICAO') == 'S' and r['SQ_CANDIDATO'] not in sq_eleitos)
    reeleitos = Counter(x['c'] for x in lista if x['re'] == 'S')
    vaga = {(v['SG_UF'], v['CD_CARGO']): int(v['QT_VAGA'] or 0) for v in vagas}
    dg = sorted({a['dg'] for a in apur if a['dg']})
    D = {
        'coletado_em': coleta.get('coletado_em', ''), 'totalizado_em': dg[-1] if dg else '',
        'fontes': coleta.get('fontes', {}), 'cargos': CARGOS,
        'vagas': {c: sum(n for (uf, cc), n in vaga.items() if cc == c) for c in CARGOS},
        'reeleitos': dict(reeleitos), 'tentaram_e_perderam': dict(tentou),
        'eleitos': lista, 'senado_continua': sorted(continuam, key=lambda x: (x['uf'], x['nm'])),
    }
    return D, erros


# ------------------------------------------------------------------ conferir

def conferir(eleitos, cands, apur, cand_csv, vagas):
    """Confere o resultado com a segunda fonte do TSE. Devolve a lista de diferenças (vazia = tudo certo)."""
    erros = []
    for a in apur:
        if a['pst'] != '100,00':
            erros.append(f"{a['uf']} cargo {a['cargo']} (eleição {a['e']}): apuração em {a['pst']}%, não terminou")
    feitos = {(a['uf'], a['cargo']) for a in apur if a['e'] == E1}
    for uf in UFS:
        for c in cargos_da_uf(uf):
            if (uf, c) not in feitos:
                erros.append(f'{uf}: falta o resultado de {CARGOS[c]}')
    # 1) número de eleitos = número de vagas do arquivo oficial de vagas
    n = Counter((x['uf'], x['c']) for x in eleitos)
    vaga = {(v['SG_UF'], v['CD_CARGO']): int(v['QT_VAGA'] or 0) for v in vagas}
    for (uf, c), qt in sorted(vaga.items()):
        if uf in UFS and c in cargos_da_uf(uf) and n.get((uf, c), 0) != qt:
            erros.append(f'{uf} {CARGOS[c]}: {n.get((uf, c), 0)} eleitos no resultado, {qt} vagas no arquivo de vagas')
    for (uf, c) in sorted(set(n) - set(vaga)):
        erros.append(f'{uf} {CARGOS[c]}: {n[(uf, c)]} eleitos, mas o arquivo de vagas não tem esse cargo')
    # 2) cada eleito consta como eleito no arquivo de candidatos, e vice-versa
    sit = defaultdict(set)
    for r in cand_csv:
        sit[r['SQ_CANDIDATO']].add(r.get('DS_SIT_TOT_TURNO', '').upper())
    if not any(any(s.startswith('ELEITO') for s in v) for v in sit.values()):
        erros.append('o arquivo de candidatos ainda não traz quem foi eleito (DS_SIT_TOT_TURNO vazio)')
        return erros
    sq_el = {x['sq'] for x in eleitos}
    for x in eleitos:
        if not any(s.startswith('ELEITO') for s in sit.get(x['sq'], ())):
            erros.append(f"{x['uf']} {CARGOS[x['c']]} {x['nmu']} ({x['sq']}): eleito no resultado, "
                         f"no arquivo de candidatos está {sorted(sit.get(x['sq'], {'(ausente)'}))}")
    por_sq = {r['SQ_CANDIDATO']: r for r in cand_csv}
    for sq, ss in sorted(sit.items()):
        if any(s.startswith('ELEITO') for s in ss) and sq not in sq_el:
            r = por_sq[sq]
            erros.append(f"{r['SG_UF']} {CARGOS.get(r['CD_CARGO'], r['CD_CARGO'])} {r['NM_URNA_CANDIDATO']} ({sq}): "
                         f'eleito no arquivo de candidatos, não no resultado')
    # 3) votos de cada eleito não podem ser zero
    for x in eleitos:
        if x['v'] <= 0:
            erros.append(f"{x['uf']} {x['nmu']}: eleito com {x['v']} votos")
    return erros
