"""Deputados estaduais (Assembleia Legislativa de Minas Gerais, ALMG): quem são, quanto gastam e o que fazem.

Fontes (dados abertos da ALMG, https://dadosabertos.almg.gov.br/):
- deputados em exercício: API /api/v2/deputados/em_exercicio (nome, partido);
- arquivo "deputados": todos os deputados, com o link da página de cada um no site da ALMG;
- verba indenizatória (o equivalente estadual da cota parlamentar): a API
  /api/v2/prestacao_contas/verbas_indenizatorias/deputados/{id}/{ano}/{mes} traz cada nota do mês (tipo de
  despesa, quem emitiu, CNPJ ou CPF, valor reembolsado). O arquivo CSV de verbas da ALMG vem sem os valores, por
  isso usamos a API: uma consulta por deputado e mês. Meses fechados ficam no cache para sempre; os 3 últimos são
  consultados de novo a cada poucos dias (o deputado tem prazo para apresentar as notas). Para não sobrecarregar
  a ALMG, cada execução faz no máximo ORCAMENTO_VERBA consultas, dos meses mais novos para os mais antigos: o
  histórico se completa em poucos dias;
- arquivo "proposicoes" (um por ano): cada proposta, com os autores e a situação (aprovada, arquivada...).

CPF: quem emitiu uma nota como pessoa física aparece só como "pessoa física", sem nenhum número.
A ALMG não publica nos dados abertos o voto de cada deputado nem a presença em Plenário; por isso não há essas
partes aqui (a página explica).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from sa_etl.util import get, id_seguro, url_segura, write_json

from . import fontes

log = logging.getLogger("mg_etl.almg")

BASE = "https://dadosabertos.almg.gov.br"
API_EM_EXERCICIO = BASE + "/api/v2/deputados/em_exercicio?formato=json"
CSV_DEPUTADOS = BASE + "/arquivo/deputados/download"
API_VERBA = BASE + "/api/v2/prestacao_contas/verbas_indenizatorias/deputados/{id}/{ano}/{mes}?formato=json"
CSV_PROPOSICOES = BASE + "/arquivo/proposicoes/download?ano={ano}"
PAGINA_VERBA = "https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/"
PAGINA_VERBA_DEPUTADO = PAGINA_VERBA + "detalhe.html?id={id}"
PAGINA_DEPUTADO = "https://www.almg.gov.br/a-assembleia/deputados/deputado/?id={id}"
# Conferido: /proposicoes/PL/3221/2025/ dá 404; a página do texto do projeto é esta
PAGINA_PROPOSICAO = "https://www.almg.gov.br/atividade-parlamentar/projetos-de-lei/texto/?tipo={sigla}&num={numero}&ano={ano}"
INICIO_LEGISLATURA = 2023
ANOS_RECENTES = 2  # foco no ano atual e no anterior (pedido em 24/10/2026): a verba desses anos completa primeiro
ORCAMENTO_VERBA = 700  # consultas à API da verba por execução
PAUSA_VERBA = 0.4  # segundos entre consultas (a API responde 429 se formos rápidos demais)
MESES_ABERTOS = 3  # meses mais recentes, que ainda podem receber notas

COL_PROPOSICOES = {"SiglaTipoProposicao", "Numero", "Ano", "Ementa", "Situacao", "Autores"}

# Tipos de proposição (siglas da ALMG)
PROJETOS = {"PL", "PLC", "PEC", "PRE"}  # projeto de lei, de lei complementar, de emenda à Constituição, de resolução
REQUERIMENTOS = {"RQN", "RQC", "RQ", "REQ"}  # requerimentos (de Plenário, de comissão)
APROVADA = re.compile(r"TRANSFORMAD|SANCIONAD|PROMULGAD|APROVAD|NORMA JURIDICA|LEI \d", re.I)


def anos_legislatura(hoje: dt.date | None = None) -> list[int]:
    hoje = hoje or dt.date.today()
    return list(range(_primeiro_ano(hoje), hoje.year + 1))


def _primeiro_ano(hoje: dt.date) -> int:
    return max(INICIO_LEGISLATURA, hoje.year - ANOS_RECENTES + 1)


# ---------------------------------------------------------------- quem são

def em_exercicio(cache: Path) -> list[dict]:
    """Deputados em exercício (id, nome, partido). Se a API falhar, usa a última lista boa do cache."""
    alvo = cache / "almg" / "em_exercicio.json"
    try:
        dados = get(API_EM_EXERCICIO, timeout=60).json()
        lista = [{"id": str(d["id"]), "nome": str(d["nome"]).strip(), "partido": str(d.get("partido") or "").strip()}
                 for d in dados["list"]]
        if len(lista) < 50:
            raise ValueError(f"só {len(lista)} deputados")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")
        return lista
    except Exception as e:  # noqa: BLE001
        log.warning("ALMG em exercício: %s", e)
        if alvo.exists():
            fontes.avisar("ALMG: a lista de deputados em exercício não respondeu; usamos a última lista baixada")
            return json.loads(alvo.read_text(encoding="utf-8"))
        raise


def paginas(cache: Path) -> dict[str, str]:
    """id -> link da página do deputado no site da ALMG (do arquivo 'deputados')."""
    texto = fontes.baixar(CSV_DEPUTADOS, cache / "almg" / "deputados.csv", 20, "ALMG (lista de deputados)",
                          colunas=("Codigo", "Nome"))
    if not texto:
        return {}
    out = {}
    for r in fontes.ler_csv(texto):
        u = url_segura(r.get("PaginaAlmg") or "")
        if r.get("Codigo") and u:
            out[r["Codigo"].strip()] = u
    return out


# ---------------------------------------------------------------- verba indenizatória

def _mes_ano(s: str) -> tuple[int, int] | None:
    """'01/02/2019' ou '2019-02-01' ou '02/2019' -> (2019, 2)."""
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"(?:\d{1,2}/)?(\d{1,2})/(\d{4})", s)
    if m:
        return int(m.group(2)), int(m.group(1))
    return None


def _data_iso(s: str) -> str:
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def meses_legislatura(hoje: dt.date) -> list[tuple[int, int]]:
    """(ano, mês) dos anos acompanhados (desde a posse, em fevereiro de 2023, no máximo os ANOS_RECENTES mais
    novos) até o mês atual, do mais novo para o mais antigo."""
    out, a, m = [], hoje.year, hoje.month
    inicio = (INICIO_LEGISLATURA, 2) if _primeiro_ano(hoje) == INICIO_LEGISLATURA else (_primeiro_ano(hoje), 1)
    while (a, m) >= inicio:
        out.append((a, m))
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
    return out


def _data(x) -> str:
    """{'@class': 'sql-timestamp', '$': '2026-03-23'} ou '2026-03-23' -> '2026-03-23'."""
    if isinstance(x, dict):
        x = x.get("$")
    return _data_iso(str(x or ""))


def notas_do_mes(dados: dict) -> list[dict]:
    """Notas de um mês, só com o que pode ser publicado: CNPJ sim, CPF nunca (vira 'pessoa física')."""
    out = []
    for tipo in (dados or {}).get("list") or []:
        desc = str(tipo.get("descTipoDespesa") or "Não informado").strip()
        det = tipo.get("listaDetalheVerba") or []
        if isinstance(det, dict):  # um item só pode vir fora da lista
            det = [det]
        if not det and fontes.valor(tipo.get("valor")):
            out.append({"tipo": desc, "valor": round(fontes.valor(tipo.get("valor")), 2), "data": _data(tipo.get("dataReferencia")),
                        "fornecedor": "Não detalhado", "cnpj": "", "pf": False})
        for d in det:
            v = fontes.valor(d.get("valorReembolsado"))
            if not v:
                continue
            doc = d.get("cpfCnpj")
            pf = fontes.tipo_doc(doc) == "cpf"
            nome = fontes.sem_cpf(fontes.bonito(str(d.get("nomeEmitente") or ""))) or ("Pessoa física" if pf else "Não informado")
            out.append({"tipo": desc, "valor": round(v, 2), "data": _data(d.get("dataEmissao")) or _data(tipo.get("dataReferencia")),
                        "fornecedor": nome, "cnpj": fontes.doc_publico(doc), "pf": pf})
    return out


def baixar_verbas(cache: Path, ids: list[str], hoje: dt.date, orcamento: int | None = None) -> dict[str, dict[tuple, list]]:
    """Notas de cada deputado e mês, do cache e da API (até `orcamento` consultas). Devolve {id: {(ano, mes): notas}}.

    Meses que nunca foram baixados ficam de fora (o site diz que o ano ainda está incompleto)."""
    orcamento = ORCAMENTO_VERBA if orcamento is None else orcamento
    meses = meses_legislatura(hoje)
    abertos = set(meses[:MESES_ABERTOS])
    out: dict[str, dict[tuple, list]] = {i: {} for i in ids}
    pendentes = []
    for (a, m) in meses:  # mais novos primeiro: o que importa mais aparece logo
        for i in ids:
            f = cache / "almg" / "verba" / i / f"{a}-{m:02d}.json"
            velho = not f.exists() or ((a, m) in abertos and (time.time() - f.stat().st_mtime) / 3600 > 72)
            if f.exists():
                try:
                    out[i][(a, m)] = json.loads(f.read_text(encoding="utf-8"))
                except ValueError:
                    velho = True
            if velho:
                pendentes.append((i, a, m, f))
    feitas, falhas_seguidas = 0, 0
    for i, a, m, f in pendentes:
        if feitas >= orcamento or falhas_seguidas >= 5:
            break
        feitas += 1
        try:
            r = get(API_VERBA.format(id=i, ano=a, mes=m), timeout=60, tries=3)
            notas = notas_do_mes(r.json())
            falhas_seguidas = 0
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):  # mês sem nenhuma nota
                notas, falhas_seguidas = [], 0
            else:
                falhas_seguidas += 1
                log.warning("ALMG verba %s %d/%d: %s", i, m, a, e)
                continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(notas, ensure_ascii=False), encoding="utf-8")
        out[i][(a, m)] = notas
        fontes.pausa(PAUSA_VERBA)
    if falhas_seguidas >= 5:
        fontes.avisar("ALMG (verba indenizatória): a consulta parou de responder; parte dos meses ficou para a próxima atualização")
    faltam = len(pendentes) - feitas
    if faltam > 0:
        log.info("ALMG verba: %d consultas feitas, %d meses ficam para as próximas execuções", feitas, faltam)
    return out


def verbas(por_mes: dict[str, dict[tuple, list]], anos: list[int], hoje: dt.date) -> dict[str, dict[int, dict]]:
    """Gastos da verba por deputado e ano: total, por tipo, por mês, fornecedores e maiores notas."""
    esperados: dict[int, set] = defaultdict(set)
    for (a, m) in meses_legislatura(hoje):
        esperados[a].add(m)
    out: dict[str, dict[int, dict]] = {}
    for dep, meses in por_mes.items():
        for ano in anos:
            ms = {m: n for (a, m), n in meses.items() if a == ano}
            if not ms:
                continue
            tipos, por_mes_v, forn, notas = Counter(), Counter(), {}, []
            for m, lista in ms.items():
                for n in lista:
                    tipos[n["tipo"]] += n["valor"]
                    por_mes_v[m] += n["valor"]
                    k = n["cnpj"] or ("pf:" if n["pf"] else "nome:") + fontes.chave_nome(n["fornecedor"])
                    f = forn.setdefault(k, {"nome": n["fornecedor"], "cnpj": n["cnpj"], "pf": n["pf"], "valor": 0.0, "n": 0})
                    f["valor"] += n["valor"]
                    f["n"] += 1
                    notas.append({**n, "mes": m})
            total = sum(tipos.values())
            out.setdefault(dep, {})[ano] = {
                "total": round(total, 2),
                "tipos": [{"tipo": t, "valor": round(x, 2)} for t, x in tipos.most_common()],
                "meses": [{"mes": m, "valor": round(por_mes_v[m], 2)} for m in sorted(ms)],
                "meses_faltando": sorted(esperados[ano] - set(ms)),
                "fornecedores": sorted(({**f, "valor": round(f["valor"], 2)} for f in forn.values()), key=lambda f: -f["valor"])[:40],
                "n_fornecedores": len(forn),
                "n_notas": len(notas),
                "notas": sorted(notas, key=lambda n: -n["valor"])[:40],
            }
    return out


# ---------------------------------------------------------------- proposições

def _autores(campo: str) -> list[str]:
    try:
        lst = json.loads(campo or "[]")
    except ValueError:
        return re.findall(r'"id"\s*:\s*(\d+)', campo or "")
    return [str(a.get("id")) for a in lst if isinstance(a, dict) and a.get("id") is not None]


def proposicoes(textos: dict[int, str], ids: set[str]) -> dict[str, dict[int, dict]]:
    """Por deputado e ano (da apresentação): projetos e requerimentos como primeiro autor, quantos foram aprovados,
    e a lista dos projetos (os mais recentes primeiro)."""
    out: dict = defaultdict(lambda: defaultdict(lambda: {"projetos": 0, "requerimentos": 0, "outras": 0, "coautor": 0,
                                                          "aprovadas": 0, "lista": []}))
    for ano, texto in textos.items():
        for r in fontes.ler_csv(texto, COL_PROPOSICOES):
            autores = _autores(r["Autores"])
            if not autores:
                continue
            sigla = r["SiglaTipoProposicao"].strip().upper()
            try:
                a = int(r["Ano"])
            except ValueError:
                a = ano
            for i, dep in enumerate(autores):
                if dep not in ids:
                    continue
                d = out[dep][a]
                if i > 0:
                    d["coautor"] += 1
                    continue
                aprovada = bool(APROVADA.search(r.get("Situacao") or ""))
                if sigla in PROJETOS:
                    d["projetos"] += 1
                    d["aprovadas"] += aprovada
                    d["lista"].append({"sigla": sigla, "numero": r["Numero"].strip(), "ano": a,
                                       "ementa": fontes.sem_cpf(r.get("Ementa") or "")[:240], "situacao": (r.get("Situacao") or "").strip(),
                                       "aprovada": aprovada, "data": _data_iso(r.get("DataPublicacao") or "")})
                elif sigla in REQUERIMENTOS:
                    d["requerimentos"] += 1
                else:
                    d["outras"] += 1
    for dep in out:
        for d in out[dep].values():
            d["lista"].sort(key=lambda p: (p["data"], int(p["numero"]) if p["numero"].isdigit() else 0), reverse=True)
            d["lista"] = d["lista"][:60]
    return out


FINAL = re.compile(r"TRANSFORMAD|SANCIONAD|PROMULGAD|NORMA JUR|ARQUIVAD|RETIRAD|REJEITAD|PREJUDICAD|VETAD|DEVOLVID|ANEXAD|LEI \d", re.I)
DIAS_ANDAMENTO = 30  # projetos com algum passo nos últimos N dias
DIAS_NOVAS = 14


def _etapa_almg(r: dict) -> int:
    """Mesmas etapas do Congresso, sem a "outra Casa" (a ALMG é uma Casa só): 0 apresentado, 1 comissões,
    2 Plenário, 4 sanção."""
    s = " ".join((r.get(k) or "") for k in ("Situacao", "NomeFaseAtual", "Local")).lower()
    if re.search(r"san[çc][ãa]o|governador", s):
        return 4
    # "1º turno" é a fase inteira (comissões e Plenário); o lugar (Local) diz onde o projeto está agora
    if re.search(r"comiss|parecer|relator", s):
        return 1
    if re.search(r"plen[áa]rio|ordem do dia", s):
        return 2
    return 0


def em_andamento(textos: dict[int, str], hoje: dt.date) -> dict:
    """Projetos da ALMG que ainda não viraram lei nem foram arquivados e que andaram nos últimos dias.

    Vem do mesmo arquivo de proposições usado na atuação dos deputados (opção 2 da regra do projeto): ele traz
    todos os projetos do ano, com situação e autores, de uma vez, enquanto a API de proposições da ALMG pede uma
    consulta por projeto. O arquivo não traz a pauta das reuniões, então aqui não há data de votação, só a
    situação oficial e o link da página do projeto. A pauta da ALMG ainda não foi ligada (a API de reuniões não
    pôde ser conferida no ambiente em que isto foi escrito).
    """
    limite = (hoje - dt.timedelta(days=DIAS_ANDAMENTO)).isoformat()
    novas = (hoje - dt.timedelta(days=DIAS_NOVAS)).isoformat()
    itens = []
    for ano, texto in textos.items():
        for r in fontes.ler_csv(texto, COL_PROPOSICOES):
            sigla = r["SiglaTipoProposicao"].strip().upper()
            num = r["Numero"].strip()
            if sigla not in PROJETOS or not num.isdigit() or FINAL.search(r.get("Situacao") or ""):
                continue
            apres = _data_iso(r.get("DataPublicacao") or "")
            ultima = _data_iso(r.get("DataUltimaAcao") or r.get("DataAtualizacao") or "") or apres
            if max(apres, ultima) < limite:
                continue
            try:
                autores = [{"nome": str(a.get("nome") or "").strip(), "partido": str(a.get("partido") or "").strip(),
                            "id": str(a.get("id") or "")} for a in json.loads(r.get("Autores") or "[]") if isinstance(a, dict)]
            except ValueError:
                autores = []
            a = r["Ano"].strip() or str(ano)
            p = {"sigla": sigla, "numero": num, "ano": a}
            itens.append({
                "id": f"mg-{sigla}-{num}-{a}", "casa": "almg", "sigla": sigla, "numero": num, "ano": a,
                "nome": f"{sigla} {num}/{a}", "ementa": fontes.sem_cpf(r.get("Ementa") or "").strip()[:600],
                "resumo_oficial": fontes.sem_cpf(r.get("Resumo") or "").strip()[:600],
                "situacao": (r.get("Situacao") or "").strip(), "fase": (r.get("NomeFaseAtual") or "").strip(),
                "onde": (r.get("Local") or "").strip(), "regime": (r.get("Regime") or "").strip(),
                "apresentada": apres, "atualizada": ultima, "etapa": _etapa_almg(r),
                "autores": [x for x in autores if x["nome"]][:6], "n_autores": len(autores),
                "grupos": ["nova"] if apres >= novas else ["andamento"], "url": link_proposicao(p),
            })
    itens.sort(key=lambda i: (i["atualizada"], i["apresentada"]), reverse=True)
    return {"atualizado_em": hoje.isoformat(), "dias_andamento": DIAS_ANDAMENTO, "dias_novas": DIAS_NOVAS,
            "itens": itens[:400], "fonte": BASE}


def link_proposicao(p: dict) -> str:
    return PAGINA_PROPOSICAO.format(sigla=p["sigla"], numero=p["numero"], ano=p["ano"])


# ---------------------------------------------------------------- montagem

def coletar(saida: Path, cache: Path, deps: list[dict], emendas: dict | None, hoje: dt.date | None = None,
            orcamento: int | None = None) -> list[dict]:
    """Escreve almg/deputados.json e almg/d/{id}.json. Devolve a lista de deputados (deps: de em_exercicio)."""
    anos = anos_legislatura(hoje)
    deps = [d for d in deps if id_seguro(d["id"])]
    ids = {d["id"] for d in deps}
    links = paginas(cache)
    hoje = hoje or dt.date.today()
    por_mes = baixar_verbas(cache, sorted(ids), hoje, orcamento)
    gastos = verbas(por_mes, anos, hoje)
    esperados: dict[int, set] = defaultdict(set)
    for (a, m) in meses_legislatura(hoje):
        esperados[a].add(m)
    # Ano completo: todos os meses de todos os deputados já consultados na ALMG
    completo = {str(a): bool(por_mes) and all({m for (x, m) in meses if x == a} >= esperados[a] for meses in por_mes.values())
                for a in anos}
    textos = {}
    for ano in anos:
        t = fontes.baixar(CSV_PROPOSICOES.format(ano=ano), cache / "almg" / f"proposicoes_{ano}.csv",
                          20 if ano >= anos[-1] - 1 else 24 * 30, f"ALMG (proposições de {ano})", colunas=("Autores",))
        if t:
            textos[ano] = t
    props = proposicoes(textos, ids)
    write_json(saida / "almg" / "tramitacao.json", em_andamento(textos, hoje))
    em = (emendas or {}).get("por_deputado", {})
    resumo = []
    for d in sorted(deps, key=lambda x: fontes.chave_nome(x["nome"])):
        i = d["id"]
        por_ano = {}
        anos_dep = {}
        for ano in anos:
            g = gastos.get(i, {}).get(ano)
            p = props.get(i, {}).get(ano)
            e = em.get(i, {}).get(ano)
            if not (g or p or e):
                continue
            for x in (p or {}).get("lista", []):
                x["url"] = link_proposicao(x)
            anos_dep[str(ano)] = {"verba": g, "proposicoes": p, "emendas": e}
            por_ano[str(ano)] = {
                "verba": g["total"] if g else 0,
                "projetos": p["projetos"] if p else 0, "requerimentos": p["requerimentos"] if p else 0,
                "aprovadas": p["aprovadas"] if p else 0,
                "emendas_indicado": e["indicado"] if e else 0, "emendas_pago": e["pago"] if e else 0,
            }
        r = {"id": i, "nome": d["nome"], "partido": d["partido"],
             "url": links.get(i) or PAGINA_DEPUTADO.format(id=i), "url_verba": PAGINA_VERBA_DEPUTADO.format(id=i),
             "por_ano": por_ano}
        resumo.append(r)
        write_json(saida / "almg" / "d" / f"{i}.json", {**r, "anos": anos_dep})
    medianas = {}
    for ano in anos:
        a = str(ano)
        # Todos os deputados em exercício entram: quem não teve nenhum gasto ou projeto no ano conta como zero
        if any(a in r["por_ano"] for r in resumo):
            com = [r["por_ano"].get(a) or dict.fromkeys(CAMPOS, 0) for r in resumo]
            medianas[a] = {k: _mediana([x[k] for x in com]) for k in CAMPOS}
    write_json(saida / "almg" / "deputados.json", {
        "anos": [str(a) for a in anos], "medianas": medianas, "deputados": resumo,
        "fontes": {"verba": PAGINA_VERBA, "dados": BASE},
        "verba_completa": completo,
    })
    log.info("ALMG: %d deputados, verba de %d, proposições de %d", len(resumo), len(gastos), len(props))
    return resumo


CAMPOS = ("verba", "projetos", "requerimentos", "aprovadas", "emendas_indicado", "emendas_pago")


def _mediana(v: list[float]) -> float:
    s = sorted(v)
    n = len(s)
    if not n:
        return 0
    return s[n // 2] if n % 2 else round((s[n // 2 - 1] + s[n // 2]) / 2, 2)
