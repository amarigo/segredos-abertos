"""Câmara dos Deputados: deputados (em exercício e os que já saíram na legislatura), cota parlamentar (CEAP) e votações nominais do plenário.

Fontes:
- API: https://dadosabertos.camara.leg.br/api/v2/deputados (e ?idLegislatura=N, /deputados/{id})
- Cota anual: https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
- Votações: https://dadosabertos.camara.leg.br/arquivos/votacoes*/csv/*-{ano}.csv
"""
from __future__ import annotations

import datetime as dt
import logging
from urllib.parse import quote
from collections import defaultdict
from pathlib import Path

from .categorias import categoria_curta, grupo_de
from .util import avisar, com_copia, digits, fora_da_lista, download, eh_csv, eh_zip, get_json, id_seguro, read_csv_file, to_float, url_segura

log = logging.getLogger("sa_etl.camara")

API = "https://dadosabertos.camara.leg.br/api/v2"
COTA_URL = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
ARQ = "https://dadosabertos.camara.leg.br/arquivos"
VOT_URLS = {
    "votacoes": ARQ + "/votacoes/csv/votacoes-{ano}.csv",
    "votos": ARQ + "/votacoesVotos/csv/votacoesVotos-{ano}.csv",
    "orientacoes": ARQ + "/votacoesOrientacoes/csv/votacoesOrientacoes-{ano}.csv",
    "proposicoes": ARQ + "/votacoesProposicoes/csv/votacoesProposicoes-{ano}.csv",
}


def pid(dep_id: str | int) -> str:
    return f"dep-{dep_id}"


def legislatura(ano: int, mes: int) -> int:
    """Número da legislatura num mês. Cada uma dura 4 anos e começa em 1º de fevereiro (a 57ª em 2023; Constituição,
    art. 44). Vale para a Câmara e para o Senado."""
    return 57 + (ano - 2023 - (mes == 1)) // 4


def legislaturas(anos: list[int]) -> list[int]:
    """Legislaturas que têm algum mês nos anos pedidos."""
    return sorted({legislatura(a, m) for a in anos for m in (1, 12)})


def _paginas(url: str, params: dict | None) -> list[dict]:
    out: list[dict] = []
    while url:
        data = get_json(url, params=params)
        out += data.get("dados", [])
        url = next((l["href"] for l in data.get("links", []) if l.get("rel") == "next"), None)
        params = None
    return out


def _deputado(d: dict, em_exercicio: bool = True) -> dict | None:
    if not str(d.get("id", "")).isdigit():
        log.warning("Câmara: deputado com id inválido ignorado: %r", d.get("id"))
        return None
    return {
        "id": pid(d["id"]),
        "casa": "camara",
        "cargo": "Deputado(a) Federal",
        "nome": (d.get("nomeEleitoral") or d.get("nome") or "").strip(),
        "partido": d.get("siglaPartido") or "",
        "uf": d.get("siglaUf") or "",
        "foto": url_segura(d.get("urlFoto")),
        "fonte": f"https://www.camara.leg.br/deputados/{d['id']}",
        "em_exercicio": em_exercicio,
    }


def deputados(anos: list[int] | None = None, cache: Path | None = None) -> list[dict]:
    """Deputados em exercício hoje e, com `anos`, também todos que tiveram mandato nas legislaturas desses anos.

    A lista sem filtro da API (/deputados) só traz quem está no cargo hoje. Quem saiu no meio do mandato (suplente
    que devolveu a vaga ao titular, licenciado, cassado, quem renunciou ou morreu) não aparece nela, e os gastos e
    votos dessa pessoa sumiam do site. Por isso pedimos também /deputados?idLegislatura=N, que traz todos que
    passaram pela legislatura, e /deputados/{id} de quem não está mais no cargo, para o nome, o partido e a situação
    de hoje (a lista da legislatura repete a pessoa uma vez por nome ou partido que ela já usou)."""
    out: list[dict] = []
    vistos: set[str] = set()
    for d in _paginas(f"{API}/deputados", {"itens": 100, "ordem": "ASC", "ordenarPor": "nome"}):
        x = _deputado(d)
        if x and x["id"] not in vistos:
            vistos.add(x["id"])
            out.append(x)
    log.info("Câmara: %d deputados em exercício", len(out))
    if not anos:
        return out
    pasta = (cache or Path(".cache")) / "camara-deputados"
    linhas: dict[str, list[dict]] = defaultdict(list)  # id -> linhas da lista da legislatura
    for leg in legislaturas(anos):
        lista = com_copia(pasta / f"legislatura-{leg}.json",
                          lambda leg=leg: _paginas(f"{API}/deputados", {"idLegislatura": leg, "itens": 100,
                                                                        "ordem": "ASC", "ordenarPor": "nome"}),
                          f"Deputados da {leg}ª legislatura")
        for d in lista:
            if str(d.get("id", "")).isdigit() and pid(d["id"]) not in vistos:
                linhas[pid(d["id"])].append(d)
    for i, ls in sorted(linhas.items()):
        num = i.removeprefix("dep-")
        try:
            st = com_copia(pasta / f"{num}.json", lambda num=num: get_json(f"{API}/deputados/{num}")["dados"],
                           f"Deputado {num}").get("ultimoStatus") or {}
        except Exception as e:  # noqa: BLE001 - sem o detalhe, fica o último nome e partido da lista da legislatura
            log.warning("Câmara: detalhe do deputado %s indisponível (%s)", num, e)
            st = {}
        x = _deputado({**ls[-1], **{k: v for k, v in st.items() if v}, "id": num}, em_exercicio=False)
        if not x:
            continue
        x["situacao"] = (st.get("situacao") or "Fora do exercício").strip()
        if st.get("data"):
            x["situacao_desde"] = str(st["data"])[:10]
        outros = sorted({(d.get("nome") or "").strip() for d in ls} - {x["nome"], ""})
        if outros:
            x["outros_nomes"] = outros
        vistos.add(i)
        out.append(x)
    log.info("Câmara: %d deputados que passaram pela legislatura e não estão no cargo hoje", len(linhas))
    return out


def _validade(ano: int) -> float | None:
    """Arquivos do ano atual e do anterior mudam (notas lançadas com atraso): baixa de novo a cada 20 horas."""
    return 20 if ano >= dt.date.today().year - 1 else None


DETALHE = ("https://www.camara.leg.br/cota-parlamentar/documento?nuDeputadoId={nu}&numMes={mes}&numAno={ano}"
           "&despesa={sub}&cnpjFornecedor={cnpj}&idDocumento={num}&idDocumentoFiscal={ide}")
LISTA_MES = ("https://www.camara.leg.br/cota-parlamentar/analitico?nuDeputadoId={nu}&dataInicio={mes}/{ano}&dataFim={mes}/{ano}"
             "&despesa={sub}&nomeHospede=&nomePassageiro=&nomeFornecedor=&cnpjFornecedor=&numDocumento=&sguf=")


def link_detalhe(nu, ano, mes, sub, cnpj, num, ide) -> str:
    """Página oficial de detalhe da despesa, a mesma que o site da Câmara abre em "detalhe".

    Serve para as despesas sem documento digitalizado (passagens compradas pelo sistema da Câmara, telefonia).
    """
    nu = (nu or "").strip()
    if not nu:
        return ""
    if len(digits(cnpj)) == 11:
        # Fornecedor pessoa física: o link de detalhe levaria o CPF no endereço. Usamos a lista do mês, sem o CPF.
        return LISTA_MES.format(nu=nu, mes=mes, ano=ano, sub=(sub or "").strip())
    return DETALHE.format(nu=nu, mes=mes, ano=ano, sub=(sub or "").strip(), cnpj=digits(cnpj),
                          num=quote((num or "").strip()), ide=(ide or "").strip() or "0")


def valor_da_nota(r: dict) -> float:
    """Valor de uma linha do arquivo da cota, como a página oficial do deputado soma."""
    valor = to_float(r.get("vlrLiquido"))
    if valor < 0 < to_float(r.get("vlrDocumento")) and "MORADIA" in (r.get("txtDescricao") or "").upper():
        # Complementação do auxílio-moradia: o arquivo anual traz o valor líquido negativo (em 2025, todas as 834
        # linhas), mas é um gasto da cota. A página oficial de cada deputado soma o valor positivo (vlrDocumento):
        # conferido em novembro de 2026 mês a mês (dep. 204422, jan/2025: 41.135,65 + 2 x 2.841,54 = 46.818,73,
        # igual à página). Com o sinal trocado, o total ficava menor e a diferença virava "sem nota".
        valor = -valor
    return valor


def parse_cota(rows, ids: set[str]) -> list[dict]:
    """Converte linhas do arquivo da cota em despesas no formato comum."""
    out = []
    for r in rows:
        # ideCadastro é o mesmo id da API; nuDeputadoId é um número interno diferente
        ide = dep = (r.get("ideCadastro") or "").strip()
        if not dep or pid(dep) not in ids:
            dep = (r.get("nuDeputadoId") or "").strip()
        if not dep or pid(dep) not in ids:
            # Sem ideCadastro é nota de liderança de partido, não de deputado. Com ideCadastro, é um deputado que
            # faltou na lista: o gasto sumiria do site.
            if ide.isdigit() and to_float(r.get("vlrLiquido")):
                fora_da_lista("cota da Câmara", pid(ide), to_float(r.get("vlrLiquido")))
            continue
        valor = valor_da_nota(r)
        if valor == 0:
            continue
        cat = r.get("txtDescricao") or ""
        url = url_segura(r.get("urlDocumento"))
        nu = (r.get("nuDeputadoId") or "").strip()
        ano, mes = int(to_float(r.get("numAno"))), int(to_float(r.get("numMes")))
        detalhe = " · ".join(x for x in (
            f"Passageiro: {r['txtPassageiro'].strip()}" if (r.get("txtPassageiro") or "").strip() else "",
            f"Trecho: {r['txtTrecho'].strip()}" if (r.get("txtTrecho") or "").strip() else "",
            f"Documento nº {r['txtNumero'].strip()}" if not url and (r.get("txtNumero") or "").strip() else "") if x)
        out.append({
            "politico": pid(dep),
            "ano": ano,
            "mes": mes,
            "data": (r.get("datEmissao") or "")[:10],
            "categoria": categoria_curta(cat),
            "grupo": grupo_de(cat),
            "fornecedor": (r.get("txtFornecedor") or "").strip(),
            "doc": digits(r.get("txtCNPJCPF")),
            "valor": round(valor, 2),
            "url": url or link_detalhe(nu, ano, mes, r.get("numSubCota"), r.get("txtCNPJCPF"), r.get("txtNumero"), r.get("ideDocumento")),
            "link": "nota" if url else ("lista" if len(digits(r.get("txtCNPJCPF"))) == 11 else "detalhe") if nu else "",
            "detalhe": detalhe,
            "nu": nu,
            "num": (r.get("txtNumero") or "").strip(),
            "sub": (r.get("numSubCota") or "").strip(),
        })
    return out


def despesas(anos: list[int], ids: set[str], cache: Path) -> list[dict]:
    out: list[dict] = []
    for ano in anos:
        try:
            f = download(COTA_URL.format(ano=ano), cache / f"camara-cota-{ano}.csv.zip", max_horas=_validade(ano),
                         validar=eh_zip)
        except Exception as e:  # noqa: BLE001 - um ano faltando não deve parar tudo
            log.warning("Cota da Câmara %s indisponível: %s", ano, e)
            avisar(f"Cota da Câmara {ano}: o arquivo oficial não pôde ser baixado; as despesas de deputados neste ano estão faltando")
            continue
        rows = parse_cota(read_csv_file(f), ids)
        log.info("Câmara: %d despesas em %s", len(rows), ano)
        out.extend(rows)
    return out


def parse_votacoes(votacoes_rows, votos_rows, orient_rows, prop_rows, ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Monta as votações nominais do plenário e os votos de cada deputado."""
    votos_por = defaultdict(list)
    ja_votou = set()  # o arquivo às vezes repete a linha do mesmo voto
    for r in votos_rows:
        dep = (r.get("deputado_id") or "").strip()
        if not dep.isdigit() or (r.get("idVotacao"), dep) in ja_votou:
            continue
        ja_votou.add((r.get("idVotacao"), dep))
        votos_por[r["idVotacao"]].append({
            "politico": pid(dep),
            "voto": normaliza_voto(r.get("voto", "")),
            "partido": r.get("deputado_siglaPartido") or "",
        })

    orient = defaultdict(dict)
    for r in orient_rows:
        sigla = (r.get("siglaBancada") or "").strip()
        if sigla:
            orient[r["idVotacao"]][sigla] = normaliza_voto(r.get("orientacao", ""))

    props: dict[str, dict] = {}
    for r in prop_rows:
        if r["idVotacao"] in props:
            continue
        props[r["idVotacao"]] = {
            "sigla": r.get("proposicao_siglaTipo") or "",
            "numero": r.get("proposicao_numero") or "",
            "ano": r.get("proposicao_ano") or "",
            "ementa": (r.get("proposicao_ementa") or "").strip(),
            "titulo": (r.get("proposicao_titulo") or "").strip(),
            "url": f"https://www.camara.leg.br/propostas-legislativas/{r.get('proposicao_id')}" if r.get("proposicao_id") else "",
        }

    votacoes, votos = [], []
    vistas = set()
    for r in votacoes_rows:
        vid = id_seguro(r.get("id"))
        if not vid or vid in vistas or (r.get("siglaOrgao") or "").upper() != "PLEN" or vid not in votos_por:
            continue
        vistas.add(vid)
        vs = [v for v in votos_por[vid] if v["politico"] in ids]
        for v in votos_por[vid]:
            if v["politico"] not in ids:
                fora_da_lista("votos da Câmara", v["politico"])
        if not vs:
            continue
        sim, nao = (r.get("votosSim") or "").strip(), (r.get("votosNao") or "").strip()
        votacoes.append({
            "id": f"cd-{vid}",
            "casa": "camara",
            # placar oficial da Câmara (todos os deputados que votaram, inclusive os que já saíram do cargo)
            **({"placar_oficial": {"sim": int(sim), "nao": int(nao)}} if sim.isdigit() and nao.isdigit() else {}),
            "data": (r.get("data") or r.get("dataHoraRegistro") or "")[:10],
            "descricao": (r.get("descricao") or "").strip(),
            "aprovada": (r.get("aprovacao") or "").strip() == "1",
            "proposicao": props.get(vid),
            "orientacoes": orient.get(vid, {}),
            "fonte": f"{API}/votacoes/{vid}",
        })
        for v in vs:
            votos.append({"votacao": f"cd-{vid}", **v})
    return votacoes, votos


def votacoes(anos: list[int], ids: set[str], cache: Path) -> tuple[list[dict], list[dict]]:
    all_v, all_votos = [], []
    for ano in anos:
        try:
            files = {k: download(u.format(ano=ano), cache / f"camara-{k}-{ano}.csv", max_horas=_validade(ano),
                                 validar=eh_csv)
                     for k, u in VOT_URLS.items()}
        except Exception as e:  # noqa: BLE001
            log.warning("Votações da Câmara %s indisponíveis: %s", ano, e)
            avisar(f"Votações da Câmara {ano}: os arquivos oficiais não puderam ser baixados; as votações deste ano estão faltando")
            continue
        v, vs = parse_votacoes(
            read_csv_file(files["votacoes"]), read_csv_file(files["votos"]),
            read_csv_file(files["orientacoes"]), read_csv_file(files["proposicoes"]), ids,
        )
        log.info("Câmara: %d votações nominais e %d votos em %s", len(v), len(vs), ano)
        all_v += v
        all_votos += vs
    return all_v, all_votos


def normaliza_voto(v: str) -> str:
    v = (v or "").strip().lower()
    if v.startswith("sim"):
        return "Sim"
    if v.startswith("n"):
        return "Não"
    if v.startswith("abst"):
        return "Abstenção"
    if v.startswith("obstr"):
        return "Obstrução"
    if v.startswith("libera"):
        return "Liberado"
    if v.startswith("art"):
        return "Art. 17"
    return v.capitalize() if v else "—"
