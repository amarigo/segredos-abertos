"""Arquivos do TSE (tse.py) e patrimônio declarado (patrimonio.py)."""
import datetime as dt
import gzip
import json

import pytest

import fakegov_candidatos
from fakegov import FakeGov, instalar
from sa_etl import patrimonio, tse, util
from sa_etl.validar import Resultado, _conferir_patrimonio

HOJE = dt.date(2026, 11, 10)


@pytest.fixture
def gov(monkeypatch):
    util.AVISOS.clear()
    tse._PACOTE.clear()
    return instalar(monkeypatch, FakeGov(n_dep=6, n_sen=3))


def test_pacote_com_outro_nome_e_achado_pela_busca_da_api(gov):
    assert tse.url("cand", 2020).endswith("/consulta_cand/consulta_cand_2020.zip")
    assert tse.pacote(2020) == "candidatos-2020-subtemas"
    assert tse.pacote(2024) == "candidatos-2024"


def test_cache_nao_guarda_cpf_email_nem_descricao_do_bem(gov, tmp_path):
    cands = tse.candidatos(2024, tmp_path)
    tse.bens(2024, tmp_path)
    for f in (tmp_path / "tse").glob("*.gz"):
        texto = gzip.open(f, "rt", encoding="utf-8").read()
        for proibido in (fakegov_candidatos.CPF_FALSO, fakegov_candidatos.EMAIL_FALSO, "RUA FICTICIA", "012345678901"):
            assert proibido not in texto, (f.name, proibido)
    assert {c["uf"] for c in cands} >= {"SP", "MG"}
    assert not list(tmp_path.rglob("*.zip"))  # o ZIP é apagado depois de lido
    n = gov.tse.pedidos_cdn
    tse.candidatos(2024, tmp_path)  # o cache vale 30 dias
    assert gov.tse.pedidos_cdn == n


def test_fonte_fora_do_ar_usa_a_copia_e_avisa(gov, tmp_path):
    tse.candidatos(2022, tmp_path)
    f = tmp_path / "tse" / "cand-2022.json.gz"
    velho = f.stat().st_mtime - 40 * 86400
    import os
    os.utime(f, (velho, velho))
    gov.falhar("cdn.tse.jus.br", "500")
    assert tse.candidatos(2022, tmp_path)
    assert any("TSE não respondeu" in a for a in util.AVISOS)


def test_patrimonio_liga_cada_parlamentar_pelo_nome_e_nascimento(gov, tmp_path):
    pols = [{"id": f"dep-{d['id']}", "nome": d["nome"], "casa": "camara", "uf": d["siglaUf"]} for d in gov.deputados]
    pols += [{"id": f"sen-{s['cod']}", "nome": s["nome"], "casa": "senado", "uf": s["uf"]} for s in gov.senadores]
    pols.append({"id": "dep-999", "nome": "Sem Registro", "casa": "camara"})
    saida = tmp_path / "saida"
    out = patrimonio.coletar(saida, tmp_path / "cache", pols, HOJE)
    assert out["anos"] == [2014, 2016, 2018, 2020, 2022, 2024, 2026]
    assert len(out["politicos"]) == 9 and out["sem_registro"] == 1
    p = json.loads((saida / "pat" / "dep-1000.json").read_text())
    anos = [d["ano"] for d in p["declaracoes"]]
    assert anos == [2014, 2016, 2018, 2020, 2022, 2024, 2026]  # o 1º também foi candidato a prefeito
    assert p["declaracoes"][0]["cargo"] == "Deputado Federal" and p["declaracoes"][1]["cargo"] == "Prefeito"
    assert all(d["principal"] for d in p["declaracoes"])
    res = Resultado()
    _conferir_patrimonio(saida, res)
    assert res.erros == [] and res.alertas == []
    texto = "".join(f.read_text() for f in (saida / "pat").glob("*.json"))
    assert fakegov_candidatos.CPF_FALSO not in texto and "RUA FICTICIA" not in texto


def test_salto_de_patrimonio_e_marcado():
    ds = [{"ano": 2022, "resultado": "Eleito", "total": 250000.0}, {"ano": 2026, "resultado": "Eleito", "total": 250_000_000.0},
          {"ano": 2026, "resultado": "", "total": 1.0}]
    patrimonio.marcar(ds)
    assert ds[1]["salto"] and ds[1]["principal"] and not ds[2]["principal"]


def test_coleta_inteira_grava_patrimonio(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    pat = coleta.ler(saida, "patrimonio.json")
    assert pat["politicos"] and pat["sem_registro"] == 0
    assert coleta.validar(saida).ok
