"""Página de incentivos: pagamentos do governo federal a empresas e entidades, renúncia fiscal e quem deu mais."""
import datetime as dt
import gzip
import json
import zipfile

from fakegov import FakeGov
from sa_etl import pagamentos, renuncias

IMP = ('"Código Pagamento";"Código Empenho";"Código Natureza Despesa Completa";"Subitem";"Valor Pago (R$)";'
       '"Valor Restos a Pagar Pagos (R$)"\n'
       '"OB1";"NE1";"33903900";"00";"1.000,00";"0,00"\n'
       '"OB1";"NE2";"33904500";"00";"0,00";"500,00"\n'    # o mesmo pagamento quitou um subsídio (restos a pagar)
       '"OB2";"NE3";"31901100";"00";"9.999,00";"0,00"\n'   # folha de pagamento: não entra
       '"OB3";"NE4";"33903900";"00";"700,00";"0,00"\n'     # empresa pública
       '"OB4";"NE5";"33504100";"00";"300,00";"0,00"\n')    # convênio com entidade
PAG = ('"Código Pagamento";"Data Emissão";"Órgão Superior";"Código Favorecido";"Favorecido"\n'
       '"OB1";"02/01/2025";"Ministério A";"12.345.678/0001-95";"EMPRESA X LTDA"\n'
       '"OB2";"02/01/2025";"Ministério A";"12.345.678/0001-95";"EMPRESA X LTDA"\n'
       '"OB3";"02/01/2025";"Ministério A";"33.683.111/0002-80";"SERVICO FEDERAL DE PROCESSAMENTO DE DADOS SERPRO"\n'
       '"OB4";"02/01/2025";"Ministério B";"11.222.333/0001-81";"ASSOCIACAO Y"\n'
       '"OB5";"02/01/2025";"Ministério B";"123.456.789-09";"PESSOA"\n')


def _zip(path, arquivos):
    with zipfile.ZipFile(path, "w") as z:
        for nome, txt in arquivos.items():
            z.writestr(nome, txt.encode("latin-1"))
    return path


def test_categoria_pela_natureza_da_despesa():
    c = pagamentos.categoria_despesa
    assert c("33903900") == "contrato" and c("3.3.90.39.00") == "contrato" and c("44905100") == "contrato"
    assert c("33504100") == "repasse" and c("33604300") == "repasse" and c("33904500") == "subsidio"
    assert c("31901100") is None and c("32902100") is None and c("46907100") is None  # pessoal e dívida
    assert c("") == "outro" and c("33909300") == "outro"


def test_ler_geral_um_dia(tmp_path):
    d = pagamentos.ler_geral(_zip(tmp_path / "d.zip", {"x_Despesas_Pagamento_EmpenhosImpactados.csv": IMP,
                                                       "x_Despesas_Pagamento.csv": PAG}))
    assert set(d["f"]) == {"12345678000195", "11222333000181"}  # nem a estatal, nem CPF
    nome, cats, n, orgs = d["f"]["12345678000195"]
    assert nome == "EMPRESA X LTDA" and cats == {"contrato": 1000.0, "subsidio": 500.0} and n == 1  # folha fora
    assert {d["o"][int(i)]: v for i, v in orgs.items()} == {"Ministério A": 1500.0}
    assert d["f"]["11222333000181"][1] == {"repasse": 300.0}


def test_coletar_geral_do_mais_recente_e_resumir(tmp_path, monkeypatch):
    chamadas = []

    def baixar(dia, dest):
        chamadas.append(dia)
        if dia == "20250102":
            _zip(dest, {"x_Despesas_Pagamento_EmpenhosImpactados.csv": IMP, "x_Despesas_Pagamento.csv": PAG})
            return True
        return None
    monkeypatch.setattr(pagamentos, "_baixar_dia", baixar)
    hoje = dt.date(2025, 1, 20)
    arqs = pagamentos.coletar_geral([2025], tmp_path, hoje=hoje)
    assert chamadas[0] == "20250119" and chamadas[-1] == "20250101"  # do mais recente para o mais antigo, só o ano pedido
    assert len(arqs) == 19 - 5  # os 5 dias recentes sem arquivo podem aparecer depois
    chamadas.clear()
    pagamentos.coletar_geral([2025], tmp_path, hoje=hoje)
    assert len(chamadas) == 5
    r = pagamentos.resumir_geral(arqs, [2025], hoje=hoje)
    e = r["anos"][2025]["12345678000195"]
    assert e["valor"] == 1500.0 and e["cats"] == {"contrato": 1000.0, "subsidio": 500.0}
    cob = r["cobertura"][2025]
    assert cob["dias"] == 14 and cob["dias_ano"] == 19 and cob["completo"] and cob["ate"] == "2025-01-14"
    assert pagamentos.coletar_geral([2025], tmp_path / "novo", minutos=0, hoje=hoje) == []


def test_renuncia_ano_parcial_e_cnpj_invalido(tmp_path, monkeypatch):
    gov = FakeGov()
    for ano in (2024, 2025):
        (tmp_path / f"{ano}_RenunciasFiscais.zip").write_bytes(gov._renuncias_zip(ano))
    monkeypatch.setattr(renuncias, "download", lambda url, dest, **kw: dest if dest.exists() else (_ for _ in ()).throw(RuntimeError("403")))
    r = renuncias.coletar(tmp_path, 2026)
    assert sorted(r["anos"]) == [2024, 2025]
    a = r["anos"][2024]
    assert a["total"] == 1001000.0 and a["sem_cnpj"] == 1000.0 and a["n"] == 3  # o registro "-3" fica no total, fora da lista
    assert [x["valor"] for x in a["top"]] == [500000.0, 300000.0, 200000.0]
    assert a["top"][0]["beneficios"] == [["Sudene", 375000.0], ["Desoneração da folha", 125000.0]]
    assert {s["setor"] for s in a["por_setor"]} == {"Construção", "Indústria", "Transporte e correio", "Sem informação"}
    assert r["anos"][2025]["parcial"] and not a["parcial"]
    assert renuncias.cnpj_de("1.234.567/0001-95") == "01234567000195" and renuncias.cnpj_de("-3") == ""


def test_pagina_de_incentivos_na_coleta(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    ce, assoc, publica, sem = gov.incentivo_empresas
    idx = coleta.ler(saida, "incentivos/indice.json")
    assert idx["anos"] == [2025] and [x["ano"] for x in idx["anos_renuncia"]] == [2024, 2025]
    d = coleta.ler(saida, "incentivos/2025.json")
    p = d["pagamentos"]
    docs = [x["cnpj"] for x in p["top"]]
    assert ce in docs and assoc in docs and publica not in docs  # estatal fica de fora (dinheiro dentro do governo)
    assert p["fora_publicos"] == 70000.0
    x = next(x for x in p["top"] if x["cnpj"] == ce)
    assert x["valor"] == 150000.0 and x["pagina"] and x["donos"] == ["DONO FICTICIO 3"] and x["n_outras"] >= 2
    assert next(x for x in p["top"] if x["cnpj"] == assoc)["tipo"] == "entidade"
    # quem deu: emendas pagas a empresas, por parlamentar, partido e estado
    em = d["emendas"]
    assert {x["sigla"] for x in em["partidos"]} == {"PL", "PT"} and em["total"] == 120000.0
    assert all(x["politico"] and x["uf"] for x in em["politicos"])
    # página da empresa: pagamentos, renúncia e as outras empresas do mesmo dono
    e = coleta.ler(saida, f"e/{ce}.json")
    assert e["governo"]["total"] == 150000.0 and e["renuncia"]["por_ano"] == {"2024": 500000.0, "2025": 250000.0}
    outras = {o["cnpj"]: o for o in e["socios"][0]["outras_empresas"]}
    assert gov.emenda_empresas[0] in outras and outras[gov.emenda_empresas[0]]["governo"] == 60999.0
    # e o caminho de volta: a construtora da emenda mostra a contratada como empresa do mesmo dono
    e2 = coleta.ler(saida, f"e/{gov.emenda_empresas[0]}.json")
    assert any(o["cnpj"] == ce and o["renuncia"] == 750000.0 for o in e2["socios"][0]["outras_empresas"])
    assert not (saida / "e" / f"{publica}.json").exists()
    assert coleta.validar(saida).erros == []


def test_portal_fora_do_ar_nao_derruba_o_site(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("/renuncias/", "parado").falhar("/download-de-dados/despesas/", "500")
    saida = coleta.rodar()
    meta = coleta.ler(saida, "meta.json")
    assert any("Renúncia fiscal" in a for a in meta["avisos"])
    idx = coleta.ler(saida, "incentivos/indice.json")
    assert idx["anos_renuncia"] == []
    assert coleta.validar(saida).erros == []


def test_resumo_geral_ignora_arquivo_com_defeito(tmp_path):
    bom = tmp_path / "20250102-geral-v1.json.gz"
    bom.write_bytes(gzip.compress(json.dumps({"f": {"12345678000195": ["X", {"contrato": 10}, 1, {"0": 10}]}, "o": ["M"]}).encode()))
    ruim = tmp_path / "20250103-geral-v1.json.gz"
    ruim.write_bytes(b"lixo")
    r = pagamentos.resumir_geral([bom, ruim], [2025], hoje=dt.date(2025, 1, 4))
    assert r["anos"][2025]["12345678000195"]["orgaos"] == {"M": 10} and r["cobertura"][2025]["dias"] == 1
