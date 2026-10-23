"""Base dos testes do Minas Nossa.

- `nacional`: dados do Segredos Abertos nacional gerados uma vez com o governo simulado (FakeGov), como na
  execução diária do GitHub Actions. O recorte de MG parte deles.
- `tse`: o TSE simulado (FakeTSE) no lugar da internet.
"""
import logging
import shutil
from pathlib import Path

import pytest

from faketse import FakeTSE, instalar
from mg_etl import tse
from sa_etl import build as build_nac, pagamentos, util

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE  # noqa: E402,F401


@pytest.fixture(scope="session")
def nacional(tmp_path_factory) -> Path:
    from fakegov import FakeGov, instalar as instalar_gov
    saida = tmp_path_factory.mktemp("nacional") / "data"
    cache = tmp_path_factory.mktemp("cache_nacional")
    with pytest.MonkeyPatch.context() as mp:
        instalar_gov(mp, FakeGov(anos=(2025,)))
        util.AVISOS.clear()
        logging.getLogger("sa_etl").setLevel(logging.WARNING)
        pag = build_nac.pagamentos_emendas([2025], cache, 5)
        dados = build_nac.coletar([2025], cache, max_empresas=200, com_recursos=False, cnpjs_emendas=pagamentos.cnpjs_empresas(pag))
        build_nac.juntar_emendas(dados, [2025], cache, saida, pag)
        build_nac.montar(dados, saida, [2025])
    util.AVISOS.clear()
    return saida


@pytest.fixture
def nac(nacional, tmp_path) -> Path:
    """Cópia dos dados nacionais que o teste pode estragar."""
    destino = tmp_path / "nacional"
    shutil.copytree(nacional, destino)
    return destino


@pytest.fixture
def gov_tse(monkeypatch) -> FakeTSE:
    util.AVISOS.clear()
    logging.getLogger("mg_etl").setLevel(logging.ERROR)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return instalar(monkeypatch, FakeTSE())


@pytest.fixture
def estado(monkeypatch):
    """Fontes do estado simuladas (ALMG, Dados MG, Tesouro e TSE) no lugar da internet, com poucas eleições."""
    from fakeestado import FakeEstado, instalar as instalar_estado
    from mg_etl import almg, siconfi
    util.AVISOS.clear()
    logging.getLogger("mg_etl").setLevel(logging.ERROR)
    logging.getLogger("sa_etl").setLevel(logging.ERROR)
    monkeypatch.setattr(tse, "anos_ate", lambda hoje=None: ([2016, 2020, 2024], [2018, 2022]))
    monkeypatch.setattr(almg, "ORCAMENTO_VERBA", 100_000)
    monkeypatch.setattr(almg, "PAUSA_VERBA", 0)
    siconfi._ENTES.clear()
    return instalar_estado(monkeypatch, FakeEstado())
