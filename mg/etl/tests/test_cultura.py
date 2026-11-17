"""Shows e cultura: contratação de artistas (PNCP), emendas Pix com show ou evento, Lei Rouanet (SALIC) e população
(IBGE). Tudo contra fontes simuladas (dados de teste; nada disso vai para o site)."""
import datetime as dt
import json

import pytest
import requests

from mg_etl import cultura, fontes
from sa_etl import util

HOJE = dt.date(2026, 2, 10)
CPF = "52998224725"

MUNICIPIOS = [
    {"id": 3132404, "nome": "Itajubá", "regiao-imediata": {"nome": "Itajubá", "regiao-intermediaria": {"nome": "Pouso Alegre"}}},
    {"id": 3147006, "nome": "Paraisópolis", "regiao-imediata": {"nome": "Itajubá", "regiao-intermediaria": {"nome": "Pouso Alegre"}}},
    {"id": 3106200, "nome": "Belo Horizonte", "regiao-imediata": {"nome": "Belo Horizonte", "regiao-intermediaria": {"nome": "Belo Horizonte"}}},
    {"id": 3122306, "nome": "Olhos-d'Água", "regiao-imediata": {"nome": "Bocaiúva", "regiao-intermediaria": {"nome": "Montes Claros"}}},
]
POPULACAO = [{"id": "9324", "resultados": [{"series": [
    {"localidade": {"id": "3132404", "nome": "Itajubá - MG"}, "serie": {"2025": "97000"}},
    {"localidade": {"id": "3147006", "nome": "Paraisópolis - MG"}, "serie": {"2025": "20000"}},
    {"localidade": {"id": "3106200", "nome": "Belo Horizonte - MG"}, "serie": {"2025": "2400000"}},
    {"localidade": {"id": "3122306", "nome": "Olhos-d'Água - MG"}, "serie": {"2025": "..."}},
]}]}]


def compra(seq, amparo, valor, cnpj="18025940000109", cod="3132404", mun="Itajubá", objeto="Show da dupla na festa"):
    return {"numeroControlePNCP": f"{cnpj}-1-{seq:06d}/2026", "anoCompra": 2026, "sequencialCompra": seq, "objetoCompra": objeto,
            "valorTotalHomologado": valor, "valorTotalEstimado": valor, "dataPublicacaoPncp": "2026-01-15T10:00:00",
            "amparoLegal": {"codigo": 0, "nome": amparo, "descricao": ""},
            "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": "MUNICIPIO DE ITAJUBA", "esferaId": "M"},
            "unidadeOrgao": {"ufSigla": "MG", "municipioNome": mun, "codigoIbge": cod}}


class Fake:
    def __init__(self):
        self.chamadas = []
        self.fora: set[str] = set()
        self.recusas_429 = 0  # quantos pedidos ao PNCP recebem HTTP 429 antes de responder
        self.compras = [
            compra(1, "Lei 14.133/2021, Art. 74, II", 80000),
            compra(2, "Lei 14.133/2021, Art. 74, I", 50000, objeto="Software exclusivo"),  # fornecedor exclusivo: não é artista
            compra(3, "Lei 14.133/2021, Art. 74, III, a", 9000, objeto="Parecer técnico"),
            compra(4, "Lei 14.133/2021, Art. 74, II", 20000, cod="3147006", mun="Paraisópolis", objeto="Apresentação musical"),
        ]
        self.resultados = {
            1: [{"niFornecedor": "11222333000181", "tipoPessoa": "PJ", "nomeRazaoSocialFornecedor": "DUPLA PRODUCOES LTDA",
                 "valorTotalHomologado": 80000}],
            4: [{"niFornecedor": CPF, "tipoPessoa": "PF", "nomeRazaoSocialFornecedor": f"JOAO CANTOR - {CPF}",
                 "valorTotalHomologado": 20000}],
        }
        self.incentivadores = [
            {"nome": "EMPRESA MINEIRA SA", "cgccpf": "11222333000181", "municipio": "Belo Horizonte", "UF": "MG", "tipo_pessoa": "juridica", "total_doado": 1_000_000},
            {"nome": "FULANO DE TAL", "cgccpf": CPF, "municipio": "Itajubá", "UF": "MG", "tipo_pessoa": "fisica", "total_doado": 5000},
            {"nome": "OUTRA LTDA", "cgccpf": "33000167000101", "municipio": "Itajuba", "UF": "MG", "tipo_pessoa": "juridica", "total_doado": 95000},
        ]
        # doações de cada incentivador, pela data do recibo (somam o total_doado da lista)
        self.doacoes = {
            "11222333000181": [{"valor": 600000, "data_recibo": "2024-05-10"}, {"valor": 400000, "data_recibo": "2025-03-02"}],
            CPF: [{"valor": 5000, "data_recibo": "2025-12-20"}],
            "33000167000101": [{"valor": 95000, "data_recibo": "2024-11-30"}],
        }
        self.projetos = [
            {"PRONAC": "230001", "nome": "Festival de Inverno", "proponente": "Associação Cultural", "municipio": "Itajubá", "UF": "MG",
             "ano_projeto": "23", "area": "Música", "segmento": "Música popular", "valor_captado": 300000},
            {"PRONAC": "240002", "nome": "Museu", "proponente": "Instituto", "municipio": "Belo Horizonte", "UF": "MG",
             "ano_projeto": "2024", "area": "Patrimônio", "segmento": "Museus", "valor_captado": 700000},
        ]

    def get(self, url, params=None, timeout=0, **kw):
        params = params or {}
        self.chamadas.append(url)
        if any(f in url for f in self.fora):
            raise RuntimeError(f"fora do ar: {url}")
        if url == cultura.IBGE_MUNICIPIOS:
            return resp(MUNICIPIOS)
        if url == cultura.IBGE_POPULACAO:
            return resp(POPULACAO)
        if url == cultura.PNCP_CONSULTA and self.recusas_429:
            self.recusas_429 -= 1
            raise RuntimeError(f"Não foi possível baixar {url}: 429 em {url}")
        if url == cultura.PNCP_CONSULTA:
            if params["dataInicial"] != "20260101":
                return resp(None, 204)
            tam, pag = params["tamanhoPagina"], params["pagina"]
            fatia = self.compras[(pag - 1) * 2: pag * 2]  # 2 por página, para testar a paginação
            restam = max(0, (len(self.compras) + 1) // 2 - pag)
            assert tam == cultura.TAM_PAGINA
            return resp({"data": fatia, "paginasRestantes": restam} if fatia else None, 200 if fatia else 204)
        if "/compras/" in url:
            seq = int(url.split("/compras/2026/")[1].split("/")[0])
            if url.endswith("/itens"):
                return resp([{"numeroItem": 1, "temResultado": seq in self.resultados}])
            return resp(self.resultados.get(seq, []))
        if url.startswith(cultura.SALIC_API) and url.endswith("/doacoes"):
            doc = url.rsplit("/", 2)[1]
            dados = self.doacoes.get(doc, [])
            off, lim = params["offset"], params["limit"]
            return resp({"_embedded": {"doacoes": dados[off: off + lim]}, "total": len(dados)})
        if url.startswith(cultura.SALIC_API):
            campo = url.rsplit("/", 1)[1]
            dados = self.incentivadores if campo == "incentivadores" else self.projetos
            off, lim = params["offset"], params["limit"]
            return resp({"_embedded": {campo: dados[off: off + lim]}, "total": len(dados), "count": len(dados[off: off + lim])})
        raise AssertionError(f"URL não simulada: {url}")


def resp(corpo, status=200):
    r = requests.Response()
    r.status_code = status
    r._content = b"" if corpo is None else json.dumps(corpo).encode()
    r.headers["content-type"] = "application/json"
    return r


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(cultura, "get", f.get)
    monkeypatch.setattr(cultura, "PRIMEIRO_MES", (2026, 1))
    monkeypatch.setattr(cultura, "PAUSA_PNCP", 0)
    monkeypatch.setattr(cultura, "ESPERA_429_PNCP", 0)
    util.AVISOS.clear()
    return f


def nacional_com_pix(tmp_path):
    """Os arquivos que o coletor nacional grava das emendas Pix (data/emendas/destino), com um plano de show."""
    nac = tmp_path / "nacional"
    pasta = nac / "emendas" / "destino"
    util.write_json(pasta / "2025.json", {"completo": True, "beneficiarios": [
        {"cnpj": "18025940000109", "uf": "MG"}, {"cnpj": "46395000000139", "uf": "SP"}]})
    util.write_json(pasta / "2025" / "18025940000109.json", {"nome": "MUNICIPIO DE ITAJUBA", "planos": [
        {"parlamentar": "Fulano Deputado", "emenda": "202512340001", "plano": "09032025-001", "objeto": "Realização do Carnaval 2025",
         "area": "Cultura", "valor": 300000, "gasto": 250000, "executores": [], "gastos": [
             {"data": "2025-02-20", "recebedor": "Banda Alegria Ltda", "cnpj": "11222333000181", "descricao": "Cachê do show da banda", "valor": 150000},
             {"data": "2025-02-21", "recebedor": "Som e Luz Ltda", "cnpj": "33000167000101", "descricao": "Locação de palco e sonorização do show", "valor": 100000}]},
        {"parlamentar": "Fulano Deputado", "emenda": "202512340002", "objeto": "Pavimentação da rua", "valor": 500000, "gasto": 0,
         "executores": [], "gastos": []},
        {"parlamentar": "Beltrana Senadora", "emenda": "202598760001", "objeto": "Festa do Peão de Boiadeiro", "valor": 100000,
         "gasto": 0, "executores": [], "gastos": []},
    ]})
    util.write_json(pasta / "2025" / "46395000000139.json", {"nome": "MUNICIPIO DE SAO PAULO", "planos": [
        {"parlamentar": "Outro", "objeto": "Show na virada", "valor": 9e6, "gasto": 0, "executores": [], "gastos": []}]})
    return nac


# ---------------------------------------------------------------- peças pequenas

@pytest.mark.parametrize("nome", ["MUNICIPIO DE ITAJUBA", "Prefeitura Municipal de Itajubá", "Itajubá - MG", "ITAJUBA/MG", "itajubá"])
def test_chave_da_cidade(nome):
    assert cultura.chave(nome) == "ITAJUBA"


def test_so_art_74_inciso_II_e_artista():
    assert cultura.artistica({"amparoLegal": {"nome": "Lei 14.133/2021, Art. 74, II"}})
    assert cultura.artistica({"amparoLegal": {"nome": "x", "descricao": "contratação de profissional do setor artístico"}})
    for nao in ("Lei 14.133/2021, Art. 74, I", "Lei 14.133/2021, Art. 74, III, a", "Lei 14.133/2021, Art. 75, II", ""):
        assert not cultura.artistica({"amparoLegal": {"nome": nao}}), nao


def test_palavras_de_show_e_evento():
    assert "carnaval" in cultura.palavras("Realização do Carnaval 2025")
    assert cultura.palavras("Pavimentação asfáltica da rua") == []
    assert cultura.pagamento_artista("Cachê do show da banda")
    assert not cultura.pagamento_artista("Locação de palco e sonorização do show")


# ---------------------------------------------------------------- cada fonte

def test_contratacoes_de_artistas_pelo_pncp(fake, tmp_path):
    mun, (pop, ano) = cultura.municipios(tmp_path), cultura.populacao(tmp_path)
    assert ano == "2025" and pop[3132404] == 97000 and 3122306 not in pop, "'...' do IBGE não vira número"
    cid = cultura.Cidades(mun, pop)
    p = cultura.coletar_pncp(tmp_path, 5, HOJE)
    assert p["completo"]
    r = cultura.resumir_pncp(p, cid)
    assert r["n"] == 2 and r["total"] == 100000, "só as duas do art. 74, II"
    assert [c["nome"] for c in r["cidades"]] == ["Itajubá", "Paraisópolis"]
    assert r["cidades"][0]["populacao"] == 97000 and r["cidades"][0]["por_habitante"] == pytest.approx(80000 / 97000, abs=0.01)
    assert r["artistas"][0]["nome"] == "Dupla Producoes Ltda" and r["artistas"][0]["cnpj"] == "11222333000181"
    pf = r["artistas"][1]
    assert pf["pessoa"] and pf["cnpj"] == "" and CPF not in json.dumps(r), "CPF do artista nunca sai"
    assert r["lista"][0]["url"].startswith("https://pncp.gov.br/app/editais/18025940000109/2026/")


def test_pncp_continua_de_onde_parou(fake, tmp_path, monkeypatch):
    chamadas = {"n": 0}
    original = cultura.Relogio.checar

    def pouco_tempo(self):
        chamadas["n"] += 1
        if chamadas["n"] > 2:  # fevereiro (vazio) e a primeira página de janeiro
            raise cultura.SemTempo()
        original(self)
    monkeypatch.setattr(cultura.Relogio, "checar", pouco_tempo)
    p = cultura.coletar_pncp(tmp_path, 5, HOJE)
    assert not p["completo"] and len(p["compras"]) == 1, "a primeira página fica guardada"
    monkeypatch.setattr(cultura.Relogio, "checar", original)
    p = cultura.coletar_pncp(tmp_path, 5, HOJE)
    assert p["completo"] and len(p["compras"]) == 2
    antes = len(fake.chamadas)
    cultura.coletar_pncp(tmp_path, 5, HOJE)
    assert not [c for c in fake.chamadas[antes:] if "/compras/" in c], "resultado já lido não é pedido de novo"


def test_pncp_espera_depois_de_429(fake, tmp_path, monkeypatch):
    """O PNCP recusa pedidos seguidos (HTTP 429): a leitura espera e tenta de novo, como nas licitações."""
    esperas = []
    monkeypatch.setattr(cultura.time, "sleep", esperas.append)
    monkeypatch.setattr(cultura, "PAUSA_PNCP", 4)
    monkeypatch.setattr(cultura, "ESPERA_429_PNCP", 30)
    fake.recusas_429 = 2
    p = cultura.coletar_pncp(tmp_path, 5, HOJE)
    assert p["completo"] and len(p["compras"]) == 2
    assert 30 in esperas and 60 in esperas, "espera maior depois de cada 429 (o dobro na segunda)"
    assert esperas.count(4) >= 3, "pausa antes de cada pedido ao PNCP"


def test_pix_com_show_e_evento(tmp_path, fake):
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    r = cultura.coletar_pix(nacional_com_pix(tmp_path), cid, set())
    assert r["n"] == 2, "carnaval e festa do peão entram; pavimentação e São Paulo não"
    assert r["parlamentares"][0]["nome"] == "Fulano Deputado" and r["parlamentares"][0]["valor"] == 300000
    assert r["planos"][0]["cidade"] == "Itajubá" and r["planos"][0]["populacao"] == 97000
    assert [a["nome"] for a in r["artistas"]] == ["Banda Alegria Ltda"], "palco e som não contam como artista"


def test_lei_rouanet_por_regiao(fake, tmp_path):
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    r = cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)
    inc = r["incentivadores"]
    assert r["completo"] and inc["total"] == 1_100_000 and inc["n_pessoas"] == 1 and inc["pessoas"] == 5000
    assert [x["regiao"] for x in inc["regioes"]] == ["Belo Horizonte", "Pouso Alegre"]
    pa = inc["regioes"][1]
    assert pa["valor"] == 100000 and pa["populacao"] == 117000
    assert next(c for c in inc["cidades"] if c["nome"] == "Itajubá")["valor"] == 100000, "'Itajuba' e 'Itajubá' são a mesma cidade"
    assert "Fulano" not in json.dumps(r) and CPF not in json.dumps(r), "pessoa física só entra na soma"
    pr = r["projetos"]
    assert pr["total"] == 1_000_000 and {x["ano"] for x in pr["por_ano"]} == {2023, 2024}


def test_lei_rouanet_por_ano_pelo_recibo_das_doacoes(fake, tmp_path):
    """O total_doado não diz o ano: a divisão sai das doações de cada incentivador, pelo ano do recibo."""
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    inc = cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)["incentivadores"]
    assert inc["por_ano"] == [{"ano": 2024, "valor": 695000, "n": 2}, {"ano": 2025, "valor": 405000, "n": 2}]
    assert sum(x["valor"] for x in inc["por_ano"]) == inc["total"]
    assert inc["cobertura_anos"] == {"lidos": 3, "de": 3, "valor": 1_100_000, "fracao": 1.0}
    a2024 = next(x for x in inc["por_ano_regioes"] if x["ano"] == 2024)["regioes"]
    assert a2024 == [{"regiao": "Belo Horizonte", "valor": 600000}, {"regiao": "Pouso Alegre", "valor": 95000}]
    assert CPF not in (tmp_path / "salic" / "doacoes-mg.json.gz").read_bytes().decode("latin1"), "o cache guarda só um resumo do número"
    # na execução seguinte, quem não mudou de total não é lido de novo
    fake.chamadas.clear()
    cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)
    assert not [u for u in fake.chamadas if u.endswith("/doacoes")]
    # quem doou de novo (total mudou) é lido de novo
    fake.incentivadores[2]["total_doado"] = 100000
    fake.doacoes["33000167000101"].append({"valor": 5000, "data_recibo": "2026-01-15"})
    fake.chamadas.clear()
    inc = cultura.coletar_rouanet(tmp_path, 5, HOJE + dt.timedelta(days=8), cid)["incentivadores"]
    assert [u for u in fake.chamadas if u.endswith("/doacoes")] == [f"{cultura.SALIC_API}/incentivadores/33000167000101/doacoes"]
    assert {x["ano"]: x["valor"] for x in inc["por_ano"]}[2026] == 5000


def test_lei_rouanet_por_ano_aos_poucos_mostra_a_cobertura(fake, tmp_path, monkeypatch):
    """Sem tempo para todos: lê os maiores primeiro e o site diz quanto do valor já está dividido por ano."""
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    pasta = tmp_path / "salic"
    inc_ok, _ = cultura._salic_lista("incentivadores", {"UF": "MG"}, cultura.Relogio(5), pasta / "incentivadores-mg.json.gz", HOJE, "incentivadores")
    rel = cultura.Relogio(5)
    restam = iter([True, False])  # só um pedido de doações cabe no tempo

    def checar():
        if not next(restam, False):
            raise cultura.SemTempo()
    monkeypatch.setattr(rel, "checar", checar)
    doacoes, completo, erro = cultura.ler_doacoes(inc_ok, rel, pasta / "doacoes-mg.json.gz")
    assert not completo and len(doacoes) == 1 and not erro
    inc = cultura.resumir_rouanet(inc_ok, [], cid, doacoes)["incentivadores"]
    assert inc["cobertura_anos"]["lidos"] == 1 and inc["cobertura_anos"]["fracao"] == round(1_000_000 / 1_100_000, 4)
    assert sum(x["valor"] for x in inc["por_ano"]) == 1_000_000, "o maior doador vem primeiro"


# ---------------------------------------------------------------- montagem e caos

def test_montagem_grava_os_arquivos(fake, tmp_path):
    saida = tmp_path / "saida"
    cont = cultura.coletar(nacional_com_pix(tmp_path), saida, tmp_path / "cache", set(), hoje=HOJE)
    assert cont == {"contratos_artistas": 2, "pix_eventos": 2, "rouanet_projetos": 2}
    d = json.loads((saida / "estado" / "cultura.json").read_text(encoding="utf-8"))
    assert d["contratos"]["anos"] == [2026] and d["populacao"]["ano"] == "2025"
    assert json.loads((saida / "estado" / "cultura" / "contratos-2026.json").read_text())["lista"]
    assert CPF not in (saida / "estado" / "cultura.json").read_text()
    assert not util.AVISOS


@pytest.mark.parametrize("fora", ["pncp.gov.br", "api.salic", "servicodados.ibge"])
def test_fonte_fora_do_ar_nao_derruba_as_outras(fake, tmp_path, fora):
    fake.fora.add(fora)
    saida = tmp_path / "saida"
    cultura.coletar(nacional_com_pix(tmp_path), saida, tmp_path / "cache", set(), hoje=HOJE)
    d = json.loads((saida / "estado" / "cultura.json").read_text(encoding="utf-8"))
    assert d["pix"]["n"] == 2
    assert util.AVISOS, "o site avisa o que ficou de fora"
    if fora == "api.salic":
        assert d["rouanet"] is None and d["contratos"]["n"] == 2
    if fora == "pncp.gov.br":
        assert d["contratos"] is None and d["rouanet"]["completo"]


def test_salic_fora_usa_a_ultima_leitura(fake, tmp_path):
    cid = cultura.Cidades({}, {})
    assert cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)["completo"]
    fake.fora.add("api.salic")
    r = cultura.coletar_rouanet(tmp_path, 5, HOJE + dt.timedelta(days=10), cid)
    assert r and not r["completo"] and r["incentivadores"]["total"] == 1_100_000


def test_bonito_existe():
    assert fontes.bonito("DUPLA PRODUCOES LTDA") == "Dupla Producoes Ltda"


def test_conferencia_aceita_e_barra_cpf(fake, tmp_path):
    from mg_etl.validar import Resultado, conferir_cultura
    saida = tmp_path / "saida"
    cultura.coletar(nacional_com_pix(tmp_path), saida, tmp_path / "cache", set(), hoje=HOJE)
    r = Resultado()
    conferir_cultura(saida, r)
    assert not r.erros, r.erros
    f = saida / "estado" / "cultura.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["contratos"]["artistas"][0]["nome"] += f" {CPF}"
    f.write_text(json.dumps(d), encoding="utf-8")
    r = Resultado()
    conferir_cultura(saida, r)
    assert r.erros


def test_cpf_no_texto_some_antes_de_gravar():
    d = cultura._limpar({"objeto": f"Show contratado, processo {CPF}", "cnpj": "123", "lista": [{"nome": f"X {CPF}"}]})
    assert CPF not in json.dumps(d) and d["cnpj"] == ""


def test_parte_que_nao_passa_na_conferencia_fica_de_fora_sem_travar(tmp_path, monkeypatch):
    """Se uma parte não bater (soma errada), só ela sai do arquivo; o resto é publicado e o site avisa."""
    util.AVISOS.clear()
    resumo = {"atualizado": "2026-02-10", "populacao": None,
              "contratos": {"total": 100.0, "por_ano": [{"ano": 2026, "valor": 50.0, "n": 1}], "cidades": [], "anos": []},
              "pix": {"total": 10.0, "parlamentares": [{"nome": "A", "valor": 10.0}]}, "rouanet": None}
    cultura.gravar(tmp_path, resumo, {})
    d = json.loads((tmp_path / "estado" / "cultura.json").read_text(encoding="utf-8"))
    assert d["contratos"] is None and d["pix"]["total"] == 10.0
    assert any("contratações de artistas" in a for a in util.AVISOS)


def test_doacoes_andam_mesmo_com_a_lista_sem_tempo(fake, tmp_path, monkeypatch):
    """A lista de incentivadores pode gastar todo o tempo dela: as doações têm um tempo próprio e andam assim mesmo,
    com a última lista completa."""
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    cultura._salic_lista("incentivadores", {"UF": "MG", "sort": "total_doado:desc"}, cultura.Relogio(5),
                         tmp_path / "salic" / "incentivadores-mg.json.gz", HOJE, "incentivadores")
    # a lista venceu (8 dias) e a leitura nova não cabe no tempo dela (0 minuto)
    r = cultura.coletar_rouanet(tmp_path, 0, HOJE + dt.timedelta(days=8), cid, minutos_doacoes=5)
    assert not r["completo"] and r["incentivadores"]["cobertura_anos"]["fracao"] == 1.0


def test_doador_com_erro_e_pulado_e_o_site_diz_o_motivo(fake, tmp_path):
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    del fake.doacoes["11222333000181"]
    orig = fake.get

    def get(url, params=None, **kw):
        if url.endswith("/11222333000181/doacoes"):
            return resp({"erro": "formato inesperado"})
        return orig(url, params=params, **kw)
    fake.get = get
    cultura.get = get
    inc = cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)["incentivadores"]
    assert inc["cobertura_anos"]["lidos"] == 2, "os outros doadores foram lidos"
    assert any("doações de cada incentivador" in a and "_embedded.doacoes" in a for a in util.AVISOS)


def _erro_404(url):
    r = resp({"message": "Not Found"}, 404)
    r.url = url
    return requests.HTTPError(f"404 Client Error: Not Found for url: {url}", response=r)


def test_link_de_doacoes_com_404_tenta_o_cnpj_e_lembra_a_forma(fake, tmp_path):
    """Em 16/11/2026 o link _links.doacoes da lista respondeu 404: tentamos as outras formas do endereço e a que
    funcionou vai primeiro para os próximos doadores."""
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    for i, x in enumerate(fake.incentivadores):
        x["_links"] = {"self": f"https://api.salic.cultura.gov.br/api/v1/incentivadores/abc{i}",
                       "doacoes": f"https://api.salic.cultura.gov.br/api/v1/incentivadores/def{i}/doacoes"}
    orig = fake.get

    def get(url, params=None, **kw):
        if "/incentivadores/abc" in url or "/incentivadores/def" in url:
            fake.chamadas.append(url)
            raise _erro_404(url)
        return orig(url, params=params, **kw)
    fake.get = get
    cultura.get = get
    inc = cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)["incentivadores"]
    assert inc["cobertura_anos"]["fracao"] == 1.0
    assert {a["ano"]: a["valor"] for a in inc["por_ano"]} == {2024: 695000.0, 2025: 405000.0}
    falhas = [u for u in fake.chamadas if "/incentivadores/abc" in u or "/incentivadores/def" in u]
    assert len(falhas) == 2, "só o primeiro doador tenta o link quebrado; os outros vão direto pelo CNPJ/CPF"
    assert not any("doações de cada incentivador" in a for a in util.AVISOS)


def test_404_em_todas_as_formas_avisa_sem_mostrar_o_cpf(fake, tmp_path):
    cid = cultura.Cidades(cultura.municipios(tmp_path), cultura.populacao(tmp_path)[0])
    orig = fake.get

    def get(url, params=None, **kw):
        if "/doacoes" in url:
            raise _erro_404(url)
        return orig(url, params=params, **kw)
    fake.get = get
    cultura.get = get
    inc = cultura.coletar_rouanet(tmp_path, 5, HOJE, cid)["incentivadores"]
    assert inc["cobertura_anos"]["fracao"] == 0
    aviso = next(a for a in util.AVISOS if "doações de cada incentivador" in a)
    assert "HTTP 404 em todas as" in aviso and "CNPJ/CPF" in aviso
    assert CPF not in aviso and "11222333000181" not in aviso
