"""Quem me representa: eleitos de cada cidade e estado, lidos dos arquivos do TSE fictício (fakegov_representantes)."""
import json
from pathlib import Path

import pytest

from fakegov import FakeGov, instalar
from sa_etl import representantes as R
from sa_etl import util
from sa_etl.validar import Resultado, _conferir_representantes

POLITICOS = [
    {"id": "dep-1", "casa": "camara", "nome": "Fulano", "partido": "PT", "uf": "MG", "em_exercicio": True,
     "cargo": "Deputado(a) Federal", "foto": "https://www.camara.leg.br/1.jpg"},
    {"id": "dep-2", "casa": "camara", "nome": "Saiu do Cargo", "partido": "PL", "uf": "MG", "em_exercicio": False},
    {"id": "sen-3", "casa": "senado", "nome": "Beltrana", "partido": "PL", "uf": "MG", "em_exercicio": True, "cargo": "Senador(a)"},
]


@pytest.fixture
def rodar(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov(anos=(2025,)))
    util.AVISOS.clear()

    def _rodar():
        saida = tmp_path / "data"
        saida.mkdir(exist_ok=True)
        (saida / "politicos.json").write_text(json.dumps(POLITICOS), encoding="utf-8")
        R.coletar(saida, tmp_path / "cache")
        return saida / "representantes"
    _rodar.gov = gov
    _rodar.tmp = tmp_path
    return _rodar


def ler(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_cidade_com_segundo_turno_e_vice_trocado(rodar):
    m = ler(rodar() / "m" / "71072.json")
    assert m["nome"] == "São Paulo" and m["uf"] == "SP"
    assert m["prefeito"]["nome"] == "Ricardo Ficticio" and m["prefeito"]["turnos"] == 2
    assert m["vice_prefeito"]["nome"] == "Coronel Mello"  # a candidatura que valeu, não a que renunciou
    assert len(m["vereadores"]) == m["vagas_vereadores"] == 7
    # o homônimo da Bahia, nascido em outro dia, não é o prefeito
    assert "em_2026" not in m["prefeito"]


def test_prefeito_que_disputou_2026_renunciou(rodar):
    m = ler(rodar() / "m" / "62910.json")
    e = m["prefeito"]["em_2026"]
    assert e == {"cargo": "Deputado federal", "uf": "SP", "partido": "PSD", "resultado": "não eleito", "renunciou": True}


def test_eleicao_suplementar_troca_o_prefeito(rodar):
    m = ler(rodar() / "m" / "40000.json")
    assert m["prefeito"]["nome"] == "Prefeito Novo" and m["vice_prefeito"]["nome"] == "Vice Novo"
    assert m["suplementar"]["data"] == "2026-04-05"
    assert m["suplementar"]["eleitos_2024"]["prefeito"]["situacao"].startswith("Cassado")


def test_suplementar_do_mandato_anterior_fica_de_fora(rodar):
    m = ler(rodar() / "m" / "41238.json")
    assert m["prefeito"]["nome"] == "Fuad" and "suplementar" not in m


def test_estado_governador_que_saiu_e_deputados(rodar):
    pasta = rodar()
    mg = ler(pasta / "uf" / "MG.json")
    assert mg["governador"]["em_2026"]["renunciou"] and mg["governador"]["em_2026"]["cargo"] == "Senador"
    assert mg["vice_governador"]["nome"] == "Mateus Simões"
    assert [d["nome"] for d in mg["deputados_estaduais"]] == ["Estadual 0", "Estadual 1", "Estadual 2", "Estadual 3"]
    assert mg["deputados_estaduais"][0]["em_2026"] == {"cargo": "Deputado estadual", "uf": "MG", "partido": "PL",
                                                       "resultado": "eleito", "reeleicao": True}
    assert [d["id"] for d in mg["deputados_federais"]] == ["dep-1"]  # quem saiu do cargo não aparece
    assert [d["id"] for d in mg["senadores"]] == ["sen-3"]
    df = ler(pasta / "uf" / "DF.json")
    assert df["casa_estadual"] == "Câmara Legislativa" and len(df["deputados_estaduais"]) == 2


def test_indice_presidente_e_busca(rodar):
    idx = ler(rodar() / "indice.json")
    assert idx["presidente"]["nome"] == "Lula Ficticio"
    assert idx["presidente"]["em_2026"]["reeleicao"] and "renunciou" not in idx["presidente"]["em_2026"]
    assert ["70670", "Santa Bárbara d'Oeste", "SP"] in idx["municipios"]
    assert ["DF", "Brasília", "DF"] in idx["municipios"]
    assert idx["fontes"]["candidatos_municipal"]["pagina"] == "https://dadosabertos.tse.jus.br/dataset/candidatos-2024"


def test_sem_dados_pessoais(rodar):
    pasta = rodar()
    texto = " ".join(f.read_text(encoding="utf-8") for f in pasta.rglob("*.json"))
    for proibido in ("12345678909", "x@x.com", "1967", "NASCIMENTO", "nascimento"):
        assert proibido not in texto
    r = Resultado()
    _conferir_representantes(pasta.parent, r)
    assert r.ok, r.erros
    assert any("Belo Horizonte" in a for a in r.alertas)  # 4 eleitos para 5 cadeiras: alerta, não erro


def test_validar_barra_mais_eleitos_que_cadeiras_e_dado_pessoal(rodar):
    pasta = rodar()
    f = pasta / "m" / "62910.json"
    m = ler(f)
    m["vagas_vereadores"] = 2
    m["prefeito"]["nascimento"] = "1960-07-26"
    f.write_text(json.dumps(m), encoding="utf-8")
    r = Resultado()
    _conferir_representantes(pasta.parent, r)
    assert any("5 vereadores eleitos para 2 cadeiras" in e for e in r.erros)
    assert any("dado pessoal" in e for e in r.erros)


def test_tse_fora_do_ar_usa_a_ultima_leitura(rodar):
    rodar()
    # a leitura de 2024 vence (7 dias) e o TSE cai: fica a cópia, com aviso e a data dela
    f = rodar.tmp / "cache" / "representantes" / "consulta_cand_2024.json"
    d = ler(f)
    d["lido_em"] = "2026-01-02"
    f.write_text(json.dumps(d), encoding="utf-8")
    rodar.gov.falhar("consulta_cand_2024", "500")
    util.AVISOS.clear()
    pasta = rodar()
    assert ler(pasta / "m" / "71072.json")["prefeito"]["nome"] == "Ricardo Ficticio"
    assert any("02/01/2026" in a for a in util.AVISOS)


def test_sem_copia_e_tse_fora_falha(rodar):
    rodar.gov.falhar("consulta_cand_2024", "500")
    with pytest.raises(Exception):
        rodar()


def test_leitura_dentro_da_validade_nao_baixa_de_novo(rodar):
    rodar()
    n = sum("consulta_cand_2022" in c for c in rodar.gov.chamadas)
    rodar()
    assert sum("consulta_cand_2022" in c for c in rodar.gov.chamadas) == n


@pytest.mark.parametrize("bruto,certo", [
    ("JOSÉ DA SILVA", "José da Silva"), ("SANTA BÁRBARA D'OESTE", "Santa Bárbara d'Oeste"),
    ("DOM PEDRO II", "Dom Pedro II"), ("DA COSTA E SILVA", "Da Costa e Silva"), ("EMBU-GUAÇU", "Embu-Guaçu"),
])
def test_nome_proprio(bruto, certo):
    assert R.nome_proprio(bruto) == certo


def test_verificar_prefeito_no_site_de_resultados(rodar):
    import random

    from sa_etl.verificar import Prazo, prefeito_resultado
    pasta = rodar()
    camp = ler(pasta / "m" / "62910.json")["prefeito"]["sq"]
    pedidos = []

    def buscar(url, **kw):
        pedidos.append(url)
        if "sp62910" in url:
            return {"cand": [{"nm": "DARIO", "sqcand": camp, "e": "s", "st": "Eleito"}, {"nm": "OUTRO", "sqcand": "1", "e": "n"}]}
        if "sp70670" in url:
            return {"cand": [{"nm": "OUTRA PESSOA", "sqcand": "999", "e": "s"}]}
        raise RuntimeError("404")
    c = prefeito_resultado(pasta.parent, random.Random(1), Prazo(1), buscar)
    # São Paulo e Belo Horizonte (2º turno) e a cidade com suplementar ficam de fora da amostra
    assert all("71072" not in u and "41238" not in u and "40000" not in u for u in pedidos)
    assert c.n == 2 and c.k == 1 and c.divergencias[0]["o_que"].startswith("Prefeito de Santa Bárbara")
