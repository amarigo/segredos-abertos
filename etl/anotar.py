"""Anotações do GitHub Actions com o motivo de cada problema da coleta, para o painel de status (/status/).

A página /status/ lê as anotações pela API do GitHub (sem senha). Sem elas, uma falha só apareceria como "Process
completed with exit code 1". Fora do GitHub Actions este script não imprime nada.

Uso:
    python etl/anotar.py avisos site/public/data/meta.json "Aviso da coleta"      (um ::warning por aviso da coleta)
    python etl/anotar.py barreira site/public/data/verificacao.json               (seções que barraram a publicação)
    python etl/anotar.py falhou "Eleição 2026" "o que aconteceu"                   (aviso: uma parte que falhou)
    python etl/anotar.py erro "Coleta dos dados" "o que aconteceu"                 (erro: parou a publicação)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sa_etl.util import anotar


def _ler(f: str) -> dict:
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def avisos(arquivo: str, titulo: str) -> None:
    for a in (_ler(arquivo).get("avisos") or [])[:10]:
        anotar("warning", titulo, a)


def barreira(arquivo: str) -> None:
    v = _ler(arquivo)
    secoes = v.get("secoes") or {}
    nomes = [secoes.get(s, {}).get("titulo", s) for s in v.get("barradas") or []]
    limite = v.get("limite_sem_motivo")
    lim = f"{limite * 100:.0f}%" if isinstance(limite, (int, float)) else "o limite"
    if nomes:
        anotar("error", "Verificação com a segunda fonte",
               f"Publicação barrada: diferenças sem motivo conhecido acima de {lim} em {', '.join(nomes)}. "
               "Entenda o motivo e registre em etl/sa_etl/oficial.py.")
    else:
        anotar("error", "Verificação com a segunda fonte", "Publicação barrada por diferenças sem motivo conhecido.")


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "avisos":
        avisos(argv[1], argv[2] if len(argv) > 2 else "Aviso da coleta")
    elif len(argv) >= 2 and argv[0] == "barreira":
        barreira(argv[1])
    elif len(argv) >= 3 and argv[0] in ("falhou", "erro"):
        anotar("warning" if argv[0] == "falhou" else "error", argv[1], argv[2])
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
