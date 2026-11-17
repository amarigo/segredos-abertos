"""Testes da conferência das planilhas de Terras Raras (terras-raras/conferir.py)."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import conferir as c  # noqa: E402

HOJE = dt.date(2026, 11, 17)
MUNICIPIOS = {"pocos de caldas", "caldas"}


def base():
    linha = {"fonte_url": "https://exemplo.gov.br/a", "verificado_em": "2026-11-17"}
    d = {t: [] for t in c.TABELAS}
    d["empresas"] = [{"id": "E01", "fonte_data": "2026", **linha}]
    d["projetos"] = [{"id": "P01", "municipios_mapa": "Poços de Caldas", "empresas_ids": "E01", "fonte_data": "sem data", **linha}]
    d["numeros"] = [{"id": "N01", "data": "2026-04", "valor_grafico": "2335", "categoria": "Investimento", **linha}]
    d["processos_noticias"] = [
        {"data": "2026-11-16", "projetos_ids": "P01", "origem": "nacional", "fonte_url_2": "https://jornal.com.br/x",
         "origem_2": "nacional", **linha},
        {"data": "2026-11", "projetos_ids": "", "origem": "nacional", "fonte_url_2": "", "origem_2": "", **linha},
    ]
    d["numeros"].append({"id": "N02", "data": "2026-11-17", "valor_grafico": "5.7851", "categoria": "Câmbio", **linha})
    d["perda_processamento"] = [{"id": "L01", "projetos_ids": "P01", "data": "2026-07-31", "producao_t_treo_ano": "12500",
                                 "cesta_baixa_usd_kg": "47", "cesta_alta_usd_kg": "86", "payability_pct": "70",
                                 "receita_vida_baixa_usd_mi": "9438", "receita_vida_alta_usd_mi": "17372", **linha}]
    d["propostas"] = [{"id": "R01", "fonte_exemplo": "https://eiti.org/countries", "verificado_em": "2026-11-17"}]
    return d


def test_planilhas_certas_passam():
    assert c.conferir(base(), MUNICIPIOS, HOJE) == []


def test_sem_fonte_ou_data_barra():
    d = base()
    d["empresas"][0]["fonte_url"] = "jornal da cidade"
    d["propostas"][0]["verificado_em"] = ""
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("empresas.csv, linha 2: sem link da fonte" in e for e in erros)
    assert any("propostas.csv" in e and "verificado_em" in e for e in erros)


def test_data_no_futuro_ou_invalida_barra():
    d = base()
    d["empresas"][0]["verificado_em"] = "2026-12-01"
    d["numeros"][0]["verificado_em"] = "2026-02-30"
    d["numeros"][0]["data"] = "abril de 2026"
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("no futuro" in e for e in erros)
    assert any("não existe no calendário" in e for e in erros)
    assert any("data 'abril de 2026'" in e for e in erros)


def test_referencias_que_nao_existem_barram():
    d = base()
    d["processos_noticias"][0]["projetos_ids"] = "P99"
    d["projetos"][0]["empresas_ids"] = "E01;E77"
    d["projetos"][0]["municipios_mapa"] = "Pocos"
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("projeto 'P99'" in e for e in erros)
    assert any("empresa 'E77'" in e for e in erros)
    assert any("município 'Pocos'" in e for e in erros)


def test_id_repetido_cpf_e_numero_barram():
    d = base()
    d["empresas"].append(copy.deepcopy(d["empresas"][0]))
    d["empresas"][1]["nome"] = "Fulano, CPF 123.456.789-09"
    d["numeros"][0]["valor_grafico"] = "2.335,00"
    d["numeros"][0]["categoria"] = ""
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("id E01 repetido" in e for e in erros)
    assert any("CPF à mostra" in e for e in erros)
    assert any("não é número" in e for e in erros)
    assert any("sem categoria" in e for e in erros)


def test_noticias_fora_de_ordem_barram():
    d = base()
    d["processos_noticias"].reverse()
    assert any("mais nova para a mais antiga" in e for e in c.conferir(d, MUNICIPIOS, HOJE))


def test_origem_da_fonte_das_noticias():
    d = base()
    d["processos_noticias"][0]["origem_2"] = "estrangeira"  # site .br marcado como estrangeiro
    d["processos_noticias"][1]["origem"] = "talvez"
    d["processos_noticias"][1]["fonte_url_2"] = "jornal local"
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("origem_2 diz estrangeira, mas o site é .br" in e for e in erros)
    assert any("origem 'talvez'" in e for e in erros)
    assert any("fonte_url_2 'jornal local' não é link" in e for e in erros)


def test_conta_da_perda_confere_numeros_e_dolar():
    d = base()
    d["perda_processamento"][0]["payability_pct"] = "0,7"
    d["perda_processamento"][0]["cesta_baixa_usd_kg"] = "90"
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("payability_pct sem número" in e for e in erros)
    d = base()
    d["perda_processamento"][0]["payability_pct"] = "100"
    d["perda_processamento"][0]["cesta_baixa_usd_kg"] = "90"
    d["numeros"] = d["numeros"][:1]
    erros = c.conferir(d, MUNICIPIOS, HOJE)
    assert any("fora de 1 a 99" in e for e in erros)
    assert any("cenário baixo maior que o alto" in e for e in erros)
    assert any("falta o dólar do dia" in e for e in erros)


def test_queda_grande_em_relacao_ao_site_barra():
    d = base()
    anterior = {t: [{}] * len(d[t]) for t in c.TABELAS}
    anterior["empresas"] = [{}] * 10
    assert c.quedas(d, anterior) == ["empresas: caiu de 10 para 1 linhas (mais de 20%) em relação ao site no ar"]
    anterior["empresas"] = [{}] * 4  # tabela pequena: não compara
    assert c.quedas(d, anterior) == []


def test_le_os_dados_da_pagina_publicada(tmp_path):
    dados = {"empresas": [{"id": "E01", "nome": "</script> teste"}]}
    txt = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    pagina = tmp_path / "index.html"
    pagina.write_text(f"<script>\nconst DADOS = {txt};\nconst X = 1;\n</script>", encoding="utf-8")
    assert c.dados_publicados(pagina) == dados
    assert c.dados_publicados(tmp_path / "nao-existe.html") is None


def test_planilhas_do_repositorio_passam():
    """As planilhas de verdade precisam passar: é a mesma conferência que roda antes de publicar."""
    assert c.main([]) == 0
