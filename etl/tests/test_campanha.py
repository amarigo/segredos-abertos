"""Dinheiro da campanha (sa_etl/campanha.py): contas do TSE ligadas à cota, às emendas e aos sócios."""
import json

import fakegov_tse
from fakegov import FakeGov
from sa_etl import campanha, util


def _todas_as_linhas(saida):
    return "\n".join(f.read_text(encoding="utf-8") for f in saida.rglob("*.json"))


def test_coleta_liga_campanha_e_mandato(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    d = coleta.ler(saida, "p/campanha/dep-1000.json")
    anos = [c["ano"] for c in d["campanhas"]]
    assert anos == [2026, 2022, 2018]  # da mais nova para a mais antiga
    c22 = next(c for c in d["campanhas"] if c["ano"] == 2022)
    assert c22["achada_por"] == "cpf"
    assert c22["fonte"] == "https://dadosabertos.tse.jus.br/dataset/" + fakegov_tse.pacote(2022)
    # 150.000 + 3.000 + 5.000 + 1.234,56 (estimável) + 75.000 + 9.000
    assert c22["receitas"]["total"] == 243234.56
    assert c22["receitas"]["estimavel"] == 1234.56
    tipos = {x["tipo"] for x in d["ligacoes"]}
    assert {"fornecedor", "doador_socio"} <= tipos
    forn = next(x for x in d["ligacoes"] if x["tipo"] == "fornecedor")
    assert forn["empresa"]["cnpj"] == gov.fornecedoras[5] and forn["campanha"] == 12345.67 and forn["ano"] == 2022
    socios = [x for x in d["ligacoes"] if x["tipo"] == "doador_socio"]
    assert {x["doador"]["nome"] for x in socios} == {"DONO FICTICIO 3"}  # o homônimo (DONO FICTICIO 4) não liga
    assert all(x["doacao"] == 75000.0 and x["doador"]["doc"] == "***.100.003-**" for x in socios)
    assert all(x.get("cota") or x.get("emendas") for x in d["ligacoes"])
    # deputado 01 mudou de nome depois da eleição: achado pelo CPF; senador 00 achado pelo nome civil
    assert coleta.ler(saida, "p/campanha/dep-1001.json")["campanhas"][0]["achada_por"] == "cpf"
    assert coleta.ler(saida, "p/campanha/sen-5000.json")["campanhas"][0]["achada_por"] == "nome"
    # a página da empresa mostra a ligação
    e = coleta.ler(saida, f"e/{gov.fornecedoras[5]}.json")
    assert any(x["politico"] == "dep-1000" and x["tipo"] == "fornecedor" for x in e["campanha"])
    geral = coleta.ler(saida, "campanha.json")
    assert geral["contagens"]["ligacoes"] == len(geral["ligacoes"]) > 0
    assert set(geral["anos"]) == {"2018", "2022", "2026"}
    # nenhum CPF do TSE vai para o site: nem de candidato, nem de doador, nem o que vem escrito no nome do fornecedor
    tudo = _todas_as_linhas(saida)
    for cpf in (fakegov_tse.CPF_DOADOR_SOCIO, fakegov_tse.CPF_HOMONIMO, fakegov_tse.CPF_FORNECEDOR_PF, fakegov_tse.cpf_deputado(0)):
        assert cpf not in tudo
    assert "JOAO FICTICIO" in tudo
    res = coleta.validar(saida)
    assert not [x for x in res.erros if "Campanha" in x], res.erros


def test_so_baixa_de_novo_quando_o_tse_troca_o_arquivo(coleta):
    gov = coleta.usar(FakeGov())
    coleta.rodar()
    assert sorted(gov.tse_baixados) == [2018, 2022, 2026]
    coleta.rodar()  # mesma versão: só pergunta (HEAD) pelo ano recente; os anteriores valem 30 dias
    assert sorted(gov.tse_baixados) == [2018, 2022, 2026]
    gov.tse_etag[2026] = '"e-2026-nova"'
    coleta.rodar()
    assert sorted(gov.tse_baixados) == [2018, 2022, 2026, 2026]


def test_tse_fora_do_ar_usa_a_copia_e_avisa(coleta):
    gov = coleta.usar(FakeGov())
    coleta.rodar()
    gov.tse_etag[2026] = '"e-2026-nova"'
    gov.falhar("cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2026", "500")
    util.AVISOS.clear()
    saida = coleta.rodar()
    assert any("campanha 2026" in a and "cópia" in a for a in util.AVISOS)
    assert coleta.ler(saida, "p/campanha/dep-1000.json")["campanhas"][0]["ano"] == 2026


def test_sem_tse_e_sem_copia_o_site_sai_sem_a_aba(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("tse.jus.br", "500")
    saida = coleta.rodar()
    assert not (saida / "campanha.json").exists()
    assert (saida / "politicos.json").exists()
    assert any("Dinheiro da campanha" in a for a in util.AVISOS)


def _cand(sq, nome, uf, cpf="", total=1.0):
    return {"sq": sq, "ano": 2022, "nome": nome, "cpf": campanha.resumo_cpf(cpf), "meio_cpf": campanha.meio_cpf(cpf), "uf": uf,
            "receitas": {"total": total, "n": 1}, "despesas": {"total": 0.0}, "doadores": {}, "originarios": {}, "fornecedores": {}}


def test_nome_igual_de_duas_pessoas_nao_liga():
    pol = [{"id": "sen-1", "casa": "senado", "uf": "SP"}]
    pess = {"sen-1": {"cpf": "", "meio_cpf": "", "nome_civil": "José da Silva"}}
    contas = {2022: {"candidatos": {"1": _cand("1", "JOSE DA SILVA", "SP", "11122233344"),
                                    "2": _cand("2", "JOSÉ DA SILVA", "SP", "55566677788")}}}
    assert campanha.ligar_candidaturas(pol, pess, contas) == {}
    contas[2022]["candidatos"].pop("2")
    assert campanha.ligar_candidaturas(pol, pess, contas)["sen-1"][0]["sq"] == "1"


def test_politico_socio_pela_chave_nome_e_cpf():
    cpf = "12312345678"
    c = _cand("1", "MARIA FICTICIA", "SP", cpf)
    donos = {f"MARIA FICTICIA|***{cpf[3:9]}**": [("11222333000181", "socio", "Sócio-Administrador")]}
    cota = {"11222333": {"cnpj": "11222333000181", "nome": "X", "valor": 900.0, "de": "2025-01-02", "ate": "2025-03-04"}}
    lig = campanha.ligacoes("dep-1", [c], cota, {}, donos, {}, {})
    assert [x["tipo"] for x in lig] == ["politico_socio"] and lig[0]["cota"] == 900.0
    # outros 6 dígitos: não liga
    assert campanha.ligacoes("dep-1", [_cand("1", "MARIA FICTICIA", "SP", "12399999978")], cota, {}, donos, {}, {}) == []


def test_textos_do_tse():
    assert campanha.valor("1.234,56") == 1234.56
    assert campanha.data_iso("31/08/2022") == "2022-08-31"
    assert campanha.sem_cpf("JOAO DA SILVA 123.456.789-09") == "JOAO DA SILVA"
    assert campanha.sem_cpf("JOAO 12345678909 ME") == "JOAO ME"
    assert campanha.sem_cpf("12.345.678 JOAO DA SILVA") == "12.345.678 JOAO DA SILVA"  # raiz de CNPJ não é CPF
    assert campanha.doc_publico("12345678909") == "***.456.789-**"
    assert campanha.meio_cpf("12345678909") == "***456789**"
    assert campanha.resumo_cpf("12345678909") != campanha.resumo_cpf("12345678900")
    assert "12345678909" not in json.dumps(campanha.resumo_cpf("12345678909"))


def test_com_cpf_o_nome_igual_nao_basta():
    """Deputado com CPF na API da Câmara que não concorreu: um candidato com o mesmo nome e outro CPF não é ele."""
    pol = [{"id": "dep-1", "casa": "camara", "uf": "SP"}]
    pess = {"dep-1": {"cpf": campanha.resumo_cpf("11122233344"), "meio_cpf": "***222333**", "nome_civil": "José da Silva"}}
    contas = {2022: {"candidatos": {"1": _cand("1", "JOSE DA SILVA", "SP", "55566677788")}}}
    assert campanha.ligar_candidaturas(pol, pess, contas) == {}
