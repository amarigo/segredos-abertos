"""Dinheiro emprestado e dívida paga desde 2018, contra o Tesouro simulado."""
import pytest

import fakegov_financas as ff
from fakegov import FakeGov, instalar
from sa_etl import fin_divida


def test_serie_desde_2018_bimestre_a_bimestre(tmp_path, monkeypatch):
    instalar(monkeypatch, FakeGov())
    d = fin_divida.coletar(tmp_path, ff.ANO)
    anos = [a["ano"] for a in d["anos"]]
    assert anos == list(range(2018, ff.ANO + 1))
    ultimo = d["anos"][-1]
    assert ultimo["parcial"] and ultimo["ate_bimestre"] == 4
    fechado = d["anos"][0]
    assert not fechado["parcial"]
    # o ano fechado traz o valor do relatório do 6º bimestre
    assert fechado["valores"]["novo"] == pytest.approx(ff.RECEITAS["ReceitasDeOperacoesDeCredito"] * ff._fator(2018), rel=1e-6)
    assert fechado["valores"]["juros"] == pytest.approx(ff.DESPESAS["JurosEEncargosDaDivida"] * ff._fator(2018) * 0.98, rel=1e-6)
    # cada bimestre é a diferença entre relatórios: a soma dá o acumulado do ano
    for a in d["anos"]:
        bs = [b for b in d["bimestres"] if b["ano"] == a["ano"]]
        assert len(bs) == a["ate_bimestre"]
        for k, v in a["valores"].items():
            assert sum(b["valores"][k] for b in bs) == pytest.approx(v, abs=1)
    assert all(b["url"].startswith("https://apidatalake.tesouro.gov.br/") for b in d["bimestres"])


def test_tesouro_fora_do_ar_nao_inventa(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov())
    gov.falhar("apidatalake.tesouro.gov.br", "500")
    assert fin_divida.coletar(tmp_path, ff.ANO) is None


def test_pessoas_e_gasto_medio_por_poder(tmp_path, monkeypatch):
    from sa_etl import fin_pessoal
    instalar(monkeypatch, FakeGov())
    ex = fin_pessoal.contar_executivo("chave-de-teste", tmp_path)
    assert (ex["ativos"], ex["aposentados"], ex["pensionistas"]) == (600000, 400000, 200000)
    poderes = [{"poder": "E", "orgaos": [{"nome": "Executivo federal", "ativos": 6e9, "inativos": 3e9}, {"nome": "Polícias, bombeiros, saúde e educação do DF (pagos pela União)", "ativos": 1e9, "inativos": 0}]},
               {"poder": "L", "orgaos": [{"nome": "Câmara dos Deputados", "ativos": 2e9, "inativos": 1e9}, {"nome": "Senado Federal", "ativos": 1e9, "inativos": 1e9},
                                         {"nome": "Tribunal de Contas da União", "ativos": 5e8, "inativos": 1e8}]},
               {"poder": "J", "orgaos": [{"nome": "STF", "ativos": 1e9, "inativos": 1e8}]}]
    camara = {"grupos": [{"pessoas": 15000}], "url": "https://x"}
    senado = {"grupos": [{"pessoas": 5000}]}
    fin_pessoal.pessoas_por_poder(poderes, ex, camara, senado)
    e, l, j = poderes
    assert e["pessoas"]["media_ativo"] == 10000.0 and e["pessoas"]["media_inativo"] == 5000.0
    assert l["pessoas"]["ativos"] == 20000 and l["pessoas"]["media_ativo"] == 150000.0  # sem o TCU nas duas pontas
    assert "pessoas" not in j  # sem fonte oficial aberta: não inventa
