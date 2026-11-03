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


# PL 250/2024 já está no Senado (veio da Câmara): a Câmara só responde quando o Senado pergunta pela origem
ORIGEM = {9007: _prop(9007, "PL", 250, 2024, "Dispõe sobre o transporte escolar rural.", _d(-800), "SF", "Remetida ao Senado Federal")}
AUTORES[9007] = [{"uri": f"https://{CD}/api/v2/deputados/1005", "nome": "Deputado Ficticio 05", "proponente": 1, "ordemAssinatura": 1}]

# Documentos com argumentos (parecer do relator e voto em separado), como /proposicoes/{id}/relacionadas devolve
RELACIONADAS = {
    9001: [{"id": 9201, "siglaTipo": "PRL", "numero": 1, "ano": 0,
            "ementa": "Parecer do Relator, Dep. Deputado Ficticio 05 (PT-SP), pela aprovação deste, e pela rejeição do PL 1/2025, apensado."},
           {"id": 9202, "siglaTipo": "VTS", "numero": 1, "ano": 0, "ementa": "Voto em separado."},
           {"id": 9203, "siglaTipo": "REQ", "numero": 5, "ano": 2026, "ementa": "Requer audiência pública."}],
    9007: [{"id": 9204, "siglaTipo": "PRL", "numero": 1, "ano": 0,
            "ementa": "Parecer da Relatora, Dep. Deputada Ficticia 06 (PSB-MG), pela aprovação."}],
}
DOCS = {9201: {"id": 9201, "siglaTipo": "PRL", "dataApresentacao": f"{_d(-30).isoformat()}T10:00",
               "uriOrgaoNumerador": f"https://{CD}/api/v2/orgaos/2001",
               "urlInteiroTeor": f"https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=9201"},
        9202: {"id": 9202, "siglaTipo": "VTS", "dataApresentacao": f"{_d(-20).isoformat()}T10:00",
               "urlInteiroTeor": f"https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=9202"},
        9204: {"id": 9204, "siglaTipo": "PRL", "dataApresentacao": f"{_d(-900).isoformat()}T10:00",
               "uriOrgaoNumerador": f"https://{CD}/api/v2/orgaos/2002",
               "urlInteiroTeor": f"https://www.camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=9204"}}
AUTORES[9202] = [{"uri": f"https://{CD}/api/v2/deputados/1003", "nome": "Deputado Ficticio 03", "proponente": 1, "ordemAssinatura": 1}]
TEXTOS = {
    9001: "PROJETO DE LEI\nArt. 1º Fica obrigatório o capacete.\nJUSTIFICAÇÃO\nO capacete reduz em 60% o risco de morte dos ciclistas "
          "em quedas, porque protege a cabeça no impacto.\nPelo exposto, contamos com o apoio dos nobres pares.\nSala das Sessões",
    9201: "I - RELATÓRIO\nVem a esta Comissão o projeto.\nII - VOTO DO RELATOR\nA medida garante mais segurança aos ciclistas "
          "e reduz o custo do SUS com internações, que passa de R$ 100 milhões por ano.\nAnte o exposto, votamos pela aprovação.\nSala da Comissão",
    9202: "VOTO EM SEPARADO\nA obrigação vai aumentar o preço da bicicleta e afastar trabalhadores de baixa renda que dependem dela, "
          "pois o capacete custa caro.\nAnte o exposto, votamos pela rejeição do projeto.\nSala da Comissão",
    9007: "PROJETO DE LEI\nJUSTIFICAÇÃO\nO transporte escolar rural garante o acesso das crianças à escola, porque muitas "
          "famílias moram longe e não têm como levar os filhos.\nSala das Sessões",
    9204: "II - VOTO DA RELATORA\nO projeto amplia o acesso à educação no campo e reduz a evasão escolar, que chega a 20% nas áreas rurais.\n"
          "Sala da Comissão",
}
def pdf(texto: str) -> bytes:
    linhas = texto.split("\n")
    def esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    corpo = "BT /F1 10 Tf 14 TL 40 800 Td " + " ".join(f"({esc(l)}) Tj T*" for l in linhas) + " ET"
    stream = corpo.encode("cp1252")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    out = b"%PDF-1.4\n"; offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    return out


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
    if netloc == "www.camara.leg.br" and path == "/proposicoesWeb/prop_mostrarintegra":
        i = int(q.get("codteor", "0"))
        return (200, pdf(TEXTOS[i]), "application/pdf") if i in TEXTOS else (404, b"", "text/html")
    if netloc == CD and path.startswith("/api/v2/orgaos/"):
        nomes = {"2001": "Comissão de Viação e Transportes", "2002": "Comissão de Educação"}
        oid = path.rsplit("/", 1)[1]
        return _ok({"dados": {"id": oid, "nome": nomes[oid]}}) if oid in nomes else (404, b"", "text/html")
    if netloc == CD and path == "/api/v2/proposicoes" and q.get("numero"):
        todas = {**PROPS, **ORIGEM}
        return _ok({"dados": [_resumo(p) for p in todas.values() if str(p["numero"]) == q["numero"] and str(p["ano"]) == q.get("ano")
                              and p["siglaTipo"] == q.get("siglaTipo")], "links": []})
    if netloc == CD and path == "/api/v2/proposicoes":
        if q.get("siglaTipo") == "MPV":
            return _ok({"dados": [_resumo(p) for p in PROPS.values() if p["siglaTipo"] == "MPV" and str(p["ano"]) == q.get("ano")], "links": []})
        ini = q.get("dataApresentacaoInicio", "")
        return _ok({"dados": [_resumo(p) for p in PROPS.values() if p["dataApresentacao"][:10] >= ini], "links": []})
    if netloc == CD and path.startswith("/api/v2/proposicoes/"):
        partes = path.split("/")
        i = int(partes[4]) if partes[4].isdigit() else 0
        todas = {**PROPS, **ORIGEM, **DOCS}
        if i not in todas:
            return 404, b"", "text/html"
        if len(partes) == 5:
            return _ok({"dados": todas[i]})
        if partes[5] == "autores":
            return _ok({"dados": AUTORES.get(i, [])})
        if partes[5] == "tramitacoes":
            return _ok({"dados": TRAM.get(i, [])})
        if partes[5] == "relacionadas":
            return _ok({"dados": RELACIONADAS.get(i, [])})
    if netloc == CD and path == "/api/v2/orgaos":
        nomes = {"CCJC": "Comissão de Constituição e Justiça e de Cidadania", "CVT": "Comissão de Viação e Transportes", "CMO": "Comissão Mista de Orçamento"}
        s = q.get("sigla", "")
        return _ok({"dados": [{"sigla": s, "nome": nomes[s]}] if s in nomes else []})
    if netloc == SF and path.startswith("/dadosabertos/plenario/agenda/mes/"):
        return _ok({"AgendaPlenario": {"Sessoes": {"Sessao": [
            {"Data": _d(2).isoformat(), "Hora": "14:00", "TipoSessao": "SESSÃO DELIBERATIVA ORDINÁRIA ", "Casa": "SF",
             "CodigoSessao": "8001", "SituacaoSessao": "Agendada",
             "Materias": {"Materia": [
                 {"CodigoMateria": "6001", "SiglaMateria": "PL", "NumeroMateria": "00200", "AnoMateria": "2025",
                  "Ementa": "Dispõe sobre bibliotecas.", "Apreciacao": "Discussão, em turno único",
                  "Parecer": "Parecer favorável da CE."},
                 {"CodigoMateria": "6004", "SiglaMateria": "PL", "NumeroMateria": "00250", "AnoMateria": "2024",
                  "Ementa": "Dispõe sobre o transporte escolar rural.", "Apreciacao": "Discussão, em turno único", "Parecer": ""}]}}]}}})
    if netloc == SF and path.startswith("/dadosabertos/processo/"):
        pid = path.rsplit("/", 1)[1]
        return _ok(PROCESSOS[pid]) if pid in PROCESSOS else (404, b"", "text/html")
    if netloc == SF and path.startswith("/sdleg-getter/documento/"):
        doc = path.rsplit("/", 1)[1]
        return (200, pdf(TEXTOS_SF[doc]), "application/pdf") if doc in TEXTOS_SF else (404, b"", "text/html")
    if netloc == SF and path.startswith("/dadosabertos/comissao/agenda/"):
        return _ok({"AgendaReuniao": {"reunioes": {"reuniao": []}}})
    if netloc == SF and path == "/dadosabertos/processo":
        base = {"casaIdentificadora": "SF", "tramitando": "Sim", "tipoDocumento": "Projeto de Lei Ordinária"}
        p250 = {**base, "id": 7250, "codigoMateria": 6004, "identificacao": "PL 250/2024", "ementa": "Dispõe sobre o transporte escolar rural.",
                "autoria": "Câmara dos Deputados", "dataApresentacao": _d(-60).isoformat(), "objetivo": "Revisora",
                "situacaoAtual": "PRONTA PARA A PAUTA NO PLENÁRIO", "dataSituacaoAtual": _d(-2).isoformat()}
        p200 = {**base, "id": 7200, "codigoMateria": 6001, "identificacao": "PL 200/2025", "ementa": "Dispõe sobre bibliotecas.",
                "autoria": "Senador Ficticio 00 (PT/SP)", "dataApresentacao": "2025-03-01", "objetivo": "Iniciadora",
                "situacaoAtual": "PRONTA PARA A PAUTA NO PLENÁRIO", "dataSituacaoAtual": _d(-2).isoformat()}
        p300 = {**base, "codigoMateria": 6002, "identificacao": "PL 300/2026", "ementa": "Institui a Semana do Livro.",
                "autoria": "Senador Ficticio 01 (PT/MG), Senadora Ficticia Nova (PL/RJ)", "dataApresentacao": _d(-2).isoformat(),
                "objetivo": "Iniciadora", "situacaoAtual": "AGUARDANDO DESPACHO", "dataSituacaoAtual": _d(-2).isoformat()}
        req = {**base, "codigoMateria": 6003, "identificacao": "REQ 9/2026", "ementa": "Requer informações.", "autoria": "x",
               "dataApresentacao": _d(-1).isoformat(), "objetivo": "Iniciadora", "situacaoAtual": "APROVADO"}
        if q.get("sigla"):
            return _ok([p for p in (p200, p250, p300) if p["identificacao"] == f"{q['sigla']} {q.get('numero')}/{q.get('ano')}"])
        return _ok([p300, req])
    return None


SFDOC = f"https://{SF}/sdleg-getter/documento/"
TEXTOS_SF = {
    "pl200": "PROJETO DE LEI\nJUSTIFICAÇÃO\nAs bibliotecas públicas ampliam o acesso das famílias à leitura, porque muitas cidades "
             "não têm livraria.\nSala das Sessões",
    "rel200": "I – RELATÓRIO\nVem à análise o projeto.\nII – ANÁLISE\nO projeto vai custar R$ 50 milhões por ano aos municípios, "
              "sem dizer de onde vem o dinheiro, e pode prejudicar outras áreas da educação.\nIII – VOTO\nPela rejeição.",
}
PROCESSOS = {
    "7200": {"id": 7200, "siglaCasaIniciadora": "SF", "objetivo": "Iniciadora",
             "documento": {"url": SFDOC + "pl200", "dataApresentacao": "2025-03-01"},
             "autoriaIniciativa": [{"autor": "Ficticio 00", "siglaTipo": "SENADOR", "siglaPartido": "PT", "ordem": 1}],
             "autuacoes": [{"informesLegislativos": [
                 {"data": f"{_d(-10).isoformat()} 10:00:00", "colegiado": {"sigla": "CE", "nome": "Comissão de Educação e Cultura"},
                  "descricao": "Recebido o relatório do Senador Ficticio 01, com voto pela rejeição do projeto.",
                  "documentosAssociados": [{"siglaTipo": "RELATORIO", "autoria": "Senador Ficticio 01 (PT/MG)", "url": SFDOC + "rel200"}]}]}]},
    "7250": {"id": 7250, "siglaCasaIniciadora": "CD", "objetivo": "Revisora",
             "documento": {"url": SFDOC + "aut250", "dataApresentacao": _d(-60).isoformat()},
             "autoriaIniciativa": [{"autor": "Deputado Ficticio 05", "siglaTipo": "DEPUTADO", "siglaPartido": "PSOL",
                                    "cargo": "Deputado Federal", "ordem": 1}],
             "outrosNumeros": [{"sigla": "PL", "numero": "00250", "ano": 2024, "casaIdentificadora": "CD"}],
             "autuacoes": []},
}
