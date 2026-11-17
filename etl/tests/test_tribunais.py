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


# ---------------------------------------------------------------- o que está em julgamento (relatório do relator)

def test_o_que_esta_em_julgamento_vem_do_relatorio(tmp_path, monkeypatch):
    out = _coletar(tmp_path, monkeypatch)
    adi = next(j for j in out["julgamentos"] if j["processo"] == "ADI 7001")
    o = adi["objeto"]
    # a frase oficial, sem o "1." e sem "A SENHORA MINISTRA ... (Relatora):"; as linhas do PDF juntas
    assert o["texto"] == ("Trata-se de ação direta de inconstitucionalidade, com pedido de medida cautelar, ajuizada pelo "
                          "Partido Ficticio em face da Lei n. 1.234, de 5 de maio de 2025, do Estado de São Paulo, que "
                          "proíbe o uso de celular nas escolas estaduais.")
    assert o["simples"].startswith("Ação direta de inconstitucionalidade (ADI: pede que o STF derrube")
    assert "com pedido de decisão urgente, apresentada pelo Partido Ficticio contra a Lei 1.234/2025" in o["simples"]
    assert o["link"] == "https://digital.stf.jus.br/decisoes-monocraticas/api/public/votos/9002/conteudo.pdf"
    assert "relatorio" not in adi  # o link vai dentro de "objeto"
    ed = next(j for j in out["julgamentos"] if j["processo"] == "ADPF 900 ED")
    assert ed["objeto"]["simples"].startswith("Embargos de declaração (pedido para esclarecer ou corrigir")
    # sem relatório publicado: sem "objeto" (o site mostra a explicação do tipo de ação)
    adc = next(j for j in out["julgamentos"] if j["processo"] == "ADC 80")
    assert "objeto" not in adc


def test_relatorio_lido_uma_vez_so(tmp_path, monkeypatch):
    _coletar(tmp_path, monkeypatch)
    gov = instalar(monkeypatch, FakeGov(anos=[2025]))
    out = t.coletar(tmp_path / "saida", tmp_path / "cache")
    assert not [c for c in gov.chamadas if "digital.stf.jus.br" in c]
    assert next(j for j in out["julgamentos"] if j["processo"] == "ADI 7001")["objeto"]["texto"].startswith("Trata-se")


def test_julgamento_guardado_antes_acha_o_relatorio_pela_lista(tmp_path, monkeypatch):
    """Sessões guardadas antes desta versão não têm o link: vem do serviço de votação, pela lista do julgamento."""
    monkeypatch.setattr(t, "PAUSA", 0)
    instalar(monkeypatch, FakeGov(anos=[2025]))
    j = {"id": "stf-7000001-9002", "classe": "ADI", "processo": "ADI 7001",
         "fonte": "https://sistemas.stf.jus.br/repgeral/votacao?sessaoVirtual=7000001"}
    out, faltam = t.com_objeto([j], tmp_path)
    assert faltam == 0 and out[0]["objeto"]["link"].endswith("/votos/9002/conteudo.pdf")


def test_relatorio_fora_do_ar_tenta_de_novo_depois(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "PAUSA", 0)
    instalar(monkeypatch, FakeGov(anos=[2025]).falhar("digital.stf.jus.br", "500"))
    j = {"id": "stf-7000001-9002", "classe": "ADI", "processo": "ADI 7001", "relatorio":
         "https://digital.stf.jus.br/decisoes-monocraticas/api/public/votos/9002/conteudo.pdf"}
    out, faltam = t.com_objeto([j], tmp_path)
    assert faltam == 1 and "objeto" not in out[0] and "relatorio" not in out[0]
    assert not list((tmp_path / "stf" / "relatorios").glob("*.json"))  # nada guardado: a próxima coleta lê de novo


def test_re_e_acao_rescisoria_sem_frase_do_relatorio(tmp_path, monkeypatch):
    """Em RE e AR o relatório pode citar pessoas comuns pelo nome: a frase não entra e o PDF nem é baixado."""
    gov = instalar(monkeypatch, FakeGov(anos=[2025]))
    js = [{"id": "stf-1-2", "classe": c, "processo": f"{c} 1", "relatorio": "https://digital.stf.jus.br/x.pdf"} for c in ("RE", "AR")]
    out, faltam = t.com_objeto(js, tmp_path)
    assert faltam == 0 and all("objeto" not in j and "relatorio" not in j for j in out)
    assert not [c for c in gov.chamadas if "digital.stf.jus.br" in c]


def test_frase_do_relatorio_como_o_stf_escreve():
    cab = "ADI 8042 MC-REF / DF\n"
    # título com letras separadas, ministro sem espaços, item "1.", corte na ementa copiada
    assert t.objeto_do_relatorio("REQTE.(S) : X\nRELATÓRIO\nOSENHORMINISTRONUNESMARQUES: 1. Trata-se de embargos de declaração "
                                 "opostos pela autora desta ação direta, a Federação Ficticia, contra acórdão deste SUPREMO, "
                                 "assim ementado: Ementa: DIREITO CONSTITUCIONAL.") == (
        "Trata-se de embargos de declaração opostos pela autora desta ação direta, a Federação Ficticia, contra acórdão deste SUPREMO […]")
    # palavras grudadas (PDF sem espaços): melhor nada do que um texto ilegível
    assert t.objeto_do_relatorio("RELATÓRIO O SENHOR MINISTRO X (RELATOR): Trata-sedeembargosdedeclaraçãoopostoscontraacórdão "
                                 "em que esta Corte decidiu a questão de modo definitivo para todos.") == ""
    # sem o título: nada
    assert t.objeto_do_relatorio(cab + "Trata-se de ação direta de inconstitucionalidade contra a Lei n. 1/2020.") == ""
    # frase longa demais: cortada na palavra, com […]
    longa = t.objeto_do_relatorio("RELATÓRIO A SENHORA MINISTRA Y (Relatora): Trata-se de ação " + "muito " * 200 + "longa.")
    assert longa.endswith(" […]") and len(longa) <= t.MAX_OBJETO + 4


def test_palavras_simples():
    s = t.em_palavras_simples("O partido Rede Sustentabilidade interpôs agravo interno de decisão em que não conheci da ação "
                              "declaratória de constitucionalidade, proposta contra os §§ 1º e 1º-A do art. 3º da Resolução n. 81/2009.")
    assert s.startswith("O partido Rede Sustentabilidade apresentou agravo interno (recurso aos 11 ministros contra a decisão de um ministro sozinho)")
    assert "não aceitei analisar a ação declaratória de constitucionalidade, apresentada contra" in s
    # só o primeiro tipo de ação ganha a explicação
    assert s.count("(") == 1
    assert t.em_palavras_simples("Trata-se de ADI contra a Emenda Constitucional nº. 141, de 16 de outubro de 2026.") == (
        "ADI contra a Emenda Constitucional 141/2026.")
    assert t.em_palavras_simples("Frase sem juridiquês nenhum para trocar aqui.") == ""


def test_validar_confere_o_resumo(tmp_path, monkeypatch):
    from sa_etl import validar as v
    out = _coletar(tmp_path, monkeypatch)
    r = v.Resultado()
    v._conferir_tribunais(tmp_path / "saida", r)
    assert r.erros == []
    adi = next(j for j in out["julgamentos"] if j["processo"] == "ADI 7001")
    adi["objeto"]["link"] = "https://exemplo.com/x.pdf"
    out["julgamentos"].append({**adi, "id": "stf-re", "classe": "RE", "objeto": {"texto": "Recurso de 123.456.789-09", "simples": "", "link": "https://digital.stf.jus.br/x.pdf"}})
    (tmp_path / "saida" / "tribunais.json").write_text(json.dumps(out), encoding="utf-8")
    r = v.Resultado()
    v._conferir_tribunais(tmp_path / "saida", r)
    assert any("sem o link do relatório" in e for e in r.erros)
    assert any("pode citar pessoas comuns" in e for e in r.erros)
    assert any("parecido com CPF" in e for e in r.erros)
