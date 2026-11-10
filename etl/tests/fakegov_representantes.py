"""Respostas fictícias do TSE para "Quem me representa": a API do Portal de Dados Abertos (CKAN) e os ZIPs de
candidatos e de vagas no CDN, no mesmo formato dos oficiais (latin-1, ';', aspas, um CSV por estado e o _BRASIL).

Casos que os testes cobrem:
- São Paulo: prefeito eleito no 2º turno; o vice teve a candidatura trocada (uma linha INAPTO, outra APTO).
- Campinas: o prefeito disputou deputado federal em 2026 (teve de renunciar; a página diz que o vice assume).
- Cidade Anulada (MG): eleição suplementar de prefeito em 2026.
- Belo Horizonte: o TSE lista menos vereadores eleitos do que vagas (recontagem pendente).
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
                _c(2026, "MG", "40000", "CIDADE ANULADA", "11", "40", "PREFEITO NOVO FICTICIO", "PREFEITO NOVO", "PSB", "01/01/1971",
                   "ELEITO", tipo=SUP, data="05/04/2026"),
                _c(2026, "MG", "40000", "CIDADE ANULADA", "12", "40", "VICE NOVO FICTICIO", "VICE NOVO", "PT", "01/01/1972",
                   "#NULO#", tipo=SUP, data="05/04/2026")]
    return []


VAGAS = {2024: [("71072", "13", 7), ("71072", "11", 1), ("62910", "13", 5), ("70670", "13", 3), ("41238", "13", 5),
                ("40000", "13", 3)],
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


def rota(host: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
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
