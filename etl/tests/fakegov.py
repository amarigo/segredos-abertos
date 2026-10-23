"""Sites do governo simulados, para testar a coleta inteira sem internet.

Os dados são fictícios e gerados com semente fixa (sempre os mesmos). Servem só para os testes.

`FakeGov` responde no lugar de `requests.Session.request` e imita:
- Câmara: lista de deputados (paginada), arquivo da cota (.zip) e os quatro arquivos de votações (.csv);
- Senado: lista de senadores, cota (CEAPS) por ano e votações mês a mês;
- Receita (Minha Receita): dados e sócios das empresas, com holdings em cadeia e um ciclo de holdings;
- Câmara: PDFs das notas (HEAD), alguns dando 404;
- Portal da Transparência: arquivo de emendas (.zip).

Engenharia de caos: `gov.falhar(padrao, modo, prob)` faz as URLs que contêm `padrao` falharem com a
probabilidade `prob`. Modos: 500, 429, 404, timeout, parado (não aceita conexão), conexao, html (página de erro no lugar do dado),
vazio (resposta 200 sem corpo), truncado (JSON ou arquivo cortado no meio) e lixo (bytes aleatórios).
"""
from __future__ import annotations

import io
import json
import random
import re
import zipfile
from urllib.parse import parse_qs, urlparse

import requests

from sa_etl.cnpj import cnpj_matriz

PARTIDOS_DEP = ["PL", "PL", "NOVO", "PT", "PT", "PSOL", "MDB", "PSD"]
PARTIDOS_SEN = ["PL", "PT", "MDB", "PSD", "NOVO"]
DIREITA = {"PL", "NOVO"}
MODOS = {"500", "429", "404", "timeout", "parado", "conexao", "html", "vazio", "truncado", "lixo"}


def _csv(cab: list[str], linhas: list[list]) -> str:
    q = lambda x: '"' + str(x).replace('"', '""') + '"'  # noqa: E731
    return "\n".join([";".join(q(c) for c in cab)] + [";".join(q(c) for c in l) for l in linhas]) + "\n"


def _cnpj(rng: random.Random) -> str:
    return cnpj_matriz(str(rng.randint(10_000_000, 99_999_999)))


class FakeGov:
    def __init__(self, anos=(2025,), n_dep=30, n_sen=10, seed=7):
        self.rng = random.Random(seed)
        self.caos = random.Random(seed + 1)
        self.anos = list(anos)
        self.falhas: list[list] = []  # [padrao, modo, prob, vezes restantes ou None]
        self.chamadas: list[str] = []
        self.repetir_linhas = False  # caos de dados: arquivos com linhas repetidas
        rng = self.rng

        # ---------- parlamentares
        self.deputados = [{"id": 1000 + i, "nome": f"Deputado Ficticio {i:02d}", "siglaPartido": PARTIDOS_DEP[i % len(PARTIDOS_DEP)],
                           "siglaUf": ["SP", "MG", "RJ", "BA"][i % 4], "urlFoto": f"https://www.camara.leg.br/fotos/{1000 + i}.jpg"}
                          for i in range(n_dep)]
        self.senadores = [{"cod": 5000 + i, "nome": f"Senador Ficticio {i:02d}", "partido": PARTIDOS_SEN[i % len(PARTIDOS_SEN)],
                           "uf": ["SP", "MG", "RJ"][i % 3]} for i in range(n_sen)]
        self.lider = "Senador Ficticio 01"  # do PT: faz o papel do líder do governo

        # ---------- empresas: fornecedoras, holdings (com cadeia e ciclo) e mesmo endereço
        self.fornecedoras = [_cnpj(rng) for _ in range(12)]
        h1, h2, h3, h4 = (_cnpj(rng) for _ in range(4))
        self.holdings = [h1, h2, h3, h4]
        pessoa = lambda n, d: {"nome_socio": n, "cnpj_cpf_do_socio": d, "identificador_de_socio": 2,  # noqa: E731
                               "qualificacao_socio": "Sócio-Administrador"}
        empresa = lambda c, n: {"nome_socio": n, "cnpj_cpf_do_socio": c, "identificador_de_socio": 1,  # noqa: E731
                                "qualificacao_socio": "Sócio"}
        self.receita: dict[str, dict] = {}
        for i, c in enumerate(self.fornecedoras):
            qsa = [pessoa(f"DONO FICTICIO {i % 5}", f"***{100000 + i % 5}**")]
            if i == 0:
                qsa = [empresa(h1, "HOLDING UM")]  # fornecedora -> h1 -> h2 -> pessoa
            if i == 1:
                qsa = [empresa(h3, "HOLDING TRES")]  # fornecedora -> h3 <-> h4 (ciclo)
            if i == 2:
                qsa = [empresa(h1[:8], "HOLDING UM")]  # a Receita às vezes traz só a raiz do CNPJ
            end = {"cep": "01001000", "numero": "100" if i in (3, 4) else str(200 + i), "complemento": ""}
            self.receita[c] = self._empresa(c, f"FORNECEDORA FICTICIA {i:02d} LTDA", qsa, end)
        # empresas pagas com emendas: a primeira tem o mesmo dono de duas fornecedoras da cota
        r2 = random.Random(seed + 2)  # separado, para não mudar os outros dados fictícios
        self.emenda_empresas = [_cnpj(r2), _cnpj(r2)]
        self.receita[self.emenda_empresas[0]] = self._empresa(self.emenda_empresas[0], "CONSTRUTORA DA EMENDA LTDA",
                                                              [pessoa("DONO FICTICIO 3", "***100003**")], {"cep": "02002000"})
        self.receita[self.emenda_empresas[1]] = self._empresa(self.emenda_empresas[1], "SERVICOS DA EMENDA LTDA",
                                                              [pessoa("OUTRA DONA", "***200000**")], {"cep": "03003000"})
        self.receita["46395000000139"] = {**self._empresa("46395000000139", "MUNICIPIO DE SAO PAULO", [], {}),
                                          "natureza_juridica": "Município"}
        self.receita[h1] = self._empresa(h1, "HOLDING UM SA", [empresa(h2, "HOLDING DOIS")], {})
        self.receita[h2] = self._empresa(h2, "HOLDING DOIS SA", [pessoa("DONA FINAL", "***777777**")], {})
        self.receita[h3] = self._empresa(h3, "HOLDING TRES SA", [empresa(h4, "HOLDING QUATRO")], {})
        self.receita[h4] = self._empresa(h4, "HOLDING QUATRO SA", [empresa(h3, "HOLDING TRES")], {})

        # ---------- despesas
        self.cota: dict[int, list[list]] = {}
        self.ceaps: dict[int, list[dict]] = {}
        self.pdf_faltando: set[str] = set()
        for ano in self.anos:
            linhas = []
            for d in self.deputados:
                for mes in range(1, 13):
                    for _ in range(rng.randint(0, 3)):
                        c = rng.choice(self.fornecedoras)
                        cat = rng.choice(["PASSAGEM AÉREA - RPA", "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.",
                                          "COMBUSTÍVEIS E LUBRIFICANTES.", "TELEFONIA"])
                        ide = str(rng.randint(7_000_000, 7_999_999))
                        url = "" if cat == "TELEFONIA" else f"https://www.camara.leg.br/cota-parlamentar/documentos/publ/{d['id']}/{ano}/{ide}.pdf"
                        if url and rng.random() < 0.05:
                            self.pdf_faltando.add(f"{d['id']}/{ano}/{ide}")
                        valor = f"{rng.randint(50, 20000)}.{rng.randint(0, 99):02d}"
                        linhas.append([d["nome"], d["id"], d["id"] + 50000, d["siglaUf"], d["siglaPartido"], cat,
                                       f"Fornecedora {c[:4]}", c, f"{ano}-{mes:02d}-{rng.randint(1, 28):02d}T00:00:00",
                                       valor, mes, ano, url, ide, rng.randint(1, 999), 3])
                # pessoa física como fornecedora (aluguel de escritório): o CPF não pode aparecer no site
                linhas.append([d["nome"], d["id"], d["id"] + 50000, d["siglaUf"], d["siglaPartido"],
                               "LOCAÇÃO DE IMÓVEL", "Proprietario Pessoa Fisica", "123.456.789-09", f"{ano}-05-10T00:00:00",
                               "1500.00", 5, ano, "", "1", "1", 1])
                # devolução (valor negativo), comum nas passagens
                linhas.append([d["nome"], d["id"], d["id"] + 50000, d["siglaUf"], d["siglaPartido"], "PASSAGEM AÉREA - RPA",
                               "Cia Aerea", self.fornecedoras[5], f"{ano}-06-10T00:00:00", "-120.30", 6, ano, "", "2", "2", 3])
            self.cota[ano] = linhas
            self.ceaps[ano] = [{"codSenador": s["cod"], "ano": ano, "mes": mes, "tipoDespesa": rng.choice(
                ["Locomoção, hospedagem, alimentação, combustíveis e lubrificantes", "Divulgação da atividade parlamentar"]),
                "cpfCnpj": rng.choice(self.fornecedoras), "fornecedor": "Fornecedora", "data": f"{ano}-{mes:02d}-05",
                "valorReembolsado": round(rng.uniform(100, 9000), 2), "documento": str(rng.randint(1, 9999)), "tipoDocumento": "Nota Fiscal"}
                for s in self.senadores for mes in range(1, 13) for _ in range(rng.randint(0, 2))]

        # ---------- votações (votos seguem o partido, com algum ruído)
        self.vot_camara: dict[int, dict] = {}
        self.vot_senado: dict[tuple[int, int], list[dict]] = {}
        for ano in self.anos:
            vs, votos, orient, props = [], [], [], []
            for j in range(30):
                vid = f"{2400000 + ano * 100 + j}-{j + 10}"
                gov = "Sim" if j % 2 else "Não"
                vs.append([vid, f"{ano}-{(j % 12) + 1:02d}-{(j % 27) + 1:02d}", "PLEN",
                           f"Aprovado o Projeto de Lei {j} sobre saúde e educação. Sim: 300; Não: 100", "1" if j % 3 else "0"])
                orient.append([vid, "Governo", gov])
                orient.append([vid, "PL", "Não" if gov == "Sim" else "Sim"])
                props.append([vid, 9000 + j, "PL", str(100 + j), str(ano), f"Dispõe sobre a saúde pública {j}.", f"PL {100 + j}/{ano}"])
                for d in self.deputados:
                    lado = gov if d["siglaPartido"] not in DIREITA else ("Não" if gov == "Sim" else "Sim")
                    if rng.random() < 0.1:
                        lado = "Não" if lado == "Sim" else "Sim"
                    if rng.random() < 0.05:
                        lado = "Abstenção"
                    votos.append([vid, lado, d["id"], d["siglaPartido"]])
            vs.append([f"{2400000 + ano * 100 + 99}-1", f"{ano}-03-03", "CCJC", "Votação em comissão (não entra)", "1"])
            self.vot_camara[ano] = {"votacoes": vs, "votos": votos, "orientacoes": orient, "proposicoes": props}
            for mes in range(1, 13):
                itens = []
                for k in range(3):
                    cod = ano * 1000 + mes * 10 + k
                    gov = "Sim" if (mes + k) % 2 else "Não"
                    vv = []
                    for s in self.senadores:
                        lado = gov if s["partido"] not in DIREITA else ("Não" if gov == "Sim" else "Sim")
                        if rng.random() < 0.1:
                            lado = "Não" if lado == "Sim" else "Sim"
                        vv.append({"codigoParlamentar": s["cod"], "nomeParlamentar": s["nome"],
                                   "siglaVotoParlamentar": lado if rng.random() > 0.05 else "MIS",
                                   "siglaPartidoParlamentar": s["partido"]})
                    itens.append({"codigoSessaoVotacao": cod, "votacaoSecreta": "S" if k == 2 and mes == 6 else "N",
                                  "dataSessao": f"{ano}-{mes:02d}-{10 + k}T14:00:00", "descricaoVotacao": f"Votação {k} sobre armas e segurança",
                                  "resultadoVotacao": "A", "sigla": "PL", "numero": str(mes * 10 + k), "ano": ano,
                                  "ementa": "Altera o Estatuto do Desarmamento.", "identificacao": f"PL {mes * 10 + k}/{ano}",
                                  "codigoMateria": 160000 + cod, "votos": vv})
                self.vot_senado[(ano, mes)] = itens

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _empresa(c, nome, qsa, end):
        return {"cnpj": c, "razao_social": nome, "nome_fantasia": "", "descricao_situacao_cadastral": "ATIVA",
                "data_inicio_atividade": "2010-01-01", "cnae_fiscal_descricao": "Atividade fictícia", "municipio": "SAO PAULO",
                "uf": "SP", "capital_social": 100000, "porte": "DEMAIS", "natureza_juridica": "Sociedade Empresária Limitada",
                "descricao_tipo_de_logradouro": "RUA", "logradouro": "FICTICIA", "numero": end.get("numero", ""),
                "complemento": end.get("complemento", ""), "bairro": "CENTRO", "cep": end.get("cep", ""), "qsa": qsa}

    def falhar(self, padrao: str, modo: str, prob: float = 1.0, vezes: int | None = None) -> "FakeGov":
        """`vezes`: falha só nas primeiras N chamadas (para testar novas tentativas)."""
        assert modo in MODOS, modo
        self.falhas.append([padrao, modo, prob, vezes])
        return self

    def consertar(self) -> None:
        self.falhas.clear()

    # ------------------------------------------------------------------ respostas
    def responder(self, method: str, url: str, params=None, **kw) -> requests.Response:
        full = url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")
        self.chamadas.append(f"{method} {full}")
        for f in self.falhas:
            padrao, modo, prob, vezes = f
            if padrao in full and vezes != 0 and self.caos.random() < prob:
                if vezes is not None:
                    f[3] -= 1
                return self._falha(modo, full)
        status, corpo, tipo = self._rota(method, url, params or {})
        return self._resp(status, corpo, full, tipo)

    def _falha(self, modo: str, url: str) -> requests.Response:
        if modo == "timeout":
            raise requests.Timeout(f"caos: tempo esgotado em {url}")
        if modo == "parado":  # o site nem aceita a conexão (servidor fora do ar)
            raise requests.ConnectTimeout(f"caos: {url} não aceitou a conexão")
        if modo == "conexao":
            raise requests.ConnectionError(f"caos: conexão recusada em {url}")
        if modo in ("500", "429", "404"):
            return self._resp(int(modo), b"erro", url)
        if modo == "html":
            return self._resp(200, b"<!DOCTYPE html><html><body>Servico indisponivel</body></html>", url, "text/html")
        if modo == "vazio":
            return self._resp(200, b"", url)
        if modo == "lixo":
            return self._resp(200, bytes(self.caos.getrandbits(8) for _ in range(300)), url)
        # truncado: a resposta certa cortada no meio
        status, corpo, tipo = self._rota("GET", url.split("?")[0], {k: v[0] for k, v in parse_qs(urlparse(url).query).items()})
        return self._resp(status, corpo[: max(1, len(corpo) // 2)], url, tipo)

    @staticmethod
    def _resp(status: int, corpo: bytes, url: str, tipo: str = "application/json") -> requests.Response:
        r = requests.Response()
        r.status_code = status
        r._content = corpo
        r._content_consumed = True
        r.url = url
        r.headers["content-type"] = tipo
        r.encoding = "utf-8"
        return r

    def _json(self, x) -> tuple[int, bytes, str]:
        return 200, json.dumps(x, ensure_ascii=False).encode(), "application/json"

    def _rep(self, linhas: list) -> list:
        return linhas + linhas[: len(linhas) // 3] if self.repetir_linhas else linhas

    def _rota(self, method: str, url: str, params: dict) -> tuple[int, bytes, str]:
        u = urlparse(url)
        path = u.path
        q = {**{k: v[0] for k, v in parse_qs(u.query).items()}, **{k: str(v) for k, v in params.items()}}

        if u.netloc == "dadosabertos.camara.leg.br" and path == "/api/v2/deputados":
            if "idLegislatura" in q:  # emendas: deputados da legislatura
                return self._json({"dados": [{"nome": "Ex Deputado Ficticio", "siglaPartido": "PP", "siglaUf": "PE"}], "links": []})
            pagina = int(q.get("pagina", 1))
            ds = self.deputados
            meio = len(ds) // 2
            fatia = ds[:meio + 1] if pagina == 1 else ds[meio:]  # o último da página 1 se repete na 2 (acontece ao paginar)
            links = [{"rel": "next", "href": "https://dadosabertos.camara.leg.br/api/v2/deputados?pagina=2"}] if pagina == 1 else []
            return self._json({"dados": [{"id": d["id"], "nome": d["nome"], "siglaPartido": d["siglaPartido"],
                                          "siglaUf": d["siglaUf"], "urlFoto": d["urlFoto"]} for d in fatia], "links": links})

        m = re.match(r"^/cotas/Ano-(\d{4})\.csv\.zip$", path)
        if u.netloc == "www.camara.leg.br" and m:
            ano = int(m.group(1))
            if ano not in self.cota:
                return 404, b"", "text/html"
            cab = ["txNomeParlamentar", "ideCadastro", "nuDeputadoId", "sgUF", "sgPartido", "txtDescricao", "txtFornecedor",
                   "txtCNPJCPF", "datEmissao", "vlrLiquido", "numMes", "numAno", "urlDocumento", "ideDocumento", "txtNumero", "numSubCota"]
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr(f"Ano-{ano}.csv", ("﻿" + _csv(cab, self.cota[ano])).encode("utf-8"))
            return 200, buf.getvalue(), "application/zip"

        m = re.match(r"^/arquivos/(\w+)/csv/\w+-(\d{4})\.csv$", path)
        if u.netloc == "dadosabertos.camara.leg.br" and m:
            tipo, ano = m.group(1), int(m.group(2))
            if ano not in self.vot_camara:
                return 404, b"", "text/html"
            d = self.vot_camara[ano]
            if tipo == "votacoes":
                return 200, _csv(["id", "data", "siglaOrgao", "descricao", "aprovacao"], self._rep(d["votacoes"])).encode(), "text/csv"
            if tipo == "votacoesVotos":
                return 200, _csv(["idVotacao", "voto", "deputado_id", "deputado_siglaPartido"], self._rep(d["votos"])).encode(), "text/csv"
            if tipo == "votacoesOrientacoes":
                return 200, _csv(["idVotacao", "siglaBancada", "orientacao"], d["orientacoes"]).encode(), "text/csv"
            if tipo == "votacoesProposicoes":
                return 200, _csv(["idVotacao", "proposicao_id", "proposicao_siglaTipo", "proposicao_numero", "proposicao_ano",
                                  "proposicao_ementa", "proposicao_titulo"], d["proposicoes"]).encode(), "text/csv"

        if u.netloc == "www.camara.leg.br" and path.startswith("/cota-parlamentar/documentos/publ/"):
            chave = path.rsplit("/publ/", 1)[1].removesuffix(".pdf")
            return (404 if chave in self.pdf_faltando else 200), b"", "application/pdf"

        if u.netloc == "legis.senado.leg.br" and path == "/dadosabertos/senador/lista/atual.json":
            return self._json({"ListaParlamentarEmExercicio": {"Parlamentares": {"Parlamentar": [
                {"IdentificacaoParlamentar": {"CodigoParlamentar": str(s["cod"]), "NomeParlamentar": s["nome"],
                                              "SiglaPartidoParlamentar": s["partido"], "UfParlamentar": s["uf"],
                                              "UrlFotoParlamentar": f"https://www.senado.leg.br/senadores/img/fotos/{s['cod']}.jpg",
                                              "UrlPaginaParlamentar": f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{s['cod']}"}}
                for s in self.senadores]}}})

        if u.netloc == "legis.senado.leg.br" and path.startswith("/dadosabertos/senador/lista/legislatura/"):
            return self._json({"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
                {"IdentificacaoParlamentar": {"NomeParlamentar": "Ex Senador Ficticio", "SiglaPartidoParlamentar": "PP", "UfParlamentar": "AL"}}]}}})

        m = re.match(r"^/adm-dadosabertos/api/v1/senadores/despesas_ceaps/(\d{4})$", path)
        if u.netloc == "adm.senado.gov.br" and m:
            return self._json(self.ceaps.get(int(m.group(1)), []))

        if u.netloc == "legis.senado.leg.br" and path == "/dadosabertos/votacao":
            ano, mes = int(q["dataInicio"][:4]), int(q["dataInicio"][5:7])
            itens = self.vot_senado.get((ano, mes), [])
            return self._json(self._rep(itens))

        if u.netloc == "minhareceita.org":
            c = path.strip("/")
            return self._json(self.receita[c]) if c in self.receita else (404, b'{"message":"not found"}', "application/json")

        if "emendas-parlamentares" in url or "EmendasParlamentares.zip" in url:
            return 200, self._emendas_zip(), "application/zip"

        if "/download-de-dados/despesas/" in url:  # arquivos diários de despesas (pagamentos das emendas)
            dia = path.rstrip("/").rsplit("/", 1)[-1]
            z = self._despesas_dia(dia)
            return (200, z, "application/zip") if z else (404, b"", "text/html")

        return 404, b"", "text/html"

    def _emendas_zip(self) -> bytes:
        cab = ["Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Nome do Autor da Emenda", "Localidade de aplicação do recurso",
               "Município", "UF", "Nome Função", "Nome Subfunção", "Valor Empenhado", "Valor Liquidado", "Valor Pago",
               "Valor Restos A Pagar Pagos"]
        linhas, fav = [], []
        for ano in self.anos:
            for i, d in enumerate(self.deputados[:10]):
                tipo = "Emenda Individual - Transferências Especiais" if i % 3 == 0 else "Emenda Individual - Transferências com Finalidade Definida"
                linhas.append([str(ano * 100 + i), str(ano), tipo, d["nome"].upper(), "SAO PAULO - SP", "SAO PAULO", "SÃO PAULO",
                               "Saúde", "Atenção básica", "1.000,00", "0,00", "600,00", "100,00"])
                fav.append([str(ano * 100 + i), d["nome"].upper(), "Individual", f"{ano}05", "46.395.000/0001-39",
                            "MUNICIPIO DE SAO PAULO", "Município", "Pessoa Jurídica", "SP", "SAO PAULO", "700,00"])
            linhas.append([str(ano * 100 + 99), str(ano), "Emenda de Bancada", "BANCADA DE SAO PAULO", "Nacional", "", "",
                           "Educação", "Ensino", "5.000,00", "0,00", "2.000,00", "0,00"])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("EmendasParlamentares.csv", _csv(cab, linhas).encode("latin-1"))
            z.writestr("EmendasParlamentares_PorFavorecido.csv", _csv(
                ["Código da Emenda", "Nome do Autor da Emenda", "Tipo de Emenda", "Ano/Mês", "Código do Favorecido", "Favorecido",
                 "Natureza Jurídica", "Tipo Favorecido", "UF Favorecido", "Município Favorecido", "Valor Recebido"], fav).encode("latin-1"))
        return buf.getvalue()


    def _despesas_dia(self, dia: str) -> bytes | None:
        """Empenhos de emenda em 10/03 e pagamentos em 20/04 de cada ano. Nos outros dias, não há arquivo."""
        ano = dia[:4]
        if not ano.isdigit() or int(ano) not in self.anos or dia[4:] not in ("0310", "0420"):
            return None
        ug = "UNIDADE FICTICIA DE OBRAS"
        favs = [(self.emenda_empresas[0], "CONSTRUTORA DA EMENDA LTDA"), (self.emenda_empresas[1], "SERVICOS DA EMENDA LTDA"),
                ("46395000000139", "MUNICIPIO DE SAO PAULO")]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            if dia.endswith("0310"):
                cab = ["Id Empenho", "Código Empenho", "Data Emissão", "Órgão Superior", "Órgão", "Unidade Gestora",
                       "Código Favorecido", "Favorecido", "Observação", "Função", "Modalidade de Aplicação", "Autor Emenda",
                       "Valor do Empenho Convertido pra R$"]
                linhas = []
                for i, d in enumerate(self.deputados[:5]):
                    c, nome = favs[i % 3]
                    linhas.append([str(i), f"11111111111{ano}NE00000{i}", f"10/03/{ano}", "Ministério da Saúde", "Fundo Nacional de Saúde",
                                   ug, c, nome, f"OBRA FICTICIA {i} - EMENDA", "Saúde", "Aplicações Diretas",
                                   f"{d['nome'].upper()} / EMENDA {i + 1}", "50000,00"])
                linhas.append(["9", f"11111111111{ano}NE000099", f"10/03/{ano}", "Ministério da Saúde", "Fundo Nacional de Saúde",
                               ug, favs[0][0], favs[0][1], "SEM RELACAO COM EMENDA", "Saúde", "Aplicações Diretas", "Sem emenda", "999,00"])
                z.writestr(f"{dia}_Despesas_Empenho.csv", _csv(cab, linhas).encode("latin-1"))
            else:
                imp, pag = [], []
                for i in range(5):
                    c, nome = favs[i % 3]
                    cod = f"11111111111{ano}OB00000{i}"
                    imp.append([cod, f"11111111111{ano}NE00000{i}", "33903900", "39", "30000,00", "0,00"])
                    pag.append([cod, f"20/04/{ano}", "Ordem Bancária", "Ministério da Saúde", "Fundo Nacional de Saúde", ug,
                                c, nome, "PAGAMENTO DA OBRA", "30000,00"])
                imp.append([f"11111111111{ano}OB000099", f"11111111111{ano}NE000099", "33903900", "39", "999,00", "0,00"])
                pag.append([f"11111111111{ano}OB000099", f"20/04/{ano}", "Ordem Bancária", "Ministério da Saúde", "Fundo Nacional de Saúde",
                            ug, favs[0][0], favs[0][1], "OUTRA COISA", "999,00"])
                z.writestr(f"{dia}_Despesas_Pagamento_EmpenhosImpactados.csv", _csv(
                    ["Código Pagamento", "Código Empenho", "Código Natureza Despesa Completa", "Subitem", "Valor Pago (R$)",
                     "Valor Restos a Pagar Pagos (R$)"], imp).encode("latin-1"))
                z.writestr(f"{dia}_Despesas_Pagamento.csv", _csv(
                    ["Código Pagamento", "Data Emissão", "Tipo Documento", "Órgão Superior", "Órgão", "Unidade Gestora",
                     "Código Favorecido", "Favorecido", "Observação", "Valor do Pagamento Convertido pra R$"], pag).encode("latin-1"))
        return buf.getvalue()


def instalar(monkeypatch, gov: FakeGov) -> FakeGov:
    """Troca a internet pelo FakeGov e tira as esperas entre tentativas (os testes não precisam esperar)."""
    def request(self, method, url, params=None, **kw):
        return gov.responder(method.upper(), url, params)
    monkeypatch.setattr(requests.Session, "request", request)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return gov
