"""Leitura dos arquivos do TSE (base da pirâmide): formato, colunas, CPF e cache."""
import datetime as dt
import io
import json
import os
import time
import zipfile

import pytest

from faketse import CPF_FALSO, FakeTSE
from mg_etl import tse
from sa_etl import util

ITA = {tse.chave_cidade("Itajubá")}
DUAS = {tse.chave_cidade("Itajubá"), tse.chave_cidade("Paraisópolis")}


def test_le_latin1_e_so_as_colunas_permitidas():
    raw = 'ANO_ELEICAO;NM_MUNICIPIO;NR_CPF_CANDIDATO;DS_EMAIL;SG_PARTIDO\r\n"2024";"ITAJUBÁ";"12345678909";"a@b.c";"PT"\r\n'.encode("latin-1")
    linhas = list(tse.ler_csv(raw))
    assert linhas == [{"ANO_ELEICAO": "2024", "NM_MUNICIPIO": "ITAJUBÁ", "SG_PARTIDO": "PT"}]


def test_le_de_arquivo_aberto_linha_a_linha():
    raw = b'ANO_ELEICAO;SG_PARTIDO\n"2024";"PT"\n"2024";"PL"\n'
    assert [r["SG_PARTIDO"] for r in tse.ler_csv(io.BytesIO(raw))] == ["PT", "PL"]


def test_sem_cabecalho_falha_em_vez_de_adivinhar_colunas():
    with pytest.raises(ValueError, match="cabeçalho"):
        list(tse.ler_csv(b'"2024";"ITAJUBA";"PT"\n'))


def test_coluna_obrigatoria_faltando_falha():
    with pytest.raises(ValueError, match="DS_CARGO"):
        list(tse.ler_csv(b"ANO_ELEICAO;SG_PARTIDO\n2024;PT\n", tse.OBRIGATORIAS["votacao"]))


def test_linha_cortada_e_ignorada():
    raw = b"ANO_ELEICAO;SG_PARTIDO;NM_MUNICIPIO\n2024;PT;ITAJUBA\n2024;PL\n"
    assert len(list(tse.ler_csv(raw))) == 1


def test_chave_da_cidade_ignora_acento_caixa_e_espaco():
    assert tse.chave_cidade("Itajubá") == tse.chave_cidade("ITAJUBA") == tse.chave_cidade(" itajubá ")
    assert tse.chave_cidade("Paraisópolis") == tse.chave_cidade("PARAISOPOLIS")
    assert tse.chave_cidade("Pouso Alegre") == tse.chave_cidade("POUSO  ALEGRE")


@pytest.mark.parametrize("hoje,mun,ger", [
    (dt.date(2024, 10, 31), 2020, 2022),  # eleição de outubro ainda não conta
    (dt.date(2024, 11, 1), 2024, 2022),
    (dt.date(2026, 10, 22), 2024, 2022),
    (dt.date(2026, 11, 2), 2024, 2026),
])
def test_anos_das_eleicoes_ja_realizadas(hoje, mun, ger):
    m, g = tse.anos_ate(hoje)
    assert m[0] == 1996 and m[-1] == mun and g[0] == 1998 and g[-1] == ger
    assert all(b - a == 4 for a, b in zip(m, m[1:]))


def _zip(tmp_path, tse_fake: FakeTSE, tipo="votacao", ano=2024):
    f = tmp_path / "x.zip"
    f.write_bytes(tse_fake.responder(f"https://cdn/{'votacao_candidato_munzona' if tipo == 'votacao' else 'consulta_cand'}_{ano}.zip"))
    return f


def test_zip_so_mg_e_so_as_cidades_pedidas(tmp_path):
    rows = tse.linhas_do_zip(_zip(tmp_path, FakeTSE()), "MG", DUAS, "votacao")
    assert rows and {r["SG_UF"] for r in rows} == {"MG"}
    assert {tse.cidade_da_linha(r) for r in rows} == DUAS
    assert not any(CPF_FALSO in json.dumps(r) for r in rows)


def test_zip_sem_a_cidade_falha_para_nao_guardar_vazio(tmp_path):
    f = _zip(tmp_path, FakeTSE().falhar("2024", "sem_cidade"))
    with pytest.raises(ValueError, match="cidades sem nenhuma linha"):
        tse.linhas_do_zip(f, "MG", DUAS, "votacao")


def test_zip_antigo_com_um_arquivo_so_para_todos_os_estados(tmp_path):
    f = tmp_path / "antigo.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("votacao_1996_BRASIL.txt", "ANO_ELEICAO;NR_TURNO;DS_CARGO;SG_PARTIDO;QT_VOTOS_NOMINAIS;DS_SIT_TOT_TURNO;SG_UF;NM_MUNICIPIO\n"
                   "1996;1;PREFEITO;PMDB;10;ELEITO;MG;ITAJUBA\n1996;1;PREFEITO;PT;10;ELEITO;SP;ITAJUBA\n".encode("latin-1"))
    rows = tse.linhas_do_zip(f, "MG", ITA, "votacao")
    assert [r["SG_PARTIDO"] for r in rows] == ["PMDB"]


# ---------------------------------------------------------------- cache e TSE fora do ar

def test_baixa_uma_vez_e_depois_usa_o_cache(gov_tse, tmp_path):
    a = tse_mod_linhas(tmp_path, 2012)
    n = len(gov_tse.chamadas)
    gov_tse.falhar("2012", "fora")
    b = tse_mod_linhas(tmp_path, 2012)
    assert a == b and len(gov_tse.chamadas) == n  # nem tentou baixar de novo
    assert util.AVISOS == []
    assert not list((tmp_path / "zips").glob("*")), "o .zip grande não pode ficar no cache"
    assert a


def tse_mod_linhas(cache, ano, tipo="votacao", cidades=DUAS, hoje=None):
    return tse.linhas(tipo, ano, "MG", cidades, cache, hoje=hoje)


def test_cache_nao_tem_cpf(gov_tse, tmp_path):
    tse_mod_linhas(tmp_path, 2016)
    tse_mod_linhas(tmp_path, 2016, "cand")
    for f in tmp_path.glob("*.json"):
        assert CPF_FALSO not in f.read_text(encoding="utf-8")
        assert "DS_EMAIL" not in f.read_text(encoding="utf-8")


def test_eleicao_recente_e_baixada_de_novo_depois_de_20_horas(gov_tse, tmp_path):
    hoje = dt.date(2025, 3, 1)
    tse_mod_linhas(tmp_path, 2024, hoje=hoje)
    n = len(gov_tse.chamadas)
    tse_mod_linhas(tmp_path, 2024, hoje=hoje)
    assert len(gov_tse.chamadas) == n
    velho = time.time() - 21 * 3600
    os.utime(tmp_path / "votacao_2024_MG.json", (velho, velho))
    tse_mod_linhas(tmp_path, 2024, hoje=hoje)
    assert len(gov_tse.chamadas) == n + 1


@pytest.mark.parametrize("modo", ["fora", "html", "cortado", "vazio", "sem_cabecalho", "sem_coluna", "sem_cidade"])
def test_tse_com_defeito_e_sem_copia_vira_aviso(gov_tse, tmp_path, modo):
    gov_tse.falhar("2020", modo)
    assert tse_mod_linhas(tmp_path, 2020) is None
    assert any("2020" in a for a in util.AVISOS)
    assert not (tmp_path / "votacao_2020_MG.json").exists()


@pytest.mark.parametrize("modo", ["fora", "html", "cortado", "sem_coluna"])
def test_tse_com_defeito_usa_a_ultima_copia(gov_tse, tmp_path, modo):
    hoje = dt.date(2025, 3, 1)
    boa = tse_mod_linhas(tmp_path, 2024, hoje=hoje)
    velho = time.time() - 30 * 3600
    os.utime(tmp_path / "votacao_2024_MG.json", (velho, velho))
    gov_tse.falhar("2024", modo)
    assert tse_mod_linhas(tmp_path, 2024, hoje=hoje) == boa
    assert any("última cópia" in a for a in util.AVISOS)


def test_cache_estragado_baixa_de_novo(gov_tse, tmp_path):
    boa = tse_mod_linhas(tmp_path, 2000)
    (tmp_path / "votacao_2000_MG.json").write_text("{isto não é json", encoding="utf-8")
    assert tse_mod_linhas(tmp_path, 2000) == boa


def test_cidade_nova_na_lista_baixa_de_novo(gov_tse, tmp_path):
    tse_mod_linhas(tmp_path, 2004, cidades=ITA)
    n = len(gov_tse.chamadas)
    rows = tse_mod_linhas(tmp_path, 2004, cidades=DUAS)
    assert len(gov_tse.chamadas) == n + 1
    assert {tse.cidade_da_linha(r) for r in rows} == DUAS
