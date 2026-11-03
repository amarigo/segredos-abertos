"""Como cada ministro do STF votou: julgamentos do Plenário em sessão virtual.

Fonte: o próprio portal do STF. O STF não tem API pública documentada nem arquivo de dados abertos com o voto de cada
ministro (o "Corte Aberta" traz só painéis e totais). Por isso usamos os serviços em JSON que as páginas oficiais do
portal chamam para mostrar a pauta e o placar de cada processo (opção 2/3 da regra "API primeiro"):

1. Calendário: portal.stf.jus.br/pauta/services/calendario-service.asp?dados=calendarios&mes=MM&ano=AAAA
   devolve as sessões virtuais do mês (`julgamentosVirtuais`: `dataInicial`, `dataFinal`).
2. Sessão: ...calendario-service.asp?dados=sessao-virtual&inicio=...&fim=... devolve, por colegiado (Plenário,
   1ª e 2ª Turma), as listas de julgamento de cada ministro relator (`colegiados[].sessoes[].listas[].ministros[]
   .listaJulgamento[].id`).
3. Lista: portal.stf.jus.br/pauta/services/lista-service.asp?lista={id} devolve os processos da lista (`id` do
   incidente, `classe`, `numero`, `cadeia` quando é um recurso dentro do processo, `procedencia`, `partes`).
4. Votos: sistemas.stf.jus.br/repgeral/votacao?sessaoVirtual={incidente} devolve, para cada sessão em que o
   processo foi julgado, o relator, o resultado, o texto da decisão e o voto de cada ministro (`votos[]`: `ministro`,
   `tipoVoto`, `acompanhandoMinistro`, `textos[].link` com a íntegra). Quando há `cadeia`, o incidente certo vem
   de .../repgeral/votacao?oi={incidente}.

O que entra: só o Plenário (os 11 ministros), e nele as ações que questionam leis e atos do poder público (ADI, ADC,
ADO e ADPF, com os recursos dentro delas), tudo o que o STF põe na lista de "controle concentrado" (inclui ações entre
a União e os estados, ACO) e os recursos extraordinários julgados no mérito (repercussão geral: a decisão vale para
todos os casos iguais). Turmas, habeas corpus e recursos de casos individuais ficam de fora: são milhares por semana
e decidem a situação de uma pessoa.

Conferido em 03/11/2026 contra o portal (sessão de 16 a 23/10/2026): 39 listas no Plenário, das quais entram 12
processos (ADI, ADPF, ACO e RE no mérito). Os nomes dos campos e os textos dos votos ("Acompanho o relator",
"Acompanho o relator com ressalvas", "Acompanho a ressalva", "Divirjo do relator", "Acompanho a divergência",
"Suspeito") são os que o serviço devolve. O voto do relator não vem em `votos`: vem em `votoRelator`.

Sessões que já terminaram não mudam: ficam guardadas no cache e não são lidas de novo. A sessão em andamento é lida
em toda coleta, porque os votos entram ao longo da semana.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

from .util import avisar, get_json, id_seguro, url_segura, write_json

log = logging.getLogger("sa_etl.tribunais")

PORTAL = "https://portal.stf.jus.br"
SISTEMAS = "https://sistemas.stf.jus.br"
CALENDARIO = PORTAL + "/pauta/services/calendario-service.asp"
LISTA = PORTAL + "/pauta/services/lista-service.asp"
VOTACAO = SISTEMAS + "/repgeral/votacao"
PROCESSO = PORTAL + "/processos/detalhe.asp?incidente={id}"
PAGINA_SESSOES = "https://portal.stf.jus.br/hotsites/plenariovirtual/"

CLASSES_LEI = {"ADI", "ADC", "ADO", "ADPF"}
LISTA_CONTROLE_CONCENTRADO = "3"  # "Listas dos Relatores em Ações de Controle Concentrado (Mérito)"
CLASSES = {
    "ADI": "Ação Direta de Inconstitucionalidade: pede que o STF derrube uma lei ou ato por ir contra a Constituição.",
    "ADC": "Ação Declaratória de Constitucionalidade: pede que o STF confirme que uma lei federal vale.",
    "ADO": "Ação Direta de Inconstitucionalidade por Omissão: diz que o poder público deixou de fazer uma lei que a "
           "Constituição manda fazer.",
    "ADPF": "Arguição de Descumprimento de Preceito Fundamental: questiona leis antigas, municipais ou atos do governo "
            "que ferem um direito básico da Constituição.",
    "ACO": "Ação Cível Originária: briga entre a União e um estado, ou entre estados, julgada direto pelo STF.",
    "RE": "Recurso Extraordinário julgado no mérito pelo Plenário: com repercussão geral, a decisão vale para todos os "
          "processos iguais do país.",
}
# A lista de processos traz o estado por extenso; o site mostra a sigla
UFS = {"ACRE": "AC", "ALAGOAS": "AL", "AMAPÁ": "AP", "AMAZONAS": "AM", "BAHIA": "BA", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
       "ESPÍRITO SANTO": "ES", "GOIÁS": "GO", "MARANHÃO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
       "MINAS GERAIS": "MG", "PARÁ": "PA", "PARAÍBA": "PB", "PARANÁ": "PR", "PERNAMBUCO": "PE", "PIAUÍ": "PI",
       "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDÔNIA": "RO", "RORAIMA": "RR",
       "SANTA CATARINA": "SC", "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO"}
# Partes que aparecem: quem pediu e contra quem. Advogados e procuradores ficam de fora.
PARTES = re.compile(r"^(REQTE|REQDO|INTDO|AUTOR|R[ÉE]U)", re.I)
PLENARIO = {"TP", "P", "PLENO", "PLENÁRIO", "PLENARIO", "TRIBUNAL PLENO"}
MESES = 6        # quantos meses para trás mostrar
DIAS_RELER = 20  # a sessão encerrada ainda é lida por N dias: o STF publica o resultado e o texto da decisão depois
PAUSA = 0.4      # segundos entre pedidos ao STF, para não pesar no portal
TENTATIVAS = 2

# O lado de cada voto em relação ao relator
LADOS = ("relator", "divergencia", "vista", "fora", "outro")


# ---------------------------------------------------------------- leitura de cada parte

def _get(url: str, params: dict | None = None) -> Any:
    time.sleep(PAUSA)
    return get_json(url, params=params, tries=TENTATIVAS, timeout=60)


def _data(s: Any) -> str:
    """'10/10/2026', '10/10/2026 00:00:00' ou '2026-10-10T00:00:00' -> '2026-10-10'. Vazio se não entender."""
    s = str(s or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}"
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m[3]}-{m[2]}-{m[1]}"
    return ""


def _desc(x: Any) -> str:
    """Muitos campos vêm como {"descricao": ...} ou como "" quando vazios."""
    if isinstance(x, dict):
        return str(x.get("descricao") or x.get("nome") or "").strip()
    return str(x or "").strip()


_PARTICULAS = {"de", "da", "do", "das", "dos", "e"}


def nome_ministro(s: Any) -> str:
    """'MIN. ALEXANDRE DE MORAES' -> 'Alexandre de Moraes'. O nome é o oficial, só sem o 'MIN.' e sem caixa alta."""
    s = re.sub(r"^\s*(MIN(?:ISTRO|ISTRA)?\.?|MINISTRA?)\s+", "", _desc(s), flags=re.I).strip()
    if not s:
        return ""
    if s.isupper():
        s = " ".join(p.lower() if p.lower() in _PARTICULAS and i else p.capitalize() for i, p in enumerate(s.split()))
    return s


def sessoes_do_mes(ano: int, mes: int) -> list[tuple[str, str]]:
    """Sessões virtuais do mês, como o calendário oficial escreve as datas (para montar o próximo endereço)."""
    d = _get(CALENDARIO, {"dados": "calendarios", "mes": f"{mes:02d}", "ano": str(ano)})
    out = []
    for s in (d or {}).get("julgamentosVirtuais") or []:
        ini, fim = str(s.get("dataInicial") or "").strip(), str(s.get("dataFinal") or "").strip()
        if _data(ini) and _data(fim) and (ini, fim) not in out:
            out.append((ini, fim))
    return out


def listas_do_plenario(ini: str, fim: str) -> list[tuple[int, str]]:
    """Ids das listas de julgamento do Plenário nessa sessão virtual, com o tipo da lista."""
    d = _get(CALENDARIO, {"dados": "sessao-virtual", "inicio": ini, "fim": fim})
    ids: list[tuple[int, str]] = []
    for cj in (d or {}).get("colegiados") or []:
        cod, nome = str(cj.get("codigo") or "").upper(), str(cj.get("descricao") or "").upper()
        if cod not in PLENARIO and "PLEN" not in nome:
            continue
        for s in cj.get("sessoes") or []:
            for lista in s.get("listas") or []:
                tipo = str(lista.get("idTipo") or "")
                for m in lista.get("ministros") or []:
                    for lj in m.get("listaJulgamento") or []:
                        i = str(lj.get("id") or "")
                        if i.isdigit() and int(i) not in [x for x, _ in ids]:
                            ids.append((int(i), tipo))
    return ids


def entra(classe: str, cadeia: str, tipo_lista: str) -> bool:
    """O processo entra na página? Ações contra leis (e recursos nelas), a lista de controle concentrado e RE no mérito."""
    return classe in CLASSES_LEI or tipo_lista == LISTA_CONTROLE_CONCENTRADO or (classe == "RE" and not cadeia)


def processos_da_lista(lista_id: int, tipo_lista: str = "") -> list[dict]:
    """Processos da lista que entram na página (veja entra())."""
    out = []
    for p in _get(LISTA, {"lista": str(lista_id)}) or []:
        classe = str(p.get("classe") or "").strip().upper()
        cadeia = str(p.get("cadeia") or "").strip()
        if not entra(classe, cadeia, tipo_lista) or not id_seguro(p.get("id")):
            continue
        # Em RE as partes podem ser pessoas comuns: não aparecem
        partes = [] if classe == "RE" else [
            {"nome": _desc(x.get("nome")), "tipo": _desc(x.get("categoria"))}
            for x in p.get("partes") or [] if isinstance(x, dict) and x.get("nome") and PARTES.match(_desc(x.get("categoria")))]
        proc = str(p.get("procedencia") or "").strip().upper()
        out.append({"incidente": str(p["id"]), "classe": classe, "numero": str(p.get("numero") or "").strip(),
                    "cadeia": cadeia, "uf": UFS.get(proc, proc if len(proc) == 2 else ""), "partes": partes[:6]})
    return out


def incidente_da_cadeia(p: dict) -> str:
    """Recurso dentro do processo: a lista traz a cadeia por extenso ('EMB.DECL. NO AG.REG. NA AÇÃO DIRETA DE
    INCONSTITUCIONALIDADE') e o voto fica num incidente próprio, achado em ?oi= pela identificação completa
    ('EMB.DECL. NO AG.REG. NA AÇÃO DIRETA DE INCONSTITUCIONALIDADE 7990')."""
    if not p["cadeia"]:
        return p["incidente"]
    alvo = f"{p['cadeia']} {p['numero']}".upper()
    for item in _get(VOTACAO, {"oi": p["incidente"]}) or []:
        oi = item.get("objetoIncidente") or {}
        if str(oi.get("identificacaoCompleta") or "").strip().upper() == alvo and id_seguro(oi.get("id")):
            return str(oi["id"])
    raise LookupError(f"incidente de '{alvo}' não achado")


# ---------------------------------------------------------------- votos

def lado_do_voto(tipo: str, acompanha: str, relator: str, lados: dict[str, str]) -> str:
    """Em que lado o voto ficou: com o relator, com a divergência, pedido de vista, fora (impedido/suspeito)."""
    t = tipo.lower()
    if re.search(r"impedi|suspei|não particip|nao particip|ausen", t):
        return "fora"
    if "vista" in t:
        return "vista"
    if acompanha:
        if acompanha == relator:
            return "relator"
        if acompanha in lados:
            return lados[acompanha]
        return "divergencia"
    if re.search(r"diverg|divirjo", t):
        return "divergencia"
    if "relator" in t:  # "Acompanho o Relator", "Acompanho o(a) Relator(a) com ressalvas"
        return "relator"
    return "outro"


def _link(x: Any) -> str:
    return url_segura(x.get("link")) if isinstance(x, dict) else ""


def julgamento(p: dict, inc: str, item: dict, lj: dict) -> dict | None:
    """Um julgamento (o processo numa sessão) no formato do site."""
    relator = nome_ministro(lj.get("ministroRelator"))
    sessao = lj.get("sessao") or {}
    colegiado = _desc(sessao.get("colegiado"))
    if colegiado and "PLEN" not in colegiado.upper() and colegiado.upper() not in PLENARIO:
        return None
    lados: dict[str, str] = {}
    votos = []
    if relator:
        lados[relator] = "relator"
        votos.append({"ministro": relator, "voto": "Relator", "lado": "relator", "acompanha": "",
                      "link": _link(lj.get("votoRelator"))})
    for v in lj.get("votos") or []:
        nome = nome_ministro(v.get("ministro"))
        if not nome or nome in lados:
            continue
        tipo = _desc(v.get("tipoVoto"))
        acompanha = nome_ministro(v.get("acompanhandoMinistro"))
        lado = lado_do_voto(tipo, acompanha, relator, lados)
        lados[nome] = lado
        textos = [_link(t) for t in v.get("textos") or []]
        votos.append({"ministro": nome, "voto": tipo or "Voto registrado", "lado": lado, "acompanha": acompanha,
                      "link": next((t for t in textos if t), "")})
    placar = {k: sum(1 for v in votos if v["lado"] == k) for k in LADOS}
    julgado = bool(lj.get("julgado")) and lj.get("julgado") not in ("N", "n", "false", "0")
    resultado = _desc(lj.get("tipoResultadoJulgamento"))
    oi = item.get("objetoIncidente") or {}
    nome_proc = str(oi.get("identificacao") or f"{p['classe']} {p['numero']}").strip()  # "ADI 7990 AgR-ED"
    return {
        "id": f"stf-{inc}-{id_seguro(lj.get('id')) or id_seguro(sessao.get('numero')) or 'x'}",
        "tribunal": "stf", "colegiado": "Plenário", "tipo_sessao": "virtual",
        "processo": nome_proc, "classe": p["classe"], "numero": p["numero"], "uf": p["uf"], "partes": p["partes"],
        "relator": relator,
        "inicio": _data(sessao.get("dataPrevistaInicio") or sessao.get("dataInicio")),
        "fim": _data(sessao.get("dataPrevistaFim") or sessao.get("dataFim") or sessao.get("dataFinal")),
        "julgado": julgado, "resultado": resultado,
        "decisao": re.sub(r"\s+", " ", str(lj.get("textoDecisao") or "")).strip()[:1500],
        "vista": nome_ministro(lj.get("ministroVista") or lj.get("ministroVistor")),
        "destaque": nome_ministro(lj.get("ministroDestaque")),
        "votos": votos, "placar": placar, "maioria": "", "situacao": "",
        "link": PROCESSO.format(id=p["incidente"]),
        "fonte": f"{VOTACAO}?sessaoVirtual={inc}",
    }


MAIORIA = 6  # metade mais um dos 11 ministros


def situacao(j: dict, hoje: dt.date) -> dict:
    """Situação do julgamento e lado vencedor, pelas regras do Plenário Virtual.

    O STF leva dias para marcar o processo como julgado e publicar o texto da decisão depois que a sessão termina
    (conferido em 03/11/2026: a sessão de 16 a 23/10 ainda tinha `julgado = false` e decisão vazia). Por isso o lado
    vencedor sai do placar oficial: terminada a sessão sem pedido de vista nem destaque, vence o lado com 6 votos ou mais
    (maioria absoluta dos 11). Sem isso, fica "sem maioria" e o site não aponta vencedor."""
    j = dict(j)
    p = j["placar"]
    if j.get("vista"):
        j["situacao"], j["maioria"] = "vista", ""
    elif j.get("destaque"):
        j["situacao"], j["maioria"] = "destaque", ""
    elif j["fim"] and j["fim"] >= hoje.isoformat() and not j.get("julgado"):
        j["situacao"], j["maioria"] = "em_julgamento", ""
    elif p["relator"] >= MAIORIA or p["divergencia"] >= MAIORIA:
        j["situacao"], j["maioria"] = "decidido", "relator" if p["relator"] >= MAIORIA else "divergencia"
    else:
        j["situacao"], j["maioria"] = "sem_maioria", ""
    return j


def votos_do_processo(p: dict, ini: str, fim: str) -> list[dict]:
    """Os julgamentos do processo na sessão [ini, fim] (normalmente um só)."""
    inc = incidente_da_cadeia(p)
    a, b = _data(ini), _data(fim)
    out = []
    for item in _get(VOTACAO, {"sessaoVirtual": inc}) or []:
        for lj in item.get("listasJulgamento") or []:
            j = julgamento(p, inc, item, lj)
            if not j:
                continue
            # O serviço devolve todas as sessões em que o processo já esteve; fica só a desta
            if j["inicio"] and not (a <= j["inicio"] <= b):
                continue
            j["inicio"] = j["inicio"] or a
            j["fim"] = j["fim"] or b
            out.append(j)
    return out


def ler_sessao(ini: str, fim: str, limite: float) -> tuple[list[dict], bool, int]:
    """Os julgamentos da página nessa sessão do Plenário. Devolve (julgamentos, completa, processos com erro)."""
    falhas = 0
    vistos: set[str] = set()
    out: list[dict] = []
    for lid, tipo in listas_do_plenario(ini, fim):
        if time.monotonic() > limite:
            return out, False, falhas
        for p in processos_da_lista(lid, tipo):
            chave = f"{p['incidente']} {p['cadeia']}"
            if chave in vistos:
                continue
            vistos.add(chave)
            if time.monotonic() > limite:
                return out, False, falhas
            try:
                out += votos_do_processo(p, ini, fim)
            except requests.HTTPError as e:
                # 404: o STF não tem placar virtual desse processo (conferido em 03/11/2026: acontece com processos
                # antigos e alguns recursos). Não muda tentando de novo, então não conta como falha.
                if e.response is not None and e.response.status_code == 404:
                    log.info("STF: %s sem placar no serviço de votação (404)", chave)
                    continue
                log.warning("STF: votos de %s não lidos (%s)", chave, e)
                falhas += 1
            except Exception as e:  # noqa: BLE001  um processo com erro não derruba a sessão inteira
                log.warning("STF: votos de %s não lidos (%s)", chave, e)
                falhas += 1
    return out, True, falhas


# ---------------------------------------------------------------- resumo por ministro

def resumo_ministros(julgamentos: list[dict]) -> list[dict]:
    """Para cada ministro: quantos votos, quantas vezes ficou com a maioria, quantas ficou vencido, quantas relatou."""
    m: dict[str, dict] = {}
    for j in julgamentos:
        for v in j["votos"]:
            x = m.setdefault(v["ministro"], {"nome": v["ministro"], "tribunal": j["tribunal"], "votos": 0, "relator": 0,
                                             "com_maioria": 0, "vencido": 0, "divergencias": 0, "fora": 0})
            if v["lado"] == "fora":
                x["fora"] += 1
                continue
            x["votos"] += 1
            x["relator"] += v["voto"] == "Relator"
            x["divergencias"] += v["lado"] == "divergencia"
            if j["maioria"] and v["lado"] in ("relator", "divergencia"):
                x["com_maioria" if v["lado"] == j["maioria"] else "vencido"] += 1
    return sorted(m.values(), key=lambda x: (-x["votos"], x["nome"]))


# ---------------------------------------------------------------- coleta

def _meses(hoje: dt.date, n: int) -> list[tuple[int, int]]:
    a, m = hoje.year, hoje.month
    out = []
    for _ in range(n):
        out.append((a, m))
        a, m = (a - 1, 12) if m == 1 else (a, m - 1)
    return out


def coletar_stf(cache: Path, hoje: dt.date, minutos: float) -> tuple[list[dict], str]:
    """Julgamentos do STF dos últimos MESES meses. Devolve (julgamentos, situação: ok, parcial, reserva ou faltando)."""
    pasta = cache / "stf"
    pasta.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + minutos * 60
    corte = (hoje - dt.timedelta(days=31 * MESES)).isoformat()
    situacao = "ok"
    try:
        sessoes = []
        for a, m in _meses(hoje, MESES):
            for s in sessoes_do_mes(a, m):
                if s not in sessoes:
                    sessoes.append(s)
    except Exception as e:  # noqa: BLE001
        log.warning("STF: calendário das sessões não respondeu (%s)", e)
        sessoes, situacao = [], "reserva"
    for ini, fim in sorted(sessoes, key=lambda s: _data(s[0]), reverse=True):
        nome = f"{_data(ini)}-{_data(fim)}.json"
        arq = pasta / f"sessao-{nome}"
        terminou = _data(fim) < (hoje - dt.timedelta(days=DIAS_RELER)).isoformat()
        if terminou and arq.exists():
            continue  # sessão encerrada há tempo e já guardada: não muda mais
        if _data(ini) > hoje.isoformat():
            continue  # ainda não começou: não há votos
        if time.monotonic() > limite:
            situacao = "parcial"
            break
        try:
            js, completa, falhas = ler_sessao(ini, fim, limite)
        except Exception as e:  # noqa: BLE001
            log.warning("STF: sessão %s a %s não lida (%s)", ini, fim, e)
            situacao = "parcial" if situacao == "ok" else situacao
            continue
        if not completa:
            situacao = "parcial"
            break
        # Encerrada: guardada de vez. Em andamento, ou com algum processo que não respondeu: guardada à parte (serve
        # de reserva) e lida de novo na próxima coleta.
        de_vez = terminou and not falhas
        write_json(arq if de_vez else pasta / f"andamento-{nome}", js)
        if de_vez:
            (pasta / f"andamento-{nome}").unlink(missing_ok=True)
    julgamentos: list[dict] = []
    vistos: set[str] = set()
    guardados = sorted(pasta.glob("sessao-*.json")) + sorted(pasta.glob("andamento-*.json"))
    encerradas = {a.name.split("-", 1)[1] for a in guardados if a.name.startswith("sessao-")}
    for arq in guardados:
        if arq.stem[-10:] < corte or (arq.name.startswith("andamento-") and arq.name.split("-", 1)[1] in encerradas):
            continue
        try:
            itens = json.loads(arq.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for j in itens:
            if j.get("id") and j["id"] not in vistos:
                vistos.add(j["id"])
                julgamentos.append(j)
    if not julgamentos and situacao != "ok":
        situacao = "faltando"
    return julgamentos, situacao


def coletar(saida: Path, cache: Path, hoje: dt.date | None = None, minutos: float = 15) -> dict:
    hoje = hoje or dt.date.today()
    js, sit = coletar_stf(cache / "tribunais", hoje, minutos)
    if sit == "reserva":
        avisar("Julgamentos do STF: o portal do STF não respondeu; mostramos os julgamentos já lidos antes")
    elif sit == "parcial":
        avisar("Julgamentos do STF: parte das sessões ainda não foi lida; a próxima coleta continua")
    elif sit == "faltando":
        avisar("Julgamentos do STF: o portal do STF não respondeu e não há cópia anterior")
    js = [situacao(j, hoje) for j in js]
    js.sort(key=lambda j: (j["fim"] or j["inicio"], j["processo"]), reverse=True)
    out = {
        "atualizado_em": hoje.isoformat(), "meses": MESES,
        "situacao_fontes": {"stf": sit},
        "fontes": {"stf": {"nome": "Supremo Tribunal Federal, Plenário Virtual", "pagina": PAGINA_SESSOES,
                           "servicos": [CALENDARIO, LISTA, VOTACAO]}},
        "classes": CLASSES,
        "ministros": resumo_ministros(js),
        "julgamentos": js,
    }
    write_json(saida / "tribunais.json", out)
    log.info("Tribunais: %d julgamentos do STF (%s)", len(js), sit)
    return out
