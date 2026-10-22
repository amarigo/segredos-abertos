"""A conferência de MG pega dado errado? Estragamos de propósito um arquivo bom, um defeito por vez
(teste de mutação do próprio validador)."""
import json

import pytest

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE
from mg_etl import build, cidades
from mg_etl import validar as V


@pytest.fixture(scope="module")
def boa_base(tmp_path_factory, nacional):
    from faketse import FakeTSE, instalar
    tmp = tmp_path_factory.mktemp("mg_boa")
    with pytest.MonkeyPatch.context() as mp:
        instalar(mp, FakeTSE())
        mp.setattr(cidades.tse, "anos_ate", lambda hoje=None: ([2016, 2020, 2024], [2022]))
        build.montar(nacional, tmp / "mg", tmp / "cache", CIDADES_TESTE)
    return tmp / "mg"


@pytest.fixture
def boa(boa_base, tmp_path):
    import shutil
    destino = tmp_path / "mg"
    shutil.copytree(boa_base, destino)
    assert V.validar(destino, minimos=MINIMOS_TESTE).erros == []
    return destino


def _mudar(saida, rel, fn):
    f = saida / rel
    x = json.loads(f.read_text(encoding="utf-8"))
    fn(x)  # muda no lugar; o que a função devolve não importa
    f.write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")


def _ita(fn):
    return lambda s: _mudar(s, "cidades/itajuba.json", fn)


def _cam0(fn):
    return _ita(lambda d: fn(d["camara"][0]))


def _exe0(fn):
    return _ita(lambda d: fn(d["executivo"][0]))


def _primeira_votacao(s):
    return json.loads((s / "votacoes.json").read_text())[0]["id"]


DEFEITOS = {
    "político de outro estado": lambda s: _mudar(s, "politicos.json", lambda x: x[0].update(uf="SP")),
    "placar da Casa menor que o de MG": lambda s: _mudar(s, "votacoes.json", lambda x: x[0]["placar_casa"].update(sim=-1)),
    "votação sem placar da Casa": lambda s: _mudar(s, "votacoes.json", lambda x: x[0].pop("placar_casa")),
    "cidade repetida": lambda s: _mudar(s, "cidades.json", lambda x: x.append(x[0])),
    "id de cidade inseguro": lambda s: _mudar(s, "cidades.json", lambda x: x[0].update(id="../../etc")),
    "eleição de prefeito repetida": _ita(lambda d: d["executivo"].append(d["executivo"][0])),
    "eleições fora de ordem": _ita(lambda d: d["executivo"].reverse()),
    "mandato de 5 anos": _exe0(lambda m: m.update(fim=m["fim"] + 1)),
    "percentual acima de 100": _exe0(lambda m: m["candidatos"][0].update(pct=130)),
    "percentuais não somam 100": _exe0(lambda m: m["candidatos"][1].update(pct=m["candidatos"][1]["pct"] + 10)),
    "dois eleitos para prefeito": _exe0(lambda m: [c.update(eleito=True) for c in m["candidatos"]]),
    "eleito diferente do prefeito": _exe0(lambda m: m["prefeito"].update(nome="Outro")),
    "cadeiras não somam as vagas": _cam0(lambda c: c["por_partido"][0].update(cadeiras=c["por_partido"][0]["cadeiras"] + 1)),
    "eleito a mais na lista": _cam0(lambda c: c["eleitos"].append(c["eleitos"][0])),
    "coligação com mais cadeiras que vagas": _cam0(lambda c: c.update(da_coligacao_do_prefeito=c["vagas"] + 1)),
    "partido repetido na Câmara": _cam0(lambda c: (c["por_partido"].append({**c["por_partido"][0], "cadeiras": 0}))),
    "resumo com anos errados": _ita(lambda d: d["resumo"]["anos_por_partido"][0].update(anos=99)),
    "resumo com cadeiras erradas": _ita(lambda d: d["resumo"]["cadeiras_por_partido"][0].update(cadeiras=99)),
    "resumo com mandatos errados": _ita(lambda d: d["resumo"].update(mandatos=99)),
    "mais votados acima do total": _ita(lambda d: d["gerais"][0]["cargos"][0].update(total_votos=1)),
    "CPF aberto numa cidade": _ita(lambda d: d["executivo"][0]["prefeito"].update(cpf="12345678909")),
    "link javascript na cidade": _ita(lambda d: d["links"].append({"nome": "x", "url": "javascript:alert(1)"})),
    "arquivo da cidade faltando": lambda s: (s / "cidades" / "itajuba.json").unlink(),
    "poucos mandatos": _ita(lambda d: d.update(executivo=[])),
    "cidade em formato errado": lambda s: (s / "cidades" / "itajuba.json").write_text("[1, 2]", encoding="utf-8"),
    "prefeito sem nome": _exe0(lambda m: m.pop("prefeito")),
}


@pytest.mark.parametrize("nome", DEFEITOS)
def test_conferencia_pega_o_defeito(boa, nome):
    DEFEITOS[nome](boa)
    minimos = {**MINIMOS_TESTE, "mandatos": 2} if nome == "poucos mandatos" else MINIMOS_TESTE
    assert V.validar(boa, minimos=minimos).erros, nome


def test_votos_com_queda_brusca_bloqueiam(boa):
    meta = json.loads((boa / "meta.json").read_text())
    anterior = {**meta, "contagens": {**meta["contagens"], "politicos": meta["contagens"]["politicos"] * 3}}
    assert any("Queda" in e for e in V.validar(boa, minimos=MINIMOS_TESTE, anterior=anterior).erros)
    assert not V.validar(boa, minimos=MINIMOS_TESTE, anterior=anterior, ignorar_queda=True).erros


def test_linha_de_comando(boa, capsys):
    assert V.main([str(boa)]) == 1  # mínimos de produção: os dados de teste são pequenos demais
    assert "Poucos parlamentares" in capsys.readouterr().out
