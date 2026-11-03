"""Emendas Pix no Transferegov: plano de ação, executor, metas e os pagamentos feitos pela prefeitura."""
import datetime as dt
import json

import pytest

from fakegov import FakeGov, instalar
from sa_etl import transferegov, util


@pytest.fixture
def gov(monkeypatch):
    return instalar(monkeypatch, FakeGov(anos=(2025,)))


def _ler(f):
    return json.loads(f.read_text())


def test_coleta_grava_lista_e_detalhe(gov, tmp_path):
    res = transferegov.executar([2025], tmp_path / "cache", tmp_path / "saida", minutos=5)
    assert res and 2025 in res
    idx = _ler(tmp_path / "saida/emendas/destino/2025.json")
    assert idx["completo"] and idx["fonte"].startswith("https://")
    assert idx["n"] == 4  # deputados 0, 3, 6 e 9 têm emenda Pix
    assert idx["emendas"] == {str(202500 + i): "46395000000139" for i in (0, 3, 6, 9)}
    sp = idx["beneficiarios"][0]
    assert sp["cnpj"] == "46395000000139" and sp["uf"] == "SP" and sp["valor"] == 4000.0
    # o mesmo pagamento em dois relatórios conta uma vez só: 300 + 100 + 50 por emenda
    assert sp["gasto"] == 4 * 450.0 and sp["n_gastos"] == 12
    det = _ler(tmp_path / "saida/emendas/destino/2025/46395000000139.json")
    p = next(x for x in det["planos"] if x["emenda"] == "202503")
    assert p["objeto"] == "Pavimentação da Rua 3 e compra de ambulância" and p["valor"] == 1000.0
    assert p["parlamentar"] == "DEPUTADO FICTICIO 03" and p["situacao"] == "Ciente"
    e = p["executores"][0]
    assert e["objeto"] == "Pavimentação da Rua 3" and e["executado"] == 450.0 and e["relatorio"] == "2025-12-31"
    assert e["metas"] == [{"nome": "Pavimentar ruas", "descricao": "Asfalto novo na Rua 3", "quantidade": 1200.0,
                           "unidade": "m²", "valor": 1000.0}]
    assert p["gasto"] == 450.0 and [g["recebedor"] for g in p["gastos"]] == ["FULANO DA SILVA", "AMBULANCIAS Y SA", "OBRAS X LTDA"]
    assert det["recebedores"][0] == {"nome": "OBRAS X LTDA", "cnpj": "12345678000195", "pessoa": False, "valor": 1200.0, "n": 4}


def test_nao_publica_cpf_nem_conta_bancaria(gov, tmp_path):
    transferegov.executar([2025], tmp_path / "cache", tmp_path / "saida", minutos=5)
    texto = (tmp_path / "saida/emendas/destino/2025/46395000000139.json").read_text()
    assert "456.789" not in texto and "456789" not in texto  # nem o pedaço do CPF que a API mostra
    assert "99999-9" not in texto  # a conta bancária da prefeitura não vai para o site
    det = json.loads(texto)
    pf = next(g for p in det["planos"] for g in p["gastos"] if g["pessoa"])
    assert pf["cnpj"] == ""


def test_continua_de_onde_parou(gov, tmp_path, monkeypatch):
    """Com pouco tempo, a leitura para no meio e continua na execução seguinte, sem repetir páginas."""
    monkeypatch.setattr(transferegov, "TAMANHO", 1)
    cache = tmp_path / "cache"
    relogio = iter(range(0, 10_000, 1))
    monkeypatch.setattr(transferegov, "_agora", lambda: next(relogio))
    rodadas = 0
    while True:
        rodadas += 1
        t = transferegov.coletar([2025], cache, minutos=5 / 60)  # 5 "segundos" (consultas ao relógio) por rodada
        if t and not t["falta"]:
            break
        assert rodadas < 200
    assert rodadas > 3
    assert len(t["planos"][2025]["linhas"]) == 4 and len(t["metas"]["linhas"]) == 4
    antes = gov.transferegov.pedidos
    t = transferegov.coletar([2025], cache, minutos=5)  # tudo no cache e dentro da validade: nenhum pedido
    assert gov.transferegov.pedidos == antes and not t["falta"]


def test_tabela_vencida_e_lida_de_novo(gov, tmp_path):
    cache = tmp_path / "cache"
    transferegov.coletar([2025], cache, minutos=5, hoje=dt.date(2026, 1, 1))
    antes = gov.transferegov.pedidos
    transferegov.coletar([2025], cache, minutos=5, hoje=dt.date(2026, 1, 3))
    assert gov.transferegov.pedidos == antes
    transferegov.coletar([2025], cache, minutos=5, hoje=dt.date(2026, 1, 9))
    assert gov.transferegov.pedidos > antes


def test_api_fora_do_ar_usa_ultima_leitura(gov, tmp_path):
    cache = tmp_path / "cache"
    transferegov.coletar([2025], cache, minutos=5, hoje=dt.date(2026, 1, 1))
    gov.falhar("transferegov", "500")
    util.AVISOS.clear()
    res = transferegov.executar([2025], cache, tmp_path / "saida", minutos=5)
    assert res and res[2025]["beneficiarios"]["46395000000139"]["gasto"] == 1800.0
    assert any("Transferegov" in a for a in util.AVISOS)


def test_sem_leitura_nenhuma_avisa_e_nao_grava(gov, tmp_path):
    gov.falhar("transferegov", "500")
    util.AVISOS.clear()
    assert transferegov.executar([2025], tmp_path / "cache", tmp_path / "saida", minutos=5) is None
    assert not (tmp_path / "saida/emendas/destino").exists()
    assert any("Transferegov" in a for a in util.AVISOS)


def test_ano_errado_fica_de_fora(gov, tmp_path):
    """Se a API ignorar o filtro de ano (ela ignora em silêncio filtro desconhecido), o resumo confere o ano."""
    for p in gov.transferegov.tabelas["planos-acao-especiais"][:1]:
        p["ano_emenda_parlamentar_plano_acao"] = 2019
    res = transferegov.executar([2025], tmp_path / "cache", tmp_path / "saida", minutos=5)
    assert sum(len(b["planos"]) for b in res[2025]["beneficiarios"].values()) == 3


def test_codigo_da_emenda():
    assert transferegov.codigo_emenda({"codigo_emenda_parlamentar_formatado_plano_acao": "2025.4415.0001"}) == "202544150001"
    assert transferegov.codigo_emenda({"ano_emenda_parlamentar_plano_acao": 2025, "codigo_parlamentar_emenda_plano_acao": 4415,
                                       "numero_emenda_parlamentar_plano_acao": 1}) == "202544150001"
