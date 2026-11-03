"""Imita os serviços do portal do STF usados em sa_etl/tribunais.py (calendário, listas e votos do Plenário Virtual).

Os nomes dos campos, os formatos (datas dd/mm/aaaa, ids em texto, estado por extenso, cadeia por extenso) e os textos
dos votos seguem o que o portal devolveu em 03/11/2026. Datas relativas a hoje: uma sessão encerrada e uma em andamento.
"""
from __future__ import annotations

import datetime as dt
import json

PORTAL = "portal.stf.jus.br"
SISTEMAS = "sistemas.stf.jus.br"
MINISTROS = ["MIN. ANA FICTICIA", "MIN. BRUNO FICTICIO", "MIN. CARLA FICTICIA", "MIN. DANIEL FICTICIO",
             "MIN. ELISA FICTICIA", "MIN. FABIO FICTICIO", "MIN. GABRIELA FICTICIA", "MIN. HUGO FICTICIO",
             "MIN. IARA FICTICIA", "MIN. JOAO FICTICIO", "MIN. LUCIA FICTICIA"]


def _d(dias: int) -> dt.date:
    return dt.date.today() + dt.timedelta(days=dias)


def _br(x: dt.date) -> str:
    return x.strftime("%d/%m/%Y")


SESSOES = [(_d(-12), _d(-5)), (_d(-2), _d(5))]  # encerrada e em andamento

# lista -> processos (como lista-service.asp devolve)
LISTAS = {
    501: [{"id": "7000001", "classe": "ADI", "numero": "7001", "cadeia": None, "procedencia": "SÃO PAULO",
           "partes": [{"nome": "PARTIDO FICTICIO", "categoria": "REQTE.(S)"}, {"nome": "ADVOGADA FICTICIA", "categoria": "ADV.(A/S)"},
                      {"nome": "ASSEMBLEIA LEGISLATIVA", "categoria": "INTDO.(A/S)"}]},
          {"id": "7000002", "classe": "ADPF", "numero": "900", "procedencia": "DISTRITO FEDERAL", "partes": [],
           "cadeia": "EMB.DECL. NA ARGUIÇÃO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL"},
          {"id": "7000003", "classe": "HC", "numero": "1", "cadeia": None, "procedencia": "RIO DE JANEIRO", "partes": []},
          {"id": "7000006", "classe": "RE", "numero": "1500", "cadeia": "AG.REG. NO RECURSO EXTRAORDINÁRIO",
           "procedencia": "SÃO PAULO", "partes": []}],  # agravo em caso individual: fica de fora
    502: [{"id": "7000004", "classe": "ADC", "numero": "80", "cadeia": None, "procedencia": "DISTRITO FEDERAL", "partes": []}],
    601: [{"id": "7000005", "classe": "ADI", "numero": "7999", "cadeia": None, "procedencia": "MINAS GERAIS", "partes": []}],  # Turma
}
SESSAO_DA_LISTA = {501: 0, 502: 1, 601: 0}
INCIDENTE_ED = 7100002  # o recurso (embargos) da ADPF 900


def _voto(i: int, tipo: str, acompanha: str | None = None) -> dict:
    return {"ministro": {"descricao": MINISTROS[i]}, "tipoVoto": {"codigo": 1, "descricao": tipo},
            "acompanhandoMinistro": {"descricao": acompanha} if acompanha else "",
            "textos": [{"descricao": "Voto", "link": f"https://{SISTEMAS}/repgeral/votacao?texto={i}"}]}


def _lj(lid: int, sessao: int, relator: int, votos: list[dict], julgado: bool, resultado: str, decisao: str) -> dict:
    ini, fim = SESSOES[sessao]
    return {"id": lid, "nomeLista": "Lista", "sessao": {"numero": 30 + sessao, "dataPrevistaInicio": _br(ini),
                                                         "dataPrevistaFim": _br(fim), "dataInicio": _br(ini), "dataFim": _br(fim),
                                                         "colegiado": {"codigo": "TP", "descricao": "Plenário"}},
            "ministroRelator": {"descricao": MINISTROS[relator]}, "julgado": julgado,
            "tipoResultadoJulgamento": {"codigo": 1, "descricao": resultado} if resultado else "",
            "textoDecisao": decisao, "votoRelator": {"link": f"https://{SISTEMAS}/repgeral/votacao?relator={lid}"},
            "ministroVista": "", "ministroDestaque": "", "votos": votos}


# incidente -> resposta de votacao?sessaoVirtual=
VOTOS = {
    # ADI 7001: relatora Ana; 7 com ela (um com ressalva), 3 seguem a divergência aberta por Bruno; Lúcia impedida
    7000001: [{"objetoIncidente": {"id": 7000001, "identificacao": "ADI 7001", "identificacaoCompleta": "AÇÃO DIRETA DE INCONSTITUCIONALIDADE 7001"},
               "sustentacoesOrais": [],
               "listasJulgamento": [
                   # uma sessão antiga, de outro período: não entra
                   _lj(9001, 0, 0, [_voto(1, "Pedido de vista")], False, "", "Pedido de vista.") | {"sessao": {
                       "numero": 1, "dataPrevistaInicio": "01/01/2020", "dataPrevistaFim": "08/01/2020",
                       "colegiado": {"codigo": "TP", "descricao": "Plenário"}}},
                   _lj(9002, 0, 0, [_voto(1, "Divergência"), _voto(2, "Acompanho o Relator"),
                                    _voto(3, "Acompanho o Relator com ressalvas"), _voto(4, "Acompanho a divergência"),
                                    _voto(5, "Acompanho a divergência", MINISTROS[1]), _voto(6, "Acompanho o Relator"),
                                    _voto(7, "Acompanho o Relator"), _voto(8, "Acompanho o Relator"),
                                    _voto(9, "Acompanho a ressalva", MINISTROS[3]), _voto(10, "Suspeito")],
                       True, "Procedente", "O Tribunal, por maioria, julgou procedente o pedido, nos termos do voto da Relatora. "
                       "Vencidos os Ministros Bruno Ficticio, Elisa Ficticia e Fabio Ficticio. Impedida a Ministra Lucia Ficticia.")]}],
    INCIDENTE_ED: [{"objetoIncidente": {"id": INCIDENTE_ED, "identificacao": "ADPF 900 ED",
                                       "identificacaoCompleta": "EMB.DECL. NA ARGUIÇÃO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL 900"},
                    "sustentacoesOrais": [],
                    "listasJulgamento": [_lj(9003, 0, 2, [_voto(i, "Acompanho o Relator") for i in range(11) if i != 2],
                                             True, "Rejeitados", "O Tribunal, por unanimidade, rejeitou os embargos de declaração.")]}],
    # ADC 80: sessão em andamento, ainda sem resultado
    7000004: [{"objetoIncidente": {"id": 7000004, "identificacao": "ADC 80", "identificacaoCompleta": "ADC 80"},
               "sustentacoesOrais": [],
               "listasJulgamento": [_lj(9004, 1, 3, [_voto(0, "Acompanho o Relator")], False, "", "")]}],
}


def _json(x):
    return 200, json.dumps(x, ensure_ascii=False).encode(), "application/json"


def rota(host: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
    if host == PORTAL and path == "/pauta/services/calendario-service.asp":
        if q.get("dados") == "calendarios":
            ano, mes = int(q["ano"]), int(q["mes"])
            jv = [{"dataInicial": _br(a), "dataFinal": _br(b), "qtdProcessosPlenario": 3, "qtdPrimeiraTurma": 1,
                   "qtdSegundaTurma": 0} for a, b in SESSOES if (a.year, a.month) == (ano, mes)]
            return _json({"diasPresenciais": [], "julgamentosVirtuais": jv})
        if q.get("dados") == "sessao-virtual":
            k = next((i for i, (a, b) in enumerate(SESSOES) if _br(a) == q.get("inicio") and _br(b) == q.get("fim")), None)
            if k is None:
                return _json({"colegiados": []})

            def col(cod, desc, listas):
                return {"codigo": cod, "descricao": desc, "sessoes": [{"dataInicio": f"{q['inicio']} 11:00", "dataFinal": f"{q['fim']} 23:59",
                        "listas": [{"idTipo": "2", "descricao": "Listas dos Relatores (Incidentes e Recursos - Todas as Classes)", "ministros": [
                            {"nome": "MIN. ANA FICTICIA", "listaJulgamento": [{"id": str(i), "descricao": "Lista", "ordem": 1,
                                                                              "quantidadeProcessos": len(LISTAS[i])} for i in listas]}]}]}]}
            return _json({"inicio": q["inicio"], "fim": q["fim"], "tipo": "V", "colegiados": [
                col("TP", "Plenário", [i for i, s in SESSAO_DA_LISTA.items() if s == k and i < 600]),
                col("1T", "Primeira Turma", [i for i, s in SESSAO_DA_LISTA.items() if s == k and i >= 600])]})
    if host == PORTAL and path == "/pauta/services/lista-service.asp":
        return _json(LISTAS.get(int(q.get("lista", 0)), []))
    if host == SISTEMAS and path == "/repgeral/votacao":
        if "oi" in q:
            if int(q["oi"]) == 7000002:
                return _json([{"objetoIncidente": {"id": 7100009, "identificacao": "ADPF 900 AgR",
                                                   "identificacaoCompleta": "AG.REG. NA ARGUIÇÃO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL 900"}},
                              {"objetoIncidente": {"id": INCIDENTE_ED, "identificacao": "ADPF 900 ED",
                                                   "identificacaoCompleta": "EMB.DECL. NA ARGUIÇÃO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL 900"}}])
            return _json([])
        return _json(VOTOS.get(int(q.get("sessaoVirtual", 0)), []))
    return None
