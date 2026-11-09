"""Comparação justa da verba de gabinete entre os estados (sa_etl/gabinetes.py)."""
import json
from collections import Counter

from fakegov import FakeGov, instalar
import fakegov_gabinetes
from sa_etl import gabinetes, validar

def test_serie_sidra_ignora_sem_valor():
    d = fakegov_gabinetes._sidra("9324", "População", "2025", "Ano", lambda c: fakegov_gabinetes.UFS[c][2])
    per, valores, nomes = gabinetes.serie_sidra(d)
    assert per == "2025" and valores["SP"] == 46_000_000 and len(valores) == len(fakegov_gabinetes.UFS)
    assert nomes["Mato Grosso"] == "MT"
    try:
        gabinetes.serie_sidra([{"V": "Valor"}])
        assert False, "resposta só com o cabeçalho deveria falhar"
    except ValueError:
        pass


def test_regras_da_pagina_da_camara():
    nomes = {u[1]: u[0] for u in fakegov_gabinetes.UFS.values()}
    r = gabinetes.regras_camara(fakegov_gabinetes.pagina_regras(), nomes)
    assert r["teto_mensal"] == 165806.07 and r["max_secretarios"] == 25
    assert r["salario_min"] == 1710.83 and r["salario_max"] == 25958.90
    assert r["cota_por_uf"]["SP"] == 40000.0 and len(r["cota_por_uf"]) == len(fakegov_gabinetes.UFS)
    assert gabinetes.regras_camara("<html>página nova, sem o texto</html>", nomes) is None


def test_secretarios_so_dos_gabinetes():
    dados = [{"grupo": "Secretário Parlamentar", "uriLotacao": "https://dadosabertos.camara.leg.br/api/v2/deputados/7"},
             {"grupo": "Secretário Parlamentar", "uriLotacao": "https://dadosabertos.camara.leg.br/api/v2/deputados/7"},
             {"grupo": "Quadro Efetivo - RJU", "uriLotacao": "https://dadosabertos.camara.leg.br/api/v2/deputados/7"},
             {"grupo": "Secretário Parlamentar", "uriLotacao": ""}]
    assert gabinetes.secretarios_por_deputado(dados) == Counter({"7": 2})


def _pol(i, casa, uf, verba=None, teto=None, mes=None, pessoal=None, exercicio=True):
    x = {k: v for k, v in {"verba_gabinete": verba, "verba_disponivel": teto, "verba_ate_mes": mes, "n_pessoal": pessoal}.items() if v}
    return {"id": f"{'dep' if casa == 'camara' else 'sen'}-{i}", "casa": casa, "uf": uf, "em_exercicio": exercicio, "por_ano": {"2025": x}}


def test_resumir_soma_a_bancada_inteira():
    pols = [_pol(1, "camara", "SP", 100, 200, 12), _pol(2, "camara", "SP", 50, 100, 6, exercicio=False),  # suplente que saiu
            _pol(3, "camara", "MT", 80, 100, 10), _pol(4, "senado", "MT", pessoal=40), _pol(5, "senado", "MT", pessoal=30, exercicio=False)]
    r = gabinetes.resumir(pols, [2025, 2026], {"SP": 1000.0, "MT": 300.0}, {"SP": 4000.0}, Counter({"1": 20, "2": 9, "3": 15}))
    assert list(r) == ["2025"]  # 2026 sem verba: fica de fora
    sp, mt = {u["uf"]: u for u in r["2025"]["ufs"]}["SP"], {u["uf"]: u for u in r["2025"]["ufs"]}["MT"]
    assert r["2025"]["meses"] == 12
    assert sp["cadeiras"] == 1 and sp["verba"] == 150 and sp["teto"] == 300 and sp["deputados_no_ano"] == 2
    assert sp["secretarios_hoje"] == 20  # só quem está no cargo hoje
    assert mt["rendimento"] is None and mt["equipe_senado"] == 40 and mt["senadores"] == 1


def test_coleta_com_governo_simulado(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov())
    pols = [_pol(d["id"], "camara", d["siglaUf"], 1000.0, 2000.0, 12) for d in gov.deputados[:4]]
    (tmp_path / "politicos.json").write_text(json.dumps(pols))
    d = gabinetes.coletar(tmp_path, tmp_path / "cache", [2025])
    assert d and d["regras"]["teto_mensal"] == 165806.07 and d["ano_populacao"] == "2025"
    sp = next(u for u in d["anos"]["2025"]["ufs"] if u["uf"] == "SP")
    assert sp["populacao"] == 46_000_000 and sp["rendimento"] == 4100.0 and sp["secretarios_hoje"] > 0
    r = validar.Resultado()
    validar._conferir_gabinetes(tmp_path, pols, r)
    assert r.ok, r.erros
    # IBGE fora do ar: usa a cópia guardada, com aviso
    gov.falhar("apisidra.ibge.gov.br", "500")
    for f in (tmp_path / "cache" / "gabinetes").glob("*.json"):
        import os
        os.utime(f, (0, 0))
    assert gabinetes.coletar(tmp_path, tmp_path / "cache", [2025])["anos"]["2025"]["ufs"][0]["populacao"]


def test_validar_acusa_soma_diferente(tmp_path):
    pols = [_pol(1, "camara", "SP", 100, 200, 12)]
    (tmp_path / "gabinetes.json").write_text(json.dumps({"anos": {"2025": {"meses": 12, "ufs": [
        {"uf": "SP", "populacao": 10, "cadeiras": 1, "verba": 999, "teto": 200}]}}, "fontes": {"populacao": "https://x"}}))
    r = validar.Resultado()
    validar._conferir_gabinetes(tmp_path, pols, r)
    assert not r.ok and "verba" in r.erros[0]
