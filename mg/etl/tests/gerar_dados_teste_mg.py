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

from faketse import FakeTSE  # noqa: E402
from mg_etl import build, cidades, tse  # noqa: E402
from mg_etl.validar import validar  # noqa: E402
from sa_etl import util  # noqa: E402


class _Resp:
    def __init__(self, content: bytes):
        self.content = content


def main(nacional: Path, saida: Path) -> None:
    logging.basicConfig(level=logging.WARNING)
    fake = FakeTSE()
    util.get = lambda url, **kw: _Resp(fake.responder(url))
    anos = tse.anos_ate(dt.date(2026, 10, 22))
    cidades.tse.anos_ate = lambda hoje=None: anos
    lista = [{**c, "links": c["links"][:1]} for c in cidades.CIDADES]
    with tempfile.TemporaryDirectory() as cache:
        build.montar(nacional, saida, Path(cache), lista)
    r = validar(saida, minimos={"camara": 1, "senado": 1, "votacoes": 1, "mandatos": 1})
    assert r.ok, r.erros
    print(f"Dados de teste do Minas Nossa em {saida}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
