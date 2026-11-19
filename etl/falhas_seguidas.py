"""Falhas seguidas de cada fonte oficial: por que falhou, nova tentativa e, depois de 3 falhas, caminho alternativo.

Regra do projeto: quando uma fonte falha, a coleta usa a última cópia boa, registra o motivo e tenta de novo
(tentar-de-novo.yml, a cada 30 minutos olha se precisa). Se a mesma fonte falhar mais de 3 vezes seguidas, tentar de
novo não está resolvendo: é hora de procurar outro caminho (outra API oficial, o arquivo de dados abertos, outro
endereço). Este script guarda a contagem no cache da coleta (etl/.cache, que passa de uma execução para a outra) e
grava a lista das fontes que passaram do limite; o workflow abre (ou atualiza) um aviso no GitHub para cada uma e
fecha o aviso quando a fonte volta.

Uso:
    python etl/falhas_seguidas.py --meta site/public/data/meta.json --estado etl/.cache/falhas-seguidas.json \
        --saida falhas.json [--etapa "Conferência dos dados" --motivo "o que aconteceu"]

--etapa: uma etapa inteira da coleta do Brasil falhou (coleta, conferência ou verificação) e o site ficou com os
dados publicados antes. Conta como falha daquela etapa, com o motivo dado.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# "Mais de 3 falhas": a partir da 4ª falha seguida, abrir o aviso pedindo um caminho alternativo
LIMITE = 3


def _ler(f: Path) -> dict:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def fonte_do_aviso(aviso: str) -> str:
    """O nome da fonte é o começo do aviso, antes do primeiro ": " ("Senadores da 57ª legislatura: a fonte ...")."""
    return aviso.split(": ", 1)[0].strip()[:120]


def falhas_desta_coleta(meta: dict, etapa: str | None, motivo: str | None) -> dict[str, dict]:
    """Fontes que falharam nesta coleta: {fonte: {"aviso", "motivo"}}. Só os avisos que outra coleta pode resolver."""
    motivos = meta.get("motivos_falha") or {}
    out: dict[str, dict] = {}
    for a in meta.get("avisos_tentar", meta.get("avisos")) or []:
        if not isinstance(a, str):
            continue
        f = fonte_do_aviso(a)
        out.setdefault(f, {"aviso": a, "motivo": motivos.get(f) or "a fonte não respondeu (veja o registro da coleta)"})
    if etapa:
        out[f"Coleta do Brasil: {etapa}"] = {"aviso": f"{etapa} falhou; o site ficou com os dados publicados antes",
                                             "motivo": motivo or "veja o registro da execução"}
    return out


def atualizar(estado: dict, falhas: dict[str, dict], agora: str) -> dict:
    """Soma 1 às fontes que falharam de novo e zera (tira) as que voltaram."""
    novo = {}
    for f, x in falhas.items():
        antes = estado.get(f) or {}
        novo[f] = {"seguidas": int(antes.get("seguidas", 0)) + 1, "desde": antes.get("desde") or agora,
                   "ultima": agora, "aviso": x["aviso"], "motivo": x["motivo"]}
    return novo


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--estado", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--etapa")
    ap.add_argument("--motivo")
    a = ap.parse_args(argv)
    meta = _ler(a.meta) if not a.etapa else {}  # com a etapa do Brasil falhando, o meta.json é o publicado antes
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    antes = _ler(a.estado)
    estado = atualizar(antes, falhas_desta_coleta(meta, a.etapa, a.motivo), agora)
    if a.etapa:  # as fontes de dentro da coleta não foram lidas desta vez: a contagem delas fica como estava
        for f, x in antes.items():
            if not f.startswith("Coleta do Brasil: "):
                estado.setdefault(f, x)
    a.estado.parent.mkdir(parents=True, exist_ok=True)
    a.estado.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    acima = {f: x for f, x in estado.items() if x["seguidas"] > LIMITE}
    voltaram = sorted(f for f in antes if f not in estado)
    a.saida.write_text(json.dumps({"limite": LIMITE, "acima": acima, "voltaram": voltaram, "todas": estado},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    for f, x in sorted(estado.items()):
        print(f"- {f}: {x['seguidas']} falha(s) seguida(s) desde {x['desde']}. Motivo: {x['motivo']}")
    for f in voltaram:
        print(f"- {f}: voltou a responder")
    if not estado and not voltaram:
        print("Nenhuma fonte falhou nesta coleta.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
