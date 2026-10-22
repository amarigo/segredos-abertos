"""Pagamentos de emendas nos arquivos diários de despesas, com dados fictícios mínimos."""
import datetime as dt
import gzip
import json
import zipfile

from sa_etl import pagamentos

EMP = ('"Código Empenho";"Data Emissão";"Órgão Superior";"Órgão";"Unidade Gestora";"Código Favorecido";"Favorecido";'
       '"Observação";"Função";"Modalidade de Aplicação";"Autor Emenda";"Valor do Empenho Convertido pra R$"\n'
       '"154040152572025NE000001";"10/03/2025";"Ministério da Saúde";"FNS";"UG SAUDE";"12.345.678/0001-95";"OBRAS X LTDA";'
       '"OBRA DA EMENDA";"Saúde";"Aplicações Diretas";"FULANO DE TAL / EMENDA 7";"1.000,00"\n'
       '"154040152572025NE000002";"10/03/2025";"Ministério da Saúde";"FNS";"UG SAUDE";"46.395.000/0001-39";"MUNICIPIO DE SAO PAULO";'
       '"REPASSE";"Saúde";"Transferências a Municípios";"FULANO DE TAL / EMENDA 8";"500,00"\n'
       '"154040152572025NE000003";"10/03/2025";"Ministério da Saúde";"FNS";"UG SAUDE";"12.345.678/0001-95";"OBRAS X LTDA";'
       '"OUTRA";"Saúde";"Aplicações Diretas";"Sem emenda";"9,00"\n')
IMP = ('"Código Pagamento";"Código Empenho";"Valor Pago (R$)";"Valor Restos a Pagar Pagos (R$)"\n'
       '"154040152572025OB000001";"154040152572025NE000001";"600,00";"0,00"\n'
       '"154040152572025OB000002";"154040152572025NE000002";"500,00";"0,00"\n'
       '"154040152572025OB000003";"154040152572025NE000003";"9,00";"0,00"\n')
PAG = ('"Código Pagamento";"Data Emissão";"Tipo Documento";"Órgão Superior";"Unidade Gestora";"Código Favorecido";"Favorecido";'
       '"Observação"\n'
       '"154040152572025OB000001";"20/04/2025";"Ordem Bancária";"Ministério da Saúde";"UG SAUDE";"12.345.678/0001-95";"OBRAS X LTDA";"PARCELA 1"\n'
       '"154040152572025OB000002";"20/04/2025";"Ordem Bancária";"Ministério da Saúde";"UG SAUDE";"46.395.000/0001-39";"MUNICIPIO DE SAO PAULO";""\n'
       '"154040152572025OB000003";"20/04/2025";"Ordem Bancária";"Ministério da Saúde";"UG SAUDE";"12.345.678/0001-95";"OBRAS X LTDA";""\n')


def _zip(path, arquivos):
    with zipfile.ZipFile(path, "w") as z:
        for nome, txt in arquivos.items():
            z.writestr(nome, txt.encode("latin-1"))
    return path


def test_autor_e_link_do_documento():
    assert pagamentos.autor_da_emenda("BANCADA DO DISTRITO FEDERAL / EMENDA 8") == ("BANCADA DO DISTRITO FEDERAL", "8")
    assert pagamentos.autor_da_emenda("Sem emenda") is None and pagamentos.autor_da_emenda("") is None
    assert pagamentos.url_documento("154040152572025NE002378").endswith("/despesas/empenho/154040152572025NE002378")
    assert "/despesas/pagamento/" in pagamentos.url_documento("154003152792025OB023004")
    assert "/despesas/liquidacao/" in pagamentos.url_documento("154003152792025NS023004")


def test_liga_pagamento_ao_empenho_de_dias_anteriores(tmp_path):
    vistos: set[str] = set()
    d1 = pagamentos.ler_dia(_zip(tmp_path / "a.zip", {"20250310_Despesas_Empenho.csv": EMP}), vistos)
    assert [e["autor"] for e in d1["empenhos"]] == ["FULANO DE TAL", "FULANO DE TAL"] and d1["empenhos"][0]["emenda"] == "7"
    d2 = pagamentos.ler_dia(_zip(tmp_path / "b.zip", {"20250420_Despesas_Pagamento_EmpenhosImpactados.csv": IMP,
                                                      "20250420_Despesas_Pagamento.csv": PAG}), vistos)
    assert [p["codigo"][-3:] for p in d2["pagamentos"]] == ["001", "002"]  # o terceiro não é de emenda
    arqs = []
    for nome, d in (("20250310", d1), ("20250420", d2)):
        f = tmp_path / f"{nome}-v1.json.gz"
        f.write_bytes(gzip.compress(json.dumps(d).encode()))
        arqs.append(f)
    r = pagamentos.resumir(arqs, [2025])
    a = r["anos"][2025]
    assert r["ate"] == "2025-04-20" and a["total"] == 1100.0 and a["n"] == 2
    assert list(a["favorecidos"]) == ["12345678000195"]  # a prefeitura não é empresa
    assert a["autores"]["fulano de tal"]["valor"] == 1100.0
    emp = pagamentos.por_empresa(r, {"fulano de tal": {"nome": "Fulano de Tal", "politico": "dep-1", "partido": "AAA"}}, {"12345678000195"})
    e = emp["12345678000195"]
    assert e["total"] == 600.0 and e["autores"] == [{"nome": "Fulano de Tal", "politico": "dep-1", "partido": "AAA", "valor": 600.0}]
    assert e["docs"][0]["descricao"] == "OBRA DA EMENDA" and e["docs"][0]["url_empenho"].endswith("NE000001")


def test_coletar_respeita_o_cache_e_o_tempo(tmp_path, monkeypatch):
    chamadas = []

    def baixar(dia, dest):
        chamadas.append(dia)
        if dia == "20250310":
            _zip(dest, {"x_Despesas_Empenho.csv": EMP})
            return True
        return None
    monkeypatch.setattr(pagamentos, "_baixar_dia", baixar)
    hoje = dt.date(2025, 3, 20)
    arqs = pagamentos.coletar([2025], tmp_path, hoje=hoje)
    assert chamadas[0] == "20240101" and len(arqs) == len(chamadas) - 5  # os 5 dias mais recentes sem arquivo ficam para depois
    chamadas.clear()
    pagamentos.coletar([2025], tmp_path, hoje=hoje)
    assert len(chamadas) == 5  # só os dias recentes são lidos de novo
    assert pagamentos.coletar([2025], tmp_path / "outro", minutos=0, hoje=hoje) == []
