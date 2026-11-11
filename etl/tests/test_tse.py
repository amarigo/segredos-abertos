"""Arquivos do TSE (tse.py), patrimônio declarado (patrimonio.py) e eleitos de estados e cidades (eleitos.py)."""
import datetime as dt
import gzip
import json

import pytest

import fakegov_candidatos
from fakegov import FakeGov, instalar
from sa_etl import eleitos, patrimonio, tse, util
from sa_etl.validar import Resultado, _conferir_eleitos, _conferir_patrimonio

HOJE = dt.date(2026, 11, 10)


@pytest.fixture
def gov(monkeypatch):
    util.AVISOS.clear()
    tse._PACOTE.clear()
    return instalar(monkeypatch, FakeGov(n_dep=6, n_sen=3))


def _c(**kw):
    base = {"ano": 2024, "tipo": "ord", "turno": 1, "data": "2024-10-06", "eleicao": "", "uf": "MG", "ue": "1",
            "nm_ue": "CIDADE", "cargo": "VEREADOR", "sq": "1", "nr": "1", "nome": "X", "urna": "X", "partido": "PT",
            "nasc": "", "situacao": "", "resultado": "ELEITO POR QP"}
    return {**base, **kw}


def test_mandato_atual():
    anos = list(range(2016, 2100, 4))
    assert eleitos.mandato_atual(anos, dt.date(2024, 12, 31)) == 2020  # o mandato de 2024 começa em 2025
    assert eleitos.mandato_atual(anos, dt.date(2025, 1, 1)) == 2024


def test_suplementar_troca_o_prefeito_e_o_segundo_turno_vale():
    cands = [_c(cargo="PREFEITO", sq="1", resultado="2º TURNO"), _c(cargo="PREFEITO", sq="1", turno=2, resultado="ELEITO"),
             _c(cargo="PREFEITO", sq="2", resultado="NÃO ELEITO"),
             _c(cargo="PREFEITO", sq="3", tipo="sup", data="2025-06-01", resultado="ELEITO")]
    lug = eleitos.eleitos_por_lugar(cands, eleitos.CARGOS_CIDADE)[("MG", "1")]
    assert [c["sq"] for c in lug["prefeito"]] == ["3"] and lug["suplementar"] == {"prefeito": "2025-06-01"}


def test_suplementar_de_uma_cadeira_nao_apaga_os_outros_vereadores():
    cands = [_c(sq=str(i)) for i in range(9)] + [_c(sq="99", tipo="sup", data="2025-12-07")]
    lug = eleitos.eleitos_por_lugar(cands, eleitos.CARGOS_CIDADE)[("MG", "1")]
    assert len(lug["vereadores"]) == 10 and lug["suplementar_parcial"] == {"vereadores": "2025-12-07"}
    p = eleitos._montar_lugar(lug, {}, com_tipos=False)
    assert [v["suplementar"] for v in p["vereadores"] if v.get("suplementar")] == ["2025-12-07"]


def test_cargo_sem_eleito_no_tse_fica_marcado():
    """Resultado "#NULO" (anulado ou em julgamento) ou só "NÃO ELEITO": o site diz que não há eleito, não inventa."""
    cands = [_c(sq="1", resultado="#NULO"), _c(sq="2", resultado="#NULO"),
             _c(cargo="PREFEITO", sq="3", resultado="NÃO ELEITO"), _c(cargo="VICE-PREFEITO", sq="4", resultado="NÃO ELEITO")]
    lug = eleitos.eleitos_por_lugar(cands, eleitos.CARGOS_CIDADE)[("MG", "1")]
    assert lug["sem_eleito"] == ["prefeito", "vice", "vereadores"] and "vereadores" not in lug


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
    assert {c["uf"] for c in cands} == {"SP", "MG"}
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


def test_eleitos_de_estados_e_cidades(gov, tmp_path):
    saida = tmp_path / "saida"
    r = eleitos.coletar(saida, tmp_path / "cache", HOJE)
    assert r["estados"] == {"ano": 2022, "ufs": 2}
    e = json.loads((saida / "eleitos" / "estados.json").read_text())
    mg = e["ufs"]["MG"]
    assert [g["nome"] for g in mg["governador"]] == ["GOV MG"] and mg["governador"][0]["resultado"] == "Eleito"
    assert len(mg["deputados"]) == mg["vagas"] == fakegov_candidatos.VAGAS_DEP
    assert mg["governador"][0]["tipos"][0] == {"tipo": "Apartamento", "valor": 500000.0}
    assert mg["vice"][0]["sem_bens"] is True and e["proxima"]  # a eleição de 2026 já aconteceu
    assert e["fonte"] == "https://dadosabertos.tse.jus.br/dataset/candidatos-2022"
    cid = {c["nome"]: c for c in json.loads((saida / "eleitos" / "cidades" / "MG.json").read_text())["cidades"]}
    assert cid["Belo Horizonte"]["prefeito"][0]["nome"] == "Pref Novo" and cid["Belo Horizonte"]["suplementar"]
    assert cid["Mercês"]["sem_eleito"] == ["prefeito", "vice"] and len(cid["Mercês"]["vereadores"]) == 3
    sp = {c["nome"]: c for c in json.loads((saida / "eleitos" / "cidades" / "SP.json").read_text())["cidades"]}
    assert sp["Campinas"]["sem_eleito"] == ["vereadores"]
    assert len(sp["São Paulo"]["vereadores"]) == 4 and sp["São Paulo"]["suplementar_parcial"]
    i = json.loads((saida / "eleitos" / "indice.json").read_text())
    assert i["prefeitos"] == 3 and i["vereadores"] == 3 + 4 + 3 and i["sem_eleito"] == 2 and len(i["cidades"]) == 4
    res = Resultado()
    _conferir_eleitos(saida, res)
    assert res.erros == [] and res.alertas == []


def test_validacao_acusa_cpf_e_indice_errado(gov, tmp_path):
    saida = tmp_path / "saida"
    eleitos.coletar(saida, tmp_path / "cache", HOJE)
    f = saida / "eleitos" / "cidades" / "MG.json"
    d = json.loads(f.read_text())
    d["cidades"][0]["prefeito"][0]["cpf"] = "12345678901"
    d["cidades"][0]["vereadores"].pop()
    f.write_text(json.dumps(d))
    res = Resultado()
    _conferir_eleitos(saida, res)
    assert any("Dado pessoal" in e for e in res.erros) and any("índice" in e for e in res.erros)
    assert any("diferente das vagas" in a for a in res.alertas)


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


def test_coleta_inteira_grava_patrimonio_e_eleitos(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    pat = coleta.ler(saida, "patrimonio.json")
    assert pat["politicos"] and pat["sem_registro"] == 0
    assert coleta.ler(saida, "eleitos/indice.json")["cidades"]
    assert coleta.validar(saida).ok
