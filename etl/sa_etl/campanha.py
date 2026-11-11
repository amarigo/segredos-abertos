"""Dinheiro da campanha: quem pagou a campanha de cada parlamentar, a quem a campanha pagou, e onde esse dinheiro
encontra o dinheiro do mandato (cota parlamentar e emendas) e os donos das empresas.

De onde vem cada dado (API primeiro):
1. Contas de campanha (receitas, doador originário e despesas contratadas) dos candidatos de 2018, 2022 e 2026:
   arquivo oficial "Prestação de contas de candidatos" do Portal de Dados Abertos do TSE. O endereço do arquivo vem da
   API do portal (CKAN, dadosabertos.tse.jus.br/api/3/action/package_show); o arquivo em si fica no CDN do TSE
   (cdn.tse.jus.br). Não há API com as receitas e despesas linha a linha: a API do DivulgaCandContas
   (divulgacandcontas.tse.jus.br/divulga/rest) recusa acesso automático (HTTP 403, conferido do GitHub Actions em
   04/11/2026, veja eleicao2026/etl/el_etl/eleitos.py) e devolve só totais de um candidato por vez.
2. CPF e nome civil de cada deputado: API da Câmara (/deputados/{id}). Nome civil dos senadores: API do Senado
   (/senador/{codigo}). O CPF serve só para achar a candidatura certa no arquivo do TSE: aqui ele vira um resumo
   (hash) e nunca é gravado nem publicado.
3. Sócios das empresas: base CNPJ da Receita, já lida em cnpj.py.

As ligações seguem a regra da pesquisa do projeto (pesquisa/Novas fontes e doações políticas.md):
- fornecedor de campanha = fornecedor da cota ou de emenda do mesmo parlamentar: mesmo CNPJ (mesma raiz), chave exata;
- doador de campanha = sócio de empresa paga pela cota ou por emenda do mesmo parlamentar: nome completo igual E os 6
  dígitos do meio do CPF iguais. A Receita só mostra esses 6 dígitos do sócio (***123456**), então é a mesma chave de
  cnpj.chave_socio. Sem os dois, não liga;
- o próprio parlamentar como sócio de empresa paga pela cota ou por emendas: mesma chave, com o CPF da candidatura.
Nenhuma ligação diz que houve irregularidade: o site mostra os fatos, com a data e o link de cada um.

Do TSE ficam só os campos abaixo. CPF de doador e de fornecedor pessoa física sai mascarado como a Receita faz
(***.123.456-**); o CPF do candidato não sai.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import logging
import re
import tempfile
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from . import cnpj as cnpj_mod
from . import util
from .util import digits, get_json, mask_cpf, norm_name, write_json

log = logging.getLogger("sa_etl.campanha")

ANOS = (2018, 2022, 2026)
# Cargos lidos no arquivo de cada estado: governador (3), senador (5) e deputado federal (6). Um deputado ou senador de
# hoje pode ter concorrido a qualquer um deles.
CARGOS = {"3": "Governador", "5": "Senador", "6": "Deputado Federal"}

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id={id}"
# O conjunto de 2022 ganhou outro nome no portal; os dois são tentados.
PACOTES = ("prestacao-de-contas-eleitorais-{ano}", "dadosabertos-tse-jus-br-dataset-prestacao-de-contas-eleitorais-{ano}")
ARQUIVO = "prestacao_de_contas_eleitorais_candidatos_{ano}.zip"
RESERVA = "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas/" + ARQUIVO  # se a API do portal falhar
PAGINA = "https://dadosabertos.tse.jus.br/dataset/{pacote}"
DIVULGA = "https://divulgacandcontas.tse.jus.br/divulga/#/"

CAMARA = "https://dadosabertos.camara.leg.br/api/v2/deputados/{id}"
SENADO = "https://legis.senado.leg.br/dadosabertos/senador/{id}.json"

# A campanha de 2026 ainda muda: a prestação final do 2º turno vence em 14/11/2026, e entregas atrasadas e
# retificações chegam por semanas. O ano da eleição mais recente é conferido a cada coleta (pergunta só se o arquivo
# mudou, sem baixar); os anteriores, uma vez por mês.
DIAS_ANO_ANTIGO = 30
N_LISTA = 15  # doadores e fornecedores mostrados por campanha (as ligações usam todos)
# Empresa que a cota de muitos parlamentares paga (Correios, companhias aéreas, telefonia, Facebook): a ligação continua
# na página, mas separada, porque coincidir com ela diz pouco. Medido nos dados de 10/11/2026: das 6.854 ligações por
# fornecedor, 5.994 são com empresas pagas por até 10 parlamentares; o resto é dominado por Facebook (317) e Correios (64).
N_COMUM = 10

# ------------------------------------------------------------------ leitura dos arquivos do TSE


def valor(s: str) -> float:
    """'1.234,56' -> 1234.56"""
    s = (s or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def data_iso(s: str) -> str:
    """'31/08/2022' -> '2022-08-31'"""
    p = (s or "").strip().split("/")
    return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 and len(p[2]) == 4 else ""


def nulo(s: str | None) -> str:
    s = (s or "").strip()
    return "" if s in ("#NULO", "#NULO#", "-1", "#NE", "#NE#") else s


def resumo_cpf(cpf: str) -> str:
    """O CPF do candidato só serve para achar a candidatura: guardamos um resumo (hash), nunca o número."""
    d = digits(cpf)
    return hashlib.sha256(f"sa-cpf|{d}".encode()).hexdigest()[:24] if len(d) == 11 else ""


def meio_cpf(cpf: str) -> str:
    """Os 6 dígitos do meio, no formato em que a Receita mostra o CPF do sócio (***123456**)."""
    d = digits(cpf)
    return f"***{d[3:9]}**" if len(d) == 11 else ""


CPF_NO_TEXTO = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")


def sem_cpf(texto: str) -> str:
    """Tira CPF escrito dentro de um nome (o TSE às vezes publica "JOAO DA SILVA 12345678909" no nome do fornecedor,
    e a razão social de empresário individual costuma trazer o CPF inteiro)."""
    return " ".join(CPF_NO_TEXTO.sub("", texto or "").split())


def doc_publico(doc: str) -> str:
    """CNPJ inteiro; CPF mascarado (***.123.456-**)."""
    d = digits(doc)
    return mask_cpf(d) if len(d) == 11 else d if len(d) == 14 else ""


def linhas_csv(z: zipfile.ZipFile, nome: str) -> Iterator[dict[str, str]]:
    """Linhas de um CSV dentro do ZIP do TSE (separado por ';', em latin-1), lidas aos poucos."""
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")


def _arquivo(z: zipfile.ZipFile, prefixo: str, ano: int) -> str | None:
    """O arquivo com todos os estados (_BRASIL). Os de cada UF e o _BR (presidente) ficam de fora."""
    nomes = z.namelist()
    for n in (f"{prefixo}_{ano}_BRASIL.csv",):
        if n in nomes:
            return n
    return None


def tipo_doador(origem: str, doc: str) -> str:
    o = (origem or "").lower()
    if "partido" in o:
        return "partido"
    if "outros candidatos" in o:
        return "candidato"
    if "próprios" in o or "proprios" in o:
        return "proprio"
    if "financiamento coletivo" in o or "internet" in o:
        return "coletivo"
    if "não identificad" in o or "nao identificad" in o:
        return "nao_identificado"
    if "aplica" in o:
        return "rendimento"
    if "fundo especial" in o or "fundo partid" in o:
        return "partido"
    return "pessoa" if len(digits(doc)) == 11 else "empresa" if len(digits(doc)) == 14 else "outro"


def _somar(d: dict, chave: Any, v: float) -> None:
    d[chave] = d.get(chave, 0.0) + v


def extrair(zip_path: Path, ano: int, cargos: Iterable[str] = CARGOS) -> dict[str, dict]:
    """Lê o ZIP do TSE e devolve, por candidatura (SQ_CANDIDATO), o resumo da campanha.

    Os doadores e fornecedores ficam todos (agrupados por documento), para as ligações; o site mostra os maiores.
    """
    cargos = set(cargos)
    cands: dict[str, dict] = {}
    prestador: dict[str, str] = {}  # SQ_PRESTADOR_CONTAS -> SQ_CANDIDATO
    with zipfile.ZipFile(zip_path) as z:
        nome = _arquivo(z, "receitas_candidatos", ano)
        if not nome:
            raise ValueError(f"TSE {ano}: o ZIP não tem o arquivo de receitas de todos os estados (_BRASIL)")
        gerado = ""

        def cand(r: dict) -> dict:
            sq = r["SQ_CANDIDATO"].strip()
            c = cands.get(sq)
            if c is None:
                c = cands[sq] = {
                    "sq": sq, "ano": ano, "nome": r["NM_CANDIDATO"].strip(), "cpf": resumo_cpf(r.get("NR_CPF_CANDIDATO", "")),
                    "meio_cpf": meio_cpf(r.get("NR_CPF_CANDIDATO", "")),
                    "uf": r["SG_UF"].strip(), "cd_cargo": r["CD_CARGO"].strip(), "cargo": r["DS_CARGO"].strip(),
                    "partido": r["SG_PARTIDO"].strip(), "numero": r.get("NR_CANDIDATO", "").strip(),
                    "eleicao": r.get("CD_ELEICAO", "").strip(), "cnpj_campanha": nulo(r.get("NR_CNPJ_PRESTADOR_CONTA")),
                    "prestacao": r.get("TP_PRESTACAO_CONTAS", "").strip(), "data_prestacao": data_iso(r.get("DT_PRESTACAO_CONTAS", "")),
                    "receitas": {"total": 0.0, "financeiro": 0.0, "estimavel": 0.0, "n": 0, "por_origem": {}, "por_fonte": {}},
                    "doadores": {}, "originarios": {},
                    "despesas": {"total": 0.0, "n": 0, "por_tipo": {}}, "fornecedores": {},
                }
            sqp = r.get("SQ_PRESTADOR_CONTAS", "").strip()
            if sqp:
                prestador[sqp] = sq
            return c

        for r in linhas_csv(z, nome):
            gerado = gerado or data_iso(r.get("DT_GERACAO", ""))
            if r.get("CD_CARGO", "").strip() not in cargos:
                continue
            c = cand(r)
            v = valor(r.get("VR_RECEITA", ""))
            rc = c["receitas"]
            rc["total"] += v
            rc["n"] += 1
            nat = (r.get("DS_NATUREZA_RECEITA") or "").lower()
            rc["estimavel" if "estim" in nat else "financeiro"] += v
            origem = nulo(r.get("DS_ORIGEM_RECEITA")) or "Não informada"
            _somar(rc["por_origem"], origem, v)
            _somar(rc["por_fonte"], nulo(r.get("DS_FONTE_RECEITA")) or "Não informada", v)
            doc = digits(r.get("NR_CPF_CNPJ_DOADOR"))
            tipo = tipo_doador(origem, doc)
            nome_d = sem_cpf(nulo(r.get("NM_DOADOR_RFB")) or nulo(r.get("NM_DOADOR"))) or "Não informado"
            if tipo == "partido":
                partido = nulo(r.get("SG_PARTIDO_DOADOR"))
                esfera = nulo(r.get("DS_ESFERA_PARTIDARIA_DOADOR"))
                nome_d = " · ".join(x for x in (f"{partido}" if partido else nome_d, esfera) if x)
            k = doc or nome_d
            d = c["doadores"].setdefault(k, {"nome": nome_d, "doc": doc_publico(doc), "meio_cpf": meio_cpf(doc) if tipo in ("pessoa", "proprio") else "",
                                             "tipo": tipo, "valor": 0.0, "n": 0, "origens": {}})
            d["valor"] += v
            d["n"] += 1
            _somar(d["origens"], origem, v)

        nome = _arquivo(z, "receitas_candidatos_doador_originario", ano)
        if nome:  # quem deu o dinheiro que chegou pelo partido, por outro candidato ou por vaquinha
            for r in linhas_csv(z, nome):
                sq = prestador.get(r.get("SQ_PRESTADOR_CONTAS", "").strip())
                if not sq:
                    continue
                c = cands[sq]
                doc = digits(r.get("NR_CPF_CNPJ_DOADOR_ORIGINARIO"))
                v = valor(r.get("VR_RECEITA", ""))
                nome_d = sem_cpf(nulo(r.get("NM_DOADOR_ORIGINARIO_RFB")) or nulo(r.get("NM_DOADOR_ORIGINARIO"))) or "Não informado"
                pessoa = (r.get("TP_DOADOR_ORIGINARIO") or "").strip().upper() == "F" or len(doc) == 11
                d = c["originarios"].setdefault(doc or nome_d, {"nome": nome_d, "doc": doc_publico(doc),
                                                                "meio_cpf": meio_cpf(doc) if pessoa else "",
                                                                "tipo": "pessoa" if pessoa else "empresa", "valor": 0.0, "n": 0,
                                                                "como": sem_cpf(nulo(r.get("DS_RECEITA")))})
                d["valor"] += v
                d["n"] += 1

        nome = _arquivo(z, "despesas_contratadas_candidatos", ano)
        if nome:
            for r in linhas_csv(z, nome):
                if r.get("CD_CARGO", "").strip() not in cargos:
                    continue
                c = cand(r)
                v = valor(r.get("VR_DESPESA_CONTRATADA", ""))
                dp = c["despesas"]
                dp["total"] += v
                dp["n"] += 1
                tipo = nulo(r.get("DS_ORIGEM_DESPESA")) or "Não informado"
                _somar(dp["por_tipo"], tipo, v)
                doc = digits(r.get("NR_CPF_CNPJ_FORNECEDOR"))
                nome_f = sem_cpf(nulo(r.get("NM_FORNECEDOR_RFB")) or nulo(r.get("NM_FORNECEDOR"))) or "Não informado"
                f = c["fornecedores"].setdefault(doc or nome_f, {"nome": nome_f, "doc": doc_publico(doc), "valor": 0.0, "n": 0, "tipos": {}})
                f["valor"] += v
                f["n"] += 1
                _somar(f["tipos"], tipo, v)
    for c in cands.values():
        c["gerado_em"] = gerado
    log.info("TSE %s: %d candidaturas (governador, senador, deputado federal) com contas", ano, len(cands))
    return cands


# ------------------------------------------------------------------ baixar (com cópia guardada)


def achar_arquivo(ano: int, buscar: Callable = get_json) -> tuple[str, str]:
    """(endereço do ZIP, nome do conjunto no portal), pela API do portal de dados abertos do TSE."""
    alvo = ARQUIVO.format(ano=ano)
    for pid in PACOTES:
        pid = pid.format(ano=ano)
        try:
            pac = (buscar(CKAN.format(id=pid), tries=2) or {}).get("result") or {}
        except Exception as e:  # noqa: BLE001
            log.info("TSE: conjunto %s não respondeu (%s)", pid, e)
            continue
        for r in pac.get("resources") or []:
            if (r.get("url") or "").rstrip("/").endswith(alvo):
                return r["url"], pac.get("name") or pid
    log.warning("TSE %s: a API do portal não achou o arquivo; usando o endereço conhecido", ano)
    return RESERVA.format(ano=ano), PACOTES[0].format(ano=ano)


def _versao(url: str) -> str:
    """ETag ou data do arquivo no CDN, sem baixar (pedido HEAD)."""
    r = util._session.head(url, timeout=60, allow_redirects=True)
    r.raise_for_status()
    return r.headers.get("ETag") or r.headers.get("Last-Modified") or ""


def _baixar(url: str, destino: Path) -> None:
    """Baixa aos poucos (os arquivos têm de 300 a 500 MB): nada fica inteiro na memória."""
    ultimo: Exception | None = None
    for i in range(4):
        try:
            with util._session.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                with open(destino, "wb") as f:
                    for parte in r.iter_content(1 << 20):
                        f.write(parte)
            if not zipfile.is_zipfile(destino):
                raise ValueError(f"{url} não devolveu um ZIP")
            return
        except Exception as e:  # noqa: BLE001
            ultimo = e
            log.warning("TSE: falha ao baixar %s (%s); nova tentativa em %ss", url, e, 2 ** (i + 2))
            time.sleep(2 ** (i + 2))
    raise RuntimeError(f"Não foi possível baixar {url}: {ultimo}")


def _ler_copia(f: Path) -> dict | None:
    try:
        with gzip.open(f, "rt", encoding="utf-8") as g:
            return json.load(g)
    except (OSError, ValueError):
        return None


def _gravar_copia(f: Path, dados: dict) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    with gzip.open(tmp, "wt", encoding="utf-8") as g:
        json.dump(dados, g, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(f)


def contas_do_ano(ano: int, cache: Path, hoje: dt.date | None = None, buscar: Callable = get_json,
                  versao: Callable[[str], str] = _versao, baixar: Callable[[str, Path], None] = _baixar) -> dict | None:
    """Resumo das contas de campanha de um ano, guardado em cache/campanha/{ano}.json.gz.

    Só baixa o ZIP de novo quando o TSE troca o arquivo (ETag diferente). Se o TSE falhar, fica a última cópia boa, com
    aviso e a data dela."""
    hoje = hoje or dt.date.today()
    f = cache / f"{ano}.json.gz"
    copia = _ler_copia(f)
    recente = ano >= max(ANOS)
    if copia and not recente and time.time() - f.stat().st_mtime < DIAS_ANO_ANTIGO * 86400:
        return copia
    try:
        url, pacote = achar_arquivo(ano, buscar)
        v = versao(url)
        if copia and v and copia.get("versao") == v:
            f.touch()
            return copia
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / f"tse-{ano}.zip"
            baixar(url, z)
            cands = extrair(z, ano)
        if not cands:
            raise ValueError(f"o arquivo de {ano} veio sem nenhuma candidatura")
        dados = {"ano": ano, "versao": v, "url": url, "pacote": pacote, "fonte": PAGINA.format(pacote=pacote),
                 "baixado_em": hoje.isoformat(), "gerado_em": next(iter(cands.values()))["gerado_em"], "candidatos": cands}
        _gravar_copia(f, dados)
        return dados
    except Exception as e:  # noqa: BLE001
        if copia:
            log.warning("TSE %s: fonte fora do ar (%s); usando a cópia de %s", ano, e, copia.get("baixado_em"))
            util.avisar(f"Dinheiro da campanha {ano}: o TSE não respondeu; usamos a cópia de {copia.get('baixado_em')}")
            return copia
        log.exception("TSE %s: contas de campanha indisponíveis", ano)
        util.avisar(f"Dinheiro da campanha {ano}: o arquivo do TSE não foi lido nesta coleta")
        return None


# ------------------------------------------------------------------ quem é quem: parlamentar -> candidatura


def _pessoa_camara(num: str, buscar: Callable) -> dict:
    d = (buscar(CAMARA.format(id=num)) or {}).get("dados") or {}
    return {"cpf": resumo_cpf(d.get("cpf") or ""), "meio_cpf": meio_cpf(d.get("cpf") or ""),
            "nome_civil": (d.get("nomeCivil") or "").strip()}


def _pessoa_senado(num: str, buscar: Callable) -> dict:
    p = ((buscar(SENADO.format(id=num)) or {}).get("DetalheParlamentar") or {}).get("Parlamentar") or {}
    ident = p.get("IdentificacaoParlamentar") or {}
    return {"cpf": "", "meio_cpf": "", "nome_civil": (ident.get("NomeCompletoParlamentar") or "").strip()}


def pessoas(politicos: list[dict], cache: Path, buscar: Callable = get_json, workers: int = 6) -> dict[str, dict]:
    """CPF (só o resumo e os 6 dígitos do meio) e nome civil de cada parlamentar, guardados para sempre: não mudam."""
    pasta = cache / "pessoas"
    out: dict[str, dict] = {}
    faltam = []
    for p in politicos:
        f = pasta / f"{p['id']}.json"
        try:
            out[p["id"]] = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            faltam.append(p)

    def uma(p: dict) -> tuple[str, dict | None]:
        num = p["id"].split("-", 1)[-1]
        try:
            x = _pessoa_camara(num, buscar) if p["casa"] == "camara" else _pessoa_senado(num, buscar)
        except Exception as e:  # noqa: BLE001
            log.info("Campanha: sem nome civil de %s (%s)", p["id"], e)
            return p["id"], None
        if not x["nome_civil"] and not x["cpf"]:
            return p["id"], None
        write_json(pasta / f"{p['id']}.json", x)
        return p["id"], x

    if faltam:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for k, x in ex.map(uma, faltam):
                if x:
                    out[k] = x
        log.info("Campanha: nome civil e CPF de %d parlamentares buscados agora (%d guardados)", len(faltam), len(out))
    return out


def chave_nome(nome: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in norm_name(nome)).split())


def ligar_candidaturas(politicos: list[dict], pess: dict[str, dict], contas: dict[int, dict]) -> dict[str, list[dict]]:
    """Para cada parlamentar, as candidaturas dele (uma por ano), da mais nova para a mais antiga.

    1º pelo CPF (deputados: o mesmo CPF na API da Câmara e no TSE). 2º, só para quem não tem CPF na fonte (senadores),
    pelo nome civil completo e a UF, quando há uma única pessoa com esse nome naquela UF e naquele ano. Nome parecido
    não basta."""
    por_cpf: dict[tuple[int, str], list[dict]] = defaultdict(list)
    por_nome: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
    for ano, dados in contas.items():
        for c in (dados or {}).get("candidatos", {}).values():
            if c.get("cpf"):
                por_cpf[(ano, c["cpf"])].append(c)
            por_nome[(ano, chave_nome(c["nome"]), c["uf"])].append(c)
    out: dict[str, list[dict]] = {}
    for p in politicos:
        x = pess.get(p["id"]) or {}
        achadas = []
        for ano in sorted(contas, reverse=True):
            cs = por_cpf.get((ano, x.get("cpf") or "-")) or []
            como = "cpf"
            # Com o CPF do parlamentar, só o CPF decide: CPF diferente é outra pessoa, mesmo com o nome igual.
            if not cs and not x.get("cpf") and x.get("nome_civil"):
                cs = por_nome.get((ano, chave_nome(x["nome_civil"]), p["uf"])) or []
                # duas pessoas diferentes com o mesmo nome na mesma UF: não dá para saber qual é
                if len({c.get("cpf") or c["sq"] for c in cs}) > 1:
                    cs = []
                como = "nome"
            if cs:
                # mesma pessoa com duas candidaturas no ano (trocou de cargo): fica a que tem as contas
                c = max(cs, key=lambda c: (c["receitas"]["total"] + c["despesas"]["total"], c["receitas"]["n"]))
                achadas.append({**c, "achada_por": como})
        if achadas:
            out[p["id"]] = achadas
    return out


# ------------------------------------------------------------------ ligações com o mandato


def _raiz(doc: str) -> str:
    d = digits(doc)
    return d[:8] if len(d) == 14 else ""


def _top(d: dict, n: int, campos: Callable[[dict], dict]) -> list[dict]:
    return [campos(x) for x in sorted(d.values(), key=lambda x: -x["valor"])[:n]]


def _r(v: float) -> float:
    return round(v + 0.0, 2)


def ligacoes(pid: str, cands: list[dict], cota: dict[str, dict], emenda: dict[str, dict],
             donos: dict[str, list[tuple[str, str, str]]], emps: dict[str, dict], pess: dict,
             npol: dict[str, int] | None = None) -> list[dict]:
    """Os pontos em que o dinheiro da campanha encontra o do mandato de um parlamentar.

    cota: raiz do CNPJ -> {"cnpj", "nome", "valor", "de", "ate"} do que este parlamentar pagou pela cota.
    emenda: raiz -> {"cnpj", "nome", "valor"} do que as emendas dele pagaram.
    donos: chave de sócio (nome|***123456**) -> [(cnpj, papel, qualificação)] das empresas pagas por ele.
    """
    out: list[dict] = []
    vistos: set[tuple] = set()

    npol = npol or {}

    def mandato(raiz: str) -> dict:
        c, e = cota.get(raiz), emenda.get(raiz)
        n = npol.get(raiz, 0)
        return {**({"cota": _r(c["valor"]), "cota_de": c["de"], "cota_ate": c["ate"]} if c else {}),
                **({"emendas": _r(e["valor"])} if e else {}),
                "n_parlamentares": n, **({"comum": True} if n > N_COMUM else {})}

    for c in cands:
        for f in c["fornecedores"].values():
            raiz = _raiz(f["doc"])
            if not raiz or (raiz not in cota and raiz not in emenda):
                continue
            k = ("fornecedor", c["ano"], raiz)
            if k in vistos:
                continue
            vistos.add(k)
            alvo = (cota.get(raiz) or emenda.get(raiz))["cnpj"]
            out.append({"tipo": "fornecedor", "ano": c["ano"], "empresa": {"cnpj": alvo, "nome": (emps.get(alvo) or {}).get("razao_social") or f["nome"]},
                        "cnpj_campanha": f["doc"], "campanha": _r(f["valor"]), "n_campanha": f["n"],
                        "servico": max(f["tipos"].items(), key=lambda kv: kv[1])[0] if f["tipos"] else "", **mandato(raiz)})
        for lista, via in ((c["doadores"], "direto"), (c["originarios"], "originario")):
            for d in lista.values():
                # Recursos próprios do próprio candidato entram abaixo (politico_socio). Na chapa de senador, os
                # recursos próprios dos suplentes também aparecem como "próprios": esses contam como doador.
                if not d.get("meio_cpf") or not (d["tipo"] == "pessoa" or d["tipo"] == "proprio" and d["meio_cpf"] != c.get("meio_cpf")):
                    continue
                chave = f"{norm_name(d['nome'])}|{d['meio_cpf']}"
                for cnpj, papel, qualif in donos.get(chave, []):
                    k = ("doador", c["ano"], chave, cnpj[:8])
                    if k in vistos:
                        continue
                    vistos.add(k)
                    out.append({"tipo": "doador_socio", "ano": c["ano"], "via": via,
                                "doador": {"nome": d["nome"], "doc": d["doc"]}, "doacao": _r(d["valor"]),
                                "empresa": {"cnpj": cnpj, "nome": (emps.get(cnpj) or {}).get("razao_social") or ""},
                                "papel": papel, "qualificacao": qualif, **mandato(cnpj[:8])})
    # o próprio parlamentar como sócio de uma empresa que ele pagou pela cota ou por emendas
    meio = (pess.get(pid) or {}).get("meio_cpf") or next((c["meio_cpf"] for c in cands if c.get("meio_cpf")), "")
    if meio:
        for nome in {c["nome"] for c in cands}:
            for cnpj, papel, qualif in donos.get(f"{norm_name(nome)}|{meio}", []):
                k = ("proprio", cnpj[:8])
                if k in vistos:
                    continue
                vistos.add(k)
                out.append({"tipo": "politico_socio", "empresa": {"cnpj": cnpj, "nome": (emps.get(cnpj) or {}).get("razao_social") or ""},
                            "papel": papel, "qualificacao": qualif, **mandato(cnpj[:8])})
    ordem = {"politico_socio": 0, "doador_socio": 1, "fornecedor": 2}
    out.sort(key=lambda x: (bool(x.get("comum")), ordem[x["tipo"]], -(x.get("cota", 0) + x.get("emendas", 0))))
    return out


def donos_por_politico(pid: str, cnpjs: Iterable[str], todas: dict[str, dict]) -> dict[str, list[tuple[str, str, str]]]:
    """Chave do sócio -> empresas (pagas por este parlamentar) em que ele aparece, direto ou por trás de holdings."""
    out: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for c in cnpjs:
        e = todas.get(c)
        if not e:
            continue
        for s in e.get("socios") or []:
            if cnpj_mod.tipo_socio(s) == "pessoa" and s.get("nome"):
                out[cnpj_mod.chave_socio(s)].append((c, "socio", s.get("qualificacao", "")))
        if any(cnpj_mod.tipo_socio(s) == "empresa" for s in e.get("socios") or []):
            for d in cnpj_mod.donos_finais(c, todas):
                if d["fim"] == "pessoa" and d["cadeia"]:
                    out[cnpj_mod.chave_socio(d)].append((c, "dono_final", d.get("qualificacao", "")))
    return out


# ------------------------------------------------------------------ montar os arquivos do site


def campanha_publica(c: dict, no_site: set[str], dados_ano: dict) -> dict:
    """Uma campanha para o site: totais, maiores doadores e fornecedores, sem CPF à mostra."""
    rc, dp = c["receitas"], c["despesas"]

    def doador(d: dict) -> dict:
        return {"nome": d["nome"], "doc": d["doc"], "tipo": d["tipo"], "valor": _r(d["valor"]), "n": d["n"],
                "origem": max(d["origens"].items(), key=lambda kv: kv[1])[0] if d.get("origens") else ""}

    def originario(d: dict) -> dict:
        return {"nome": d["nome"], "doc": d["doc"], "tipo": d["tipo"], "valor": _r(d["valor"]), "n": d["n"], "como": d.get("como", "")}

    def fornecedor(f: dict) -> dict:
        return {"nome": f["nome"], "doc": f["doc"], "valor": _r(f["valor"]), "n": f["n"],
                "tipo": max(f["tipos"].items(), key=lambda kv: kv[1])[0] if f["tipos"] else "",
                **({"pagina": True} if f["doc"] in no_site else {})}

    return {
        "ano": c["ano"], "cargo": c["cargo"], "uf": c["uf"], "partido": c["partido"], "numero": c["numero"],
        "nome": c["nome"], "achada_por": c.get("achada_por", ""),
        "prestacao": c["prestacao"].capitalize(), "data_prestacao": c["data_prestacao"], "gerado_em": c.get("gerado_em", ""),
        "fonte": dados_ano.get("fonte", ""), "arquivo": dados_ano.get("url", ""), "cnpj_campanha": c.get("cnpj_campanha", ""),
        "divulga": DIVULGA,
        "receitas": {"total": _r(rc["total"]), "financeiro": _r(rc["financeiro"]), "estimavel": _r(rc["estimavel"]), "n": rc["n"],
                     "por_origem": [[k, _r(v)] for k, v in sorted(rc["por_origem"].items(), key=lambda kv: -kv[1])],
                     "por_fonte": [[k, _r(v)] for k, v in sorted(rc["por_fonte"].items(), key=lambda kv: -kv[1])]},
        "n_doadores": len(c["doadores"]),
        "doadores": _top(c["doadores"], N_LISTA, doador),
        "n_originarios": len(c["originarios"]),
        "originarios": _top(c["originarios"], N_LISTA, originario),
        "despesas": {"total": _r(dp["total"]), "n": dp["n"],
                     "por_tipo": [[k, _r(v)] for k, v in sorted(dp["por_tipo"].items(), key=lambda kv: -kv[1])]},
        "n_fornecedores": len(c["fornecedores"]),
        "fornecedores": _top(c["fornecedores"], N_LISTA, fornecedor),
    }


def montar(saida: Path, politicos: list[dict], despesas: list[dict], emps: dict[str, dict], socias: dict[str, dict],
           emendas_empresas: dict[str, dict], contas: dict[int, dict], pess: dict[str, dict],
           hoje: dt.date | None = None) -> dict:
    """Grava p/campanha/{id}.json, campanha.json e acrescenta "campanha" nas páginas de empresa (e/{cnpj}.json)."""
    hoje = hoje or dt.date.today()
    todas = {**socias, **emps}
    no_site = {f.stem for f in (saida / "e").glob("*.json")}
    por_id = {p["id"]: p for p in politicos}
    cands = ligar_candidaturas(politicos, pess, contas)

    cota: dict[str, dict[str, dict]] = defaultdict(dict)  # politico -> raiz -> pago pela cota
    for d in despesas:
        if len(digits(d["doc"])) != 14:
            continue
        x = cota[d["politico"]].setdefault(d["doc"][:8], {"cnpj": d["doc"], "nome": d["fornecedor"], "valor": 0.0, "de": d["data"], "ate": d["data"]})
        x["valor"] += d["valor"]
        if d["data"]:
            x["de"] = min(x["de"] or d["data"], d["data"])
            x["ate"] = max(x["ate"] or d["data"], d["data"])
    emenda: dict[str, dict[str, dict]] = defaultdict(dict)  # politico -> raiz -> pago com as emendas dele
    for c, e in (emendas_empresas or {}).items():
        for a in e.get("autores") or []:
            if a.get("politico"):
                x = emenda[a["politico"]].setdefault(c[:8], {"cnpj": c, "nome": e.get("nome", ""), "valor": 0.0})
                x["valor"] += a.get("valor") or 0

    quem_paga: dict[str, set[str]] = defaultdict(set)  # raiz -> parlamentares que pagaram pela cota
    for d in despesas:
        if len(digits(d["doc"])) == 14:
            quem_paga[d["doc"][:8]].add(d["politico"])
    npol = {k: len(v) for k, v in quem_paga.items()}
    lista, por_empresa = [], defaultdict(list)
    n_com = 0
    for p in politicos:
        cs = cands.get(p["id"]) or []
        pagos = {x["cnpj"] for x in cota[p["id"]].values()} | {x["cnpj"] for x in emenda[p["id"]].values()}
        donos = donos_por_politico(p["id"], pagos, todas)
        lig = ligacoes(p["id"], cs, cota[p["id"]], emenda[p["id"]], donos, todas, pess, npol) if (cs or pess.get(p["id"])) else []
        if not cs and not lig:
            continue
        n_com += bool(cs)
        write_json(saida / "p" / "campanha" / f"{p['id']}.json", {
            "id": p["id"], "atualizado_em": hoje.isoformat(),
            "campanhas": [campanha_publica(c, no_site, contas.get(c["ano"]) or {}) for c in cs],
            "ligacoes": lig,
        })
        for x in lig:
            lista.append({"politico": p["id"], "nome": p["nome"], "partido": p["partido"], "uf": p["uf"], "casa": p["casa"], **x})
            por_empresa[x["empresa"]["cnpj"]].append({"politico": p["id"], "nome": p["nome"], "partido": p["partido"], "uf": p["uf"],
                                                      **{k: v for k, v in x.items() if k != "empresa"}})
        # fornecedoras da campanha que têm página no site, mesmo sem ligação com o mandato deste parlamentar
        for c in cs:
            for f in c["fornecedores"].values():
                if f["doc"] in no_site and not any(x["empresa"]["cnpj"] == f["doc"] for x in lig):
                    por_empresa[f["doc"]].append({"politico": p["id"], "nome": p["nome"], "partido": p["partido"], "uf": p["uf"],
                                                  "tipo": "fornecedor_campanha", "ano": c["ano"], "campanha": _r(f["valor"])})
    for c, xs in por_empresa.items():
        f = saida / "e" / f"{c}.json"
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        e["campanha"] = sorted(xs, key=lambda x: (-(x.get("ano") or 9999), x["nome"]))
        write_json(f, e)
    anos = {str(a): {k: d.get(k) for k in ("url", "fonte", "gerado_em", "baixado_em")} for a, d in sorted(contas.items()) if d}
    resumo = {"atualizado_em": hoje.isoformat(), "anos": anos,
              "contagens": {"politicos": len(politicos), "com_campanha": n_com, "ligacoes": len(lista),
                            **{t: sum(1 for x in lista if x["tipo"] == t) for t in ("fornecedor", "doador_socio", "politico_socio")},
                            "comuns": sum(1 for x in lista if x.get("comum"))},
              "ligacoes": lista}
    write_json(saida / "campanha.json", resumo)
    log.info("Campanha: %d de %d parlamentares com contas achadas; %d ligações com o mandato (%s)", n_com, len(politicos),
             len(lista), resumo["contagens"])
    return resumo


def coletar(saida: Path, cache: Path, dados: dict, anos: Iterable[int] = ANOS, hoje: dt.date | None = None) -> dict | None:
    """Etapa da coleta nacional (build.py), depois de montar(): usa as empresas, a cota e as emendas já coletadas."""
    pasta = cache / "campanha"
    contas = {a: contas_do_ano(a, pasta, hoje) for a in anos}
    contas = {a: d for a, d in contas.items() if d}
    if not contas:
        return None
    pess = pessoas(dados["politicos"], pasta)
    return montar(saida, dados["politicos"], dados["despesas"], dados["empresas"], dados.get("empresas_socias") or {},
                  dados.get("emendas_empresas") or {}, contas, pess, hoje)
