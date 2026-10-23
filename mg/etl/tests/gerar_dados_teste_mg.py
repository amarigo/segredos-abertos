"""Gera os dados do Minas Nossa a partir dos dados nacionais de teste e do TSE simulado, para os testes de
navegador do site de MG (site/e2e/mg.spec.ts).

Uso (de dentro de mg/etl):
    python ../../etl/tests/gerar_dados_teste.py ../../site/public/data
    PYTHONPATH=../../etl:../../etl/tests python tests/gerar_dados_teste_mg.py ../../site/public/data ../../site/public-mg/data
"""
import datetime as dt
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "etl"))

import requests  # noqa: E402

from fakeestado import FakeEstado  # noqa: E402
from mg_etl import almg, build, cidades, tse  # noqa: E402
from sa_etl import emendas as emendas_nac  # noqa: E402
from mg_etl.validar import validar  # noqa: E402


def main(nacional: Path, saida: Path) -> None:
    logging.basicConfig(level=logging.WARNING)
    fake = FakeEstado()  # ALMG, Dados MG, Tesouro e o TSE simulados
    requests.Session.request = lambda self, method, url, params=None, **kw: fake.responder(method.upper(), url, params)
    import time
    time.sleep = lambda s: None
    almg.ORCAMENTO_VERBA = 100_000
    anos = tse.anos_ate(dt.date(2026, 10, 22))
    cidades.tse.anos_ate = lambda hoje=None: anos
    lista = [{**c, "links": c["links"][:1]} for c in cidades.CIDADES]
    with tempfile.TemporaryDirectory() as cache:
        nac = Path(cache) / "nacional"
        fake.emendas_federais_zip(emendas_nac.zip_no_cache(nac))
        build.montar(nacional, saida, Path(cache), lista, cache_nacional=nac)
    r = validar(saida, minimos={"camara": 1, "senado": 1, "votacoes": 1, "mandatos": 1})
    assert r.ok, r.erros
    print(f"Dados de teste do Minas Nossa em {saida}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
