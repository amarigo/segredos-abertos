"""Monta os dados do Minas Nossa.

1. Recorte de MG dos dados nacionais já gerados na mesma execução (deputados federais, senadores, votações,
   empresas, partidos).
2. Histórico das cidades acompanhadas, com os arquivos do TSE.
3. Junta os avisos da coleta (fontes fora do ar, cópias antigas em uso) no meta.json, para o site mostrar.

Uso (de dentro de mg/etl, com o coletor nacional no PYTHONPATH):
    PYTHONPATH=../../etl python -m mg_etl.build --nacional ../../site/public/data --saida ../../site/public-mg/data --cache .cache
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

from sa_etl import util

from . import cidades, recorte

log = logging.getLogger("mg_etl.build")


def limpar_saida(saida: Path, nacional: Path) -> None:
    """Começa do zero, para não sobrar arquivo de político que saiu. Só apaga uma pasta que já é de dados."""
    if saida.resolve() == nacional.resolve():
        raise ValueError("A pasta de saída não pode ser a mesma dos dados nacionais")
    if saida.exists():
        if any(saida.iterdir()) and not (saida / "meta.json").exists():
            raise ValueError(f"{saida} não está vazia e não parece uma pasta de dados; não vou apagar")
        shutil.rmtree(saida)
    saida.mkdir(parents=True)


def montar(nacional: Path, saida: Path, cache: Path, lista_cidades: list[dict] | None = None) -> dict:
    util.AVISOS.clear()
    limpar_saida(saida, nacional)
    cont = recorte.recortar(nacional, saida)
    lista = cidades.coletar(saida, cache, lista_cidades)
    meta_f = saida / "meta.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    avisos = list(meta.get("avisos") or [])
    avisos += [a for a in util.AVISOS if a not in avisos]
    meta.update({"recorte": "MG", "avisos": avisos, "cidades": [c["id"] for c in lista]})
    util.write_json(meta_f, meta)
    cont["cidades"] = len(lista)
    log.info("Minas Nossa: %s", cont)
    return cont


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nacional", type=Path, required=True, help="pasta de dados do Segredos Abertos nacional")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path(".cache"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(json.dumps(montar(a.nacional, a.saida, a.cache), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
