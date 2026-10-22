"""Testes com dados fictícios mínimos (apenas para testar o código, nunca exibidos no site)."""
import json
import random

from sa_etl import camara, senado, ideologia, cnpj, recursos
from sa_etl.build import montar
from sa_etl.categorias import grupo_de
from sa_etl.util import cnpj_valido, read_csv_text, to_float, mask_cpf


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
    assert p["total"] == 4500.5 and p["anos"]["2025"]["grupos"]["servicos"] == 3000 and p["por_ano"]["2025"]["custo_total"] == 4500.5
    e = json.loads((tmp_path / "e" / "22222222000122.json").read_text())
    assert e["socios"][0]["nome"] == "Maria"
    assert any("dias antes" in a for a in e["alertas"])
    assert json.loads((tmp_path / "votacoes.json").read_text())[0]["sim"] == 1


def test_senado_usa_voto_do_lider_como_orientacao():
    items = [{"codigoSessaoVotacao": 3, "votacaoSecreta": "N", "votos": [
        {"codigoParlamentar": 5, "siglaVotoParlamentar": "Não", "nomeParlamentar": senado.LIDER_GOVERNO_SENADO}]}]
    v, _ = senado.parse_votacoes(items, {"sen-5"})
    assert v[0]["orientacoes"] == {"Governo (voto do líder)": "Não"}


def test_cota_usa_idecadastro():
    csv_ = '"ideCadastro";"nuDeputadoId";"txtDescricao";"vlrLiquido";"numAno";"numMes"\n"204379";"3001";"TELEFONIA";"10";"2025";"1"\n'
    rows = camara.parse_cota(read_csv_text(csv_), {"dep-204379"})
    assert rows and rows[0]["politico"] == "dep-204379"


def test_cnpj_valido():
    assert cnpj_valido("33.683.111/0001-07")
    assert not cnpj_valido("00000000000001")
    assert not cnpj_valido("33683111000108")


RESUMO_CAMARA = """<main><h3>Cota parlamentar <a>?</a></h3><table><tr><td>Gasto</td><td>463.434,64</td><td>87%</td></tr>
<tr><td>Não utilizado</td><td>10,00</td><td>13%</td></tr></table><p>Gasto mensal</p><table><tr><td>JAN</td><td>1.000,00</td></tr></table>
<h3>Verba de gabinete <a>?</a></h3><table><tr><td>Gasto</td><td>1.275.362,63</td><td>80.19%</td></tr>
<tr><td>Não utilizado</td><td>314.992,00</td><td>19.81%</td></tr></table><p>Gasto mensal</p>
<table><tr><td>JAN</td><td>90.210,79</td><td>71.89%</td></tr><tr><td>FEV</td><td>99.718,07</td><td>74.88%</td></tr></table>
<h3>Pessoal de gabinete <a>?</a></h3> <a> 18 pessoas </a>
<h3>Salário mensal bruto <a>? </a></h3> <a>R$ 46.366,19</a>
<h3>Imóvel funcional <a>?</a></h3> <span> Faz uso desde 09/03/2023 </span>
<h3>Auxílio-moradia <a>?</a></h3> <span> Não recebe o auxílio </span>
<h3>Viagens em missão oficial <a>?</a></h3> <a>1</a>
<h3>Passaporte diplomático <a>?</a></h3> <a> Possui </a></main>"""


def test_resumo_camara():
    r = recursos.parse_camara_resumo(RESUMO_CAMARA)
    assert r["cota_oficial"] == 463434.64
    assert r["verba_gasto"] == 1275362.63 and r["verba_disponivel"] == 1590354.63
    assert r["verba_meses"] == [{"mes": 1, "valor": 90210.79}, {"mes": 2, "valor": 99718.07}]
    assert r["n_pessoal"] == 18 and r["salario_bruto"] == 46366.19
    assert r["imovel_funcional"] == "Faz uso desde 09/03/2023"
    assert r["auxilio_moradia"] == "Não recebe o auxílio"
    assert r["viagens_missao"] == 1 and r["passaporte_diplomatico"] == "Possui"


def test_pessoal_e_salario_camara():
    h = """<table><thead><tr><th>Nome</th></tr></thead><tbody><tr><td>ALINE MARIA</td><td>SECRETÁRIO PARLAMENTAR</td>
    <td>SP15</td><td>De 19/02/2025 a 17/02/2026</td><td><a>Consultar</a></td></tr></tbody></table>"""
    assert recursos.parse_camara_pessoal(h) == [{"nome": "ALINE MARIA", "grupo": "Secretário parlamentar", "cargo": "SP15",
                                                 "periodo": "De 19/02/2025 a 17/02/2026"}]
    s = "<table><tbody><tr><td>01</td><td><a> 44.008,52 </a></td></tr><tr><td>02</td><td><a> 46.366,191 </a></td></tr></tbody></table>"
    assert recursos.parse_camara_remuneracao(s) == [{"mes": 1, "valor": 44008.52}, {"mes": 2, "valor": 46366.19}]


def test_senado_recursos():
    d = {"data": [{"cotas": {"totalValor": 488073.13}, "gastosNaoInclusos": {"despesas": [
        {"recurso": "Correios", "valor": 41254.35}, {"recurso": "X", "valor": 0}], "totalValor": 41254.35},
        "beneficios": [{"beneficio": "Auxílio-Moradia", "utilizacao": "Utilizou"}],
        "pessoal": [{"local": "Gabinete", "quantidade": 41, "vinculos": [{"vinculo": "Comissionado", "quantidade": 38}]}]}]}
    r = recursos.parse_senado_json(d)
    assert r["cota_oficial"] == 488073.13 and r["outros_total"] == 41254.35 and len(r["outros_gastos"]) == 1
    assert r["n_pessoal"] == 41 and r["beneficios"][0]["utilizacao"] == "Utilizou"
    h = """<table> <caption>Funcionários Comissionados</caption> <thead><tr><th>F</th></tr></thead> <tbody>
    <tr><td><a><span>ELIA SANTOS</span></a></td><td>SF02</td><td>ASSESSOR PARLAMENTAR</td></tr></tbody></table>"""
    assert recursos.parse_senado_pessoal(h) == [{"nome": "ELIA SANTOS", "grupo": "Comissionados", "cargo": "Assessor parlamentar (SF02)", "periodo": ""}]


def test_mesmo_endereco():
    end = {"cep": "30.140-010", "numero": "100", "complemento": "Sala 2"}
    emps = {"11111111000111": {"endereco": end}, "11111111000222": {"endereco": end},  # filial: mesma empresa
            "22222222000122": {"endereco": dict(end, complemento="SALA 2")},
            "33333333000133": {"endereco": dict(end, numero="S/N")}}
    g = cnpj.mesmo_endereco(emps)
    assert list(g.values()) == [["11111111000111", "11111111000222", "22222222000122"]]
    assert cnpj.mesmo_endereco({"11111111000111": {"endereco": end}, "11111111000222": {"endereco": end}}) == {}


def test_montar_marca_mesmo_endereco(tmp_path):
    pols = [{"id": "dep-1", "casa": "camara", "cargo": "Deputado(a) Federal", "nome": "Fulano", "partido": "AAA",
             "uf": "SP", "foto": "", "fonte": ""}]
    desp = [{"politico": "dep-1", "ano": 2025, "mes": 1, "data": "2025-01-02", "categoria": "x", "grupo": "servicos",
             "fornecedor": f"E{c}", "doc": c, "valor": 5000.0, "url": ""} for c in ("11111111000111", "22222222000122")]
    end = {"cep": "30140010", "numero": "100", "complemento": ""}
    emps = {c: {"cnpj": c, "razao_social": f"E{c}", "situacao": "ATIVA", "abertura": "", "capital_social": 0,
                "endereco": end, "socios": [{"nome": "Ana", "doc": "***1**", "qualificacao": "", "entrada": ""}]}
            for c in ("11111111000111", "22222222000122")}
    montar({"politicos": pols, "despesas": desp, "votacoes": [], "votos": [], "empresas": emps,
            "recursos": {"dep-1": {2025: {"salario_ano": 100.0, "verba_gasto": 50.0}}}}, tmp_path, [2025])
    e = json.loads((tmp_path / "e" / "11111111000111.json").read_text())
    assert e["mesmo_endereco"] == [{"cnpj": "22222222000122", "nome": "E22222222000122", "total": 5000.0, "mesmos_socios": True}]
    assert any("mesmo endereço" in a for a in e["alertas"])
    assert e["n_notas"] == 1 and e["notas_por_ano"] == {"2025": 1}
    notas = json.loads((tmp_path / "e" / "notas" / "11111111000111-2025.json").read_text())
    assert notas == [["2025-01-02", "dep-1", "x", 5000.0, "", "", ""]]
    assert e["por_mes"] == [{"politico": "dep-1", "nome": "Fulano", "ano": 2025, "mes": 1, "valor": 5000.0}]
    p = json.loads((tmp_path / "politicos.json").read_text())[0]
    assert p["por_ano"]["2025"]["custo_total"] == 10150.0
    part = json.loads((tmp_path / "partidos.json").read_text())[0]
    assert part["por_ano"]["2025"]["cota_por_membro"] == 10000.0


def test_completa_com_valor_oficial():
    from sa_etl.build import completar_com_oficial, SEM_NOTA
    pols = [{"id": "dep-1", "casa": "camara"}]
    desp = [{"politico": "dep-1", "ano": 2025, "mes": 8, "valor": 100.0}]
    rec = {"dep-1": {2025: {"cota_meses": [{"mes": 8, "valor": 150.0}, {"mes": 9, "valor": 20.0}]}}}
    out = completar_com_oficial(desp, pols, rec)
    extra = [d for d in out if d.get("sem_nota")]
    assert [(d["mes"], d["valor"], d["categoria"]) for d in extra] == [(8, 50.0, SEM_NOTA), (9, 20.0, SEM_NOTA)]
    assert recursos.parse_camara_resumo(RESUMO_CAMARA)["cota_meses"] == [{"mes": 1, "valor": 1000.0}]


def test_temas():
    from sa_etl.temas import temas_de
    assert temas_de("Amplia o limite de faturamento do MEI") == ["Micro e pequenas empresas"]
    assert temas_de("Dispõe sobre o meio ambiente") == ["Meio ambiente"]
    assert "Mulheres" in temas_de("Altera a Lei Maria da Penha")
    assert temas_de("Denomina viaduto") == []


def test_salario_de_senador_usa_subsidio():
    from sa_etl.build import salario_senadores
    pols = [{"id": "dep-1", "casa": "camara"}, {"id": "dep-2", "casa": "camara"}, {"id": "sen-1", "casa": "senado"}]
    rec = {"dep-1": {2025: {"salario_meses": [{"mes": 1, "valor": 100.0}]}},
           "dep-2": {2025: {"salario_meses": [{"mes": 1, "valor": 100.0}]}}, "sen-1": {2025: {"cota_oficial": 5}}}
    out = salario_senadores(pols, rec)
    assert out["sen-1"][2025]["salario_ano"] == 100.0 and out["sen-1"][2025]["cota_oficial"] == 5


def test_fora_do_periodo_oficial():
    from sa_etl.build import fora_do_periodo_oficial
    ds = [{"mes": 1, "valor": 100.0}, {"mes": 2, "valor": 50.0}, {"mes": 7, "valor": -30.0}]
    r = {"cota_meses": [{"mes": 2, "valor": 50.0}]}
    assert fora_do_periodo_oficial(ds, r) == {"fora_do_periodo": 70.0, "meses_fora": [1, 7]}
    assert fora_do_periodo_oficial(ds, {}) == {}


def test_donos_finais_segue_holdings():
    todas = {
        "11111111000111": {"razao_social": "GRAFICA", "socios": [
            {"nome": "HOLDING X LTDA", "doc": "22222222000122", "qualificacao": "Sócio"},
            {"nome": "ANA", "doc": "***111111**", "qualificacao": "Sócio"}]},
        "22222222000122": {"razao_social": "HOLDING X LTDA", "socios": [
            {"nome": "HOLDING Y SA", "doc": "33333333000133", "qualificacao": "Sócio"},
            {"nome": "BETO", "doc": "***222222**", "qualificacao": "Sócio-Administrador"},
            {"nome": "FOREIGN CORP", "doc": "", "qualificacao": "Sócio Pessoa Jurídica Domiciliado no Exterior", "tipo": "estrangeiro"}]},
        "33333333000133": {"razao_social": "HOLDING Y SA", "socios": [
            {"nome": "HOLDING X LTDA", "doc": "22222222000122", "qualificacao": "Sócio"}]},  # ciclo
        "44444444000144": {"razao_social": "OUTRA", "socios": [{"nome": "BETO", "doc": "***222222**"}]},
    }
    d = cnpj.donos_finais("11111111000111", todas)
    por_nome = {x["nome"]: x for x in d}
    assert por_nome["ANA"]["cadeia"] == [] and por_nome["ANA"]["fim"] == "pessoa"
    assert [c["nome"] for c in por_nome["BETO"]["cadeia"]] == ["HOLDING X LTDA"]
    assert por_nome["FOREIGN CORP"]["fim"] == "estrangeiro"
    assert any(x["fim"] == "ciclo" for x in d)
    # a outra empresa do Beto aparece ligada à gráfica, através da holding
    comuns = cnpj.socios_em_comum({k: todas[k] for k in ("11111111000111", "44444444000144")},
                                  {k: todas[k] for k in ("22222222000122", "33333333000133")})
    assert ["11111111000111", "44444444000144"] in comuns.values()


def test_buscar_socias_busca_por_niveis(tmp_path, monkeypatch):
    base = {"22222222000122": {"razao_social": "H1", "socios": [{"nome": "H2", "doc": "33333333000133"}]},
            "33333333000133": {"razao_social": "H2", "socios": [{"nome": "ZE", "doc": "***1**"}]}}
    monkeypatch.setattr(cnpj, "_fetch", lambda c, cache: base.get(c))
    emps = {"1": {"socios": [{"nome": "H1", "doc": "22222222000122"}]}}
    assert set(cnpj.buscar_socias(emps, tmp_path)) == {"22222222000122", "33333333000133"}


def test_socio_empresa_so_com_raiz_do_cnpj():
    s = {"nome": "AEROTUR HOLDING LTDA", "doc": "07575651", "qualificacao": "Sócio"}
    assert cnpj.tipo_socio(s) == "empresa"
    assert cnpj.cnpj_socio(s) == "07575651000159"  # matriz, com dígitos verificadores
    todas = {"11111111000111": {"razao_social": "A", "socios": [s]},
             "07575651000159": {"razao_social": "AEROTUR HOLDING LTDA", "socios": [{"nome": "ZE", "doc": "***123456**"}]}}
    d = cnpj.donos_finais("11111111000111", todas)
    assert d[0]["nome"] == "ZE" and d[0]["cadeia"][0]["cnpj"] == "07575651000159"


LISTA_HTML = """<table><thead><tr><th>Fornecedor</th></tr></thead><tbody>
<tr><td>LATAM Airlines Brasil</td><td>02.012.862/0001-60</td><td>15/10/2025</td><td>9572255027892</td>
<td>R$3.019,06</td><td></td><td>R$3.019,06</td>
<td><a href="/cota-parlamentar/documento?nuDeputadoId=2227&amp;
		numMes=10&amp;numAno=2025&amp;despesa=998&amp;cnpjFornecedor=02012862000160&amp;idDocumento=9572255027892&amp;idDocumentoFiscal=D4A9">detalhe</a></td></tr>
<tr><td>Gol Linhas Aéreas</td><td>07.575.651/0001-59</td><td>11/11/2025</td><td>1272148920939</td>
<td>(R$2.186,27)</td><td></td><td>(R$2.186,27)</td><td><a href="/cota-parlamentar/documento?nuDeputadoId=2227&amp;numMes=11">detalhe</a></td></tr>
<tr><td>Total</td><td>R$5.047,83</td></tr></tbody></table>"""


def test_lista_oficial_de_passagens():
    from sa_etl import passagens
    r = passagens.parse_lista(LISTA_HTML)
    assert len(r) == 2
    assert r[0]["fornecedor"] == "LATAM Airlines Brasil" and r[0]["doc"] == "02012862000160"
    assert r[0]["data"] == "2025-10-15" and r[0]["numero"] == "9572255027892" and r[0]["valor"] == 3019.06
    assert r[0]["url"].startswith("https://www.camara.leg.br/cota-parlamentar/documento?nuDeputadoId=2227&numMes=10")
    assert "\t" not in r[0]["url"] and " " not in r[0]["url"]
    assert r[1]["valor"] == -2186.27  # devolução


def test_busca_passagens_sem_repetir_e_completa_o_resto(tmp_path, monkeypatch):
    from sa_etl import build, passagens
    monkeypatch.setattr(passagens, "_get_text", lambda url: LISTA_HTML)
    pols = [{"id": "dep-1", "casa": "camara"}]
    desp = [{"politico": "dep-1", "ano": 2025, "mes": 10, "valor": 3019.06, "nu": "2227", "num": "9572255027892"}]
    rec = {"dep-1": {2025: {"cota_meses": [{"mes": 10, "valor": 3019.06 + 500}]}}}
    novas = build.buscar_passagens(desp, pols, rec, tmp_path)
    assert [(n["num"], n["valor"], n["link"]) for n in novas] == [("1272148920939", -2186.27, "detalhe")]  # a LATAM já estava
    resto = build.completar_com_oficial(desp + novas, pols, rec)[-1]
    assert resto["sem_nota"] and resto["valor"] == 2686.27 and "sumarizado?nuDeputadoId=2227" in resto["url"]


def test_links_oficiais_das_notas():
    from sa_etl.camara import link_detalhe
    from sa_etl.senado import link_lista
    u = link_detalhe("2227", 2025, 1, "10", "66.970.229/0018-05", "0013648685", "7867324")
    assert u == ("https://www.camara.leg.br/cota-parlamentar/documento?nuDeputadoId=2227&numMes=1&numAno=2025"
                 "&despesa=10&cnpjFornecedor=66970229001805&idDocumento=0013648685&idDocumentoFiscal=7867324")
    assert "/sen/6008/ceaps/8/?ano=2025" in link_lista(6008, "Passagens aéreas, aquáticas e terrestres nacionais", 2025)


def test_passagens_nunca_passam_do_total_oficial(tmp_path, monkeypatch):
    from sa_etl import build, passagens
    monkeypatch.setattr(passagens, "_get_text", lambda url: LISTA_HTML)
    pols = [{"id": "dep-1", "casa": "camara"}]
    # O bilhete da LATAM já está nos dados abertos, mas em outro mês e com zeros à esquerda: não entra de novo.
    desp = [{"politico": "dep-1", "ano": 2025, "mes": 9, "valor": 3019.06, "nu": "2227", "num": "0009572255027892"}]
    rec = {"dep-1": {2025: {"cota_meses": [{"mes": 9, "valor": 3019.06}, {"mes": 10, "valor": 50}]}}}
    novas = build.buscar_passagens(desp, pols, rec, tmp_path / "a")
    assert [n["num"] for n in novas] == ["1272148920939"]
    # Sem nada nos dados abertos e com pouca diferença, a lista passaria do total oficial: não é usada.
    rec = {"dep-1": {2025: {"cota_meses": [{"mes": 10, "valor": 50}]}}}
    desp = [{"politico": "dep-1", "ano": 2025, "mes": 9, "valor": 10, "nu": "2227", "num": "1"}]
    assert build.buscar_passagens(desp, pols, rec, tmp_path / "b") == []
