"""Página da cidade: quem governou, quem legislou, por partido, e como a cidade votou."""
import json

import pytest
from hypothesis import given, settings, strategies as st

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE
from faketse import FakeTSE
from mg_etl import cidades, partidos_hist, tse
from mg_etl.validar import conferir_cidades
from sa_etl import util
from sa_etl.validar import Resultado


def _municipais(fake: FakeTSE, anos):
    out = {}
    for a in anos:
        vot, cand = fake.municipal(a)
        out[a] = (vot, cand)
    return out


def _montar(fake=None, anos=(2016, 2020, 2024), ger=(2018, 2022)):
    fake = fake or FakeTSE()
    return fake, cidades.montar_cidade(CIDADES_TESTE[0], _municipais(fake, anos), {a: fake.geral(a) for a in ger})


def test_prefeito_vice_e_mandato():
    fake, d = _montar()
    m = d["executivo"][0]
    esp = fake.esperado[("ITAJUBÁ", 2024)]
    assert (m["eleicao"], m["inicio"], m["fim"]) == (2024, 2025, 2028)
    assert m["prefeito"]["nome"] == esp["prefeito"] and m["prefeito"]["partido"] == esp["partido"]
    assert m["prefeito"]["votos"] == pytest.approx(esp["votos"], abs=2)  # somado das duas zonas
    assert m["vice"]["nome"] == esp["vice"], "o vice com registro indeferido não pode entrar"
    assert sum(c["pct"] for c in m["candidatos"]) == pytest.approx(100, abs=0.05)


def test_mais_novo_primeiro():
    _, d = _montar()
    assert [m["eleicao"] for m in d["executivo"]] == [2024, 2020, 2016]
    assert [c["eleicao"] for c in d["camara"]] == [2024, 2020, 2016]
    assert [g["eleicao"] for g in d["gerais"]] == [2022, 2018]


def test_eleicao_suplementar_nao_vira_mandato():
    fake, d = _montar(anos=(2008,))
    assert d["executivo"][0]["prefeito"]["nome"] == fake.esperado[("ITAJUBÁ", 2008)]["prefeito"]
    assert all(c["nome"] != "Suplementar Fulano" for c in d["executivo"][0]["candidatos"])


def test_camara_cadeiras_somam_as_vagas_e_inclui_eleito_por_media_antigo():
    _, d = _montar(anos=(2000, 2024))
    for c in d["camara"]:
        assert c["vagas"] == 9 == len(c["eleitos"]) == sum(x["cadeiras"] for x in c["por_partido"])


def test_partido_antigo_aparece_com_o_nome_de_hoje():
    _, d = _montar(anos=(2000,))
    p = d["executivo"][0]["prefeito"]
    assert p["partido"] in ("PMDB", "PFL", "PSDB", "PT", "PPB", "PL", "PTB", "PCdoB")
    assert p["partido_hoje"] == partidos_hist.hoje(p["partido"], 2000)["sigla"]


@pytest.mark.parametrize("sigla,ano,hoje", [
    ("PMDB", 2000, "MDB"), ("PFL", 1996, "UNIÃO"), ("DEM", 2016, "UNIÃO"), ("PSL", 2018, "UNIÃO"), ("PPB", 2000, "PP"),
    ("PR", 2012, "PL"), ("PL", 2000, "PL"), ("PRB", 2016, "REPUBLICANOS"), ("PPS", 2008, "CIDADANIA"), ("PTN", 2012, "PODE"),
    ("PT do B", 2008, "AVANTE"), ("PTdoB", 2012, "AVANTE"), ("PC do B", 2000, "PCdoB"), ("PPL", 2016, "PCdoB"),
    ("PSD", 2000, "PRD"), ("PSD", 2016, "PSD"), ("PTB", 2020, "PRD"), ("PT", 1996, "PT"), ("PSDB", 1996, "PSDB"),
    ("PROS", 2020, "SOLIDARIEDADE"), ("PMN", 2004, "MOBILIZA"),
])
def test_linhagem_dos_partidos(sigla, ano, hoje):
    h = partidos_hist.hoje(sigla, ano)
    assert h["sigla"] == hoje
    assert (h["mudou"] is None) == (partidos_hist.chave(sigla) == partidos_hist.chave(hoje) and not (sigla == "PL" and ano < 2006))


def test_resumo_junta_pmdb_e_mdb():
    exe = [{"inicio": 2001, "fim": 2004, "prefeito": {"partido": "PMDB", "partido_hoje": "MDB"}},
           {"inicio": 2021, "fim": 2024, "prefeito": {"partido": "MDB", "partido_hoje": "MDB"}},
           {"inicio": 2025, "fim": 2028, "prefeito": {"partido": "PT", "partido_hoje": "PT"}}]
    r = cidades.resumo(exe, [])
    assert r["anos_por_partido"][0] == {"partido": "MDB", "anos": 8, "siglas": ["PMDB", "MDB"]}


def test_coligacao_com_federacao_e_barras():
    r = {"DS_COMPOSICAO_COLIGACAO": "Federação PT/PC do B/PV / PSB", "SG_PARTIDO": "PT"}
    assert cidades._partidos_coligacao(r) == ["PT", "PCdoB", "PV", "PSB"]
    assert cidades._partidos_coligacao({"DS_COMPOSICAO_COLIGACAO": "#NULO#", "SG_PARTIDO": "PSD"}) == ["PSD"]


def test_votos_validos_quando_existem():
    assert cidades._votos({"QT_VOTOS_NOMINAIS": "500", "QT_VOTOS_NOMINAIS_VALIDOS": "0"}) == 0
    assert cidades._votos({"QT_VOTOS_NOMINAIS": "500", "QT_VOTOS_NOMINAIS_VALIDOS": "#NULO#"}) == 500
    assert cidades._votos({"QT_VOTOS_NOMINAIS": "500"}) == 500


def test_como_a_cidade_votou_mostra_os_mais_votados():
    _, d = _montar(ger=(2022,))
    cargos = {(c["cargo"], c["turno"]) for c in d["gerais"][0]["cargos"]}
    assert {("Presidente", 1), ("Presidente", 2), ("Governador", 1), ("Deputado Federal", 1)} <= cargos
    dep = next(c for c in d["gerais"][0]["cargos"] if c["cargo"] == "Deputado Federal")
    assert len(dep["candidatos"]) == cidades.TOP_PROP and dep["n_candidatos"] == 14


def test_ano_sem_dados_do_tse_vira_aviso_na_pagina():
    fake = FakeTSE()
    mun = _municipais(fake, (2016, 2024))
    mun[2020] = (None, None)
    d = cidades.montar_cidade(CIDADES_TESTE[0], mun, {})
    assert [m["eleicao"] for m in d["executivo"]] == [2024, 2016]
    assert any("2020" in a for a in d["avisos"])


def test_sem_lista_de_candidatos_o_vice_fica_sem_nome():
    fake = FakeTSE()
    vot, _ = fake.municipal(2024)
    d = cidades.montar_cidade(CIDADES_TESTE[0], {2024: (vot, None)}, {})
    assert d["executivo"][0]["vice"] is None and d["executivo"][0]["prefeito"]["nome"]


def test_coletar_escreve_as_paginas_e_passa_na_conferencia(gov_tse, tmp_path, monkeypatch):
    monkeypatch.setattr(cidades.tse, "anos_ate", lambda hoje=None: ([2016, 2020, 2024], [2018, 2022]))
    lista = cidades.coletar(tmp_path / "saida", tmp_path / "cache", CIDADES_TESTE)
    assert [c["id"] for c in lista] == ["itajuba", "paraisopolis"]
    assert lista[0]["desde"] == 2025 and lista[0]["vereadores"] == 9
    r = Resultado()
    conferir_cidades(tmp_path / "saida", r, MINIMOS_TESTE["mandatos"])
    assert r.erros == []
    texto = "".join(f.read_text(encoding="utf-8") for f in (tmp_path / "saida").rglob("*.json"))
    assert "12345678909" not in texto


# ---------------------------------------------------------------- propriedades

@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.sampled_from(["PT", "PL", "MDB", "PSD", "NOVO"]), st.integers(0, 5000), st.booleans()),
                min_size=1, max_size=25))
def test_camara_sempre_bate_cadeiras_e_percentuais(cands):
    rows = []
    for i, (partido, votos, eleito) in enumerate(cands):
        rows.append({"DS_CARGO": "VEREADOR", "NR_TURNO": "1", "SQ_CANDIDATO": str(i), "NM_CANDIDATO": f"C{i}", "SG_PARTIDO": partido,
                     "QT_VOTOS_NOMINAIS": str(votos), "DS_SIT_TOT_TURNO": "ELEITO POR QP" if eleito else "SUPLENTE"})
    c = cidades.camara(2024, rows, ["PT", "PL"], "PT")
    if not any(e for *_, e in cands):
        assert c is None
        return
    assert c["vagas"] == sum(x["cadeiras"] for x in c["por_partido"]) == len(c["eleitos"])
    assert 0 <= c["do_partido_do_prefeito"] <= c["da_coligacao_do_prefeito"] <= c["vagas"]
    turnos = cidades.candidatos(rows, "VEREADOR")
    total = sum(x["votos"] for x in turnos[1])
    if total:
        assert sum(x["pct"] for x in turnos[1]) == pytest.approx(100, abs=0.01 * len(cands) + 0.01)


@settings(max_examples=40, deadline=None)
@given(st.sampled_from([1996, 2000, 2004, 2008, 2012, 2016, 2020, 2024]), st.integers(0, 50))
def test_cidade_inteira_passa_na_conferencia(ano, seed):
    fake = FakeTSE(seed=seed)
    d = cidades.montar_cidade(CIDADES_TESTE[1], _municipais(fake, [ano]), {})
    r = Resultado()
    from mg_etl import validar as V
    V._conferir_cidade(json.loads(json.dumps(d)), r, 1)
    assert r.erros == []


def test_chave_e_tse_combinam():
    assert tse.chave_cidade(CIDADES_TESTE[0]["nome"]) == tse.chave_cidade("ITAJUBÁ")
    assert util.norm_name("Itajubá") == "ITAJUBA"


def test_valores_nulos_do_tse_nao_viram_nome():
    assert cidades._nome({"NM_URNA_CANDIDATO": "#NULO#", "NM_CANDIDATO": "MARIA DA SILVA"}) == "Maria da Silva"
    assert cidades._nome({"NM_URNA_CANDIDATO": "#NE#", "NM_CANDIDATO": "#NULO#"}) == ""
    assert cidades._coligacao_nome({"NM_COLIGACAO": "#NULO#"}) == ""
