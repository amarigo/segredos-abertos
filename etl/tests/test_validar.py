"""A conferência pega dado errado? Estragamos de propósito arquivos bons, um defeito por vez,
e a conferência tem de apontar cada um (teste de mutação do próprio validador)."""
import json
import shutil

import pytest

from fakegov import FakeGov
from sa_etl import validar as V


@pytest.fixture
def boa(coleta, tmp_path):
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []
    return saida, coleta


def _mudar(saida, rel, fn):
    f = saida / rel
    x = json.loads(f.read_text(encoding="utf-8"))
    x = fn(x) or x
    f.write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")


def _primeiro(saida, pasta, casa=None):
    return sorted((saida / pasta).glob(f"{casa or ''}*.json"))[0].stem


def _da_cota(saida):
    """Uma empresa paga pela cota (há também as que só aparecem por emendas ou pela página de incentivos)."""
    return json.loads((saida / "empresas.json").read_text())[0]["cnpj"]


def _com(saida, chave):
    for f in sorted((saida / "e").glob("*.json")):
        if json.loads(f.read_text()).get(chave):
            return f.stem
    raise AssertionError(f"nenhuma empresa com {chave}")


def _empresa_com_holding(saida):
    for f in sorted((saida / "e").glob("*.json")):
        x = json.loads(f.read_text())
        if any(d["cadeia"] and d["fim"] == "pessoa" for d in x.get("donos_finais") or []):
            return f.stem
    raise AssertionError("sem empresa com holding")


DEFEITOS = {
    "total do parlamentar": lambda s: _mudar(s, "politicos.json", lambda x: x[0].update(total=x[0]["total"] + 10)),
    "grupos não somam": lambda s: _mudar(s, "politicos.json", lambda x: x[0]["por_ano"]["2025"]["grupos"].update(pessoal=-1)),
    "meta.total_gasto": lambda s: _mudar(s, "meta.json", lambda x: x.update(total_gasto=1)),
    "parlamentar repetido": lambda s: _mudar(s, "politicos.json", lambda x: x.append(x[0])),
    "votação repetida": lambda s: _mudar(s, "votacoes.json", lambda x: x.append(x[0])),
    "voto duplicado": lambda s: _mudar(s, f"v/{_primeiro(s, 'v', 'cd')}.json", lambda x: x["votos"].append(x["votos"][0])),
    "placar errado": lambda s: _mudar(s, "votacoes.json", lambda x: x[0].update(sim=x[0]["sim"] + 1)),
    "link javascript": lambda s: _mudar(s, "politicos.json", lambda x: x[0].update(foto="javascript:alert(1)")),
    "CPF aberto": lambda s: _mudar(s, f"p/{_primeiro(s, 'p', 'dep')}.json",
                                   lambda x: x["anos"]["2025"]["fornecedores"][0].update(doc="12345678909")),
    "CPF no link": lambda s: _mudar(s, f"p/{_primeiro(s, 'p', 'dep')}.json", lambda x: x["anos"]["2025"]["maiores_notas"][0].update(
        url="https://www.camara.leg.br/cota-parlamentar/documento?cnpjFornecedor=12345678909&x=1")),
    "nota a mais": lambda s: _mudar(s, f"e/notas/{_primeiro(s, 'e/notas')}.json", lambda x: x.append(x[0])),
    "pagadores não somam": lambda s: _mudar(s, f"e/{_da_cota(s)}.json", lambda x: x["pagadores"][0].update(valor=0)),
    "ciclo escondido": lambda s: _mudar(s, f"e/{_empresa_com_holding(s)}.json",
                                        lambda x: [d["cadeia"].append(d["cadeia"][0]) for d in x["donos_finais"] if d["cadeia"]] and None),
    "emendas por tipo": lambda s: _mudar(s, "emendas/2025.json", lambda x: x["por_tipo"][0].update(empenhado=0)),
    "incentivos por categoria": lambda s: _mudar(s, "incentivos/2025.json", lambda x: x["pagamentos"]["por_categoria"][0].update(valor=1)),
    "renúncia por estado": lambda s: _mudar(s, "incentivos/renuncia-2024.json", lambda x: x["por_uf"][0].__setitem__(1, 1)),
    "renúncia na empresa": lambda s: _mudar(s, f"e/{_com(s, 'renuncia')}.json", lambda x: x["renuncia"].update(total=1)),
    "arquivo faltando": lambda s: (s / "partidos.json").unlink(),
    "JSON quebrado": lambda s: (s / "votacoes.json").write_text("[{", encoding="utf-8"),
    "nome de arquivo": lambda s: shutil.copy(s / "meta.json", s / "p" / "x.y.json"),
}


@pytest.mark.parametrize("defeito", list(DEFEITOS))
def test_conferencia_pega_cada_defeito(boa, defeito):
    saida, coleta = boa
    DEFEITOS[defeito](saida)
    assert coleta.validar(saida).erros, f"a conferência não pegou: {defeito}"


def test_queda_brusca_bloqueia(boa):
    saida, coleta = boa
    meta = coleta.ler(saida, "meta.json")
    anterior = {**meta, "total_por_ano": {"2025": meta["total_por_ano"]["2025"] * 2},
                "contagens": {**meta["contagens"], "votacoes": meta["contagens"]["votacoes"] * 3}}
    r = coleta.validar(saida, anterior=anterior)
    assert sum("Queda" in e for e in r.erros) == 2


def test_linha_de_comando(boa, capsys):
    saida, _ = boa
    assert V.main([str(saida)]) == 1  # poucos parlamentares para os mínimos de produção
    assert "Poucos parlamentares" in capsys.readouterr().out
