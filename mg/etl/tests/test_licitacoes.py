"""Licitações e contratações diretas (PNCP): cidade e estado, com e sem licitação, quem recebeu, em que pé está.

Os dados vêm do PNCP simulado (FakeEstado.pncp), no formato real conferido na sondagem de 08/11/2026: HTTP 204 sem
corpo quando não há nada no período, no máximo 50 linhas por página, compras de órgãos federais e estaduais
dentro da cidade, fornecedor pessoa física com CPF no nome.
"""
import datetime as dt
import json

import pytest

from apoio_mg import CIDADES_TESTE, MINIMOS_TESTE
from fakeestado import CPF_EMITENTE
from mg_etl import pncp
from mg_etl.validar import Resultado, conferir_licitacoes
from sa_etl import util

HOJE = dt.date(2026, 11, 8)
CPF_FORMATOS = [CPF_EMITENTE, f"{CPF_EMITENTE[:3]}.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-{CPF_EMITENTE[9:]}"]


def _json(f):
    return json.loads(f.read_text(encoding="utf-8"))


def _coletar(tmp_path, minutos=5, cache=None):
    saida = tmp_path / "saida"
    cont = pncp.coletar(saida, cache or tmp_path / "cache", CIDADES_TESTE, anos=[2025, 2026], minutos=minutos, hoje=HOJE)
    return saida, cont


@pytest.mark.parametrize("mod,forma", [(6, "licitacao"), (4, "licitacao"), (8, "dispensa"), (9, "inexigibilidade"), (12, "outro"), (14, "outro")])
def test_forma_da_compra(mod, forma):
    assert pncp.forma(mod) == forma


@pytest.mark.parametrize("compra,contratos,esperado", [
    ({"situacao": 2}, [], "Revogada"),
    ({"situacao": 3, "homologado": 10}, [], "Anulada"),
    ({"situacao": 1, "homologado": 10}, [{"fim": "2026-01-01"}], "Contrato encerrado"),
    ({"situacao": 1, "homologado": 10}, [{"fim": "2027-01-01"}], "Contrato em vigor"),
    ({"situacao": 1, "homologado": 10}, [], "Concluída, sem contrato no PNCP"),
    ({"situacao": 1, "homologado": 0}, [], "Sem resultado publicado"),
])
def test_andamento(compra, contratos, esperado):
    assert pncp.andamento(compra, contratos, HOJE) == esperado


def test_cidade_so_orgaos_municipais_com_e_sem_licitacao(estado, tmp_path):
    saida, cont = _coletar(tmp_path)
    d = _json(saida / "licitacoes" / "itajuba-2025.json")
    assert d["completo"] and d["faltam"] == []
    assert d["total"]["n"] == estado.esperado["licitacoes_itajuba_2025"], "a universidade federal e a escola estadual ficam de fora"
    assert {c["orgao"] for c in d["compras"]} == {"Municipio de Itajuba"}
    formas = {f["forma"]: f for f in d["por_forma"]}
    assert formas["licitacao"]["n"] == 2 and formas["dispensa"]["n"] == 1 and formas["inexigibilidade"]["n"] == 1
    assert formas["licitacao"]["homologado"] == 800000.0, "a compra revogada não entra no valor"
    asfalto = next(c for c in d["compras"] if c["objeto"].startswith("Asfalto"))
    assert asfalto["andamento"] == "Contrato em vigor" and asfalto["contratos"][0]["fornecedor"] == "Asfaltos Minas Ltda"
    assert asfalto["url"] == "https://pncp.gov.br/app/editais/18025940000109/2025/1"
    assert asfalto["contratos"][0]["url"] == "https://pncp.gov.br/app/contratos/18025940000109/2025/1"
    show = next(c for c in d["compras"] if c["forma"] == "inexigibilidade")
    assert show["amparo"] == "Lei 14.133/2021, Art. 74, II" and show["andamento"] == "Contrato encerrado"
    assert show["contratos"][0]["fornecedor"] == "Pessoa física" and show["contratos"][0]["cnpj"] == ""
    assert {a["nome"] for a in d["amparos"]} == {"Lei 14.133/2021, Art. 75, II", "Lei 14.133/2021, Art. 74, II"}
    assert d["fornecedores"][0] == {"nome": "Asfaltos Minas Ltda", "cnpj": "11222333000181", "valor": 800000.0, "n": 1}
    # Câmara municipal também é da cidade; Paraisópolis não publicou nada: o arquivo existe com zero, não some
    assert _json(saida / "licitacoes" / "itajuba-2026.json")["total"]["n"] == 1
    assert _json(saida / "licitacoes" / "paraisopolis-2025.json")["total"]["n"] == 0, "compra de outra cidade com o mesmo código fica fora"
    assert util.AVISOS == []


def test_estado_so_orgaos_estaduais_e_varias_paginas(estado, tmp_path):
    saida, _ = _coletar(tmp_path)
    assert not (saida / "licitacoes" / "estado-2025.json").exists(), "o estado é lido só no ano atual (volume da API)"
    d26 = _json(saida / "licitacoes" / "estado-2026.json")
    assert d26["total"]["n"] == 62, "60 compras num mês (duas páginas), a merenda da escola estadual em Itajubá e a reforma"
    assert d26["compras"][0]["contratos"][0]["fornecedor"] == "Construtora Escolar Ltda"
    idx = _json(saida / "licitacoes" / "index.json")
    assert [x["id"] for x in idx["locais"]] == ["itajuba", "paraisopolis", "estado"]


def test_nenhum_cpf_e_conferencia_passa(estado, tmp_path):
    saida, _ = _coletar(tmp_path)
    texto = "".join(f.read_text(encoding="utf-8") for f in (saida / "licitacoes").glob("*.json"))
    assert not any(c in texto for c in CPF_FORMATOS)
    assert "CANTOR FULANO" not in texto.upper(), "pessoa física aparece sem nome"
    r = Resultado()
    conferir_licitacoes(saida, r)
    assert r.erros == []


def test_sem_tempo_continua_na_proxima_execucao(estado, tmp_path, monkeypatch):
    """Com o tempo acabando no meio, o que foi lido fica no cache, o site avisa, e a execução seguinte completa."""
    relogio = iter(range(0, 10_000, 7))
    monkeypatch.setattr(pncp, "_agora", lambda: next(relogio))
    cache = tmp_path / "cache"
    saida, _ = _coletar(tmp_path, minutos=1, cache=cache)  # 60 s: só alguns pedidos
    idx = _json(saida / "licitacoes" / "index.json")
    assert any(not a["completo"] for x in idx["locais"] for a in x["anos"]) or not idx["locais"]
    assert any("leitura ainda em andamento" in a for a in util.AVISOS) or not idx["locais"]
    for _ in range(60):
        util.AVISOS.clear()
        relogio = iter(range(0, 100_000, 7))
        saida, _ = _coletar(tmp_path, minutos=10, cache=cache)
        idx = _json(saida / "licitacoes" / "index.json")
        if len(idx["locais"]) == 3 and all(a["completo"] for x in idx["locais"] for a in x["anos"]):
            break
    else:
        pytest.fail("a leitura aos poucos nunca terminou")
    assert _json(saida / "licitacoes" / "estado-2026.json")["total"]["n"] == 62


@pytest.mark.parametrize("modo", ["fora", "500", "429", "html"])
def test_pncp_fora_do_ar_usa_a_ultima_leitura(estado, tmp_path, monkeypatch, modo):
    cache = tmp_path / "cache"
    _coletar(tmp_path, cache=cache)
    antes = _json(tmp_path / "saida" / "licitacoes" / "itajuba-2025.json")
    util.AVISOS.clear()
    estado.falhar("pncp.gov.br", modo)
    saida, _ = _coletar(tmp_path, cache=cache, minutos=5)
    # no mesmo dia, a leitura ainda vale: nem pergunta ao PNCP
    assert _json(saida / "licitacoes" / "itajuba-2025.json")["total"] == antes["total"]
    # dias depois, o PNCP fora do ar: fica a última leitura e o site avisa
    util.AVISOS.clear()
    saida = tmp_path / "saida2"
    pncp.coletar(saida, cache, CIDADES_TESTE, anos=[2025, 2026], minutos=5, hoje=HOJE + dt.timedelta(days=20))
    assert _json(saida / "licitacoes" / "itajuba-2025.json")["total"] == antes["total"]
    assert any("PNCP" in a and "não respondeu" in a for a in util.AVISOS)


def test_pncp_fora_do_ar_sem_copia_nao_mostra_zero(estado, tmp_path):
    estado.falhar("pncp.gov.br", "fora")
    saida, cont = _coletar(tmp_path)
    assert cont == {}, "sem nenhuma leitura, nenhum ano aparece como se fosse zero"
    assert _json(saida / "licitacoes" / "index.json")["locais"] == []
    assert any("PNCP" in a for a in util.AVISOS)


def test_numero_de_11_digitos_colado_num_ponto_some_antes_de_gravar(estado, tmp_path):
    """Caso real (Itajubá 2025): um objeto com 11 dígitos colados num ponto passou pela limpeza da leitura, ficou no
    cache e a conferência barrou o Minas Nossa inteiro. A limpeza final, na hora de gravar, usa o padrão da conferência."""
    import gzip

    cache = tmp_path / "cache"
    _coletar(tmp_path, cache=cache)
    mexidos = 0
    for f in (cache / "pncp").rglob("*.gz"):
        st = json.loads(gzip.decompress(f.read_bytes()))
        for c in st.get("linhas") or []:
            if "objeto" in c:
                c["objeto"] = "AQUISIÇÃO DE MEDICAMENTOS, processo 12345678901. Lote 1"
                mexidos += 1
        f.write_bytes(gzip.compress(json.dumps(st, ensure_ascii=False).encode()))
    assert mexidos
    saida, _ = _coletar(tmp_path, cache=cache)  # no mesmo dia: usa o cache, sem perguntar de novo ao PNCP
    texto = "".join(f.read_text(encoding="utf-8") for f in (saida / "licitacoes").glob("*.json"))
    assert "12345678901" not in texto and "AQUISIÇÃO DE MEDICAMENTOS" in texto
    r = Resultado()
    conferir_licitacoes(saida, r)
    assert r.erros == []
