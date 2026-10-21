"""Dados das empresas fornecedoras e seus sócios (QSA), a partir da base pública da Receita Federal.

Consulta individual via https://minhareceita.org/{cnpj} (espelho aberto da base CNPJ da Receita),
com cache local para não repetir consultas.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .util import get, norm_name

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


def socios_em_comum(emps: dict[str, dict]) -> dict[str, list[str]]:
    """Para cada sócio, a lista de empresas (entre as fornecedoras) em que ele aparece."""
    idx: dict[str, set[str]] = {}
    for cnpj, e in emps.items():
        for s in e["socios"]:
            if not s["nome"]:
                continue
            idx.setdefault(chave_socio(s), set()).add(cnpj)
    return {k: sorted(v) for k, v in idx.items() if len(v) > 1}
