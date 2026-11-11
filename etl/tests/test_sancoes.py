"""Punições oficiais: formato de cada lista, ligação só por CNPJ ou CPF (nunca só pelo nome), CPF sempre mascarado,
leitura aos poucos e cópia anterior quando a fonte cai."""
import datetime as dt
import json

import pytest

import fakegov_sancoes as fs
from fakegov import FakeGov, instalar
from sa_etl import sancoes as s
from sa_etl import util
from sa_etl.validar import CPF_ABERTO

HOJE = dt.date(2026, 11, 10)


def test_meio_do_cpf_nas_tres_mascaras():
    assert s.meio_cpf("***.435.151-**") == "435151"  # Portal
    assert s.meio_cpf("***435151**") == "435151"  # Receita
    assert s.meio_cpf("106.996.817-07") == "996817"  # CPF inteiro (CEIS, TCU)
    assert s.meio_cpf("12.345.678/0001-90") == ""
    assert s.meio_cpf("") == ""
    assert s.cpf_mascarado("106.996.817-07") == "***.996.817-**"


def test_multa_no_formato_brasileiro():
    assert s.valor_br("1.500.000,00") == 1500000.0
    assert s.valor_br("0,00") == 0.0
    assert s.valor_br("Sem informação") == 0.0
    assert s.valor_br(12.5) == 12.5


def test_nome_do_acordao_e_registro_do_tcu():
    assert s.nome_acordao("2180/2023-PL") == "Acórdão 2180/2023 (Plenário)"
    assert s.nome_acordao("10367/2023-1C") == "Acórdão 10367/2023 (1ª Câmara)"
    r = s.registro_tcu("tcu_eleitoral", fs._tcu("FULANO DE TAL", "10699681707", 1, "2030-07-16", True))
    assert r["doc"] == "***.996.817-**" and r["fim"] == "2030-07-16" and r["link"].startswith("https://contas.tcu.gov.br/")
    assert "10699681707" not in json.dumps(s._publico(r, HOJE))
    e = s.registro_tcu("tcu_irregulares", fs._tcu("EMPRESA X LTDA", "12345678000190", 2, None))
    assert e["cnpj"] == "12345678000190" and not e["pf"] and s._publico(e, HOJE)["vigente"]
    assert s.registro_tcu("tcu_irregulares", {"nome": "SEM DOCUMENTO", "numeroRegistro": ""}) is None


def test_registro_do_ceis_guarda_cpf_inteiro_so_em_campo_interno():
    x = fs._ceis(1, "FULANO DE TAL", "10699681707", False, "2024-01-01", "2030-01-01")
    r = s.registro_portal("ceis", x)
    assert r["pf"] and r["doc"] == "***.996.817-**" and r["meio"] == "996817" and r["_cpf"] == "10699681707"
    pub = s._publico(r, HOJE)
    assert "_cpf" not in pub and "meio" not in pub and pub["vigente"]
    assert "10699681707" not in json.dumps(pub)


def test_registro_de_empresa_e_vigencia():
    x = fs._ceis(2, "EMPRESA X LTDA", "12345678000190", True, "2019-01-01", "2021-01-01")
    r = s.registro_portal("ceis", x)
    assert r["cnpj"] == "12345678000190" and not r["pf"]
    assert not s._publico(r, HOJE)["vigente"]
    assert r["link"] == "https://portaldatransparencia.gov.br/pessoa-juridica/12345678000190"  # o Portal não tem página por punição
    sem_fim = s.registro_portal("cnep", fs._ceis(3, "EMPRESA Y SA", "12345678000271", True, "2025-01-01", "", "cnep"))
    assert s._publico(sem_fim, HOJE)["vigente"] and sem_fim["multa"] == 1500000.0


def _listas():
    ceis = [s.registro_portal("ceis", fs._ceis(1, "MARIA DA SILVA", "11122233344", False, "2024-01-01", "2030-01-01")),
            s.registro_portal("ceis", fs._ceis(2, "EMPRESA PUNIDA LTDA", "12345678000190", True, "2024-01-01", "2030-01-01"))]
    ceaf = [s.registro_portal("ceaf", fs._ceaf(1, "JOAO SOUZA", "55566677788"))]
    tcu = [s.registro_tcu("tcu_inabilitados", fs._tcu("PEDRO ALVES", "99988877766", 1))]
    return {"ceis": ceis, "ceaf": ceaf, "tcu_inabilitados": tcu}


def test_socio_liga_so_com_nome_e_meio_do_cpf_iguais():
    emps = [
        {"cnpj": "12345678000190", "nome": "EMPRESA PUNIDA LTDA", "socios": []},
        {"cnpj": "98765432000110", "nome": "BOA LTDA", "socios": [
            {"nome": "MARIA DA SILVA", "doc": "***222333**", "tipo": "pessoa"},  # mesma pessoa: liga
            {"nome": "JOAO SOUZA", "doc": "***111111**", "tipo": "pessoa"},  # homônimo, outro CPF: não liga
            {"nome": "PEDRO ALVES", "doc": "***888777**", "tipo": "pessoa"},  # TCU, CPF inteiro: liga pelo meio
        ]},
        {"cnpj": "11111111000111", "nome": "SOCIA PUNIDA SA", "socios": [{"nome": "EMPRESA PUNIDA LTDA", "doc": "12345678000190"}]},
    ]
    emp, pol = s.ligar(_listas(), emps, [], {}, HOJE)
    por = {e["cnpj"]: e for e in emp}
    assert por["12345678000190"]["registros"][0]["cad"] == "ceis" and por["12345678000190"]["vigente"]
    nomes = {x["nome"] for x in por["98765432000110"]["socios"]}
    assert nomes == {"MARIA DA SILVA", "PEDRO ALVES"}
    assert por["11111111000111"]["socios"][0]["doc"] == "12345678000190"  # sócio que é empresa: pelo CNPJ
    for e in emp:
        for x in e["socios"]:
            assert not CPF_ABERTO.match(x["doc"])
    assert pol == []


def test_deputado_liga_pelo_cpf_e_nunca_so_pelo_nome():
    listas = _listas()
    pols = [{"id": "dep-1", "nome": "Maria", "casa": "camara"}, {"id": "dep-2", "nome": "Pedro", "casa": "camara"},
            {"id": "dep-3", "nome": "Joao", "casa": "camara"}, {"id": "sen-4", "nome": "Maria da Silva", "casa": "senado"}]
    cpfs = {"dep-1": {"cpf": "11122233344", "nome_civil": "MARIA DA SILVA"},  # CEIS pelo CPF inteiro
            "dep-2": {"cpf": "00000000000", "nome_civil": "PEDRO ALVES"},  # homônimo no TCU, outro CPF
            "dep-3": {"cpf": "00066677700", "nome_civil": "JOAO SOUZA"}}  # CEAF: nome civil e meio do CPF
    _, pol = s.ligar(listas, [], pols, cpfs, HOJE)
    assert {p["id"] for p in pol} == {"dep-1", "dep-3"}
    assert "11122233344" not in json.dumps(pol)


def test_coleta_inteira_contra_o_governo_simulado(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_TRANSPARENCIA_CHAVE", "chave-de-teste")
    gov = instalar(monkeypatch, FakeGov(anos=(2025,)))
    from sa_etl import build
    util.AVISOS.clear()
    saida = tmp_path / "saida"
    build.executar([2025], tmp_path / "cache", saida, max_empresas=200, com_recursos=False, com_incentivos=False,
                   com_financas=False, com_tramitacao=False, com_tribunais=False, minutos_pagamentos=5)
    d = json.loads((saida / "sancoes.json").read_text(encoding="utf-8"))
    f = gov.fornecedoras
    emp = {e["cnpj"]: e for e in d["empresas"]}
    paginas = {e.stem for e in (saida / "e").glob("*.json")}
    for i, cad in ((3, "ceis"), (4, "ceis"), (5, "cnep"), (6, "tcu_inidoneos"), (7, "tcu_irregulares")):
        if f[i] in paginas:
            assert cad in {r["cad"] for r in emp[f[i]]["registros"]}, (i, cad)
    if f[4] in emp:
        assert not emp[f[4]]["registros"][0]["vigente"]  # sanção que já terminou aparece como encerrada
    if f[5] in emp:
        assert emp[f[5]]["registros"][0]["multa"] == 1500000.0
    socios = [x for e in d["empresas"] for x in e["socios"]]
    assert {x["nome"] for x in socios} <= {"DONO FICTICIO 1"}  # o homônimo DONO FICTICIO 2 (outro CPF) fica de fora
    pol = {p["id"]: {r["cad"] for r in p["registros"]} for p in d["politicos"]}
    assert pol.get("dep-1002") == {"ceis"} and pol.get("dep-1003") == {"ceaf"} and pol.get("dep-1004") == {"tcu_inabilitados", "tcu_eleitoral"}
    assert "dep-1005" not in pol  # homônimo no TCU com outro CPF
    texto = json.dumps(d)
    for dep in (1002, 1003, 1004):
        assert fs.cpf_deputado(dep) not in texto  # CPF inteiro nunca vai para o site
    assert d["fontes"]["ceis"]["situacao"] == "ok" and d["fontes"]["ceis"]["n"] == len(gov.sancoes.listas["ceis"])
    assert d["cobertura"]["deputados_com_cpf"] == d["cobertura"]["deputados"]


def test_leitura_aos_poucos_continua_na_coleta_seguinte(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov(anos=(2025,)))
    leitor = s.LeitorPortal(tmp_path, "chave-de-teste", HOJE, minutos=10)
    # a página 2 do CEIS falha: a leitura para ali e guarda o andamento
    gov.falhar("ceis?pagina=2", "500", 1.0)
    assert leitor.ler("ceis") == "falhou"
    andamento = json.loads(leitor.lendo("ceis").read_text())
    assert andamento["proxima"] == 2 and len(andamento["linhas"]) == 15
    gov.falhas.clear()
    antes = gov.sancoes.pedidos.get("ceis", 0)
    assert s.LeitorPortal(tmp_path, "chave-de-teste", HOJE, minutos=10).ler("ceis") == "pronta"
    assert gov.sancoes.pedidos["ceis"] - antes <= 4 + s.EM_PARALELO  # não releu a página 1
    final = json.loads(leitor.final("ceis").read_text())
    assert len(final["linhas"]) == len(gov.sancoes.listas["ceis"]) and not leitor.lendo("ceis").exists()


def test_lista_em_dia_nao_e_lida_de_novo_e_copia_velha_avisa(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov(anos=(2025,)))
    util.AVISOS.clear()
    s.LeitorPortal(tmp_path, "chave-de-teste", HOJE).coletar()
    n = dict(gov.sancoes.pedidos)
    s.LeitorPortal(tmp_path, "chave-de-teste", HOJE + dt.timedelta(days=1)).coletar()
    assert gov.sancoes.pedidos == n  # dentro de DIAS_LISTA: usa a cópia
    # a API cai e a cópia fica velha: o site mostra a lista anterior e avisa com a data
    gov.falhar("api-de-dados/c", "500", 1.0)
    listas, sit = s.LeitorPortal(tmp_path, "chave-de-teste", HOJE + dt.timedelta(days=s.DIAS_AVISO + 1)).coletar()
    assert listas["ceis"] and sit["ceis"]["situacao"] == "falhou" and sit["ceis"]["lida_em"] == HOJE.isoformat()
    assert any("CEIS" in a and "10/11/2026" in a for a in util.AVISOS)


def test_sem_chave_nao_quebra_e_avisa(tmp_path, monkeypatch):
    instalar(monkeypatch, FakeGov(anos=(2025,)))
    listas, sit = s.LeitorPortal(tmp_path, "", HOJE).coletar()
    assert listas == {} and sit["ceis"]["situacao"] == "sem_chave"


def test_tcu_fora_do_ar_usa_copia(tmp_path, monkeypatch):
    gov = instalar(monkeypatch, FakeGov(anos=(2025,)))
    l1, _ = s.coletar_tcu(tmp_path)
    assert len(l1["tcu_inidoneos"]) == 1
    for f in tmp_path.glob("*.json"):  # cópia de ontem
        import os
        os.utime(f, (f.stat().st_atime - 2 * 86400, f.stat().st_mtime - 2 * 86400))
    gov.falhar("certidoes.apps.tcu.gov.br", "500", 1.0)
    l2, sit = s.coletar_tcu(tmp_path)
    assert len(l2["tcu_inidoneos"]) == 1 and sit["tcu_inidoneos"]["situacao"] == "copia"  # a página diz que é cópia


@pytest.mark.parametrize("modo", ["html", "vazio", "lixo", "truncado"])
def test_resposta_estragada_do_portal_nao_vira_lista_vazia(tmp_path, monkeypatch, modo):
    gov = instalar(monkeypatch, FakeGov(anos=(2025,)))
    gov.falhar("cnep?pagina=1", modo, 1.0)
    assert s.LeitorPortal(tmp_path, "chave-de-teste", HOJE, minutos=1).ler("cnep") == "falhou"
    assert not s.LeitorPortal(tmp_path, "chave-de-teste", HOJE).final("cnep").exists()


def test_validar_barra_cpf_inteiro_link_estranho_e_ligacao_errada(tmp_path):
    from sa_etl.validar import Resultado, _conferir_sancoes
    (tmp_path / "e").mkdir()
    (tmp_path / "e" / "12345678000190.json").write_text("{}")
    reg = {"cad": "ceis", "id": 1, "nome": "X", "cnpj": "12345678000190", "link": "https://portaldatransparencia.gov.br/pessoa-juridica/12345678000190",
           "fim": "2030-01-01", "vigente": True}
    base = {"atualizado_em": "2026-11-10", "fontes": {}, "empresas": [{"cnpj": "12345678000190", "registros": [reg], "socios": []}],
            "politicos": []}

    def rodar(d):
        (tmp_path / "sancoes.json").write_text(json.dumps(d))
        r = Resultado()
        _conferir_sancoes(tmp_path, [{"id": "dep-1"}], r)
        return r.erros

    assert rodar(base) == []
    assert rodar({**base, "politicos": [{"id": "dep-1", "casa": "camara", "registros": [{**reg, "doc": "106.996.817-07"}]}]})
    assert rodar({**base, "empresas": [{"cnpj": "12345678000190", "socios": [], "registros": [{**reg, "link": "https://exemplo.com/x"}]}]})
    assert rodar({**base, "empresas": [{"cnpj": "12345678000190", "socios": [], "registros": [{**reg, "cnpj": "99999999000199"}]}]})
    assert rodar({**base, "empresas": [{"cnpj": "12345678000190", "socios": [], "registros": [{**reg, "vigente": False}]}]})
    assert rodar({**base, "politicos": [{"id": "sen-9", "casa": "senado", "registros": [reg]}]})
