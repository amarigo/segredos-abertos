"""Emendas Pix: em que a prefeitura ou o estado gastou o dinheiro, e a quem pagou.

Na emenda Pix (transferência especial) o dinheiro cai direto no caixa da prefeitura ou do estado. O governo federal
só registra o repasse; o que a prefeitura fez depois com o dinheiro fica no Transferegov, onde ela é obrigada a
registrar o plano de ação (o objeto), quem executa, as metas e, no relatório de gestão, cada pagamento que fez com o
dinheiro da emenda (quem recebeu, para quê, quanto e quando). É o mais perto das notas fiscais que um órgão federal
publica.

Fonte: API oficial de dados abertos do Transferegov, módulo de Transferências Especiais:
    https://api-publica.transferegov.gestao.gov.br/especiais/docs

Tabelas usadas (cada uma liga com a seguinte pelo identificador):
- planos-acao-especiais: uma linha por emenda Pix (parlamentar, número da emenda, valor, objeto); filtrada pelo ano
- beneficiarios-especiais: quem recebeu (prefeitura ou estado, com CNPJ e UF)
- executores-especiais: quem executa o plano e o objeto de cada um
- relatorios-gestao-novos-especiais: o relatório de gestão de cada executor (quanto já foi executado)
- relatorios-gestao-documento-liquidacao-especiais: cada pagamento feito com o dinheiro, ligado a um relatório
- meta-especiais: as metas do executor (o que vai ser entregue, com quantidade e valor)

A API devolve no máximo 200 linhas por página. A leitura completa leva vários minutos, então ela é feita aos poucos,
com um limite de tempo por execução, e continua de onde parou na execução seguinte. Cada tabela completa vale por
uma semana (VALIDADE_DIAS); enquanto a nova leitura não termina, o site usa a última leitura completa.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from .util import avisar, digits, get_json, to_float, write_json

log = logging.getLogger("sa_etl.transferegov")

API = "https://api-publica.transferegov.gestao.gov.br/especiais"
FONTE = "https://api-publica.transferegov.gestao.gov.br/especiais/docs"
CONSULTA = "https://especiais.transferegov.sistema.gov.br/transferencia-especial/plano-acao/consulta"
TAMANHO = 200        # linhas por página (o máximo que o módulo aceita)
LOTE_IDS = 100       # identificadores por pedido nos filtros que aceitam vários (o máximo do módulo)
VALIDADE_DIAS = 7
VERSAO = 1

# Só as colunas que o site usa (as tabelas trazem também conta bancária, e-mail etc.)
CAMPOS = {
    "planos": ["id_plano_acao", "codigo_plano_acao", "situacao_plano_acao", "nome_parlamentar_emenda_plano_acao",
               "codigo_emenda_parlamentar_formatado_plano_acao", "ano_emenda_parlamentar_plano_acao",
               "codigo_parlamentar_emenda_plano_acao", "numero_emenda_parlamentar_plano_acao", "valor_custeio_plano_acao",
               "valor_investimento_plano_acao", "id_beneficiario", "nome_objeto", "detalhamento_objeto",
               "codigo_descricao_areas_politicas_publicas_plano_acao", "descricao_programacao_orcamentaria_plano_acao",
               "motivo_impedimento_plano_acao"],
    "beneficiarios": ["id_beneficiario", "uf_beneficiario", "nome_beneficiario", "cnpj_beneficiario"],
    "executores": ["id_executor", "id_plano_acao", "cnpj_executor", "nome_executor", "objeto_executor",
                   "vl_custeio_executor", "vl_investimento_executor"],
    "relatorios": ["id_relatorio_gestao_novo", "id_plano_acao", "id_executor", "data_relatorio_gestao_novo",
                   "situacao_relatorio_gestao_novo", "valor_executado_relatorio_gestao_novo",
                   "valor_pendente_relatorio_gestao_novo"],
    "gastos": ["id_relatorio_gestao_dl", "id_relatorio_gestao_novo", "tx_descricao_relatorio_gestao_dl",
               "tp_doc_recebedor_relatorio_gestao_dl", "tx_identificacao_recebedor_mascarado_relatorio_gestao_dl",
               "tx_nome_recebedor_relatorio_gestao_dl", "vl_pagamento_relatorio_gestao_dl", "dt_pagamento_relatorio_gestao_dl",
               "tx_natureza_relatorio_gestao_dl"],
    "metas": ["id_executor", "id_meta", "sequencial_meta", "nome_meta", "desc_meta", "un_medida_meta", "qt_unidade_meta",
              "vl_custeio_emenda_especial_meta", "vl_investimento_emenda_especial_meta"],
}
CAMINHO = {
    "planos": "planos-acao-especiais", "beneficiarios": "beneficiarios-especiais", "executores": "executores-especiais",
    "relatorios": "relatorios-gestao-novos-especiais", "gastos": "relatorios-gestao-documento-liquidacao-especiais",
    "metas": "meta-especiais",
}
CHAVE = {"planos": "id_plano_acao", "beneficiarios": "id_beneficiario", "executores": "id_executor",
         "relatorios": "id_relatorio_gestao_novo", "gastos": "id_relatorio_gestao_dl", "metas": "id_meta"}


def _agora() -> float:
    return time.monotonic()


class SemTempo(Exception):
    """O limite de tempo desta execução acabou; a leitura continua na próxima."""


def _pagina(caminho: str, filtros: dict, pagina: int) -> tuple[list[dict], int]:
    """Uma página da API: (linhas, total de linhas que a consulta tem)."""
    d = get_json(f"{API}/{caminho}", params={**filtros, "pagina": pagina, "tamanho_da_pagina": TAMANHO}, timeout=90)
    if not isinstance(d, dict) or not isinstance(d.get("data"), list):
        raise RuntimeError(f"Transferegov: resposta inesperada em {caminho} (sem a lista 'data')")
    return d["data"], int(d.get("total_items") or 0)


def _ler_gz(f: Path) -> dict | None:
    try:
        return json.loads(gzip.decompress(f.read_bytes()))
    except (OSError, ValueError):
        return None


def _gravar_gz(f: Path, d: dict) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    tmp.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode()))
    tmp.replace(f)


def _vencida(estado: dict, hoje: dt.date) -> bool:
    em = estado.get("completo_em")
    return not em or (hoje - dt.date.fromisoformat(em)).days >= VALIDADE_DIAS


class Leitor:
    """Lê as tabelas da API aos poucos, guardando o progresso no cache para continuar na próxima execução."""

    def __init__(self, cache: Path, minutos: float, hoje: dt.date | None = None):
        self.cache = cache
        self.fim = _agora() + minutos * 60
        self.hoje = hoje or dt.date.today()
        self.paginas = 0

    def _tempo(self) -> None:
        if _agora() > self.fim:
            raise SemTempo

    def tabela(self, nome: str, filtros: dict | None = None, rotulo: str = "") -> dict:
        """Tabela inteira (ou a parte que o filtro pede), página por página.

        Devolve {"linhas", "completo_em"}: a leitura completa mais recente. Se a leitura nova não terminou, as linhas
        são as da leitura completa anterior (ou vazias, na primeira vez)."""
        filtros = filtros or {}
        f = self.cache / f"{nome}{rotulo}-v{VERSAO}.json.gz"
        st = _ler_gz(f) or {"linhas": [], "completo_em": None, "parcial": None}
        if not _vencida(st, self.hoje):
            return st
        p = st.get("parcial") or {"pagina": 1, "linhas": [], "total": None}
        campos = CAMPOS[nome]
        try:
            while True:
                self._tempo()
                linhas, total = _pagina(CAMINHO[nome], filtros, p["pagina"])
                self.paginas += 1
                p["total"] = total
                p["linhas"] += [{k: x.get(k) for k in campos} for x in linhas]
                p["pagina"] += 1
                if not linhas or len(p["linhas"]) >= total:
                    break
        except SemTempo:
            st["parcial"] = p
            _gravar_gz(f, st)
            log.info("Transferegov %s%s: %d de %s linhas lidas; continua na próxima execução",
                     nome, rotulo, len(p["linhas"]), p["total"])
            raise
        except Exception:
            st["parcial"] = p  # o que já veio não se perde
            _gravar_gz(f, st)
            raise
        # sem repetir linhas (se a tabela mudou durante a leitura, uma linha pode vir em duas páginas)
        unicas = {x.get(CHAVE[nome]): x for x in p["linhas"]}
        if p["total"] and len(unicas) < 0.98 * p["total"]:
            log.warning("Transferegov %s%s: %d linhas de %d anunciadas", nome, rotulo, len(unicas), p["total"])
        st = {"linhas": list(unicas.values()), "completo_em": self.hoje.isoformat(), "parcial": None, "total": p["total"]}
        _gravar_gz(f, st)
        log.info("Transferegov %s%s: %d linhas", nome, rotulo, len(st["linhas"]))
        return st

    def gastos(self, ids_relatorio: list[int]) -> dict:
        """Pagamentos dos relatórios de gestão, pedidos em lotes de 100 relatórios (o filtro aceita vários).

        {"por_relatorio": {id: [linhas]}, "lidos": {id: data}}. Cada relatório é lido de novo depois de VALIDADE_DIAS."""
        f = self.cache / f"gastos-v{VERSAO}.json.gz"
        st = _ler_gz(f) or {"por_relatorio": {}, "lidos": {}}
        falta = [i for i in sorted(set(ids_relatorio))
                 if not st["lidos"].get(str(i)) or (self.hoje - dt.date.fromisoformat(st["lidos"][str(i)])).days >= VALIDADE_DIAS]
        campos = CAMPOS["gastos"]
        try:
            for k in range(0, len(falta), LOTE_IDS):
                self._tempo()  # entre lotes: um lote começado vai até o fim (são poucas páginas)
                lote = falta[k:k + LOTE_IDS]
                novas: dict[str, list] = {str(i): [] for i in lote}
                pagina, lidas = 1, 0
                while True:
                    linhas, total = _pagina(CAMINHO["gastos"], {"id_relatorio_gestao_novo": ",".join(map(str, lote))}, pagina)
                    self.paginas += 1
                    for x in linhas:
                        rel = str(x.get("id_relatorio_gestao_novo"))
                        if rel in novas:  # se a API ignorar o filtro, não guarda o que não foi pedido
                            novas[rel].append({c: x.get(c) for c in campos})
                    lidas += len(linhas)
                    pagina += 1
                    if not linhas or lidas >= total:
                        break
                for rel, ls in novas.items():
                    st["por_relatorio"][rel] = list({x.get("id_relatorio_gestao_dl"): x for x in ls}.values())
                    st["lidos"][rel] = self.hoje.isoformat()
        finally:
            _gravar_gz(f, st)
        return st


# ---------------------------------------------------------------- coleta

def coletar(anos: list[int], cache: Path, minutos: float = 15, hoje: dt.date | None = None) -> dict | None:
    """Lê o que faltar das tabelas, até o limite de tempo. Devolve as tabelas já lidas (as completas mais recentes)
    e o que ainda falta, ou None se não há nada lido ainda."""
    cache.mkdir(parents=True, exist_ok=True)
    ler = Leitor(cache, minutos, hoje)
    t: dict = {"planos": {}, "falta": []}
    try:
        t["beneficiarios"] = ler.tabela("beneficiarios")
        for ano in sorted(anos, reverse=True):  # o ano mais recente primeiro
            t["planos"][ano] = ler.tabela("planos", {"ano_emenda_parlamentar_plano_acao": ano}, f"-{ano}")
        t["executores"] = ler.tabela("executores")
        t["relatorios"] = ler.tabela("relatorios")
        ids = _relatorios_dos_planos(t)
        t["gastos"] = ler.gastos(ids)
        t["metas"] = ler.tabela("metas")
    except SemTempo:
        t["falta"].append("leitura incompleta")
    except Exception as e:  # noqa: BLE001
        log.warning("Transferegov: a leitura parou (%s); o site usa o que já foi lido", str(e)[:200])
        t["falta"].append(str(e)[:120])
    # o que não deu tempo de ler nesta execução vem das leituras completas anteriores, no cache
    for nome in ("beneficiarios", "executores", "relatorios", "metas"):
        t.setdefault(nome, _ler_gz(cache / f"{nome}-v{VERSAO}.json.gz") or {"linhas": []})
    for ano in anos:
        if not t["planos"].get(ano):
            t["planos"][ano] = _ler_gz(cache / f"planos-{ano}-v{VERSAO}.json.gz") or {"linhas": []}
    t.setdefault("gastos", _ler_gz(cache / f"gastos-v{VERSAO}.json.gz") or {"por_relatorio": {}, "lidos": {}})
    log.info("Transferegov: %d páginas lidas nesta execução%s", ler.paginas,
             f"; falta: {', '.join(t['falta'])}" if t["falta"] else "; tudo em dia")
    if not any(t["planos"][a].get("linhas") for a in anos):
        return None
    return t


def _relatorios_dos_planos(t: dict) -> list[int]:
    planos = {x["id_plano_acao"] for p in t["planos"].values() for x in p.get("linhas", [])}
    return [x["id_relatorio_gestao_novo"] for x in t["relatorios"].get("linhas", []) if x.get("id_plano_acao") in planos
            and x.get("id_relatorio_gestao_novo") is not None]


# ---------------------------------------------------------------- resumo para o site

def codigo_emenda(p: dict) -> str:
    """O número da emenda como no Portal da Transparência (ano + autor + sequencial, 12 dígitos)."""
    c = digits(p.get("codigo_emenda_parlamentar_formatado_plano_acao"))
    if c:
        return c
    ano, autor, num = p.get("ano_emenda_parlamentar_plano_acao"), p.get("codigo_parlamentar_emenda_plano_acao"), p.get("numero_emenda_parlamentar_plano_acao")
    if ano and autor and num:
        return f"{int(ano)}{int(autor):04d}{int(num):04d}"
    return c


def _texto(*xs) -> str:
    for x in xs:
        if isinstance(x, str) and x.strip():
            return " ".join(x.split())
    return ""


def _data(s) -> str:
    return (s or "")[:10] if isinstance(s, str) else ""


def _gasto(x: dict) -> dict:
    """Um pagamento feito pela prefeitura ou pelo estado. Só mostramos o CNPJ; de pessoa física, só o nome, como a
    própria API (que já vem com o CPF mascarado)."""
    tipo = (x.get("tp_doc_recebedor_relatorio_gestao_dl") or "").upper()
    doc = digits(x.get("tx_identificacao_recebedor_mascarado_relatorio_gestao_dl"))
    return {"data": _data(x.get("dt_pagamento_relatorio_gestao_dl")),
            "recebedor": _texto(x.get("tx_nome_recebedor_relatorio_gestao_dl")) or "Não informado",
            "cnpj": doc if tipo == "CNPJ" and len(doc) == 14 else "",
            "pessoa": tipo == "CPF",
            "descricao": _texto(x.get("tx_descricao_relatorio_gestao_dl")),
            "natureza": _texto(x.get("tx_natureza_relatorio_gestao_dl")).capitalize(),
            "valor": round(to_float(x.get("vl_pagamento_relatorio_gestao_dl")), 2)}


def resumir(t: dict, anos: list[int]) -> dict[int, dict]:
    """Junta as tabelas: para cada ano da emenda, cada prefeitura ou estado com os planos, executores, metas e
    pagamentos. {ano: {"beneficiarios": {cnpj: {...}}, "emendas": {código: cnpj}, ...}}"""
    benef = {x["id_beneficiario"]: x for x in t["beneficiarios"].get("linhas", [])}
    execs = defaultdict(list)
    for x in t["executores"].get("linhas", []):
        execs[x.get("id_plano_acao")].append(x)
    metas = defaultdict(list)
    for x in t["metas"].get("linhas", []):
        metas[x.get("id_executor")].append(x)
    rels = defaultdict(list)
    for x in t["relatorios"].get("linhas", []):
        rels[x.get("id_plano_acao")].append(x)
    gastos_rel = t["gastos"].get("por_relatorio", {})
    lidos = t["gastos"].get("lidos", {})

    out: dict[int, dict] = {}
    for ano in anos:
        bs: dict[str, dict] = {}
        emendas: dict[str, str] = {}
        sem_gastos_lidos = 0
        for p in t["planos"].get(ano, {}).get("linhas", []):
            if p.get("ano_emenda_parlamentar_plano_acao") not in (None, ano):
                continue  # a API ignora em silêncio um filtro que não conhece: conferimos o ano aqui também
            b = benef.get(p.get("id_beneficiario")) or {}
            cnpj = digits(b.get("cnpj_beneficiario"))
            if len(cnpj) != 14:
                continue
            item = bs.setdefault(cnpj, {"cnpj": cnpj, "nome": _texto(b.get("nome_beneficiario")), "uf": b.get("uf_beneficiario") or "",
                                        "valor": 0.0, "executado": 0.0, "gasto": 0.0, "n_gastos": 0, "planos": []})
            valor = round(to_float(p.get("valor_custeio_plano_acao")) + to_float(p.get("valor_investimento_plano_acao")), 2)
            pid = p.get("id_plano_acao")
            # relatório de gestão: o mais recente de cada executor diz quanto já foi executado
            ultimo: dict = {}
            for r in rels.get(pid, []):
                k = r.get("id_executor")
                if k not in ultimo or (r.get("data_relatorio_gestao_novo") or "") > (ultimo[k].get("data_relatorio_gestao_novo") or ""):
                    ultimo[k] = r
            # os pagamentos de todos os relatórios do plano, sem repetir o mesmo pagamento em dois relatórios
            vistos, gastos = set(), []
            todos_lidos = True
            for r in rels.get(pid, []):
                rid = str(r.get("id_relatorio_gestao_novo"))
                if rid not in lidos:
                    todos_lidos = False
                for g in gastos_rel.get(rid, []):
                    gg = _gasto(g)
                    chave = (gg["data"], gg["recebedor"], gg["valor"], gg["descricao"])
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    gastos.append(gg)
            if not todos_lidos:
                sem_gastos_lidos += 1
            gastos.sort(key=lambda g: (g["data"], -g["valor"]), reverse=True)
            executores = []
            for e in execs.get(pid, []):
                r = ultimo.get(e.get("id_executor")) or {}
                executores.append({
                    "cnpj": digits(e.get("cnpj_executor")), "nome": _texto(e.get("nome_executor")),
                    "objeto": _texto(e.get("objeto_executor")),
                    "valor": round(to_float(e.get("vl_custeio_executor")) + to_float(e.get("vl_investimento_executor")), 2),
                    "executado": round(to_float(r.get("valor_executado_relatorio_gestao_novo")), 2),
                    "relatorio": _data(r.get("data_relatorio_gestao_novo")),
                    "metas": [{"nome": _texto(m.get("nome_meta")), "descricao": _texto(m.get("desc_meta")),
                               "quantidade": to_float(m.get("qt_unidade_meta")), "unidade": _texto(m.get("un_medida_meta")),
                               "valor": round(to_float(m.get("vl_custeio_emenda_especial_meta"))
                                              + to_float(m.get("vl_investimento_emenda_especial_meta")), 2)}
                              for m in sorted(metas.get(e.get("id_executor"), []), key=lambda m: m.get("sequencial_meta") or 0)],
                })
            cod = codigo_emenda(p)
            plano = {
                "id": pid, "plano": p.get("codigo_plano_acao") or "", "emenda": cod,
                "parlamentar": _texto(p.get("nome_parlamentar_emenda_plano_acao")),
                "situacao": _texto(p.get("situacao_plano_acao")).capitalize(),
                "impedimento": _texto(p.get("motivo_impedimento_plano_acao")),
                "valor": valor, "custeio": round(to_float(p.get("valor_custeio_plano_acao")), 2),
                "investimento": round(to_float(p.get("valor_investimento_plano_acao")), 2),
                "area": _texto(p.get("codigo_descricao_areas_politicas_publicas_plano_acao")),
                "objeto": _texto(p.get("detalhamento_objeto"), p.get("nome_objeto")),
                "executores": executores,
                "executado": round(sum(e["executado"] for e in executores), 2),
                "gasto": round(sum(g["valor"] for g in gastos), 2),
                "gastos": gastos,
            }
            item["planos"].append(plano)
            item["valor"] += valor
            item["executado"] += plano["executado"]
            item["gasto"] += plano["gasto"]
            item["n_gastos"] += len(gastos)
            if cod:
                emendas[cod] = cnpj
        for b in bs.values():
            b["planos"].sort(key=lambda p: -p["valor"])
            for k in ("valor", "executado", "gasto"):
                b[k] = round(b[k], 2)
            b["recebedores"] = _recebedores(b["planos"])
        if bs:
            out[ano] = {"beneficiarios": bs, "emendas": emendas, "planos_sem_gastos_lidos": sem_gastos_lidos}
            log.info("Transferegov %d: %d emendas Pix em %d prefeituras e estados, R$ %.0f no plano, R$ %.0f em %d "
                     "pagamentos informados", ano, sum(len(b["planos"]) for b in bs.values()), len(bs),
                     sum(b["valor"] for b in bs.values()), sum(b["gasto"] for b in bs.values()),
                     sum(b["n_gastos"] for b in bs.values()))
    return out


def _recebedores(planos: list[dict]) -> list[dict]:
    """A quem a prefeitura mais pagou com o dinheiro das emendas Pix (todos, sem corte)."""
    soma: dict[tuple, dict] = {}
    for p in planos:
        for g in p["gastos"]:
            k = (g["cnpj"] or g["recebedor"], g["pessoa"])
            x = soma.setdefault(k, {"nome": g["recebedor"], "cnpj": g["cnpj"], "pessoa": g["pessoa"], "valor": 0.0, "n": 0})
            x["valor"] += g["valor"]
            x["n"] += 1
    return [{**x, "valor": round(x["valor"], 2)} for x in sorted(soma.values(), key=lambda x: -x["valor"])]


def gravar(saida: Path, res: dict[int, dict], t: dict) -> None:
    """data/emendas/destino/{ano}.json (a lista) e data/emendas/destino/{ano}/{cnpj}.json (o detalhe, aberto sob demanda)."""
    datas = [x.get("completo_em") for x in [t["beneficiarios"], t["executores"], t["relatorios"], t["metas"], *t["planos"].values()]
             if x.get("completo_em")]
    for ano, r in res.items():
        pasta = saida / "emendas" / "destino" / str(ano)
        lista = []
        for cnpj, b in r["beneficiarios"].items():
            write_json(pasta / f"{cnpj}.json", {**b, "ano": ano, "fonte": FONTE, "consulta": CONSULTA})
            lista.append({k: b[k] for k in ("cnpj", "nome", "uf", "valor", "executado", "gasto", "n_gastos")} | {"n": len(b["planos"])})
        lista.sort(key=lambda x: -x["valor"])
        write_json(saida / "emendas" / "destino" / f"{ano}.json", {
            "ano": ano, "fonte": FONTE, "consulta": CONSULTA, "atualizado": min(datas) if datas else "",
            "completo": not t.get("falta") and not r["planos_sem_gastos_lidos"],
            "planos_sem_gastos_lidos": r["planos_sem_gastos_lidos"],
            "n": sum(x["n"] for x in lista), "valor": round(sum(x["valor"] for x in lista), 2),
            "gasto": round(sum(x["gasto"] for x in lista), 2), "n_gastos": sum(x["n_gastos"] for x in lista),
            "beneficiarios": lista, "emendas": r["emendas"],
        })


def executar(anos: list[int], cache: Path, saida: Path, minutos: float = 15) -> dict[int, dict] | None:
    """Coleta, resume e grava. Se falhar, o resto do site segue (e a página mostra os links do Transferegov)."""
    t = coletar(anos, cache, minutos)
    if not t:
        avisar("Emendas Pix: o Transferegov ainda não foi lido; a página mostra só os links para a consulta oficial")
        return None
    if t["falta"]:
        avisar("Emendas Pix: a leitura do Transferegov continua na próxima execução; os planos e pagamentos mostrados "
               "são os da última leitura completa")
    res = resumir(t, anos)
    gravar(saida, res, t)
    return res
