"""Testes com dados fictícios mínimos (apenas para testar o código, nunca exibidos no site)."""
import json
import random

from sa_etl import camara, senado, ideologia, cnpj
from sa_etl.build import montar
from sa_etl.categorias import grupo_de
from sa_etl.util import read_csv_text, to_float, mask_cpf


def test_grupos():
    assert grupo_de("PASSAGEM AÉREA - SIGEPA") == "pessoal"
    assert grupo_de("COMBUSTÍVEIS E LUBRIFICANTES.") == "pessoal"
    assert grupo_de("DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.") == "servicos"
    assert grupo_de("MANUTENÇÃO DE ESCRITÓRIO DE APOIO À ATIVIDADE PARLAMENTAR") == "escritorio"


def test_numeros_e_cpf():
    assert to_float("1.234,56") == 1234.56
    assert to_float("1234.56") == 1234.56
    assert mask_cpf("123.456.789-01") == "***.456.789-**"


COTA = '''"txNomeParlamentar";"cpf";"ideCadastro";"sgUF";"sgPartido";"txtDescricao";"txtFornecedor";"txtCNPJCPF";"datEmissao";"vlrLiquido";"numMes";"numAno";"nuDeputadoId";"urlDocumento"
"Fulano";"1";"1";"SP";"AAA";"PASSAGEM AÉREA - SIGEPA";"Cia Aérea";"11.111.111/0001-11";"2025-03-01T00:00:00";"1500.50";"3";"2025";"1";""
"Fulano";"1";"1";"SP";"AAA";"DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.";"Gráfica";"22222222000122";"2025-04-01T00:00:00";"3000";"4";"2025";"1";""
"Outro";"9";"9";"RJ";"BBB";"DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.";"Gráfica";"22222222000122";"2025-04-01T00:00:00";"999";"4";"2025";"9";""
'''


def test_parse_cota_filtra_e_converte():
    rows = camara.parse_cota(read_csv_text(COTA), {"dep-1"})
    assert len(rows) == 2
    assert rows[0]["grupo"] == "pessoal" and rows[0]["valor"] == 1500.5
    assert rows[1]["doc"] == "22222222000122"


def test_parse_ceaps():
    rows = senado.parse_ceaps([{"codSenador": 5, "ano": 2026, "mes": 1, "tipoDespesa": "Locomoção, hospedagem",
                                "cpfCnpj": "02.964.380/0001-00", "fornecedor": "X", "data": "2026-01-07",
                                "valorReembolsado": 10}], {"sen-5"})
    assert rows[0]["doc"] == "02964380000100" and rows[0]["grupo"] == "pessoal"


def test_votacoes_senado_ignora_secreta():
    items = [{"codigoSessaoVotacao": 1, "votacaoSecreta": "S", "votos": [{"codigoParlamentar": 5, "siglaVotoParlamentar": "Votou"}]},
             {"codigoSessaoVotacao": 2, "votacaoSecreta": "N", "dataSessao": "2026-09-01", "sigla": "PL", "numero": "1",
              "ano": 2026, "resultadoVotacao": "A",
              "votos": [{"codigoParlamentar": 5, "siglaVotoParlamentar": "Sim", "siglaPartidoParlamentar": "AAA"}]}]
    v, vs = senado.parse_votacoes(items, {"sen-5"})
    assert [x["id"] for x in v] == ["sf-2"] and vs[0]["voto"] == "Sim"


def test_posicoes_separa_dois_blocos():
    random.seed(1)
    votos, partido = [], {}
    for i in range(40):
        p = f"dep-{i}"
        partido[p] = "PL" if i < 20 else "PT"
        for j in range(30):
            lado = (i < 20) == (j % 2 == 0)
            if random.random() < 0.05:
                lado = not lado
            votos.append({"politico": p, "votacao": f"v{j}", "voto": "Sim" if lado else "Não"})
    pos = ideologia.posicoes(votos, partido)
    assert sum(pos[f"dep-{i}"] for i in range(20)) > 0 > sum(pos[f"dep-{i}"] for i in range(20, 40))


def test_socios_em_comum():
    emps = {"1": {"socios": [{"nome": "Maria Silva", "doc": "***123456**"}]},
            "2": {"socios": [{"nome": "MARIA SILVA", "doc": "***123456**"}]},
            "3": {"socios": [{"nome": "Maria Silva", "doc": "***999999**"}]}}
    assert cnpj.socios_em_comum(emps) == {"MARIA SILVA|***123456**": ["1", "2"]}


def test_montar_gera_arquivos(tmp_path):
    pols = [{"id": "dep-1", "casa": "camara", "cargo": "Deputado(a) Federal", "nome": "Fulano", "partido": "AAA",
             "uf": "SP", "foto": "", "fonte": ""}]
    desp = camara.parse_cota(read_csv_text(COTA), {"dep-1"})
    votac = [{"id": "cd-1", "casa": "camara", "data": "2025-05-01", "descricao": "Teste", "aprovada": True,
              "proposicao": None, "orientacoes": {"Governo": "Sim"}, "fonte": ""}]
    votos = [{"votacao": "cd-1", "politico": "dep-1", "voto": "Sim", "partido": "AAA"}]
    emps = {"22222222000122": {"cnpj": "22222222000122", "razao_social": "GRAFICA LTDA", "situacao": "ATIVA",
                               "abertura": "2025-03-01", "capital_social": 1000, "socios": [
                                   {"nome": "Maria", "doc": "***1**", "qualificacao": "Sócio", "entrada": ""}]}}
    montar({"politicos": pols, "despesas": desp, "votacoes": votac, "votos": votos, "empresas": emps}, tmp_path, [2025])
    p = json.loads((tmp_path / "p" / "dep-1.json").read_text())
    assert p["total"] == 4500.5 and p["grupos"]["servicos"] == 3000
    e = json.loads((tmp_path / "e" / "22222222000122.json").read_text())
    assert e["socios"][0]["nome"] == "Maria"
    assert any("dias antes" in a for a in e["alertas"])
    assert json.loads((tmp_path / "votacoes.json").read_text())[0]["sim"] == 1
