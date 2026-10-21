"""Dados das empresas fornecedoras e seus sócios (QSA), a partir da base pública da Receita Federal.

Consulta individual via https://minhareceita.org/{cnpj} (espelho aberto da base CNPJ da Receita),
com cache local para não repetir consultas.
"""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .util import digits, get, norm_name

log = logging.getLogger("sa_etl.cnpj")

URL = "https://minhareceita.org/{cnpj}"


def parse_empresa(d: dict) -> dict:
    socios = []
    for s in d.get("qsa") or []:
        socios.append({
            "nome": (s.get("nome_socio") or "").strip(),
            "doc": (s.get("cnpj_cpf_do_socio") or "").strip(),
            "qualificacao": s.get("qualificacao_socio") or "",
            "entrada": s.get("data_entrada_sociedade") or "",
            "faixa_etaria": s.get("faixa_etaria") or "",
            "tipo": {1: "empresa", 2: "pessoa", 3: "estrangeiro"}.get(s.get("identificador_de_socio"), ""),
            "pais": (s.get("pais") or "").strip() if isinstance(s.get("pais"), str) else "",
        })
    mun = d.get("municipio") or ""
    return {
        "cnpj": d.get("cnpj") or "",
        "razao_social": d.get("razao_social") or "",
        "nome_fantasia": d.get("nome_fantasia") or "",
        "situacao": d.get("descricao_situacao_cadastral") or "",
        "abertura": d.get("data_inicio_atividade") or "",
        "atividade": d.get("cnae_fiscal_descricao") or "",
        "municipio": mun.title() if isinstance(mun, str) else "",
        "uf": d.get("uf") or "",
        "capital_social": d.get("capital_social") or 0,
        "porte": d.get("porte") or "",
        "natureza": d.get("natureza_juridica") or "",
        "endereco": {
            "logradouro": " ".join(x for x in (d.get("descricao_tipo_de_logradouro") or "", d.get("logradouro") or "") if x).strip(),
            "numero": (d.get("numero") or "").strip(),
            "complemento": (d.get("complemento") or "").strip(),
            "bairro": (d.get("bairro") or "").strip(),
            "cep": (d.get("cep") or "").strip(),
        },
        "socios": socios,
    }


def _fetch(cnpj: str, cache: Path) -> dict | None:
    f = cache / f"{cnpj}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    try:
        raw = get(URL.format(cnpj=cnpj), tries=3, timeout=60).json()
    except Exception as e:  # noqa: BLE001
        log.debug("CNPJ %s sem dados: %s", cnpj, e)
        return None
    emp = parse_empresa(raw)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(emp, ensure_ascii=False), encoding="utf-8")
    return emp


def empresas(cnpjs: list[str], cache: Path, workers: int = 6) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for cnpj, emp in zip(cnpjs, ex.map(lambda c: _fetch(c, cache), cnpjs)):
            if emp:
                out[cnpj] = emp
    log.info("Receita: dados de %d de %d empresas", len(out), len(cnpjs))
    return out


def chave_socio(s: dict) -> str:
    """Identifica um sócio. A Receita mascara o CPF (***123456**), então usamos nome + dígitos visíveis."""
    return f"{norm_name(s['nome'])}|{s['doc']}"


def socios_em_comum(emps: dict[str, dict], socias: dict[str, dict] | None = None) -> dict[str, list[str]]:
    """Para cada dono, a lista de empresas (entre as fornecedoras) por trás das quais ele aparece.

    Conta o sócio direto e também quem está por trás das holdings (donos finais), para ligar empresas
    do mesmo dono mesmo quando uma delas pertence a ele através de outra empresa.
    """
    todas = {**(socias or {}), **emps}
    idx: dict[str, set[str]] = {}
    for cnpj in emps:
        for k in chaves_de_dono(cnpj, todas):
            idx.setdefault(k, set()).add(cnpj)
    return {k: sorted(v) for k, v in idx.items() if len(v) > 1}


def chave_endereco(e: dict) -> str | None:
    """Endereço normalizado (CEP + número + complemento). Sem número, não dá para comparar com segurança."""
    end = e.get("endereco") or {}
    cep = re.sub(r"\D", "", end.get("cep") or "")
    num = norm_name(end.get("numero") or "")
    if len(cep) != 8 or not num or num in ("SN", "S/N", "0"):
        return None
    comp = norm_name(end.get("complemento") or "")
    comp = re.sub(r"[^A-Z0-9 ]", "", comp)
    return f"{cep}|{num}|{comp}"


def mesmo_endereco(emps: dict[str, dict]) -> dict[str, list[str]]:
    """Para cada endereço, as empresas fornecedoras registradas nele (só quando há mais de uma)."""
    idx: dict[str, set[str]] = {}
    for cnpj, e in emps.items():
        k = chave_endereco(e)
        if k:
            idx.setdefault(k, set()).add(cnpj[:8])  # raiz do CNPJ: filiais da mesma empresa contam uma vez
    grupos = {}
    for cnpj, e in emps.items():
        k = chave_endereco(e)
        if k and len(idx[k]) > 1:
            grupos.setdefault(k, []).append(cnpj)
    return {k: sorted(v) for k, v in grupos.items() if len({c[:8] for c in v}) > 1}


# ---------------------------------------------------------------- donos finais (sócios de sócios)

MAX_NIVEL = 5  # empresa -> holding -> holding ... até no máximo 5 empresas no caminho


def cnpj_matriz(raiz: str) -> str:
    """CNPJ completo da matriz (0001) a partir da raiz de 8 dígitos, com os dígitos verificadores."""
    base = digits(raiz)[:8].zfill(8) + "0001"
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        r = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        base += "0" if r < 2 else str(11 - r)
    return base


def cnpj_socio(s: dict) -> str:
    """CNPJ de um sócio que é empresa. A base da Receita às vezes traz só a raiz (8 dígitos): usamos a matriz."""
    d = digits(s.get("doc"))
    return d if len(d) == 14 else cnpj_matriz(d) if len(d) == 8 else d


def tipo_socio(s: dict) -> str:
    """empresa, pessoa ou estrangeiro. Dados antigos do cache não têm o campo: deduzimos pelo documento."""
    doc = s.get("doc") or ""
    if "*" not in doc and len(digits(doc)) in (8, 14):
        return "empresa"
    if s.get("tipo"):
        return s["tipo"]
    if "*" in doc or len(digits(doc)) == 11:
        return "pessoa"
    return "estrangeiro" if s.get("nome") else "pessoa"


def buscar_socias(emps: dict[str, dict], cache: Path, max_nivel: int = MAX_NIVEL, limite: int = 5000,
                  workers: int = 6) -> dict[str, dict]:
    """Busca na Receita as empresas que aparecem como sócias (holdings), nível por nível."""
    conhecidas = dict(emps)
    novas: dict[str, dict] = {}
    fila = {cnpj_socio(s) for e in emps.values() for s in e["socios"] if tipo_socio(s) == "empresa"} - set(conhecidas)
    log.info("Receita: %d sócios são empresas fora da lista de fornecedoras", len(fila))
    falhas = 0
    for _ in range(max_nivel):
        fila = sorted(c for c in fila if c not in conhecidas)[: max(0, limite - len(novas))]
        if not fila:
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            achadas = dict(zip(fila, ex.map(lambda c: _fetch(c, cache), fila)))
        prox = set()
        for c, e in achadas.items():
            conhecidas[c] = e or {}
            falhas += not e
            if e:
                novas[c] = e
                prox |= {cnpj_socio(s) for s in e["socios"] if tipo_socio(s) == "empresa"}
        fila = prox
    log.info("Receita: %d empresas sócias (holdings) buscadas, %d sem resposta", len(novas), falhas)
    return novas


def donos_finais(cnpj: str, todas: dict[str, dict], max_nivel: int = MAX_NIVEL) -> list[dict]:
    """Segue os sócios que são empresas até chegar às pessoas.

    Cada item: nome, doc, tipo, qualificacao, cadeia (empresas no caminho, sem a própria) e fim:
    "pessoa", "estrangeiro", "sem_socios" (a Receita não lista sócios da holding), "sem_dados"
    (não achamos a holding), "limite" (caminho longo demais) ou "ciclo" (empresas sócias umas das outras).
    """
    out: list[dict] = []
    vistos: set[tuple] = set()

    def seguir(c: str, cadeia: list[dict]):
        e = todas.get(c)
        for s in (e or {}).get("socios", []):
            t = tipo_socio(s)
            if t != "empresa":
                k = (chave_socio(s), tuple(x["cnpj"] for x in cadeia))
                if k not in vistos:
                    vistos.add(k)
                    out.append({"nome": s["nome"], "doc": s["doc"], "tipo": t, "qualificacao": s.get("qualificacao", ""),
                                "pais": s.get("pais", ""), "cadeia": cadeia, "fim": t})
                continue
            filho = cnpj_socio(s)
            sub = todas.get(filho) or next((v for k, v in todas.items() if k[:8] == filho[:8]), None)
            elo = {"cnpj": filho, "nome": (sub or {}).get("razao_social") or s["nome"], "qualificacao": s.get("qualificacao", "")}
            nova = cadeia + [elo]
            fim = ("ciclo" if filho[:8] == cnpj[:8] or any(x["cnpj"][:8] == filho[:8] for x in cadeia)
                   else "limite" if len(nova) > max_nivel
                   else "sem_dados" if not sub
                   else "sem_socios" if not sub.get("socios") else "")
            if fim:
                out.append({"nome": elo["nome"], "doc": filho, "tipo": "empresa", "qualificacao": s.get("qualificacao", ""),
                            "pais": "", "cadeia": nova, "fim": fim})
            else:
                seguir(filho, nova)

    seguir(cnpj, [])
    return out


def chave_dono(s: dict) -> str:
    """Como chave_socio, mas uma empresa sócia é identificada só pelo CNPJ (o nome pode vir escrito diferente)."""
    return f"PJ|{cnpj_socio(s)[:8]}" if tipo_socio(s) == "empresa" else chave_socio(s)  # raiz: matriz e filiais


def chaves_de_dono(cnpj: str, todas: dict[str, dict], finais: list[dict] | None = None) -> set[str]:
    """Quem está por trás da empresa: sócios diretos, holdings no caminho e donos finais."""
    ks = {chave_dono(s) for s in (todas.get(cnpj) or {}).get("socios", []) if s.get("nome")}
    for d in finais if finais is not None else donos_finais(cnpj, todas):
        ks.add(chave_dono(d))
        ks |= {f"PJ|{x['cnpj'][:8]}" for x in d["cadeia"]}
    return ks
