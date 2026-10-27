"""Verificação independente (sa_etl/verificar.py): a conta da confiança, a leitura das atas e, principalmente, que
nada aparece como conferido sem ter sido conferido de verdade."""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from fakegov import FakeGov
from sa_etl import verificar as vf

HOJE = dt.date(2026, 10, 27)


# ---------------------------------------------------------------- estatística

def test_erro_maximo_sem_divergencia_regra_conhecida():
    # com zero erros, o limite de 95% é 1 - 0,05^(1/n) (perto de 3/n, a "regra de três")
    assert vf.erro_maximo(300, 0) == pytest.approx(1 - 0.05 ** (1 / 300))
    assert vf.erro_maximo(300, 0) == pytest.approx(3 / 300, rel=0.01)
    assert vf.erro_maximo(0, 0) is None


def test_para_99_99_precisa_de_cerca_de_30_mil():
    n = vf.conferidos_para(0.9999)
    assert 29_000 < n < 31_000
    assert 1 - vf.erro_maximo(n, 0) >= 0.9999
    assert 1 - vf.erro_maximo(n - 1, 0) < 0.9999


def test_erro_maximo_cresce_com_divergencias():
    a, b, c = vf.erro_maximo(1000, 0), vf.erro_maximo(1000, 1), vf.erro_maximo(1000, 10)
    assert a < b < c < 1
    assert b > 1 / 1000  # o limite superior fica acima da taxa observada
    assert vf.erro_maximo(10, 10) == 1.0


# ---------------------------------------------------------------- atas do Senado

@pytest.mark.parametrize("texto, esperado", [
    ("com o seguinte resultado: sim – 65; não – 1, Presidente – 1; abstenção – 0; total – 67.", (65, 1)),
    ("com o seguinte resultado: Sim 54  Não 13, Presidente 1, Total 68.", (54, 13)),
    ("com o seguinte resultado: Sim: 72, Pres.: 1, Total: 73.", (72, 0)),
    ("Sim - 38, Não - 4, Abstenções - 1, Total - 43.", (38, 4)),
    ("Aprovado o requerimento. Sim: 72 ... depois, Sim: 70, Total: 71.", None),  # dois resultados: ambíguo
    ("Aprovado o projeto.", None),
])
def test_placar_da_ata(texto, esperado):
    assert vf.placar_da_ata(texto) == esperado


# ---------------------------------------------------------------- coleta inteira + fontes oficiais simuladas

@pytest.fixture
def saida(coleta):
    coleta.usar(FakeGov(anos=(2025,)))
    s = coleta.rodar(anos=(2025,))
    _com_placar_oficial(s)
    return s


def _ler(f: Path):
    return json.loads(f.read_text(encoding="utf-8"))


def _com_placar_oficial(s: Path) -> None:
    """O FakeGov não traz o placar oficial; aqui ele é a contagem de todos os votos (como na Câmara e no Senado)."""
    lista = _ler(s / "votacoes.json")
    for v in lista:
        d = _ler(s / "v" / f"{v['id']}.json")
        d["placar_casa"] = v["placar_casa"] = {"sim": d["sim"], "nao": d["nao"]}
        (s / "v" / f"{v['id']}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (s / "votacoes.json").write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")


class Oficial:
    """Responde no lugar das APIs oficiais usadas na verificação, a partir dos próprios arquivos do site (ou seja,
    tudo bate). Cada teste estraga uma parte para ver a verificação pegar."""

    def __init__(self, s: Path) -> None:
        self.s = s
        self.pedidos: list[str] = []
        self.despesas_vazias = False
        self.fora_do_ar: set[str] = set()
        self.voto_trocado: str | None = None
        self.senado_total_diferente = 0.0
        self.mes: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
        por_cnpj = defaultdict(float)
        for f in (s / "e").glob("*.json"):
            for x in _ler(f).get("por_mes") or []:
                if x["politico"].startswith("dep-"):
                    k = (x["politico"].removeprefix("dep-"), x["ano"], x["mes"])
                    self.mes[k].append({"cnpjCpfFornecedor": f.stem, "valorLiquido": x["valor"]})
                    por_cnpj[k] += x["valor"]
        for p in _ler(s / "politicos.json"):
            if p["casa"] != "camara":
                continue
            for ano, a in (_ler(s / "p" / f"{p['id']}.json").get("anos") or {}).items():
                for m in a.get("meses") or []:
                    k = (p["id"].removeprefix("dep-"), int(ano), m["mes"])
                    resto = round(m["valor"] - por_cnpj[k], 2)
                    if abs(resto) > 0.001:
                        self.mes[k].append({"cnpjCpfFornecedor": "", "valorLiquido": resto})

    def __call__(self, url, params=None, headers=None, timeout=None, **kw):
        self.pedidos.append(url)
        for site in self.fora_do_ar:
            if site in url:
                raise RuntimeError(f"Não foi possível baixar {url}: 503")
        if m := re.search(r"/deputados/(\d+)/despesas\?ano=(\d+)&mes=(\d+)", url):
            k = (m.group(1), int(m.group(2)), int(m.group(3)))
            return {"dados": [] if self.despesas_vazias else self.mes.get(k, []), "links": []}
        if m := re.search(r"/votacoes/([^/]+)/votos$", url):
            d = _ler(self.s / "v" / f"cd-{m.group(1)}.json")
            dados = [{"tipoVoto": x["voto"], "deputado_": {"id": int(x["politico"].removeprefix("dep-"))}} for x in d["votos"]]
            if self.voto_trocado and dados:
                dados[0]["tipoVoto"] = self.voto_trocado
            return {"dados": dados, "links": []}
        if url.endswith("/votacao"):
            out = []
            for f in (self.s / "v").glob("sf-*.json"):
                d = _ler(f)
                if d["data"] == params["dataInicio"]:
                    votos = [{"codigoParlamentar": int(x["politico"].removeprefix("sen-")),
                              "siglaVotoParlamentar": {"Sim": "Sim", "Não": "Não"}.get(x["voto"], x["voto"])} for x in d["votos"]]
                    out.append({"codigoSessaoVotacao": int(d["id"].removeprefix("sf-")), "votos": votos,
                                "informeLegislativo": {"texto": f"Aprovado, com o seguinte resultado: Sim - {d['placar_casa']['sim']}; "
                                                                f"Não - {d['placar_casa']['nao']}; Total - 70."}})
            return out
        if m := re.search(r"/senadores/(\d+)/recursos-utilizados\?ano=(\d+)", url):
            p = next(p for p in _ler(self.s / "politicos.json") if p["id"] == f"sen-{m.group(1)}")
            return {"data": [{"cotas": {"totalValor": p["por_ano"][m.group(2)]["total"] + self.senado_total_diferente}}]}
        if m := re.search(r"/cnpj/v1/(\d{14})", url):
            e = _ler(self.s / "e" / f"{m.group(1)}.json")
            return {"razao_social": (e.get("empresa") or {}).get("razao_social") or "",
                    "qsa": [{"nome_socio": x["nome"]} for x in e.get("socios") or []]}
        if url == vf.PORTAL_EMENDAS:
            if params["pagina"] > 1:
                return []
            br = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
            for ano in _ler(self.s / "emendas" / "anos.json")["anos"]:
                for a in _ler(self.s / "emendas" / f"{ano}.json")["autores"]:
                    if a["nome"] == params["nomeAutor"] and ano == params["ano"]:
                        return [{"nomeAutor": a["nome"], "valorEmpenhado": br(a["empenhado"]), "valorPago": br(a["pago"]),
                                 "valorRestoPago": "0,00"}]
            return []
        raise AssertionError(f"pedido inesperado: {url}")


def _rodar(saida: Path, of: Oficial, chave="chave-de-teste") -> dict:
    return vf.verificar(saida, hoje=HOJE, chave=chave, buscar=of, minutos=5)


def _checagem(v: dict, cid: str) -> dict:
    return next(c for c in v["checagens"] if c["id"] == cid)


def test_tudo_batendo_fica_conferido(saida):
    v = _rodar(saida, Oficial(saida))
    for cid in ("cota_camara_mes", "cota_camara_empresa", "cota_senado_ano", "votos_camara", "placar_camara",
                "votos_senado", "placar_senado_ata", "empresas_receita", "emendas_autor"):
        c = _checagem(v, cid)
        assert c["status"] == "conferido", (cid, c)
        assert c["conferidos"] > 0 and c["divergentes"] == 0
    assert v["secoes"]["votacoes"]["status"] == "conferido"
    assert v["secoes"]["incentivos"]["status"] == "sem_segunda_fonte"
    # a cota tem uma checagem que não roda sem as páginas oficiais (coleta sem recursos): fica "em parte", não "conferido"
    assert v["secoes"]["cota"]["status"] == "parcial"
    a = v["secoes"]["votacoes"]["acumulado"]
    assert a["conferidos"] > 0 and a["divergentes"] == 0 and 0 < a["certos_min"] < 1


def test_divergencia_aparece_com_link(saida):
    of = Oficial(saida)
    of.voto_trocado = "Obstrução"
    of.senado_total_diferente = 100.0
    v = _rodar(saida, of)
    c = _checagem(v, "votos_camara")
    assert c["status"] == "divergente" and c["divergencias"]
    assert all(d["fonte"].startswith("https://") for d in c["divergencias"])
    assert v["secoes"]["votacoes"]["status"] == "divergente"
    assert _checagem(v, "cota_senado_ano")["status"] == "divergente"
    assert v["secoes"]["cota"]["status"] == "divergente"


def test_api_sem_dados_nunca_vira_conferido(saida):
    """Já aconteceu: a API de despesas da Câmara respondendo vazio para todo mundo. Não é divergência nem conferência."""
    of = Oficial(saida)
    of.despesas_vazias = True
    v = _rodar(saida, of)
    for cid in ("cota_camara_mes", "cota_camara_empresa"):
        c = _checagem(v, cid)
        assert c["status"] == "nao_conferido" and c["conferidos"] == 0, c
        assert "sem nenhuma despesa" in c["motivo"]


def test_fonte_fora_do_ar_fica_nao_conferido(saida):
    of = Oficial(saida)
    of.fora_do_ar = {"brasilapi.com.br", "api.portaldatransparencia.gov.br", "dadosabertos.camara.leg.br"}
    v = _rodar(saida, of)
    for cid in ("empresas_receita", "emendas_autor", "votos_camara", "cota_camara_mes"):
        assert _checagem(v, cid)["status"] == "nao_conferido", cid
    assert v["secoes"]["empresas"]["status"] == "nao_conferido"
    assert v["secoes"]["emendas"]["status"] == "nao_conferido"


def test_sem_chave_do_portal_nao_confere_emendas(saida):
    v = _rodar(saida, Oficial(saida), chave="")
    c = _checagem(v, "emendas_autor")
    assert c["status"] == "nao_conferido" and "chave" in c["motivo"]


def test_mes_aberto_nao_e_conferido(saida):
    """Meses recentes ainda recebem notas atrasadas: nenhum pedido de cota para eles."""
    of = Oficial(saida)
    vf.verificar(saida, hoje=dt.date(2025, 12, 15), chave="", buscar=of, minutos=5)
    meses = [re.search(r"ano=(\d+)&mes=(\d+)", u).groups() for u in of.pedidos if "/despesas?" in u]
    assert meses and all(int(m) <= 10 for a, m in meses)


def test_historico_soma_os_dias_e_descarta_os_antigos(saida):
    of = Oficial(saida)
    ontem = vf.verificar(saida, hoje=HOJE - dt.timedelta(days=1), chave="", buscar=of, minutos=5)
    hoje = vf.verificar(saida, anterior=ontem, hoje=HOJE, chave="", buscar=of, minutos=5)
    s = hoje["secoes"]["votacoes"]
    assert s["acumulado"]["dias"] == 2
    assert s["acumulado"]["conferidos"] == ontem["secoes"]["votacoes"]["hoje"]["conferidos"] + s["hoje"]["conferidos"]
    # rodar de novo no mesmo dia substitui o dia, não soma duas vezes
    de_novo = vf.verificar(saida, anterior=hoje, hoje=HOJE, chave="", buscar=of, minutos=5)
    assert de_novo["secoes"]["votacoes"]["acumulado"]["dias"] == 2
    # mais de 90 dias depois, o histórico antigo sai da conta
    longe = vf.verificar(saida, anterior=hoje, hoje=HOJE + dt.timedelta(days=200), chave="", buscar=of, minutos=5)
    assert longe["secoes"]["votacoes"]["acumulado"]["dias"] == 1


def test_mesma_data_mesma_amostra(saida):
    a = _rodar(saida, Oficial(saida))
    b = _rodar(saida, Oficial(saida))
    assert [c["exemplos"] for c in a["checagens"]] == [c["exemplos"] for c in b["checagens"]]


def test_checagem_com_defeito_nao_derruba_as_outras(saida, monkeypatch):
    def quebra(*a, **k):
        raise KeyError("campo novo")
    monkeypatch.setattr(vf, "empresas_receita", quebra)
    v = _rodar(saida, Oficial(saida))
    assert _checagem(v, "empresas_receita")["status"] == "nao_conferido"
    assert _checagem(v, "votos_camara")["status"] == "conferido"


def test_relatorio_e_arquivo(saida, tmp_path):
    v = _rodar(saida, Oficial(saida))
    txt = vf.relatorio(v)
    assert "Verificação independente" in txt and "Votações" in txt
    json.dumps(v)  # o arquivo do site precisa ser JSON puro



# ---------------------------------------------------------------- placar oficial (a verificação achou o placar incompleto)

def test_placar_oficial_do_senado_conta_quem_saiu_do_cargo():
    from sa_etl import senado
    item = {"codigoSessaoVotacao": 1, "votacaoSecreta": "N", "dataSessao": "2025-05-21",
            "votos": [{"codigoParlamentar": 1, "siglaVotoParlamentar": "Sim"},
                      {"codigoParlamentar": 2, "siglaVotoParlamentar": "Sim"},  # já saiu do cargo
                      {"codigoParlamentar": 3, "siglaVotoParlamentar": "Não"}]}
    vs, votos = senado.parse_votacoes([item], {"sen-1", "sen-3"})
    assert vs[0]["placar_oficial"] == {"sim": 2, "nao": 1}
    assert len(votos) == 2
    # quando o Senado publica o total, vale o total publicado
    vs, _ = senado.parse_votacoes([{**item, "totalVotosSim": 40, "totalVotosNao": 1}], {"sen-1"})
    assert vs[0]["placar_oficial"] == {"sim": 40, "nao": 1}


def test_placar_oficial_da_camara_vem_do_arquivo():
    from sa_etl import camara
    vot = [{"id": "1-1", "siglaOrgao": "PLEN", "data": "2025-01-01", "aprovacao": "1", "votosSim": "300", "votosNao": "100"}]
    votos = [{"idVotacao": "1-1", "deputado_id": "10", "voto": "Sim", "deputado_siglaPartido": "PT"}]
    vs, _ = camara.parse_votacoes(vot, votos, [], [], {"dep-10"})
    assert vs[0]["placar_oficial"] == {"sim": 300, "nao": 100}
    vs, _ = camara.parse_votacoes([{**vot[0], "votosSim": ""}], votos, [], [], {"dep-10"})
    assert "placar_oficial" not in vs[0]
