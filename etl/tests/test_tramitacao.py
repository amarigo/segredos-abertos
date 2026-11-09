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


def test_proposta_sem_detalhe_sai_da_agenda(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("dadosabertos.camara.leg.br/api/v2/proposicoes/9001", "html")
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    d = coleta.ler(saida, "tramitacao.json")
    ids = {i["id"] for i in d["itens"]}
    assert "cd-9001" not in ids
    assert all(x in ids for ev in d["agenda"] for x in ev["itens"])
    assert coleta.validar(saida).ok


def test_autor_original_e_argumentos_dos_documentos_oficiais(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    por = {i["nome"]: i for i in coleta.ler(saida, "tramitacao.json")["itens"]}
    # Na Câmara: a justificação do autor e o parecer pela aprovação contam a favor; o voto em separado, contra
    deb = por["PL 101/2025"]["debate"]
    assert [a["papel"] for a in deb["favor"]] == ["Autores da proposta", "Relator na Comissão de Viação e Transportes"]
    assert deb["favor"][0]["trechos"] == ["O capacete reduz em 60% o risco de morte dos ciclistas em quedas, porque protege a cabeça no impacto."]
    assert deb["favor"][1]["trechos"][0].startswith("A medida garante")
    assert deb["favor"][1]["conclusao"] == "aprovação" and deb["favor"][1]["quem"] == "Deputado Ficticio 05 (PT-SP)"
    assert deb["contra"][0]["quem"].startswith("Deputado Ficticio 03") and deb["contra"][0]["conclusao"] == "rejeição"
    assert "aumentar o preço da bicicleta" in deb["contra"][0]["trechos"][0]
    assert all(a["url"].startswith("https://www.camara.leg.br/") for a in deb["favor"] + deb["contra"])
    # No Senado: proposta que veio da Câmara mostra o deputado que a apresentou, e os documentos da Câmara
    pl = por["PL 250/2024"]
    assert pl["veio_da_camara"] and pl["autores"][0]["nome"] == "Deputado Ficticio 05" and pl["autores"][0]["id"] == "dep-1005"
    assert pl["url_origem"] == "https://www.camara.leg.br/propostas-legislativas/9007"
    assert [a["casa"] for a in pl["debate"]["favor"]] == ["Câmara", "Câmara"] and pl["debate"]["contra"] == []
    # Relator do Senado pela rejeição, com o trecho que fala do custo
    sen = por["PL 200/2025"]["debate"]
    assert sen["favor"][0]["papel"] == "Autor da proposta"
    assert sen["contra"][0]["quem"] == "Ficticio 01 (PT-MG)" and "R$ 50 milhões" in sen["contra"][0]["trechos"][0]
    assert coleta.validar(saida).ok


def test_documento_fora_do_ar_nao_derruba_o_cartao(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("prop_mostrarintegra", "500")
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    por = {i["nome"]: i for i in coleta.ler(saida, "tramitacao.json")["itens"]}
    assert "PL 101/2025" in por and por["PL 101/2025"].get("debate") is None
    assert por["PL 200/2025"]["debate"]["contra"]  # o Senado respondeu


def test_conclusao_ignora_o_que_e_so_sobre_emendas():
    from sa_etl import debate as d
    assert d.conclusao("Parecer do Relator, Dep. A (PT-SP), pela aprovação deste, e pela rejeição do PL 1/2025, apensado.") == "aprovação"
    assert d.conclusao("com voto favorável à Proposta e às Emendas nºs 22 e 39, e contrário às demais emendas.") == "aprovação"
    assert d.conclusao("Complementação de Voto sobre as Emendas 67 a 81, concluindo pela rejeição dessas emendas.") == ""
    assert d.conclusao("pela constitucionalidade, juridicidade e boa técnica legislativa") == ""
    assert d.conclusao("Ante o exposto, votamos pela aprovação com emendas. Em suma, pela rejeição.", ultima=True) == "rejeição"


def test_trechos_copiam_frases_sem_protocolo():
    from sa_etl import debate as d
    texto = d.limpar("Senhor Presidente, é o relatório.\n*CD250605464200* PRL n.1\nA medida reduz o preço da energia em 10% para "
                     "as famílias de baixa renda, porque corta impostos.\nPelo exposto, contamos com o apoio dos nobres pares.")
    assert d.trechos(texto) == ["A medida reduz o preço da energia em 10% para as famílias de baixa renda, porque corta impostos."]
    assert d.frases("Conforme o art. 5º da Lei. Outra frase.") == ["Conforme o art. 5º da Lei.", "Outra frase."]
    assert d.trechos("") == []
    assert d.secao("I - RELATÓRIO x. II - VOTO DO RELATOR A medida reduz. Sala da Comissão", "parecer") == "A medida reduz"


def test_autor_que_veio_do_senado_e_presidente():
    a = t.autores_camara([{"uri": "x/orgaos/78", "nome": "Senado Federal - Rodrigo Pacheco", "proponente": 1, "ordemAssinatura": 1},
                          {"uri": "x/orgaos/1", "nome": "Poder Executivo", "proponente": 1, "ordemAssinatura": 2}],
                         {}, {"RODRIGO PACHECO": "sen-1"})
    assert a[0] == {"nome": "Rodrigo Pacheco", "partido": "", "uf": "", "id": "sen-1", "cargo": "Senador(a)"}
    assert a[1]["nome"] == "Presidente da República"


def test_sem_documento_oficial_contra_procura_em_noticias(coleta):
    """PL 250/2024 está na pauta e nenhum documento oficial é contra: o contra vem de notícia, com veículo, link e a
    frase copiada sem mudança. Notícia que não cita o número, que fala de outro projeto ou que recusa robô fica de fora."""
    from fakegov_noticias import A, E
    coleta.usar(FakeGov())
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    por = {i["nome"]: i for i in coleta.ler(saida, "tramitacao.json")["itens"]}
    deb = por["PL 250/2024"]["debate"]
    assert deb["contra"] == [] and deb["noticias_buscadas_em"]
    assert [n["url"] for n in deb["noticias_contra"]] == [A, E]  # a mais nova primeiro; E veio do Google, decodificado
    n, e = deb["noticias_contra"]
    assert e["veiculo"] == "Jornal E" and e["quem"] == "Deputada Sicrana Silva" and e["autor"] == "João Colunista"
    assert e["trechos"][0].startswith("“O texto é um retrocesso")
    assert n["url"] == A and n["veiculo"] == "Jornal A" and n["autor"] == "Maria Repórter" and n["data"] == "2026-10-30"
    assert n["titulo"] == "Prefeitos criticam PL 250/2024 do transporte escolar"
    assert n["quem"] == "Confederação Nacional de Municípios"
    assert n["trechos"] == ["Segundo a Confederação Nacional de Municípios, o texto cria uma despesa sem fonte e pode "
                            "prejudicar o orçamento das prefeituras pequenas."]
    # Com documento oficial contra, não procuramos em notícias
    assert "noticias_contra" not in por["PL 101/2025"]["debate"]
    assert coleta.validar(saida).ok


def test_busca_de_noticias_fora_do_ar_nao_diz_que_nao_achou(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("api.gdeltproject.org", "500")
    gov.falhar("www.bing.com", "500")
    gov.falhar("news.google.com", "429")
    saida = coleta.rodar(com_emendas=False, com_incentivos=False)
    por = {i["nome"]: i for i in coleta.ler(saida, "tramitacao.json")["itens"]}
    assert "noticias_buscadas_em" not in por["PL 250/2024"]["debate"]
    assert coleta.validar(saida).ok


def test_noticias_reconhece_a_proposta_e_quem_fala():
    from sa_etl import noticias as n
    p = n.padrao_proposta("PL", "4881", "2023")
    for t in ("o PL 4.881/2023 prevê", "PL nº 4881/2023", "Projeto de Lei 4.881, de 2023", "PL 4881/23"):
        assert p.search(t), t
    assert not p.search("PL 4881/2022") and not p.search("PLP 14881/2023")
    assert n.quem_fala("Segundo a ABSAE, a proposta enfraquece o programa.") == "ABSAE"
    assert n.quem_fala("O senador Fulano de Tal afirmou que o texto é um retrocesso.") == "Senador Fulano de Tal"
    assert n.quem_fala("Técnicos veem risco de desvio de recursos.") == ""
    # Frase a favor ("reduz o risco") não conta como contra
    assert n.trechos_contra(["O PL 4.881/2023 reduz o risco de apagão, afirmou o relator Beltrano em entrevista ontem."], "", p) == []
