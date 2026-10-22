"""Integração: a coleta inteira contra os sites do governo simulados (FakeGov), sem falhas.

Confere o "estado normal" que os testes de caos depois tentam quebrar: todos os totais batem entre si,
nada repetido, nenhum CPF aberto, todo link é http(s).
"""
import re

from fakegov import FakeGov


def test_coleta_completa_passa_na_conferencia(coleta):
    gov = coleta.usar(FakeGov(anos=(2025,)))
    saida = coleta.rodar()
    r = coleta.validar(saida)
    assert r.erros == []
    meta = coleta.ler(saida, "meta.json")
    assert meta["avisos"] == []
    assert meta["contagens"]["politicos"] == len(gov.deputados) + len(gov.senadores)


def test_total_igual_a_soma_das_notas_da_fonte(coleta):
    """O total do site é exatamente a soma das notas dos arquivos oficiais (nenhuma nota perdida ou contada duas vezes)."""
    gov = coleta.usar(FakeGov(anos=(2025,)))
    saida = coleta.rodar()
    meta = coleta.ler(saida, "meta.json")
    fonte = sum(float(l[9]) for l in gov.cota[2025]) + sum(x["valorReembolsado"] for x in gov.ceaps[2025])
    assert abs(meta["total_por_ano"]["2025"] - fonte) < 0.05


def test_deputado_repetido_na_paginacao_aparece_uma_vez(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    pols = coleta.ler(saida, "politicos.json")
    assert len(pols) == len({p["id"] for p in pols}) == len(gov.deputados) + len(gov.senadores)


def test_cpf_de_fornecedor_nunca_aparece_aberto(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    for f in saida.rglob("*.json"):
        texto = f.read_text(encoding="utf-8")
        assert "12345678909" not in texto and "123.456.789-09" not in texto, f


def test_votacao_secreta_e_de_comissao_ficam_de_fora(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    vots = coleta.ler(saida, "votacoes.json")
    assert not any("comissão" in v["descricao"] for v in vots)
    ids_senado = {v["id"] for v in vots if v["casa"] == "senado"}
    assert "sf-2025062" not in ids_senado  # a secreta de junho
    assert len(ids_senado) == 12 * 3 - 1


def test_placar_bate_com_a_fonte(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    for linha in gov.vot_camara[2025]["votacoes"][:5]:
        vid = linha[0]
        fonte = [v for v in gov.vot_camara[2025]["votos"] if v[0] == vid]
        v = coleta.ler(saida, f"v/cd-{vid}.json")
        assert v["sim"] == sum(1 for x in fonte if x[1] == "Sim")
        assert v["nao"] == sum(1 for x in fonte if x[1] == "Não")


def test_holdings_cadeia_e_ciclo(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    h1, h2, h3, h4 = gov.holdings
    e0 = coleta.ler(saida, f"e/{gov.fornecedoras[0]}.json")
    dono = e0["donos_finais"][0]
    assert dono["nome"] == "DONA FINAL" and [c["cnpj"] for c in dono["cadeia"]] == [h1, h2] and dono["fim"] == "pessoa"
    e1 = coleta.ler(saida, f"e/{gov.fornecedoras[1]}.json")
    assert [d["fim"] for d in e1["donos_finais"]] == ["ciclo"]
    # a sócia com só a raiz do CNPJ é a mesma holding: as duas fornecedoras aparecem como do mesmo dono
    e2 = coleta.ler(saida, f"e/{gov.fornecedoras[2]}.json")
    assert e2["donos_finais"][0]["nome"] == "DONA FINAL"
    outras = {o["cnpj"] for s in e0["socios"] for o in s["outras_empresas"]}
    assert gov.fornecedoras[2] in outras


def test_mesmo_endereco(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    e3 = coleta.ler(saida, f"e/{gov.fornecedoras[3]}.json")
    assert [x["cnpj"] for x in e3["mesmo_endereco"]] == [gov.fornecedoras[4]]


def test_notas_sem_pdf_levam_a_pagina_de_detalhe(coleta):
    gov = coleta.usar(FakeGov())
    saida = coleta.rodar()
    assert gov.pdf_faltando
    vistos = 0
    for f in (saida / "e" / "notas").glob("*.json"):
        for n in coleta.ler(saida, f"e/notas/{f.name}"):
            k = re.search(r"/publ/(\d+/\d+/\d+)\.pdf$", n[4] or "")
            if n[5] == "sem_pdf":
                vistos += 1
                assert "cota-parlamentar/documento?" in n[4]
            elif k:
                assert k.group(1) not in gov.pdf_faltando
    assert vistos > 0


def test_emendas_somam_certo(coleta):
    coleta.usar(FakeGov())
    saida = coleta.rodar()
    d = coleta.ler(saida, "emendas/2025.json")
    assert d["total"]["empenhado"] == 10 * 1000 + 5000
    assert d["total"]["pago"] == 10 * 700 + 2000  # pago + restos a pagar pagos
    assert d["favorecidos"]["total"] == 10 * 700


def test_rodar_duas_vezes_da_o_mesmo_resultado(coleta):
    """Idempotência: com o cache cheio, a segunda coleta gera exatamente os mesmos arquivos."""
    coleta.usar(FakeGov())
    a = coleta.rodar()
    b = coleta.rodar()
    fa = sorted(p.relative_to(a) for p in a.rglob("*.json"))
    assert fa == sorted(p.relative_to(b) for p in b.rglob("*.json"))
    for rel in fa:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel
