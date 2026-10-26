"""Renúncia fiscal: quanto cada empresa deixou de pagar de impostos federais por causa de um benefício.

Fonte: Portal da Transparência (CGU), com dados da Receita Federal (declarações ECF e DIRBI e importações):
    https://portaldatransparencia.gov.br/download-de-dados/renuncias
O link do Portal leva a um arquivo por ano-calendário:
    https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/renuncias/{ano}_RenunciasFiscais.zip

Cada .zip traz quatro tabelas (CSV com ;, latin-1, vírgula decimal). Usamos duas:
- {ano}_RenúnciasFiscaisPorBeneficiário.csv: o total por CNPJ, com nome, atividade (CNAE), cidade e UF;
- {ano}_RenúnciasFiscais.csv: uma linha por CNPJ × benefício × fundamento legal, com o tributo.
As outras duas (empresas habilitadas e imunes ou isentas) não têm valor de renúncia.

A Receita publica os dados com atraso: o ano mais recente costuma estar incompleto.
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections import defaultdict
from pathlib import Path

from .emendas import SIGLAS, achar_colunas, bonito
from .util import avisar, digits, download, eh_zip, to_float

log = logging.getLogger("sa_etl.renuncias")

URLS = [
    "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/renuncias/{ano}_RenunciasFiscais.zip",
    "https://portaldatransparencia.gov.br/download-de-dados/renuncias/{ano}",
]
FONTE = "https://portaldatransparencia.gov.br/download-de-dados/renuncias"
CONSULTA = "https://portaldatransparencia.gov.br/renuncias/beneficiario"
N_ANOS = 4  # anos-calendário mostrados (os mais recentes que existirem)
N_TOP = 300

REGRAS_BEN = {
    "ano": [["ano", "calendario"], ["ano"]],
    "cnpj": [["cnpj"]],
    "nome": [["razao", "social"]],
    "fantasia": [["nome", "fantasia"]],
    "cnae_cod": [["codigo", "cnae"]],
    "cnae": [["cnae"]],
    "municipio": [["municipio"]],
    "uf": [["uf"]],
    "valor": [["valor", "renuncia"], ["valor"]],
}
REGRAS_DET = {
    "cnpj": [["cnpj"]],
    "tipo": [["tipo", "renuncia"]],
    "beneficio": [["beneficio", "fiscal"], ["beneficio"]],
    "fundamento": [["fundamento"]],
    "tributo": [["tributo"]],
    "valor": [["valor", "renuncia"], ["valor"]],
}

# Seções da CNAE 2.0 pela divisão (2 primeiros dígitos do código)
SECOES = [
    ((1, 3), "Agropecuária"), ((5, 9), "Mineração, petróleo e gás"), ((10, 33), "Indústria"), ((35, 35), "Eletricidade e gás"),
    ((36, 39), "Água, esgoto e lixo"), ((41, 43), "Construção"), ((45, 47), "Comércio"), ((49, 53), "Transporte e correio"),
    ((55, 56), "Hotéis e restaurantes"), ((58, 63), "Informação e comunicação"), ((64, 66), "Bancos, seguros e finanças"),
    ((68, 68), "Imóveis"), ((69, 75), "Serviços profissionais e técnicos"), ((77, 82), "Serviços administrativos"),
    ((84, 84), "Administração pública"), ((85, 85), "Educação"), ((86, 88), "Saúde e assistência social"),
    ((90, 93), "Cultura, esporte e lazer"), ((94, 96), "Outros serviços e associações"), ((97, 99), "Outros"),
]


def setor(cnae_cod: str) -> str:
    d = digits(cnae_cod)
    if len(d) < 2 or d[:2] == "00":
        return "Sem informação"
    div = int(d[:2])
    return next((nome for (a, b), nome in SECOES if a <= div <= b), "Sem informação")


def cnpj_de(v: str) -> str:
    """O CNPJ pode vir com máscara ou sem os zeros à esquerda. Códigos que não são CNPJ (a Receita usa -3 para
    'inválido') ficam vazios, mas o valor continua no total."""
    d = digits(v)
    if 11 < len(d) < 14:
        d = d.zfill(14)
    return d if len(d) == 14 else ""


def baixar(ano: int, cache: Path) -> Path | None:
    dest = cache / f"{ano}_RenunciasFiscais.zip"
    for url in URLS:
        try:
            return download(url.format(ano=ano), dest, max_horas=24 * 7, validar=eh_zip)
        except Exception as e:  # noqa: BLE001 - ano que ainda não existe responde 403 ou 404
            log.info("Renúncias %d: %s indisponível (%s)", ano, url.format(ano=ano), str(e)[:120])
    return None


def _tabelas(z: zipfile.ZipFile) -> tuple[str | None, str | None]:
    """(por beneficiário, detalhe). Os nomes têm acento, que o .zip às vezes guarda em outra codificação."""
    csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
    ben = next((n for n in csvs if "porbenefici" in n.lower()), None)
    det = next((n for n in csvs if n not in (ben,) and not any(x in n.lower() for x in ("habilitad", "imune", "isent"))), None)
    return ben, det


def _linhas(z: zipfile.ZipFile, nome: str):
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", errors="replace", newline=""), delimiter=";")


def ler_ano(zip_path: Path, ano: int, n_top: int = N_TOP) -> tuple[dict, dict[str, dict]] | None:
    """Resumo do ano e, para cada CNPJ, o total e os benefícios (para as páginas das empresas)."""
    with zipfile.ZipFile(zip_path) as z:
        ben, det = _tabelas(z)
        if not ben:
            log.warning("Renúncias %d: tabela por beneficiário não encontrada (%s)", ano, z.namelist())
            return None
        empresas: dict[str, dict] = {}
        total, sem_cnpj, col = 0.0, 0.0, None
        por_uf: dict[str, list] = defaultdict(lambda: [0.0, 0])
        por_setor: dict[str, list] = defaultdict(lambda: [0.0, 0])
        for r in _linhas(z, ben):
            if col is None:
                col = achar_colunas(list(r.keys()), REGRAS_BEN)
                if not col["cnpj"] or not col["valor"]:
                    log.error("Renúncias %d: colunas essenciais não encontradas (%s)", ano, list(r.keys()))
                    return None
            g = lambda k: (r.get(col[k]) or "").strip() if col.get(k) else ""  # noqa: E731
            v = to_float(g("valor"))
            if not v:
                continue
            total += v
            doc = cnpj_de(g("cnpj"))
            uf = g("uf").upper() if g("uf").upper() in SIGLAS else ""
            st = setor(g("cnae_cod"))
            por_uf[uf or "Não informado"][0] += v
            por_uf[uf or "Não informado"][1] += 1
            por_setor[st][0] += v
            por_setor[st][1] += 1
            if not doc:
                sem_cnpj += v
                continue
            e = empresas.setdefault(doc, {"nome": bonito(g("nome")) or g("fantasia"), "uf": uf, "municipio": bonito(g("municipio")),
                                          "setor": st, "atividade": g("cnae"), "valor": 0.0, "beneficios": defaultdict(float)})
            e["valor"] += v
        por_ben: dict[tuple, list] = defaultdict(lambda: [0.0, set()])
        por_tributo: dict[str, float] = defaultdict(float)
        if det:
            col = None
            for r in _linhas(z, det):
                if col is None:
                    col = achar_colunas(list(r.keys()), REGRAS_DET)
                g = lambda k: (r.get(col[k]) or "").strip() if col.get(k) else ""  # noqa: E731
                v = to_float(g("valor"))
                if not v:
                    continue
                nome_b = g("beneficio") or g("fundamento") or "Não informado"
                doc = cnpj_de(g("cnpj"))
                b = por_ben[(nome_b, g("tributo"))]
                b[0] += v
                b[1].add(doc)
                por_tributo[g("tributo") or "Não informado"] += v
                if doc in empresas:
                    empresas[doc]["beneficios"][nome_b] += v
    ordem = sorted(empresas.items(), key=lambda kv: -kv[1]["valor"])
    par = lambda d, n: [[k, round(x, 2)] for k, x in sorted(d.items(), key=lambda kv: -kv[1])[:n]]  # noqa: E731
    resumo = {
        "ano": ano, "total": round(total, 2), "n": len(empresas), "sem_cnpj": round(sem_cnpj, 2),
        "por_uf": [[k, round(x[0], 2), x[1]] for k, x in sorted(por_uf.items(), key=lambda kv: -kv[1][0])],
        "por_setor": [{"setor": k, "valor": round(x[0], 2), "n": x[1]} for k, x in sorted(por_setor.items(), key=lambda kv: -kv[1][0])],
        "por_beneficio": [{"nome": k[0], "tributo": k[1], "valor": round(x[0], 2), "n": len(x[1] - {""})}
                          for k, x in sorted(por_ben.items(), key=lambda kv: -kv[1][0])[:25]],
        "por_tributo": par(por_tributo, 12),
        "top": [{"cnpj": doc, "nome": e["nome"], "uf": e["uf"], "municipio": e["municipio"], "setor": e["setor"],
                 "atividade": e["atividade"], "valor": round(e["valor"], 2), "beneficios": par(e["beneficios"], 3)}
                for doc, e in ordem[:n_top]],
    }
    por_empresa = {doc: {"valor": round(e["valor"], 2), "beneficios": par(e["beneficios"], 8)} for doc, e in ordem}
    log.info("Renúncias %d: R$ %.0f, %d empresas", ano, total, len(empresas))
    return resumo, por_empresa


def coletar(cache: Path, ano_atual: int, n_anos: int = N_ANOS) -> dict:
    """Os anos-calendário mais recentes que o Portal tiver. {"anos": {ano: resumo}, "empresas": {cnpj: {ano: {...}}}}"""
    cache.mkdir(parents=True, exist_ok=True)
    anos: dict[int, dict] = {}
    por_emp: dict[str, dict] = defaultdict(dict)
    for ano in range(ano_atual, ano_atual - n_anos - 3, -1):
        if len(anos) >= n_anos:
            break
        z = baixar(ano, cache)
        if not z:
            continue
        try:
            r = ler_ano(z, ano)
        except (zipfile.BadZipFile, OSError, ValueError) as e:
            log.warning("Renúncias %d: arquivo com problema (%s)", ano, e)
            r = None
        if not r:
            continue
        anos[ano], emps = r
        for doc, x in emps.items():
            por_emp[doc][ano] = x
    if not anos:
        avisar("Renúncia fiscal: o Portal da Transparência não respondeu; a parte de renúncias da página de incentivos não foi atualizada")
    # Ano incompleto: a Receita ainda não processou todas as declarações (fica bem abaixo do ano anterior)
    for ano, r in anos.items():
        ant = anos.get(ano - 1)
        r["parcial"] = bool(ant and r["total"] < 0.6 * ant["total"])
    return {"anos": anos, "empresas": dict(por_emp)}
