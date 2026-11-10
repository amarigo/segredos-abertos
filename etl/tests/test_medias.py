"""Média da Casa ao lado de cada número do perfil (sa_etl/medias.py) e a conferência dela (validar.py)."""
import datetime as dt
import json

from sa_etl import medias
from sa_etl.validar import Resultado, _conferir_medias_casa


def _nota(ano, mes, valor=100.0):
    return {"ano": ano, "mes": mes, "valor": valor}


def _pol(pid, casa, por_ano, fid=None, gov=None):
    return {"id": pid, "casa": casa, "por_ano": por_ano, "fidelidade_partido": fid, "alinhamento_governo": gov}


def _ano(total, meses, custo=None, verba=None, n=None, plen=None):
    a = {"total": total, "custo_total": custo if custo is not None else total, "verba_gabinete": verba, "n_pessoal": n,
         "meses_com_nota": meses}
    if plen:
        a["atuacao"] = {"plenario": plen}
    return a


def test_periodo_do_ano_fechado_e_do_ano_em_andamento():
    notas = [_nota(2025, m) for m in range(1, 13)] + [_nota(2026, m) for m in range(1, 12)]
    # Em 10/11/2026 o mês 11 ainda não acabou: o período de 2026 vai até outubro
    assert medias.meses_do_periodo(notas, [2025, 2026], dt.date(2026, 11, 10)) == {"2025": 12, "2026": 10}
    # Ano fechado sem nota em dezembro continua com 12 meses
    assert medias.meses_do_periodo([_nota(2024, 3)], [2024], dt.date(2026, 11, 10)) == {"2024": 12}


def test_meses_com_nota_conta_meses_distintos_dentro_do_periodo():
    ds = [_nota(2026, 1), _nota(2026, 1), _nota(2026, 2), _nota(2026, 11), _nota(2025, 3)]
    assert medias.meses_com_nota(ds, 2026, 10) == 2


def test_suplente_de_poucos_meses_fica_fora_da_media_de_dinheiro():
    resumo = [
        _pol("dep-1", "camara", {"2025": _ano(480_000, 12, verba=1_000_000, n=20)}),
        _pol("dep-2", "camara", {"2025": _ano(460_000, 11, verba=1_100_000, n=24)}),  # um mês sem nota: ainda conta
        _pol("dep-3", "camara", {"2025": _ano(40_000, 2, verba=150_000, n=6)}),       # suplente de dois meses: fora
    ]
    m = medias.medias_da_casa(resumo, {"2025": 12})["anos"]["2025"]["camara"]
    assert m["meses"] == 12
    assert m["total"] == {"media": 470_000.0, "n": 2}
    assert m["verba_gabinete"] == {"media": 1_050_000.0, "n": 2}
    assert m["n_pessoal"] == {"media": 22.0, "n": 2}
    assert "senado" not in medias.medias_da_casa(resumo, {"2025": 12})["anos"]["2025"]


def test_taxas_usam_todos_que_tem_a_taxa():
    resumo = [
        _pol("dep-1", "camara", {"2026": _ano(1, 10, plen=[90, 5, 5])}, fid=0.9, gov=0.2),
        _pol("dep-2", "camara", {"2026": _ano(1, 2, plen=[10, 0, 0])}, fid=0.8, gov=None),  # pouco tempo, mas tem taxa
        _pol("dep-3", "camara", {"2026": _ano(1, 2, plen=[0, 0, 0])}),                      # sem sessão: fora
    ]
    out = medias.medias_da_casa(resumo, {"2026": 10})
    assert out["anos"]["2026"]["camara"]["presenca_plenario"] == {"media": 0.95, "n": 2}
    assert out["votos"]["camara"] == {"min_votos": 15, "fidelidade_partido": {"media": 0.85, "n": 2}, "alinhamento_governo": {"media": 0.2, "n": 1}}


def test_validar_refaz_a_conta_e_pega_media_adulterada():
    resumo = [_pol("dep-1", "camara", {"2025": _ano(300, 12, plen=[9, 1, 0])}, fid=0.9),
              _pol("sen-1", "senado", {"2025": _ano(500, 12)}, gov=0.7)]
    mc = medias.medias_da_casa(resumo, {"2025": 12})
    r = Resultado()
    _conferir_medias_casa({"medias_casa": mc}, resumo, r)
    assert r.ok, r.erros

    ruim = json.loads(json.dumps(mc))
    ruim["anos"]["2025"]["camara"]["total"]["media"] = 999
    r = Resultado()
    _conferir_medias_casa({"medias_casa": ruim}, resumo, r)
    assert not r.ok and "refeita" in r.erros[0]

    ruim = json.loads(json.dumps(mc))
    ruim["votos"]["camara"]["fidelidade_partido"]["media"] = 1.4
    r = Resultado()
    _conferir_medias_casa({"medias_casa": ruim, "recorte": "MG"}, resumo, r)  # no recorte não refaz, mas confere a faixa
    assert not r.ok and "fora do possível" in r.erros[0]


def test_recorte_de_mg_nao_refaz_a_media_da_casa_inteira():
    resumo = [_pol("dep-1", "camara", {"2025": _ano(300, 12)})]
    mc = {"anos": {"2025": {"camara": {"meses": 12, "total": {"media": 470_000.0, "n": 486}}}}, "votos": {}}
    r = Resultado()
    _conferir_medias_casa({"medias_casa": mc, "recorte": "MG"}, resumo, r)
    assert r.ok, r.erros
