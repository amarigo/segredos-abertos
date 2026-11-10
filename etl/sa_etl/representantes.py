"""Quem me representa: para cada cidade, todos os cargos eleitos, do vereador ao presidente.

O que cada cargo usa (API primeiro):
- Deputados federais e senadores de hoje: a lista que a coleta já monta pela API da Câmara (/deputados) e pela API do
  Senado (politicos.json, só quem está em exercício). Liga cada um à página de gastos e votos do site.
- Vereadores, prefeito e vice (eleição de 2024), deputados estaduais ou distritais, governador e vice, presidente e
  vice (eleição de 2022): arquivo oficial de candidatos do TSE (consulta_cand_{ano}.zip), achado pela API do Portal
  de Dados Abertos do TSE (CKAN, dadosabertos.tse.jus.br/api/3), com o endereço do CDN como reserva. Não há API com
  esses dados: a do DivulgaCandContas recusa acesso automático (HTTP 403, conferido do GitHub Actions em 04/11/2026,
  veja eleicao2026/etl/el_etl/eleitos.py) e o site de resultados só dá uma cidade por pedido (mais de 11 mil pedidos).
- Número de cadeiras de cada Câmara Municipal e de cada Assembleia: arquivo oficial de vagas do TSE
  (consulta_vagas_{ano}.zip), do mesmo pacote. Serve para conferir: o número de eleitos tem de bater com o de vagas.
- Quem deixou o cargo para disputar a eleição de 2026: arquivo de candidatos de 2026 do TSE. A Constituição
  (art. 14, § 6º) obriga presidente, governador e prefeito a renunciar 6 meses antes para concorrer a outro cargo.
  A pessoa é a mesma quando o nome completo e a data de nascimento são iguais nos dois arquivos (o TSE não publica
  mais o CPF dos candidatos). A data de nascimento só é usada para ligar os arquivos e não vai para o site.
- Eleição suplementar (quando a eleição de 2024 de uma cidade, para prefeito ou para vereador, foi anulada e feita de
  novo): site de resultados do TSE, que publica a lista oficial das eleições (comum/config/ele-c.json) e o resultado de
  cada cidade em JSON (o mesmo do aplicativo Resultados, também usado em eleicao2026/etl/el_etl/eleitos.py). Os dados
  abertos não servem aqui: não há pacote de candidatos de 2025 (HTTP 404 na API CKAN e no CDN) e o arquivo de 2026 não
  traz as suplementares (conferido no GitHub Actions em 10/11/2026: 0 suplementares nos arquivos, 46 no site).
- Cidade sem prefeito eleito ou com menos vereadores que cadeiras: o mesmo arquivo do site de resultados traz o aviso
  oficial do TSE (eleição anulada, votos anulados, totalização ainda não concluída), que a página mostra.

O TSE registra quem foi eleito. Troca no meio do mandato por outro motivo (cassação, morte, licença, suplente que
assume) não aparece nesses arquivos, e a página avisa.

Grava em data/representantes/: indice.json (cidades para a busca, presidente e fontes), uf/{UF}.json (estado) e
m/{código da cidade no TSE}.json (cidade).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import logging
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from .util import avisar, download, eh_zip, get_json, norm_name, write_json

log = logging.getLogger("sa_etl.representantes")

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=candidatos-{ano}"
PAGINA_CKAN = "https://dadosabertos.tse.jus.br/dataset/candidatos-{ano}"
CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/{tipo}/{tipo}_{ano}.zip"
CONSTITUICAO = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art14%C2%A76"
API_CAMARA = "https://dadosabertos.camara.leg.br/api/v2/deputados"
API_SENADO = "https://legis.senado.leg.br/dadosabertos/senador/lista/atual"
DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga/#/home"

MUNICIPAL, GERAL, SEGUINTE = 2024, 2022, 2026  # eleições dos mandatos de hoje e a que já escolheu os próximos
# Suplementar marcada depois do 2º turno de 2024 refaz a eleição do mandato de 2025 a 2028; antes disso, é do anterior
INICIO_SUPLEMENTAR = "2024-10-28"
# Por quantos dias a leitura de cada arquivo vale. O resultado de 2024 e o de 2026 ainda mudam (recontagem, cassação,
# eleição suplementar); o de 2022 quase não muda mais.
VALIDADE_DIAS = {GERAL: 30, MUNICIPAL: 7, SEGUINTE: 7}

# Site de resultados do TSE (JSON oficial). 619 é a eleição municipal ordinária de 2024, 1º turno.
RESULTADOS = "https://resultados.tse.jus.br/oficial"
ELEICOES_TSE = RESULTADOS + "/comum/config/ele-c.json"
ARQ_RESULTADO = RESULTADOS + "/{ciclo}/{eleicao}/dados/{uf}/{uf}{ue}-c{cargo:0>4}-e{eleicao:0>6}-u.json"
PAGINA_RESULTADOS = RESULTADOS + "/app/index.html"
ORDINARIA_2024 = ("ele2024", "619")
VALIDADE_RESULTADO = 7  # dias

# Códigos de cargo do TSE (CD_CARGO)
PRESIDENTE, VICE_PRESIDENTE, GOVERNADOR, VICE_GOVERNADOR = "1", "2", "3", "4"
SENADOR, DEP_FEDERAL, DEP_ESTADUAL, DEP_DISTRITAL = "5", "6", "7", "8"
PREFEITO, VICE_PREFEITO, VEREADOR = "11", "12", "13"
NOME_CARGO = {PRESIDENTE: "Presidente", VICE_PRESIDENTE: "Vice-presidente", GOVERNADOR: "Governador",
              VICE_GOVERNADOR: "Vice-governador", SENADOR: "Senador", DEP_FEDERAL: "Deputado federal",
              DEP_ESTADUAL: "Deputado estadual", DEP_DISTRITAL: "Deputado distrital", PREFEITO: "Prefeito",
              VICE_PREFEITO: "Vice-prefeito", VEREADOR: "Vereador"}
MIN_CIDADES = 5000  # o Brasil tem 5.569 cidades com eleição municipal; menos que isso é arquivo incompleto
TITULARES = {PRESIDENTE, GOVERNADOR, PREFEITO}  # quem precisa renunciar para disputar outro cargo (CF, art. 14, § 6º)

UFS = {"AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia", "CE": "Ceará",
       "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais",
       "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
       "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia",
       "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
       "TO": "Tocantins"}

# Colunas lidas do arquivo de candidatos. CPF, e-mail e título de eleitor nunca são lidos.
COLUNAS = ("ANO_ELEICAO", "NM_TIPO_ELEICAO", "DT_ELEICAO", "NR_TURNO", "SG_UF", "SG_UE", "NM_UE", "CD_CARGO",
           "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO", "DT_NASCIMENTO",
           "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND", "DS_SIT_TOT_TURNO")
OBRIGATORIAS = {"NR_TURNO", "SG_UF", "SG_UE", "CD_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO",
                "SG_PARTIDO", "DS_SIT_TOT_TURNO"}


# ---------------------------------------------------------------- arquivos do TSE

def url_arquivo(tipo: str, ano: int) -> str:
    """Endereço oficial do arquivo, pela API do Portal de Dados Abertos do TSE (CKAN); o do CDN se ela não responder."""
    nome = f"{tipo}_{ano}.zip"
    try:
        for res in get_json(CKAN.format(ano=ano), tries=3, timeout=60)["result"]["resources"]:
            u = str(res.get("url") or "")
            if u.startswith("https://") and u.endswith("/" + nome):
                return u
    except Exception as e:  # noqa: BLE001 - o CDN é o mesmo endereço que a API costuma devolver
        log.info("CKAN do TSE sem resposta para %s (%s); usando o endereço do CDN", nome, e)
    return CDN.format(tipo=tipo, ano=ano)


def linhas_csv(zp: Path, prefixo: str) -> Iterator[dict[str, str]]:
    """Linhas dos CSV do ZIP do TSE (latin-1, ';'). Usa o arquivo _BRASIL quando existe (tem todos os estados); senão,
    junta os de cada estado. Falha se faltar coluna obrigatória: adivinhar a posição daria dados errados."""
    with zipfile.ZipFile(zp) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv") and Path(n).name.startswith(prefixo)]
        if not nomes:
            raise ValueError(f"{zp.name}: nenhum CSV {prefixo}* dentro do ZIP")
        br = [n for n in nomes if Path(n).stem.upper().endswith("_BRASIL")]
        for nome in br or nomes:
            with z.open(nome) as f:
                leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")
                faltam = (OBRIGATORIAS if prefixo.startswith("consulta_cand") else {"SG_UE", "CD_CARGO"}) - set(leitor.fieldnames or [])
                if faltam:
                    raise ValueError(f"{nome}: colunas faltando no arquivo do TSE: {sorted(faltam)}")
                for r in leitor:
                    yield {k: (v or "").strip() for k, v in r.items() if k}


def _txt(v: str | None) -> str:
    v = (v or "").strip()
    return "" if v.upper() in ("#NULO", "#NULO#", "#NE", "#NE#", "-1", "-3", "-4") else v


def _data_iso(v: str) -> str:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", _txt(v))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def ler_candidatos(zp: Path, ano: int) -> list[dict]:
    """Só as linhas que a página usa, com só as COLUNAS. Uma linha por candidato e turno."""
    out, vistos = [], set()
    for r in linhas_csv(zp, f"consulta_cand_{ano}"):
        cargo = r.get("CD_CARGO", "")
        sit = _txt(r.get("DS_SIT_TOT_TURNO")).upper()
        tipo = (r.get("NM_TIPO_ELEICAO") or "").upper()
        suplementar = "SUPLEMENTAR" in tipo
        if ano == MUNICIPAL and not suplementar:
            if cargo not in (PREFEITO, VICE_PREFEITO, VEREADOR) or (cargo != VICE_PREFEITO and not sit.startswith("ELEITO")):
                continue
        elif ano == GERAL and not suplementar:
            if cargo not in (PRESIDENTE, VICE_PRESIDENTE, GOVERNADOR, VICE_GOVERNADOR, DEP_ESTADUAL, DEP_DISTRITAL):
                continue
            if cargo in (PRESIDENTE, GOVERNADOR, DEP_ESTADUAL, DEP_DISTRITAL) and not sit.startswith("ELEITO"):
                continue
        elif ano == SEGUINTE and not suplementar:
            if cargo not in (PRESIDENTE, GOVERNADOR, SENADOR, DEP_FEDERAL, DEP_ESTADUAL, DEP_DISTRITAL):
                continue
        else:  # suplementares vêm do site de resultados (veja o começo do arquivo)
            continue
        k = (r.get("SQ_CANDIDATO"), r.get("NR_TURNO"), r.get("DT_ELEICAO"))
        if k in vistos:
            continue
        vistos.add(k)
        out.append({c: r.get(c, "") for c in COLUNAS})
    return out


def ler_vagas(zp: Path, ano: int) -> dict[str, int]:
    """{"SG_UE|CD_CARGO": vagas} da eleição ordinária."""
    out: dict[str, int] = {}
    for r in linhas_csv(zp, f"consulta_vagas_{ano}"):
        if "SUPLEMENTAR" in (r.get("NM_TIPO_ELEICAO") or "").upper():
            continue
        qt = r.get("QT_VAGA") or r.get("QT_VAGAS") or ""
        if qt.isdigit():
            out[f"{r['SG_UE']}|{r['CD_CARGO']}"] = int(qt)
    if not out:
        raise ValueError(f"arquivo de vagas de {ano} sem nenhuma linha")
    return out


def _lido(cache: Path, tipo: str, ano: int, ler, obrigatorio: bool = True):
    """Baixa o ZIP, lê o que interessa e guarda só isso no cache (o ZIP tem dezenas de MB e é apagado). A leitura vale
    VALIDADE_DIAS; se o TSE não responder, usa a última leitura boa e avisa com a data dela."""
    alvo = cache / f"{tipo}_{ano}.json"
    antigo = None
    if alvo.exists():
        try:
            antigo = json.loads(alvo.read_text(encoding="utf-8"))
        except ValueError:
            log.warning("Cache com defeito: %s", alvo.name)
    hoje = dt.date.today()
    if antigo and (hoje - dt.date.fromisoformat(antigo["lido_em"])).days < VALIDADE_DIAS.get(ano, 7):
        return antigo
    zp = cache / "zips" / f"{tipo}_{ano}.zip"
    url = url_arquivo(tipo, ano)
    try:
        download(url, zp, validar=eh_zip)
        dados = {"lido_em": hoje.isoformat(), "url": url, "linhas": ler(zp, ano)}
    except Exception as e:  # noqa: BLE001
        log.warning("TSE %s %s: %s", tipo, ano, e)
        if antigo:
            avisar(f"Quem me representa: o TSE não respondeu ({tipo}_{ano}); usamos a leitura de {_br(antigo['lido_em'])}")
            return antigo
        if obrigatorio:
            raise
        return None
    finally:
        zp.unlink(missing_ok=True)
        zp.with_suffix(".zip.part").unlink(missing_ok=True)
    write_json(alvo, dados)
    return dados


def _br(iso: str) -> str:
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


# ---------------------------------------------------------------- site de resultados do TSE

def ue5(ue: str) -> str:
    """Código da cidade no TSE com 5 dígitos, como no site de resultados (01120, não 1120)."""
    return str(ue).zfill(5)


def url_resultado(ciclo: str, eleicao: str, uf: str, ue: str, cargo: str) -> str:
    return ARQ_RESULTADO.format(ciclo=ciclo, eleicao=eleicao, uf=uf.lower(), ue=ue5(ue), cargo=cargo)


def eleitos_do_resultado(d: dict) -> list[dict]:
    """Eleitos de um arquivo do site de resultados (…-u.json), no formato das linhas do arquivo de candidatos, para
    passar por pessoa(). O vice da chapa vem dentro do titular ("vs")."""
    out = []
    for c in d.get("carg") or []:
        for a in c.get("agr") or []:
            for par in a.get("par") or []:
                for x in par.get("cand") or []:
                    if str(x.get("e", "")).lower() != "s":
                        continue
                    r = {"NM_URNA_CANDIDATO": x.get("nmu", ""), "NM_CANDIDATO": x.get("nm", ""), "SG_PARTIDO": par.get("sg", ""),
                         "NR_CANDIDATO": str(x.get("n", "")), "SQ_CANDIDATO": str(x.get("sqcand", "")),
                         "DT_NASCIMENTO": x.get("dt", ""), "DS_SIT_TOT_TURNO": x.get("st", "")}
                    vs = [v for v in x.get("vs") or [] if v.get("tp") == "v"]
                    if vs:
                        r["vice"] = {"NM_URNA_CANDIDATO": vs[0].get("nmu", ""), "NM_CANDIDATO": vs[0].get("nm", ""),
                                     "SG_PARTIDO": vs[0].get("sgp", ""), "NR_CANDIDATO": r["NR_CANDIDATO"],
                                     "SQ_CANDIDATO": str(vs[0].get("sqcand", ""))}
                    out.append(r)
    return out


def _resumo_resultado(d: dict) -> dict:
    """O que guardamos de cada arquivo do site de resultados."""
    if not isinstance(d, dict) or not isinstance(d.get("carg"), list):
        raise ValueError("resposta sem a lista de cargos")
    nv = [int(c["nv"]) for c in d["carg"] if str(c.get("nv", "")).isdigit()]
    return {"data": _data_iso(d.get("dt", "")), "totalizado": d.get("tf") == "s", "vagas": nv[0] if nv else None,
            "mensagens": [str(m) for m in d.get("mnae") or [] if m], "eleitos": eleitos_do_resultado(d)}


def _resumo_eleicoes(d: dict) -> list[dict]:
    """Eleições suplementares de prefeito ou de vereador do mandato de 2025 a 2028, da lista oficial do site."""
    out = []
    for pl in d.get("pl") or []:
        data = _data_iso(pl.get("dt", ""))
        if data < INICIO_SUPLEMENTAR:
            continue
        for e in pl.get("e") or []:
            if "SUPLEMENTAR" not in str(e.get("nm", "")).upper():
                continue
            for a in e.get("abr") or []:
                cargos = [str(c.get("cd")) for c in a.get("cp") or [] if str(c.get("cd")) in (PREFEITO, VEREADOR)]
                for mu in a.get("mu") or []:
                    for cargo in cargos:
                        out.append({"ciclo": pl.get("c", ""), "eleicao": str(e.get("cd", "")), "turno2": str(e.get("cdt2") or ""),
                                    "data": data, "uf": str(a.get("cd", "")).upper(), "ue": ue5(mu.get("cd", "")), "cargo": cargo})
    if not out and not d.get("pl"):
        raise ValueError("lista de eleições vazia")
    return out


class Resultados:
    """Leituras do site de resultados do TSE, guardadas no cache por VALIDADE_RESULTADO dias. Se o site não responder,
    usa a última leitura boa e avisa com a data dela."""

    def __init__(self, cache: Path, buscar=get_json):
        self.alvo = cache / "resultados.json"
        self.buscar = buscar
        try:
            self.guardado = json.loads(self.alvo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.guardado = {}
        self.guardado.setdefault("arquivos", {})
        self.velhas: list[str] = []  # datas das leituras antigas usadas porque o site não respondeu
        self.sem_resposta = 0
        self.eleicoes: list[dict] | None = None
        self.lido_em = ""

    def ler(self, url: str, resumir) -> dict | list | None:
        g = self.guardado["arquivos"].get(url)
        hoje = dt.date.today()
        if g and (hoje - dt.date.fromisoformat(g["lido_em"])).days < VALIDADE_RESULTADO:
            self.lido_em = max(self.lido_em, g["lido_em"])
            return g["dados"]
        try:
            dados = resumir(self.buscar(url, tries=3, timeout=60))
        except Exception as e:  # noqa: BLE001
            log.info("Site de resultados do TSE: %s (%s)", url, str(e)[:120])
            self.sem_resposta += 1
            if g:
                self.velhas.append(g["lido_em"])
                return g["dados"]
            return None
        self.guardado["arquivos"][url] = {"lido_em": hoje.isoformat(), "dados": dados}
        self.lido_em = hoje.isoformat()
        return dados

    def suplementares(self) -> dict[str, list[dict]]:
        """{código da cidade com 5 dígitos: [suplementares, da mais antiga à mais nova]}"""
        self.eleicoes = self.ler(ELEICOES_TSE, _resumo_eleicoes)
        if self.eleicoes is None:
            avisar("Quem me representa: o site de resultados do TSE não respondeu; as eleições suplementares ficaram de fora")
        por: dict[str, list[dict]] = defaultdict(list)
        for e in sorted(self.eleicoes or [], key=lambda e: e["data"]):
            por[e["ue"]].append(e)
        return por

    def resultado(self, ciclo: str, eleicao: str, uf: str, ue: str, cargo: str) -> tuple[dict | None, str]:
        url = url_resultado(ciclo, eleicao, uf, ue, cargo)
        return self.ler(url, _resumo_resultado), url

    def gravar(self) -> None:
        if self.velhas:
            avisar(f"Quem me representa: o site de resultados do TSE não respondeu; usamos a leitura de {_br(min(self.velhas))}")
        write_json(self.alvo, self.guardado)


# ---------------------------------------------------------------- montar

PEQUENAS = {"DA", "DAS", "DE", "DO", "DOS", "E", "DI", "DEL", "DU"}


def nome_proprio(s: str) -> str:
    """'JOSÉ DA SILVA' -> 'José da Silva'; 'SANTA BÁRBARA D'OESTE' -> "Santa Bárbara d'Oeste"; mantém 'II', 'III'."""
    out = []
    for i, w in enumerate((s or "").split()):
        u = w.upper()
        if i and u in PEQUENAS:
            out.append(u.lower())
        elif re.fullmatch(r"I{1,3}|IV|VI{0,3}", u):
            out.append(u)
        elif re.match(r"D['’]", u) and len(u) > 2:
            out.append("d'" + u[2:].capitalize())
        else:
            out.append("-".join(x.capitalize() for x in w.lower().split("-")))
    return " ".join(out)


def _chave_pessoa(r: dict) -> tuple[str, str] | None:
    nasc = _txt(r.get("DT_NASCIMENTO"))
    nome = norm_name(_txt(r.get("NM_CANDIDATO")))
    return (nome, nasc) if nome and nasc else None


RESULTADO = {"ELEITO": "eleito", "ELEITO POR QP": "eleito", "ELEITO POR MÉDIA": "eleito", "ELEITO POR MEDIA": "eleito",
             "SUPLENTE": "suplente", "NÃO ELEITO": "não eleito", "NAO ELEITO": "não eleito", "2º TURNO": "2º turno"}


def candidaturas_2026(linhas: list[dict]) -> dict[tuple[str, str], dict]:
    """(nome, nascimento) -> {cargo, uf, partido, resultado} na eleição de 2026 (o último turno de que participou)."""
    por: dict[tuple[str, str], dict] = {}
    for r in sorted(linhas, key=lambda r: int(r.get("NR_TURNO") or 1)):
        k = _chave_pessoa(r)
        if not k:
            continue
        sit = _txt(r.get("DS_SIT_TOT_TURNO")).upper()
        por[k] = {"cargo": NOME_CARGO.get(r["CD_CARGO"], ""), "cd": r["CD_CARGO"], "uf": r.get("SG_UF", ""),
                  "partido": _txt(r.get("SG_PARTIDO")),
                  "resultado": RESULTADO.get(sit, "candidatura sem votos válidos" if not sit else sit.lower())}
    return por


def pessoa(r: dict, cand26: dict, cargo: str) -> dict:
    """O que o site mostra de cada eleito. Sem CPF, sem data de nascimento."""
    nome = nome_proprio(_txt(r.get("NM_URNA_CANDIDATO")) or _txt(r.get("NM_CANDIDATO")))
    civil = nome_proprio(_txt(r.get("NM_CANDIDATO")))
    p = {"nome": nome, "partido": _txt(r.get("SG_PARTIDO")), "numero": _txt(r.get("NR_CANDIDATO")),
         "sq": _txt(r.get("SQ_CANDIDATO"))}
    if civil and norm_name(civil) != norm_name(nome):
        p["nome_completo"] = civil
    det = _txt(r.get("DS_DETALHE_SITUACAO_CAND")).upper()
    if re.search(r"CASSAD|INDEFERID|CANCELAD|RENÚNCIA|RENUNCIA|FALECID|NÃO CONHECIMENTO", det):
        p["situacao"] = det.capitalize()  # o TSE marca a candidatura como cassada, indeferida...: a página avisa
    k = _chave_pessoa(r)
    c = cand26.get(k) if k else None
    if c:
        mesmo = c["cd"] == cargo or {c["cd"], cargo} <= {DEP_ESTADUAL, DEP_DISTRITAL}
        p["em_2026"] = {"cargo": c["cargo"], "uf": c["uf"], "partido": c["partido"], "resultado": c["resultado"],
                        **({"reeleicao": True} if mesmo else {}),
                        # titular que disputou outro cargo teve de renunciar (Constituição, art. 14, § 6º)
                        **({"renunciou": True} if cargo in TITULARES and not mesmo else {})}
    return p


def _ultimo_turno(rs: list[dict]) -> list[dict]:
    t = max(int(r.get("NR_TURNO") or 1) for r in rs)
    return [r for r in rs if int(r.get("NR_TURNO") or 1) == t]


def titular_e_vice(rs: list[dict], cargo: str, cargo_vice: str, onde: str) -> tuple[dict | None, dict | None, int]:
    """O eleito para `cargo` (o do último turno) e o vice da mesma chapa (mesmo número)."""
    eleitos = {r["SQ_CANDIDATO"]: r for r in rs if r["CD_CARGO"] == cargo and _txt(r["DS_SIT_TOT_TURNO"]).upper().startswith("ELEITO")}
    if not eleitos:
        return None, None, 0
    tit = max(eleitos.values(), key=lambda r: (int(r.get("NR_TURNO") or 1), _data_iso(r.get("DT_ELEICAO", ""))))
    if len(eleitos) > 1:
        log.warning("%s: %d eleitos para %s; ficou o do último turno", onde, len(eleitos), NOME_CARGO[cargo])
    vices = [r for r in rs if r["CD_CARGO"] == cargo_vice and r.get("NR_CANDIDATO") == tit.get("NR_CANDIDATO")]

    def nota(r: dict) -> tuple:
        sit = (r.get("DS_SITUACAO_CANDIDATURA") or "").upper()
        return (bool(re.search(r"\b(APTO|DEFERIDO)\b", sit)) and "INAPTO" not in sit,
                _txt(r.get("DS_SIT_TOT_TURNO")).upper().startswith("ELEITO"), int(r.get("NR_TURNO") or 1))
    vice = max(vices, key=nota) if vices else None
    return tit, vice, int(tit.get("NR_TURNO") or 1)


def _ordem(p: dict) -> tuple:
    return (norm_name(p["nome"]), p.get("numero", ""))


def _suplementar(res: Resultados, e: dict) -> tuple[dict | None, str, int]:
    """Resultado de uma suplementar: o do 2º turno, se houve e já tem eleito; senão o do 1º."""
    if e["turno2"]:
        r, url = res.resultado(e["ciclo"], e["turno2"], e["uf"], e["ue"], e["cargo"])
        if r and r.get("eleitos"):
            return r, url, 2
    r, url = res.resultado(e["ciclo"], e["eleicao"], e["uf"], e["ue"], e["cargo"])
    return r, url, 1


def _aviso(r: dict | None, url: str, **extra) -> dict:
    """O que o TSE diz sobre a cidade no site de resultados, para a página mostrar."""
    a = {"mensagens": (r or {}).get("mensagens") or [], "fonte": url, **extra}
    if r is not None:
        a["totalizado"] = bool(r.get("totalizado"))
    return a


def montar(cand: dict[int, list[dict]], vagas: dict[int, dict[str, int]], politicos: list[dict], saida: Path,
           fontes: dict, res: Resultados | None = None) -> dict:
    """Grava os arquivos do site e devolve um resumo das conferências."""
    pasta = saida / "representantes"
    c26 = candidaturas_2026(cand.get(SEGUINTE) or [])
    resumo: dict = {"cidades": 0, "vereadores": 0, "sem_prefeito": [], "vagas_diferentes": [], "suplementares": 0,
                    "suplementares_sem_resultado": [], "renunciaram": 0, "estados": 0, "estaduais_diferentes": [],
                    "federais_diferentes": []}
    sups = res.suplementares() if res else {}

    # --- cidades (eleição municipal de 2024 e suplementares)
    por_ue: dict[str, list[dict]] = defaultdict(list)
    nome_ue: dict[str, tuple[str, str]] = {}
    for r in cand.get(MUNICIPAL) or []:
        if "SUPLEMENTAR" in (r.get("NM_TIPO_ELEICAO") or "").upper():
            continue
        por_ue[r["SG_UE"]].append(r)
        nome_ue.setdefault(r["SG_UE"], (r.get("NM_UE", ""), r.get("SG_UF", "")))
    municipios = []
    for ue in sorted(por_ue):
        rs = por_ue[ue]
        nome, uf = nome_ue[ue]
        if uf not in UFS or not re.fullmatch(r"\d{4,6}", ue):
            continue
        cidade = nome_proprio(nome)
        onde = f"{cidade} ({uf})"
        pref, vice, turnos = titular_e_vice(rs, PREFEITO, VICE_PREFEITO, onde)
        out: dict = {"ue": ue, "nome": cidade, "uf": uf, "eleicao": MUNICIPAL}
        avisos: dict = {}
        cid_sups = sups.get(ue5(ue), [])
        # prefeito: a última suplementar da cidade, se houve, troca prefeito e vice
        sp = [e for e in cid_sups if e["cargo"] == PREFEITO]
        if sp and res:
            r, url, t = _suplementar(res, sp[-1])
            novos = (r or {}).get("eleitos") or []
            if novos:
                out["suplementar"] = {"data": sp[-1]["data"], "fonte": url, "eleitos_2024": {
                    "prefeito": pessoa(pref, {}, PREFEITO) if pref else None,
                    "vice_prefeito": pessoa(vice, {}, VICE_PREFEITO) if vice else None}}
                if len(novos) > 1:
                    log.warning("%s: %d eleitos na suplementar de prefeito; ficou o primeiro", onde, len(novos))
                pref, vice, turnos = novos[0], novos[0].get("vice"), t
                resumo["suplementares"] += 1
            else:  # marcada, ou ainda sem resultado: o aviso da eleição de 2024 explica por que foi refeita
                r0, url0 = res.resultado(*ORDINARIA_2024, uf, ue, PREFEITO)
                avisos["prefeito"] = _aviso(r0, url0, suplementar=sp[-1]["data"])
                resumo["suplementares_sem_resultado"].append(f"{onde}: prefeito, {_br(sp[-1]['data'])}")
        if pref:
            out["prefeito"] = pessoa(pref, c26, PREFEITO)
            out["prefeito"]["turnos"] = turnos
            resumo["renunciaram"] += bool(out["prefeito"].get("em_2026", {}).get("renunciou"))
        else:
            resumo["sem_prefeito"].append(onde)
            if res and "prefeito" not in avisos:
                r, url = res.resultado(*ORDINARIA_2024, uf, ue, PREFEITO)
                if r is not None:
                    avisos["prefeito"] = _aviso(r, url)
        if vice:
            out["vice_prefeito"] = pessoa(vice, c26, VICE_PREFEITO)
        vers = [pessoa(r, c26, VEREADOR) for r in {r["SQ_CANDIDATO"]: r for r in rs if r["CD_CARGO"] == VEREADOR}.values()]
        vagas_cm = vagas.get(MUNICIPAL, {}).get(f"{ue}|{VEREADOR}")
        # vereadores: suplementar para todas as cadeiras troca a lista inteira; para só algumas (o TSE refaz a conta de
        # uma cadeira, por exemplo), a lista de 2024 fica e a página mostra quem entrou nela
        sv = [e for e in cid_sups if e["cargo"] == VEREADOR]
        if sv and res:
            r, url, _ = _suplementar(res, sv[-1])
            novos = (r or {}).get("eleitos") or []
            if novos:
                todas = r.get("vagas") is None or vagas_cm is None or r["vagas"] >= vagas_cm
                out["suplementar_vereadores"] = {"data": sv[-1]["data"], "fonte": url, "cadeiras": r.get("vagas") or len(novos),
                                                 "eleitos_2024": len(vers)}
                if todas:
                    vers = [pessoa(x, c26, VEREADOR) for x in novos]
                else:
                    out["suplementar_vereadores"]["eleitos"] = sorted((pessoa(x, c26, VEREADOR) for x in novos), key=_ordem)
                resumo["suplementares"] += 1
            else:
                r0, url0 = res.resultado(*ORDINARIA_2024, uf, ue, VEREADOR)
                avisos["vereadores"] = _aviso(r0, url0, suplementar=sv[-1]["data"])
                resumo["suplementares_sem_resultado"].append(f"{onde}: vereadores, {_br(sv[-1]['data'])}")
        out["vereadores"] = sorted(vers, key=_ordem)
        out["vagas_vereadores"] = vagas_cm
        if out["vagas_vereadores"] is not None and out["vagas_vereadores"] != len(vers):
            resumo["vagas_diferentes"].append(f"{onde}: {len(vers)} eleitos, {out['vagas_vereadores']} vagas")
            if res and "vereadores" not in avisos and len(vers) < out["vagas_vereadores"]:
                r, url = res.resultado(*ORDINARIA_2024, uf, ue, VEREADOR)
                if r is not None:
                    avisos["vereadores"] = _aviso(r, url)
        if avisos:
            out["aviso_tse"] = avisos
        resumo["cidades"] += 1
        resumo["vereadores"] += len(vers)
        write_json(pasta / "m" / f"{ue}.json", out)
        municipios.append([ue, cidade, uf])

    # --- estados (eleição geral de 2022) e o Congresso de hoje
    geral = cand.get(GERAL) or []
    por_uf: dict[str, list[dict]] = defaultdict(list)
    for r in geral:
        if "SUPLEMENTAR" not in (r.get("NM_TIPO_ELEICAO") or "").upper():
            por_uf[r["SG_UF"]].append(r)
    hoje = [p for p in politicos if p.get("em_exercicio") is not False and p.get("casa") in ("camara", "senado")]
    for uf, nome_uf in UFS.items():
        rs = por_uf.get(uf, [])
        gov, vgov, turnos = titular_e_vice(rs, GOVERNADOR, VICE_GOVERNADOR, uf)
        dep = DEP_DISTRITAL if uf == "DF" else DEP_ESTADUAL
        deps = [pessoa(r, c26, dep) for r in {r["SQ_CANDIDATO"]: r for r in rs if r["CD_CARGO"] == dep}.values()]
        vag_est = vagas.get(GERAL, {}).get(f"{uf}|{dep}")
        if vag_est is not None and vag_est != len(deps):
            resumo["estaduais_diferentes"].append(f"{uf}: {len(deps)} eleitos, {vag_est} vagas")
        fed = sorted(({"id": p["id"], "nome": p["nome"], "partido": p.get("partido", ""), "foto": p.get("foto", ""),
                       "cargo": p.get("cargo", "")} for p in hoje if p.get("uf") == uf and p["casa"] == "camara"), key=_ordem)
        sen = sorted(({"id": p["id"], "nome": p["nome"], "partido": p.get("partido", ""), "foto": p.get("foto", ""),
                       "cargo": p.get("cargo", "")} for p in hoje if p.get("uf") == uf and p["casa"] == "senado"), key=_ordem)
        vag_fed = vagas.get(GERAL, {}).get(f"{uf}|{DEP_FEDERAL}")
        if vag_fed is not None and vag_fed != len(fed):
            resumo["federais_diferentes"].append(f"{uf}: {len(fed)} em exercício, {vag_fed} vagas")
        e = {"uf": uf, "nome": nome_uf, "eleicao": GERAL,
             "governador": {**pessoa(gov, c26, GOVERNADOR), "turnos": turnos} if gov else None,
             "vice_governador": pessoa(vgov, c26, VICE_GOVERNADOR) if vgov else None,
             "deputados_estaduais": sorted(deps, key=_ordem), "vagas_estaduais": vag_est,
             "casa_estadual": "Câmara Legislativa" if uf == "DF" else "Assembleia Legislativa",
             "cargo_estadual": "Deputado distrital" if uf == "DF" else "Deputado estadual",
             "deputados_federais": fed, "vagas_federais": vag_fed, "senadores": sen}
        resumo["renunciaram"] += bool(((e["governador"] or {}).get("em_2026") or {}).get("renunciou"))
        resumo["estados"] += 1
        write_json(pasta / "uf" / f"{uf}.json", e)
    # Brasília não tem prefeito nem vereadores: quem procura a cidade cai no Distrito Federal
    municipios.append(["DF", "Brasília", "DF"])

    # --- presidente (eleição geral de 2022)
    pres, vpres, turnos = titular_e_vice([r for r in geral if r["CD_CARGO"] in (PRESIDENTE, VICE_PRESIDENTE)],
                                         PRESIDENTE, VICE_PRESIDENTE, "Brasil")
    indice = {
        "atualizado_em": dt.date.today().isoformat(),
        "eleicoes": {"municipal": MUNICIPAL, "geral": GERAL, "seguinte": SEGUINTE},
        "municipios": sorted(municipios, key=lambda m: (norm_name(m[1]), m[2])),
        "presidente": {**pessoa(pres, c26, PRESIDENTE), "turnos": turnos} if pres else None,
        "vice_presidente": pessoa(vpres, c26, VICE_PRESIDENTE) if vpres else None,
        "fontes": fontes,
        "conferencia": {"cidades": resumo["cidades"], "vereadores": resumo["vereadores"],
                        "vagas_diferentes": len(resumo["vagas_diferentes"]), "sem_prefeito": len(resumo["sem_prefeito"]),
                        "suplementares": resumo["suplementares"]},
    }
    if res and res.lido_em:
        fontes["resultados"] = {"url": ELEICOES_TSE, "pagina": PAGINA_RESULTADOS, "lido_em": res.lido_em}
    write_json(pasta / "indice.json", indice)
    return resumo


# ---------------------------------------------------------------- coleta

def fontes_de(lidos: dict) -> dict:
    f = {"camara": API_CAMARA, "senado": API_SENADO, "constituicao": CONSTITUICAO, "divulga": DIVULGA,
         "resultados_pagina": PAGINA_RESULTADOS}
    for chave, (tipo, ano) in {"candidatos_municipal": ("consulta_cand", MUNICIPAL), "vagas_municipal": ("consulta_vagas", MUNICIPAL),
                               "candidatos_geral": ("consulta_cand", GERAL), "vagas_geral": ("consulta_vagas", GERAL),
                               "candidatos_seguinte": ("consulta_cand", SEGUINTE)}.items():
        d = lidos.get((tipo, ano))
        if d:
            f[chave] = {"url": d["url"], "pagina": PAGINA_CKAN.format(ano=ano), "lido_em": d["lido_em"]}
    return f


def coletar(saida: Path, cache: Path, buscar=get_json) -> dict:
    """Lê os arquivos do TSE (com cache) e o politicos.json já gravado, e grava data/representantes/."""
    cache = cache / "representantes"
    lidos = {
        ("consulta_cand", MUNICIPAL): _lido(cache, "consulta_cand", MUNICIPAL, ler_candidatos),
        ("consulta_vagas", MUNICIPAL): _lido(cache, "consulta_vagas", MUNICIPAL, ler_vagas, obrigatorio=False),
        ("consulta_cand", GERAL): _lido(cache, "consulta_cand", GERAL, ler_candidatos),
        ("consulta_vagas", GERAL): _lido(cache, "consulta_vagas", GERAL, ler_vagas, obrigatorio=False),
    }
    seguinte = _lido(cache, "consulta_cand", SEGUINTE, ler_candidatos, obrigatorio=False)
    if seguinte is None:
        avisar("Quem me representa: a lista de candidatos de 2026 do TSE não respondeu; a página não mostra quem deixou o cargo para concorrer")
    lidos[("consulta_cand", SEGUINTE)] = seguinte
    cand: dict = {MUNICIPAL: lidos[("consulta_cand", MUNICIPAL)]["linhas"], GERAL: lidos[("consulta_cand", GERAL)]["linhas"],
                  SEGUINTE: (seguinte or {}).get("linhas") or []}
    vagas = {ano: (lidos[("consulta_vagas", ano)] or {}).get("linhas") or {} for ano in (MUNICIPAL, GERAL)}
    try:
        politicos = json.loads((saida / "politicos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        politicos = []
        avisar("Quem me representa: sem a lista de deputados federais e senadores nesta coleta")
    res = Resultados(cache, buscar)
    resumo = montar(cand, vagas, politicos, saida, fontes_de(lidos), res)
    res.gravar()
    log.info("Quem me representa: %d cidades, %d vereadores, %d estados, %d suplementares, %d renúncias para 2026",
             resumo["cidades"], resumo["vereadores"], resumo["estados"], resumo["suplementares"], resumo["renunciaram"])
    for k in ("sem_prefeito", "vagas_diferentes", "suplementares_sem_resultado", "estaduais_diferentes", "federais_diferentes"):
        if resumo[k]:
            log.warning("Quem me representa, %s (%d): %s", k, len(resumo[k]), "; ".join(resumo[k][:15]))
    if resumo["cidades"] < MIN_CIDADES:
        raise RuntimeError(f"Quem me representa: só {resumo['cidades']} cidades no arquivo de 2024")
    return resumo


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera data/representantes/ (quem me representa, por cidade)")
    ap.add_argument("--saida", type=Path, required=True, help="pasta data/ do site, com o politicos.json já gravado")
    ap.add_argument("--cache", type=Path, default=Path(".cache"))
    ap.add_argument("--mostrar", nargs="*", default=[], help="cidades (código do TSE) para mostrar no fim, para conferir")
    ap.add_argument("--conferir", action="store_true", help="no fim, confere prefeitos sorteados no site de resultados do TSE")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = coletar(a.saida, a.cache)
    print(json.dumps({k: (v if not isinstance(v, list) else {"n": len(v), "exemplos": v[:30]}) for k, v in r.items()},
                     ensure_ascii=False, indent=1))
    pasta = a.saida / "representantes"
    idx = json.loads((pasta / "indice.json").read_text(encoding="utf-8"))
    print("Presidente:", json.dumps(idx.get("presidente"), ensure_ascii=False), json.dumps(idx.get("vice_presidente"), ensure_ascii=False))
    for uf in sorted(UFS):
        e = json.loads((pasta / "uf" / f"{uf}.json").read_text(encoding="utf-8"))
        g = e.get("governador") or {}
        print(f"{uf}: governador {g.get('nome')} ({g.get('partido')}) {json.dumps(g.get('em_2026'), ensure_ascii=False)}; "
              f"vice {(e.get('vice_governador') or {}).get('nome')}; {len(e['deputados_estaduais'])}/{e['vagas_estaduais']} estaduais; "
              f"{len(e['deputados_federais'])}/{e['vagas_federais']} federais; {len(e['senadores'])} senadores")
    from .validar import Resultado, _conferir_representantes
    v = Resultado()
    _conferir_representantes(a.saida, v)
    print("Conferência (validar):", json.dumps({"erros": v.erros[:30], "alertas": v.alertas[:30]}, ensure_ascii=False, indent=1))
    if a.conferir:
        import random

        from .verificar import Prazo, prefeito_resultado
        c = prefeito_resultado(a.saida, random.Random(dt.date.today().isoformat()), Prazo(5)).json()
        print("Conferência com o site de resultados do TSE:", json.dumps(c, ensure_ascii=False, indent=1))
    for ue in a.mostrar:
        f = pasta / "m" / f"{ue}.json"
        if f.exists():
            m = json.loads(f.read_text(encoding="utf-8"))
            print(json.dumps({**m, "vereadores": [f"{v['nome']} ({v['partido']})" for v in m["vereadores"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
