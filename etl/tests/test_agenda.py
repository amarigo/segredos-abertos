"""Calendário dia a dia: presença em eventos da Câmara, votos do Senado, notas do dia e pontos para conferir."""
from fakegov import FakeGov

from sa_etl import agenda

EV = [
    {"id": "1", "dataHoraInicio": "2025-05-06T14:00:00", "situacao": "Encerrada", "descricaoTipo": "Sessão Deliberativa",
     "descricao": "Sessão Deliberativa Extraordinária Presencial (AM nº 123/2020)", "localExterno": "",
     "localCamara.nome": "Plenário da Câmara dos Deputados"},
    {"id": "2", "dataHoraInicio": "2025-05-07T14:00:00", "situacao": "Encerrada", "descricaoTipo": "Sessão Deliberativa",
     "descricao": "Sessão Deliberativa Extraordinária Semipresencial (AM nº 123/2020)", "localExterno": "",
     "localCamara.nome": "Plenário da Câmara dos Deputados"},
    {"id": "3", "dataHoraInicio": "2025-05-08T09:00:00", "situacao": "Encerrada", "descricaoTipo": "Visita Técnica",
     "descricao": "Visita\r\n\r\nConvidados: muita gente", "localExterno": "Aterro sanitário em Manaus-AM", "localCamara.nome": ""},
    {"id": "4", "dataHoraInicio": "2025-05-09T10:00:00", "situacao": "Cancelada", "descricaoTipo": "Audiência Pública",
     "descricao": "Cancelada", "localExterno": "", "localCamara.nome": "Anexo II, Plenário 01"},
    {"id": "5", "dataHoraInicio": "2025-05-06T10:00:00", "situacao": "Encerrada (Final)", "descricaoTipo": "Reunião Deliberativa",
     "descricao": "Reunião\nConvidados", "localExterno": "", "localCamara.nome": "Anexo II, Plenário 01"},
]
PRES = [{"idEvento": e, "idDeputado": d} for e, d in
        [("1", "10"), ("1", "10"), ("2", "10"), ("3", "10"), ("4", "10"), ("5", "10"), ("1", "99"), ("1", "x")]]
ORG = [{"idEvento": "5", "siglaOrgao": "CCJC"}, {"idEvento": "5", "siglaOrgao": "CFT"}, {"idEvento": "1", "siglaOrgao": "PLEN"}]


def test_presenca_le_os_arquivos_de_eventos():
    p = agenda.parse_eventos(EV, PRES, ORG, {"dep-10"})
    assert set(p) == {"dep-10"}  # deputado fora da lista e id inválido ficam de fora
    evs = p["dep-10"]
    assert [e["id"] for e in evs] == [5, 1, 2, 3]  # cancelado fora, repetido uma vez só, em ordem de data e hora
    por_id = {e["id"]: e for e in evs}
    assert por_id[1]["brasilia"] and por_id[5]["brasilia"]
    assert not por_id[2]["brasilia"]  # sessão semipresencial aceita voto à distância
    assert not por_id[3]["brasilia"] and por_id[3]["local"] == "Aterro sanitário em Manaus-AM"
    assert por_id[5]["orgao"] == "CCJC/CFT" and por_id[5]["titulo"] == "Reunião" and por_id[3]["titulo"] == "Visita"
    assert por_id[1]["hora"] == "14:00" and por_id[1]["data"] == "2025-05-06"


RESTAURANTE = {"municipio": "Recife", "uf": "PE", "atividade": "Restaurantes e similares"}
EMPS = {"11111111000111": RESTAURANTE, "22222222000122": {**RESTAURANTE, "municipio": "Brasília", "uf": "DF"},
        "33333333000133": {"municipio": "Recife", "uf": "PE", "atividade": "Comércio varejista de combustíveis"}}


def _nota(data, doc, cat="Fornecimento de alimentação do parlamentar", valor=80.0):
    return {"data": data, "doc": doc, "categoria": cat, "fornecedor": "F", "valor": valor, "url": "https://x/nota.pdf", "ano": 2025}


def test_ponto_para_conferir_so_com_refeicao_de_outro_estado_em_dia_de_presenca_em_brasilia():
    evs = agenda.parse_eventos(EV, PRES, ORG, {"dep-10"})["dep-10"]
    notas = [_nota("2025-05-06", "11111111000111"),  # sessão presencial + restaurante em Recife: conferir
             _nota("2025-05-06", "22222222000122"),  # restaurante em Brasília: normal
             _nota("2025-05-06", "33333333000133", cat="Combustíveis e lubrificantes"),  # combustível pode ser da equipe
             _nota("2025-05-07", "11111111000111"),  # sessão semipresencial: não prova que estava em Brasília
             _nota("2025-05-08", "11111111000111"),  # evento fora de Brasília
             _nota("2025-05-20", "11111111000111"),  # dia sem presença
             {**_nota("2025-05-06", "11111111000111"), "sem_nota": True}]  # valor completado com a página oficial
    a = agenda.montar_ano("camara", 2025, evs, [], {}, notas, EMPS)
    assert [(c["data"], c["uf"], c["eventos"]) for c in a["conferir"]] == [("2025-05-06", "PE", [5, 1])]
    assert a["resumo"] == {"dias_presenca": 3, "dias_gastos": 4, "conferir": 1, "conferir_cercado": 0}
    assert a["lugares"]["11111111000111"] == ["Recife", "PE", "Restaurantes e similares"]
    assert a["dias"]["2025-05-08"]["e"][0][4] == "Aterro sanitário em Manaus-AM" and a["dias"]["2025-05-08"]["e"][0][5] == 0
    # Senado: o voto pode ser dado à distância; mostra o dia, mas não aponta nada
    s = agenda.montar_ano("senado", 2025, [], [{"votacao": "sf-1", "voto": "Sim"}, {"votacao": "sf-2", "voto": "Em missão"}],
                          {"sf-1": {"data": "2025-05-06"}, "sf-2": {"data": "2025-05-21"}}, notas[:1], EMPS)
    assert s["conferir"] == [] and s["dias"]["2025-05-06"]["v"] == [["sf-1", "Sim"]]
    assert s["resumo"]["dias_presenca"] == 1  # o dia em missão aparece, mas não conta como presença


def test_ramo_do_fornecedor_vale_para_refeicao_sem_o_tipo_da_camara():
    evs = agenda.parse_eventos(EV, PRES, ORG, {"dep-10"})["dep-10"]
    a = agenda.montar_ano("camara", 2025, evs, [], {}, [_nota("2025-05-06", "11111111000111", cat="Locação de veículos")], EMPS)
    assert len(a["conferir"]) == 1


def test_coleta_grava_o_calendario_de_cada_parlamentar(coleta):
    gov = coleta.usar(FakeGov(anos=(2025,)))
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []
    d0, d1 = gov.deputados[0]["id"], gov.deputados[1]["id"]
    a = coleta.ler(saida, f"p/agenda/dep-{d0}-2025.json")
    # a refeição em Recife no dia da sessão presencial; a do dia da sessão semipresencial não entra
    assert [(c["uf"], c["valor"]) for c in a["conferir"]] == [("PE", 86.5)]
    assert a["lugares"][gov.restaurante][:2] == ["Recife", "PE"]
    assert not any(e[6] == 2025 * 1000 + 901 for x in a["dias"].values() for e in x.get("e", []))  # evento cancelado
    b = coleta.ler(saida, f"p/agenda/dep-{d1}-2025.json")
    assert b["dias"]["2025-04-08"]["e"][0][4] == "Aterro sanitário em Manaus-AM" and b["conferir"] == []
    p = coleta.ler(saida, f"p/dep-{d0}.json")
    assert p["anos"]["2025"]["agenda"]["conferir"] == 1
    s = coleta.ler(saida, f"p/agenda/sen-{gov.senadores[0]['cod']}-2025.json")
    assert s["conferir"] == [] and any(x.get("v") for x in s["dias"].values())


def test_sem_os_arquivos_de_eventos_o_site_sai_e_avisa(coleta):
    gov = coleta.usar(FakeGov(anos=(2025,)))
    gov.falhar("/arquivos/eventos", "500")
    saida = coleta.rodar()
    meta = coleta.ler(saida, "meta.json")
    assert any("Presença na Câmara 2025" in a for a in meta["avisos"])
    a = coleta.ler(saida, f"p/agenda/dep-{gov.deputados[0]['id']}-2025.json")
    assert a["conferir"] == [] and a["resumo"]["dias_gastos"] > 0


def test_ponto_cercado_quando_tambem_esteve_em_brasilia_na_vespera_e_no_dia_seguinte():
    ev = [{"id": str(i), "dataHoraInicio": f"2025-06-{d}T14:00:00", "situacao": "Encerrada", "descricaoTipo": "Sessão Deliberativa",
           "descricao": "Sessão Deliberativa Extraordinária Presencial", "localExterno": "", "localCamara.nome": "Plenário"}
          for i, d in ((1, 10), (2, 11), (3, 12), (4, 18))]
    evs = agenda.parse_eventos(ev, [{"idEvento": str(i), "idDeputado": "10"} for i in range(1, 5)], [], {"dep-10"})["dep-10"]
    a = agenda.montar_ano("camara", 2025, evs, [], {}, [_nota("2025-06-11", "11111111000111"), _nota("2025-06-18", "11111111000111")], EMPS)
    assert [(c["data"], c["cercado"]) for c in a["conferir"]] == [("2025-06-11", True), ("2025-06-18", False)]
    assert a["resumo"]["conferir"] == 2 and a["resumo"]["conferir_cercado"] == 1
