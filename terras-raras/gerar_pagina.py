"""Gera tracker.html a partir das planilhas em dados/ e do mapa em geo/.

Uso:  python3 gerar_pagina.py                    (gera tracker.html nesta pasta, versão do link do Claude)
      python3 gerar_pagina.py saida.html         (gera em outro caminho)
      python3 gerar_pagina.py --site saida.html  (versão do site Segredos Abertos: documento HTML completo,
                                                  barra dos projetos e dicas enviadas como issue no GitHub)
"""
import csv, json, sys, unicodedata, re
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SITE = "--site" in sys.argv
ARGS = [a for a in sys.argv[1:] if a != "--site"]
URL_SITE = "https://amarigo.github.io/segredos-abertos/terras-raras/"
TABELAS = ["empresas", "projetos", "licencas", "areas_potencial", "donos_terra", "numeros", "leis", "impactos", "processos_noticias", "propostas"]

def ler(nome):
    with open(PASTA / "dados" / f"{nome}.csv", encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in linha.items()} for linha in csv.DictReader(f)]

def norm(s):
    s = unicodedata.normalize("NFD", s); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z ]", "", s.lower()).strip()

dados = {t: ler(t) for t in TABELAS}
datas = [l.get("verificado_em", "") for t in dados.values() for l in t if l.get("verificado_em")]
dados["atualizado_em"] = max(datas) if datas else ""
dados["geo"] = json.loads((PASTA / "geo" / "mg.json").read_text(encoding="utf-8"))

# confere se os municípios escritos nas planilhas existem no mapa
nomes = {norm(f["properties"]["n"]) for f in dados["geo"]["municipios"]["features"]}
for t in ("projetos", "areas_potencial"):
    for r in dados[t]:
        for m in filter(None, (x.strip() for x in r.get("municipios_mapa", "").split(";"))):
            if norm(m) not in nomes:
                print(f"AVISO: município '{m}' ({t}, {r.get('id')}) não encontrado no mapa do IBGE")

modelo = (PASTA / "pagina_modelo.html").read_text(encoding="utf-8")
leaflet_css = (PASTA / "geo" / "leaflet.css").read_text(encoding="utf-8")
json_txt = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = modelo.replace("/*__LEAFLET_CSS__*/", leaflet_css).replace("/*__DADOS__*/", json_txt)
html = html.replace("/*__MODO__*/", "site" if SITE else "artifact")
if SITE:
    descricao = ("Quem quer lucrar com as terras raras de Minas Gerais: projetos, empresas e seus países, donos da terra, "
                 "licenças pendentes, dinheiro envolvido, leis, impactos e o que pedir aos legisladores. Com fonte e data.")
    cabeca = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
              f'<meta name="description" content="{descricao}"><link rel="canonical" href="{URL_SITE}">'
              '<meta property="og:type" content="website"><meta property="og:title" content="Terras Raras em Minas">'
              f'<meta property="og:description" content="{descricao}"><meta property="og:url" content="{URL_SITE}">'
              '<link rel="icon" href="../icon.svg">'
              '<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}</style></head><body>')
    # Barra dos projetos do Segredos Abertos (links relativos, como nos outros projetos)
    projetos = ('<style>nav.projetos{background:#1f2a44;color:#b7c3d9;font:600 12px/1.4 system-ui,sans-serif;'
                'text-transform:uppercase;letter-spacing:.06em}nav.projetos .wrap{display:flex;flex-wrap:wrap;gap:.2rem .9rem;'
                'align-items:center;padding-block:.45rem}nav.projetos a{color:#e3e9f4;text-decoration:none}'
                'nav.projetos a:hover{color:#fff;text-decoration:underline}nav.projetos a[aria-current="page"]{color:#fff;'
                'text-decoration:underline;text-underline-offset:3px}</style>'
                '<nav class="projetos" aria-label="Projetos do Segredos Abertos"><div class="wrap"><span>Projetos:</span>'
                '<a href="../">Brasil</a><a href="../mg/">Minas Nossa</a><a href="../eleicao2026/">Eleição 2026</a>'
                '<a href="./" aria-current="page">Terras Raras MG</a></div></nav>')
    html = cabeca + html.replace("<!--__PROJETOS__-->", projetos) + "</body></html>"
else:
    html = html.replace("<!--__PROJETOS__-->", "")
saida = Path(ARGS[0]) if ARGS else PASTA / "tracker.html"
saida.parent.mkdir(parents=True, exist_ok=True)
saida.write_text(html, encoding="utf-8")
print(f"Página gerada: {saida}  ({sum(len(dados[t]) for t in TABELAS)} registros, atualizado em {dados['atualizado_em']}, {len(html)//1024} KB)")
