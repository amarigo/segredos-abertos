"""Recorte de MG dos dados nacionais e montagem completa (meio e topo da pirâmide no coletor)."""
import json
import random

import pytest

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE
from mg_etl import build, cidades, recorte
from mg_etl import validar as V
from sa_etl import util


def ler(saida, rel):
    return json.loads((saida / rel).read_text(encoding="utf-8"))


@pytest.fixture
def mg(nac, tmp_path):
    saida = tmp_path / "mg"
    recorte.recortar(nac, saida)
    return nac, saida


def test_so_politicos_de_mg(mg):
    nac, saida = mg
    pols = ler(saida, "politicos.json")
    esperado = [p["id"] for p in ler(nac, "politicos.json") if p["uf"] == "MG"]
    assert [p["id"] for p in pols] == esperado and esperado
    assert {p["casa"] for p in pols} == {"camara", "senado"}
    assert sorted(f.stem for f in (saida / "p").glob("*.json")) == sorted(esperado)


def test_votacao_mostra_bancada_de_mg_e_placar_da_casa(mg):
    nac, saida = mg
    ids = {p["id"] for p in ler(saida, "politicos.json")}
    for v in ler(saida, "votacoes.json"):
        d, n = ler(saida, f"v/{v['id']}.json"), ler(nac, f"v/{v['id']}.json")
        assert {x["politico"] for x in d["votos"]} <= ids
        assert d["placar_casa"] == {"sim": n["sim"], "nao": n["nao"], "contagem": n["contagem"]}
        assert v["placar_casa"] == {"sim": n["sim"], "nao": n["nao"]}
        assert d["sim"] == sum(1 for x in d["votos"] if x["voto"] == "Sim") <= n["sim"]
        por_partido = {}
        for x in d["votos"]:
            por_partido.setdefault(x["partido"], {}).setdefault(x["voto"], 0)
            por_partido[x["partido"]][x["voto"]] += 1
        assert d["por_partido_mg"] == por_partido
        assert d["por_partido"] == n["por_partido"], "o quadro por partido continua sendo o da Casa inteira"


def test_votacao_sem_ninguem_de_mg_fica_de_fora(mg):
    nac, saida = mg
    ids = {p["id"] for p in ler(saida, "politicos.json")}
    fora = [v["id"] for v in ler(nac, "votacoes.json") if not any(x["politico"] in ids for x in ler(nac, f"v/{v['id']}.json")["votos"])]
    assert not set(fora) & {v["id"] for v in ler(saida, "votacoes.json")}


def test_empresas_so_com_o_que_mg_pagou(mg):
    nac, saida = mg
    ids = {p["id"] for p in ler(saida, "politicos.json")}
    emps = ler(saida, "empresas.json")
    assert emps and [e["total"] for e in emps] == sorted((e["total"] for e in emps), reverse=True)
    for e in emps:
        d = ler(saida, f"e/{e['cnpj']}.json")
        assert {x["politico"] for x in d["pagadores"]} <= ids
        assert d["total"] == pytest.approx(sum(x["valor"] for x in d["pagadores"]), abs=0.02)
        assert d["mesmo_endereco"] == [] and all(s["outras_empresas"] == [] for s in d["socios"])
        notas = [n for a in d["notas_por_ano"] for n in ler(saida, f"e/notas/{e['cnpj']}-{a}.json")]
        assert len(notas) == d["n_notas"] and {n[1] for n in notas} <= ids


def test_recorte_passa_na_conferencia_nacional_e_na_de_mg(mg):
    _, saida = mg
    (saida / "cidades.json").write_text("[]", encoding="utf-8")
    r = V.validar(saida, minimos=MINIMOS_TESTE)
    assert r.erros == []


def test_sem_ninguem_de_mg_para_tudo(nac, tmp_path):
    pols = ler(nac, "politicos.json")
    (nac / "politicos.json").write_text(json.dumps([p for p in pols if p["uf"] != "MG"]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Nenhum político de MG"):
        recorte.recortar(nac, tmp_path / "mg")


# ---------------------------------------------------------------- montagem completa

@pytest.fixture
def anos_curtos(monkeypatch):
    monkeypatch.setattr(cidades.tse, "anos_ate", lambda hoje=None: ([2016, 2020, 2024], [2018, 2022]))


def test_montagem_completa_passa_na_conferencia(nac, tmp_path, gov_tse, anos_curtos):
    saida = tmp_path / "mg"
    cont = build.montar(nac, saida, tmp_path / "cache", CIDADES_TESTE)
    assert cont["cidades"] == 2
    r = V.validar(saida, minimos=MINIMOS_TESTE)
    assert r.erros == []
    meta = ler(saida, "meta.json")
    assert meta["recorte"] == "MG" and meta["cidades"] == ["itajuba", "paraisopolis"]


def test_saida_e_refeita_do_zero(nac, tmp_path, gov_tse, anos_curtos):
    saida = tmp_path / "mg"
    build.montar(nac, saida, tmp_path / "cache", CIDADES_TESTE)
    (saida / "p" / "camara-velho.json").write_text("{}", encoding="utf-8")
    build.montar(nac, saida, tmp_path / "cache", CIDADES_TESTE)
    assert not (saida / "p" / "camara-velho.json").exists()


def test_nao_apaga_pasta_que_nao_e_de_dados(nac, tmp_path, gov_tse):
    outra = tmp_path / "documentos"
    outra.mkdir()
    (outra / "importante.txt").write_text("não apague", encoding="utf-8")
    with pytest.raises(ValueError):
        build.montar(nac, outra, tmp_path / "cache", CIDADES_TESTE)
    assert (outra / "importante.txt").exists()
    with pytest.raises(ValueError):
        build.montar(nac, nac, tmp_path / "cache", CIDADES_TESTE)


# ---------------------------------------------------------------- caos: TSE instável

def test_tse_fora_do_ar_na_primeira_vez_bloqueia_a_publicacao(nac, tmp_path, gov_tse, anos_curtos):
    """Sem nenhuma cópia, a cidade fica sem prefeitos: a conferência barra e o site publicado continua no ar."""
    gov_tse.falhar("odsele", "fora")
    saida = tmp_path / "mg"
    build.montar(nac, saida, tmp_path / "cache", CIDADES_TESTE)
    meta = ler(saida, "meta.json")
    assert any("TSE" in a for a in meta["avisos"])
    r = V.validar(saida, minimos=MINIMOS_TESTE)
    assert any("mandatos de prefeito" in e for e in r.erros)


def test_tse_fora_do_ar_depois_usa_o_cache_sem_aviso(nac, tmp_path, gov_tse, anos_curtos):
    cache = tmp_path / "cache"
    build.montar(nac, tmp_path / "a", cache, CIDADES_TESTE)
    gov_tse.falhar("odsele", "fora")
    build.montar(nac, tmp_path / "b", cache, CIDADES_TESTE)
    for c in ("itajuba", "paraisopolis"):
        assert ler(tmp_path / "a", f"cidades/{c}.json") == ler(tmp_path / "b", f"cidades/{c}.json")
    assert V.validar(tmp_path / "b", minimos=MINIMOS_TESTE).erros == []


@pytest.mark.parametrize("rodada", range(12))
def test_caos_falhas_aleatorias_nunca_publicam_dado_errado(nac, tmp_path, gov_tse, anos_curtos, rodada):
    """Cada rodada derruba ou corrompe arquivos do TSE ao acaso. Ou a cidade sai certa, ou o ano some com aviso."""
    rng = random.Random(rodada)
    modos = ["fora", "html", "cortado", "vazio", "sem_cabecalho", "sem_coluna", "sem_cidade"]
    caidos = set()
    for ano in (2016, 2018, 2020, 2022, 2024):
        for tipo in ("munzona", "consulta_cand") if ano % 4 == 0 else ("munzona",):  # candidatos: só nas municipais
            if rng.random() < 0.35:
                gov_tse.falhar(f"{tipo}_{ano}", rng.choice(modos))
                caidos.add((tipo, ano))
    saida = tmp_path / "mg"
    build.montar(nac, saida, tmp_path / "cache", CIDADES_TESTE)
    r = V.validar(saida, minimos={**MINIMOS_TESTE, "mandatos": 0})
    assert r.erros == [], (caidos, r.erros)
    meta = ler(saida, "meta.json")
    d = ler(saida, "cidades/itajuba.json")
    for tipo, ano in caidos:
        assert any(str(ano) in a for a in meta["avisos"]), (tipo, ano, meta["avisos"])
        if tipo == "munzona" and ano % 4 == 0:
            assert ano not in [m["eleicao"] for m in d["executivo"]]
            assert any(str(ano) in a for a in d["avisos"])
        if tipo == "consulta_cand" and ("munzona", ano) not in caidos and ano % 4 == 0:
            m = next(m for m in d["executivo"] if m["eleicao"] == ano)
            assert m["vice"] is None
    assert not util.AVISOS or set(util.AVISOS) <= set(meta["avisos"])
