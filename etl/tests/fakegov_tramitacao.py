"""Imita as APIs da Câmara e do Senado usadas na lista de projetos em andamento (sa_etl/tramitacao.py).

Datas relativas a hoje: sempre há uma sessão nos próximos dias, propostas novas e medidas provisórias.
"""
from __future__ import annotations

import datetime as dt
import json

CD = "dadosabertos.camara.leg.br"
SF = "legis.senado.leg.br"


def _d(dias: int) -> dt.date:
    return dt.date.today() + dt.timedelta(days=dias)


def _br(x: dt.date) -> str:
    return x.strftime("%d/%m/%Y")


def _prop(i, sigla, num, ano, ementa, apres, org, sit, cod=None):
    return {"id": i, "uri": f"https://{CD}/api/v2/proposicoes/{i}", "siglaTipo": sigla, "codTipo": 139, "numero": num,
            "ano": ano, "ementa": ementa, "dataApresentacao": f"{apres.isoformat()}T10:00",
            "statusProposicao": {"dataHora": f"{_d(-1).isoformat()}T00:00", "siglaOrgao": org, "descricaoSituacao": sit,
                                 "codSituacao": cod, "regime": "Ordinário (Art. 151, III, RICD)"},
            "urlInteiroTeor": f"https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor={i}"}


PROPS = {
    9001: _prop(9001, "PL", 101, 2025, "Altera a Lei nº 9.503, de 23 de setembro de 1997 (Código de Trânsito Brasileiro), "
                "para dispor sobre capacete em bicicletas.", _d(-300), "PLEN", "Aguardando Deliberação"),
    9002: _prop(9002, "PL", 102, 2026, "Dispõe sobre merenda escolar orgânica.", _d(-3), "MESA", "Aguardando Despacho do Presidente da Câmara dos Deputados"),
    9003: _prop(9003, "PEC", 7, 2026, "Altera o art. 14 da Constituição Federal, para tratar da reeleição.", _d(-5), "CCJC",
                "Aguardando Designação de Relator(a)"),
    9004: _prop(9004, "MPV", 1400, 2026, "Abre crédito extraordinário, em favor do Ministério da Saúde, no valor de "
                "R$ 10.000.000,00, para o fim que especifica.", _d(-20), "CMO", ""),
    9005: _prop(9005, "MPV", 1300, 2025, "Dispõe sobre o programa antigo.", _d(-400), "PLEN", ""),
    9006: _prop(9006, "PL", 103, 2024, "Institui o Dia Nacional da Bicicleta.", _d(-700), "CVT", "Aguardando Parecer do Relator(a)"),
}
TRAM = {
    9004: [{"dataHora": f"{_d(-19).isoformat()}T00:00", "sequencia": 1, "siglaOrgao": "CN",
            "despacho": f"Prazo para Emendas: x. Sobrestar Pauta: a partir de {_br(_d(25))}.Congresso Nacional: "
                        f"{_br(_d(-19))} a {_br(_d(40))}.Prorrogação pelo Congresso Nacional: Prazo ainda não prorrogado."}],
    9005: [{"dataHora": f"{_d(-399).isoformat()}T00:00", "sequencia": 1, "siglaOrgao": "CN",
            "despacho": f"Congresso Nacional: {_br(_d(-399))} a {_br(_d(-340))}."}],
}
AUTORES = {9001: [{"uri": f"https://{CD}/api/v2/deputados/1000", "nome": "Deputado Ficticio 00", "proponente": 1, "ordemAssinatura": 1},
                  {"uri": f"https://{CD}/api/v2/deputados/1001", "nome": "Deputado Ficticio 01", "proponente": 1, "ordemAssinatura": 2}],
           9002: [{"uri": f"https://{CD}/api/v2/deputados/1002", "nome": "Deputado Ficticio 02", "proponente": 1, "ordemAssinatura": 1}],
           9003: [{"uri": f"https://{CD}/api/v2/deputados/1003", "nome": "Deputado Ficticio 03", "proponente": 1, "ordemAssinatura": 1}],
           9004: [{"uri": f"https://{CD}/api/v2/orgaos/78", "nome": "Poder Executivo", "proponente": 1, "ordemAssinatura": 1}],
           9006: [{"uri": f"https://{CD}/api/v2/deputados/1004", "nome": "Deputado Ficticio 04", "proponente": 1, "ordemAssinatura": 1}]}


def _resumo(p):
    return {k: p[k] for k in ("id", "uri", "siglaTipo", "codTipo", "numero", "ano", "ementa", "dataApresentacao")}


def _ok(x):
    return 200, json.dumps(x, ensure_ascii=False).encode(), "application/json"


def rota(netloc: str, path: str, q: dict):
    if netloc == CD and path == "/api/v2/eventos":
        return _ok({"dados": [
            {"id": 7001, "dataHoraInicio": f"{_d(1).isoformat()}T14:00", "situacao": "Convocada", "descricaoTipo": "Sessão Deliberativa",
             "orgaos": [{"sigla": "PLEN", "nome": "Plenário"}]},
            {"id": 7002, "dataHoraInicio": f"{_d(2).isoformat()}T10:00", "situacao": "Convocada", "descricaoTipo": "Reunião Deliberativa",
             "orgaos": [{"sigla": "CVT", "nome": "Comissão de Viação e Transportes", "nomePublicacao": "Comissão de Viação e Transportes"}]},
            {"id": 7003, "dataHoraInicio": f"{_d(3).isoformat()}T10:00", "situacao": "Convocada", "descricaoTipo": "Audiência Pública",
             "orgaos": [{"sigla": "CE"}]}], "links": []})
    if netloc == CD and path == "/api/v2/eventos/7001/pauta":
        return _ok({"dados": [
            {"ordem": 1, "regime": "Urgência", "proposicao_": _resumo(PROPS[9001]),
             "relator": {"nome": "Deputado Ficticio 05", "siglaPartido": "PT", "siglaUf": "SP"}},
            {"ordem": 2, "regime": "Matéria Sobre a Mesa", "proposicao_": {"id": 9100, "siglaTipo": "REQ", "numero": 5, "ano": 2026},
             "proposicaoRelacionada_": _resumo(PROPS[9006])}]})
    if netloc == CD and path == "/api/v2/eventos/7002/pauta":
        return _ok({"dados": [{"ordem": 1, "proposicao_": _resumo(PROPS[9006]), "relator": None}]})
    if netloc == CD and path == "/api/v2/proposicoes":
        if q.get("siglaTipo") == "MPV":
            return _ok({"dados": [_resumo(p) for p in PROPS.values() if p["siglaTipo"] == "MPV" and str(p["ano"]) == q.get("ano")], "links": []})
        ini = q.get("dataApresentacaoInicio", "")
        return _ok({"dados": [_resumo(p) for p in PROPS.values() if p["dataApresentacao"][:10] >= ini], "links": []})
    if netloc == CD and path.startswith("/api/v2/proposicoes/"):
        partes = path.split("/")
        i = int(partes[4]) if partes[4].isdigit() else 0
        if i not in PROPS:
            return 404, b"", "text/html"
        if len(partes) == 5:
            return _ok({"dados": PROPS[i]})
        if partes[5] == "autores":
            return _ok({"dados": AUTORES.get(i, [])})
        if partes[5] == "tramitacoes":
            return _ok({"dados": TRAM.get(i, [])})
    if netloc == CD and path == "/api/v2/orgaos":
        nomes = {"CCJC": "Comissão de Constituição e Justiça e de Cidadania", "CVT": "Comissão de Viação e Transportes", "CMO": "Comissão Mista de Orçamento"}
        s = q.get("sigla", "")
        return _ok({"dados": [{"sigla": s, "nome": nomes[s]}] if s in nomes else []})
    if netloc == SF and path.startswith("/dadosabertos/plenario/agenda/mes/"):
        return _ok({"AgendaPlenario": {"Sessoes": {"Sessao": [
            {"Data": _d(2).isoformat(), "Hora": "14:00", "TipoSessao": "SESSÃO DELIBERATIVA ORDINÁRIA ", "Casa": "SF",
             "CodigoSessao": "8001", "SituacaoSessao": "Agendada",
             "Materias": {"Materia": {"CodigoMateria": "6001", "SiglaMateria": "PL", "NumeroMateria": "00200", "AnoMateria": "2025",
                                      "Ementa": "Dispõe sobre bibliotecas.", "Apreciacao": "Discussão, em turno único",
                                      "Parecer": "Parecer favorável da CE."}}}]}}})
    if netloc == SF and path.startswith("/dadosabertos/comissao/agenda/"):
        return _ok({"AgendaReuniao": {"reunioes": {"reuniao": []}}})
    if netloc == SF and path == "/dadosabertos/processo":
        base = {"casaIdentificadora": "SF", "tramitando": "Sim", "tipoDocumento": "Projeto de Lei Ordinária"}
        p200 = {**base, "codigoMateria": 6001, "identificacao": "PL 200/2025", "ementa": "Dispõe sobre bibliotecas.",
                "autoria": "Senador Ficticio 00 (PT/SP)", "dataApresentacao": "2025-03-01", "objetivo": "Iniciadora",
                "situacaoAtual": "PRONTA PARA A PAUTA NO PLENÁRIO", "dataSituacaoAtual": _d(-2).isoformat()}
        p300 = {**base, "codigoMateria": 6002, "identificacao": "PL 300/2026", "ementa": "Institui a Semana do Livro.",
                "autoria": "Senador Ficticio 01 (PT/MG), Senadora Ficticia Nova (PL/RJ)", "dataApresentacao": _d(-2).isoformat(),
                "objetivo": "Iniciadora", "situacaoAtual": "AGUARDANDO DESPACHO", "dataSituacaoAtual": _d(-2).isoformat()}
        req = {**base, "codigoMateria": 6003, "identificacao": "REQ 9/2026", "ementa": "Requer informações.", "autoria": "x",
               "dataApresentacao": _d(-1).isoformat(), "objetivo": "Iniciadora", "situacaoAtual": "APROVADO"}
        if q.get("sigla"):
            return _ok([p for p in (p200, p300) if p["identificacao"] == f"{q['sigla']} {q.get('numero')}/{q.get('ano')}"])
        return _ok([p300, req])
    return None
