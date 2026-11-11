"""Gera os arquivos do site a partir do FakeGov (dados fictícios), para os testes de navegador (site/e2e).

Uso: python tests/gerar_dados_teste.py ../site/public/data
"""
import logging
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from fakegov import FakeGov  # noqa: E402
from sa_etl import build, representantes  # noqa: E402
from sa_etl.validar import validar  # noqa: E402


def main(saida: Path) -> None:
    logging.basicConfig(level=logging.WARNING)
    gov = FakeGov(anos=(2025,))
    requests.Session.request = lambda self, method, url, params=None, **kw: gov.responder(
        method.upper(), url, params, headers={**self.headers, **(kw.get("headers") or {})})
    representantes.MIN_CIDADES = 1  # o TSE fictício tem só algumas cidades
    import time
    time.sleep = lambda s: None
    with tempfile.TemporaryDirectory() as cache:
        build.executar([2025], Path(cache), saida, max_empresas=200, minutos_pagamentos=5, minutos_gerais=5)
        # Punições oficiais de novo, agora com a chave da API do Portal (CEIS, CNEP e CEAF simulados); sem ela, só o TCU.
        # A chave entra só aqui para não mudar o caminho da renúncia fiscal (que também usa a API) nos dados de teste.
        import os
        from sa_etl import sancoes
        os.environ["PORTAL_TRANSPARENCIA_CHAVE"] = gov.api_chave
        try:
            sancoes.coletar(saida, Path(cache))
        finally:
            os.environ.pop("PORTAL_TRANSPARENCIA_CHAVE", None)
    r = validar(saida, minimos={"camara": 1, "senado": 1, "votacoes": 1})
    assert r.ok, r.erros
    print(f"Dados de teste em {saida}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
