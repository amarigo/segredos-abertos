"""Respostas fictícias do TSE (API do portal de dados abertos e arquivos do CDN) e do arquivo de deputados da Câmara:
o que o patrimônio declarado lê. O detalhe de cada senador fica no fakegov.py. Os eleitos de estados e cidades
(Quem me representa) ficam no fakegov_representantes.py.

Os arquivos imitam os de verdade: CSV latin-1 com ';' dentro de ZIP, um _BRASIL.csv, e com as colunas que o site
não pode ler (CPF, e-mail, título de eleitor, descrição do bem). Os testes conferem que nada disso chega ao site.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

import fakegov_tse  # noqa: E402  (mesma pasta dos testes)

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
GERAIS = set(range(2014, 2100, 4))
CPF_FALSO = "12345678901"
EMAIL_FALSO = "fulano@exemplo.com"
DESCRICAO_FALSA = "APARTAMENTO NA RUA FICTICIA 123, PLACA ABC1D23"

COL_CAND = ["DT_GERACAO", "ANO_ELEICAO", "NM_TIPO_ELEICAO", "NR_TURNO", "DS_ELEICAO", "DT_ELEICAO", "SG_UF", "SG_UE",
            "NM_UE", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "NR_CPF_CANDIDATO",
            "DS_EMAIL", "SG_PARTIDO", "DT_NASCIMENTO", "NR_TITULO_ELEITORAL_CANDIDATO", "DS_SITUACAO_CANDIDATURA",
            "DS_SIT_TOT_TURNO"]
COL_BEM = ["ANO_ELEICAO", "SG_UF", "SQ_CANDIDATO", "NR_ORDEM_BEM_CANDIDATO", "DS_TIPO_BEM_CANDIDATO", "DS_BEM_CANDIDATO",
           "VR_BEM_CANDIDATO"]


def nascimento(i: int) -> str:
    return f"19{60 + i % 30}-{1 + i % 12:02d}-{1 + i % 27:02d}"


def _br(d: str) -> str:
    return f"{d[8:10]}/{d[5:7]}/{d[0:4]}"


def _valor(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _zip(nome: str, cab: list[str], linhas: list[list]) -> bytes:
    def csv(ls):
        return "\n".join(";".join(f'"{x}"' for x in ln) for ln in [cab] + ls).encode("latin-1")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{nome}_BRASIL.csv", csv(linhas))
        z.writestr(f"{nome}_SP.csv", csv([x for x in linhas if "SP" in x]))  # arquivo por estado: não é lido
        z.writestr("leiame.pdf", b"%PDF")
    return buf.getvalue()


class TSE:
    def __init__(self, deputados: list[dict], senadores: list[dict]):
        # nome civil e nascimento de cada parlamentar (o TSE não usa o código da Câmara nem o do Senado)
        # Os mesmos nomes civis das contas de campanha (fakegov_tse): no governo de verdade, a pessoa é uma só.
        self.civil = {f"dep-{d['id']}": (fakegov_tse.nome_civil_deputado(d["id"] - 1000).upper(), nascimento(d["id"]))
                      for d in deputados}
        self.civil |= {f"sen-{s['cod']}": (fakegov_tse.nome_civil_senador(i).upper(), nascimento(s["cod"]))
                       for i, s in enumerate(senadores)}
        self.pedidos_cdn = 0
        self.ckan_fora = False

    # ---------- linhas
    def _cand(self, ano: int) -> tuple[list[list], list[list]]:
        cands, bens = [], []
        sq = [ano * 100000]

        def add(uf, ue, nm_ue, cargo, nome, urna, partido, nasc, res, turno=1, tipo="ELEIÇÃO ORDINÁRIA",
                data=f"{ano}-10-02", bens_=((("Apartamento", 500000.0), ("Veículo automotor terrestre", 80000.0))),
                eleicao=None, sit="DEFERIDO"):
            sq[0] += 1
            s = str(sq[0])
            for t in range(1, turno + 1):
                cands.append(["01/11/2026", ano, tipo, t, eleicao or f"Eleições {ano}", _br(data), uf, ue, nm_ue, cargo, s,
                              str(10 + len(cands)), nome, urna, CPF_FALSO, EMAIL_FALSO, partido, _br(nasc), "012345678901",
                              sit, res if t == turno else "2º TURNO"])
            for i, (tipo_bem, v) in enumerate(bens_):
                bens.append([ano, uf, s, i + 1, tipo_bem, DESCRICAO_FALSA, _valor(v)])
            return s

        geral = ano in GERAIS
        # parlamentares do site: cada um se candidatou a deputado federal ou senador nas eleições gerais;
        # nas municipais, só os primeiros (alguns foram candidatos a prefeito)
        for k, (pid, (nome, nasc)) in enumerate(sorted(self.civil.items())):
            if not geral and k % 5:
                continue
            cargo = ("DEPUTADO FEDERAL" if pid.startswith("dep") else "SENADOR") if geral else "PREFEITO"
            valor = 100000.0 * (1 + k) * (1 + (ano - 2014) / 10)
            add("SP", "SP" if geral else "71072", "SÃO PAULO", cargo, nome, nome.split()[0], "PT", nasc,
                "ELEITO" if geral else "NÃO ELEITO", bens_=(("Casa", valor), ("Depósito bancário em conta-corrente", 1000.0)))
        return cands, bens

    @staticmethod
    def _pacote(a: str) -> dict:
        res = [{"url": f"{CDN}/{p}/{p}_{a}.zip", "format": "ZIP"} for p in ("consulta_cand", "bem_candidato")]
        res.append({"url": f"{CDN}/consulta_cand/leiame-{a}.pdf", "format": "PDF"})
        return {"name": f"candidatos-{a}" + ("-subtemas" if a == "2020" else ""), "resources": res}

    # ---------- rotas
    def rota(self, netloc: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
        if netloc == "dadosabertos.tse.jus.br" and path == "/api/3/action/package_show":
            if self.ckan_fora:
                return 503, b"", "text/html"
            # o pacote de 2020 tem outro nome no portal ("candidatos-2020-subtemas"): só a busca acha
            m = re.fullmatch(r"candidatos-(\d{4})(-subtemas)?", q.get("id", ""))
            if not m or (m.group(1) == "2020") != bool(m.group(2)):
                return 404, b"", "application/json"
            return 200, json.dumps({"success": True, "result": self._pacote(m.group(1))}).encode(), "application/json"
        if netloc == "dadosabertos.tse.jus.br" and path == "/api/3/action/package_search":
            m = re.fullmatch(r"name:candidatos-(\d{4})\*", q.get("q", ""))
            res = [self._pacote(m.group(1))] if m else []
            return 200, json.dumps({"success": True, "result": {"count": len(res), "results": res}}).encode(), "application/json"
        if netloc == "cdn.tse.jus.br":
            m = re.fullmatch(r"/estatistica/sead/odsele/(consulta_cand|bem_candidato)/\1_(\d{4})\.zip", path)
            if not m:
                return 404, b"", "text/html"
            self.pedidos_cdn += 1
            tipo, ano = m.group(1), int(m.group(2))
            cands, bens = self._cand(ano)
            if tipo == "consulta_cand":
                return 200, _zip(f"consulta_cand_{ano}", COL_CAND, cands), "application/zip"
            return 200, _zip(f"bem_candidato_{ano}", COL_BEM, bens), "application/zip"
        if netloc == "dadosabertos.camara.leg.br" and path == "/arquivos/deputados/json/deputados.json":
            return 200, json.dumps({"dados": [
                {"uri": f"https://dadosabertos.camara.leg.br/api/v2/deputados/{pid[4:]}", "nome": nome.title(),
                 "nomeCivil": nome, "dataNascimento": nasc}
                for pid, (nome, nasc) in self.civil.items() if pid.startswith("dep-")]}).encode(), "application/json"
        return None  # o detalhe de cada senador (nome civil e nascimento) fica no fakegov.py
