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

import csv
import io
import json
import random
import re
import zipfile
from urllib.parse import parse_qs, urlparse

import requests

from sa_etl.cnpj import cnpj_matriz

import fakegov_financas  # noqa: E402  (mesma pasta dos testes)
import fakegov_gabinetes  # noqa: E402
import fakegov_noticias  # noqa: E402
import fakegov_representantes  # noqa: E402
import fakegov_tramitacao  # noqa: E402
import fakegov_transferegov  # noqa: E402
import fakegov_candidatos  # noqa: E402
import fakegov_sancoes  # noqa: E402
import fakegov_tribunais  # noqa: E402
import fakegov_tse  # noqa: E402

PARTIDOS_DEP = ["PL", "PL", "NOVO", "PT", "PT", "PSOL", "MDB", "PSD"]
PARTIDOS_SEN = ["PL", "PT", "MDB", "PSD", "NOVO"]
DIREITA = {"PL", "NOVO"}
MODOS = {"500", "429", "404", "405", "timeout", "parado", "conexao", "html", "vazio", "truncado", "lixo"}


def _csv(cab: list[str], linhas: list[list]) -> str:
    q = lambda x: '"' + str(x).replace('"', '""') + '"'  # noqa: E731
    return "\n".join([";".join(q(c) for c in cab)] + [";".join(q(c) for c in l) for l in linhas]) + "\n"


def _cnpj(rng: random.Random) -> str:
    return cnpj_matriz(str(rng.randint(10_000_000, 99_999_999)))



def _linhas_zip(corpo: bytes) -> tuple[str, list[str], list[dict]] | None:
    """Prefixo, colunas e linhas do CSV _BRASIL de um ZIP do TSE simulado."""
    with zipfile.ZipFile(io.BytesIO(corpo)) as z:
        for n in z.namelist():
            if n.endswith("_BRASIL.csv"):
                leitor = csv.DictReader(io.StringIO(z.read(n).decode("latin-1")), delimiter=";")
                return n[: -len("_BRASIL.csv")], list(leitor.fieldnames or []), list(leitor)
    return None


def _juntar_tse(a: tuple | None, b: tuple | None) -> tuple | None:
    """Junta as respostas das duas simulações do TSE para o mesmo endereço. Falha simulada (status diferente de 200 e
    de 404) vale para as duas; 404 de um lado fica com a resposta do outro. Na API (JSON), os recursos se somam; nos
    ZIPs, as colunas e as linhas se somam (coluna que um lado não tem fica vazia)."""
    if a is None or b is None:
        return a if b is None else b
    for r in (a, b):
        if r[0] not in (200, 404):
            return r
    if a[0] != 200 or b[0] != 200:
        return a if a[0] == 200 else b
    if a[2] == "application/json":
        ja, jb = json.loads(a[1]), json.loads(b[1])
        ra = (ja.get("result") or {}).get("resources")
        rb = (jb.get("result") or {}).get("resources")
        if isinstance(ra, list) and isinstance(rb, list):
            urls = {x.get("url") for x in ra}
            ja["result"]["resources"] = ra + [x for x in rb if x.get("url") not in urls]
            return 200, json.dumps(ja).encode(), a[2]
        return a
    la, lb = _linhas_zip(a[1]), _linhas_zip(b[1])
    if not la or not lb:
        return a if la else b
    cols = la[1] + [c for c in lb[1] if c not in la[1]]
    out = io.StringIO()
    w = csv.DictWriter(out, cols, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n", restval="")
    w.writeheader()
    w.writerows(la[2] + lb[2])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{la[0]}_BRASIL.csv", out.getvalue().encode("latin-1"))
        z.writestr("leiame.pdf", b"%PDF")
    return 200, buf.getvalue(), a[2]


class FakeGov:
    def __init__(self, anos=(2025,), n_dep=30, n_sen=10, seed=7):
        self.rng = random.Random(seed)
        self.caos = random.Random(seed + 1)
        self.anos = list(anos)
        self.falhas: list[list] = []  # [padrao, modo, prob, vezes restantes ou None]
        self.chamadas: list[str] = []
        self.renuncia_so_navegador = False  # o servidor de arquivos da CGU recusa quem não parece navegador
        self.api_chave = "chave-de-teste"  # a API de dados do Portal pede a chave no cabeçalho chave-api-dados
        self.api_exige_uf = False  # a consulta sem filtro pode não ser aceita
        self.recursos_max_pagina = None  # a consulta de recursos recebidos sem filtro falha depois desta página
        self.api_paginas_sem_filtro = None  # a consulta sem filtro falha depois desta página (a API não pula tantas linhas)
        self.repetir_linhas = False  # caos de dados: arquivos com linhas repetidas
        self.legislatura_so_atuais = False  # a lista da legislatura sem quem saiu (o defeito que escondia gente)
        self.tse_baixados: list[int] = []  # anos cujo ZIP de contas de campanha foi baixado (não só conferido)
        self.tse_etag: dict[int, str] = {}  # troca a versão de um ano (o TSE publicou um arquivo novo)
        rng = self.rng

        # ---------- parlamentares
        self.deputados = [{"id": 1000 + i, "nome": f"Deputado Ficticio {i:02d}", "siglaPartido": PARTIDOS_DEP[i % len(PARTIDOS_DEP)],
                           "siglaUf": ["SP", "MG", "RJ", "BA"][i % 4], "urlFoto": f"https://www.camara.leg.br/fotos/{1000 + i}.jpg"}
                          for i in range(n_dep)]
        self.transferegov = fakegov_transferegov.Transferegov(self.anos, self.deputados)  # emendas Pix
        self.senadores = [{"cod": 5000 + i, "nome": f"Senador Ficticio {i:02d}", "partido": PARTIDOS_SEN[i % len(PARTIDOS_SEN)],
                           "uf": ["SP", "MG", "RJ"][i % 3]} for i in range(n_sen)]
        # Quem passou pela legislatura e não está no cargo hoje (suplente que devolveu a vaga): some da lista atual,
        # mas gastou e votou no ano. Como a deputada Dayany Bittencourt, que a lista atual da Câmara deixou de trazer.
        self.dep_fora = {self.deputados[-1]["id"]} if n_dep >= 3 else set()
        self.sen_fora = {self.senadores[-1]["cod"]} if n_sen >= 3 else set()
        self.tse = fakegov_candidatos.TSE(self.deputados, self.senadores)  # patrimônio declarado e eleitos
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
        self.sancoes = fakegov_sancoes.Sancoes(self.fornecedoras, self.deputados)  # listas oficiais de punidos
        # empresas pagas com emendas: a primeira tem o mesmo dono de duas fornecedoras da cota
        r2 = random.Random(seed + 2)  # separado, para não mudar os outros dados fictícios
        self.emenda_empresas = [_cnpj(r2), _cnpj(r2)]
        self.receita[self.emenda_empresas[0]] = self._empresa(self.emenda_empresas[0], "CONSTRUTORA DA EMENDA LTDA",
                                                              [pessoa("DONO FICTICIO 3", "***100003**")], {"cep": "02002000"})
        self.receita[self.emenda_empresas[1]] = self._empresa(self.emenda_empresas[1], "SERVICOS DA EMENDA LTDA",
                                                              [pessoa("OUTRA DONA", "***200000**")], {"cep": "03003000"})
        self.receita["46395000000139"] = {**self._empresa("46395000000139", "MUNICIPIO DE SAO PAULO", [], {}),
                                          "natureza_juridica": "Município"}
        # incentivos: empresa contratada pelo governo (mesmo dono de fornecedoras da cota), entidade sem fins lucrativos,
        # empresa pública (não entra) e empresa com renúncia fiscal que não está na Receita
        r3 = random.Random(seed + 3)
        self.incentivo_empresas = [_cnpj(r3) for _ in range(4)]
        ce, assoc, publica, _sem = self.incentivo_empresas
        self.receita[ce] = self._empresa(ce, "CONTRATADA FICTICIA LTDA", [pessoa("DONO FICTICIO 3", "***100003**")], {"cep": "04004000"})
        self.receita[assoc] = {**self._empresa(assoc, "ASSOCIACAO FICTICIA DE APOIO", [pessoa("PRESIDENTE FICTICIA", "***300000**")],
                                               {"cep": "05005000"}), "natureza_juridica": "Associação Privada", "uf": "BA"}
        self.receita[publica] = {**self._empresa(publica, "ESTATAL FICTICIA SA", [], {}), "natureza_juridica": "Empresa Pública"}
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

        # ---------- presença em eventos da Câmara (calendário dia a dia), com um gerador à parte para não mudar o resto
        r4 = random.Random(seed + 4)
        self.restaurante = _cnpj(r4)  # restaurante em Recife: refeição do deputado num dia de sessão em Brasília
        self.receita[self.restaurante] = {**self._empresa(self.restaurante, "RESTAURANTE FICTICIO DO RECIFE LTDA",
                                                          [pessoa("DONA DO RESTAURANTE", "***400000**")], {"cep": "50000000"}),
                                          "cnae_fiscal_descricao": "Restaurantes e similares", "municipio": "RECIFE", "uf": "PE"}
        self.eventos: dict[int, dict[str, list[list]]] = {}
        for ano in self.anos:
            evs, pres, orgs = [], [], []
            plen = [v for v in self.vot_camara[ano]["votacoes"] if v[2] == "PLEN"]
            for j, v in enumerate(plen):
                eid = ano * 1000 + j
                tipo = "Semipresencial" if j % 5 == 0 else "Presencial"
                evs.append([eid, f"{v[1]}T14:00:00", "Encerrada", f"Sessão Deliberativa Extraordinária {tipo} (AM nº 123/2020)",
                            "Sessão Deliberativa", "", "Plenário da Câmara dos Deputados"])
                orgs.append([eid, "PLEN"])
                pres += [[eid, f"{v[1]}T14:00:00", x[2]] for x in self.vot_camara[ano]["votos"] if x[0] == v[0]]
            for mes in range(1, 13):
                eid = ano * 1000 + 500 + mes
                evs.append([eid, f"{ano}-{mes:02d}-15T10:00:00", "Encerrada (Final)", "Reunião sobre saúde\nConvidados: fulano",
                            "Reunião Deliberativa", "", "Anexo II, Plenário 01"])
                orgs.append([eid, "CSAUDE"])
                pres += [[eid, f"{ano}-{mes:02d}-15T10:00:00", d["id"]] for d in self.deputados[::2]]
            evs.append([ano * 1000 + 900, f"{ano}-04-08T09:00:00", "Encerrada", "Visita ao aterro sanitário", "Visita Técnica",
                        "Aterro sanitário em Manaus-AM", ""])
            pres += [[ano * 1000 + 900, f"{ano}-04-08T09:00:00", d["id"]] for d in self.deputados[1:2]]
            evs.append([ano * 1000 + 901, f"{ano}-04-09T09:00:00", "Cancelada", "Reunião cancelada", "Audiência Pública", "",
                        "Anexo II, Plenário 02"])
            pres += [[ano * 1000 + 901, f"{ano}-04-09T09:00:00", d["id"]] for d in self.deputados[:1]]
            self.eventos[ano] = {"eventos": evs, "eventosPresencaDeputados": pres, "eventosOrgaos": orgs}
            for d0, (k, v) in ((d0, kv) for d0 in self.deputados[:1] for kv in ((1, "86.50"), (0, "40.00"))):  # dia de sessão presencial (para conferir) e semipresencial (não)
                dia = plen[k][1]
                self.cota[ano].append([d0["nome"], d0["id"], d0["id"] + 50000, d0["siglaUf"], d0["siglaPartido"],
                                       "FORNECIMENTO DE ALIMENTAÇÃO DO PARLAMENTAR", "Restaurante Ficticio", self.restaurante,
                                       f"{dia}T00:00:00", v, int(dia[5:7]), ano, "", f"9{k}", f"9{k}", 13])

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
        h = kw.get("headers") or {}
        if "api.portaldatransparencia.gov.br" in url and h.get("chave-api-dados") != self.api_chave:
            return self._resp(401, b'{"Erro":"chave"}', full)
        if "/renuncias/" in url and (self.renuncia_so_navegador and "Mozilla" not in h.get("User-Agent", "")
                                     or "json" in h.get("Accept", "")):
            return self._resp(403, b"<Error>AccessDenied</Error>", full, "application/xml")
        if fakegov_tse.CDN in url and method == "HEAD":  # o CDN do TSE diz a versão do arquivo sem mandar o arquivo
            ano = next((a for a in fakegov_tse.ANOS if f"_{a}.zip" in url), None)
            r = self._resp(200 if ano else 404, b"", full, "application/zip")
            if ano:
                r.headers["ETag"] = self.tse_etag.get(ano, fakegov_tse.ETAG[ano])
            return r
        status, corpo, tipo = self._rota(method, url, params or {})
        r = self._resp(status, corpo, full, tipo)
        if status == 200 and url.endswith("_RenunciasFiscais.zip"):  # o S3 da CGU diz quando o arquivo foi publicado
            r.headers["last-modified"] = "Thu, 05 Dec 2024 23:26:16 GMT"
        return r

    def _falha(self, modo: str, url: str) -> requests.Response:
        if modo == "timeout":
            raise requests.Timeout(f"caos: tempo esgotado em {url}")
        if modo == "parado":  # o site nem aceita a conexão (servidor fora do ar)
            raise requests.ConnectTimeout(f"caos: {url} não aceitou a conexão")
        if modo == "conexao":
            raise requests.ConnectionError(f"caos: conexão recusada em {url}")
        if modo in ("500", "429", "404"):
            return self._resp(int(modo), b"erro", url)
        if modo == "405":  # desde 29/10/2026 o CloudFront do Portal recusa os arquivos a quem não é navegador
            r = self._resp(405, b"<html>405 Not Allowed</html>", url, "text/html")
            r.headers["server"] = "CloudFront"
            return r
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
        gab = fakegov_gabinetes.rota(u.netloc, path, q, self.deputados)  # verba de gabinete, IBGE e equipe dos senadores
        if gab is not None:
            return gab
        fin = fakegov_financas.rota(u.netloc, path, q)  # aba de arrecadação e gastos
        if fin is not None:
            return fin
        tra = fakegov_tramitacao.rota(u.netloc, path, q)  # projetos em andamento
        if tra is not None:
            return tra
        noti = fakegov_noticias.rota(u.netloc, path, q)  # busca de notícias e páginas dos jornais
        if noti is not None:
            return noti
        tse = fakegov_tse.rota(u.netloc, path, q, self)  # contas de campanha (TSE)
        if tse is not None:
            return tse
        sanc = self.sancoes.rota(u.netloc, path, q)  # CEIS, CNEP, CEAF e listas do TCU
        if sanc is not None:
            return sanc
        trib = fakegov_tribunais.rota(u.netloc, path, q)  # votos dos ministros do STF
        if trib is not None:
            return trib
        # TSE: o patrimônio e os eleitos (fakegov_candidatos) e Quem me representa (fakegov_representantes) leem
        # os mesmos arquivos de verdade. Cada simulação tem as linhas dos seus testes; aqui elas viram um arquivo só.
        tse = _juntar_tse(self.tse.rota(u.netloc, path, q), fakegov_representantes.rota(u.netloc, path, q))
        if tse is not None:
            return tse
        tg = self.transferegov.rota(u.netloc, path, q)  # emendas Pix no Transferegov
        if tg is not None:
            return tg

        if u.netloc == "dadosabertos.camara.leg.br" and path == "/api/v2/deputados":
            if "idLegislatura" in q:  # todos que passaram pela legislatura; a pessoa se repete a cada nome que usou
                ds = [{"id": d["id"], "nome": d["nome"], "siglaPartido": d["siglaPartido"], "siglaUf": d["siglaUf"],
                       "urlFoto": d["urlFoto"]} for d in self.deputados
                      if not (self.legislatura_so_atuais and d["id"] in self.dep_fora)]
                ds += [{**x, "nome": x["nome"].replace("Deputado", "Deputada do Capitao")} for x in ds if x["id"] in self.dep_fora]
                return self._json({"dados": sorted(ds, key=lambda x: x["nome"])
                                   + [{"nome": "Ex Deputado Ficticio", "siglaPartido": "PP", "siglaUf": "PE"}], "links": []})
            pagina = int(q.get("pagina", 1))
            ds = [d for d in self.deputados if d["id"] not in self.dep_fora]
            meio = len(ds) // 2
            fatia = ds[:meio + 1] if pagina == 1 else ds[meio:]  # o último da página 1 se repete na 2 (acontece ao paginar)
            links = [{"rel": "next", "href": "https://dadosabertos.camara.leg.br/api/v2/deputados?pagina=2"}] if pagina == 1 else []
            return self._json({"dados": [{"id": d["id"], "nome": d["nome"], "siglaPartido": d["siglaPartido"],
                                          "siglaUf": d["siglaUf"], "urlFoto": d["urlFoto"]} for d in fatia], "links": links})

        m = re.match(r"^/api/v2/deputados/(\d+)$", path)
        if u.netloc == "dadosabertos.camara.leg.br" and m:
            d = next((d for d in self.deputados if str(d["id"]) == m.group(1)), None)
            if not d:
                return 404, b"", "application/json"
            fora = d["id"] in self.dep_fora
            # um CPF e um nome civil por deputado, os mesmos nas contas de campanha e nas listas de punidos
            return self._json({"dados": {"id": d["id"], "cpf": fakegov_sancoes.cpf_deputado(d["id"]),
                                         "nomeCivil": fakegov_sancoes.nome_civil(d["id"]), "ultimoStatus": {
                "id": d["id"], "nome": d["nome"], "nomeEleitoral": d["nome"], "siglaPartido": d["siglaPartido"],
                "siglaUf": d["siglaUf"], "urlFoto": d["urlFoto"], "data": "2025-07-09" if fora else "2023-02-01",
                "situacao": "Suplência" if fora else "Exercício", "condicaoEleitoral": "Suplente" if fora else "Titular"}}})

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
            if tipo in ("eventos", "eventosPresencaDeputados", "eventosOrgaos"):
                if ano not in self.eventos:
                    return 404, b"", "text/html"
                cab = {"eventos": ["id", "dataHoraInicio", "situacao", "descricao", "descricaoTipo", "localExterno", "localCamara.nome"],
                       "eventosPresencaDeputados": ["idEvento", "dataHoraInicio", "idDeputado"],
                       "eventosOrgaos": ["idEvento", "siglaOrgao"]}[tipo]
                return 200, _csv(cab, self.eventos[ano][tipo]).encode(), "text/csv"
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
                for s in self.senadores if s["cod"] not in self.sen_fora]}}})

        if u.netloc == "legis.senado.leg.br" and path.startswith("/dadosabertos/senador/lista/legislatura/"):
            leg = path.rsplit("/", 1)[1].removesuffix(".json")
            # como a API: a UF fica no mandato; quem saiu tem o fim do exercício e o motivo
            return self._json({"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
                {"IdentificacaoParlamentar": {"NomeParlamentar": "Ex Senador Ficticio", "SiglaPartidoParlamentar": "PP", "UfParlamentar": "AL"}}]
                + [{"IdentificacaoParlamentar": {"CodigoParlamentar": str(s["cod"]), "NomeParlamentar": s["nome"],
                                                 "SiglaPartidoParlamentar": s["partido"]},
                    "Mandatos": {"Mandato": [{"UfParlamentar": s["uf"], "PrimeiraLegislaturaDoMandato": {"NumeroLegislatura": leg},
                                              "Exercicios": {"Exercicio": [{"DataInicio": "2025-01-10", "DataFim": "2025-09-30",
                                                                            "DescricaoCausaAfastamento": "Retorno do titular"}]
                                                             if s["cod"] in self.sen_fora else []}}]}}
                   for s in self.senadores]}}})

        m = re.match(r"^/dadosabertos/senador/(\d+)\.json$", path)
        if u.netloc == "legis.senado.leg.br" and m:
            s = next((s for s in self.senadores if str(s["cod"]) == m.group(1)), None)
            if not s:
                return 404, b"", "application/json"
            return self._json({"DetalheParlamentar": {"Parlamentar": {"IdentificacaoParlamentar": {
                "CodigoParlamentar": str(s["cod"]), "NomeParlamentar": s["nome"],
                "NomeCompletoParlamentar": fakegov_tse.nome_civil_senador(self.senadores.index(s)), "UfParlamentar": s["uf"]},
                "DadosBasicosParlamentar": {"DataNascimento": fakegov_candidatos.nascimento(s["cod"])}}}})

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

        if u.netloc == "api.portaldatransparencia.gov.br" and path == "/api-de-dados/renuncias-valor":
            if self.api_exige_uf and "nomeSiglaUF" not in params:
                return 400, b'{"Erro":"Filtro obrigatorio"}', "application/json"
            todos = [x for ano in range(2015, 2031) for x in self._renuncias_api(ano)]
            if "nomeSiglaUF" in params:
                todos = [x for x in todos if x["municipio"]["uf"]["sigla"] == params["nomeSiglaUF"]]
            p = int(params.get("pagina", 1))
            if self.api_paginas_sem_filtro and "nomeSiglaUF" not in params and p > self.api_paginas_sem_filtro:
                return 400, '{"Erro na API":"Erro ao executar a consulta"}'.encode(), "application/json"
            return self._json(todos[(p - 1) * 15: p * 15])

        if u.netloc == "api.portaldatransparencia.gov.br" and path == "/api-de-dados/despesas/recursos-recebidos":
            mi, mf = params["mesAnoInicio"], params["mesAnoFim"]
            if mi != mf:
                return 400, b'{"Erro":"periodo"}', "application/json"
            linhas = self.recursos_mes(int(mi[3:]), int(mi[:2]))
            if "orgaoSuperior" in params:
                linhas = [x for x in linhas if x["codigoOrgaoSuperior"] == params["orgaoSuperior"]]
            p = int(params.get("pagina", 1))
            if self.recursos_max_pagina and "orgaoSuperior" not in params and p > self.recursos_max_pagina:
                return 400, '{"Erro na API":"Erro ao executar a consulta"}'.encode(), "application/json"
            return self._json(linhas[(p - 1) * 15: p * 15])

        if u.netloc == "api.portaldatransparencia.gov.br" and path == "/api-de-dados/servidores/por-orgao":
            todos = [{"qntPessoas": n, "qntVinculos": n, "descSituacao": sit, "nomOrgaoExercicioSiape": org}
                     for org in ("Ministério da Saúde", "Ministério da Educação")
                     for sit, n in (("Ativo Permanente", 300000), ("Aposentado", 200000), ("Pensionista", 100000))]
            p = int(params.get("pagina", 1))
            return self._json(todos[(p - 1) * 15: p * 15])

        if u.netloc == "api.portaldatransparencia.gov.br" and path == "/api-de-dados/orgaos-siafi":
            p = int(params.get("pagina", 1))
            todos = [{"codigo": c, "descricao": n} for c, n in self.ORGAOS_SUP] + [{"codigo": "26246", "descricao": "Universidade X"}]
            return self._json(todos[(p - 1) * 15: p * 15])

        m = re.search(r"/renuncias/(\d{4})_RenunciasFiscais\.zip$", path)
        if m:
            z = self._renuncias_zip(int(m.group(1)))
            return (200, z, "application/zip") if z else (403, b"<Error>AccessDenied</Error>", "application/xml")

        if "/download-de-dados/despesas/" in url:  # arquivos diários de despesas (pagamentos das emendas)
            dia = path.rstrip("/").rsplit("/", 1)[-1]
            z = self._despesas_dia(dia)
            return (200, z, "application/zip") if z else (404, b"", "text/html")

        return 404, b"", "text/html"

    ORGAOS_SUP = [("26000", "Ministério da Educação"), ("36000", "Ministério da Saúde"), ("52000", "Ministério da Defesa")]

    def recursos_mes(self, ano: int, mes: int) -> list[dict]:
        """Linhas da consulta "recursos recebidos por favorecido" de um mês (empresas, uma prefeitura e pessoas físicas)."""
        rng = random.Random(ano * 100 + mes)
        out = []
        for i in range(40):
            cs, ns = self.ORGAOS_SUP[i % 3]
            ug = f"{150000 + i % 7}"
            if i % 13 == 5:
                cod, nome = "***.123.456-**", "FULANO DE TAL"
            elif i % 17 == 3:
                cod, nome = "18.715.383/0001-40", "MUNICIPIO DE ITAJUBA"
            else:
                c = cnpj_matriz(str(10_000_000 + (i % 23) * 1_234_567 % 89_999_999))
                cod, nome = f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}", f"EMPRESA {i % 23} LTDA"
            out.append({"anoMes": ano * 100 + mes, "codigoPessoa": cod, "nomePessoa": nome, "tipoPessoa": "Pessoa Jurídica",
                        "municipioPessoa": "ITAJUBA", "siglaUFPessoa": "MG", "codigoUG": ug, "nomeUG": f"UG {ug}",
                        "codigoOrgao": cs, "nomeOrgao": ns, "codigoOrgaoSuperior": cs, "nomeOrgaoSuperior": ns,
                        "valor": round(rng.uniform(1000, 900000), 2)})
        # a mesma empresa e unidade gestora aparecem uma vez por mês: junta as que o sorteio repetiu
        unico: dict[tuple, dict] = {}
        for x in out:
            k = (x["codigoPessoa"], x["codigoUG"])
            if k in unico:
                unico[k]["valor"] = round(unico[k]["valor"] + x["valor"], 2)
            else:
                unico[k] = x
        return list(unico.values())

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
                # pagamentos sem emenda (página de incentivos): contrato, convênio com entidade, estatal e folha (não entram as duas últimas)
                ce, assoc, publica, _ = self.incentivo_empresas
                for k, (doc, nome, natureza, valor, org) in enumerate([
                        (ce, "CONTRATADA FICTICIA LTDA", "33903900", "100000,00", "Ministério da Defesa"),
                        (ce, "CONTRATADA FICTICIA LTDA", "44905100", "50000,00", "Ministério dos Transportes"),
                        (assoc, "ASSOCIACAO FICTICIA DE APOIO", "33504100", "20000,00", "Ministério da Cultura"),
                        (publica, "ESTATAL FICTICIA SA", "33903900", "70000,00", "Ministério da Defesa"),
                        (ce, "CONTRATADA FICTICIA LTDA", "31901100", "999,00", "Ministério da Defesa")]):
                    cod = f"22222222222{ano}OB00000{k}"
                    imp.append([cod, f"22222222222{ano}NE00000{k}", natureza, "00", valor, "0,00"])
                    pag.append([cod, f"20/04/{ano}", "Ordem Bancária", org, org, "UG FICTICIA", doc, nome, "CONTRATO", valor])
                z.writestr(f"{dia}_Despesas_Pagamento_EmpenhosImpactados.csv", _csv(
                    ["Código Pagamento", "Código Empenho", "Código Natureza Despesa Completa", "Subitem", "Valor Pago (R$)",
                     "Valor Restos a Pagar Pagos (R$)"], imp).encode("latin-1"))
                z.writestr(f"{dia}_Despesas_Pagamento.csv", _csv(
                    ["Código Pagamento", "Data Emissão", "Tipo Documento", "Órgão Superior", "Órgão", "Unidade Gestora",
                     "Código Favorecido", "Favorecido", "Observação", "Valor do Pagamento Convertido pra R$"], pag).encode("latin-1"))
        return buf.getvalue()


    def _renuncias_api(self, ano: int) -> list[dict]:
        """As mesmas linhas do .zip, no formato da API (campos aninhados, número com ponto)."""
        z = self._renuncias_zip(ano)
        if not z:
            return []
        with zipfile.ZipFile(io.BytesIO(z)) as zz:
            nome = next(n for n in zz.namelist() if n.endswith("_RenúnciasFiscais.csv"))
            linhas = list(csv.DictReader(io.StringIO(zz.read(nome).decode("latin-1")), delimiter=";"))
        return [{"id": i, "ano": int(r["Ano-calendário"]), "cnpj": r["CNPJ"], "razaoSocial": r["Razão Social"],
                 "nomeFantasia": r["Nome Fantasia"], "cnae": {"codigo": r["Código CNAE"], "descricao": r["CNAE"]},
                 "municipio": {"codigoIBGE": "", "nomeIBGE": r["Município"], "uf": {"sigla": r["UF"], "nome": ""}},
                 "tipoRenuncia": r["Tipo Renúncia"], "beneficioFiscal": r["Benefício Fiscal"],
                 "fundamentoLegal": r["Fundamento Legal"], "tributo": r["Tributo"], "formaTributacao": r["Forma Tributação"],
                 "valorRenunciado": float(r["Valor Renúncia Fiscal (R$)"].replace(",", "."))} for i, r in enumerate(linhas)]

    def _renuncias_zip(self, ano: int) -> bytes | None:
        """Renúncia fiscal do ano do site e do anterior (o mais recente pela metade, como na Receita)."""
        if ano not in self.anos and ano + 1 not in self.anos:
            return None
        ce, _, _, sem = self.incentivo_empresas
        f = 1 if ano + 1 in self.anos else 0.5
        empresas = [(ce, "CONTRATADA FICTICIA LTDA", "41204", "Construção de edifícios", "SAO PAULO", "SP", 500000 * f),
                    (self.fornecedoras[0], "FORNECEDORA FICTICIA 00 LTDA", "49302", "Transporte rodoviário de carga", "SAO PAULO", "SP", 200000 * f),
                    (sem, "INDUSTRIA SEM CADASTRO SA", "10996", "Fabricação de alimentos", "MANAUS", "AM", 300000 * f),
                    ("-3", "Inválido", "", "", "", "", 1000)]
        num = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
        ben = [[str(ano), c, n, "", cod, cnae, mun, uf, num(v)] for c, n, cod, cnae, mun, uf, v in empresas]
        det = []
        for c, n, cod, cnae, mun, uf, v in empresas:
            det.append([str(ano), c, n, "", cod, cnae, mun, uf, "Tributo Federal", "Zona Franca de Manaus" if uf == "AM" else "Sudene",
                        "Lei 0000/00", "Descrição", "IRPJ", "Lucro Real", num(v * 0.75)])
            det.append([str(ano), c, n, "", cod, cnae, mun, uf, "Tributo Federal", "Desoneração da folha", "Lei 0001/00", "Descrição",
                        "Contribuição Previdenciária", "Lucro Real", num(v * 0.25)])
        cab = ["Ano-calendário", "CNPJ", "Razão Social", "Nome Fantasia", "Código CNAE", "CNAE", "Município", "UF"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(f"{ano}_RenúnciasFiscaisPorBeneficiário.csv", _csv(cab + ["Valor Renúncia Fiscal (R$)"], ben).encode("latin-1"))
            z.writestr(f"{ano}_RenúnciasFiscais.csv", _csv(cab + ["Tipo Renúncia", "Benefício Fiscal", "Fundamento Legal", "Descrição Benefício",
                                                                   "Tributo", "Forma Tributação", "Valor Renúncia Fiscal (R$)"], det).encode("latin-1"))
            z.writestr(f"{ano}_EmpresasHabilitadas.csv", _csv(["CNPJ"], [[ce]]).encode("latin-1"))
        return buf.getvalue()


def instalar(monkeypatch, gov: FakeGov) -> FakeGov:
    """Troca a internet pelo FakeGov e tira as esperas entre tentativas (os testes não precisam esperar)."""
    def request(self, method, url, params=None, **kw):
        return gov.responder(method.upper(), url, params, headers={**self.headers, **(kw.get("headers") or {})})
    monkeypatch.setattr(requests.Session, "request", request)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return gov
