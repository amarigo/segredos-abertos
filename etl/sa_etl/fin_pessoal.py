"""Quem trabalha para o governo federal: concursados, cargos de confiança e comissionados sem concurso.

Três fontes oficiais:
- Executivo (servidores civis): cadastro e remuneração do SIAPE no Portal da Transparência, um arquivo por mês,
      https://portaldatransparencia.gov.br/download-de-dados/servidores
  Por que arquivo e não API: a API do Portal (servidores/por-orgao) só conta pessoas; a remuneração na API é uma
  consulta por servidor (mais de 600 mil consultas por mês). O arquivo traz cadastro e remuneração de todos de uma vez.
- Câmara dos Deputados: arquivo de funcionários dos dados abertos da Câmara (a API v2 não tem consulta de
  funcionários; o arquivo é a publicação oficial),
      https://dadosabertos.camara.leg.br/arquivos/funcionarios/json/funcionarios.json
- Senado Federal: API de dados abertos administrativos do Senado (servidores e remuneração do mês),
      https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html

Cargos e funções de confiança (CCE, FCE, FG, CD, FC, CNE, secretário parlamentar) são de livre nomeação: quem
ocupa pode ser trocado a cada governo ou a cada mandato. Os comissionados sem concurso saem do serviço público
quando são exonerados; os concursados com função de confiança voltam ao cargo de origem.
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .fin_receita import numero
from .util import download, eh_zip, get_json

log = logging.getLogger("sa_etl.financas")

URL_SIAPE = "https://portaldatransparencia.gov.br/download-de-dados/servidores/{am}_Servidores_SIAPE"
FONTE_SIAPE = "https://portaldatransparencia.gov.br/download-de-dados/servidores"
URL_CAMARA = "https://dadosabertos.camara.leg.br/arquivos/funcionarios/json/funcionarios.json"
URL_SENADO = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/servidores"
URL_SENADO_REM = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/servidores/remuneracoes/{ano}/{mes}"

# ---------------------------------------------------------------- Executivo (SIAPE)

SEM_VINCULO = {"NOMEADO CARGO COMIS.", "SEM VINCULO", "NATUREZA ESPECIAL"}
SEM_FUNCAO = {"", "sem informação", "sigiloso", "-1"}
GRUPOS_EXEC = [
    ("comissionado", "Comissionados sem concurso", "Nomeados para cargo de confiança sem ser servidores de carreira. Saem quando o governo troca."),
    ("confianca", "Concursados em cargo ou função de confiança", "Servidores de carreira que ocupam um cargo de chefia ou assessoramento, com gratificação. A função muda com o governo; o servidor fica."),
    ("concursado", "Concursados sem função de confiança", "Servidores e empregados públicos de carreira, que entraram por concurso."),
    ("temporario", "Temporários, residentes e Mais Médicos", "Contratos por tempo determinado, professores substitutos, residentes e médicos do programa Mais Médicos."),
    ("sigiloso", "Dados sigilosos", "Servidores de órgãos de inteligência e segurança, sem dados públicos."),
]


def grupo_siape(situacao: str, funcao: str) -> str:
    s = situacao.strip().upper()
    if s == "SIGILOSO":
        return "sigiloso"
    if s in SEM_VINCULO:
        return "comissionado"
    if any(t in s for t in ("TEMPORARIO", "SUBSTITUTO", "VISITANTE", "RESIDENCIA", "PMM")):
        return "temporario"
    if funcao.strip().lower() not in SEM_FUNCAO:
        return "confianca"
    return "concursado"


def tipo_funcao(funcao: str) -> str:
    """Nome curto do tipo de cargo ou função de confiança."""
    f = funcao.strip().upper()
    for chave, nome in (("CARGO COMISSIONADO EXECUTIVO", "CCE (cargo comissionado executivo)"),
                        ("FUNCÃO COMISSIONADA EXECUTIVA", "FCE (função comissionada executiva)"),
                        ("FUNÇÃO COMISSIONADA EXECUTIVA", "FCE (função comissionada executiva)"),
                        ("FUNCAO COMISSIONADA EXECUTIVA", "FCE (função comissionada executiva)"),
                        ("FUNCAO GRATIFICADA - IFES", "FG de universidades e institutos"),
                        ("CARGO DE DIRECAO - CD - IFES", "CD de universidades e institutos"),
                        ("FUNCAO COMISSIONADA DE COORD", "FCC (coordenação de curso)"),
                        ("FUNCAO GRATIFICADA", "FG (função gratificada)"),
                        ("GRATIF", "Gratificações de representação")):
        if f.startswith(chave):
            return nome
    return "Outros cargos e funções"


REM_BRUTA = ("REMUNERAÇÃO BÁSICA BRUTA (R$)", "ABATE-TETO (R$)", "GRATIFICAÇÃO NATALINA (R$)",
             "ABATE-TETO DA GRATIFICAÇÃO NATALINA (R$)", "FÉRIAS (R$)", "OUTRAS REMUNERAÇÕES EVENTUAIS (R$)")
REM_INDENIZ = "TOTAL DE VERBAS INDENIZATÓRIAS (R$)(*)"


def baixar_siape(ano: int, mes: int, cache: Path) -> Path | None:
    am = f"{ano}{mes:02d}"
    dest = cache / "siape" / f"{am}_Servidores_SIAPE.zip"
    try:
        return download(URL_SIAPE.format(am=am), dest, validar=eh_zip)  # o mês fechado não muda: cache para sempre
    except Exception as e:  # noqa: BLE001
        log.info("SIAPE %s: indisponível (%s)", am, str(e)[:120])
        return None


def _csv(z: zipfile.ZipFile, fim: str):
    nome = next((n for n in z.namelist() if n.endswith(fim)), None)
    if not nome:
        return
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def resumir_siape(arq: Path) -> dict:
    """Pessoas e folha do mês por grupo, por tipo de função e por órgão."""
    pessoa: dict[str, tuple[str, str, str]] = {}  # id -> (grupo, tipo de função, órgão superior de exercício)
    ordem = {g: i for i, (g, _, _) in enumerate(GRUPOS_EXEC)}
    with zipfile.ZipFile(arq) as z:
        for r in _csv(z, "_Cadastro.csv"):
            pid = r.get("Id_SERVIDOR_PORTAL", "")
            g = grupo_siape(r.get("SITUACAO_VINCULO", ""), r.get("FUNCAO", ""))
            tf = tipo_funcao(r.get("FUNCAO", "")) if g in ("comissionado", "confianca") and r.get("FUNCAO", "").strip().lower() not in SEM_FUNCAO else ""
            org = (r.get("ORGSUP_EXERCICIO") or r.get("ORGSUP_LOTACAO") or "").strip()
            antes = pessoa.get(pid)
            # uma pessoa com mais de um vínculo fica no grupo mais "de confiança" (comissionado > confiança > ...)
            if antes is None or ordem[g] < ordem[antes[0]]:
                pessoa[pid] = (g, tf or (antes[1] if antes else ""), org if org and org.lower() != "sem informação" else (antes[2] if antes else ""))
        folha: dict[str, float] = defaultdict(float)
        indeniz: dict[str, float] = defaultdict(float)
        por_tipo: dict[str, list] = defaultdict(lambda: [0, 0.0])
        por_org: dict[str, dict] = defaultdict(lambda: {"comissionado": 0, "confianca": 0, "total": 0, "folha_confianca": 0.0})
        com_rem = 0
        for r in _csv(z, "_Remuneracao.csv"):
            pid = r.get("Id_SERVIDOR_PORTAL", "")
            g, tf, org = pessoa.get(pid, ("concursado", "", ""))
            v = sum(numero(r.get(c, "")) for c in REM_BRUTA)
            com_rem += 1
            folha[g] += v
            indeniz[g] += numero(r.get(REM_INDENIZ, ""))
            if tf:
                por_tipo[tf][1] += v
            if org and g in ("comissionado", "confianca"):
                por_org[org]["folha_confianca"] += v
    contagem = Counter(g for g, _, _ in pessoa.values())
    for g, tf, org in pessoa.values():
        if tf:
            por_tipo[tf][0] += 1
        if org:
            por_org[org]["total"] += 1
            if g in ("comissionado", "confianca"):
                por_org[org][g] += 1
    grupos = [{"id": g, "nome": n, "explica": e, "pessoas": contagem.get(g, 0), "folha_mes": round(folha.get(g, 0.0), 2),
               "indenizacoes_mes": round(indeniz.get(g, 0.0), 2)} for g, n, e in GRUPOS_EXEC]
    orgaos = sorted(({"nome": o, **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}} for o, d in por_org.items()),
                    key=lambda o: -(o["comissionado"] + o["confianca"]))
    return {
        "pessoas": len(pessoa), "com_remuneracao": com_rem,
        "grupos": grupos,
        "funcoes": sorted(([t, n, round(v, 2)] for t, (n, v) in por_tipo.items()), key=lambda t: -t[1]),
        "orgaos": orgaos[:40],
    }


def coletar_siape(ano: int, mes_max: int, cache: Path) -> dict | None:
    """O mês mais recente do ano (até mes_max) que já está publicado."""
    for mes in range(mes_max, 0, -1):
        arq = baixar_siape(ano, mes, cache)
        if not arq:
            continue
        try:
            r = resumir_siape(arq)
        except Exception:  # noqa: BLE001
            log.exception("SIAPE %d/%02d: erro ao ler", ano, mes)
            return None
        log.info("SIAPE %d/%02d: %d pessoas", ano, mes, r["pessoas"])
        return {"ano": ano, "mes": mes, **r, "url": URL_SIAPE.format(am=f"{ano}{mes:02d}"), "fonte": FONTE_SIAPE}
    return None


# ---------------------------------------------------------------- Câmara

GRUPOS_CAMARA = {
    "Secretário Parlamentar": ("secretario", "Secretários parlamentares", "Equipe do gabinete de cada deputado, escolhida por ele, sem concurso. Paga com a verba de gabinete."),
    "Cargo de Natureza Especial": ("cne", "Cargos de natureza especial", "Comissionados sem concurso nas lideranças de partido, na Mesa e em órgãos da Câmara."),
    "Quadro Efetivo - RJU": ("efetivo", "Servidores concursados", "Servidores de carreira da Câmara."),
    "Parlamentar": ("parlamentar", "Deputados", "Os 513 deputados e os suplentes em exercício."),
}


def coletar_camara() -> dict | None:
    try:
        dados = get_json(URL_CAMARA, timeout=300).get("dados") or []
    except Exception as e:  # noqa: BLE001
        log.warning("Câmara: funcionários indisponíveis (%s)", e)
        return None
    cont: Counter = Counter()
    efetivo_funcao = 0
    for f in dados:
        g = GRUPOS_CAMARA.get(str(f.get("grupo") or "").strip())
        chave = g[0] if g else "outro"
        cont[chave] += 1
        if chave == "efetivo" and str(f.get("funcao") or "").strip():
            efetivo_funcao += 1
    grupos = [{"id": c, "nome": n, "explica": e, "pessoas": cont.get(c, 0)} for c, n, e in GRUPOS_CAMARA.values()]
    if cont.get("outro"):
        grupos.append({"id": "outro", "nome": "Outros", "explica": "", "pessoas": cont["outro"]})
    return {"grupos": grupos, "efetivos_com_funcao": efetivo_funcao, "url": URL_CAMARA}


# ---------------------------------------------------------------- Senado

GRUPOS_SENADO = {
    "COMISSIONADO": ("comissionado", "Comissionados sem concurso", "Nos gabinetes dos senadores, lideranças e órgãos do Senado."),
    "EFETIVO": ("efetivo", "Servidores concursados", "Servidores de carreira do Senado."),
    "REQUISITADO": ("requisitado", "Requisitados de outros órgãos", "Servidores de outros órgãos trabalhando no Senado."),
    "PARLAMENTAR": ("parlamentar", "Senadores", "Os 81 senadores e suplentes em exercício."),
}


def coletar_senado(ano: int, mes_max: int) -> dict | None:
    try:
        servidores = get_json(URL_SENADO, timeout=300)
    except Exception as e:  # noqa: BLE001
        log.warning("Senado: servidores indisponíveis (%s)", e)
        return None
    cont: Counter = Counter()
    efetivo_funcao = 0
    for s in servidores or []:
        if str(s.get("situacao") or "").upper() != "ATIVO":
            continue
        g = GRUPOS_SENADO.get(str(s.get("vinculo") or "").upper())
        chave = g[0] if g else "outro"
        cont[chave] += 1
        if chave == "efetivo" and s.get("funcao"):
            efetivo_funcao += 1
    # Sem folha por grupo: na API de remuneração do Senado só ~15% dos registros têm o mesmo "sequencial" da API de
    # servidores (conferido em out/2026: 1.473 de 10.633), então somar a folha por vínculo daria um número errado.
    # Mostramos só as pessoas por vínculo e o link para a remuneração oficial.
    grupos = [{"id": c, "nome": n, "explica": e, "pessoas": cont.get(c, 0), "folha_mes": None}
              for c, n, e in GRUPOS_SENADO.values()]
    return {"grupos": grupos, "efetivos_com_funcao": efetivo_funcao, "mes": None, "ano": ano,
            "url": URL_SENADO, "url_remuneracao": URL_SENADO_REM.format(ano=ano, mes=mes_max)}
