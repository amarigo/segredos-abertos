"""Julgamentos do STF: lado de cada voto, placar, resumo por ministro e a coleta inteira contra o STF simulado."""
import datetime as dt
import json

from fakegov import FakeGov, instalar
from sa_etl import tribunais as t
from sa_etl import util


def test_nome_do_ministro_sem_titulo_e_sem_caixa_alta():
    assert t.nome_ministro({"descricao": "MIN. ALEXANDRE DE MORAES"}) == "Alexandre de Moraes"
    assert t.nome_ministro("MIN. CÁRMEN LÚCIA") == "Cármen Lúcia"
    assert t.nome_ministro("Flávio Dino") == "Flávio Dino"
    assert t.nome_ministro("") == ""


def test_datas_nos_dois_formatos():
    assert t._data("10/10/2026") == "2026-10-10"
    assert t._data("10/10/2026 00:00:00") == "2026-10-10"
    assert t._data("2026-10-10T00:00:00") == "2026-10-10"
    assert t._data(None) == ""


def test_lado_do_voto():
    lados = {"Ana": "relator", "Bruno": "divergencia"}
    assert t.lado_do_voto("Acompanho o Relator", "", "Ana", lados) == "relator"
    assert t.lado_do_voto("Acompanho o(a) Relator(a) com ressalvas", "", "Ana", lados) == "relator"
    assert t.lado_do_voto("Divergência", "", "Ana", lados) == "divergencia"
    assert t.lado_do_voto("Acompanho a divergência", "", "Ana", lados) == "divergencia"
    assert t.lado_do_voto("Acompanho o voto", "Bruno", "Ana", lados) == "divergencia"
    assert t.lado_do_voto("Acompanho o voto", "Ana", "Ana", lados) == "relator"
    assert t.lado_do_voto("Impedido", "", "Ana", lados) == "fora"
    assert t.lado_do_voto("Suspeição", "", "Ana", lados) == "fora"
    assert t.lado_do_voto("Pedido de vista", "", "Ana", lados) == "vista"
    assert t.lado_do_voto("Algo novo", "", "Ana", lados) == "outro"


def test_o_que_entra():
    assert t.entra("ADI", "", "2") and t.entra("ADPF", "EMB.DECL. NA ARGUIÇÃO", "2")
    assert t.entra("ACO", "", "3")  # lista de controle concentrado
    assert t.entra("RE", "", "1")  # recurso extraordinário no mérito (repercussão geral)
    assert not t.entra("RE", "AG.REG. NO RECURSO EXTRAORDINÁRIO", "2")
    assert not t.entra("HC", "", "2") and not t.entra("ARE", "AG.REG.", "2")


def test_situacao_pelo_placar():
    hoje = dt.date(2026, 11, 3)
    base = {"fim": "2026-10-23", "julgado": False, "vista": "", "destaque": "",
            "placar": {"relator": 3, "divergencia": 7, "vista": 0, "fora": 0, "outro": 0}}
    assert t.situacao(base, hoje) | {} == base | {"situacao": "decidido", "maioria": "divergencia"}
    assert t.situacao(base | {"vista": "Edson Fachin"}, hoje)["situacao"] == "vista"
    assert t.situacao(base | {"fim": "2026-11-10"}, hoje)["situacao"] == "em_julgamento"
    poucos = base | {"placar": {"relator": 5, "divergencia": 2, "vista": 0, "fora": 1, "outro": 0}}
    assert t.situacao(poucos, hoje)["situacao"] == "sem_maioria" and t.situacao(poucos, hoje)["maioria"] == ""


def _coletar(tmp_path, monkeypatch):
    util.AVISOS.clear()
    instalar(monkeypatch, FakeGov(anos=[2025]))
    monkeypatch.setattr(t, "PAUSA", 0)
    return t.coletar(tmp_path / "saida", tmp_path / "cache")


def test_coleta_so_plenario_e_acoes_contra_leis(tmp_path, monkeypatch):
    out = _coletar(tmp_path, monkeypatch)
    procs = sorted(j["processo"] for j in out["julgamentos"])
    # HC fica de fora (não é ação contra lei); a ADI 7999 é da Turma; a sessão de 2020 é de outro período
    assert procs == ["ADC 80", "ADI 7001", "ADPF 900 ED"]
    assert out["situacao_fontes"] == {"stf": "ok"}
    assert json.loads((tmp_path / "saida" / "tribunais.json").read_text(encoding="utf-8")) == out


def test_placar_e_maioria(tmp_path, monkeypatch):
    out = _coletar(tmp_path, monkeypatch)
    adi = next(j for j in out["julgamentos"] if j["processo"] == "ADI 7001")
    assert adi["relator"] == "Ana Ficticia"
    assert adi["placar"] == {"relator": 7, "divergencia": 3, "vista": 0, "fora": 1, "outro": 0}
    assert adi["maioria"] == "relator" and adi["situacao"] == "decidido" and adi["resultado"] == "Procedente"
    assert adi["uf"] == "SP" and [p["nome"] for p in adi["partes"]] == ["PARTIDO FICTICIO", "ASSEMBLEIA LEGISLATIVA"]
    assert len(adi["votos"]) == 11 and len({v["ministro"] for v in adi["votos"]}) == 11
    fabio = next(v for v in adi["votos"] if v["ministro"] == "Fabio Ficticio")
    assert fabio["lado"] == "divergencia" and fabio["acompanha"] == "Bruno Ficticio"
    joao = next(v for v in adi["votos"] if v["ministro"] == "Joao Ficticio")  # acompanhou a ressalva de quem ficou com a relatora
    assert joao["lado"] == "relator"
    assert adi["link"] == "https://portal.stf.jus.br/processos/detalhe.asp?incidente=7000001"
    assert all(v["link"].startswith("https://sistemas.stf.jus.br/") for v in adi["votos"])
    # embargos: o voto vem do incidente do recurso, achado pela cadeia
    ed = next(j for j in out["julgamentos"] if j["processo"] == "ADPF 900 ED")
    assert ed["fonte"].endswith(f"sessaoVirtual={7100002}") and ed["placar"]["relator"] == 11
    # em andamento: sem resultado, sem maioria
    adc = next(j for j in out["julgamentos"] if j["processo"] == "ADC 80")
    assert adc["situacao"] == "em_julgamento" and adc["maioria"] == ""


def test_resumo_por_ministro(tmp_path, monkeypatch):
    out = _coletar(tmp_path, monkeypatch)
    m = {x["nome"]: x for x in out["ministros"]}
    assert m["Bruno Ficticio"]["vencido"] == 1 and m["Bruno Ficticio"]["divergencias"] == 1
    assert m["Ana Ficticia"]["com_maioria"] == 2 and m["Ana Ficticia"]["relator"] == 1
    assert m["Lucia Ficticia"]["fora"] == 1


def test_sessao_encerrada_nao_e_lida_de_novo(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "DIAS_RELER", 0)
    _coletar(tmp_path, monkeypatch)
    gov = instalar(monkeypatch, FakeGov(anos=[2025]))
    out = t.coletar(tmp_path / "saida", tmp_path / "cache")
    lidas = [c for c in gov.chamadas if "sessao-virtual" in c]
    assert len(lidas) == 1  # só a sessão em andamento
    assert len(out["julgamentos"]) == 3


def test_stf_fora_do_ar_usa_o_que_ja_leu(tmp_path, monkeypatch):
    _coletar(tmp_path, monkeypatch)
    util.AVISOS.clear()
    instalar(monkeypatch, FakeGov(anos=[2025]).falhar("stf.jus.br", "500"))
    out = t.coletar(tmp_path / "saida", tmp_path / "cache")
    assert out["situacao_fontes"]["stf"] == "reserva" and len(out["julgamentos"]) == 3
    assert any("STF" in a for a in util.AVISOS)


def test_stf_fora_do_ar_sem_copia(tmp_path, monkeypatch):
    util.AVISOS.clear()
    instalar(monkeypatch, FakeGov(anos=[2025]).falhar("stf.jus.br", "html"))
    out = t.coletar(tmp_path / "saida", tmp_path / "cache")
    assert out["situacao_fontes"]["stf"] == "faltando" and out["julgamentos"] == []


def test_processo_sem_placar_404_nao_trava_a_sessao(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "DIAS_RELER", 0)
    util.AVISOS.clear()
    instalar(monkeypatch, FakeGov(anos=[2025]).falhar("sessaoVirtual=7000001", "404"))
    monkeypatch.setattr(t, "PAUSA", 0)
    out = t.coletar(tmp_path / "saida", tmp_path / "cache")
    assert out["situacao_fontes"]["stf"] == "ok" and "ADI 7001" not in [j["processo"] for j in out["julgamentos"]]
    assert list((tmp_path / "cache" / "tribunais" / "stf").glob("sessao-*.json"))  # encerrada guardada de vez
