import json
import logging
from pathlib import Path

import pytest

from fakegov import FakeGov, instalar
from sa_etl import build, emendas, util
from sa_etl.validar import validar

MINIMOS_TESTE = {"camara": 1, "senado": 1, "votacoes": 1}


class Coleta:
    """Roda a coleta inteira (como o GitHub Actions) contra o FakeGov e devolve onde ficaram os arquivos."""

    def __init__(self, tmp_path: Path, monkeypatch):
        self.tmp = tmp_path
        self.cache = tmp_path / "cache"
        self.monkeypatch = monkeypatch
        self.gov: FakeGov | None = None
        self.n = 0

    def usar(self, gov: FakeGov) -> FakeGov:
        self.gov = instalar(self.monkeypatch, gov)
        return gov

    def rodar(self, anos=(2025,), com_emendas=True) -> Path:
        assert self.gov, "chame usar(FakeGov(...)) antes"
        self.n += 1
        saida = self.tmp / f"saida{self.n}"
        anos = list(anos)
        dados = build.coletar(anos, self.cache, max_empresas=200, com_recursos=False)
        if com_emendas:
            emendas.coletar(dados["politicos"], anos, self.cache / "emendas", saida)
        build.montar(dados, saida, anos)
        return saida

    @staticmethod
    def ler(saida: Path, rel: str):
        return json.loads((saida / rel).read_text(encoding="utf-8"))

    @staticmethod
    def validar(saida: Path, **kw):
        return validar(saida, minimos=MINIMOS_TESTE, **kw)


@pytest.fixture
def coleta(tmp_path, monkeypatch):
    util.AVISOS.clear()
    logging.getLogger("sa_etl").setLevel(logging.WARNING)
    return Coleta(tmp_path, monkeypatch)
