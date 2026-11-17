"""Histórico da cota desde 2008 (sa_etl/historico.py) e a página do deputado num ano sem mandato (recursos.py)."""
import datetime as dt
import json
import random

from sa_etl import historico, recursos, verificar
from sa_etl.validar import Resultado, _conferir_historico


def _linha(ide, mes, valor, cat="TELEFONIA", data="2015-01-10", doc=None, nome="FULANO", ano=2015):
    return {"ideCadastro": ide, "numAno": str(ano), "numMes": str(mes), "vlrLiquido": str(valor),
            "vlrDocumento": str(doc if doc is not None else valor), "txtDescricao": cat, "datEmissao": data,
            "txNomeParlamentar": nome, "sgUF": "MG", "sgPartido": "PT"}


def test_resumo_camara_soma_por_deputado_mes_e_tipo():
    linhas = [
        _linha("10", 1, 100), _linha("10", 1, 50, cat="DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR."),
        _linha("10", 2, 30, data=""),  # telefonia sem data: fora da API
        _linha("20", 3, -200, cat="COMPLEMENTAÇÃO DO AUXÍLIO-MORADIA", doc=200),  # sinal trocado no arquivo
        _linha("", 3, 70, nome="LIDERANÇA DO PT"),  # liderança: no total da Casa, fora dos deputados
        _linha("10", 5, 999, ano=2014),  # outro ano no mesmo arquivo: fora
    ]
    r = historico.resumir_camara(linhas, 2015)
    assert r["total"] == 450 and r["notas"] == 5
    assert r["fora_parlamentares"] == 70
    p = r["pessoas"]["dep-10"]
    assert p["total"] == 180 and p["por_mes"] == {"1": 150, "2": 30} and p["sem_data"] == {"2": 30}
    assert r["pessoas"]["dep-20"]["total"] == 200
    assert r["meses"] == {"1": 150, "2": 30, "3": 270}
    # o ponto final do nome do tipo não separa o mesmo tipo em dois
    assert "Divulgação da atividade parlamentar" in r["categorias"]


def test_resumo_senado():
    linhas = [{"ano": 2012, "mes": 3, "codSenador": 5, "nomeSenador": "BELTRANA", "tipoDespesa": "Aluguel", "valorReembolsado": 10.5},
              {"ano": 2012, "mes": 4, "codSenador": 5, "nomeSenador": "BELTRANA", "tipoDespesa": "Aluguel", "valorReembolsado": 4.5}]
    r = historico.resumir_senado(linhas, 2012)
    assert r["total"] == 15 and r["pessoas"]["sen-5"]["por_mes"] == {"3": 10.5, "4": 4.5}


def _resumos():
    r1 = json.loads(json.dumps(historico.resumir_camara([_linha("10", m, 1000) for m in range(1, 13)]
                                                        + [_linha("11", m, 500) for m in range(1, 13)], 2015)))
    r2 = json.loads(json.dumps(historico.resumir_camara([_linha("10", 1, 10, ano=2016)], 2016)))
    r3 = json.loads(json.dumps(historico.resumir_senado([{"ano": 2015, "mes": 1, "codSenador": 5, "nomeSenador": "B",
                                                          "tipoDespesa": "Aluguel", "valorReembolsado": 100}], 2015)))
    return [r1, r2, r3]


def test_montar_grava_totais_que_a_validacao_aceita(tmp_path):
    idx = {f"2015{m:02d}": 100.0 for m in range(1, 13)} | {f"2016{m:02d}": 110.0 for m in range(1, 13)}
    resumos = _resumos()
    assert historico.dar_uf_senado(resumos, {"sen-5": "MG"}) == 0
    out = historico.montar(resumos, idx, tmp_path, hoje=dt.date(2026, 11, 10))
    cam15 = next(x for x in out["anos"] if x["ano"] == 2015 and x["casa"] == "camara")
    assert cam15["total"] == 18000 and cam15["parlamentares"] == 2 and cam15["por_parlamentar"] == 9000
    assert cam15["total_hoje"] == 19800  # 10% de inflação até o último mês com IPCA
    cam16 = next(x for x in out["anos"] if x["ano"] == 2016 and x["casa"] == "camara")
    assert cam16["poucas_notas"] is True  # R$ 10 por deputado, contra R$ 9.000 no ano anterior
    h = json.loads((tmp_path / "h" / "dep-10.json").read_text())
    assert h["anos"]["2015"]["total"] == 12000 and h["anos"]["2015"]["total_hoje"] == 13200 and h["total"] == 12010
    assert out["maiores"]["camara"][0]["id"] == "dep-10"
    r = Resultado()
    _conferir_historico(tmp_path, r)
    assert r.erros == [] and r.alertas == ["Histórico da cota: 2016 só tem camara", "Histórico da cota de MG: 2016 só tem camara"]
    # a bancada de MG: os dois deputados e o senador (o estado do senador veio da lista da legislatura)
    mg = json.loads((tmp_path / "historico-uf" / "MG.json").read_text())
    assert mg["uf"] == "MG" and mg["fontes"] == out["fontes"]
    sen15 = next(x for x in mg["anos"] if x["ano"] == 2015 and x["casa"] == "senado")
    assert sen15["total"] == 100 and sen15["parlamentares"] == 1 and sen15["categorias"] == {"Aluguel": 100}
    assert next(x for x in mg["anos"] if x["ano"] == 2015 and x["casa"] == "camara")["total_hoje"] == 19800
    assert mg["maiores"]["senado"][0]["id"] == "sen-5"


def test_bancada_so_com_os_anos_no_estado_e_parlamentar_sem_estado_avisa(tmp_path):
    """Quem foi eleito por outro estado entra só nos anos daquele estado; senador sem estado sai dos estados e a
    conferência avisa (não some calado)."""
    r1 = historico.resumir_camara([_linha("10", 1, 100)] + [{**_linha("11", 1, 40), "sgUF": "SP"}], 2015)
    r2 = historico.resumir_camara([{**_linha("10", 1, 70, ano=2016), "sgUF": "SP"}], 2016)
    r3 = historico.resumir_senado([{"ano": 2015, "mes": 1, "codSenador": 5, "nomeSenador": "B", "tipoDespesa": "Aluguel",
                                    "valorReembolsado": 9}], 2015)
    resumos = json.loads(json.dumps([r1, r2, r3]))
    assert historico.dar_uf_senado(resumos, {}) == 1
    historico.montar(resumos, {}, tmp_path)
    mg = json.loads((tmp_path / "historico-uf" / "MG.json").read_text())
    assert [(x["ano"], x["casa"], x["total"]) for x in mg["anos"]] == [(2015, "camara", 100)]
    assert mg["maiores"]["camara"] == [{**mg["maiores"]["camara"][0], "id": "dep-10", "total": 100, "anos": 1}]
    r = Resultado()
    _conferir_historico(tmp_path, r)
    assert r.erros == []
    assert "Histórico senado 2015: 9.00 reais de parlamentares sem estado (fora dos estados)" in r.alertas


def test_estado_dos_senadores_pela_lista_da_legislatura(tmp_path, monkeypatch):
    pedidos = []

    def get_json(url, params=None, **kw):
        pedidos.append(url)
        leg = int(url.rsplit("/", 1)[1].removesuffix(".json"))
        return {"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
            {"IdentificacaoParlamentar": {"CodigoParlamentar": "5", "UfParlamentar": "SP"},
             "Mandatos": {"Mandato": [{"UfParlamentar": "MG", "PrimeiraLegislaturaDoMandato": {"NumeroLegislatura": str(leg)}}]}},
            {"IdentificacaoParlamentar": {"CodigoParlamentar": "7", "UfParlamentar": "BA"}},
            {"IdentificacaoParlamentar": {"NomeParlamentar": "sem código", "UfParlamentar": "AL"}}]}}}
    monkeypatch.setattr(historico, "get_json", get_json)
    ufs = historico.ufs_senadores(tmp_path, [2015, 2016], hoje=dt.date(2026, 11, 10))
    assert ufs == {"sen-5": "MG", "sen-7": "BA"}  # a UF do mandato vale mais que a de hoje
    assert len(pedidos) == 2  # 54ª (2011-2015) e 55ª (2015-2019)
    historico.ufs_senadores(tmp_path, [2015, 2016], hoje=dt.date(2026, 11, 10))
    assert len(pedidos) == 2  # legislatura passada: a cópia vale 30 dias


def test_validacao_acusa_total_que_nao_bate(tmp_path):
    historico.montar(_resumos(), {}, tmp_path)
    d = json.loads((tmp_path / "historico.json").read_text())
    d["anos"][0]["total"] += 500
    (tmp_path / "historico.json").write_text(json.dumps(d))
    r = Resultado()
    _conferir_historico(tmp_path, r)
    assert any("diferente da soma dos parlamentares" in e for e in r.erros)


def test_anos_da_coleta_principal_usam_o_numero_do_perfil(tmp_path):
    """Desde agosto de 2025 o arquivo anual não traz as passagens compradas pela Câmara; o perfil traz."""
    res = _resumos()
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "dep-10.json").write_text(json.dumps({"nome": "Fulano", "anos": {"2015": {
        "meses": [{"mes": m, "valor": 1100.0 if m == 1 else 1000.0} for m in range(1, 13)],
        "categorias": [{"categoria": "Telefonia", "valor": 11000.0}, {"categoria": "Passagem aérea (comprada pela Câmara)", "valor": 1100.0}]}}}))
    assert historico.usar_numeros_do_site(res, tmp_path) == 1
    cam15 = res[0]
    assert cam15["total"] == 18100 and cam15["meses"]["1"] == 1600
    assert cam15["categorias"]["Passagem aérea (comprada pela Câmara)"] == 1100
    historico.montar(res, {}, tmp_path)
    h = json.loads((tmp_path / "h" / "dep-10.json").read_text())
    assert h["anos"]["2015"]["do_site"] is True and h["anos"]["2015"]["total"] == 12100
    r = Resultado()
    _conferir_historico(tmp_path, r)
    assert r.erros == []


def test_verificacao_compara_so_os_meses_que_a_pagina_mostra(tmp_path):
    historico.montar(_resumos(), {}, tmp_path)
    paginas = {("10", 2015): [{"mes": m, "valor": 1000.0} for m in range(2, 13)],  # janeiro fora do mandato
               ("11", 2015): [{"mes": m, "valor": 500.0 if m != 7 else 480.0} for m in range(1, 13)]}
    verificar.AMOSTRAS["historico_camara_pagina"] = 10
    c = verificar.historico_camara_pagina(tmp_path, random.Random(1), verificar.Prazo(5), dt.date(2026, 11, 10),
                                          pagina=lambda num, ano: {"cota_meses": paginas.get((num, ano), [])})
    assert c.n == 11 + 12 and c.k == 1
    assert c.divergencias[0]["o_que"].endswith("07/2015") and c.divergencias[0]["oficial"] == 480.0
    assert any("não mostrou" in f for f in c.falhas)  # 2016: página sem gasto mensal


def test_pagina_de_ano_sem_mandato_e_ignorada(monkeypatch):
    """Pedido um ano sem mandato, a Câmara mostra o último ano do deputado: não pode virar gasto do ano pedido."""
    html = ('<a href="https://www.camara.leg.br/deputados/215045/verba-gabinete?ano=2023">Veja</a>'
            "<p>Cota parlamentar Gasto 35.472,00 Gasto mensal JAN 35.472,00</p>")
    monkeypatch.setattr(recursos, "_get_text", lambda url, **kw: html)
    assert recursos.ano_da_pagina(html) == 2023
    assert recursos.camara_ano("215045", 2024) == {}
    assert recursos.camara_ano("215045", 2023)["cota_meses"] == [{"mes": 1, "valor": 35472.0}]


def test_coleta_inteira_grava_o_historico(coleta):
    from fakegov import FakeGov
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    h = coleta.ler(saida, "historico.json")
    assert {x["casa"] for x in h["anos"]} == {"camara", "senado"}
    assert all(x["total_hoje"] for x in h["anos"])  # IPCA do governo simulado
    pols = {p["id"]: p for p in coleta.ler(saida, "politicos.json")}
    # o ano da coleta principal tem o mesmo total do perfil
    for f in (saida / "h").glob("dep-*.json"):
        x = json.loads(f.read_text())
        if f.stem in pols and "2025" in x["anos"]:
            assert abs(x["anos"]["2025"]["total"] - pols[f.stem]["por_ano"]["2025"]["total"]) < 0.01
    assert coleta.validar(saida).ok
