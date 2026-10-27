"""Projetos em andamento: resumo simples, etapa, próximo passo, prazo das MPs e a coleta inteira contra o FakeGov."""
import datetime as dt

from fakegov import FakeGov
from sa_etl import tramitacao as t


def test_resumo_troca_numero_da_lei_pelo_nome():
    r = t.resumo_simples("Altera a Lei nº 9.504, de 30 de setembro de 1997, para dispor sobre o registro de candidatos.")
    assert r == "Muda a Lei das Eleições, para tratar do registro de candidatos."


def test_resumo_usa_o_apelido_que_a_ementa_ja_traz():
    r = t.resumo_simples("Altera o Decreto-Lei nº 2848, de 07 de dezembro de 1940 – Código Penal, para dispor sobre drones.")
    assert r == "Muda o Código Penal, para tratar de drones."


def test_resumo_lei_sem_nome_fica_curta():
    r = t.resumo_simples("Altera a Lei nº 9.250, de 26 de dezembro de 1995, para prever a dedução.")
    assert r == "Muda a Lei 9.250/1995, para prever a dedução."


def test_resumo_constituicao_e_credito():
    assert t.resumo_simples("Altera o art. 14 da Constituição Federal, para tratar da reeleição.") == "Muda a Constituição, para tratar da reeleição."
    r = t.resumo_simples("Abre crédito extraordinário, em favor do Ministério X, no valor de R$ 1,00, para o fim que especifica.")
    assert r.startswith("Libera dinheiro extra no Orçamento") and "especifica" not in r


def test_resumo_vazio_quando_nada_muda():
    assert t.resumo_simples("Estabelece normas gerais para bibliotecas.") == ""
    assert t.resumo_simples("") == ""


def test_etapas():
    assert t.etapa_camara({"siglaOrgao": "MESA", "descricaoSituacao": "Aguardando Despacho"}) == 0
    assert t.etapa_camara({"siglaOrgao": "CCJC", "descricaoSituacao": "Aguardando Parecer"}) == 1
    assert t.etapa_camara({"siglaOrgao": "PLEN", "descricaoSituacao": "Aguardando Deliberação"}) == 2
    assert t.etapa_camara({"siglaOrgao": "MESA", "descricaoSituacao": "Aguardando Apreciação pelo Senado Federal"}) == 3
    assert t.etapa_camara({"siglaOrgao": "MESA", "descricaoSituacao": "Aguardando Sanção"}) == 4
    assert t.etapa_senado("AGUARDANDO DESPACHO", False) == 0
    assert t.etapa_senado("MATÉRIA COM A RELATORIA", False) == 1
    assert t.etapa_senado("PRONTA PARA A PAUTA NO PLENÁRIO", False) == 2
    assert t.etapa_senado("MATÉRIA COM A RELATORIA", True) == 3


def test_prazo_mpv_pega_a_ultima_data():
    tram = [{"dataHora": "2026-09-11T00:00", "despacho": "Sobrestar Pauta: a partir de 26/10/2026.Congresso Nacional: 11/09/2026 a 09/11/2026."},
            {"dataHora": "2026-10-08T00:00", "despacho": "Prorrogação do prazo por 60 dias. Data final após prorrogação: 10/12/2026."}]
    assert t.prazo_mpv(tram) == {"prazo": "2026-12-10", "suspenso": False, "tranca_pauta": "2026-10-26"}
    tram.append({"dataHora": "2026-10-09T00:00", "despacho": "Os prazos de tramitação e a vigência ficarão suspensos a partir de 1º/8."})
    assert t.prazo_mpv(tram)["suspenso"] is True


def test_proximo_passo():
    assert "relator" in t.proximo_passo({"situacao": "Aguardando Designação de Relator(a)"})
    assert "pauta" in t.proximo_passo({"pauta": [{"data": "2026-10-28T14:00", "onde": "Plenário da Câmara", "urgencia": False}]})
    assert "urgência" in t.proximo_passo({"pauta": [{"data": "2026-10-28T14:00", "onde": "Plenário da Câmara", "urgencia": True}]})
    assert "10/12" in t.proximo_passo({"sigla": "MPV", "prazo": "2026-12-10", "situacao": ""})
    assert t.data_hora_br("2026-10-28T14:00") == "quarta, 28/10, às 14h00"


def test_coleta_inteira(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    d = coleta.ler(saida, "tramitacao.json")
    por = {i["nome"]: i for i in d["itens"]}
    # Na pauta do Plenário, com autores ligados à página do político
    pl = por["PL 101/2025"]
    assert pl["grupos"] == ["pauta"] and pl["etapa_nome"] == "Plenário"
    assert [a["id"] for a in pl["autores"]] == ["dep-1000", "dep-1001"]
    assert pl["resumo"].startswith("Muda o Código de Trânsito")
    assert pl["url"] == "https://www.camara.leg.br/propostas-legislativas/9001"
    # Pedido de urgência no Plenário e votação na comissão
    bici = por["PL 103/2024"]
    assert any(x["urgencia"] for x in bici["pauta"]) and any(x["onde"] == "Comissão de Viação e Transportes" for x in bici["pauta"])
    assert bici["etapa_nome"] == "Comissões"
    # Novas e MPs: a MP vencida fica de fora
    assert "nova" in por["PEC 7/2026"]["grupos"] and por["PEC 7/2026"]["onde"] == "Comissão de Constituição e Justiça e de Cidadania"
    assert "mpv" in por["MPV 1400/2026"]["grupos"] and por["MPV 1400/2026"]["prazo"] == (dt.date.today() + dt.timedelta(days=40)).isoformat()
    assert "MPV 1300/2025" not in por
    # Senado: pauta do Plenário e projeto novo com o senador ligado; requerimento fica de fora
    assert por["PL 200/2025"]["grupos"] == ["pauta"] and por["PL 200/2025"]["casa"] == "senado"
    novo = por["PL 300/2026"]
    assert novo["autores"][0]["id"] == "sen-5001" and novo["autores"][1]["id"] == ""
    assert not any(i["sigla"] == "REQ" for i in d["itens"])
    # A agenda aponta só para itens que existem
    ids = {i["id"] for i in d["itens"]}
    assert d["agenda"] and all(x in ids for ev in d["agenda"] for x in ev["itens"])
    assert coleta.validar(saida).ok


def test_api_fora_do_ar_usa_a_ultima_lista(coleta):
    gov = coleta.usar(FakeGov())
    coleta.rodar(com_emendas=False, com_incentivos=False)
    gov.falhar("dadosabertos.camara.leg.br/api/v2/eventos", "html")
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    d = coleta.ler(saida, "tramitacao.json")
    assert d["situacao_fontes"]["camara"] == "reserva"
    assert any(i["nome"] == "PL 101/2025" for i in d["itens"])
    assert any("Projetos em andamento" in a for a in coleta.ler(saida, "meta.json")["avisos"])
