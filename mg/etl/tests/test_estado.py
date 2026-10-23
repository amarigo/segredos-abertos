"""Estado de Minas: deputados estaduais (ALMG), emendas estaduais, governo (eleição, salários e viagens) e o
dinheiro de cada cidade (emendas federais e estaduais, contas da prefeitura).

Pirâmide: primeiro as peças pequenas (ler valor, achar coluna, tirar CPF), depois cada fonte com o seu arquivo
simulado, depois a montagem inteira e, por fim, o caos: cada fonte fora do ar, com página de erro no lugar do
arquivo, cortada ou com coluna trocada. Em nenhum caso o resto pode parar, e nenhum CPF pode sair.
"""
import datetime as dt
import json
import re

import pytest
from hypothesis import given, settings, strategies as st

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE
from fakeestado import CPF_EMITENTE, EMENDAS_COLS, FakeEstado
from mg_etl import almg, build, emendas_federais, emendas_mg, equipe, fontes, governo, siconfi
from mg_etl.validar import validar
from sa_etl import emendas as emendas_nac, util

HOJE = dt.date(2026, 10, 23)
MAPA_CIDADES = {emendas_mg.chave_cidade(c["nome"]): c["id"] for c in CIDADES_TESTE}
CPF_FORMATOS = [CPF_EMITENTE, f"{CPF_EMITENTE[:3]}.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-{CPF_EMITENTE[9:]}"]


# ---------------------------------------------------------------- peças pequenas

@pytest.mark.parametrize("entrada,esperado", [
    ("R$1.234,56", 1234.56), ("R$ 100.000,00", 100000.0), ("1234.56", 1234.56), ("1234,5", 1234.5),
    ("1.234.567", 1234567.0), ("-", 0.0), ("N/A", 0.0), ("", 0.0), (None, 0.0), ("(1,00)", -1.0), (12, 12.0),
])
def test_valor(entrada, esperado):
    assert fontes.valor(entrada) == pytest.approx(esperado)


@given(st.from_regex(r"\d{11}", fullmatch=True))
def test_cpf_nunca_passa_como_documento_publico(cpf):
    assert fontes.doc_publico(cpf) == ""
    assert fontes.doc_publico(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}") == ""


@given(st.text(max_size=40), st.from_regex(r"\d{11}", fullmatch=True), st.text(max_size=40))
@settings(max_examples=200)
def test_sem_cpf_tira_qualquer_cpf_de_texto_livre(antes, cpf, depois):
    for forma in (cpf, f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"):
        limpo = fontes.sem_cpf(f"{antes} {forma} {depois}")
        assert forma not in limpo


def test_sem_cpf_mantem_cnpj_e_numero_de_processo():
    assert fontes.sem_cpf("CNPJ 18.025.940/0001-09") == "CNPJ 18.025.940/0001-09"
    assert fontes.sem_cpf("SEI 1450.01.0045460/2023-77") == "SEI 1450.01.0045460/2023-77"
    assert fontes.sem_cpf("CARLOS - 519.349.306-87") == "Carlos" or fontes.sem_cpf("CARLOS - 519.349.306-87") == "CARLOS"


def test_colunas_do_arquivo_de_emendas_da_almg():
    col = emendas_mg.achar_colunas(EMENDAS_COLS)
    assert col["ano"] == "Ano da Indicação" and col["numero"] == "Número da Indicação"
    assert col["municipio"] == "Município " and col["beneficiario"] == "Nome Beneficiário"
    assert col["indicado"] == "Valor Indicado" and col["pago"] == "Valor Pago Atualizado"
    assert col["status"] == "Status" and col["status_indicacao"] == "Status da Indicação"
    assert col["tipo_beneficiario"] == "Descrição do Tipo de Beneficiário"


def test_meses_da_legislatura():
    m = almg.meses_legislatura(dt.date(2023, 4, 10))
    assert m == [(2023, 4), (2023, 3), (2023, 2)]
    assert almg.meses_legislatura(HOJE)[0] == (2026, 10) and len(almg.meses_legislatura(HOJE)) == 45


def test_cargos_da_equipe_de_governo():
    for c in ("GOVERNADOR DO ESTADO", "VICE  GOVERNADOR DO ESTADO", "VICE-GOVERNADOR", "SECRETARIO DE ESTADO", "SECRETÁRIA DE ESTADO",
              "SECRETARIO-GERAL", "ADVOGADO GERAL DO ESTADO", "CONTROLADOR GERAL DO ESTADO"):
        assert equipe.eh_da_equipe(c), c
    for c in ("ASSESSOR DE SECRETARIO DE ESTADO II", "SECRETARIO-GERAL ADJUNTO", "CHEFE DE GABINETE DO GOVERNADOR DO ESTADO",
              "ASSISTENTE DO ADVOGADO GERAL DO ESTADO", "CONTROLADOR GERAL DO ESTADO ADJUNTO", "UNIDADE REGIONAL - GOVERNADOR VALADARES", ""):
        assert not equipe.eh_da_equipe(c), c
    assert equipe.mes_do_recurso("Remuneração de Março de 2026") == (2026, 3)
    assert equipe.mes_do_recurso("Dicionário de dados") is None


# ---------------------------------------------------------------- cada fonte

def test_emendas_estaduais_somas_repetidas_e_reprovadas():
    fake = FakeEstado()
    rows = emendas_mg.linhas(fontes.decodificar(fake.emendas_csv()))
    assert len(rows) == len(fake.emendas_linhas) - 1, "a linha repetida entra uma vez só"
    assert not any("E+" in json.dumps(r) for r in rows), "o CNPJ estragado pelo Excel não pode aparecer"
    deps = {fontes.chave_nome(d["nome"]): str(d["id"]) for d in fake.deputados}
    r = emendas_mg.resumir(rows, deps, MAPA_CIDADES)
    for (ano, cidade), (ind, pago) in fake.esperado["emendas"].items():
        cid = MAPA_CIDADES.get(emendas_mg.chave_cidade(cidade))
        if cid:
            lst = [x for x in r["por_cidade"][cid] if x["ano"] == ano]
            assert sum(x["indicado"] for x in lst) == pytest.approx(ind)
            assert sum(x["pago"] for x in lst) == pytest.approx(pago)
    for ano, e in r["estado"].items():
        assert e["indicado"] == pytest.approx(sum(v[0] for (a, _), v in fake.esperado["emendas"].items() if a == ano))
        assert sum(a["indicado"] for a in e["autores"]) == pytest.approx(e["indicado"])
    assert not any(x["indicado"] == 999_999 for x in r["por_cidade"]["itajuba"]), "indicação reprovada não vira dinheiro"
    ex = [a for a in r["estado"][2023]["autores"] if "Ex Deputado" in a["nome"]]
    assert ex and ex[0]["deputado"] is None, "quem saiu da Assembleia aparece sem link"
    d0 = r["por_deputado"][str(fake.deputados[0]["id"])][2023]
    assert d0["n"] == 4 and d0["n_municipios"] == 4


def test_proposicoes_contam_so_o_primeiro_autor_e_projetos_que_viraram_lei():
    fake = FakeEstado()
    ids = {str(d["id"]) for d in fake.deputados}
    p = almg.proposicoes({2025: fontes.decodificar(fake.proposicoes_csv(2025))}, ids)
    for d in fake.deputados[:10]:
        i = d["id"] - 20000
        x = p[str(d["id"])][2025]
        assert x["projetos"] == i % 5
        assert x["aprovadas"] == (1 if i % 5 else 0), "requerimento aprovado não conta como projeto aprovado"
        assert x["requerimentos"] == 1
        assert all(y["url"].startswith("https://www.almg.gov.br/") for y in x["lista"]) if x["lista"] and "url" in x["lista"][0] else True
    assert p[str(fake.deputados[1]["id"])][2025]["coautor"] == 0  # o 0 não tem projetos
    assert p[str(fake.deputados[2]["id"])][2025]["coautor"] == 1  # coautor do único projeto do deputado 1
    assert almg.link_proposicao({"sigla": "PL", "numero": "3221", "ano": 2025}).endswith("?tipo=PL&num=3221&ano=2025")


def test_notas_da_verba_sem_cpf():
    fake = FakeEstado()
    notas = almg.notas_do_mes(json.loads(fake.verba_mes(20003, 2025, 2)))
    assert sum(n["valor"] for n in notas) == pytest.approx(4000 + 500)
    pf = [n for n in notas if n["pf"]]
    assert len(pf) == 1 and pf[0]["cnpj"] == "" and pf[0]["fornecedor"] == "Jose da Silva"
    assert not any(c in json.dumps(notas) for c in CPF_FORMATOS)
    assert all(n["cnpj"] in ("", "11222333000181") for n in notas)
    assert almg.notas_do_mes(json.loads(fake.verba_mes(20050, 2025, 2))) == []


def test_contas_da_prefeitura_sem_contar_duas_vezes(estado, tmp_path):
    c = siconfi.contas("Itajubá", "MG", tmp_path, hoje=HOJE)
    assert c["cod_ibge"] == 3132404, "a Itajubá de MG, não a de mesmo nome em SP"
    a = c["anos"][0]
    assert a["ano"] == 2025 and [x["ano"] for x in c["anos"]] == list(range(2025, 2017, -1))
    saude = next(f for f in a["funcoes"] if f["funcao"] == "Saúde")
    assert saude["liquidado"] == pytest.approx(4_000_000 * 1.7), "intraorçamentárias e restos a pagar ficam de fora"
    assert a["total_liquidado"] == pytest.approx(sum(f["liquidado"] for f in a["funcoes"]))
    assert [p["nome"] for p in saude["principais"]] == ["Atenção Básica", "Assistência Hospitalar e Ambulatorial"]
    # anos fechados ficam no cache: a segunda vez não consulta o Tesouro
    n = len(estado.chamadas)
    siconfi._ENTES.clear()
    siconfi.contas("Itajubá", "MG", tmp_path, hoje=HOJE)
    assert not any("/dca" in u for u in estado.chamadas[n:])


def test_emendas_federais_na_cidade(tmp_path):
    fake = FakeEstado()
    z = fake.emendas_federais_zip(tmp_path / "EmendasParlamentares.zip")
    from sa_etl import emendas as E
    r = emendas_federais.resumir(E.linhas(z, "favorecido"), MAPA_CIDADES, {})
    ita = r["itajuba"]
    assert sum(x["valor"] for x in ita["por_ano"]) == pytest.approx(fake.esperado["federais_itajuba"]), "a Itajubá de SP fica de fora"
    pf = [f for f in ita["favorecidos"] if not f["cnpj"]]
    assert pf and pf[0]["nome"] == "Pessoa física" and pf[0]["url"] == ""
    assert all(f["url"].startswith("https://portaldatransparencia.gov.br/pessoa-juridica/") for f in ita["favorecidos"] if f["cnpj"])
    assert "paraisopolis" not in r


def test_governador_e_vice_da_chapa(estado, tmp_path):
    g = governo.eleicao(2022, tmp_path / "tse")
    assert g["governador"]["nome"] == "Governador 0" and g["inicio"] == 2023
    assert g["vice"]["nome"] == "Vice do Governador 0", "nem o indeferido, nem o da eleição suplementar, nem o de SP"
    assert sum(c["pct"] for c in g["candidatos"]) == pytest.approx(100, abs=0.05)


def test_salarios_e_viagens_da_equipe(estado, tmp_path):
    e = equipe.coletar(tmp_path, hoje=HOJE)
    nomes = [p["nome"] for p in e["pessoas"]]
    assert nomes[0] == "Governadora de Teste", "o governador vem primeiro"
    assert set(nomes) == {"Governadora de Teste", "Secretario da Saude", "Secretaria da Fazenda"}, "adjuntos e assessores ficam de fora"
    assert e["mes_salarios"] == "2026-08", "o mês mais recente"
    faz = next(p for p in e["pessoas"] if p["nome"] == "Secretaria da Fazenda")
    assert faz["jetons"] == pytest.approx(6724.29) and faz["bruto"] == pytest.approx(34774.64)
    gov = e["pessoas"][0]["viagens"]
    assert gov["anos"][0] == {"ano": 2026, "viagens": 2, "diarias": 1880.0, "passagens": 1245.23}
    assert gov["destinos"][0]["nome"] in ("Brasilia", "Itajuba")
    sau = next(p for p in e["pessoas"] if p["nome"] == "Secretario da Saude")["viagens"]
    assert sau is not None, "o CPF grudado no nome do arquivo de viagens não pode impedir de achar a pessoa"
    texto = json.dumps(e, ensure_ascii=False)
    assert not any(c in texto for c in CPF_FORMATOS) and "35999998888" not in texto and "***" not in texto
    # o arquivo de salários (200+ MB) não é baixado de novo se o mês já foi lido
    n = len(estado.chamadas)
    equipe.salarios(tmp_path)
    assert not any(u.endswith(".csv") for u in estado.chamadas[n:])


# ---------------------------------------------------------------- montagem inteira

def _montar(nacional, tmp_path, cache=None):
    cache = cache or tmp_path / "cache"
    fake_zip = emendas_nac.zip_no_cache(tmp_path / "cache_nacional")
    if not fake_zip.exists():
        FakeEstado().emendas_federais_zip(fake_zip)
    saida = tmp_path / "mg"
    cont = build.montar(nacional, saida, cache, CIDADES_TESTE, cache_nacional=tmp_path / "cache_nacional")
    return saida, cont


def _json(saida, rel):
    return json.loads((saida / rel).read_text(encoding="utf-8"))


def test_montagem_completa(estado, nacional, tmp_path):
    saida, cont = _montar(nacional, tmp_path)
    assert cont["deputados_estaduais"] == 60 and cont["governo"] == 2 and cont["equipe_governo"] == 3
    idx = _json(saida, "almg/deputados.json")
    assert len(idx["deputados"]) == 60 and len(list((saida / "almg" / "d").glob("*.json"))) == 60
    assert idx["verba_completa"]["2025"] is True
    d3 = _json(saida, "almg/d/20003.json")
    v = d3["anos"]["2025"]["verba"]
    assert v["total"] == pytest.approx(3 * (4000 + 500)) and v["meses_faltando"] == []
    assert d3["por_ano"]["2025"]["verba"] == v["total"]
    assert sum(t["valor"] for t in v["tipos"]) == pytest.approx(v["total"])
    assert sum(m["valor"] for m in v["meses"]) == pytest.approx(v["total"])
    assert d3["url_verba"].endswith("detalhe.html?id=20003")
    assert idx["medianas"]["2025"]["verba"] == 0, "mais da metade não gastou nada: a mediana é zero"
    em = _json(saida, "estado/emendas.json")
    assert set(em["anos"]) == {"2023", "2024", "2025"}
    gov = _json(saida, "estado/governo.json")
    assert gov["eleicoes"][0]["eleicao"] == 2022 and gov["equipe"]["pessoas"]
    ita = _json(saida, "cidades/dinheiro/itajuba.json")
    assert ita["contas"]["anos"] and ita["federais"]["por_ano"] and ita["estaduais"]["lista"]
    par = _json(saida, "cidades/dinheiro/paraisopolis.json")
    assert par["federais"] == {"fonte": emendas_federais.PAGINA, "por_ano": [], "favorecidos": [], "autores": []}, \
        "a fonte respondeu e a cidade não recebeu nada: lista vazia, não 'fonte fora do ar'"
    meta = _json(saida, "meta.json")
    assert meta["estado"]["deputados_estaduais"] == 60
    assert meta["avisos"] == [], "com todas as fontes no ar, nada pode ficar de fora (avisos da execução de 23/10/2026)"
    assert sum(p["projetos"] for p in d3["por_ano"].values()) > 0, "proposições da ALMG lidas"
    r = validar(saida, minimos=MINIMOS_TESTE)
    assert r.erros == []


def test_nenhum_cpf_em_nenhum_arquivo(estado, nacional, tmp_path):
    saida, _ = _montar(nacional, tmp_path)
    for f in saida.rglob("*.json"):
        texto = f.read_text(encoding="utf-8")
        for c in CPF_FORMATOS:
            assert c not in texto, f"CPF em {f.relative_to(saida)}"
        assert not re.search(r'"cnpj": "\d{11}"', texto), f"CPF no lugar de CNPJ em {f.relative_to(saida)}"


def test_orcamento_da_verba_completa_aos_poucos(estado, nacional, tmp_path, monkeypatch):
    monkeypatch.setattr(almg, "ORCAMENTO_VERBA", 1000)
    saida, _ = _montar(nacional, tmp_path)
    assert sum("verbas_indenizatorias" in u for u in estado.chamadas) == 1000
    idx = _json(saida, "almg/deputados.json")
    assert idx["verba_completa"]["2023"] is False, "o site avisa que o ano ainda está incompleto"
    assert idx["verba_completa"]["2026"] is True, "os meses mais novos vêm primeiro"
    # nas execuções seguintes, completa (e não pergunta de novo o que já tem)
    for _ in range(3):
        estado.chamadas.clear()
        saida, _ = _montar(nacional, tmp_path, cache=tmp_path / "cache")
    idx = _json(saida, "almg/deputados.json")
    assert all(idx["verba_completa"].values())
    assert sum("verbas_indenizatorias" in u for u in estado.chamadas) == 0


# ---------------------------------------------------------------- caos

FONTES = {
    "ALMG (deputados)": "/deputados/em_exercicio",
    "verba": "verbas_indenizatorias",
    "proposições": "/arquivo/proposicoes",
    "emendas estaduais": "mediaserver.almg.gov.br",
    "Tesouro": "apidatalake.tesouro.gov.br",
    "salários": "servidores-2026",
    "viagens": ".csv.gz",
    "Dados MG": "dados.mg.gov.br",
    "TSE": "tse.jus.br",
}


@pytest.mark.parametrize("modo", ["fora", "500", "html", "vazio", "cortado"])
@pytest.mark.parametrize("fonte", list(FONTES))
def test_uma_fonte_falha_e_o_resto_sai(estado, nacional, tmp_path, fonte, modo):
    estado.falhar(FONTES[fonte], modo)
    saida, cont = _montar(nacional, tmp_path)
    assert (saida / "cidades.json").exists() and (saida / "politicos.json").exists(), "o resto do site não pode parar"
    assert (saida / "estado" / "governo.json").exists()
    for c in CIDADES_TESTE:
        assert (saida / "cidades" / "dinheiro" / f"{c['id']}.json").exists()
    if fonte not in ("ALMG (deputados)", "TSE") and not (fonte == "emendas estaduais" and modo == "cortado"):
        assert cont.get("deputados_estaduais") == 60, f"{fonte} não deveria derrubar a lista de deputados"
    r = validar(saida, minimos=MINIMOS_TESTE)
    if fonte == "TSE":  # sem o TSE (e sem cópia), as cidades ficam sem prefeitos: a conferência barra, de propósito
        assert any("mandatos de prefeito" in e for e in r.erros)
    else:
        assert r.erros == [], r.erros
    texto = "".join(f.read_text(encoding="utf-8") for f in saida.rglob("*.json"))
    assert not any(c in texto for c in CPF_FORMATOS)


def test_fonte_fora_do_ar_usa_a_ultima_copia_e_avisa(estado, nacional, tmp_path, monkeypatch):
    _montar(nacional, tmp_path)
    estado.consertar()
    for pedaco in ("/deputados/em_exercicio", "mediaserver", "dados.mg.gov.br", "apidatalake", "verbas_indenizatorias"):
        estado.falhar(pedaco, "fora")
    # cópias velhas: o coletor tenta baixar de novo e, como falha, usa a cópia
    monkeypatch.setattr(util, "download", _download_sempre_velho(util.download))
    monkeypatch.setattr(fontes, "download", _download_sempre_velho(fontes.download))
    saida, cont = _montar(nacional, tmp_path, cache=tmp_path / "cache")
    assert cont["deputados_estaduais"] == 60 and cont["equipe_governo"] == 3
    ita = _json(saida, "cidades/dinheiro/itajuba.json")
    assert ita["estaduais"]["lista"] and ita["contas"]["anos"]
    avisos = " ".join(_json(saida, "meta.json")["avisos"])
    assert "deputados em exercício" in avisos and "última cópia" in avisos


def _download_sempre_velho(orig):
    def baixar(url, dest, max_horas=None, validar=None, headers=None):
        return orig(url, dest, max_horas=0 if max_horas is not None else None, validar=validar, headers=headers)
    return baixar


def test_arquivo_de_emendas_com_coluna_trocada(estado, nacional, tmp_path):
    estado.falhar("mediaserver", "sem_coluna")
    saida, _ = _montar(nacional, tmp_path)
    assert not (saida / "estado" / "emendas.json").exists()
    assert _json(saida, "cidades/dinheiro/itajuba.json")["estaduais"] is None
    assert any("formato diferente" in a for a in _json(saida, "meta.json")["avisos"])


def test_verba_fora_do_ar_para_depois_de_5_falhas(estado, nacional, tmp_path):
    estado.falhar("verbas_indenizatorias", "500")
    _montar(nacional, tmp_path)
    assert sum("verbas_indenizatorias" in u for u in estado.chamadas) <= 5 * 3, "não insiste com a ALMG fora do ar"
