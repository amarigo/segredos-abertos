"""Respostas fictícias do TSE (API do portal de dados abertos e arquivos do CDN) e do arquivo de deputados da Câmara:
o que o patrimônio declarado e a página de eleitos leem. O detalhe de cada senador fica no fakegov.py.

Os arquivos imitam os de verdade: CSV latin-1 com ';' dentro de ZIP, um _BRASIL.csv, e com as colunas que o site
não pode ler (CPF, e-mail, título de eleitor, descrição do bem). Os testes conferem que nada disso chega ao site.

Casos do mundo real que estão aqui: eleição suplementar que troca o prefeito (substitui a normal), suplementar que
elege só 1 vereador (não substitui), vereadores com resultado "#NULO" (eleição anulada ou em julgamento), 2º turno.
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
COL_VAGAS = ["ANO_ELEICAO", "NM_TIPO_ELEICAO", "SG_UF", "SG_UE", "NM_UE", "DS_CARGO", "QT_VAGA"]
UFS = {"SP": "SÃO PAULO", "MG": "MINAS GERAIS"}
CIDADES = {"SP": [("71072", "SÃO PAULO"), ("62910", "CAMPINAS")], "MG": [("41238", "BELO HORIZONTE"), ("48313", "MERCÊS")]}
VAGAS_DEP, VAGAS_VER = 3, 3


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
        if geral:
            for uf, nome_uf in UFS.items():
                add(uf, uf, nome_uf, "GOVERNADOR", f"GOVERNADOR DE {uf}", f"GOV {uf}", "PSD", "1960-05-05", "ELEITO", turno=2)
                add(uf, uf, nome_uf, "VICE-GOVERNADOR", f"VICE DE {uf}", f"VICE {uf}", "PP", "1961-05-05", "ELEITO", turno=2,
                    bens_=())
                add(uf, uf, nome_uf, "GOVERNADOR", f"PERDEDOR DE {uf}", f"PERDEU {uf}", "PL", "1962-05-05", "NÃO ELEITO",
                    turno=2)
                for i in range(VAGAS_DEP):
                    add(uf, uf, nome_uf, "DEPUTADO ESTADUAL", f"ESTADUAL {uf} {i}", f"Est {uf} {i}", ["PT", "PL", "MDB"][i],
                        "1970-01-01", ["ELEITO POR QP", "ELEITO POR QP", "ELEITO POR MÉDIA"][i])
                add(uf, uf, nome_uf, "DEPUTADO ESTADUAL", f"SUPLENTE {uf}", f"Sup {uf}", "PT", "1970-01-01", "SUPLENTE")
            return cands, bens
        for uf, cidades in CIDADES.items():
            for ue, nome in cidades:
                if nome == "MERCÊS":  # o mais votado teve o registro negado: ninguém eleito para prefeito
                    add(uf, ue, nome, "PREFEITO", "MAIS VOTADO", "Mais Votado", "PL", "1970-02-02", "NÃO ELEITO",
                        sit="INDEFERIDO COM RECURSO")
                    add(uf, ue, nome, "VICE-PREFEITO", "VICE DO MAIS VOTADO", "Vice", "PL", "1970-02-02", "NÃO ELEITO")
                else:
                    add(uf, ue, nome, "PREFEITO", f"PREFEITO DE {nome}", f"Pref {nome.title()}", "MDB", "1965-03-03", "ELEITO",
                        turno=2 if nome == "SÃO PAULO" else 1)
                    add(uf, ue, nome, "VICE-PREFEITO", f"VICE DE {nome}", f"Vice {nome.title()}", "MDB", "1966-03-03", "ELEITO")
                anulada = nome == "CAMPINAS"  # vereadores "#NULO": eleição do cargo anulada ou em julgamento
                for i in range(VAGAS_VER):
                    add(uf, ue, nome, "VEREADOR", f"VEREADOR {nome} {i}", f"Ver {i}", ["PT", "PL", "PSOL"][i], "1980-04-04",
                        "#NULO" if anulada else "ELEITO POR QP", bens_=() if i == 2 else (("Terreno", 30000.0),))
                add(uf, ue, nome, "VEREADOR", f"SUPLENTE {nome}", "Sup", "PT", "1980-04-04", "#NULO" if anulada else "SUPLENTE")
        # Belo Horizonte: a eleição foi anulada e houve suplementar, que troca prefeito e vice
        sup = {"tipo": "ELEIÇÃO SUPLEMENTAR", "data": f"{ano + 1}-06-01", "eleicao": "Eleição Suplementar Belo Horizonte - MG"}
        add("MG", "41238", "BELO HORIZONTE", "PREFEITO", "PREFEITO DA SUPLEMENTAR", "Pref Novo", "PSB", "1975-05-05",
            "ELEITO", **sup)
        add("MG", "41238", "BELO HORIZONTE", "VICE-PREFEITO", "VICE DA SUPLEMENTAR", "Vice Novo", "PSB", "1975-05-05",
            "ELEITO", **sup)
        # São Paulo: suplementar para 1 cadeira de vereador (como Braga-RS em 2025): não troca os outros
        add("SP", "71072", "SÃO PAULO", "VEREADOR", "VEREADOR DA SUPLEMENTAR", "Ver Sup", "NOVO", "1985-06-06",
            "ELEITO POR QP", **{**sup, "eleicao": "Eleição Suplementar São Paulo - SP"})
        return cands, bens

    def _vagas(self, ano: int) -> list[list]:
        if ano in GERAIS:
            return [[ano, "ELEIÇÃO ORDINÁRIA", uf, uf, n, c, q] for uf, n in UFS.items()
                    for c, q in (("GOVERNADOR", 1), ("VICE-GOVERNADOR", 1), ("DEPUTADO ESTADUAL", VAGAS_DEP))]
        out = [[ano, "ELEIÇÃO ORDINÁRIA", uf, ue, n, c, q] for uf, cs in CIDADES.items() for ue, n in cs
               for c, q in (("PREFEITO", 1), ("VICE-PREFEITO", 1), ("VEREADOR", VAGAS_VER))]
        return out + [[ano, "ELEIÇÃO SUPLEMENTAR", "MG", "41238", "BELO HORIZONTE", "PREFEITO", 1]]

    @staticmethod
    def _pacote(a: str) -> dict:
        res = [{"url": f"{CDN}/{p}/{p}_{a}.zip", "format": "ZIP"} for p in ("consulta_cand", "bem_candidato", "consulta_vagas")]
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
            m = re.fullmatch(r"/estatistica/sead/odsele/(consulta_cand|bem_candidato|consulta_vagas)/\1_(\d{4})\.zip", path)
            if not m:
                return 404, b"", "text/html"
            self.pedidos_cdn += 1
            tipo, ano = m.group(1), int(m.group(2))
            if tipo == "consulta_vagas":
                return 200, _zip(f"consulta_vagas_{ano}", COL_VAGAS, self._vagas(ano)), "application/zip"
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
