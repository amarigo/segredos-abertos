"""Emendas parlamentares com dados fictícios mínimos (apenas para testar o código, nunca exibidos no site)."""
import json
import zipfile

from sa_etl import emendas

CAB = ('"Código da Emenda";"Ano da Emenda";"Tipo de Emenda";"Código do Autor da Emenda";"Nome do Autor da Emenda";'
       '"Número da emenda";"Localidade de aplicação do recurso";"Código Município IBGE";"Município";"Código UF IBGE";"UF";'
       '"Região";"Código Função";"Nome Função";"Código Subfunção";"Nome Subfunção";"Valor Empenhado";"Valor Liquidado";'
       '"Valor Pago";"Valor Restos A Pagar Inscritos";"Valor Restos A Pagar Cancelados";"Valor Restos A Pagar Pagos"')
LINHAS = [
    '"1";"2025";"Emenda Individual - Transferências com Finalidade Definida";"10";"FULANO DE TAL";"1";"BELO HORIZONTE - MG";"1";"BELO HORIZONTE";"31";"MINAS GERAIS";"SUDESTE";"10";"Saúde";"301";"Atenção básica";"1.000,00";"0,00";"600,00";"0,00";"0,00";"100,00"',
    '"2";"2025";"Emenda Individual - Transferências Especiais";"10";"FULANO DE TAL";"2";"CONTAGEM - MG";"2";"CONTAGEM";"31";"MINAS GERAIS";"SUDESTE";"28";"Encargos especiais";"845";"Transferências";"500,00";"0,00";"500,00";"0,00";"0,00";"0,00"',
    '"3";"2025";"Emenda Individual - Transferências com Finalidade Definida";"11";"BELTRANA SILVA";"1";"MINAS GERAIS (UF)";"";"";"31";"MINAS GERAIS";"SUDESTE";"12";"Educação";"361";"Ensino";"2.000,00";"0,00";"0,00";"0,00";"0,00";"0,00"',
    '"4";"2025";"Emenda de Bancada";"99";"BANCADA DE MINAS GERAIS";"1";"Nacional";"";"";"";"";"";"10";"Saúde";"302";"Hospital";"9.000,00";"0,00";"3.000,00";"0,00";"0,00";"0,00"',
    '"5";"2019";"Emenda Individual - Transferências com Finalidade Definida";"10";"FULANO DE TAL";"1";"BELO HORIZONTE - MG";"";"";"";"";"";"10";"Saúde";"301";"x";"7,00";"0,00";"7,00";"0,00";"0,00";"0,00"',
]
FAV = ('"Código da Emenda";"Código do Autor da Emenda";"Nome do Autor da Emenda";"Número da emenda";"Tipo de Emenda";"Ano/Mês";'
       '"Código do Favorecido";"Favorecido";"Natureza Jurídica";"Tipo Favorecido";"UF Favorecido";"Município Favorecido";"Valor Recebido"\n'
       '"1";"10";"FULANO DE TAL";"1";"Individual";"202503";"18.715.383/0001-40";"MUNICIPIO DE BELO HORIZONTE";"Município";"Pessoa Jurídica";"MG";"BELO HORIZONTE";"600,00"\n'
       '"2";"10";"FULANO DE TAL";"2";"Individual";"202504";"12.345.678/0001-95";"HOSPITAL X";"Associação Privada";"Pessoa Jurídica";"MG";"CONTAGEM";"500,00"\n'
       '"2";"10";"FULANO DE TAL";"2";"Individual";"202404";"12.345.678/0001-95";"HOSPITAL X";"Associação Privada";"Pessoa Jurídica";"MG";"CONTAGEM";"9,00"\n')
POLITICOS = [{"id": "dep-1", "nome": "Fulano de Tal", "partido": "AAA", "uf": "MG", "casa": "camara", "foto": ""}]
EXTRAS = [{"nome": "Beltrana Silva", "partido": "BBB", "uf": "MG", "casa": "camara"}]


def _zip(tmp_path):
    z = tmp_path / "EmendasParlamentares.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("EmendasParlamentares.csv", ("\n".join([CAB] + LINHAS) + "\n").encode("latin-1"))
        f.writestr("EmendasParlamentares_PorFavorecido.csv", FAV.encode("latin-1"))
        f.writestr("EmendasParlamentares_Convenios.csv", "a;b\n1;2\n")
    return z


def test_colunas_sem_confundir_pago_com_restos():
    col = emendas.achar_colunas(CAB.replace('"', "").split(";"), emendas.REGRAS)
    assert col["pago"] == "Valor Pago" and col["rap_pago"] == "Valor Restos A Pagar Pagos"
    assert col["codigo"] == "Código da Emenda" and col["autor"] == "Nome do Autor da Emenda"
    assert col["funcao"] == "Nome Função" and col["uf"] == "UF"


def test_local():
    col = emendas.achar_colunas(["Localidade de aplicação do recurso", "Município", "UF"], emendas.REGRAS)
    assert emendas.local_de({"Localidade de aplicação do recurso": "SÃO PAULO - SP"}, col) == ("municipio", "SÃO PAULO", "SP")
    assert emendas.local_de({"Localidade de aplicação do recurso": "PARÁ (UF)"}, col) == ("estado", "", "PA")
    assert emendas.local_de({"Localidade de aplicação do recurso": "Nacional"}, col)[0] == "nacional"


def test_resumo(tmp_path):
    z = _zip(tmp_path)
    r = emendas.resumir(emendas.linhas(z, ""), [2025], POLITICOS, EXTRAS)[2025]
    assert r["total"] == {"empenhado": 12500.0, "pago": 4200.0, "n": 4}
    fulano = next(a for a in r["autores"] if a["politico"] == "dep-1")
    assert fulano["pago"] == 1200.0 and fulano["pix"] == 500.0 and fulano["partido"] == "AAA" and fulano["n"] == 2
    assert dict(fulano["areas"])[emendas.SEM_AREA_PIX] == 500.0
    beltrana = next(a for a in r["autores"] if a["nome"] == "Beltrana Silva")
    assert beltrana["partido"] == "BBB" and beltrana["politico"] is None  # não é parlamentar atual: sem página, mas com partido
    assert [c["tipo"] for c in r["coletivos"]] == ["bancada"]
    assert {p["sigla"] for p in r["partidos"]} == {"AAA", "BBB"}
    assert r["municipios"][0] == {"nome": "Belo Horizonte", "uf": "MG", "empenhado": 1000.0, "pago": 700.0, "n": 1}
    assert {u["uf"]: u["empenhado"] for u in r["por_uf"]}["MG"] == 3500.0


def test_favorecidos(tmp_path):
    f = emendas.favorecidos(emendas.linhas(_zip(tmp_path), "favorecido"), [2024, 2025])
    assert f[2025]["total"] == 1100.0 and f[2025]["lista"][0]["doc"] == "18715383000140"
    assert f[2024]["lista"][0]["nome"] == "Hospital X"


def test_coletar_grava_arquivos(tmp_path, monkeypatch):
    z = _zip(tmp_path)
    monkeypatch.setattr(emendas, "baixar", lambda cache: z)
    monkeypatch.setattr(emendas, "deputados_legislatura", lambda leg: EXTRAS)
    emendas.coletar(POLITICOS, [2024, 2025], tmp_path / "c", tmp_path / "out")
    ind = json.loads((tmp_path / "out" / "emendas" / "anos.json").read_text())
    assert ind["anos"] == [2025]
    d = json.loads((tmp_path / "out" / "emendas" / "2025.json").read_text())
    assert d["favorecidos"]["lista"][0]["valor"] == 600.0
