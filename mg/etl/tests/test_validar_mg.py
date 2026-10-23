"""A conferência de MG pega dado errado? Estragamos de propósito um arquivo bom, um defeito por vez
(teste de mutação do próprio validador)."""
import json

import pytest

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE
from mg_etl import build, cidades
from mg_etl import validar as V
from sa_etl import emendas as emendas_nac


@pytest.fixture(scope="module")
def boa_base(tmp_path_factory, nacional):
    from fakeestado import FakeEstado, instalar
    from mg_etl import almg
    tmp = tmp_path_factory.mktemp("mg_boa")
    fake = FakeEstado()
    fake.emendas_federais_zip(emendas_nac.zip_no_cache(tmp / "nac"))
    with pytest.MonkeyPatch.context() as mp:
        instalar(mp, fake)
        mp.setattr(cidades.tse, "anos_ate", lambda hoje=None: ([2016, 2020, 2024], [2018, 2022]))
        mp.setattr(almg, "ORCAMENTO_VERBA", 100_000)
        build.montar(nacional, tmp / "mg", tmp / "cache", CIDADES_TESTE, cache_nacional=tmp / "nac")
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


def _dep(fn):
    return lambda s: _mudar(s, "almg/d/20003.json", fn)


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
    # estado
    "verba que não soma por tipo": _dep(lambda d: d["anos"]["2025"]["verba"]["tipos"][0].update(valor=1)),
    "verba que não soma por mês": _dep(lambda d: d["anos"]["2025"]["verba"]["meses"].pop(0)),
    "nota com valor negativo": _dep(lambda d: d["anos"]["2025"]["verba"]["notas"][0].update(valor=-5)),
    "resumo da verba diferente": _dep(lambda d: d["por_ano"]["2025"].update(verba=1)),
    "mais aprovados que projetos": _dep(lambda d: d["anos"]["2025"]["proposicoes"].update(aprovadas=99)),
    "CPF no lugar do CNPJ do fornecedor": _dep(lambda d: d["anos"]["2025"]["verba"]["fornecedores"][0].update(cnpj="52998224725")),
    "CPF no nome do fornecedor": _dep(lambda d: d["anos"]["2025"]["verba"]["notas"][0].update(fornecedor="Jose 529.982.247-25")),
    "arquivo do deputado faltando": lambda s: (s / "almg" / "d" / "20003.json").unlink(),
    "deputado repetido": lambda s: _mudar(s, "almg/deputados.json", lambda x: x["deputados"].append(x["deputados"][0])),
    "id de deputado inseguro": lambda s: _mudar(s, "almg/deputados.json", lambda x: x["deputados"][0].update(id="../x")),
    "emendas por deputado acima do total": lambda s: _mudar(s, "estado/emendas.json", lambda x: x["anos"]["2024"].update(indicado=1)),
    "CPF na descrição da emenda": lambda s: _mudar(s, "cidades/dinheiro/itajuba.json",
                                                   lambda x: x["estaduais"]["lista"][0].update(descricao="para 52998224725")),
    "governador não é o eleito": lambda s: _mudar(s, "estado/governo.json", lambda x: x["eleicoes"][0]["governador"].update(nome="Outro")),
    "salário negativo": lambda s: _mudar(s, "estado/governo.json", lambda x: x["equipe"]["pessoas"][0].update(liquido=-1)),
    "contas da prefeitura que não somam": lambda s: _mudar(s, "cidades/dinheiro/itajuba.json",
                                                           lambda x: x["contas"]["anos"][0].update(total_liquidado=1)),
    "pessoa física com nome": lambda s: _mudar(s, "cidades/dinheiro/itajuba.json",
                                               lambda x: [f.update(nome="Maria de Tal") for f in x["federais"]["favorecidos"] if not f["cnpj"]]),
    "link de favorecido de outro site": lambda s: _mudar(s, "cidades/dinheiro/itajuba.json",
                                                         lambda x: x["federais"]["favorecidos"][0].update(url="https://exemplo.com/x")),
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
