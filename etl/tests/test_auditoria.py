"""Falhas silenciosas achadas na auditoria de 04/11/2026: cada uma agora deixa aviso no site e no painel de status."""
import gzip
import json
import os
import time

import fakegov_financas as ff
from fakegov import FakeGov, instalar
from sa_etl import build, financas, fin_tesouro, pagamentos, util


def _reiniciar():
    util.AVISOS.clear()
    util.SEM_RETENTATIVA.clear()
    util.reiniciar_quedas()


def test_pagamentos_de_emendas_parados_avisam_com_a_data(tmp_path, monkeypatch):
    """Desde 29/10/2026 o Portal recusa os arquivos diários. A leitura das emendas parava sem aviso nenhum, e a página
    de incentivos dizia que ela "avança a cada atualização"."""
    import datetime as dt
    _reiniciar()
    hoje = dt.date(2025, 3, 10)
    # dias já lidos até 05/03; depois, o Portal recusa
    for d in range(1, 6):
        f = tmp_path / f"202503{d:02d}-v{pagamentos.VERSAO}.json.gz"
        f.write_bytes(gzip.compress(json.dumps({"empenhos": [], "pagamentos": []}).encode()))

    def recusa(dia, dest):
        pagamentos.ULTIMA_FALHA = "HTTP 405, CloudFront"
        return False
    monkeypatch.setattr(pagamentos, "_baixar_dia", recusa)
    monkeypatch.setattr(pagamentos, "FALHAS_PARA_PARAR", 1)
    pagamentos.coletar([2025], tmp_path, hoje=hoje)
    aviso = next(a for a in util.AVISOS if a.startswith("Pagamentos de emendas"))
    assert "HTTP 405" in aviso and "parados em" in aviso
    assert aviso not in util.avisos_para_tentar()  # outra coleta daqui a 2 horas não resolve
    assert pagamentos.recusa_em_curso()
    _reiniciar()
    assert not pagamentos.recusa_em_curso()


def test_queda_passageira_nas_emendas_pede_nova_coleta(tmp_path, monkeypatch):
    import datetime as dt
    _reiniciar()

    def cai(dia, dest):
        pagamentos.ULTIMA_FALHA = "HTTP 500"
        return False
    monkeypatch.setattr(pagamentos, "_baixar_dia", cai)
    pagamentos.coletar([2025], tmp_path, hoje=dt.date(2025, 1, 10))
    aviso = next(a for a in util.AVISOS if a.startswith("Pagamentos de emendas"))
    assert "continua na próxima execução" in aviso and aviso in util.avisos_para_tentar()
    _reiniciar()


def _envelhecer(pasta):
    velho = time.time() - 3 * 24 * 3600
    for f in pasta.rglob("*.json"):
        os.utime(f, (velho, velho))


def test_siconfi_fora_do_ar_usa_a_copia_do_ano_corrente(tmp_path, monkeypatch):
    """Antes, com o Tesouro fora do ar, o ano corrente sumia da aba (e o ano anterior aparecia como o mais recente),
    mesmo com a cópia de ontem guardada."""
    gov = instalar(monkeypatch, FakeGov())
    bim, itens = fin_tesouro.rreo(ff.ANO, "RREO-Anexo 01", tmp_path, ff.ANO)
    _envelhecer(tmp_path)
    financas.AVISOS.clear()
    gov.falhar("apidatalake.tesouro.gov.br", "500")
    antes = len(gov.chamadas)
    r = fin_tesouro.rreo(ff.ANO, "RREO-Anexo 01", tmp_path, ff.ANO)
    assert r == (bim, itens)
    assert any("usa a cópia de" in a and str(ff.ANO) in a for a in financas.AVISOS)
    # depois da primeira falha, os bimestres anteriores só vêm do cache: nada de esperar de novo cada tentativa
    feitas = [c for c in gov.chamadas[antes:] if "apidatalake" in c]
    assert len(feitas) <= 4 * (6 - bim + 1)


def test_siconfi_fora_do_ar_sem_copia_nao_inventa(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov())
    gov.falhar("apidatalake.tesouro.gov.br", "500")
    assert fin_tesouro.rreo(ff.ANO, "RREO-Anexo 01", tmp_path, ff.ANO) is None


def test_avisos_das_etapas_finais_vao_para_o_meta(tmp_path, monkeypatch):
    """Arrecadação e gastos roda depois de montar(): sem a aba, o aviso dela ficava fora do meta.json, e o site e o
    painel de status não mostravam nada."""
    _reiniciar()
    (tmp_path / "meta.json").write_text(json.dumps({"avisos": [], "avisos_tentar": [], "anos": [2025]}), encoding="utf-8")

    def sem_tesouro(saida, cache):
        financas.AVISOS[:] = ["Arrecadação e gastos: o Tesouro Nacional não respondeu; a aba não foi atualizada"]
        return None
    monkeypatch.setattr(financas, "coletar", sem_tesouro)
    build.coletar_financas(tmp_path, tmp_path / "cache")
    build.regravar_avisos(tmp_path)
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["avisos"] == ["Arrecadação e gastos: o Tesouro Nacional não respondeu; a aba não foi atualizada"]
    assert meta["avisos_tentar"] == meta["avisos"] and meta["anos"] == [2025]
    _reiniciar()


def test_erro_inesperado_nas_etapas_finais_tambem_avisa(tmp_path, monkeypatch):
    _reiniciar()

    def quebra(*a, **k):
        raise ValueError("formato novo")
    monkeypatch.setattr(financas, "coletar", quebra)
    build.coletar_financas(tmp_path, tmp_path)
    from sa_etl import tramitacao
    monkeypatch.setattr(tramitacao, "coletar", quebra)
    build.coletar_tramitacao(tmp_path, tmp_path, [])
    assert any(a.startswith("Arrecadação e gastos: a coleta falhou") for a in util.AVISOS)
    assert any(a.startswith("Projetos em andamento: a coleta falhou") for a in util.AVISOS)
    _reiniciar()
