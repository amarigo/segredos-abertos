"""Página "Quem assume em 2027" (eleitos/): o modelo em site/eleitos.html, com o mesmo visual da página da eleição para
presidente (o CSS vem de site/cabecalho.html e site/corpo.html), e as planilhas para baixar."""
import csv
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(AQUI, '..', '..', 'site')
URL = 'https://amarigo.github.io/segredos-abertos/eleicao2026/eleitos/'
DESCRICAO = ('Governadores, senadores, deputados federais e estaduais eleitos em 2026 para o mandato de 2027 a 2030: '
             'partido, coligação, votos, foto e quem foi reeleito. Dados oficiais do TSE, conferidos.')

CSS_PAGINA = """
.volta{margin-top:1rem}
.filtros{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:.8rem}
.filtros input[type=search]{min-height:3.2rem;border:2px solid var(--line);border-radius:999px;background:var(--panel);padding:.3rem 1rem;width:100%}
.facts .fact{gap:.25rem}
.pbar-list{display:flex;flex-direction:column;gap:.25rem}
.pbar{display:grid;grid-template-columns:minmax(4.5rem,8rem) 1fr 3rem minmax(0,8rem);align-items:center;gap:.5rem;font-size:.95rem}
.pbar .pn{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pbar .pb{display:block;height:1.1rem;background:var(--soft);border-radius:999px;overflow:hidden}
.pbar .pb i{display:block;height:100%;background:var(--br-blue);border-radius:999px}
.pbar .pk{text-align:right}
@media (max-width:560px){.pbar{grid-template-columns:5rem 1fr 2.6rem}.pbar .pl{display:none}}
:root{--esq:#C0392B;--dir:#1351B4;--centro:#8A94A6}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--esq:#FF8A7A;--dir:#7FB0FF;--centro:#9AA5B3}}
:root[data-theme="dark"]{--esq:#FF8A7A;--dir:#7FB0FF;--centro:#9AA5B3}
.lbar{display:flex;height:1.6rem;border-radius:999px;overflow:hidden;gap:2px}
.l0{background:var(--esq)} .l1{background:color-mix(in oklab,var(--esq) 55%,var(--centro))} .l2{background:var(--centro)}
.l3{background:color-mix(in oklab,var(--dir) 55%,var(--centro))} .l4{background:var(--dir)}
.ls{background:repeating-linear-gradient(45deg,var(--line) 0 6px,transparent 6px 12px)}
.legend .sw{vertical-align:middle}
.cards-el{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(22rem,1fr));gap:.8rem}
@media (max-width:560px){.cards-el{grid-template-columns:1fr}}
.el{display:flex;gap:.9rem;align-items:flex-start;border:1px solid var(--line);border-radius:12px;padding:.9rem;background:var(--panel)}
.el .foto{flex:none;position:relative;width:4rem;height:5.3rem;border-radius:8px;overflow:hidden;background:var(--soft);display:flex;align-items:center;justify-content:center}
.el .foto img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.el .foto b{font-size:1.2rem;color:var(--muted)}
.el .info{display:flex;flex-direction:column;gap:.2rem;min-width:0}
.el .nome{font-size:1.1rem}
.el .links{display:flex;flex-wrap:wrap;gap:.2rem .9rem;margin-top:.2rem}
.tag.re{background:var(--soft);color:var(--br-ink)}
.tag.nv{background:#E3F5E1;color:#0E5A16}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .tag.nv{background:#173A1C;color:#9BE3A5}}
:root[data-theme="dark"] .tag.nv{background:#173A1C;color:#9BE3A5}
.aviso{color:var(--warnc);font-weight:700}
.simples{margin:0;padding-left:1.2rem;display:flex;flex-direction:column;gap:.4rem}
"""

CABECA = """<meta charset="utf-8">
<title>Quem assume em 2027 · Eleição 2026 Aberta</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{d}">
<link rel="icon" href="../icone.svg" type="image/svg+xml">
<link rel="canonical" href="{u}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Segredos Abertos">
<meta property="og:title" content="Quem assume em 2027">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{u}">
<meta property="og:locale" content="pt_BR">
<script src="../i18n/tradutor.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Raleway:wght@400..900&display=swap">
"""

CSV_COLUNAS = (('cargo', None), ('uf', 'uf'), ('numero', 'n'), ('nome_urna', 'nm'), ('nome_completo', 'nc'),
               ('partido', 'p'), ('federacao', 'fed'), ('coligacao', 'col'), ('composicao_coligacao', 'comp'),
               ('votos', 'v'), ('percentual_validos', 'pv'), ('situacao_tse', 'st'), ('concorreu_a_reeleicao', 're'),
               ('mandato_hoje', None), ('id_tse', 'sq'), ('link_tse', 'tse'))


def css():
    """O CSS da página da eleição para presidente: do <style> de cabecalho.html até o </style> de corpo.html."""
    with open(os.path.join(SITE, 'cabecalho.html'), encoding='utf-8') as f:
        cab = f.read()
    with open(os.path.join(SITE, 'corpo.html'), encoding='utf-8') as f:
        corpo = f.read()
    return cab[cab.index('<style>') + len('<style>'):] + corpo[:corpo.index('</style>')]


def pagina(D):
    with open(os.path.join(SITE, 'eleitos.html'), encoding='utf-8') as f:
        corpo = f.read()
    # o JSON vai dentro de <script>: "</" não pode aparecer cru
    if D:  # na página, o link da foto e do TSE é montado no navegador (página menor); nos arquivos para baixar, vai inteiro
        D = {**D, 'eleitos': [{k: v for k, v in x.items() if k not in ('foto', 'tse')} for x in D['eleitos']]}
    dados = json.dumps(D, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') if D else 'null'
    corpo = corpo.replace('/*DATA*/', dados)
    return ('<!doctype html>\n<html lang="pt-BR">\n<head>\n' + CABECA.format(d=DESCRICAO, u=URL) + '<style>'
            + css() + CSS_PAGINA + '</style>\n</head>\n<body>\n' + corpo + '\n</body>\n</html>\n')


def linhas_csv(D):
    for x in D['eleitos']:
        h = x.get('hoje')
        hoje = (('Deputado federal' if h['casa'] == 'camara' else 'Senador') + f" ({h['partido']}-{h['uf']})") if h else ''
        out = {}
        for col, k in CSV_COLUNAS:
            out[col] = D['cargos'][x['c']] if col == 'cargo' else hoje if col == 'mandato_hoje' else x.get(k, '')
        yield out


def gravar(saida, D, erros):
    """Grava eleitos/ em `saida`. Sem D (conferência falhou), a página só diz que os eleitos estão em conferência."""
    pasta = os.path.join(saida, 'eleitos')
    os.makedirs(os.path.join(pasta, 'dados'), exist_ok=True)
    with open(os.path.join(pasta, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(pagina(D))
    if not D:
        return
    with open(os.path.join(pasta, 'dados', 'eleitos.json'), 'w', encoding='utf-8') as f:
        json.dump(D, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(pasta, 'dados', 'eleitos.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=[c for c, _ in CSV_COLUNAS], delimiter=';')
        w.writeheader()
        w.writerows(linhas_csv(D))
