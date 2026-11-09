"""Dia a dia de cada parlamentar: onde registrou presença e o que gastou em cada data.

Câmara (presença em sessões do Plenário, reuniões de comissão, audiências e outros eventos):
- A API tem o dado certo, mas um evento por vez: /eventos/{id}/deputados traz quem registrou presença. São mais de
  3 mil eventos por ano, e a consulta por deputado (/deputados/{id}/eventos) não serve: ela lista também eventos em
  que o deputado não registrou presença, inclusive cancelados (conferido em novembro de 2026, deputado 220574,
  maio de 2025: 77 eventos na consulta por deputado, 74 com presença; os 3 a mais não têm o deputado em
  /eventos/{id}/deputados).
- Por isso usamos os arquivos anuais dos dados abertos da Câmara, que são a mesma publicação da API em um arquivo só:
  eventos-{ano}.csv (data, tipo, local), eventosPresencaDeputados-{ano}.csv (quem registrou presença em cada evento)
  e eventosOrgaos-{ano}.csv (comissão de cada evento). Conferido: os eventos 76052 e 76214 têm exatamente as mesmas
  pessoas no arquivo e na API. A verificação diária (verificar.py, presenca_camara) sorteia eventos e confere de novo.

Senado: a presença no Plenário vem das votações nominais que o coletor já lê pela API (/votacao): presente, em missão,
de licença ou ausente em cada votação.

Gastos: as notas da cota com a data de emissão; a cidade e a UF do fornecedor vêm do cadastro do CNPJ na Receita.

Pontos para conferir: dia com presença registrada num evento dentro da Câmara, em Brasília, e nota de refeição do
próprio deputado (a cota da Câmara só paga a alimentação do parlamentar) de um restaurante de outro estado na mesma
data. Quando também há presença em Brasília no dia anterior e no seguinte, o ponto é marcado como "cercado" (a viagem
no mesmo dia fica menos provável). Conferido com um caso real: nota de restaurante em São Paulo emitida em 11/06/2025
às 22h15, de um deputado com presença em Brasília em 10, 11 e 12/06/2025 (/eventos/76809/deputados). É um fato para conferir, não uma acusação: a nota pode ter data diferente do consumo, o deputado pode ter
viajado no mesmo dia e a Câmara aceita, em algumas reuniões, presença registrada pelo aplicativo. Sessões do Plenário
"semipresenciais" (que aceitam voto à distância) não contam como prova de estar em Brasília. No Senado o voto pode
ser dado à distância e os dados não dizem onde a pessoa estava; por isso o Senado não tem pontos para conferir.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from collections import defaultdict
from pathlib import Path

from .camara import _validade, pid
from .categorias import tema_de
from .util import avisar, doc_kind, download, eh_csv, read_csv_file

log = logging.getLogger("sa_etl.agenda")

ARQ = "https://dadosabertos.camara.leg.br/arquivos/{k}/csv/{k}-{ano}.csv"
ARQUIVOS = ("eventos", "eventosPresencaDeputados", "eventosOrgaos")
LINK_EVENTO = "https://www.camara.leg.br/evento-legislativo/{id}"
API_PRESENCA = "https://dadosabertos.camara.leg.br/api/v2/eventos/{id}/deputados"
FONTE_CAMARA = "https://dadosabertos.camara.leg.br/swagger/api.html#/Eventos/deputadosEvento"

# Descrição que diz que a sessão aceita participação à distância
_A_DISTANCIA = re.compile(r"semipresencial|remot|virtual|videoconfer", re.I)
# Atividade principal (CNAE) de quem vende refeição: restaurantes, lanchonetes, bares, padarias, bufês
_RAMO_REFEICAO = re.compile(r"^(restaurantes|lanchonetes|bares |padaria|servi[cç]os ambulantes de alimenta|cantinas|"
                            r"servi[cç]os de alimenta[cç][aã]o para eventos)", re.I)


def _titulo(descricao: str) -> str:
    """Primeira linha da descrição, sem espaços repetidos (a descrição às vezes traz a lista de convidados)."""
    linha = next((x.strip() for x in (descricao or "").splitlines() if x.strip()), "")
    linha = re.sub(r"\s+", " ", linha)
    return linha if len(linha) <= 160 else linha[:157].rstrip() + "..."


def parse_eventos(eventos_rows, presenca_rows, orgaos_rows, ids: set[str]) -> dict[str, list[dict]]:
    """Presença de cada deputado: politico -> eventos (data, hora, tipo, comissão, título, local, em Brasília, id)."""
    orgaos: dict[str, list[str]] = defaultdict(list)
    for r in orgaos_rows:
        s = (r.get("siglaOrgao") or "").strip()
        if s and s not in orgaos[r.get("idEvento") or ""]:
            orgaos[r.get("idEvento") or ""].append(s)
    eventos: dict[str, dict] = {}
    for r in eventos_rows:
        i = (r.get("id") or "").strip()
        ini = (r.get("dataHoraInicio") or "").strip()
        if not i.isdigit() or not re.match(r"\d{4}-\d{2}-\d{2}", ini) or "cancel" in (r.get("situacao") or "").lower():
            continue
        externo = (r.get("localExterno") or "").strip()
        camara = (r.get("localCamara.nome") or "").strip()
        titulo = _titulo(r.get("descricao") or "")
        eventos[i] = {
            "id": int(i), "data": ini[:10], "hora": ini[11:16], "tipo": (r.get("descricaoTipo") or "").strip(),
            "orgao": "/".join(orgaos.get(i, [])), "titulo": titulo, "local": externo or camara,
            # Prova de estar em Brasília: evento numa sala da Câmara (sem local externo) que não aceita participação à
            # distância segundo a própria descrição
            "brasilia": bool(camara and not externo and not _A_DISTANCIA.search(titulo)),
        }
    out: dict[str, list[dict]] = defaultdict(list)
    vistos: set[tuple[str, str]] = set()
    for r in presenca_rows:
        dep, ev = (r.get("idDeputado") or "").strip(), (r.get("idEvento") or "").strip()
        if not dep.isdigit() or ev not in eventos or pid(dep) not in ids or (dep, ev) in vistos:
            continue
        vistos.add((dep, ev))
        out[pid(dep)].append(eventos[ev])
    for evs in out.values():
        evs.sort(key=lambda e: (e["data"], e["hora"], e["id"]))
    return dict(out)


def presenca_camara(anos: list[int], ids: set[str], cache: Path) -> dict[str, list[dict]]:
    """Baixa os arquivos de eventos de cada ano. Um ano faltando não para o resto (o calendário fica sem a presença)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for ano in anos:
        try:
            f = {k: download(ARQ.format(k=k, ano=ano), cache / f"camara-{k}-{ano}.csv", max_horas=_validade(ano),
                             validar=eh_csv) for k in ARQUIVOS}
        except Exception as e:  # noqa: BLE001
            log.warning("Presença na Câmara %s indisponível: %s", ano, e)
            avisar(f"Presença na Câmara {ano}: os arquivos de eventos não puderam ser baixados; o calendário dia a dia "
                   f"dos deputados está sem a presença deste ano")
            continue
        p = parse_eventos(read_csv_file(f["eventos"]), read_csv_file(f["eventosPresencaDeputados"]),
                          read_csv_file(f["eventosOrgaos"]), ids)
        log.info("Câmara: presença de %d deputados em %d registros em %s", len(p), sum(map(len, p.values())), ano)
        for k, evs in p.items():
            out[k] += evs
    return dict(out)


def _refeicao(d: dict, emp: dict | None) -> bool:
    """Nota de refeição: tipo de despesa da Câmara "alimentação do parlamentar" ou fornecedor do ramo de refeições."""
    return tema_de(d.get("categoria") or "") == "Alimentação" or bool(emp and _RAMO_REFEICAO.match(emp.get("atividade") or ""))


def montar_ano(casa: str, ano: int, eventos: list[dict], votos: list[dict], votacao_por_id: dict,
               despesas: list[dict], emps: dict[str, dict]) -> dict | None:
    """Calendário de um parlamentar num ano, para p/agenda/{id}-{ano}.json.

    dias: data -> {"e": eventos [hora, tipo, comissão, título, local, em Brasília (1/0), id], "v": votos [votação, voto]}
    lugares: CNPJ -> [cidade, UF, atividade] dos fornecedores das notas do ano (cadastro da Receita)
    conferir: dias com presença em Brasília e refeição em restaurante de outro estado (só Câmara; ver o topo do arquivo)
    """
    a = str(ano)
    dias: dict[str, dict] = defaultdict(lambda: {"e": [], "v": []})
    for e in eventos:
        if e["data"].startswith(a):
            dias[e["data"]]["e"].append([e["hora"], e["tipo"], e["orgao"], e["titulo"], e["local"], int(e["brasilia"]), e["id"]])
    for v in votos:
        vt = votacao_por_id.get(v["votacao"])
        if vt and (vt.get("data") or "").startswith(a):
            dias[vt["data"][:10]]["v"].append([v["votacao"], v["voto"]])
    notas = [d for d in despesas if not d.get("sem_nota") and (d.get("data") or "").startswith(a)]
    lugares = {}
    for d in notas:
        emp = emps.get(d["doc"]) if doc_kind(d["doc"]) == "cnpj" else None
        if emp and (emp.get("municipio") or emp.get("uf")):
            lugares[d["doc"]] = [emp.get("municipio") or "", emp.get("uf") or "", emp.get("atividade") or ""]
    if not dias and not notas:
        return None
    conferir = []
    em_bsb = {e["data"] for e in eventos if e["brasilia"]}
    if casa == "camara":
        for d in sorted(notas, key=lambda d: (d["data"], d["fornecedor"])):
            dia = dias.get(d["data"][:10])
            emp = emps.get(d["doc"]) if doc_kind(d["doc"]) == "cnpj" else None
            if not dia or not emp or not emp.get("uf") or emp["uf"] == "DF" or not _refeicao(d, emp):
                continue
            em_brasilia = [e for e in dia["e"] if e[5]]
            if em_brasilia:
                conferir.append({"data": d["data"][:10], "fornecedor": d["fornecedor"], "doc": d["doc"], "valor": d["valor"],
                                 "url": d.get("url") or "", "categoria": d["categoria"],
                                 "cidade": emp.get("municipio") or "", "uf": emp["uf"],
                                 "eventos": [e[6] for e in em_brasilia],
                                 # também em Brasília no dia anterior e no seguinte: a viagem no mesmo dia fica menos provável
                                 "cercado": _vizinho(d["data"][:10], -1) in em_bsb and _vizinho(d["data"][:10], 1) in em_bsb})
    com_presenca = sum(1 for x in dias.values() if x["e"] or any(_presente(v[1]) for v in x["v"]))
    return {
        "ano": ano, "casa": casa,
        "dias": {k: {kk: vv for kk, vv in x.items() if vv} for k, x in sorted(dias.items())},
        "lugares": lugares, "conferir": conferir,
        "resumo": {"dias_presenca": com_presenca, "dias_gastos": len({d["data"][:10] for d in notas}),
                   "conferir": len({c["data"] for c in conferir}),
                   "conferir_cercado": len({c["data"] for c in conferir if c["cercado"]})},
        "fontes": ({"presenca": FONTE_CAMARA, "arquivos": "https://dadosabertos.camara.leg.br/swagger/api.html#staticfile"}
                   if casa == "camara" else {"presenca": "https://legis.senado.leg.br/dadosabertos/docs/ui/index.html#/Vota%C3%A7%C3%A3o"}),
    }


def _vizinho(dia: str, n: int) -> str:
    return (dt.date.fromisoformat(dia) + dt.timedelta(days=n)).isoformat()


def _presente(voto: str) -> bool:
    return voto not in ("Ausente", "Licença", "Em missão", "Em atividade parlamentar", "—", "")
