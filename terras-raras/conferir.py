"""Confere as planilhas de terras-raras/dados antes de publicar (como o validar.py faz com o site nacional).

Se algo não bater, sai com erro e o site continua com a versão anterior da página.

Uso:  python3 terras-raras/conferir.py                                 (só as planilhas)
      python3 terras-raras/conferir.py --anterior site/terras-raras/index.html
          (também compara com a página publicada: nenhuma tabela pode perder mais de 20% das linhas)
      python3 terras-raras/conferir.py --anterior ... --ignorar-queda   (publica mesmo com a queda; use só se for real)

Regras:
- toda linha tem fonte (link http ou https) e data da conferência (verificado_em, AAAA-MM-DD, nunca no futuro);
- datas das fontes em AAAA, AAAA-MM ou AAAA-MM-DD ("-" ou "sem data" quando a fonte não diz);
- ids sem repetição; projetos_ids e empresas_ids apontam para linhas que existem;
- municípios do mapa com o nome do IBGE;
- numeros.csv: valor_grafico é número (ou vazio) e toda linha tem categoria;
- notícias da mais nova para a mais antiga, cada fonte marcada como nacional ou estrangeira (site .br é nacional);
- perda_processamento.csv: números nos campos da conta, payability entre 1 e 99%, cenário baixo <= alto;
- numeros.csv tem o dólar do dia (categoria Câmbio), usado para passar a perda para reais;
- nenhum CPF à mostra.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

PASTA = Path(__file__).resolve().parent
TABELAS = ["empresas", "projetos", "licencas", "areas_potencial", "donos_terra", "numeros", "leis", "impactos",
           "processos_noticias", "propostas", "perda_processamento"]
COLUNA_FONTE = {"propostas": "fonte_exemplo"}  # nas outras tabelas é fonte_url
COLUNAS_DATA = ("data", "fonte_data", "data_pedido")
QUEDA_MAXIMA = 0.20
DATA_FONTE = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")
DATA_CHEIA = re.compile(r"\d{4}-\d{2}-\d{2}")
CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
NUMERO = re.compile(r"-?\d+(\.\d+)?")
ORIGENS = ("nacional", "estrangeira")
CAMPOS_PERDA = ("producao_t_treo_ano", "cesta_baixa_usd_kg", "cesta_alta_usd_kg", "payability_pct",
                "receita_vida_baixa_usd_mi", "receita_vida_alta_usd_mi")


def ler(pasta: Path, nome: str) -> list[dict]:
    with open(pasta / "dados" / f"{nome}.csv", encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in linha.items()} for linha in csv.DictReader(f)]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def lista(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def conferir(dados: dict[str, list[dict]], municipios: set[str], hoje: dt.date) -> list[str]:
    erros: list[str] = []
    ids = {t: {r.get("id") for r in dados[t]} for t in TABELAS}
    for t in TABELAS:
        col_fonte = COLUNA_FONTE.get(t, "fonte_url")
        vistos: set[str] = set()
        for n, r in enumerate(dados[t], start=2):
            onde = f"{t}.csv, linha {n}"
            if not re.match(r"https?://\S+$", r.get(col_fonte, "")):
                erros.append(f"{onde}: sem link da fonte em {col_fonte}")
            v = r.get("verificado_em", "")
            if not DATA_CHEIA.fullmatch(v):
                erros.append(f"{onde}: verificado_em '{v}' não é uma data AAAA-MM-DD")
            else:
                try:
                    if dt.date.fromisoformat(v) > hoje + dt.timedelta(days=1):
                        erros.append(f"{onde}: verificado_em {v} está no futuro")
                except ValueError:
                    erros.append(f"{onde}: verificado_em '{v}' não existe no calendário")
            for c in COLUNAS_DATA:
                d = r.get(c)
                if d is not None and d not in ("", "-", "sem data") and not DATA_FONTE.fullmatch(d):
                    erros.append(f"{onde}: {c} '{d}' deve ser AAAA, AAAA-MM ou AAAA-MM-DD")
            if "id" in r:
                if not r["id"]:
                    erros.append(f"{onde}: sem id")
                elif r["id"] in vistos:
                    erros.append(f"{onde}: id {r['id']} repetido")
                vistos.add(r["id"])
            for i in lista(r.get("projetos_ids", "")):
                if i not in ids["projetos"]:
                    erros.append(f"{onde}: projeto '{i}' não existe em projetos.csv")
            for i in lista(r.get("empresas_ids", "")):
                if i not in ids["empresas"]:
                    erros.append(f"{onde}: empresa '{i}' não existe em empresas.csv")
            for m in lista(r.get("municipios_mapa", "")):
                if norm(m) not in municipios:
                    erros.append(f"{onde}: município '{m}' não está no mapa do IBGE")
            if any(CPF.search(x) for x in r.values()):
                erros.append(f"{onde}: CPF à mostra")
            if t == "numeros":
                if r.get("valor_grafico") and not NUMERO.fullmatch(r["valor_grafico"]):
                    erros.append(f"{onde}: valor_grafico '{r['valor_grafico']}' não é número")
                if not r.get("categoria"):
                    erros.append(f"{onde}: sem categoria")
            if t == "processos_noticias":
                for col_url, col_or in (("fonte_url", "origem"), ("fonte_url_2", "origem_2")):
                    u, o = r.get(col_url, ""), r.get(col_or, "")
                    if col_url == "fonte_url_2" and not u and not o:
                        continue
                    if col_url == "fonte_url_2" and not re.match(r"https?://\S+$", u):
                        erros.append(f"{onde}: fonte_url_2 '{u}' não é link")
                    if o not in ORIGENS:
                        erros.append(f"{onde}: {col_or} '{o}' deve ser nacional ou estrangeira")
                    elif o == "estrangeira" and re.match(r"https?://[^/]+\.br(/|$)", u):
                        erros.append(f"{onde}: {col_or} diz estrangeira, mas o site é .br")
            if t == "perda_processamento":
                v = {c: r.get(c, "") for c in CAMPOS_PERDA}
                ruins = [c for c, x in v.items() if not NUMERO.fullmatch(x)]
                if ruins:
                    erros.append(f"{onde}: {', '.join(ruins)} sem número")
                else:
                    x = {c: float(n) for c, n in v.items()}
                    if not 1 <= x["payability_pct"] <= 99:
                        erros.append(f"{onde}: payability_pct {v['payability_pct']} fora de 1 a 99")
                    if x["cesta_baixa_usd_kg"] > x["cesta_alta_usd_kg"] or x["receita_vida_baixa_usd_mi"] > x["receita_vida_alta_usd_mi"]:
                        erros.append(f"{onde}: cenário baixo maior que o alto")
    cambio = [r for r in dados["numeros"] if r.get("categoria") == "Câmbio"]
    if dados["perda_processamento"] and not any(NUMERO.fullmatch(r.get("valor_grafico", "")) and float(r["valor_grafico"]) > 0 for r in cambio):
        erros.append("numeros.csv: falta o dólar do dia (categoria Câmbio, valor_grafico em R$ por US$)")
    datas = [r.get("data", "") for r in dados["processos_noticias"]]
    for n, (a, b) in enumerate(zip(datas, datas[1:]), start=2):
        if a < b:
            erros.append(f"processos_noticias.csv, linha {n + 1}: notícia de {b} depois de uma de {a} "
                         "(a lista vai da mais nova para a mais antiga)")
    return erros


def dados_publicados(pagina: Path) -> dict | None:
    """Lê os dados embutidos na página publicada (const DADOS = {...};)."""
    try:
        html = pagina.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"const DADOS = (\{.*?\});\n", html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1).replace("<\\/", "</"))
    except ValueError:
        return None


def quedas(dados: dict[str, list[dict]], anterior: dict) -> list[str]:
    erros = []
    for t in TABELAS:
        antes, agora = len(anterior.get(t) or []), len(dados[t])
        if antes >= 5 and agora < antes * (1 - QUEDA_MAXIMA):
            erros.append(f"{t}: caiu de {antes} para {agora} linhas (mais de {QUEDA_MAXIMA:.0%}) em relação ao site no ar")
    return erros


def anotar(nivel: str, msg: str) -> None:
    """Anotação do GitHub Actions, lida pelo painel de status (/status/)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        msg = msg.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::{nivel} title=Terras Raras::{msg}")


def main(argv: list[str]) -> int:
    anterior = None
    if "--anterior" in argv:
        i = argv.index("--anterior")
        anterior = Path(argv[i + 1]) if i + 1 < len(argv) else None
    ignorar_queda = "--ignorar-queda" in argv

    dados = {t: ler(PASTA, t) for t in TABELAS}
    geo = json.loads((PASTA / "geo" / "mg.json").read_text(encoding="utf-8"))
    municipios = {norm(f["properties"]["n"]) for f in geo["municipios"]["features"]}
    hoje = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date()  # horário de Brasília
    erros = conferir(dados, municipios, hoje)

    if anterior is not None:
        publicado = dados_publicados(anterior)
        if publicado is None:
            print(f"Sem página anterior legível em {anterior}; comparação de quedas pulada.")
        else:
            q = quedas(dados, publicado)
            if q and ignorar_queda:
                print("Quedas aceitas (--ignorar-queda): " + "; ".join(q))
            else:
                erros += q

    total = sum(len(v) for v in dados.values())
    if erros:
        print(f"### Terras Raras: {len(erros)} problema(s) nas planilhas; a página publicada fica como estava")
        for e in erros:
            print(f"- {e}")
        anotar("error", f"{len(erros)} problema(s) nas planilhas: " + "; ".join(erros[:5]))
        return 1
    print(f"### Terras Raras: planilhas conferidas ({total} linhas em {len(TABELAS)} tabelas)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
