import json
import logging
from pathlib import Path

import pytest

from fakegov import FakeGov, instalar
from sa_etl import build, pagamentos, util
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
        util.reiniciar_quedas()  # cada coleta é um processo novo no GitHub Actions
        saida = self.tmp / f"saida{self.n}"
        anos = list(anos)
        pag = build.pagamentos_emendas(anos, self.cache, 5) if com_emendas else None
        dados = build.coletar(anos, self.cache, max_empresas=200, com_recursos=False, cnpjs_emendas=pagamentos.cnpjs_empresas(pag))
        if com_emendas:
            build.juntar_emendas(dados, anos, self.cache, saida, pag)
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
    util.reiniciar_quedas()
    logging.getLogger("sa_etl").setLevel(logging.WARNING)
    return Coleta(tmp_path, monkeypatch)
