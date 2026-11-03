"""Pagamentos a empresas pela API do Portal (recursos recebidos por favorecido), contra o governo simulado."""
import datetime as dt

import pytest

from fakegov import FakeGov, instalar
from sa_etl import recursos_recebidos as rr
from sa_etl.util import digits

HOJE = dt.date(2026, 1, 15)


@pytest.fixture(autouse=True)
def rapido(monkeypatch):
    monkeypatch.setattr(rr, "POR_MINUTO_DIA", 10**6)
    monkeypatch.setattr(rr, "POR_MINUTO_MADRUGADA", 10**6)


def esperado(gov: FakeGov, ano: int) -> tuple[dict[str, float], float]:
    """Total por CNPJ que não é público, direto das linhas simuladas, e o total pago a pessoas físicas."""
    por, pessoas = {}, 0.0
    for m in range(1, 13):
        for x in gov.recursos_mes(ano, m):
            if "*" in x["codigoPessoa"]:
                pessoas += x["valor"]
            elif "MUNICIPIO" not in x["nomePessoa"]:
                d = digits(x["codigoPessoa"])
                por[d] = por.get(d, 0.0) + x["valor"]
    return por, pessoas


def test_le_todos_os_meses_sem_corte(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov())
    r = rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE).coletar([2025], 5)
    assert len(r["feitos"]) == 12 and not r["faltam"]
    res = rr.resumir(tmp_path, [2025], hoje=HOJE)
    por, pessoas = esperado(gov, 2025)
    got = {d: round(e["valor"], 2) for d, e in res["anos"][2025].items()}
    assert got == {d: round(v, 2) for d, v in por.items()}  # todas as empresas, nenhuma de fora
    assert all(len(d) == 14 for d in got)  # CPF não entra
    assert res["cobertura"][2025]["pessoas_fisicas"] == pytest.approx(pessoas, abs=0.05)
    assert "18715383000140" in res["publicos"][2025]  # prefeitura separada pelo nome
    c = res["cobertura"][2025]
    assert c["completo"] and c["origem"] == "api" and c["meses"] == 12 and c["dias"] == 365


def test_para_no_limite_de_tempo_e_continua_depois(tmp_path, monkeypatch):
    instalar(monkeypatch, FakeGov())
    lt = rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE)
    assert lt.coletar([2025], 0)["feitos"] == []
    r = lt.coletar([2025], 5)
    assert not r["faltam"]


def test_mes_fechado_nao_e_lido_de_novo_e_o_recente_sim(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov())
    rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE).coletar([2025, 2026], 5)
    gov.chamadas.clear()
    lt = rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE + dt.timedelta(days=10))
    lt.coletar([2025, 2026], 5)
    meses = {c.split("mesAnoInicio=")[1][:7] for c in gov.chamadas if "recursos-recebidos" in c}
    assert meses == {"01/2026", "12/2025"}  # só os dois meses recentes


def test_recusa_logo_no_comeco_para_e_continua_depois(tmp_path, monkeypatch):
    """HTTP 400 nas primeiras páginas não é página funda: para, guarda o que leu e tenta de novo na próxima execução."""
    gov = instalar(monkeypatch, FakeGov())
    gov.recursos_max_pagina = 1
    lt = rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE)
    r = lt.coletar([2025], 5)
    assert r["falhou"] and r["motivo"].startswith("HTTP 400") and not lt.final("202512").exists()
    gov.recursos_max_pagina = None
    assert not rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE).coletar([2025], 5)["faltam"]


def test_pagina_funda_depois_de_50_paginas(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov())
    linhas = [{**x, "codigoUG": f"{x['codigoUG']}-{i}"} for i in range(60) for x in gov.recursos_mes(2025, 3)]  # muitas páginas
    monkeypatch.setattr(gov, "recursos_mes", lambda a, m: linhas)
    gov.recursos_max_pagina = 55
    lt = rr.Leitor(tmp_path, "chave-de-teste", hoje=HOJE)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(rr.EM_PARALELO) as pool:
        assert lt.ler_mes("202503", 10**12, pool) is True
    d = lt._abrir(lt.final("202503"))
    assert d["por_orgao"] and d["linhas"] > len(linhas)  # leu de novo por órgão
    assert sum(f[1] for f in d["f"].values()) == pytest.approx(
        sum(x["valor"] for x in linhas if len(digits(x["codigoPessoa"])) == 14), abs=0.5)


def test_chave_recusada_para_e_diz_o_motivo(tmp_path, monkeypatch):
    instalar(monkeypatch, FakeGov())
    r = rr.Leitor(tmp_path, "outra", hoje=HOJE).coletar([2025], 5)
    assert r["falhou"] and r["motivo"].startswith("HTTP 401") and not r["feitos"]


def test_juntar_fica_com_a_fonte_que_cobre_mais_dias():
    arq = {"anos": {2025: {"1": {"valor": 1}}, 2026: {"1": {"valor": 5}}},
           "cobertura": {2025: {"dias": 365}, 2026: {"dias": 290}}, "publicos": {}, "cobertura_publicos": {}}
    api = {"anos": {2025: {"1": {"valor": 2}}, 2026: {"1": {"valor": 9}}},
           "cobertura": {2025: {"dias": 0}, 2026: {"dias": 300, "origem": "api"}}, "publicos": {}, "cobertura_publicos": {}}
    j = rr.juntar(arq, api, [2025, 2026])
    assert j["anos"][2025]["1"]["valor"] == 1 and j["anos"][2026]["1"]["valor"] == 9
    assert j["cobertura"][2026]["origem"] == "api"


def test_por_minuto_segue_o_horario_de_brasilia():
    assert rr.por_minuto(dt.datetime(2026, 1, 1, 5, 0, tzinfo=dt.timezone.utc)) == rr.POR_MINUTO_MADRUGADA  # 2h em Brasília
    assert rr.por_minuto(dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)) == rr.POR_MINUTO_DIA


def test_site_usa_a_api_quando_os_arquivos_diarios_falham(coleta, monkeypatch):
    """O caso de novembro de 2026: o Portal recusa os arquivos diários (HTTP 405), a API tem os meses."""
    monkeypatch.setattr(rr, "POR_MINUTO_DIA", 10**6)
    gov = coleta.usar(FakeGov())
    gov.falhar("/download-de-dados/despesas/", "404")
    rr.Leitor(coleta.cache, "chave-de-teste", hoje=HOJE).coletar([2025], 5)
    saida = coleta.rodar()
    a = coleta.ler(saida, "incentivos/2025.json")["pagamentos"]
    por, _ = esperado(gov, 2025)
    assert a["cobertura"]["origem"] == "api" and a["cobertura"]["completo"]
    assert a["total"] == pytest.approx(sum(por.values()), abs=1)
    assert a["n"] == len(por)
    assert a["por_categoria"][0]["cat"] == "pago"
    assert coleta.validar(saida).erros == []
