"""Engenharia de caos: derrubamos, atrasamos e corrompemos os sites do governo simulados e conferimos
que o site continua certo.

Cada teste é um experimento:
- Estado normal (hipótese): os arquivos gerados passam na conferência (validar.py) sem erros: totais batem,
  nada repetido, nenhum CPF aberto, links seguros.
- Falha injetada: um site fora do ar, lento, devolvendo página de erro, arquivo cortado ou dados repetidos.
- Resultado esperado: ou a coleta usa a última cópia boa, ou deixa o dado de fora e AVISA (meta.avisos), ou
  para de vez sem gerar nada (e o site publicado antes continua no ar). Nunca publica dado errado calado.
"""
import os
import time
from datetime import datetime, timezone

import pytest

from fakegov import FakeGov
from sa_etl import util

SENADO_VOT = "legis.senado.leg.br/dadosabertos/votacao"
CEAPS = "despesas_ceaps"
COTA = "/cotas/Ano-"
RECEITA = "minhareceita.org"
VOT_CAMARA = "dadosabertos.camara.leg.br/arquivos/"
DEPUTADOS = "api/v2/deputados?itens"
EMENDAS = "emendas-parlamentares"


def _envelhecer(pasta, padrao):
    """Faz os arquivos do cache parecerem antigos, para a coleta tentar baixar de novo."""
    velho = time.time() - 30 * 3600
    for f in pasta.glob(padrao):
        os.utime(f, (velho, velho))


# ---------------------------------------------------------------- Senado (API instável: meses faltando)

def test_senado_fora_do_ar_em_alguns_meses_vira_aviso(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("dataInicio=2025-03", "500").falhar("dataInicio=2025-07", "timeout")
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []
    meta = coleta.ler(saida, "meta.json")
    aviso = next(a for a in meta["avisos"] if "Votações do Senado" in a)
    assert "03/2025" in aviso and "07/2025" in aviso
    datas = {v["data"][:7] for v in coleta.ler(saida, "votacoes.json") if v["casa"] == "senado"}
    assert "2025-03" not in datas and "2025-07" not in datas and "2025-04" in datas


def test_senado_fora_do_ar_usa_os_meses_guardados(coleta):
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    gov.falhar(SENADO_VOT, "conexao")
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "votacoes.json") == coleta.ler(boa, "votacoes.json")
    assert not any("Votações do Senado" in a for a in coleta.ler(ruim, "meta.json")["avisos"])


def test_senado_responde_lista_vazia_num_mes_que_tinha_votacoes(coleta):
    """A API às vezes responde [] (sucesso, mas sem nada). Não pode apagar o mês guardado."""
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    gov.vot_senado = {k: ([] if k == (2025, 4) else v) for k, v in gov.vot_senado.items()}
    for f in (coleta.cache / "senado-votacoes").glob("*"):
        os.utime(f, (0, 0))  # cópia velha: a coleta pergunta de novo
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "votacoes.json") == coleta.ler(boa, "votacoes.json")


def test_ceaps_responde_lista_vazia(coleta):
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    gov.ceaps = {a: [] for a in gov.ceaps}
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "meta.json")["total_gasto"] == coleta.ler(boa, "meta.json")["total_gasto"]


@pytest.mark.parametrize("modo", ["html", "vazio", "truncado", "lixo"])
def test_senado_resposta_corrompida_nao_quebra(coleta, modo):
    gov = coleta.usar(FakeGov())
    gov.falhar("dataInicio=2025-05", modo)
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []


def test_senado_repete_votacao_na_resposta(coleta):
    gov = coleta.usar(FakeGov())
    gov.repetir_linhas = True
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []
    vots = coleta.ler(saida, "votacoes.json")
    assert len(vots) == len({v["id"] for v in vots})


# ---------------------------------------------------------------- cota do Senado (CEAPS)

def test_ceaps_fora_do_ar_usa_a_ultima_copia(coleta):
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    gov.falhar(CEAPS, "500")
    baixada = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc).timestamp()  # 15h em Brasília
    for f in coleta.cache.glob("senado-ceaps-*.json"):
        os.utime(f, (baixada, baixada))
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "meta.json")["total_gasto"] == coleta.ler(boa, "meta.json")["total_gasto"]
    # o aviso diz de quando é a cópia em uso
    assert "Cota do Senado 2025: a API oficial não respondeu; usamos a última cópia baixada, de 25/10/2026" in \
        coleta.ler(ruim, "meta.json")["avisos"]


def test_ceaps_fora_do_ar_sem_copia_bloqueia_publicacao_pela_queda(coleta, tmp_path):
    """Sem cópia, os senadores ficam sem gastos. A conferência com a versão publicada antes pega a queda."""
    gov = coleta.usar(FakeGov(n_sen=40))
    boa = coleta.rodar()
    anterior = coleta.ler(boa, "meta.json")
    for f in coleta.cache.glob("senado-ceaps-*.json"):
        f.unlink()
    gov.falhar(CEAPS, "html")
    ruim = coleta.rodar()
    meta = coleta.ler(ruim, "meta.json")
    assert any("Cota do Senado 2025" in a and "faltando" in a for a in meta["avisos"])
    r = coleta.validar(ruim, anterior=anterior)
    assert any("Queda" in e for e in r.erros)
    # quem decide publicar mesmo assim pode ignorar a queda (vira alerta)
    assert coleta.validar(ruim, anterior=anterior, ignorar_queda=True).erros == []


def test_ceaps_volta_depois_de_429(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar(CEAPS, "429", vezes=2)  # a coleta tenta 4 vezes
    saida = coleta.rodar()
    assert coleta.ler(saida, "meta.json")["avisos"] == []
    assert any(p["casa"] == "senado" and p["total"] > 0 for p in coleta.ler(saida, "politicos.json"))


# ---------------------------------------------------------------- cota da Câmara

def test_cota_camara_fora_do_ar_usa_copia_antiga(coleta):
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    _envelhecer(coleta.cache, "camara-cota-*")
    gov.falhar(COTA, "timeout")
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "meta.json")["total_gasto"] == coleta.ler(boa, "meta.json")["total_gasto"]
    assert any("camara-cota-2025" in a for a in coleta.ler(ruim, "meta.json")["avisos"])


@pytest.mark.parametrize("modo", ["html", "truncado", "vazio"])
def test_cota_camara_corrompida_nao_substitui_a_copia_boa(coleta, modo):
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    _envelhecer(coleta.cache, "camara-cota-*")
    gov.falhar(COTA, modo)
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "meta.json")["total_gasto"] == coleta.ler(boa, "meta.json")["total_gasto"]
    assert coleta.validar(ruim).erros == []


def test_cota_camara_corrompida_sem_copia_vira_aviso(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar(COTA, "html")
    saida = coleta.rodar()
    meta = coleta.ler(saida, "meta.json")
    assert any("Cota da Câmara 2025" in a for a in meta["avisos"])
    assert coleta.validar(saida).erros == []


# ---------------------------------------------------------------- votações da Câmara

def test_votacoes_camara_com_linhas_repetidas(coleta):
    gov = coleta.usar(FakeGov())
    normal = coleta.rodar()
    gov.repetir_linhas = True
    for f in coleta.cache.glob("camara-vot*"):
        f.unlink()
    for f in coleta.cache.glob("camara-votos*"):
        f.unlink()
    repetida = coleta.rodar()
    assert coleta.validar(repetida).erros == []
    assert coleta.ler(repetida, "votacoes.json") == coleta.ler(normal, "votacoes.json")


def test_votacoes_camara_pagina_de_erro_no_lugar_do_csv(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar(VOT_CAMARA + "votacoesVotos", "html")
    saida = coleta.rodar()
    meta = coleta.ler(saida, "meta.json")
    assert any("Votações da Câmara 2025" in a for a in meta["avisos"])
    assert not any(v["casa"] == "camara" for v in coleta.ler(saida, "votacoes.json"))
    assert coleta.validar(saida).erros == []


# ---------------------------------------------------------------- Receita (sócios e holdings)

@pytest.mark.parametrize("modo", ["500", "timeout", "html", "truncado"])
def test_receita_instavel_nao_quebra_holdings(coleta, modo):
    gov = coleta.usar(FakeGov())
    gov.falhar(RECEITA, modo, prob=0.5)
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []


# ---------------------------------------------------------------- PDFs das notas

def test_site_da_camara_fora_do_ar_na_conferencia_dos_pdfs(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar("/cota-parlamentar/documentos/publ/", "conexao")
    saida = coleta.rodar()
    assert coleta.validar(saida).erros == []  # os links ficam como a Câmara publicou


# ---------------------------------------------------------------- emendas

@pytest.mark.parametrize("modo", ["500", "html", "truncado"])
def test_portal_da_transparencia_fora_do_ar(coleta, modo):
    gov = coleta.usar(FakeGov())
    gov.falhar(EMENDAS, modo).falhar("EmendasParlamentares.zip", modo)
    saida = coleta.rodar()
    assert not (saida / "emendas" / "anos.json").exists()
    assert any("Emendas" in a for a in coleta.ler(saida, "meta.json")["avisos"])
    assert coleta.validar(saida).erros == []


def test_portal_fora_do_ar_usa_a_ultima_copia_e_diz_de_quando(coleta):
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    z = coleta.cache / "emendas" / "EmendasParlamentares.zip"
    assert z.exists()
    baixada = datetime(2026, 10, 24, 2, 30, tzinfo=timezone.utc).timestamp()  # 23h30 do dia 23 em Brasília
    os.utime(z, (baixada, baixada))
    gov.falhar(EMENDAS, "500").falhar("EmendasParlamentares.zip", "500")
    ruim = coleta.rodar()
    assert coleta.ler(ruim, "emendas/anos.json") == coleta.ler(boa, "emendas/anos.json")
    assert "Emendas: o Portal da Transparência não respondeu; usamos a última cópia baixada, de 23/10/2026" in \
        coleta.ler(ruim, "meta.json")["avisos"]


# ---------------------------------------------------------------- falha total: não publica nada

def test_lista_de_deputados_fora_do_ar_para_tudo(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar(DEPUTADOS, "500")
    with pytest.raises(RuntimeError):
        coleta.rodar()
    assert not list(coleta.tmp.glob("saida*/meta.json"))


def test_lista_de_deputados_vazia_para_tudo(coleta):
    gov = coleta.usar(FakeGov(n_dep=0))
    with pytest.raises(RuntimeError):
        coleta.rodar()


# ---------------------------------------------------------------- macaco do caos: falhas aleatórias em tudo

ALVOS = [SENADO_VOT, CEAPS, COTA, RECEITA, VOT_CAMARA, EMENDAS, "/cota-parlamentar/documentos/publ/",
         "senador/lista/atual.json", DEPUTADOS]
MODOS = ["500", "429", "404", "timeout", "conexao", "html", "vazio", "truncado", "lixo"]


@pytest.mark.parametrize("semente", range(int(os.environ.get("CAOS_RODADAS", "12"))))
def test_macaco_do_caos(coleta, semente):
    """Falhas aleatórias em todas as fontes, em duas coletas seguidas (a segunda com cache).

    Em todas as rodadas: ou a coleta para sem gerar arquivos, ou o que ela gera passa na conferência.
    """
    import random
    rnd = random.Random(semente)
    gov = coleta.usar(FakeGov(seed=semente))
    gov.repetir_linhas = rnd.random() < 0.5
    for _ in range(2):
        gov.consertar()
        for alvo in rnd.sample(ALVOS, k=rnd.randint(1, 4)):
            gov.falhar(alvo, rnd.choice(MODOS), prob=rnd.choice([0.2, 0.5, 1.0]))
        _envelhecer(coleta.cache, "*")
        try:
            saida = coleta.rodar()
        except Exception:  # noqa: BLE001 - parou de vez: o passo do GitHub Actions falha e o site publicado antes continua no ar
            assert not (coleta.tmp / f"saida{coleta.n}" / "meta.json").exists()
            continue
        r = coleta.validar(saida)
        # "Poucas votações", "Poucos parlamentares": a trava de tamanho barrou a publicação, que é o certo.
        # Qualquer outro erro seria dado inconsistente.
        inconsistentes = [e for e in r.erros if not e.startswith(("Poucas", "Poucos"))]
        assert inconsistentes == [], (semente, gov.falhas, inconsistentes[:5])


# ---------------------------------------------------------------- site parado (não aceita conexão)

def test_camara_parada_nao_trava_a_coleta(coleta):
    """Em 23/10/2026 o site da Câmara parou de aceitar conexões: cada endereço esperava minutos e a coleta
    estourou as 2 horas do GitHub Actions sem publicar nada. Depois de 3 esperas seguidas sem resposta,
    o site fica de fora até o fim da coleta e o resto segue."""
    gov = coleta.usar(FakeGov())
    boa = coleta.rodar()
    gov.falhar("dadosabertos.camara.leg.br", "parado")
    antes = len(gov.chamadas)
    try:
        coleta.rodar()
    except Exception:  # noqa: BLE001  (sem a Câmara a coleta pode parar de vez, e o site anterior fica no ar)
        pass
    na_camara = [c for c in gov.chamadas[antes:] if "dadosabertos.camara.leg.br" in c]
    assert len(na_camara) <= 3, na_camara
    assert "dadosabertos.camara.leg.br" in util.FORA_DO_AR
    assert boa.exists()


def test_site_parado_volta_a_ser_tentado_na_coleta_seguinte(coleta):
    gov = coleta.usar(FakeGov())
    gov.falhar(SENADO_VOT, "parado", vezes=util.QUEDAS_PARA_DESISTIR)
    coleta.rodar()
    gov.consertar()
    saida = coleta.rodar()
    assert "legis.senado.leg.br" not in util.FORA_DO_AR
    assert any(v["casa"] == "senado" for v in coleta.ler(saida, "votacoes.json"))


def test_uma_espera_isolada_nao_derruba_o_site(coleta):
    """Só desistimos depois de esperas SEGUIDAS: uma resposta boa no meio zera a conta."""
    gov = coleta.usar(FakeGov())
    gov.falhar(SENADO_VOT, "parado", vezes=util.QUEDAS_PARA_DESISTIR - 1)
    saida = coleta.rodar()
    assert "legis.senado.leg.br" not in util.FORA_DO_AR
    assert coleta.validar(saida).erros == []
