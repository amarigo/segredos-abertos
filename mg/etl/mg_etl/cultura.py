"""Shows e cultura em Minas: quanto as prefeituras gastam contratando artistas, quem indicou o dinheiro, a Lei
Rouanet por região do estado e a população de cada cidade.

Quatro fontes oficiais, todas por API:

1. Contratações de artistas pelas prefeituras e pelo estado: API de consultas do PNCP (Portal Nacional de
   Contratações Públicas), onde todo órgão público é obrigado a publicar as compras feitas pela Lei 14.133/2021.
       https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao (modalidade 9, inexigibilidade, uf=MG)
   Só entram as contratações com amparo legal no art. 74, inciso II da lei: "contratação de profissional do setor
   artístico, diretamente ou por meio de empresário exclusivo". É a própria prefeitura que escolhe esse amparo ao
   publicar; não classificamos nada por palavra. Quem recebeu (o artista ou a empresa dele) vem do resultado de cada
   item da compra (/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens/{n}/resultados).
   O PNCP passou a valer para todas as prefeituras em 2024; antes disso a maioria não publicava lá.

2. Quem indicou o dinheiro: emendas Pix (transferências especiais). Não é uma coleta nova: o coletor nacional já lê
   a API do Transferegov (sa_etl/transferegov.py) e grava data/emendas/destino/{ano}/{cnpj}.json. Aqui separamos os
   planos de ação de prefeituras de MG cujo objeto, metas ou pagamentos falam de show, apresentação artística,
   cachê, carnaval, festa, rodeio etc. Essa separação é nossa, por palavras do texto oficial: cada plano mostra as
   palavras que o puseram na lista, e o link do Transferegov para conferir.

3. Lei Rouanet: API do SALIC (Ministério da Cultura), https://api.salic.cultura.gov.br/api/v1/
   - /incentivadores?UF=MG: pessoas e empresas de MG que destinaram parte do imposto de renda a projetos culturais
     (total_doado, o acumulado desde o início do programa). É o imposto que deixou de entrar nos cofres por causa da
     Lei Rouanet, somado pela cidade de quem destinou. Em projetos do art. 18 o desconto no imposto é de 100%; nos
     do art. 26, de 30% a 80%. Por isso o site diz "até".
   - /projetos?UF=MG: projetos culturais realizados em MG e quanto captaram.

4. População: API de agregados do IBGE (estimativa da população, tabela 6579, variável 9324) e a lista de
   municípios com as regiões intermediárias e imediatas (API de localidades do IBGE).

A leitura do PNCP e do SALIC é feita aos poucos, com limite de tempo por execução, e continua na seguinte (como no
Transferegov). Meses e páginas já lidos ficam no cache.
"""
from __future__ import annotations

import calendar
import datetime as dt
import gzip
import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path

from sa_etl.util import avisar, com_copia, digits, get, norm_name, to_float, write_json

from . import fontes

log = logging.getLogger("mg_etl.cultura")

UF, COD_UF = "MG", 31

# ---------------------------------------------------------------- IBGE

IBGE_MUNICIPIOS = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{COD_UF}/municipios"
IBGE_POPULACAO = f"https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-1/variaveis/9324?localidades=N6[N3[{COD_UF}]]"
IBGE_PAGINA = "https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html"


def chave(nome: str) -> str:
    """Nome de cidade para comparar: sem acento, sem 'Município de', sem pontuação. 'D'Água' = 'Dagua'."""
    n = norm_name(nome or "")
    n = re.sub(r"\s*[-/(]\s*MG\)?\s*$", "", n)
    n = re.sub(r"^(PREFEITURA\s+(MUNICIPAL\s+)?D[EOA]\s+|MUNICIPIO\s+D[EOA]\s+|FUNDO\s+MUNICIPAL\s+.*?\s+D[EOA]\s+)", "", n)
    return re.sub(r"[^A-Z]", "", n)


def municipios(cache: Path) -> dict[int, dict]:
    """{código IBGE: {nome, regiao (intermediária), imediata}} das 853 cidades de MG."""
    dados = com_copia(cache / "ibge" / "municipios-mg.json", lambda: _ibge_json(IBGE_MUNICIPIOS),
                      "Cidades de MG (IBGE)", max_horas=24 * 30)
    out = {}
    for m in dados or []:
        try:
            imediata = m.get("regiao-imediata") or {}
            inter = imediata.get("regiao-intermediaria") or {}
            out[int(m["id"])] = {"nome": m["nome"], "regiao": inter.get("nome") or "", "imediata": imediata.get("nome") or ""}
        except (KeyError, TypeError, ValueError):
            continue
    return out


def populacao(cache: Path) -> tuple[dict[int, int], str]:
    """({código IBGE: habitantes}, ano da estimativa)."""
    dados = com_copia(cache / "ibge" / "populacao-mg.json", lambda: _ibge_json(IBGE_POPULACAO),
                      "População das cidades (IBGE)", max_horas=24 * 30)
    out, ano = {}, ""
    for var in dados or []:
        for res in var.get("resultados") or []:
            for s in res.get("series") or []:
                serie = s.get("serie") or {}
                if not serie:
                    continue
                a = max(serie)
                v = serie[a]
                if not str(v).strip().isdigit():
                    continue  # "-" ou "..." quando o IBGE não tem o número
                try:
                    out[int(s["localidade"]["id"])] = int(v)
                except (KeyError, TypeError, ValueError):
                    continue
                ano = max(ano, a)
    return out, ano


def _ibge_json(url: str):
    r = get(url, timeout=90)
    d = r.json()
    if not isinstance(d, list) or not d:
        raise RuntimeError(f"IBGE: resposta inesperada em {url}")
    return d


class Cidades:
    """Acha a cidade de MG pelo código do IBGE ou pelo nome, e diz população e região."""

    def __init__(self, mun: dict[int, dict], pop: dict[int, int]):
        self.mun, self.pop = mun, pop
        self.por_nome = {chave(m["nome"]): c for c, m in mun.items()}

    def codigo(self, nome: str = "", cod=None) -> int | None:
        c = digits(str(cod or ""))
        if len(c) == 7 and int(c) in self.mun:
            return int(c)
        return self.por_nome.get(chave(nome))

    def info(self, cod: int | None, nome: str = "") -> dict:
        m = self.mun.get(cod or -1) or {}
        return {"cod": cod, "nome": m.get("nome") or fontes.bonito(nome) or "Não informado", "regiao": m.get("regiao") or "",
                "populacao": self.pop.get(cod or -1)}


def _por_hab(valor: float, pop: int | None) -> float | None:
    return round(valor / pop, 2) if pop else None


# ---------------------------------------------------------------- leitura aos poucos


class SemTempo(Exception):
    """O tempo desta execução acabou; continua na próxima."""


class Relogio:
    def __init__(self, minutos: float):
        self.fim = time.monotonic() + minutos * 60
        self.pedidos = 0

    def checar(self) -> None:
        if time.monotonic() > self.fim:
            raise SemTempo()
        self.pedidos += 1


def _ler_gz(f: Path):
    try:
        return json.loads(gzip.decompress(f.read_bytes()))
    except (OSError, ValueError):
        return None


def _gravar_gz(f: Path, d) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    tmp.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode()))
    tmp.replace(f)


def _json_ou_nada(url: str, params: dict | None = None, timeout: int = 90):
    """O PNCP responde 204 (sem corpo) quando não há nada; isso vira None."""
    r = get(url, params=params, timeout=timeout)
    if r.status_code == 204 or not r.content.strip():
        return None
    return r.json()


# ---------------------------------------------------------------- PNCP: contratação de artistas

PNCP_CONSULTA = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
PNCP_API = "https://pncp.gov.br/api/pncp/v1"
PNCP_PAGINA = "https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"
PNCP_FONTE = "https://pncp.gov.br/app/editais?q=&status=todos&ufs=MG&modalidades=9"
INEXIGIBILIDADE = 9
PRIMEIRO_MES = (2024, 1)  # a Lei 14.133 vale para todas as prefeituras desde 30/12/2023
TAM_PAGINA = 50
MESES_ABERTOS = 2   # meses recentes são lidos de novo (a prefeitura publica com atraso)
VALIDADE_ABERTO_DIAS = 7
DIAS_SEM_RESULTADO = 120  # compra sem resultado publicado: pergunta de novo até ela ter esta idade
# "Lei 14.133/2021, Art. 74, II" e a descrição "contratação de profissional do setor artístico"
ART_74_II = re.compile(r"art\.?\s*74\s*,?\s*(inc(iso|\.)?\s*)?II(?![IVX])|setor\s+art[ií]stico", re.I)


def artistica(compra: dict) -> bool:
    a = compra.get("amparoLegal") or {}
    return bool(ART_74_II.search(f"{a.get('nome') or ''} {a.get('descricao') or ''}"))


def _meses(hoje: dt.date) -> list[tuple[int, int]]:
    out, (a, m) = [], PRIMEIRO_MES
    while (a, m) <= (hoje.year, hoje.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def _aberto(a: int, m: int, hoje: dt.date) -> bool:
    return (hoje.year - a) * 12 + hoje.month - m < MESES_ABERTOS


def _compra_resumida(c: dict) -> dict:
    org, un = c.get("orgaoEntidade") or {}, c.get("unidadeOrgao") or {}
    homologado = to_float(c.get("valorTotalHomologado"))
    return {
        "controle": c.get("numeroControlePNCP") or "", "cnpj_orgao": digits(org.get("cnpj")), "orgao": fontes.bonito(org.get("razaoSocial") or org.get("razaosocial") or ""),
        "esfera": org.get("esferaId") or "", "ano": c.get("anoCompra"), "seq": c.get("sequencialCompra"),
        "cod_ibge": digits(str(un.get("codigoIbge") or "")), "municipio": un.get("municipioNome") or "", "uf": un.get("ufSigla") or "",
        "objeto": fontes.sem_cpf(" ".join(str(c.get("objetoCompra") or "").split())),
        "valor": round(homologado or to_float(c.get("valorTotalEstimado")), 2), "estimado": not homologado,
        "data": str(c.get("dataPublicacaoPncp") or c.get("dataAberturaProposta") or "")[:10],
    }


class LeitorPNCP:
    def __init__(self, cache: Path, relogio: Relogio, hoje: dt.date):
        self.pasta, self.rel, self.hoje = cache / "pncp", relogio, hoje

    def mes(self, a: int, m: int) -> list[dict]:
        """Compras de artistas publicadas no mês (de órgãos de MG). A leitura em curso fica num arquivo à parte, para
        não estragar a última leitura completa se o tempo acabar no meio."""
        f = self.pasta / f"compras-{a}-{m:02d}.json.gz"
        f_parcial = self.pasta / f"compras-{a}-{m:02d}.parcial.json.gz"
        d = _ler_gz(f)
        if d and (not _aberto(a, m, self.hoje) or (self.hoje - dt.date.fromisoformat(d["lido_em"])).days < VALIDADE_ABERTO_DIAS):
            return d["compras"]
        parcial = _ler_gz(f_parcial) or {}
        if parcial.get("lido_em") != self.hoje.isoformat():
            parcial = {"compras": [], "pagina": 0}
        ultimo = calendar.monthrange(a, m)[1]
        pagina, compras = parcial["pagina"], parcial["compras"]
        while True:
            self.rel.checar()
            pagina += 1
            resp = _json_ou_nada(PNCP_CONSULTA, {
                "dataInicial": f"{a}{m:02d}01", "dataFinal": f"{a}{m:02d}{ultimo}", "codigoModalidadeContratacao": INEXIGIBILIDADE,
                "uf": UF, "pagina": pagina, "tamanhoPagina": TAM_PAGINA})
            if resp is not None and not isinstance(resp, dict):
                raise RuntimeError("PNCP: resposta inesperada")
            linhas = (resp or {}).get("data") or []
            if not isinstance(linhas, list):
                raise RuntimeError("PNCP: resposta sem a lista 'data'")
            compras += [_compra_resumida(c) for c in linhas if isinstance(c, dict) and artistica(c)
                        and (c.get("unidadeOrgao") or {}).get("ufSigla") in (UF, None)]
            restam = int((resp or {}).get("paginasRestantes") or 0)
            _gravar_gz(f_parcial, {"pagina": pagina, "compras": compras, "lido_em": self.hoje.isoformat()})
            if not linhas or restam <= 0:
                break
        vistos, unicas = set(), []
        for c in compras:  # a mesma compra pode cair em duas páginas se algo foi publicado no meio da leitura
            if c["controle"] not in vistos:
                vistos.add(c["controle"])
                unicas.append(c)
        _gravar_gz(f, {"compras": unicas, "lido_em": self.hoje.isoformat()})
        f_parcial.unlink(missing_ok=True)
        return unicas

    def resultados(self, compras: list[dict], guardados: dict) -> None:
        """Quem recebeu em cada compra (artista ou empresa). Guardado para sempre quando a compra já tem resultado."""
        for c in compras:
            k = c["controle"]
            g = guardados.get(k)
            if g and (g["forn"] or g.get("tentado") == self.hoje.isoformat()):
                continue
            if g and c["data"] and (self.hoje - dt.date.fromisoformat(c["data"])).days > DIAS_SEM_RESULTADO:
                continue
            if not (c["cnpj_orgao"] and c["ano"] and c["seq"]):
                continue
            self.rel.checar()
            base = f"{PNCP_API}/orgaos/{c['cnpj_orgao']}/compras/{c['ano']}/{c['seq']}/itens"
            forn: dict[str, dict] = {}
            itens = _json_ou_nada(base, {"pagina": 1, "tamanhoPagina": 100}) or []
            for it in itens if isinstance(itens, list) else []:
                if not it.get("temResultado", True) or it.get("numeroItem") is None:
                    continue
                self.rel.checar()
                res = _json_ou_nada(f"{base}/{it['numeroItem']}/resultados") or []
                for r in res if isinstance(res, list) else []:
                    _somar_fornecedor(forn, r)
            guardados[k] = {"forn": list(forn.values()), "tentado": self.hoje.isoformat()}


def _somar_fornecedor(forn: dict, r: dict) -> None:
    """Resultado de um item. CPF nunca sai daqui: de pessoa física fica só o nome, como o PNCP mostra."""
    tipo = str(r.get("tipoPessoa") or "").upper()
    doc = digits(r.get("niFornecedor"))
    cnpj = doc if tipo != "PF" and len(doc) == 14 else ""
    nome = fontes.sem_cpf(fontes.bonito(r.get("nomeRazaoSocialFornecedor") or "")) or "Não informado"
    v = to_float(r.get("valorTotalHomologado")) or to_float(r.get("valorUnitarioHomologado")) * (to_float(r.get("quantidadeHomologada")) or 1)
    x = forn.setdefault(cnpj or f"pf:{chave(nome)}", {"nome": nome, "cnpj": cnpj, "pessoa": not cnpj, "valor": 0.0})
    x["valor"] = round(x["valor"] + v, 2)


def coletar_pncp(cache: Path, minutos: float, hoje: dt.date) -> dict:
    """{"compras": [...com "fornecedores"], "completo": bool, "meses": n lidos}. Lê do mês mais novo para o mais velho."""
    rel = Relogio(minutos)
    ler = LeitorPNCP(cache, rel, hoje)
    res_f = cache / "pncp" / "resultados.json.gz"
    guardados = _ler_gz(res_f) or {}
    compras, completo = [], True
    meses = list(reversed(_meses(hoje)))
    try:
        for a, m in meses:
            c = ler.mes(a, m)
            compras += c
        ler.resultados(sorted(compras, key=lambda c: -c["valor"]), guardados)
    except SemTempo:
        completo = False
    except Exception as e:  # noqa: BLE001
        log.warning("PNCP: a leitura parou (%s)", str(e)[:200])
        completo = False
    finally:
        _gravar_gz(res_f, guardados)
    if not completo:  # o que não deu tempo de ler agora vem das leituras anteriores, no cache
        lidos = {c["controle"] for c in compras}
        for a, m in meses:
            d = (_ler_gz(cache / "pncp" / f"compras-{a}-{m:02d}.json.gz")
                 or _ler_gz(cache / "pncp" / f"compras-{a}-{m:02d}.parcial.json.gz") or {})
            compras += [c for c in d.get("compras") or [] if c["controle"] not in lidos]
            lidos |= {c["controle"] for c in d.get("compras") or []}
    for c in compras:
        c["fornecedores"] = sorted((guardados.get(c["controle"]) or {}).get("forn") or [], key=lambda f: -f["valor"])
    log.info("PNCP: %d contratações de artistas em MG (%d pedidos nesta execução)%s", len(compras), rel.pedidos,
             "" if completo else "; a leitura continua na próxima")
    return {"compras": compras, "completo": completo}


def resumir_pncp(p: dict, cid: Cidades) -> dict:
    compras = p["compras"]
    por_ano: dict = defaultdict(lambda: [0.0, 0])
    por_cidade: dict = defaultdict(lambda: [0.0, 0])
    artistas: dict = {}
    lista = []
    for c in compras:
        ano = int(c["data"][:4]) if c["data"][:4].isdigit() else c["ano"]
        por_ano[ano][0] += c["valor"]
        por_ano[ano][1] += 1
        cod = cid.codigo(c["municipio"], c["cod_ibge"])
        por_cidade[cod][0] += c["valor"]
        por_cidade[cod][1] += 1
        info = cid.info(cod, c["municipio"])
        for f in c["fornecedores"]:
            k = f["cnpj"] or f"pf:{chave(f['nome'])}"
            a = artistas.setdefault(k, {"nome": f["nome"], "cnpj": f["cnpj"], "pessoa": f["pessoa"], "valor": 0.0, "n": 0, "cidades": set()})
            a["valor"] += f["valor"]
            a["n"] += 1
            a["cidades"].add(info["nome"])
        lista.append({"ano": ano, "data": c["data"], "cidade": info["nome"], "cod": cod, "orgao": c["orgao"], "objeto": c["objeto"],
                      "valor": c["valor"], "estimado": c["estimado"],
                      "fornecedores": [{k: f[k] for k in ("nome", "cnpj", "valor")} for f in c["fornecedores"][:5]],
                      "url": PNCP_PAGINA.format(cnpj=c["cnpj_orgao"], ano=c["ano"], seq=c["seq"]) if c["cnpj_orgao"] else ""})
    lista.sort(key=lambda x: (-x["ano"], -x["valor"]))
    cidades = []
    for cod, (v, n) in por_cidade.items():
        i = cid.info(cod)
        cidades.append({**i, "valor": round(v, 2), "n": n, "por_habitante": _por_hab(v, i["populacao"])})
    cidades.sort(key=lambda x: -x["valor"])
    return {
        "fonte": PNCP_FONTE, "api": PNCP_CONSULTA, "completo": p["completo"],
        "total": round(sum(c["valor"] for c in compras), 2), "n": len(compras),
        "sem_fornecedor": sum(1 for c in compras if not c["fornecedores"]),
        "por_ano": [{"ano": a, "valor": round(x[0], 2), "n": x[1]} for a, x in sorted(por_ano.items())],
        "cidades": cidades,
        "artistas": [{**{k: a[k] for k in ("nome", "cnpj", "pessoa", "n")}, "valor": round(a["valor"], 2), "cidades": sorted(a["cidades"])[:12]}
                     for a in sorted(artistas.values(), key=lambda a: -a["valor"])[:200]],
        "lista": lista,
    }


# ---------------------------------------------------------------- Emendas Pix com show e evento

TRANSFEREGOV_FONTE = "https://api-publica.transferegov.gestao.gov.br/especiais/docs"
TRANSFEREGOV_CONSULTA = "https://especiais.transferegov.sistema.gov.br/transferencia-especial/plano-acao/consulta"
# O que é contratar artista. Estrutura (palco, som, banheiro) fica de fora da lista de artistas, mas o plano entra.
ARTISTICO = re.compile(r"\b(shows?|cach[eê]s?|apresenta[cç](?:[aã]o|[oõ]es)\s+(?:art[ií]stic|music|cultur)\w*|atra[cç](?:[aã]o|[oõ]es)\s+art[ií]stic\w*"
                       r"|contrata[cç](?:[aã]o|[oõ]es)\s+art[ií]stic\w*|bandas?\s+(?:music|de\s+m[uú]sica)\w*|cantor(?:a|es)?|dupla\s+sertanej\w*)\b", re.I)
EVENTO = re.compile(r"\b(carnava(?:l|is)|festas?|festival|festivais|rodeios?|r[eé]veillon|exposi[cç](?:[aã]o|[oõ]es)\s+agropecu\w*"
                    r"|anivers[aá]rio\s+d[aeo]\s+(?:cidade|munic[ií]pio|emancipa\w*)|eventos?\s+(?:art[ií]stic|cultur|music|festiv)\w*|cavalgada)\b", re.I)
ESTRUTURA = re.compile(r"\b(palco|sonoriza\w*|som\s+e\s+ilumina\w*|ilumina[cç][aã]o|tendas?|banheiros?|geradores?|seguran[cç]a|"
                       r"grades?|locac[aã]o|loca[cç][aã]o|estrutura|camarim|alimenta[cç][aã]o|brigad\w*)\b", re.I)


def palavras(*textos: str) -> list[str]:
    achadas = []
    for t in textos:
        for rx in (ARTISTICO, EVENTO):
            for m in rx.finditer(t or ""):
                p = m.group(0).lower()
                if p not in achadas:
                    achadas.append(p)
    return achadas[:6]


def pagamento_artista(descricao: str) -> bool:
    return bool(ARTISTICO.search(descricao or "")) and not ESTRUTURA.search(descricao or "")


def _autores(nacional: Path) -> dict[str, dict]:
    """Nome do parlamentar (chave) -> página no Minas Nossa, quando ele é de MG."""
    from sa_etl import emendas as E
    out: dict[str, dict] = {}
    for f in sorted((nacional / "emendas").glob("[0-9]*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for a in (d.get("autores") or []) + (d.get("coletivos") or []):
            out.setdefault(E._chave(a.get("nome") or ""), {"politico": a.get("politico"), "partido": a.get("partido") or ""})
    return out


def coletar_pix(nacional: Path, cid: Cidades, ids_mg: set[str]) -> dict | None:
    """Planos de emenda Pix para prefeituras de MG com show ou evento, dos arquivos que o coletor nacional gravou."""
    from sa_etl import emendas as E
    pasta = nacional / "emendas" / "destino"
    anos = sorted(int(f.stem) for f in pasta.glob("[0-9]*.json")) if pasta.exists() else []
    if not anos:
        return None
    autores = _autores(nacional)
    planos, completo = [], True
    for ano in anos:
        try:
            idx = json.loads((pasta / f"{ano}.json").read_text(encoding="utf-8"))
        except ValueError:
            continue
        completo = completo and bool(idx.get("completo"))
        for b in idx.get("beneficiarios") or []:
            if b.get("uf") != UF:
                continue
            try:
                det = json.loads((pasta / str(ano) / f"{b['cnpj']}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError, KeyError):
                continue
            cod = cid.codigo(det.get("nome") or "")
            info = cid.info(cod, det.get("nome") or "") if cod else {"cod": None, "nome": fontes.bonito(det.get("nome") or ""),
                                                                      "regiao": "", "populacao": None}
            for p in det.get("planos") or []:
                metas = " ".join(f"{m.get('nome', '')} {m.get('descricao', '')}" for e in p.get("executores") or [] for m in e.get("metas") or [])
                objs = " ".join(e.get("objeto") or "" for e in p.get("executores") or [])
                gastos = p.get("gastos") or []
                achadas = palavras(p.get("objeto") or "", objs, metas, *(g.get("descricao") or "" for g in gastos))
                if not achadas:
                    continue
                art = [g for g in gastos if pagamento_artista(g.get("descricao") or "")]
                a = autores.get(E._chave(p.get("parlamentar") or "")) or {}
                planos.append({
                    "ano": ano, "cidade": info["nome"], "cod": info["cod"], "regiao": info["regiao"], "populacao": info["populacao"],
                    "beneficiario": det.get("nome") or "", "parlamentar": p.get("parlamentar") or "Não informado",
                    "politico": a.get("politico") if a.get("politico") in ids_mg else None, "partido": a.get("partido") or "",
                    "emenda": p.get("emenda") or "", "plano": p.get("plano") or "", "objeto": fontes.sem_cpf(p.get("objeto") or ""),
                    "area": p.get("area") or "", "valor": p.get("valor") or 0.0, "gasto": p.get("gasto") or 0.0,
                    "palavras": achadas,
                    "pagamentos_artistas": [{"data": g.get("data") or "", "nome": g.get("recebedor") or "", "cnpj": g.get("cnpj") or "",
                                             "descricao": fontes.sem_cpf(g.get("descricao") or ""), "valor": g.get("valor") or 0.0} for g in art],
                })
    planos.sort(key=lambda p: (-p["ano"], -p["valor"]))
    parl: dict = {}
    for p in planos:
        x = parl.setdefault(p["parlamentar"], {"nome": p["parlamentar"], "politico": p["politico"], "partido": p["partido"],
                                               "valor": 0.0, "gasto": 0.0, "n": 0, "cidades": set()})
        x["valor"] += p["valor"]
        x["gasto"] += p["gasto"]
        x["n"] += 1
        x["cidades"].add(p["cidade"])
    rec: dict = {}
    for p in planos:
        for g in p["pagamentos_artistas"]:
            k = g["cnpj"] or f"pf:{chave(g['nome'])}"
            x = rec.setdefault(k, {"nome": g["nome"], "cnpj": g["cnpj"], "valor": 0.0, "n": 0, "cidades": set()})
            x["valor"] += g["valor"]
            x["n"] += 1
            x["cidades"].add(p["cidade"])
    fim = lambda x: {**x, "valor": round(x["valor"], 2), **({"gasto": round(x["gasto"], 2)} if "gasto" in x else {}),  # noqa: E731
                     "cidades": sorted(x["cidades"])[:12]}
    return {
        "fonte": TRANSFEREGOV_FONTE, "consulta": TRANSFEREGOV_CONSULTA, "anos": anos, "completo": completo,
        "total": round(sum(p["valor"] for p in planos), 2), "gasto": round(sum(p["gasto"] for p in planos), 2), "n": len(planos),
        "parlamentares": [fim(x) for x in sorted(parl.values(), key=lambda x: -x["valor"])],
        "artistas": [fim(x) for x in sorted(rec.values(), key=lambda x: -x["valor"])[:100]],
        "planos": planos,
    }


# ---------------------------------------------------------------- Lei Rouanet (SALIC)

SALIC_API = "https://api.salic.cultura.gov.br/api/v1"
SALIC_FONTE = "https://dados.cultura.gov.br/dataset/incentivos-da-lei-rouanet"
SALIC_PROJETO = "https://salic.cultura.gov.br/projeto/#/{pronac}"
SALIC_TAM = 100  # o máximo da API
SALIC_VALIDADE_DIAS = 7


def _salic_lista(caminho: str, filtros: dict, rel: Relogio, f: Path, hoje: dt.date, campo: str) -> tuple[list[dict], bool]:
    """Lê a lista inteira, página a página. A leitura completa vale por uma semana; a leitura em curso fica num
    arquivo à parte e continua na execução seguinte. Se o tempo acabar, devolve a última leitura completa."""
    d = _ler_gz(f) or {}
    if d and (hoje - dt.date.fromisoformat(d["lido_em"])).days < SALIC_VALIDADE_DIAS:
        return d["linhas"], True
    f_parcial = f.with_name(f.name.replace(".json.gz", ".parcial.json.gz"))
    p = _ler_gz(f_parcial) or {}
    if not p.get("desde") or (hoje - dt.date.fromisoformat(p["desde"])).days > 3:  # a lista muda: não emendar leitura velha
        p = {"linhas": [], "offset": 0, "desde": hoje.isoformat()}
    linhas, offset = p["linhas"], p["offset"]
    try:
        while True:
            rel.checar()
            r = get(f"{SALIC_API}/{caminho}", params={**filtros, "limit": SALIC_TAM, "offset": offset, "format": "json"}, timeout=90)
            corpo = r.json() if r.content.strip() else {}
            pagina = ((corpo if isinstance(corpo, dict) else {}).get("_embedded") or {}).get(campo)
            if not isinstance(pagina, list):
                raise RuntimeError(f"SALIC: resposta sem a lista '_embedded.{campo}'")
            linhas += pagina
            offset += SALIC_TAM
            total = int(corpo.get("total") or r.headers.get("X-Total-Count") or 0)
            _gravar_gz(f_parcial, {"linhas": linhas, "offset": offset, "desde": p["desde"]})
            if not pagina or offset >= total:
                break
    except SemTempo:
        return d.get("linhas") or [], False
    _gravar_gz(f, {"linhas": linhas, "lido_em": hoje.isoformat()})
    f_parcial.unlink(missing_ok=True)
    return linhas, True


def coletar_rouanet(cache: Path, minutos: float, hoje: dt.date, cid: Cidades) -> dict | None:
    rel = Relogio(minutos)
    pasta = cache / "salic"
    try:
        inc, inc_ok = _salic_lista("incentivadores", {"UF": UF, "sort": "total_doado:desc"}, rel, pasta / "incentivadores-mg.json.gz", hoje, "incentivadores")
        proj, proj_ok = _salic_lista("projetos", {"UF": UF, "sort": "valor_captado:desc"}, rel, pasta / "projetos-mg.json.gz", hoje, "projetos")
    except Exception as e:  # noqa: BLE001
        log.warning("SALIC: %s", str(e)[:200])
        inc, inc_ok = (_ler_gz(pasta / "incentivadores-mg.json.gz") or {}).get("linhas") or [], False
        proj, proj_ok = (_ler_gz(pasta / "projetos-mg.json.gz") or {}).get("linhas") or [], False
    if not inc and not proj and not (inc_ok and proj_ok):  # fonte fora do ar e nenhuma leitura guardada
        return None
    return {**resumir_rouanet(inc, proj, cid), "completo": inc_ok and proj_ok}


def _grupos(itens: list[tuple[int | None, str, float]], cid: Cidades) -> tuple[list[dict], list[dict]]:
    """[(cod, nome, valor)] -> (por região intermediária, por cidade), com população e valor por habitante."""
    pc: dict = defaultdict(lambda: [0.0, 0, ""])
    for cod, nome, v in itens:
        k = cod or f"?{fontes.bonito(nome)}"
        pc[k][0] += v
        pc[k][1] += 1
        pc[k][2] = nome
    cidades, reg = [], defaultdict(lambda: [0.0, 0, 0, set()])
    for k, (v, n, nome) in pc.items():
        i = cid.info(k if isinstance(k, int) else None, nome)
        cidades.append({**i, "valor": round(v, 2), "n": n, "por_habitante": _por_hab(v, i["populacao"])})
        r = reg[i["regiao"] or "Não informado"]
        r[0] += v
        r[1] += n
        r[3].add(i["cod"])
    for nome_r, r in reg.items():
        r[2] = sum(cid.pop.get(c, 0) for c, m in cid.mun.items() if m["regiao"] == nome_r)
    cidades.sort(key=lambda x: -x["valor"])
    regioes = [{"regiao": k, "valor": round(r[0], 2), "n": r[1], "cidades": len(r[3] - {None}), "populacao": r[2] or None,
                "por_habitante": _por_hab(r[0], r[2])} for k, r in sorted(reg.items(), key=lambda kv: -kv[1][0])]
    return regioes, cidades


def resumir_rouanet(inc: list[dict], proj: list[dict], cid: Cidades) -> dict:
    itens_inc, empresas, n_pf, v_pf = [], [], 0, 0.0
    vistos: set = set()
    for x in inc:
        k = x.get("cgccpf") or json.dumps(x, sort_keys=True)
        if k in vistos:  # a mesma pessoa ou empresa em duas páginas
            continue
        vistos.add(k)
        if str(x.get("UF") or "").upper() != UF:
            continue
        v = to_float(x.get("total_doado"))
        if v <= 0:
            continue
        nome_mun = x.get("municipio") or ""
        itens_inc.append((cid.codigo(nome_mun), nome_mun, v))
        doc = digits(x.get("cgccpf"))
        pf = str(x.get("tipo_pessoa") or "").lower().startswith("f") or len(doc) != 14
        if pf:  # pessoa física: só entra na soma, sem nome nem número
            n_pf += 1
            v_pf += v
        else:
            empresas.append({"nome": fontes.bonito(x.get("nome") or ""), "cnpj": doc, "cidade": cid.info(cid.codigo(nome_mun), nome_mun)["nome"],
                             "valor": round(v, 2)})
    reg_inc, cid_inc = _grupos(itens_inc, cid)
    itens_proj, por_ano, maiores = [], defaultdict(lambda: [0.0, 0]), []
    vistos = set()
    for p in proj:
        k = p.get("PRONAC") or json.dumps(p, sort_keys=True)
        if k in vistos:
            continue
        vistos.add(k)
        if str(p.get("UF") or "").upper() != UF:
            continue
        v = to_float(p.get("valor_captado"))
        if v <= 0:
            continue
        nome_mun = p.get("municipio") or ""
        cod = cid.codigo(nome_mun)
        itens_proj.append((cod, nome_mun, v))
        ano = str(p.get("ano_projeto") or "")
        ano = int(ano) if len(ano) == 4 and ano.isdigit() else (2000 + int(ano) if len(ano) == 2 and ano.isdigit() else None)
        if ano:
            por_ano[ano][0] += v
            por_ano[ano][1] += 1
        maiores.append({"pronac": str(p.get("PRONAC") or ""), "nome": " ".join(str(p.get("nome") or "").split()),
                        "proponente": fontes.sem_cpf(fontes.bonito(p.get("proponente") or "")), "cidade": cid.info(cod, nome_mun)["nome"],
                        "ano": ano, "area": p.get("area") or "", "segmento": p.get("segmento") or "", "valor": round(v, 2),
                        "url": SALIC_PROJETO.format(pronac=p.get("PRONAC")) if p.get("PRONAC") else ""})
    maiores.sort(key=lambda x: -x["valor"])
    reg_proj, cid_proj = _grupos(itens_proj, cid)
    return {
        "fonte": SALIC_FONTE, "api": SALIC_API,
        "incentivadores": {"total": round(sum(v for *_, v in itens_inc), 2), "n": len(itens_inc), "n_pessoas": n_pf,
                           "pessoas": round(v_pf, 2), "regioes": reg_inc, "cidades": cid_inc,
                           "empresas": sorted(empresas, key=lambda e: -e["valor"])[:50]},
        "projetos": {"total": round(sum(v for *_, v in itens_proj), 2), "n": len(itens_proj), "regioes": reg_proj, "cidades": cid_proj,
                     "por_ano": [{"ano": a, "valor": round(x[0], 2), "n": x[1]} for a, x in sorted(por_ano.items())],
                     "maiores": maiores[:100]},
    }


# ---------------------------------------------------------------- montagem


def coletar(nacional: Path, saida: Path, cache: Path, ids_mg: set[str], minutos_pncp: float = 8, minutos_salic: float = 4,
            hoje: dt.date | None = None) -> dict:
    """Grava estado/cultura.json (resumo) e estado/cultura/contratos-{ano}.json (cada contratação, por ano).
    Cada fonte é independente: a que falhar fica None e o site diz isso."""
    hoje = hoje or dt.date.today()
    cache = cache / "cultura"
    try:
        mun = municipios(cache)
        pop, ano_pop = populacao(cache)
    except Exception as e:  # noqa: BLE001
        log.warning("IBGE: %s", e)
        avisar("Shows e cultura: a lista de cidades e a população do IBGE não puderam ser baixadas")
        mun, pop, ano_pop = {}, {}, ""
    cid = Cidades(mun, pop)

    def parte(nome: str, fn):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            log.exception("Shows e cultura: erro em %s", nome)
            avisar(f"Shows e cultura: {nome} não pôde ser atualizado")
            return None

    pncp = parte("contratações de artistas (PNCP)", lambda: resumir_pncp(coletar_pncp(cache, minutos_pncp, hoje), cid))
    if pncp is not None and not pncp["n"] and not pncp["completo"]:
        avisar("Shows e cultura: o PNCP não respondeu e ainda não há leitura guardada das contratações de artistas")
        pncp = None
    elif pncp is not None and not pncp["completo"]:
        avisar("Shows e cultura: a leitura das contratações de artistas no PNCP continua na próxima atualização", tentar_de_novo=False)
    pix = parte("emendas Pix com shows e eventos", lambda: coletar_pix(nacional, cid, ids_mg))
    rouanet = parte("Lei Rouanet (SALIC)", lambda: coletar_rouanet(cache, minutos_salic, hoje, cid))
    if rouanet is None:
        avisar("Shows e cultura: a API da Lei Rouanet (SALIC, Ministério da Cultura) não respondeu e não há cópia guardada")
    elif not rouanet["completo"]:
        avisar("Shows e cultura: a leitura da Lei Rouanet continua na próxima atualização; os números são da última leitura completa",
               tentar_de_novo=False)

    if pncp:
        for ano in sorted({x["ano"] for x in pncp["lista"]}):
            write_json(saida / "estado" / "cultura" / f"contratos-{ano}.json",
                       {"ano": ano, "fonte": PNCP_FONTE, "lista": [x for x in pncp["lista"] if x["ano"] == ano]})
        pncp["anos"] = sorted({x["ano"] for x in pncp["lista"]})
        pncp["maiores"] = sorted(pncp.pop("lista"), key=lambda x: -x["valor"])[:30]
    resumo = {
        "atualizado": hoje.isoformat(),
        "populacao": {"fonte": IBGE_PAGINA, "api": IBGE_POPULACAO, "ano": ano_pop, "cidades": len(pop)} if pop else None,
        "contratos": pncp, "pix": pix, "rouanet": rouanet,
    }
    write_json(saida / "estado" / "cultura.json", resumo)
    return {"contratos_artistas": (pncp or {}).get("n", 0), "pix_eventos": (pix or {}).get("n", 0),
            "rouanet_projetos": ((rouanet or {}).get("projetos") or {}).get("n", 0)}
