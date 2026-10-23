"""Monta os dados do Minas Nossa.

1. Recorte de MG dos dados nacionais já gerados na mesma execução (deputados federais, senadores, votações,
   empresas, partidos).
2. Histórico das cidades acompanhadas, com os arquivos do TSE.
3. Estado: deputados estaduais (ALMG: verba, proposições), emendas estaduais, governador e vice (TSE), e o
   dinheiro que chega às cidades (emendas federais e estaduais) e onde cada prefeitura gasta (SICONFI).
   Cada fonte é independente: se uma falhar, as outras seguem e o meta.json avisa.
4. Junta os avisos da coleta (fontes fora do ar, cópias antigas em uso) no meta.json, para o site mostrar.

Uso (de dentro de mg/etl, com o coletor nacional no PYTHONPATH):
    PYTHONPATH=../../etl python -m mg_etl.build --nacional ../../site/public/data --saida ../../site/public-mg/data \
        --cache .cache --cache-nacional ../../etl/.cache
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

from sa_etl import emendas as emendas_nac, util

from . import almg, cidades, emendas_federais, emendas_mg, equipe, fontes, governo, recorte, siconfi

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


def montar(nacional: Path, saida: Path, cache: Path, lista_cidades: list[dict] | None = None,
           cache_nacional: Path | None = None, estado: bool = True) -> dict:
    util.AVISOS.clear()
    limpar_saida(saida, nacional)
    cont = recorte.recortar(nacional, saida)
    lista_cidades = lista_cidades or cidades.CIDADES
    lista = cidades.coletar(saida, cache, lista_cidades)
    if estado:
        cont.update(montar_estado(nacional, saida, cache, lista_cidades, cache_nacional))
    meta_f = saida / "meta.json"
    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    avisos = list(meta.get("avisos") or [])
    avisos += [a for a in util.AVISOS if a not in avisos]
    meta.update({"recorte": "MG", "avisos": avisos, "cidades": [c["id"] for c in lista],
                 "estado": {k: cont.get(k, 0) for k in ("deputados_estaduais", "emendas_estaduais", "governo", "equipe_governo")}})
    util.write_json(meta_f, meta)
    cont["cidades"] = len(lista)
    log.info("Minas Nossa: %s", cont)
    return cont


def _seguro(nome: str, fn, padrao=None):
    """Roda uma parte do estado; se der erro inesperado, avisa e segue com as outras."""
    try:
        return fn()
    except Exception:  # noqa: BLE001
        log.exception("Minas Nossa: erro em %s", nome)
        util.avisar(f"{nome}: erro ao montar os dados; essa parte ficou sem atualização")
        return padrao


def montar_estado(nacional: Path, saida: Path, cache: Path, lista_cidades: list[dict], cache_nacional: Path | None) -> dict:
    cont: dict = {}
    mapa_cidades = {emendas_mg.chave_cidade(c["nome"]): c["id"] for c in lista_cidades}
    deps = _seguro("ALMG (deputados em exercício)", lambda: almg.em_exercicio(cache), [])
    mapa_dep = {fontes.chave_nome(d["nome"]): d["id"] for d in deps}
    em = _seguro("Emendas estaduais (ALMG)", lambda: emendas_mg.coletar(cache, mapa_dep, mapa_cidades))
    if deps:
        feitos = _seguro("Deputados estaduais (ALMG)", lambda: almg.coletar(saida, cache, deps, em), [])
        cont["deputados_estaduais"] = len(feitos or [])
    if em:
        util.write_json(saida / "estado" / "emendas.json", {
            "fonte": emendas_mg.PAGINA, "anos": {str(a): e for a, e in sorted(em["estado"].items())}})
        cont["emendas_estaduais"] = sum(e["n"] for e in em["estado"].values())
    gov = _seguro("Governo de MG (TSE)", lambda: governo.coletar(cache)) or {"eleicoes": [], "links": governo.LINKS,
                                                                            "fonte_tse": governo.FONTE_TSE}
    gov["equipe"] = _seguro("Salários e viagens do governo de MG", lambda: equipe.coletar(cache))
    util.write_json(saida / "estado" / "governo.json", gov)
    cont["governo"] = len(gov["eleicoes"])
    cont["equipe_governo"] = len((gov["equipe"] or {}).get("pessoas") or [])
    ids_mg = {f.stem for f in (saida / "p").glob("*.json")}
    zip_nac = emendas_nac.zip_no_cache(cache_nacional or Path("../../etl/.cache"))
    # None = a fonte falhou (o site diz isso); {} = a fonte respondeu e a cidade não recebeu nada
    fed = _seguro("Emendas federais nas cidades", lambda: emendas_federais.coletar(zip_nac, nacional, mapa_cidades, ids_mg))
    vazio_fed = {"fonte": emendas_federais.PAGINA, "por_ano": [], "favorecidos": [], "autores": []}
    n_dinheiro = 0
    for c in lista_cidades:
        contas = _seguro(f"Contas de {c['nome']} (SICONFI)", lambda c=c: siconfi.contas(c["nome"], c["uf"], cache))
        util.write_json(saida / "cidades" / "dinheiro" / f"{c['id']}.json", {
            "id": c["id"], "nome": c["nome"],
            "estaduais": {"fonte": emendas_mg.PAGINA, "lista": em["por_cidade"].get(c["id"], [])} if em else None,
            "federais": (fed.get(c["id"]) or vazio_fed) if fed is not None else None,
            "contas": contas,
        })
        n_dinheiro += 1
    cont["cidades_dinheiro"] = n_dinheiro
    return cont


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nacional", type=Path, required=True, help="pasta de dados do Segredos Abertos nacional")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path(".cache"))
    ap.add_argument("--cache-nacional", type=Path, default=Path("../../etl/.cache"),
                    help="cache do coletor nacional (onde está o arquivo de emendas do Portal da Transparência)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(json.dumps(montar(a.nacional, a.saida, a.cache, cache_nacional=a.cache_nacional), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
