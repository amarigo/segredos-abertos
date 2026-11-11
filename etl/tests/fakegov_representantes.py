"""Respostas fictícias do TSE para "Quem me representa": a API do Portal de Dados Abertos (CKAN) e os ZIPs de
candidatos e de vagas no CDN, no mesmo formato dos oficiais (latin-1, ';', aspas, um CSV por estado e o _BRASIL), e o
site de resultados (lista de eleições ele-c.json e o resultado de cada cidade, …-u.json), no formato real.

Casos que os testes cobrem:
- São Paulo: prefeito eleito no 2º turno; o vice teve a candidatura trocada (uma linha INAPTO, outra APTO).
- Campinas: o prefeito disputou deputado federal em 2026 (teve de renunciar; a página diz que o vice assume).
- Cidade Anulada (MG): eleição suplementar de prefeito em 2026 (só no site de resultados, como no TSE de verdade).
- Vila Recontada (MG): eleição de 2024 anulada; vereadores eleitos de novo numa suplementar; a de prefeito ainda não
  tem resultado e a página mostra o aviso do TSE.
- Belo Horizonte: o TSE lista menos vereadores eleitos do que vagas (totalização ainda não concluída no site).
- Santa Bárbara d'Oeste: nome com apóstrofo.
- Minas Gerais: o governador disputou o Senado em 2026; um deputado estadual tentou a reeleição.
- Presidente: disputou a reeleição (não precisa renunciar).
- 2025: o pacote não existe no CKAN e o arquivo não existe no CDN (404).
- Uma linha de 2024 é de uma eleição suplementar do mandato anterior: fica de fora.
"""
from __future__ import annotations

import io
import json
import zipfile
import zlib

CKAN = "dadosabertos.tse.jus.br"
CDN = "cdn.tse.jus.br"

COLS = ["DT_GERACAO", "ANO_ELEICAO", "CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO", "NR_TURNO", "CD_ELEICAO", "DT_ELEICAO",
        "SG_UF", "SG_UE", "NM_UE", "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO",
        "NM_URNA_CANDIDATO", "NR_CPF_CANDIDATO", "DS_EMAIL", "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND",
        "SG_PARTIDO", "DT_NASCIMENTO", "DS_SIT_TOT_TURNO"]

ORD, SUP = "ELEIÇÃO ORDINÁRIA", "ELEIÇÃO SUPLEMENTAR"
_sq = [100]


def _c(ano, uf, ue, nm_ue, cargo, nr, nome, urna, partido, nasc, sit, turno=1, apto="APTO", det="DEFERIDO",
       tipo=ORD, data=None):
    _sq[0] += 1
    data = data or {2022: "02/10/2022", 2024: "06/10/2024", 2026: "04/10/2026"}[ano]
    if turno == 2:
        data = {2022: "30/10/2022", 2024: "27/10/2024", 2026: "25/10/2026"}.get(ano, data)
    return {"DT_GERACAO": "01/11/2026", "ANO_ELEICAO": str(ano), "CD_TIPO_ELEICAO": "2" if tipo == ORD else "1",
            "NM_TIPO_ELEICAO": tipo, "NR_TURNO": str(turno), "CD_ELEICAO": "1", "DT_ELEICAO": data, "SG_UF": uf,
            "SG_UE": ue, "NM_UE": nm_ue, "CD_CARGO": cargo, "DS_CARGO": "X", "SQ_CANDIDATO": f"{ano}{_sq[0]:06d}",
            "NR_CANDIDATO": nr, "NM_CANDIDATO": nome, "NM_URNA_CANDIDATO": urna, "NR_CPF_CANDIDATO": "12345678909",
            "DS_EMAIL": "x@x.com", "DS_SITUACAO_CANDIDATURA": apto, "DS_DETALHE_SITUACAO_CAND": det,
            "SG_PARTIDO": partido, "DT_NASCIMENTO": nasc, "DS_SIT_TOT_TURNO": sit}


def _vereadores(ue, nome_ue, uf, n, partido_de=("PT", "PL", "MDB", "PSD", "UNIÃO")):
    return [_c(2024, uf, ue, nome_ue, "13", f"{10000 + i}", f"VEREADOR {i:02d} DE {nome_ue}", f"VER {i:02d} {nome_ue}",
               partido_de[i % len(partido_de)], f"{1 + i % 28:02d}/03/1970", "ELEITO POR QP" if i % 3 else "ELEITO POR MÉDIA")
            for i in range(n)]


def candidatos(ano: int) -> list[dict]:
    if ano == 2024:
        sp = [_c(2024, "SP", "71072", "SÃO PAULO", "11", "15", "RICARDO NUNES FICTICIO", "RICARDO FICTICIO", "MDB", "13/11/1967", "2º TURNO"),
              _c(2024, "SP", "71072", "SÃO PAULO", "11", "15", "RICARDO NUNES FICTICIO", "RICARDO FICTICIO", "MDB", "13/11/1967", "ELEITO", turno=2),
              _c(2024, "SP", "71072", "SÃO PAULO", "11", "50", "OUTRO CANDIDATO", "OUTRO", "PSOL", "01/01/1980", "NÃO ELEITO", turno=2),
              _c(2024, "SP", "71072", "SÃO PAULO", "12", "15", "VICE QUE DESISTIU", "VICE DESISTIU", "PL", "02/02/1960", "#NULO#", apto="INAPTO", det="RENÚNCIA"),
              _c(2024, "SP", "71072", "SÃO PAULO", "12", "15", "MELLO ARAUJO FICTICIO", "CORONEL MELLO", "PL", "03/03/1961", "ELEITO", turno=2)]
        sp += _vereadores("71072", "SÃO PAULO", "SP", 7)
        camp = [_c(2024, "SP", "62910", "CAMPINAS", "11", "45", "DARIO JORGE FICTICIO", "DARIO", "REPUBLICANOS", "26/07/1960", "ELEITO"),
                _c(2024, "SP", "62910", "CAMPINAS", "12", "45", "WANDAO FICTICIO", "WANDÃO", "PSD", "05/05/1965", "#NULO#")]
        camp += _vereadores("62910", "CAMPINAS", "SP", 5)
        sbo = [_c(2024, "SP", "70670", "SANTA BÁRBARA D'OESTE", "11", "22", "RAFAEL PIOVEZAN FICTICIO", "RAFAEL PIOVEZAN", "PL", "10/10/1980", "ELEITO"),
               _c(2024, "SP", "70670", "SANTA BÁRBARA D'OESTE", "12", "22", "VICE SBO", "VICE SBO", "PP", "11/10/1980", "#NULO#")]
        sbo += _vereadores("70670", "SANTA BÁRBARA D'OESTE", "SP", 3)
        bh = [_c(2024, "MG", "41238", "BELO HORIZONTE", "11", "55", "FUAD NOMAN FICTICIO", "FUAD", "PSD", "18/06/1947", "ELEITO", turno=2),
              _c(2024, "MG", "41238", "BELO HORIZONTE", "12", "55", "ALVARO DAMIAO FICTICIO", "ÁLVARO DAMIÃO", "UNIÃO", "20/02/1970", "#NULO#", turno=2)]
        bh += _vereadores("41238", "BELO HORIZONTE", "MG", 4)
        anul = [_c(2024, "MG", "40000", "CIDADE ANULADA", "11", "10", "PREFEITO CASSADO", "CASSADO", "PP", "01/01/1950", "ELEITO", det="CASSADO COM RECURSO"),
                _c(2024, "MG", "40000", "CIDADE ANULADA", "12", "10", "VICE CASSADO", "VICE CASSADO", "PP", "02/01/1950", "#NULO#")]
        anul += _vereadores("40000", "CIDADE ANULADA", "MG", 3)
        # Vila Recontada: ninguém eleito em 2024 (eleição anulada); só o vice aparece no arquivo, como no TSE
        anul += [_c(2024, "MG", "40001", "VILA RECONTADA", "12", "20", "VICE SEM CHAPA", "VICE SEM CHAPA", "PV", "03/01/1950", "#NULO#")]
        # suplementar de 2024 do mandato anterior: não pode virar o prefeito de hoje
        velha = [_c(2024, "MG", "41238", "BELO HORIZONTE", "11", "99", "PREFEITO TAMPAO", "TAMPÃO", "NOVO", "01/01/1966", "ELEITO", tipo=SUP, data="03/03/2024")]
        return sp + camp + sbo + bh + anul + velha
    if ano == 2022:
        r = [_c(2022, "BR", "BR", "BRASIL", "1", "13", "LUIZ INACIO FICTICIO", "LULA FICTICIO", "PT", "27/10/1945", "2º TURNO"),
             _c(2022, "BR", "BR", "BRASIL", "1", "13", "LUIZ INACIO FICTICIO", "LULA FICTICIO", "PT", "27/10/1945", "ELEITO", turno=2),
             _c(2022, "BR", "BR", "BRASIL", "2", "13", "GERALDO FICTICIO", "ALCKMIN FICTICIO", "PSB", "07/11/1952", "#NULO#"),
             _c(2022, "MG", "MG", "MINAS GERAIS", "3", "30", "ROMEU ZEMA FICTICIO", "ZEMA FICTICIO", "NOVO", "28/10/1964", "ELEITO"),
             _c(2022, "MG", "MG", "MINAS GERAIS", "4", "30", "MATEUS SIMOES FICTICIO", "MATEUS SIMÕES", "NOVO", "29/10/1975", "#NULO#"),
             _c(2022, "SP", "SP", "SÃO PAULO", "3", "10", "TARCISIO FICTICIO", "TARCÍSIO", "REPUBLICANOS", "19/06/1975", "ELEITO", turno=2),
             _c(2022, "SP", "SP", "SÃO PAULO", "4", "10", "FELICIO FICTICIO", "FELICIO RAMUTH", "PSD", "20/06/1968", "#NULO#", turno=2),
             _c(2022, "DF", "DF", "DISTRITO FEDERAL", "3", "15", "IBANEIS FICTICIO", "IBANEIS", "MDB", "15/07/1971", "ELEITO"),
             _c(2022, "DF", "DF", "DISTRITO FEDERAL", "4", "15", "CELINA FICTICIA", "CELINA LEÃO", "PP", "15/07/1977", "#NULO#")]
        r += [_c(2022, "MG", "MG", "MINAS GERAIS", "7", f"{30000 + i}", f"ESTADUAL {i} DE MINAS", f"ESTADUAL {i}", ["PL", "PT", "NOVO"][i % 3],
                 f"{1 + i:02d}/05/1975", "ELEITO POR QP") for i in range(4)]
        r += [_c(2022, "SP", "SP", "SÃO PAULO", "7", f"{40000 + i}", f"ESTADUAL {i} DE SAO PAULO", f"ESTADUAL SP {i}", ["PL", "PT"][i % 2],
                 f"{1 + i:02d}/06/1975", "ELEITO POR QP") for i in range(3)]
        r += [_c(2022, "DF", "DF", "DISTRITO FEDERAL", "8", f"{50000 + i}", f"DISTRITAL {i}", f"DISTRITAL {i}", "PL",
                 f"{1 + i:02d}/07/1975", "ELEITO POR MÉDIA") for i in range(2)]
        r += [_c(2022, "MG", "MG", "MINAS GERAIS", "7", "39999", "NAO ELEITO", "NAO ELEITO", "PCO", "01/01/1990", "SUPLENTE")]
        return r
    if ano == 2026:
        return [_c(2026, "BR", "BR", "BRASIL", "1", "13", "LUIZ INACIO FICTICIO", "LULA", "PT", "27/10/1945", "ELEITO"),
                _c(2026, "MG", "MG", "MINAS GERAIS", "5", "300", "ROMEU ZEMA FICTICIO", "ZEMA", "NOVO", "28/10/1964", "ELEITO"),
                _c(2026, "SP", "SP", "SÃO PAULO", "6", "4545", "DARIO JORGE FICTICIO", "DARIO", "PSD", "26/07/1960", "NÃO ELEITO"),
                # homônimo de outro estado, nascido em outro dia: não é o prefeito de São Paulo
                _c(2026, "BA", "BA", "BAHIA", "6", "1515", "RICARDO NUNES FICTICIO", "RICARDO", "MDB", "14/11/1967", "SUPLENTE"),
                _c(2026, "MG", "MG", "MINAS GERAIS", "7", "30000", "ESTADUAL 0 DE MINAS", "ESTADUAL 0", "PL", "01/05/1975", "ELEITO POR QP"),
                # o prefeito eleito na suplementar disputou deputado estadual (liga pelo nome e nascimento do site)
                _c(2026, "MG", "MG", "MINAS GERAIS", "7", "40404", "PREFEITO NOVO FICTICIO", "PREFEITO NOVO", "PSB", "01/01/1971", "SUPLENTE"),
                # linha suplementar no arquivo de 2026: fica de fora (as suplementares vêm do site de resultados)
                _c(2026, "MG", "40000", "CIDADE ANULADA", "11", "77", "NAO E ESTE", "NÃO É ESTE", "PSB", "01/01/1971",
                   "ELEITO", tipo=SUP, data="05/04/2026")]
    return []


VAGAS = {2024: [("71072", "13", 7), ("71072", "11", 1), ("62910", "13", 5), ("70670", "13", 3), ("41238", "13", 5),
                ("40000", "13", 3), ("40001", "13", 3)],
         2022: [("MG", "7", 4), ("SP", "7", 3), ("DF", "8", 2), ("MG", "6", 53), ("SP", "6", 70), ("DF", "6", 8)]}


def _csv(linhas: list[dict], cols: list[str]) -> bytes:
    out = io.StringIO()
    out.write(";".join(f'"{c}"' for c in cols) + "\r\n")
    for r in linhas:
        out.write(";".join(f'"{r.get(c, "")}"' for c in cols) + "\r\n")
    return out.getvalue().encode("latin-1")


def zip_candidatos(ano: int) -> bytes:
    linhas = candidatos(ano)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("leiame.pdf", b"%PDF")
        for uf in sorted({r["SG_UF"] for r in linhas}):
            z.writestr(f"consulta_cand_{ano}_{uf}.csv", _csv([r for r in linhas if r["SG_UF"] == uf], COLS))
        z.writestr(f"consulta_cand_{ano}_BRASIL.csv", _csv(linhas, COLS))
    return buf.getvalue()


def zip_vagas(ano: int) -> bytes:
    cols = ["ANO_ELEICAO", "NM_TIPO_ELEICAO", "SG_UF", "SG_UE", "CD_CARGO", "QT_VAGA"]
    linhas = [{"ANO_ELEICAO": str(ano), "NM_TIPO_ELEICAO": ORD, "SG_UF": ue if len(ue) == 2 else "SP", "SG_UE": ue,
               "CD_CARGO": c, "QT_VAGA": str(n)} for ue, c, n in VAGAS.get(ano, [])]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"consulta_vagas_{ano}_BRASIL.csv", _csv(linhas, cols))
    return buf.getvalue()


# ---------------------------------------------------------------- site de resultados do TSE

RESULTADOS = "resultados.tse.jus.br"


def _sup(ciclo, cd, data, uf, mu, cargo, nome):
    return {"cd": str(int(cd) + 1000), "c": ciclo, "dt": data, "e": [
        {"cd": cd, "cdt2": "", "nm": f"Eleição Suplementar - {nome}", "t": "1", "tp": "4",
         "abr": [{"cd": uf, "mu": [{"cd": mu, "cdi": "0"}], "cp": [{"cd": cargo, "ds": "X", "tp": "1"}]}]}]}


ELEICOES = {"dg": "29/09/2026", "hg": "19:26:27", "f": "o", "pl": [
    {"cd": "452", "c": "ele2024", "dt": "06/10/2024", "e": [{"cd": "619", "cdt2": "620", "nm": "Eleição Ordinária Municipal - 2024 - 06/10/2024 1º Turno", "t": "1", "tp": "3", "abr": [{"cd": "br", "cp": [{"cd": "11"}, {"cd": "13"}]}]}]},
    _sup("ele2024", "6100", "05/04/2026", "mg", "40000", "11", "Cidade Anulada"),
    _sup("ele2024", "6269", "17/05/2026", "mg", "40001", "13", "Vila Recontada"),
    _sup("ele2026", "6299", "06/12/2026", "mg", "40001", "11", "Vila Recontada"),
    _sup("ele2024", "6247", "07/12/2025", "sp", "62910", "13", "Campinas"),  # só uma cadeira
    # suplementar do mandato anterior (antes do 2º turno de 2024): não pode trocar o prefeito de hoje
    _sup("ele2020", "555", "03/03/2024", "mg", "41238", "11", "Belo Horizonte"),
]}


def _cand(n, nm, nmu, nasc, e, st, vice=None, sq=""):
    c = {"n": n, "sqcand": sq or f"9{zlib.crc32(nm.encode()):010d}", "nm": nm, "nmu": nmu, "dt": nasc, "dvt": "Válido",
         "e": e, "st": st}
    if vice:
        c["vs"] = [{"tp": "v", "sqcand": "9" + c["sqcand"][1:], "nm": vice[0], "nmu": vice[1], "sgp": vice[2]}]
    return c


def _arquivo(ele, tf, cands, mnae=(), dt="06/10/2024", nv="1"):
    """cands: [(partido, cand)]; nv: cadeiras em disputa"""
    return {"ele": ele, "t": "1", "f": "o", "tf": "s" if tf else "n", "dt": dt, "mnae": list(mnae),
            "carg": [{"cd": "11", "nv": nv, "agr": [{"n": "1", "par": [{"n": "1", "sg": p, "cand": [c]} for p, c in cands]}]}]}


ARQUIVOS = {
    "/oficial/ele2024/6100/dados/mg/mg40000-c0011-e006100-u.json": _arquivo("6100", True, [
        ("PSB", _cand("40", "PREFEITO NOVO FICTICIO", "PREFEITO NOVO", "01/01/1971", "s", "Eleito", ("VICE NOVO FICTICIO", "VICE NOVO", "PT"))),
        ("PL", _cand("22", "PERDEU A SUPLEMENTAR", "PERDEU", "02/02/1970", "n", "Não eleito"))], dt="05/04/2026"),
    "/oficial/ele2024/6269/dados/mg/mg40001-c0013-e006269-u.json": _arquivo("6269", True, [
        ("PT", _cand("13001", "VEREADORA NOVA UM", "NOVA UM", "01/02/1980", "s", "Eleito por QP")),
        ("PL", _cand("22002", "VEREADOR NOVO DOIS", "NOVO DOIS", "02/02/1980", "s", "Eleito por média")),
        ("PL", _cand("22003", "VEREADOR NOVO TRES", "NOVO TRÊS", "03/02/1980", "s", "Eleito por QP")),
        ("MDB", _cand("15004", "SUPLENTE QUATRO", "SUPLENTE", "04/02/1980", "n", "Suplente"))], dt="17/05/2026", nv="3"),
    "/oficial/ele2024/6247/dados/sp/sp62910-c0013-e006247-u.json": _arquivo("6247", True, [
        ("PP", _cand("11111", "EVERTON FICTICIO", "EVERTON", "05/05/1985", "s", "Eleito por QP")),
        ("PP", _cand("11112", "VITORIA FICTICIA", "VITORIA", "06/05/1985", "n", "Suplente"))], dt="07/12/2025", nv="1"),
    "/oficial/ele2024/619/dados/mg/mg40001-c0011-e000619-u.json": _arquivo("619", True, [
        ("PP", _cand("11", "MAIS VOTADO ANULADO", "ANULADO", "01/01/1960", "n", "Não eleito"))],
        mnae=["Votos anulados ultrapassam 50% da votação nominal, incluindo votos de seções anuladas."]),
    "/oficial/ele2024/619/dados/mg/mg41238-c0013-e000619-u.json": _arquivo("619", False, []),
}


def rota_resultados(path: str) -> tuple[int, bytes, str] | None:
    if path == "/oficial/comum/config/ele-c.json":
        return 200, json.dumps(ELEICOES).encode(), "application/json"
    if path in ARQUIVOS:
        return 200, json.dumps(ARQUIVOS[path]).encode(), "application/json"
    return 404, b"<html>404</html>", "text/html"


def rota(host: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
    if host == RESULTADOS and path.startswith("/oficial/"):
        return rota_resultados(path)
    if host == CKAN and path == "/api/3/action/package_show":
        ano = int(str(q.get("id", "0")).rsplit("-", 1)[-1] or 0)
        if ano not in (2022, 2024, 2026):
            return 404, json.dumps({"success": False, "error": {"message": "Não encontrado"}}).encode(), "application/json"
        res = [{"name": n, "url": f"https://{CDN}/estatistica/sead/odsele/{t}/{t}_{ano}.zip"}
               for t, n in (("consulta_cand", "Candidatos"), ("consulta_vagas", "Vagas"))]
        return 200, json.dumps({"success": True, "result": {"resources": res}}).encode(), "application/json"
    if host == CDN and path.startswith("/estatistica/sead/odsele/consulta_"):
        nome = path.rsplit("/", 1)[-1]
        for t, f in (("consulta_cand_", zip_candidatos), ("consulta_vagas_", zip_vagas)):
            if nome.startswith(t) and nome.endswith(".zip"):
                ano = int(nome[len(t):-4])
                if ano in (2022, 2024, 2026):
                    return 200, f(ano), "application/zip"
        return 404, b"<html>404</html>", "text/html"
    return None
