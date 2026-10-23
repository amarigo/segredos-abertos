"""TSE simulado: gera os .zip de votação e de candidatos no formato dos arquivos de dados abertos do TSE.

Os dados são fictícios, mas o formato imita o de verdade: latin-1, ';', aspas, um CSV por estado, colunas com
CPF e e-mail que o coletor não pode ler, várias zonas por cidade, eleição suplementar, 2º turno e partidos com
nomes antigos (PMDB, PFL...). Também sabe falhar de propósito (caos): fora do ar, página de erro em HTML no lugar
do .zip, .zip cortado, arquivo sem cabeçalho, coluna faltando, arquivo sem a cidade.
"""
from __future__ import annotations

import csv
import io
import random
import re
import zipfile

import requests

CIDADES = ["ITAJUBÁ", "PARAISÓPOLIS", "POUSO ALEGRE"]
VOT_COLS = ["DT_GERACAO", "ANO_ELEICAO", "CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO", "NR_TURNO", "SG_UF", "SG_UE", "NM_UE",
            "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO",
            "NM_URNA_CANDIDATO", "NR_CPF_CANDIDATO", "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND", "SG_PARTIDO",
            "NM_COLIGACAO", "DS_COMPOSICAO_COLIGACAO", "QT_VOTOS_NOMINAIS", "QT_VOTOS_NOMINAIS_VALIDOS", "DS_SIT_TOT_TURNO"]
CAND_COLS = ["ANO_ELEICAO", "CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO", "SG_UF", "NM_UE", "DS_CARGO", "SQ_CANDIDATO",
             "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "NR_CPF_CANDIDATO", "DS_EMAIL", "SG_PARTIDO",
             "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND"]
CPF_FALSO = "12345678909"


def partidos_do_ano(ano: int) -> list[str]:
    if ano <= 2004:
        return ["PMDB", "PFL", "PSDB", "PT", "PPB", "PL", "PTB", "PC do B"]
    if ano <= 2016:
        return ["PMDB", "DEM", "PSDB", "PT", "PP", "PR", "PSB", "PT do B"]
    return ["MDB", "UNIÃO", "PSDB", "PT", "PP", "PL", "PSD", "PCdoB"]


class FakeTSE:
    def __init__(self, seed: int = 3, cidades=CIDADES, vagas: int = 9):
        self.seed = seed  # mesmos dados a cada download do mesmo ano, como o TSE de verdade
        self.cidades = list(cidades)
        self.vagas = vagas
        self.falhas: dict[str, str] = {}  # pedaço da URL -> modo
        self.chamadas: list[str] = []
        self.arquivos: dict[str, bytes] = {}
        self.esperado: dict[tuple, dict] = {}  # (cidade, ano) -> {"prefeito": nome, "partido": sigla, "vice": nome}

    # ------------------------------------------------------------ falhas (caos)
    def falhar(self, pedaco: str, modo: str) -> "FakeTSE":
        """modo: fora, html, cortado, sem_cabecalho, sem_coluna, sem_cidade, vazio"""
        self.falhas[pedaco] = modo
        return self

    def consertar(self) -> "FakeTSE":
        self.falhas.clear()
        return self

    # ------------------------------------------------------------ dados
    def _csv(self, cols: list[str], linhas: list[dict], cabecalho: bool = True) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        if cabecalho:
            w.writerow(cols)
        for ln in linhas:
            w.writerow([ln.get(c, "#NULO#") for c in cols])
        return buf.getvalue().encode("latin-1")

    def municipal(self, ano: int) -> tuple[list[dict], list[dict]]:
        rng = random.Random(f"{self.seed}-{ano}")
        vot, cand = [], []
        parts = partidos_do_ano(ano)
        sq = ano * 1000
        for ci, cidade in enumerate(self.cidades):
            base = dict(ANO_ELEICAO=ano, CD_TIPO_ELEICAO=2, NM_TIPO_ELEICAO="Eleição Ordinária", SG_UF="MG", NM_UE=cidade,
                        NM_MUNICIPIO=cidade, NR_CPF_CANDIDATO=CPF_FALSO, DS_SITUACAO_CANDIDATURA="APTO",
                        DS_DETALHE_SITUACAO_CAND="DEFERIDO")
            # prefeito: 3 candidatos, 2 zonas; o 1º da lista vence
            pref = [(f"PREFEITO {cidade} {ano} {i}", parts[(ci + i + ano // 4) % len(parts)], str(10 + i * 5)) for i in range(3)]
            votos = [rng.randint(8000, 15000), rng.randint(2000, 7000), rng.randint(100, 1500)]
            venc = pref[0]
            colig = " / ".join([venc[1], parts[(ci + 3) % len(parts)], parts[(ci + 4) % len(parts)]])
            for i, (nome, partido, numero) in enumerate(pref):
                sq += 1
                for zona, frac in ((101, 0.6), (102, 0.4)):
                    v = int(votos[i] * frac)
                    vot.append({**base, "NR_TURNO": 1, "NR_ZONA": zona, "DS_CARGO": "PREFEITO", "SQ_CANDIDATO": sq,
                                "NR_CANDIDATO": numero, "NM_CANDIDATO": nome, "NM_URNA_CANDIDATO": nome.title(), "SG_PARTIDO": partido,
                                "NM_COLIGACAO": f"COLIGAÇÃO {i}", "DS_COMPOSICAO_COLIGACAO": colig if i == 0 else partido,
                                "QT_VOTOS_NOMINAIS": v, "QT_VOTOS_NOMINAIS_VALIDOS": v if ano >= 2020 else "#NULO#",
                                "DS_SIT_TOT_TURNO": "ELEITO" if i == 0 else "NÃO ELEITO"})
                # vice: um com registro indeferido (deve ser ignorado) e o de verdade
                cand.append({**base, "DS_CARGO": "VICE-PREFEITO", "NR_CANDIDATO": numero, "SG_PARTIDO": parts[(ci + 3) % len(parts)],
                             "NM_CANDIDATO": f"VICE TROCADO {nome}", "DS_SITUACAO_CANDIDATURA": "INAPTO",
                             "DS_DETALHE_SITUACAO_CAND": "INDEFERIDO", "DS_EMAIL": "x@y.com"})
                cand.append({**base, "DS_CARGO": "VICE-PREFEITO", "NR_CANDIDATO": numero, "SG_PARTIDO": parts[(ci + 3) % len(parts)],
                             "NM_CANDIDATO": f"VICE {nome}", "DS_EMAIL": "x@y.com"})
                cand.append({**base, "DS_CARGO": "PREFEITO", "NR_CANDIDATO": numero, "SG_PARTIDO": partido, "NM_CANDIDATO": nome})
            self.esperado[(cidade, ano)] = {"prefeito": venc[0].title(), "partido": venc[1], "vice": f"Vice {venc[0].title()}",
                                            "votos": votos[0]}
            # eleição suplementar no meio (cassação): não pode virar prefeito do mandato
            if ano == 2008 and ci == 0:
                vot.append({**base, "CD_TIPO_ELEICAO": 1, "NM_TIPO_ELEICAO": "Eleição Suplementar", "NR_TURNO": 1, "NR_ZONA": 101,
                            "DS_CARGO": "PREFEITO", "SQ_CANDIDATO": 9, "NR_CANDIDATO": "99", "NM_CANDIDATO": "SUPLEMENTAR FULANO",
                            "SG_PARTIDO": "PSOL", "QT_VOTOS_NOMINAIS": 99999, "DS_SIT_TOT_TURNO": "ELEITO"})
            # vereadores: 20 candidatos, `vagas` eleitos
            for i in range(20):
                sq += 1
                partido = parts[(i * 3 + ci) % len(parts)]
                sit = ("ELEITO POR QP" if i < self.vagas - 2 else ("MÉDIA" if ano <= 2004 else "ELEITO POR MÉDIA")) if i < self.vagas \
                    else ("SUPLENTE" if i < 15 else "NÃO ELEITO")
                nome = f"VEREADOR {cidade} {ano} {i:02d}"
                for zona in (101, 102):
                    v = 1000 - i * 40 + zona % 3
                    vot.append({**base, "NR_TURNO": 1, "NR_ZONA": zona, "DS_CARGO": "VEREADOR", "SQ_CANDIDATO": sq,
                                "NR_CANDIDATO": str(10000 + i), "NM_CANDIDATO": nome, "NM_URNA_CANDIDATO": nome.title(), "SG_PARTIDO": partido,
                                "NM_COLIGACAO": "PARTIDO ISOLADO", "DS_COMPOSICAO_COLIGACAO": partido,
                                "QT_VOTOS_NOMINAIS": v, "QT_VOTOS_NOMINAIS_VALIDOS": v if ano >= 2020 else "#NULO#", "DS_SIT_TOT_TURNO": sit})
        return vot, cand

    def geral(self, ano: int) -> list[dict]:
        rng = random.Random(f"{self.seed}-{ano}")
        vot, sq = [], ano * 1000
        parts = partidos_do_ano(ano)
        for cidade in self.cidades:
            base = dict(ANO_ELEICAO=ano, CD_TIPO_ELEICAO=2, NM_TIPO_ELEICAO="Eleição Ordinária", SG_UF="MG", NM_UE="MINAS GERAIS",
                        NM_MUNICIPIO=cidade, NR_ZONA=101, NR_CPF_CANDIDATO=CPF_FALSO)
            for cargo, n, turnos in (("PRESIDENTE", 4, 2), ("GOVERNADOR", 3, 1), ("SENADOR", 3, 1),
                                     ("DEPUTADO FEDERAL", 14, 1), ("DEPUTADO ESTADUAL", 14, 1)):
                for turno in range(1, turnos + 1):
                    for i in range(n if turno == 1 else 2):
                        sq += 1
                        sit = ("2º TURNO" if turnos == 2 and turno == 1 and i < 2 else
                               "ELEITO" if (turno == turnos and i == 0) else "NÃO ELEITO")
                        vot.append({**base, "NR_TURNO": turno, "DS_CARGO": cargo, "SQ_CANDIDATO": f"{cargo[:3]}{i}",
                                    "NR_CANDIDATO": str(10 + i), "NM_CANDIDATO": f"{cargo} {i}", "SG_PARTIDO": parts[i % len(parts)],
                                    "QT_VOTOS_NOMINAIS": rng.randint(100, 9000) // (i + 1), "DS_SIT_TOT_TURNO": sit})
        return vot

    def geral_cand(self, ano: int) -> list[dict]:
        """Candidatos a governador e vice (o vice vem na lista de candidatos com o número da chapa). O vice com
        registro indeferido e o de uma eleição suplementar não podem entrar."""
        parts = partidos_do_ano(ano)
        base = dict(ANO_ELEICAO=ano, CD_TIPO_ELEICAO=2, NM_TIPO_ELEICAO="Eleição Ordinária", SG_UF="MG", NM_UE="MINAS GERAIS",
                    NR_CPF_CANDIDATO=CPF_FALSO, DS_EMAIL="x@y.com", DS_SITUACAO_CANDIDATURA="APTO", DS_DETALHE_SITUACAO_CAND="DEFERIDO")
        out = []
        for i in range(3):
            out.append({**base, "DS_CARGO": "GOVERNADOR", "NR_CANDIDATO": str(10 + i), "NM_CANDIDATO": f"GOVERNADOR {i}",
                        "NM_URNA_CANDIDATO": f"Governador {i}", "SG_PARTIDO": parts[i % len(parts)]})
            out.append({**base, "DS_CARGO": "VICE-GOVERNADOR", "NR_CANDIDATO": f"0{10 + i}", "NM_CANDIDATO": f"VICE TROCADO {i}",
                        "SG_PARTIDO": parts[(i + 1) % len(parts)], "DS_SITUACAO_CANDIDATURA": "INAPTO", "DS_DETALHE_SITUACAO_CAND": "INDEFERIDO"})
            out.append({**base, "DS_CARGO": "VICE-GOVERNADOR", "NR_CANDIDATO": f"0{10 + i}", "NM_CANDIDATO": f"VICE DO GOVERNADOR {i}",
                        "NM_URNA_CANDIDATO": f"Vice do Governador {i}", "SG_PARTIDO": parts[(i + 1) % len(parts)]})
        out.append({**base, "CD_TIPO_ELEICAO": 1, "NM_TIPO_ELEICAO": "Eleição Suplementar", "DS_CARGO": "VICE-GOVERNADOR",
                    "NR_CANDIDATO": "10", "NM_CANDIDATO": "VICE SUPLEMENTAR", "SG_PARTIDO": "PSOL"})
        outro = [{**r, "SG_UF": "SP", "NM_UE": "SÃO PAULO", "NM_CANDIDATO": "VICE DE SP"} for r in out if r["DS_CARGO"] == "VICE-GOVERNADOR"][:1]
        return out + outro

    def _zip(self, tipo: str, ano: int, modo: str | None) -> bytes:
        if ano % 4 == 0:
            vot, cand = self.municipal(ano)
        else:
            vot, cand = self.geral(ano), self.geral_cand(ano)
        linhas, cols = (vot, VOT_COLS) if tipo == "votacao" else (cand, CAND_COLS)
        if modo == "sem_coluna":
            cols = [c for c in cols if c != "DS_CARGO"]
        if modo == "sem_cidade":
            linhas = [r for r in linhas if r["NM_MUNICIPIO" if "NM_MUNICIPIO" in r else "NM_UE"] != "ITAJUBÁ"]
        nome = f"{'votacao_candidato_munzona' if tipo == 'votacao' else 'consulta_cand'}_{ano}"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{nome}_MG.csv", self._csv(cols, linhas, cabecalho=modo != "sem_cabecalho"))
            # outro estado no mesmo .zip, com uma cidade de mesmo nome: não pode entrar
            outro = [{**r, "SG_UF": "SP"} for r in linhas[:5]]
            z.writestr(f"{nome}_SP.csv", self._csv(cols, outro))
            z.writestr("leiame.pdf", b"%PDF-1.4")
        return buf.getvalue()

    def responder(self, url: str) -> bytes:
        self.chamadas.append(url)
        m = re.search(r"/(votacao_candidato_munzona|consulta_cand)_(\d{4})\.zip$", url)
        if not m:
            raise requests.HTTPError(f"404 {url}")
        tipo = "votacao" if m.group(1).startswith("votacao") else "cand"
        ano = int(m.group(2))
        modo = next((mo for p, mo in self.falhas.items() if p in url), None)
        if modo == "fora":
            raise requests.ConnectionError("TSE fora do ar")
        if modo == "html":
            return b"<!doctype html><html><body>Manutencao</body></html>"
        if modo == "vazio":
            return b""
        raw = self._zip(tipo, ano, modo)
        return raw[: len(raw) // 2] if modo == "cortado" else raw


class _Resp:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200
        self.ok = True


def instalar(monkeypatch, tse: FakeTSE) -> FakeTSE:
    """Troca o download do TSE pelo FakeTSE (só o que passa por sa_etl.util.get)."""
    from sa_etl import util
    monkeypatch.setattr(util, "get", lambda url, **kw: _Resp(tse.responder(url)))
    return tse
