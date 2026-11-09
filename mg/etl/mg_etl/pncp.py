"""Licitações e contratações diretas de cada cidade e do governo de Minas: quem recebeu, quanto, para quê, em que pé
está e se houve licitação ou se ela foi dispensada.

Fonte: API oficial de consulta do PNCP, o Portal Nacional de Contratações Públicas (https://pncp.gov.br). Desde a Lei
14.133/2021, prefeituras, câmaras, o estado e a União são obrigados a publicar ali cada compra (com licitação ou sem)
e cada contrato. Documentação: https://pncp.gov.br/api/consulta/swagger-ui/index.html

Consultas usadas (conferidas na sondagem no GitHub Actions em 08/11/2026):
- /v1/contratacoes/publicacao: as compras publicadas num período. A modalidade é obrigatória (uma consulta por
  modalidade); filtra por UF e por município (código do IBGE). No máximo 50 linhas por página.
- /v1/contratos: os contratos assinados, com o fornecedor (quem recebeu). Não filtra por UF nem por cidade, só pelo
  CNPJ do órgão; por isso pedimos os contratos de cada órgão que apareceu nas compras.

O que cada compra mostra:
- se houve licitação: a modalidade (pregão, concorrência...) ou a contratação direta (dispensa, inexigibilidade) e o
  motivo legal que o órgão escolheu (artigo da lei, "amparo legal");
- quanto: valor estimado e valor homologado (o resultado da disputa); o valor de cada contrato;
- quem recebeu: o fornecedor do contrato. Pessoa física aparece só como "Pessoa física", sem nome nem CPF;
- se foi feito: a situação da compra (divulgada, revogada, anulada, suspensa) e o contrato (assinado, em vigor ou já
  encerrado). O PNCP não registra a entrega da obra ou do serviço nem os pagamentos; o site diz isso.

A API responde HTTP 429 (muitas requisições) com facilidade: na sondagem, com 1 segundo entre pedidos, foram só
~10 páginas por minuto. Há PAUSA segundos entre os pedidos e uma espera maior depois de cada 429. Por isso:
- cidades: uma consulta por modalidade cobrindo o ano inteiro (poucas páginas); anos anteriores e o atual;
- estado: centenas de compras por dia em MG (de todas as esferas; a API não filtra por esfera). Só o ano atual,
  mês a mês e modalidade por modalidade, aos poucos, com limite de tempo por execução (MINUTOS), continuando de onde
  parou na execução seguinte. O mês atual vale VALIDADE_MES_ATUAL_ESTADO dias; os anteriores, VALIDADE_MES_ESTADO.
  A primeira leitura completa do ano leva algumas execuções; até lá o site avisa que a leitura está em andamento.
Depois de 3 falhas seguidas o PNCP é dado como fora do ar e a execução usa só o cache.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path

from sa_etl.util import avisar, get, write_json

from . import fontes, siconfi

log = logging.getLogger("mg_etl.pncp")

API = "https://pncp.gov.br/api/consulta/v1"
PAGINA = "https://pncp.gov.br/app/editais"
DOC_API = "https://pncp.gov.br/api/consulta/swagger-ui/index.html"
TAMANHO = 50          # o máximo que a consulta aceita (500 dá HTTP 400 "Tamanho de página inválido")
PAUSA = 4.0           # segundos entre pedidos: com 1 s, HTTP 429 quase o tempo todo (sondagem de 08/11/2026)
ESPERA_429 = 30       # segundos de espera depois de um HTTP 429
MINUTOS = 18          # limite de tempo por execução para a leitura do PNCP (na sondagem, ~7 páginas por minuto)
VALIDADE_RECENTE = 1  # dias: o ano de hoje nas cidades
VALIDADE_MES_ATUAL_ESTADO = 3  # dias: o mês de hoje no estado (umas 100 páginas por leitura)
VALIDADE_ANTIGO = 15  # dias: anos anteriores nas cidades
VALIDADE_MES_ESTADO = 30  # dias: meses anteriores no estado (cada mês do estado tem centenas de páginas)
VALIDADE_CONTRATOS_ESTADO = 7  # dias: contratos do ano de hoje dos órgãos do estado (são muitos órgãos)
MAX_LISTA = 2000      # compras na lista de cada arquivo (as maiores); os totais contam todas
VERSAO = 1

# Códigos de modalidade do PNCP (manual de integração, tabela "Modalidade de Contratação")
MODALIDADES = list(range(1, 15))
FORMA = {8: "dispensa", 9: "inexigibilidade"}
LICITACAO = {1, 2, 3, 4, 5, 6, 7, 13}
ROTULO_FORMA = {"licitacao": "Com licitação", "dispensa": "Sem licitação: dispensa",
                "inexigibilidade": "Sem licitação: inexigibilidade", "outro": "Outro procedimento"}
ESTADO = {"id": "estado", "nome": "Governo de Minas Gerais"}


def forma(modalidade: int) -> str:
    """Se houve disputa: 'licitacao', 'dispensa', 'inexigibilidade' ou 'outro' (credenciamento, pré-qualificação,
    manifestação de interesse, inaplicabilidade da licitação)."""
    return "licitacao" if modalidade in LICITACAO else FORMA.get(modalidade, "outro")


def _agora() -> float:
    return time.monotonic()


class SemTempo(Exception):
    """O limite de tempo desta execução acabou; a leitura continua na próxima."""


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


def _pagina(caminho: str, params: dict) -> dict:
    """Uma página da consulta. HTTP 204 (nada no período) vira página vazia. Com HTTP 429 (muitas requisições),
    espera ESPERA_429 segundos (o dobro a cada vez) antes de tentar de novo."""
    for tentativa in range(4):
        time.sleep(PAUSA)
        try:
            r = get(f"{API}/{caminho}", params=params, timeout=90, tries=1)
            break
        except RuntimeError as e:
            if tentativa == 3:
                raise
            espera = ESPERA_429 * 2 ** tentativa if "429" in str(e) else 10
            log.info("PNCP: %s; nova tentativa em %ss", str(e)[:80], espera)
            time.sleep(espera)
    if r.status_code == 204 or not r.content:
        return {"data": [], "totalRegistros": 0, "paginasRestantes": 0}
    try:
        d = r.json()
    except ValueError as e:
        raise RuntimeError(f"PNCP: resposta que não é JSON em {caminho}") from e
    if not isinstance(d, dict) or not isinstance(d.get("data"), list):
        raise RuntimeError(f"PNCP: resposta inesperada em {caminho} (sem a lista 'data')")
    return d


def _txt(s) -> str:
    return fontes.sem_cpf(re.sub(r"\s+", " ", str(s or "")).strip())


def enxugar_compra(x: dict) -> dict:
    """Só o que o site usa, sem CPF em nenhum texto."""
    org, uni, amp = x.get("orgaoEntidade") or {}, x.get("unidadeOrgao") or {}, x.get("amparoLegal") or {}
    return {
        "id": x.get("numeroControlePNCP") or "",
        "cnpj": fontes.doc_publico(org.get("cnpj")), "ano": x.get("anoCompra"), "seq": x.get("sequencialCompra"),
        "esfera": org.get("esferaId") or "", "orgao": fontes.bonito(_txt(org.get("razaoSocial"))),
        "unidade": fontes.bonito(_txt(uni.get("nomeUnidade"))), "ibge": str(uni.get("codigoIbge") or ""),
        "municipio": uni.get("municipioNome") or "", "uf": uni.get("ufSigla") or "",
        "modalidade": x.get("modalidadeId"), "modalidade_nome": x.get("modalidadeNome") or "",
        "amparo": _txt(amp.get("nome")), "amparo_descricao": _txt(amp.get("descricao")),
        "objeto": _txt(x.get("objetoCompra"))[:600], "processo": _txt(x.get("processo"))[:60],
        "estimado": float(x.get("valorTotalEstimado") or 0), "homologado": float(x.get("valorTotalHomologado") or 0),
        "situacao": x.get("situacaoCompraId"), "situacao_nome": x.get("situacaoCompraNome") or "",
        "data": str(x.get("dataPublicacaoPncp") or "")[:10], "srp": bool(x.get("srp")),
    }


def enxugar_contrato(x: dict) -> dict:
    """Fornecedor pessoa física: sem nome e sem CPF (o PNCP publica os dois, mas o site não repete dado pessoal)."""
    pf = (x.get("tipoPessoa") or "").upper() == "PF"
    cnpj = "" if pf else fontes.doc_publico(x.get("niFornecedor"))
    nome = "Pessoa física" if pf else (fontes.bonito(_txt(x.get("nomeRazaoSocialFornecedor"))) or "Fornecedor sem nome")
    org = x.get("orgaoEntidade") or {}
    return {
        "id": x.get("numeroControlePNCP") or "", "compra": x.get("numeroControlePncpCompra") or "",
        "orgao_cnpj": fontes.doc_publico(org.get("cnpj")), "ano": x.get("anoContrato"), "seq": x.get("sequencialContrato"),
        "tipo": ((x.get("tipoContrato") or {}).get("nome") or ""), "fornecedor": nome, "cnpj": cnpj, "pf": pf,
        "estrangeiro": (x.get("tipoPessoa") or "").upper() == "PE",
        "objeto": _txt(x.get("objetoContrato"))[:300],
        "valor": float(x.get("valorGlobal") or x.get("valorInicial") or 0),
        "assinatura": str(x.get("dataAssinatura") or "")[:10],
        "inicio": str(x.get("dataVigenciaInicio") or "")[:10], "fim": str(x.get("dataVigenciaFim") or "")[:10],
    }


def _meses(ano: int, hoje: dt.date) -> list[tuple[int, int]]:
    """Os meses do ano até o mês de hoje, do mais novo para o mais antigo."""
    return [(ano, m) for m in range(12, 0, -1) if dt.date(ano, m, 1) <= hoje]


def _faixa_mes(ano: int, mes: int, hoje: dt.date) -> tuple[str, str]:
    ini = dt.date(ano, mes, 1)
    fim = (dt.date(ano + (mes == 12), mes % 12 + 1, 1) - dt.timedelta(days=1))
    return ini.strftime("%Y%m%d"), min(fim, hoje).strftime("%Y%m%d")


def _faixa_ano(ano: int, hoje: dt.date) -> tuple[str, str]:
    return f"{ano}0101", min(dt.date(ano, 12, 31), hoje).strftime("%Y%m%d")


class Leitor:
    """Lê o PNCP aos poucos, guardando cada pedaço lido no cache para a próxima execução."""

    def __init__(self, cache: Path, minutos: float = MINUTOS, hoje: dt.date | None = None):
        self.cache = cache / "pncp"
        self.fim = _agora() + minutos * 60
        self.hoje = hoje or dt.date.today()
        self.paginas = 0
        self.sem_tempo = False
        self.falhou = False   # alguma consulta falhou nesta execução (o site avisa)
        self.falhas = 0       # falhas seguidas
        self.fora = False     # o PNCP parou de responder: o resto da execução usa só o cache

    def _tempo(self) -> None:
        if _agora() > self.fim:
            self.sem_tempo = True
            raise SemTempo

    def _vencido(self, st: dict | None, validade: int) -> bool:
        if not st or not st.get("lido_em"):
            return True
        return (self.hoje - dt.date.fromisoformat(st["lido_em"])).days >= validade

    def _todas(self, caminho: str, params: dict, filtro=None, enxugar=enxugar_compra) -> list[dict]:
        linhas, pag = [], 1
        while True:
            self._tempo()
            d = _pagina(caminho, {**params, "pagina": pag, "tamanhoPagina": TAMANHO})
            self.paginas += 1
            linhas += [enxugar(x) for x in d["data"] if filtro is None or filtro(x)]
            if not d["data"] or not d.get("paginasRestantes"):
                return linhas
            pag += 1

    def compras(self, escopo: str, params: dict, rotulo: str, faixa: tuple[str, str], validade: int,
                filtro=None) -> list[dict] | None:
        """Compras de um período (todas as modalidades). None: alguma modalidade ainda não foi lida (sem tempo ou
        fonte fora do ar). Cada modalidade fica no cache separada: se o tempo acabar no meio, o que já foi lido não
        se perde."""
        todas, falta = [], False
        for mod in MODALIDADES:
            f = self.cache / f"compras-{escopo}-{rotulo}-m{mod:02d}-v{VERSAO}.json.gz"
            st = _ler_gz(f)
            if not (self.sem_tempo or self.fora) and self._vencido(st, validade):
                try:
                    linhas = self._todas("contratacoes/publicacao", {**params, "dataInicial": faixa[0], "dataFinal": faixa[1],
                                                                      "codigoModalidadeContratacao": mod}, filtro)
                    st = {"linhas": linhas, "lido_em": self.hoje.isoformat()}
                    _gravar_gz(f, st)
                    self.falhas = 0
                except SemTempo:
                    pass
                except Exception as e:  # noqa: BLE001 - fonte fora do ar: fica a leitura anterior
                    log.warning("PNCP %s %s modalidade %d: %s", escopo, rotulo, mod, e)
                    self._falha()
            if st is None:
                falta = True
            else:
                todas += st["linhas"]
        return None if falta else list({x["id"]: x for x in todas}.values())

    def _falha(self) -> None:
        """Depois de 3 falhas seguidas, o PNCP é dado como fora do ar nesta execução: usa só o cache."""
        self.falhou = True
        self.falhas += 1
        if self.falhas >= 3:
            self.fora = True

    def contratos(self, cnpj: str, ano: int, validade: int) -> list[dict] | None:
        """Contratos publicados por um órgão num ano."""
        f = self.cache / f"contratos-{cnpj}-{ano}-v{VERSAO}.json.gz"
        st = _ler_gz(f)
        if self.sem_tempo or self.fora or not self._vencido(st, validade if ano == self.hoje.year else VALIDADE_ANTIGO):
            return st["linhas"] if st else None
        fim = min(dt.date(ano, 12, 31), self.hoje)
        try:
            linhas = self._todas("contratos", {"cnpjOrgao": cnpj, "dataInicial": f"{ano}0101",
                                               "dataFinal": fim.strftime("%Y%m%d")}, enxugar=enxugar_contrato)
        except SemTempo:
            return st["linhas"] if st else None
        except Exception as e:  # noqa: BLE001
            log.warning("PNCP contratos %s %d: %s", cnpj, ano, e)
            self._falha()
            return st["linhas"] if st else None
        unicos = list({x["id"]: x for x in linhas}.values())
        _gravar_gz(f, {"linhas": unicos, "lido_em": self.hoje.isoformat()})
        self.falhas = 0
        return unicos


# ---------------------------------------------------------------- montagem

def andamento(c: dict, contratos: list[dict], hoje: dt.date) -> str:
    """Em que pé está, pelo que o PNCP registra."""
    sit = c.get("situacao")
    if sit == 2:
        return "Revogada"
    if sit == 3:
        return "Anulada"
    if sit == 4:
        return "Suspensa"
    if contratos:
        fins = [x["fim"] for x in contratos if x.get("fim")]
        if fins and max(fins) < hoje.isoformat():
            return "Contrato encerrado"
        return "Contrato em vigor"
    if c.get("homologado"):
        return "Concluída, sem contrato no PNCP"
    return "Sem resultado publicado"


def link_compra(c: dict) -> str:
    return f"{PAGINA}/{c['cnpj']}/{c['ano']}/{c['seq']}" if c.get("cnpj") and c.get("ano") and c.get("seq") else PAGINA


def link_contrato(x: dict) -> str:
    if x.get("orgao_cnpj") and x.get("ano") and x.get("seq"):
        return f"https://pncp.gov.br/app/contratos/{x['orgao_cnpj']}/{x['ano']}/{x['seq']}"
    return "https://pncp.gov.br/app/contratos"


def resumir(local: dict, ano: int, compras: list[dict], contratos: list[dict], hoje: dt.date,
            faltam: list[str], fonte_api: str) -> dict:
    """O arquivo de um lugar (cidade ou estado) num ano: totais, quem mais recebeu, órgãos, motivos da contratação
    direta e a lista das compras (as MAX_LISTA maiores), cada uma com os contratos e o link do PNCP."""
    por_compra = defaultdict(list)
    for x in contratos:
        por_compra[x["compra"]].append(x)
    formas = defaultdict(lambda: {"n": 0, "estimado": 0.0, "homologado": 0.0, "contratado": 0.0})
    situacoes: dict[str, int] = defaultdict(int)
    orgaos = defaultdict(lambda: {"nome": "", "cnpj": "", "n": 0, "valor": 0.0})
    amparos = defaultdict(lambda: {"nome": "", "descricao": "", "forma": "", "n": 0, "valor": 0.0})
    lista = []
    for c in compras:
        cs = por_compra.get(c["id"], [])
        fm = forma(c.get("modalidade") or 0)
        valor = c["homologado"] or c["estimado"]
        contratado = round(sum(x["valor"] for x in cs), 2)
        anda = andamento(c, cs, hoje)
        cancelada = anda in ("Revogada", "Anulada")
        situacoes[anda] += 1
        f = formas[fm]
        f["n"] += 1
        if not cancelada:  # compra revogada ou anulada não gastou
            f["estimado"] += c["estimado"]
            f["homologado"] += c["homologado"]
            f["contratado"] += contratado
            o = orgaos[c["cnpj"] or c["orgao"]]
            o.update(nome=c["orgao"], cnpj=c["cnpj"])
            o["n"] += 1
            o["valor"] += c["homologado"]  # o estimado de uma ata de registro de preço é um teto, não gasto
            if fm != "licitacao" and c.get("amparo"):
                a = amparos[c["amparo"]]
                a.update(nome=c["amparo"], descricao=c["amparo_descricao"], forma=fm)
                a["n"] += 1
                a["valor"] += c["homologado"]
        lista.append({
            "id": c["id"], "data": c["data"], "orgao": c["orgao"], "unidade": c["unidade"] if c["unidade"] != c["orgao"] else "",
            "forma": fm, "modalidade": c["modalidade_nome"], "amparo": c["amparo"], "amparo_descricao": c["amparo_descricao"],
            "objeto": c["objeto"], "processo": c["processo"], "estimado": round(c["estimado"], 2),
            "homologado": round(c["homologado"], 2), "valor": round(valor, 2), "situacao": c["situacao_nome"],
            "andamento": anda, "url": link_compra(c),
            "contratos": [{"fornecedor": x["fornecedor"], "cnpj": x["cnpj"], "valor": round(x["valor"], 2),
                           "assinatura": x["assinatura"], "fim": x["fim"], "tipo": x["tipo"], "url": link_contrato(x)}
                          for x in sorted(cs, key=lambda x: -x["valor"])],
        })
    # Quem recebeu: soma dos contratos do ano (todos os do órgão, inclusive de compras de anos anteriores)
    forn = defaultdict(lambda: {"nome": "", "cnpj": "", "valor": 0.0, "n": 0})
    for x in contratos:
        k = x["cnpj"] or ("PF" if x["pf"] else x["fornecedor"])
        g = forn[k]
        g.update(nome=x["fornecedor"], cnpj=x["cnpj"])
        g["valor"] += x["valor"]
        g["n"] += 1
    lista.sort(key=lambda x: (-x["valor"], x["data"]))
    total = {k: round(sum(f[k] for f in formas.values()), 2) for k in ("estimado", "homologado", "contratado")}
    total["n"] = len(compras)
    total["contratos"] = len(contratos)
    total["valor_contratos"] = round(sum(x["valor"] for x in contratos), 2)
    arred = lambda d: {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}  # noqa: E731
    return {
        "id": local["id"], "nome": local["nome"], "ano": ano, "atualizado": hoje.isoformat(),
        "fonte": PAGINA, "api": fonte_api, "completo": not faltam, "faltam": faltam,
        "total": total,
        "por_forma": [{"forma": k, "rotulo": ROTULO_FORMA[k], **arred(formas[k])} for k in ROTULO_FORMA if k in formas],
        "por_andamento": [{"andamento": k, "n": v} for k, v in sorted(situacoes.items(), key=lambda x: -x[1])],
        "orgaos": [arred(o) for o in sorted(orgaos.values(), key=lambda o: -o["valor"])[:30]],
        "fornecedores": [arred(g) for g in sorted(forn.values(), key=lambda g: -g["valor"])[:100]],
        "amparos": [arred(a) for a in sorted(amparos.values(), key=lambda a: -a["n"])[:15]],
        "n_lista": min(len(lista), MAX_LISTA),
        "compras": lista[:MAX_LISTA],
    }


def _do_ano(compras: list[dict], ano: int) -> list[dict]:
    return [c for c in compras if (c.get("data") or "")[:4] == str(ano)]


def coletar(saida: Path, cache: Path, cidades: list[dict], anos: list[int] | None = None, minutos: float = MINUTOS,
            hoje: dt.date | None = None) -> dict:
    """Grava licitacoes/<lugar>-<ano>.json e licitacoes/index.json. Devolve {lugar: número de compras}."""
    hoje = hoje or dt.date.today()
    anos = anos or [hoje.year - 1, hoje.year]
    ler = Leitor(cache, minutos, hoje)
    esfera = lambda e: lambda x: (x.get("orgaoEntidade") or {}).get("esferaId") == e  # noqa: E731
    # Cada lugar: (local, escopo do cache, filtros da API, pedaços [(ano, rótulo, faixa, validade)], filtro, validade dos contratos)
    locais = []
    # 1. Cidades: poucas compras, consulta pelo código do IBGE; só os órgãos da prefeitura e da câmara (esfera
    #    municipal). A universidade federal, o exército e as escolas estaduais da cidade ficam de fora.
    for c in cidades:
        ibge = siconfi.codigo_ibge(c["nome"], c["uf"], cache)
        if not ibge:
            avisar(f"Licitações de {c['nome']}: código do IBGE não encontrado; essa parte ficou sem atualização")
            continue
        chave = fontes.chave_nome(c["nome"])
        pedacos = [(a, str(a), _faixa_ano(a, hoje), VALIDADE_RECENTE if a == hoje.year else VALIDADE_ANTIGO) for a in anos]
        # o município da compra tem de ser a própria cidade (proteção contra código do IBGE trocado)
        filtro = (lambda chave: lambda x: esfera("M")(x) and fontes.chave_nome((x.get("unidadeOrgao") or {}).get("municipioNome") or "") == chave)(chave)
        locais.append(({"id": c["id"], "nome": c["nome"]}, f"c{ibge}", {"uf": c["uf"], "codigoMunicipioIbge": str(ibge)},
                       pedacos, filtro, VALIDADE_RECENTE))
    # 2. Estado: todas as compras de MG, só as dos órgãos do estado (esfera estadual); só o ano atual
    pedacos = [(a, f"{a}{m:02d}", _faixa_mes(a, m, hoje), VALIDADE_MES_ATUAL_ESTADO if (a, m) == (hoje.year, hoje.month) else VALIDADE_MES_ESTADO)
               for a, m in _meses(hoje.year, hoje)]
    locais.append((ESTADO, "mg-estado", {"uf": "MG"}, pedacos, esfera("E"), VALIDADE_CONTRATOS_ESTADO))

    resumo: dict = {}
    indice = []
    for local, escopo, params, pedacos, filtro, val_contratos in locais:
        compras, faltam = [], []
        for ano, rotulo, faixa, validade in pedacos:
            ls = ler.compras(escopo, params, rotulo, faixa, validade, filtro)
            if ls is None:
                faltam.append(f"{rotulo[:4]}-{rotulo[4:]}" if len(rotulo) == 6 else rotulo)
            else:
                compras += ls
        cnpjs = sorted({c["cnpj"] for c in compras if c["cnpj"]})
        anos_local = []
        for ano in sorted({p[0] for p in pedacos}):
            contratos, sem_contratos = [], 0
            for cnpj in cnpjs:
                ls = ler.contratos(cnpj, ano, val_contratos)
                if ls is None:
                    sem_contratos += 1
                else:
                    contratos += ls
            do_ano = _do_ano(compras, ano)
            falta_ano = [f for f in faltam if f.startswith(str(ano))]
            if not do_ano and falta_ano:
                continue  # nada lido ainda deste ano: o site não mostra um ano vazio como se fosse zero
            if sem_contratos:
                falta_ano.append(f"contratos de {sem_contratos} órgão(s)")
            api = f"{API}/contratacoes/publicacao?uf={params['uf']}" + (
                f"&codigoMunicipioIbge={params['codigoMunicipioIbge']}" if "codigoMunicipioIbge" in params else "")
            d = resumir(local, ano, do_ano, contratos, hoje, falta_ano, api)
            write_json(saida / "licitacoes" / f"{local['id']}-{ano}.json", d)
            anos_local.append({"ano": ano, "n": d["total"]["n"], "completo": d["completo"]})
            resumo[f"{local['id']}-{ano}"] = d["total"]["n"]
        if anos_local:
            indice.append({**local, "anos": sorted(anos_local, key=lambda x: -x["ano"])})
        if faltam:
            log.info("PNCP %s: faltam %s; a leitura continua na próxima execução", local["nome"], ", ".join(faltam))
    if ler.falhou:
        avisar("Licitações (PNCP): o portal não respondeu em parte das consultas; usamos a última leitura guardada")
    incompletos = [x["nome"] for x in indice if not all(a["completo"] for a in x["anos"])]
    if incompletos:
        avisar(f"Licitações (PNCP): leitura ainda em andamento para {', '.join(incompletos)}; os números vão crescer nas "
               "próximas atualizações", tentar_de_novo=False)
    write_json(saida / "licitacoes" / "index.json", {"fonte": "https://pncp.gov.br", "api": DOC_API,
                                                      "atualizado": hoje.isoformat(), "locais": indice})
    log.info("PNCP: %d páginas lidas nesta execução", ler.paginas)
    return resumo
