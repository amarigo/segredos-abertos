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
3. Quem já tem mandato hoje: API da Câmara (/deputados?idLegislatura=N; o nome civil e o nascimento vêm do arquivo
   oficial de deputados da Câmara, veja baixar_camara) e API do Senado (/senador/lista/atual, /senador/{codigo}). Liga o eleito ao que o site já mostra de gastos e votos desta legislatura.

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
CKAN = 'https://dadosabertos.tse.jus.br/api/3/action/package_show?id={id}'
PACOTE_CAND = 'candidatos-2026'
ARQ_CAND = 'consulta_cand_2026.zip'
ARQ_VAGAS = 'consulta_vagas_2026.zip'
ARQ_COMPL = 'consulta_cand_complementar_2026.zip'
# endereços conhecidos, usados só se a API do portal não responder
RESERVA = {ARQ_CAND: 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip',
           ARQ_VAGAS: 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_vagas/consulta_vagas_2026.zip',
           ARQ_COMPL: 'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand_complementar/consulta_cand_complementar_2026.zip'}
PAGINA_CAND = 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026'

CAMARA = 'https://dadosabertos.camara.leg.br/api/v2'
ARQ_DEPUTADOS = 'https://dadosabertos.camara.leg.br/arquivos/deputados/json/deputados.json'
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
                with open(os.path.join(pasta, f'{uf.lower()}-c{c}-e{e}.json.gz'), 'wb') as f:
                    f.write(gzip.compress(r.content, compresslevel=9, mtime=0))  # sem data: só muda se o conteúdo mudar
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
    """Do arquivo de candidatos, guarda só os cargos estaduais e federais (sem presidente) e só as COLUNAS. Desde 2024
    parte das colunas (como ST_REELEICAO) pode estar no arquivo "Informações complementares": o que faltar no principal
    vem de lá, pelo SQ_CANDIDATO."""
    url = url_arquivo(ARQ_CAND)
    r = _get(url, timeout=600)
    linhas, colunas = [], set()
    for row in _csvs_do_zip(r.content, 'consulta_cand_2026'):
        colunas.update(row)
        if row.get('CD_CARGO') in CARGOS:
            linhas.append({k: (row.get(k) or '').strip() for k in COLUNAS})
    if not linhas:
        raise RuntimeError('arquivo de candidatos sem nenhuma linha de governador, senador ou deputado')
    faltam = [k for k in COLUNAS if k not in colunas]
    print('candidatos: colunas do arquivo principal:', ', '.join(sorted(colunas)), flush=True)
    if faltam:
        rc = _get(url_arquivo(ARQ_COMPL), timeout=600)
        compl, cols_c = {}, set()
        for row in _csvs_do_zip(rc.content, 'consulta_cand_complementar_2026'):
            cols_c.update(row)
            compl[row.get('SQ_CANDIDATO', '').strip()] = row
        print('candidatos: colunas do arquivo complementar:', ', '.join(sorted(cols_c)), flush=True)
        for x in linhas:
            c = compl.get(x['SQ_CANDIDATO'], {})
            for k in faltam:
                x[k] = (c.get(k) or '').strip()
        faltam = [k for k in faltam if k not in cols_c]
    if faltam:
        print('::warning title=Eleitos 2026::colunas que o TSE não publicou nos arquivos de candidatos: '
              + ', '.join(faltam), flush=True)
    texto = io.StringIO(newline='')
    w = csv.DictWriter(texto, fieldnames=COLUNAS, delimiter=';')
    w.writeheader()
    w.writerows(sorted(linhas, key=lambda x: (x['SG_UF'], x['CD_CARGO'], x['SQ_CANDIDATO'], x['NR_TURNO'])))
    with open(os.path.join(pasta, 'candidatos.csv.gz'), 'wb') as f:
        f.write(gzip.compress(texto.getvalue().encode('utf-8'), compresslevel=9, mtime=0))
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
                dep = vistos.setdefault(str(x['id']), {'id': str(x['id']), 'nome': x['nome'], 'uf': x['siglaUf'],
                                                       'partido': x['siglaPartido'], 'leg': []})
                if leg not in dep['leg']:  # a lista repete a pessoa uma vez por nome ou partido que ela usou
                    dep['leg'].append(leg)
            url = next((ln['href'] for ln in d.get('links', []) if ln.get('rel') == 'next'), None)
    # quem está no exercício do mandato hoje, com o partido de hoje (a lista da legislatura pode trazer um partido antigo)
    url = f'{CAMARA}/deputados?itens=100&ordem=ASC&ordenarPor=nome'
    while url:
        d = _get(url, tentativas=6, headers={'Accept': 'application/json'}).json()
        for x in d['dados']:
            dep = vistos.setdefault(str(x['id']), {'id': str(x['id']), 'nome': x['nome'], 'uf': x['siglaUf'], 'leg': [x['idLegislatura']]})
            dep.update({'partido': x['siglaPartido'], 'em_exercicio': True})
        url = next((ln['href'] for ln in d.get('links', []) if ln.get('rel') == 'next'), None)
    # Nome civil e nascimento: a API só dá um deputado por consulta (/deputados/{id}, mais de 600 consultas) e respondeu
    # 504 no meio da lista (04/11/2026). O arquivo oficial de deputados da Câmara traz os dois campos de todos de uma
    # vez; a API fica para quem faltar no arquivo.
    try:
        arq = {str(x['uri']).rsplit('/', 1)[-1]: x for x in _get(ARQ_DEPUTADOS, timeout=180, tentativas=4).json()['dados']}
    except (requests.RequestException, KeyError, ValueError):
        arq = {}
    for i, dep in vistos.items():
        det = arq.get(i) or _get(f'{CAMARA}/deputados/{i}', headers={'Accept': 'application/json'}).json()['dados']
        dep['nome_civil'] = det.get('nomeCivil') or ''
        dep['nascimento'] = det.get('dataNascimento') or ''
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


PARTICULAS = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E', 'D'}


def _parecido(a, b):
    """Mesmo nome, abreviado ("A" e "ALVES") ou com uma letra trocada ("MURILO" e "MURILLO", "BONFIM" e "BOMFIM")."""
    if a == b or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    # distância de edição até 1
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    curto, longo = sorted((a, b), key=len)
    return any(longo[:i] + longo[i + 1:] == curto for i in range(len(longo)))


def mesma_pessoa(nome_tse, nasc_tse, nome_casa, nasc_casa):
    """Mesmo dia de nascimento, o mesmo primeiro nome e pelo menos 75% dos nomes do mais curto no mais longo (sem contar
    "de", "da", "dos"...). A Câmara às vezes encurta ou abrevia o nome civil, e o TSE pode juntar ou separar sobrenomes
    ("ABDELAZIZ" e "ABDEL AZIZ"). Irmãos gêmeos têm o mesmo nascimento e quase o mesmo nome: o primeiro nome os separa."""
    if not nasc_tse or _data_iso(nasc_tse) != _data_iso(nasc_casa):
        return False
    a = [w for w in normal(nome_tse).split() if w not in PARTICULAS]
    b = [w for w in normal(nome_casa).split() if w not in PARTICULAS]
    if not a or not b or not _parecido(a[0], b[0]) or min(len(a[0]), len(b[0])) < 2:
        return False
    if a == b or ''.join(a) == ''.join(b):
        return True
    curto, longo = sorted((a, b), key=len)
    iguais = sum(1 for w in curto if any(_parecido(w, x) for x in longo))
    return len(curto) >= 2 and iguais >= 2 and iguais / len(curto) >= 0.75


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
                          'exercicio': casa == 'senado' or bool(x.get('em_exercicio')),
                          **({'leg': x['leg']} if 'leg' in x else {}),
                          **({'fim': x['fim_mandato']} if x.get('fim_mandato') else {})}
    return eleitos


def reeleito(el, r):
    """'S' (reeleito: já tem o mesmo cargo hoje), 'N' (novo no cargo) ou '' (sem informação oficial).
    Primeiro o campo ST_REELEICAO do TSE. Em 2026 o TSE publicou esse campo vazio ('#NE', conferido em 04/11/2026); então,
    para deputado federal e senador, vale quem está no exercício do mesmo cargo hoje, segundo as APIs da Câmara e do
    Senado. Para governador e deputado estadual não há fonte oficial de quem está no cargo hoje: fica sem informação."""
    tse = (r.get('ST_REELEICAO') or '').strip().upper()
    if tse in ('S', 'N'):
        return tse
    h = el.get('hoje') or {}
    if el['c'] == '6':
        return 'S' if h.get('casa') == 'camara' and h.get('exercicio') else 'N'
    if el['c'] == '5':
        return 'S' if h.get('casa') == 'senado' and h.get('fim', '')[:4] == '2027' else 'N'
    return ''


def fonte_reeleicao(cand_csv):
    return 'tse' if any((r.get('ST_REELEICAO') or '').strip().upper() in ('S', 'N') for r in cand_csv) else 'camara_senado'


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
                'tse': RES.format(e=el['e'], u=el['uf'].lower(), c=el['c']),  # o arquivo oficial de onde vêm os números
                're': reeleito(el, r), 'g': titulo(r.get('DS_GENERO', '')),
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
    # senador com mandato até 2031 eleito agora para outro cargo (governador, por exemplo): o suplente assume a cadeira
    outro = {x['hoje']['id']: CARGOS[x['c']] for x in lista if x.get('hoje', {}).get('casa') == 'senado' and x['c'] != '5'}
    for s in continuam:
        if s['id'] in outro:
            s['eleito'] = outro[s['id']]
    # quem tentou a reeleição (ST_REELEICAO = S) e não se elegeu, por cargo: só se o TSE preencher o campo
    sq_eleitos = {x['sq'] for x in lista}
    tentou = Counter(r['CD_CARGO'] for r in {r['SQ_CANDIDATO']: r for r in cand_csv}.values()
                     if r.get('ST_REELEICAO') == 'S' and r['SQ_CANDIDATO'] not in sq_eleitos)
    reeleitos = Counter(x['c'] for x in lista if x['re'] == 'S')
    sem_info = Counter(x['c'] for x in lista if x['re'] not in ('S', 'N'))
    # quem tem o cargo hoje e não volta em 2027 (não concorreu, perdeu ou foi eleito para outro cargo)
    voltam = {x['hoje']['id'] for x in lista if x.get('hoje') and x['re'] == 'S'}
    nao_voltam = {'6': sum(1 for d in camara if d.get('em_exercicio') and 'dep-' + d['id'] not in voltam),
                  '5': sum(1 for s in senado if s.get('fim_mandato', '')[:4] == '2027' and 'sen-' + s['id'] not in voltam)}
    vaga = {(v['SG_UF'], v['CD_CARGO']): int(v['QT_VAGA'] or 0) for v in vagas}
    dg = sorted({a['dg'] for a in apur if a['dg']})
    D = {
        'coletado_em': coleta.get('coletado_em', ''), 'totalizado_em': dg[-1] if dg else '',
        'fontes': coleta.get('fontes', {}), 'cargos': CARGOS,
        'vagas': {c: sum(n for (uf, cc), n in vaga.items() if cc == c) for c in CARGOS},
        'reeleitos': dict(reeleitos), 'tentaram_e_perderam': dict(tentou), 'sem_info_reeleicao': dict(sem_info),
        'nao_voltam': nao_voltam, 'fonte_reeleicao': fonte_reeleicao(cand_csv),
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
