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

5. O que está em julgamento: o relatório do ministro relator (`relatorioRelator.link`, PDF em digital.stf.jus.br),
   o mesmo documento que o portal mostra na aba "Sessão virtual". Nenhum serviço do STF dá o assunto do processo em
   texto: o "Assunto" do portal é só uma classificação ("Servidor Público Civil") e a lista de processos não traz
   ementa. Do relatório copiamos, sem mudar palavras, a primeira frase depois do título, que diz quem pediu, contra
   qual lei ou ato e por quê ("Trata-se de ação direta de inconstitucionalidade... contra a Lei n. ..."). Ao lado vai
   a mesma frase com o juridiquês trocado por palavras do dia a dia (`em_palavras_simples`), marcada como explicação.
   Só nas ações contra leis e atos (ADI, ADC, ADO, ADPF) e nas ACO: em RE e em ação rescisória o relatório pode trazer
   o nome de pessoas comuns, que o site não mostra. Conferido em 17/11/2026 com 14 relatórios reais.

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
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

from . import debate
from .util import avisar, get, get_json, id_seguro, url_segura, write_json

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

# Relatório do relator: em que classes a frase entra (nas outras pode haver nome de pessoa comum) e quanto dela
CLASSES_RELATORIO = CLASSES_LEI | {"ACO"}
MAX_OBJETO = 520
MINUTOS_RELATORIOS = 4
VERSAO_RELATORIO = 1  # mude quando a forma de recortar a frase mudar (aí os relatórios são lidos de novo)

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
        "relatorio": _link(lj.get("relatorioRelator")),
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



# ---------------------------------------------------------------- o que está em julgamento (relatório do relator)

_TITULO_RELATORIO = re.compile(r"R\s?E\s?L\s?A\s?T\s?[ÓO]\s?R\s?I\s?O")  # às vezes "R E L A T Ó R I O"
# "O SENHOR MINISTRO GILMAR MENDES (RELATOR):", "A SENHORA MINISTRA CÁRMEN LÚCIA (Relatora):", às vezes sem espaços
_QUEM_RELATA = re.compile(r"\b[OA]\s*S\s*E\s*N\s*H\s*O\s*R\s*A?\s*M\s*I\s*N\s*I\s*S\s*T\s*R\s*[OA][^:]{0,90}:\s*", re.I)
_NUMERO_ITEM = re.compile(r"^\s*1\s*[.)-]\s*")
_PROXIMO_ITEM = re.compile(r"(?<=[.;:])\s+\d{1,2}(?:\.\d{1,2})*\.\s+(?=[A-ZÁÉÍÓÚÂÊÔ“\"])")
# Onde a frase passa a copiar outro texto (a ementa do acórdão, a lei inteira): corta ali
_CORTE = re.compile(r",?\s*(?:assim ementado|com o seguinte teor|nos seguintes termos|in verbis)\b|\bEmenta\s*:", re.I)
_COLADO = re.compile(r"[A-Za-zÀ-ú]{28,}")  # palavras grudadas: o PDF não guardou os espaços


def objeto_do_relatorio(texto: str) -> str:
    """A primeira frase do relatório, copiada sem mudar palavras: diz o que a ação pede. "" se não der para achar."""
    t = re.sub(r"\s+", " ", (texto or "").replace("\ufffe", "-").replace("\ufffd", "")).strip()
    m = _TITULO_RELATORIO.search(t)
    if not m:
        return ""
    t = t[m.end():].lstrip(" :.-–")
    q = _QUEM_RELATA.search(t[:250])  # às vezes há antes "CONJUNTO ADC 87, ADI 7.582..."
    if q:
        t = t[q.end():]
    t = _NUMERO_ITEM.sub("", t, count=1)
    t = _PROXIMO_ITEM.split(t[:4000], maxsplit=1)[0]  # "... estaduais. 2. O requerente": o item 2 já é outra coisa
    fs = debate.frases(t)
    if not fs:
        return ""
    f = fs[0]
    if len(f) < 140 and len(fs) > 1 and not _CORTE.search(f):
        f = f"{f} {fs[1]}"
    c = _CORTE.search(f)
    cortada = False
    if c and c.start() >= 60:
        f, cortada = f[:c.start()].rstrip(" ,;:"), True
    if len(f) > MAX_OBJETO:
        f, cortada = f[:MAX_OBJETO].rsplit(" ", 1)[0].rstrip(" ,;:"), True
    if len(f) < 60 or _COLADO.search(f) or not re.search(r"[a-zà-ú]{3}", f):
        return ""
    if not re.search(r"[.!?”\")]$", f):
        cortada = True  # a frase continua além do que foi lido
    return f + " […]" if cortada else f


# Explicação: o juridiquês trocado por palavras do dia a dia. A frase oficial aparece sempre ao lado, com o link.
# Tipos de ação e de recurso: o nome oficial fica, e a primeira vez que aparece ganha a explicação entre parênteses.
_TIPOS = [
    (r"aç(?:ão|ões) diretas? de inconstitucionalidade por omissão", "ADO: diz que faltou fazer uma lei que a Constituição exige"),
    (r"aç(?:ão|ões) diretas? de inconstitucionalidade", "ADI: pede que o STF derrube uma lei ou ato por ir contra a Constituição"),
    (r"arguição de descumprimento de preceito fundamental", "ADPF: diz que uma lei ou ato fere um direito básico da Constituição"),
    (r"ação declaratória de constitucionalidade", "ADC: pede que o STF confirme que uma lei vale"),
    (r"ação cível originária", "ACO: briga entre a União e um estado, ou entre estados"),
    (r"embargos de declaração", "pedido para esclarecer ou corrigir uma decisão já tomada"),
    (r"agravo (?:regimental|interno)", "recurso aos 11 ministros contra a decisão de um ministro sozinho"),
    (r"referendo d[ae] medida cautelar", "os 11 ministros confirmam ou não uma decisão urgente de um ministro"),
]
_TIPO_QUALQUER = re.compile("|".join(rf"\b({p})\b" for p, _ in _TIPOS), re.I)
_SIMPLES = [
    (r"^\s*(?:Trata-se|Cuida-se)\s+d[eo]s?\s+", ""),
    (r",?\s*com (?:pedidos?|requerimentos?) de medida cautelar\b", ", com pedido de decisão urgente"),
    (r"\bmedida cautelar\b", "decisão urgente (liminar)"),
    (r"\binterpôs\b", "apresentou"), (r"\bajuizou\b", "apresentou"), (r"\bpropôs\b", "apresentou"),
    (r"\b(?:ajuizad|propost|movid|interpost|apresentad|opost)([ao]s?)\b", r"apresentad\1"),
    (r"\bem (?:face|desfavor) de\b", "contra"), (r"\bem (?:face|desfavor) d([ao]s?)\b", r"contra \1"),
    (r"\btendo (?:por|como) objeto\b", "contra"),
    (r"\bdecisão monocrática\b", "decisão de um ministro sozinho"),
    (r"\bacórdão\b", "decisão"),
    (r"\bdispositivos\b", "trechos"), (r"\bdispositivo\b", "trecho"),
    (r"\bnormas impugnadas\b", "normas questionadas"), (r"\bimpugnad([ao]s?)\b", r"questionad\1"), (r"\bimpugna\b", "questiona"),
    (r"\bjulgou procedente\b", "aceitou"), (r"\bjulgou improcedente\b", "rejeitou"),
    (r"\b(?:neguei|negou) seguimento (?:à|a)\b", "não aceitou analisar a"), (r"\b(?:neguei|negou) seguimento (?:ao|o)\b", "não aceitou analisar o"),
    (r"\bnão conheci d([ao])\b", r"não aceitei analisar \1"), (r"\bnão conheceu d([ao])\b", r"não aceitou analisar \1"),
    (r"\bd[oa] requerente\b", "de quem pediu"), (r"\b(?:o|a) requerente\b", "quem pediu"),
    (r"\b(?:deste|do) SUPREMO TRIBUNAL FEDERAL\b", "do STF"), (r"\besta Corte\b", "o STF"),
    (r"\bcom o objetivo de\b", "para"), (r"\bvisando\b", "para"),
    (r"\bdeclarar a inconstitucionalidade(?:,? (?:formal e material|material|formal),?)? d([aoe]s?)\b", r"derrubar \1"),
    (r"\b(?:o )?Poder Executivo municipal\b", "a prefeitura"), (r"\b(?:o )?Poder Executivo estadual\b", "o governo do estado"),
]
_LEI_CURTA = re.compile(r"\b(Lei Complementar|Lei|Emenda Constitucional)(?: Estadual| Municipal)?\s+n[º°o.]*\s*([\d.]+)"
                        r"(?:,\s*de\s+\d{1,2}[º°]?\s+de\s+\w+\s+de\s+|/)(\d{4})", re.I)


def em_palavras_simples(frase: str) -> str:
    """A frase oficial com o juridiquês trocado por palavras do dia a dia. "" quando nada mudou."""
    e = re.sub(r"\s+", " ", frase or "").strip()
    if not e:
        return ""
    orig = e
    for de, para in _SIMPLES:
        e = re.sub(de, para, e, flags=re.I)
    # Só o primeiro tipo que aparece na frase (o que está sendo julgado) ganha a explicação
    m = _TIPO_QUALQUER.search(e)
    if m:
        explica = next(x for (_, x), g in zip(_TIPOS, m.groups()) if g)
        e = f"{e[:m.end()]} ({explica}){e[m.end():]}"
    e = _LEI_CURTA.sub(lambda m: f"{m[1].title()} {m[2]}/{m[3]}", e)
    e = re.sub(r"\s+\d+(?:\.\d+)*\.?$", "", e)  # "1.1." solto no fim
    e = re.sub(r"\s{2,}", " ", e).strip()
    if not e:
        return ""
    e = e[:1].upper() + e[1:]
    return "" if e == orig else e


def _arq_relatorio(pasta: Path, jid: str) -> Path:
    return pasta / f"{id_seguro(jid) or 'x'}.json"


def ler_relatorio(link: str) -> str:
    """Baixa o PDF do relatório e devolve a frase do que está em julgamento."""
    time.sleep(PAUSA)
    r = get(link, timeout=60, tries=TENTATIVAS, headers={"Accept": "application/pdf,*/*"})
    raw = r.content
    if raw[:5] != b"%PDF-" or len(raw) > debate.MAX_BYTES:
        return ""
    return objeto_do_relatorio(texto_do_pdf(raw))


_CABECALHO = re.compile(r"^(?:[A-Za-z]{2,5}\s*[\d.]+[^/]{0,30}/\s*[A-Z]{2}|\d{1,3})$")


def texto_do_pdf(raw: bytes, paginas: int = 8) -> str:
    """Texto das primeiras páginas (a frase fica logo depois da lista das partes, que em ação com muitos interessados
    passa de 5 páginas), sem o cabeçalho de cada página
    ("ADI 8042 MC-REF / DF" e o número da página). Lido com o pdfium: o pypdf gruda as palavras destes PDFs
    ("Trata-sedeembargos"), conferido em 17/11/2026."""
    import pypdfium2 as pdfium  # só aqui: o resto da coleta não precisa da biblioteca

    pdf = pdfium.PdfDocument(raw)
    try:
        partes = []
        for i in range(min(paginas, len(pdf))):
            linhas = [l.strip() for l in pdf[i].get_textpage().get_text_range().splitlines()]
            if i:
                while linhas and (not linhas[0] or _CABECALHO.match(linhas[0])):
                    linhas.pop(0)
            partes.append("\n".join(linhas))
        return "\n".join(partes)
    finally:
        pdf.close()


def link_do_relatorio(j: dict) -> str:
    """Julgamentos guardados antes desta versão não têm o link: vem do mesmo serviço de votação, pela lista certa."""
    inc = str(j.get("fonte") or "").rsplit("=", 1)[-1]
    lid = str(j.get("id") or "").rsplit("-", 1)[-1]
    if not inc.isdigit():
        return ""
    for item in _get(VOTACAO, {"sessaoVirtual": inc}) or []:
        for lj in item.get("listasJulgamento") or []:
            if str(lj.get("id")) == lid:
                return _link(lj.get("relatorioRelator"))
    return ""


def com_objeto(julgamentos: list[dict], cache: Path, minutos: float = MINUTOS_RELATORIOS) -> tuple[list[dict], int]:
    """Põe em cada julgamento o que está em julgamento ("objeto": frase oficial, explicação e link do relatório).
    O relatório publicado não muda: cada um é lido uma vez e guardado. Devolve (julgamentos, quantos ficaram para depois)."""
    pasta = cache / "stf" / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + minutos * 60
    faltam = 0
    out = []
    for j in julgamentos:
        j = dict(j)
        out.append(j)
        if j.get("classe") not in CLASSES_RELATORIO:
            j.pop("relatorio", None)
            continue
        arq = _arq_relatorio(pasta, j.get("id", ""))
        d = None
        if arq.exists():
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
                if d.get("v") != VERSAO_RELATORIO:
                    d = None
            except ValueError:
                d = None
        if d is None:
            if time.monotonic() > limite:
                j.pop("relatorio", None)
                faltam += 1
                continue
            try:
                link = url_segura(j.get("relatorio")) or link_do_relatorio(j)
                frase = ler_relatorio(link) if link else ""
            except Exception as e:  # noqa: BLE001 - sem o relatório hoje, tenta na próxima coleta
                log.info("STF: relatório de %s não lido (%s)", j.get("processo"), e)
                j.pop("relatorio", None)
                faltam += 1
                continue
            d = {"v": VERSAO_RELATORIO, "link": link, "texto": frase}
            write_json(arq, d)
        j.pop("relatorio", None)
        link = url_segura(d.get("link"))
        if d.get("texto") and link:
            j["objeto"] = {"texto": d["texto"], "simples": em_palavras_simples(d["texto"]), "link": link}
    return out, faltam

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


def coletar(saida: Path, cache: Path, hoje: dt.date | None = None, minutos: float = 15,
            minutos_relatorios: float = MINUTOS_RELATORIOS) -> dict:
    hoje = hoje or dt.date.today()
    js, sit = coletar_stf(cache / "tribunais", hoje, minutos)
    js, faltam = com_objeto(js, cache / "tribunais", minutos_relatorios)
    if faltam:
        log.info("STF: %d relatórios ficam para a próxima coleta", faltam)
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
                           "servicos": [CALENDARIO, LISTA, VOTACAO], "relatorios": "https://digital.stf.jus.br/"}},
        "classes": CLASSES,
        "ministros": resumo_ministros(js),
        "julgamentos": js,
    }
    write_json(saida / "tribunais.json", out)
    log.info("Tribunais: %d julgamentos do STF (%s)", len(js), sit)
    return out
