"""Número oficial: cada diferença tem um motivo, o site usa o número oficial, e diferença sem motivo barra a publicação."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from sa_etl import cnpj, oficial, senado
from sa_etl import verificar as vf


# ---------------------------------------------------------------- classificar

def test_motivos_tem_texto_para_o_site():
    for mid, m in {**oficial.MOTIVOS, "sem_motivo": oficial.SEM_MOTIVO}.items():
        assert m["titulo"] and m["explica"] and m["decisao"], mid
        assert isinstance(m["corrigido"], bool)


def test_senado_sem_tipo_explica_a_diferenca():
    item = {"site": 1_000.0, "oficial": 900.0, "sem_tipo": 100.0}
    assert oficial.classificar("cota_senado_ano", item) == "senado_sem_tipo"
    # se a diferença não é a soma das notas sem tipo, não sabemos o motivo
    assert oficial.classificar("cota_senado_ano", {**item, "oficial": 800.0}) is None
    assert oficial.classificar("cota_senado_ano", {"site": 1_000.0, "oficial": 900.0}) is None


def test_placar_do_painel_e_receita():
    assert oficial.classificar("placar_senado_ata", {"painel_difere_da_ata": True}) == "senado_painel_ata"
    assert oficial.classificar("placar_senado_ata", {}) is None
    base = {"oficial_normalizado": "X|A"}
    assert oficial.classificar("empresas_receita", {**base, "minha_receita_agora": "X|A"}) == "receita_copia_antiga"
    assert oficial.classificar("empresas_receita", {**base, "minha_receita_agora": "X|B"}) == "receita_meses_diferentes"
    assert oficial.classificar("empresas_receita", base) is None


def test_checagem_conta_sem_motivo_e_fica_explicada():
    c = vf.Checagem("cota_senado_ano", "cota", "t", "c", "f")
    c.bateu(True, {"site": 1, "oficial": 1})
    c.bateu(False, {"o_que": "x", "site": 1_000.0, "oficial": 900.0, "sem_tipo": 100.0, "fonte": "https://a"})
    assert c.status == "explicado" and c.sem_motivo == 0
    assert c.divergencias[0]["motivo"] == "senado_sem_tipo"
    c.bateu(False, {"o_que": "y", "site": 1_000.0, "oficial": 1.0, "fonte": "https://a"})
    assert c.status == "divergente" and c.sem_motivo == 1
    assert c.divergencias[1]["motivo"] is None


# ---------------------------------------------------------------- barreira

def _checagem(n: int, sem_motivo: int, secao="votacoes") -> vf.Checagem:
    c = vf.Checagem("votos_camara", secao, "t", "c", "f")
    for i in range(n):
        c.bateu(i >= sem_motivo, {"o_que": str(i), "site": "Sim", "oficial": "Não", "fonte": "https://a"})
    return c


def test_barra_com_diferencas_sem_motivo_demais():
    s = vf.resumo_secoes([_checagem(100, 3)], {}, "2026-10-28")
    assert s["votacoes"]["barrar"] is True and s["votacoes"]["hoje"]["sem_motivo"] == 3
    s = vf.resumo_secoes([_checagem(100, 2)], {}, "2026-10-28")  # 2% ainda passa
    assert "barrar" not in s["votacoes"]
    s = vf.resumo_secoes([_checagem(10, 5)], {}, "2026-10-28")  # amostra pequena demais para barrar
    assert "barrar" not in s["votacoes"] and s["votacoes"]["status"] == "divergente"


def test_main_devolve_3_quando_barra(tmp_path, monkeypatch):
    def falso(saida, *a, **k):
        return {"secoes": {}, "checagens": [], "barradas": ["votacoes"], "limite_sem_motivo": 0.02}
    monkeypatch.setattr(vf, "verificar", falso)
    monkeypatch.setattr(vf, "relatorio", lambda v: "")
    assert vf.main([str(tmp_path)]) == 3
    assert vf.main([str(tmp_path), "--ignorar-barreira"]) == 0
    assert json.loads((tmp_path / "verificacao.json").read_text())["barradas"] == ["votacoes"]


# ---------------------------------------------------------------- empresas: cópia antiga sai do cache

def test_empresa_diferente_consulta_de_novo_e_limpa_o_cache(tmp_path):
    saida, cache = tmp_path / "data", tmp_path / "cache"
    (saida / "e").mkdir(parents=True)
    cache.mkdir()
    c14 = "12345678000199"
    (saida / "empresas.json").write_text(json.dumps([{"cnpj": c14}]))
    (saida / "e" / f"{c14}.json").write_text(json.dumps(
        {"nome": "Loja", "empresa": {"razao_social": "LOJA LTDA"}, "socios": [{"nome": "Ana"}]}))
    (cache / f"{c14}.json").write_text("{}")

    def buscar(url, timeout=None, **k):
        if "brasilapi" in url:
            return {"razao_social": "LOJA LTDA", "qsa": [{"nome_socio": "Bruno"}]}
        if "minhareceita" in url:
            return {"razao_social": "LOJA LTDA", "qsa": [{"nome_socio": "Bruno"}]}
        raise AssertionError(url)

    c = vf.empresas_receita(saida, __import__("random").Random(1), vf.Prazo(1), buscar, cache)
    assert c.k == 1 and c.divergencias[0]["motivo"] == "receita_copia_antiga"
    assert not (cache / f"{c14}.json").exists()


def test_cache_de_cnpj_vence(tmp_path, monkeypatch):
    c14 = "12345678000190"  # termina em 0: prazo de 30 dias
    f = tmp_path / f"{c14}.json"
    f.write_text(json.dumps({"razao_social": "ANTIGA"}))
    pedidos = []

    class R:
        def json(self):
            return {"razao_social": "NOVA", "cnpj": c14}

    def get(url, **k):
        pedidos.append(url)
        return R()
    monkeypatch.setattr(cnpj, "get", get)
    assert cnpj._fetch(c14, tmp_path)["razao_social"] == "ANTIGA" and not pedidos  # recente: usa o cache
    velho = time.time() - 31 * 86400
    os.utime(f, (velho, velho))
    assert cnpj._fetch(c14, tmp_path)["razao_social"] == "NOVA" and pedidos

    def cai(url, **k):
        raise RuntimeError("fora do ar")
    monkeypatch.setattr(cnpj, "get", cai)
    os.utime(f, (velho, velho))
    assert cnpj._fetch(c14, tmp_path)["razao_social"] == "NOVA"  # sem resposta, fica a cópia que já tínhamos


# ---------------------------------------------------------------- Senado: número oficial na coleta

def test_nota_sem_tipo_fica_fora_do_total_oficial():
    rows = [{"codSenador": "1", "ano": "2025", "mes": "3", "valorReembolsado": "100", "tipoDespesa": ""},
            {"codSenador": "1", "ano": "2025", "mes": "3", "valorReembolsado": "50", "tipoDespesa": "Passagens aéreas"}]
    a, b = senado.parse_ceaps(rows, {"sen-1"})
    assert a["fora_total_oficial"] == "senado_sem_tipo" and "fora_total_oficial" not in b


def test_placar_da_ata_vale_sobre_o_painel():
    item = {"codigoSessaoVotacao": 1, "votacaoSecreta": "N", "dataSessao": "2025-05-21",
            "informeLegislativo": {"texto": "Aprovado, com o seguinte resultado: Sim - 2; Não - 0; Total - 2."},
            "votos": [{"codigoParlamentar": 1, "siglaVotoParlamentar": "Sim"},
                      {"codigoParlamentar": 2, "siglaVotoParlamentar": "Sim"},
                      {"codigoParlamentar": 3, "siglaVotoParlamentar": "Não"}]}
    vs, _ = senado.parse_votacoes([item], {"sen-1"})
    assert vs[0]["placar_oficial"] == {"sim": 2, "nao": 0, "fonte": "ata", "painel": {"sim": 2, "nao": 1}}
    # ata igual ao painel: sem marca
    item["informeLegislativo"]["texto"] = "Sim - 2; Não - 1; Total - 3."
    vs, _ = senado.parse_votacoes([item], {"sen-1"})
    assert vs[0]["placar_oficial"] == {"sim": 2, "nao": 1}


def test_verificacao_publica_os_motivos(tmp_path):
    v = vf.verificar(Path(tmp_path), hoje=__import__("datetime").date(2026, 10, 28), chave="", buscar=lambda *a, **k: {},
                     minutos=0.01)
    assert "senado_sem_tipo" in v["motivos"] and "sem_motivo" in v["motivos"]
    assert v["barradas"] == []
