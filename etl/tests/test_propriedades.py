"""Base da pirâmide: testes unitários e de propriedades (Hypothesis gera milhares de entradas por teste).

Cada teste afirma uma regra que vale para QUALQUER entrada, não só para os exemplos que pensamos.
"""
import json
import re
import string

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sa_etl import camara, cnpj, senado, temas, util
from sa_etl.build import montar, sem_repetidos
from sa_etl.validar import validar

rapido = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


# ---------------------------------------------------------------- números e documentos

@rapido
@given(st.decimals(min_value=-10**9, max_value=10**9, places=2, allow_nan=False, allow_infinity=False))
def test_to_float_le_o_formato_brasileiro_e_o_americano(v):
    br = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    assert util.to_float(br) == float(v)
    assert util.to_float(f"{v:.2f}") == float(v)


@rapido
@given(st.text())
def test_to_float_nunca_quebra(s):
    assert isinstance(util.to_float(s), float)


@rapido
@given(st.text(alphabet=string.digits, min_size=8, max_size=8))
def test_cnpj_da_matriz_sempre_valido(raiz):
    c = cnpj.cnpj_matriz(raiz)
    assert len(c) == 14 and c.startswith(raiz) and util.cnpj_valido(c)


@rapido
@given(st.text(alphabet=string.digits, min_size=14, max_size=14))
def test_cnpj_com_um_digito_trocado_e_invalido(c):
    if not util.cnpj_valido(c):
        return
    errado = c[:13] + str((int(c[13]) + 1) % 10)
    assert not util.cnpj_valido(errado)


@rapido
@given(st.text(alphabet=string.digits, min_size=11, max_size=11))
def test_mascara_de_cpf_esconde_inicio_e_fim(cpf):
    m = util.mask_cpf(cpf)
    assert m.startswith("***.") and m.endswith("-**") and cpf not in m
    assert re.sub(r"\D", "", m) == cpf[3:9]


# ---------------------------------------------------------------- segurança: ids e links

@rapido
@given(st.text())
def test_id_seguro_nunca_sai_da_pasta(s):
    i = util.id_seguro(s)
    assert i is None or (re.fullmatch(r"[A-Za-z0-9_-]+", i) and "/" not in i and ".." not in i)


@rapido
@given(st.text())
def test_url_segura_so_aceita_http(s):
    u = util.url_segura(s)
    assert u == "" or re.match(r"^https?://", u, re.I)


def test_url_segura_bloqueia_esquemas_perigosos():
    for ruim in ["javascript:alert(1)", " JaVaScRiPt:alert(1)", "data:text/html,<script>", "vbscript:x", "//evil.com",
                 "https://ok.gov.br/\"><script>", "file:///etc/passwd"]:
        assert util.url_segura(ruim) == "", ruim
    assert util.url_segura(" https://www.camara.leg.br/x.pdf ") == "https://www.camara.leg.br/x.pdf"


def test_deputado_com_id_estranho_e_ignorado(monkeypatch):
    monkeypatch.setattr(camara, "get_json", lambda url, params=None: {"dados": [
        {"id": "../../etc", "nome": "X"}, {"id": 7, "nome": "Ok", "urlFoto": "javascript:alert(1)"}], "links": []})
    ds = camara.deputados()
    assert [d["id"] for d in ds] == ["dep-7"] and ds[0]["foto"] == ""


def test_link_de_detalhe_nunca_leva_cpf():
    u = camara.link_detalhe("123", 2025, 5, "1", "123.456.789-09", "1", "9")
    assert "12345678909" not in u and u.startswith("https://www.camara.leg.br/cota-parlamentar/analitico")
    assert "11222333000181" in camara.link_detalhe("123", 2025, 5, "1", "11.222.333/0001-81", "1", "9")


# ---------------------------------------------------------------- votações

voto = st.sampled_from(["Sim", "Não", "Abstenção", "Obstrução", "Art. 17"])


@rapido
@given(st.lists(st.tuples(st.integers(1, 5), st.integers(1, 8), voto), max_size=80))
def test_votacoes_camara_sem_voto_duplicado(linhas):
    """Mesmo com linhas repetidas no arquivo, cada deputado vota uma vez em cada votação."""
    ids = {f"dep-{i}" for i in range(1, 9)}
    votacoes = [{"id": str(v), "siglaOrgao": "PLEN", "data": "2025-01-01"} for v in range(1, 6)] * 2
    votos = [{"idVotacao": str(v), "deputado_id": str(d), "voto": x, "deputado_siglaPartido": "A"} for v, d, x in linhas]
    vs, vts = camara.parse_votacoes(votacoes, votos, [], [], ids)
    assert len(vs) == len({v["id"] for v in vs})
    assert len(vts) == len({(v["votacao"], v["politico"]) for v in vts})


@rapido
@given(st.text(max_size=12))
def test_normaliza_voto_nunca_quebra(s):
    assert isinstance(camara.normaliza_voto(s), str)
    assert isinstance(senado.normaliza_voto_senado(s), str)


def test_senado_ignora_votacao_sem_codigo_e_repetida():
    item = {"codigoSessaoVotacao": 9, "votacaoSecreta": "N", "votos": [
        {"codigoParlamentar": 5, "siglaVotoParlamentar": "Sim"}, {"codigoParlamentar": 5, "siglaVotoParlamentar": "Sim"}]}
    v, vs = senado.parse_votacoes([item, item, {"votacaoSecreta": "N", "votos": item["votos"]}, "lixo"], {"sen-5"})
    assert [x["id"] for x in v] == ["sf-9"] and len(vs) == 1


@rapido
@given(st.text())
def test_temas_nunca_quebram(s):
    assert set(temas.temas_de(s)) <= set(temas.TEMAS)


# ---------------------------------------------------------------- holdings: qualquer grafo de sócios termina

@settings(max_examples=200, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 7), st.integers(0, 9)), max_size=25))
def test_donos_finais_termina_em_qualquer_grafo(arestas):
    """Empresas 0..7 com sócios que são empresas (0..7) ou pessoas (8, 9). Ciclos, auto-participação, tudo vale."""
    cn = [cnpj.cnpj_matriz(str(10_000_000 + i)) for i in range(8)]
    todas = {c: {"razao_social": f"E{i}", "socios": []} for i, c in enumerate(cn)}
    for de, para in arestas:
        if para < 8:
            todas[cn[de]]["socios"].append({"nome": f"E{para}", "doc": cn[para], "tipo": "empresa"})
        else:
            todas[cn[de]]["socios"].append({"nome": f"PESSOA {para}", "doc": f"***{para}**", "tipo": "pessoa"})
    for c in cn:
        for d in cnpj.donos_finais(c, todas):
            cadeia = [x["cnpj"][:8] for x in d["cadeia"]]
            assert len(cadeia) <= cnpj.MAX_NIVEL + 1
            assert d["fim"] in {"pessoa", "estrangeiro", "sem_socios", "sem_dados", "limite", "ciclo"}
            if d["fim"] != "ciclo":
                assert len(set(cadeia)) == len(cadeia) and c[:8] not in cadeia


# ---------------------------------------------------------------- montar: as somas sempre batem

despesa = st.fixed_dictionaries({
    "politico": st.sampled_from(["dep-1", "dep-2", "sen-3"]),
    "mes": st.integers(1, 12),
    "valor": st.decimals(min_value=-5000, max_value=50000, places=2).map(float),
    "doc": st.sampled_from(["11222333000181", "45997418000153", "12345678909", ""]),
    "categoria": st.sampled_from(["PASSAGEM AÉREA", "TELEFONIA", "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR."]),
})


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(despesa, max_size=60))
def test_montar_somas_batem_para_quaisquer_despesas(tmp_path_factory, ds):
    from sa_etl.categorias import categoria_curta, grupo_de
    pols = [{"id": "dep-1", "casa": "camara", "nome": "A", "partido": "PT", "uf": "SP", "foto": "", "fonte": ""},
            {"id": "dep-2", "casa": "camara", "nome": "B", "partido": "PL", "uf": "RJ", "foto": "", "fonte": ""},
            {"id": "sen-3", "casa": "senado", "nome": "C", "partido": "PL", "uf": "MG", "foto": "", "fonte": ""}]
    desp = [{**d, "ano": 2025, "data": f"2025-{d['mes']:02d}-01", "categoria": categoria_curta(d["categoria"]),
             "grupo": grupo_de(d["categoria"]), "fornecedor": "F", "url": "https://www.camara.leg.br/x.pdf", "link": "nota"}
            for d in ds if d["valor"]]
    saida = tmp_path_factory.mktemp("s")
    montar({"politicos": pols, "despesas": desp, "votacoes": [], "votos": [], "empresas": {}}, saida, [2025])
    r = validar(saida, minimos={"camara": 1, "senado": 1, "votacoes": 0})
    assert r.erros == []
    meta = json.loads((saida / "meta.json").read_text())
    assert abs(meta["total_gasto"] - sum(d["valor"] for d in desp)) < 0.01 * (len(desp) + 1)


def test_sem_repetidos_mantem_o_primeiro():
    assert sem_repetidos([{"id": 1, "x": "a"}, {"id": 1, "x": "b"}, {"id": 2}], "id") == [{"id": 1, "x": "a"}, {"id": 2}]
