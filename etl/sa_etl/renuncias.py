"""Renúncia fiscal: quanto cada empresa deixou de pagar de impostos federais por causa de um benefício.

Fonte: Portal da Transparência (CGU), com dados da Receita Federal (declarações ECF e DIRBI e importações):
    https://portaldatransparencia.gov.br/download-de-dados/renuncias
O link do Portal leva a um arquivo por ano-calendário:
    https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/renuncias/{ano}_RenunciasFiscais.zip

Cada .zip traz quatro tabelas (CSV com ;, latin-1, vírgula decimal). Usamos duas:
- {ano}_RenúnciasFiscaisPorBeneficiário.csv: o total por CNPJ, com nome, atividade (CNAE), cidade e UF;
- {ano}_RenúnciasFiscais.csv: uma linha por CNPJ × benefício × fundamento legal, com o tributo.
As outras duas (empresas habilitadas e imunes ou isentas) não têm valor de renúncia.

A Receita publica os dados com atraso: o ano mais recente costuma estar incompleto.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import re
import shutil
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

from .emendas import SIGLAS, achar_colunas, bonito
from .util import SiteForaDoAr, _session, avisar, chave_portal, data_do_arquivo, digits, to_float

log = logging.getLogger("sa_etl.renuncias")

URLS = [
    "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/renuncias/{ano}_RenunciasFiscais.zip",
    "https://portaldatransparencia.gov.br/download-de-dados/renuncias/{ano}",
]
FONTE = "https://portaldatransparencia.gov.br/download-de-dados/renuncias"
CONSULTA = "https://portaldatransparencia.gov.br/renuncias/beneficiario"
N_ANOS = 4  # anos-calendário mostrados (os mais recentes que existirem)
N_TOP = 300

REGRAS_BEN = {
    "ano": [["ano", "calendario"], ["ano"]],
    "cnpj": [["cnpj"]],
    "nome": [["razao", "social"]],
    "fantasia": [["nome", "fantasia"]],
    "cnae_cod": [["codigo", "cnae"]],
    "cnae": [["cnae"]],
    "municipio": [["municipio"]],
    "uf": [["uf"]],
    "valor": [["valor", "renuncia"], ["valor"]],
}
REGRAS_DET = {
    "cnpj": [["cnpj"]],
    "tipo": [["tipo", "renuncia"]],
    "beneficio": [["beneficio", "fiscal"], ["beneficio"]],
    "fundamento": [["fundamento"]],
    "tributo": [["tributo"]],
    "valor": [["valor", "renuncia"], ["valor"]],
}

# Seções da CNAE 2.0 pela divisão (2 primeiros dígitos do código)
SECOES = [
    ((1, 3), "Agropecuária"), ((5, 9), "Mineração, petróleo e gás"), ((10, 33), "Indústria"), ((35, 35), "Eletricidade e gás"),
    ((36, 39), "Água, esgoto e lixo"), ((41, 43), "Construção"), ((45, 47), "Comércio"), ((49, 53), "Transporte e correio"),
    ((55, 56), "Hotéis e restaurantes"), ((58, 63), "Informação e comunicação"), ((64, 66), "Bancos, seguros e finanças"),
    ((68, 68), "Imóveis"), ((69, 75), "Serviços profissionais e técnicos"), ((77, 82), "Serviços administrativos"),
    ((84, 84), "Administração pública"), ((85, 85), "Educação"), ((86, 88), "Saúde e assistência social"),
    ((90, 93), "Cultura, esporte e lazer"), ((94, 96), "Outros serviços e associações"), ((97, 99), "Outros"),
]


def setor(cnae_cod: str) -> str:
    d = digits(cnae_cod)
    if len(d) < 2 or d[:2] == "00":
        return "Sem informação"
    div = int(d[:2])
    return next((nome for (a, b), nome in SECOES if a <= div <= b), "Sem informação")


def cnpj_de(v: str) -> str:
    """O CNPJ pode vir com máscara ou sem os zeros à esquerda. Códigos que não são CNPJ (a Receita usa -3 para
    'inválido') ficam vazios, mas o valor continua no total."""
    d = digits(v)
    if 11 < len(d) < 14:
        d = d.zfill(14)
    return d if len(d) == 14 else ""


NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_falhas: dict[int, str] = {}  # ano -> o que o Portal respondeu (vai para o aviso da coleta)


def _servidor(r) -> str:
    """Quem respondeu (o servidor ou o firewall na frente dele): ajuda a saber se é bloqueio."""
    s = r.headers.get("server") or r.headers.get("via") or ""
    return f", {s[:40]}" if s else ""


def _baixar_url(url: str, dest: Path) -> str | None:
    """None se baixou; senão, o motivo. Pede um .zip (a sessão padrão pede JSON) e tenta também com cara de
    navegador, como nas emendas: o servidor de arquivos da CGU recusa alguns pedidos que não parecem de navegador."""
    motivo = "sem resposta"
    for ua in (_session.headers["User-Agent"], NAVEGADOR):
        for tentativa in range(3):
            try:
                r = _session.get(url, timeout=600, stream=True, allow_redirects=True,
                                 headers={"Accept": "application/zip,application/octet-stream,*/*", "User-Agent": ua})
                if r.status_code != 200:
                    motivo = f"HTTP {r.status_code}{_servidor(r)}"
                    if r.status_code >= 500 or r.status_code == 429:
                        time.sleep(2 ** (tentativa + 1))
                        continue
                    break  # 403/404: ano que ainda não existe, ou pedido recusado; tenta o outro agente
                tmp = dest.with_suffix(".part")
                with tmp.open("wb") as f:
                    for bloco in r.iter_content(1 << 20):
                        f.write(bloco)
                if not zipfile.is_zipfile(tmp):
                    motivo = f"não devolveu um .zip ({r.headers.get('content-type')})"
                    tmp.unlink(missing_ok=True)
                    break
                tmp.replace(dest)
                log.info("Renúncias: baixado %s (%.1f MB)", r.url, dest.stat().st_size / 1e6)
                return None
            except SiteForaDoAr as e:
                return str(e)[:120]
            except Exception as e:  # noqa: BLE001
                motivo = str(e)[:120]
                time.sleep(2 ** (tentativa + 1))
    return motivo


def baixar(ano: int, cache: Path, max_horas: float = 24 * 7) -> Path | None:
    dest = cache / f"{ano}_RenunciasFiscais.zip"
    if dest.exists() and dest.stat().st_size > 0 and (time.time() - dest.stat().st_mtime) / 3600 < max_horas:
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    motivos = []
    for url in URLS:
        u = url.format(ano=ano)
        motivo = _baixar_url(u, dest)
        if motivo is None:
            _falhas.pop(ano, None)
            return dest
        log.warning("Renúncias %d: %s indisponível (%s)", ano, u, motivo)
        motivos.append(motivo)
    _falhas[ano] = "; ".join(dict.fromkeys(motivos))
    if dest.exists() and dest.stat().st_size > 0:  # o Portal falhou: fica a cópia antiga
        avisar(f"Renúncia fiscal {ano}: o Portal da Transparência não respondeu; usamos a última cópia baixada, "
               f"de {data_do_arquivo(dest)}")
        return dest
    return None


def _tabelas(z: zipfile.ZipFile) -> tuple[str | None, str | None]:
    """(por beneficiário, detalhe). Os nomes têm acento, que o .zip às vezes guarda em outra codificação."""
    csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
    ben = next((n for n in csvs if "porbenefici" in n.lower()), None)
    det = next((n for n in csvs if n not in (ben,) and not any(x in n.lower() for x in ("habilitad", "imune", "isent"))), None)
    return ben, det


def _linhas(z: zipfile.ZipFile, nome: str):
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", errors="replace", newline=""), delimiter=";")


def _normalizadas(linhas, regras: dict) -> "Iterator[dict]":
    """Linhas com as nossas chaves (as da regra), seja qual for o nome da coluna no arquivo."""
    col = None
    for r in linhas:
        if col is None:
            col = achar_colunas(list(r.keys()), regras)
        yield {k: (str(r.get(c) or "")).strip() if c else "" for k, c in col.items()}


def ler_ano(zip_path: Path, ano: int, n_top: int = N_TOP) -> tuple[dict, dict[str, dict]] | None:
    """Resumo do ano e, para cada CNPJ, o total e os benefícios (para as páginas das empresas)."""
    with zipfile.ZipFile(zip_path) as z:
        ben, det = _tabelas(z)
        if not ben:
            log.warning("Renúncias %d: tabela por beneficiário não encontrada (%s)", ano, z.namelist())
            return None
        cab = next(_linhas(z, ben), {})
        col = achar_colunas(list(cab.keys()), REGRAS_BEN)
        if not col["cnpj"] or not col["valor"]:
            log.error("Renúncias %d: colunas essenciais não encontradas (%s)", ano, list(cab.keys()))
            return None
        return resumir(ano, _normalizadas(_linhas(z, ben), REGRAS_BEN),
                       _normalizadas(_linhas(z, det), REGRAS_DET) if det else [], n_top)


def resumir(ano: int, ben, det, n_top: int = N_TOP) -> tuple[dict, dict[str, dict]]:
    """ben: uma linha por CNPJ (total); det: uma linha por CNPJ × benefício. As duas com as chaves das regras."""
    empresas: dict[str, dict] = {}
    total, sem_cnpj = 0.0, 0.0
    por_uf: dict[str, list] = defaultdict(lambda: [0.0, 0])
    por_setor: dict[str, list] = defaultdict(lambda: [0.0, 0])
    for g in ben:
        v = to_float(g["valor"])
        if not v:
            continue
        total += v
        doc = cnpj_de(g["cnpj"])
        uf = g["uf"].upper() if g["uf"].upper() in SIGLAS else ""
        st = setor(g["cnae_cod"])
        por_uf[uf or "Não informado"][0] += v
        por_uf[uf or "Não informado"][1] += 1
        por_setor[st][0] += v
        por_setor[st][1] += 1
        if not doc:
            sem_cnpj += v
            continue
        e = empresas.setdefault(doc, {"nome": bonito(g["nome"]) or g["fantasia"], "uf": uf, "municipio": bonito(g["municipio"]),
                                      "setor": st, "atividade": g["cnae"], "valor": 0.0, "beneficios": defaultdict(float)})
        e["valor"] += v
    por_ben: dict[tuple, list] = defaultdict(lambda: [0.0, set()])
    por_tributo: dict[str, float] = defaultdict(float)
    for g in det:
        v = to_float(g["valor"])
        if not v:
            continue
        nome_b = g["beneficio"] or g["fundamento"] or "Não informado"
        doc = cnpj_de(g["cnpj"])
        b = por_ben[(nome_b, g["tributo"])]
        b[0] += v
        b[1].add(doc)
        por_tributo[g["tributo"] or "Não informado"] += v
        if doc in empresas:
            empresas[doc]["beneficios"][nome_b] += v
    ordem = sorted(empresas.items(), key=lambda kv: -kv[1]["valor"])
    par = lambda d, n: [[k, round(x, 2)] for k, x in sorted(d.items(), key=lambda kv: -kv[1])[:n]]  # noqa: E731
    resumo = {
        "ano": ano, "total": round(total, 2), "n": len(empresas), "sem_cnpj": round(sem_cnpj, 2),
        "por_uf": [[k, round(x[0], 2), x[1]] for k, x in sorted(por_uf.items(), key=lambda kv: -kv[1][0])],
        "por_setor": [{"setor": k, "valor": round(x[0], 2), "n": x[1]} for k, x in sorted(por_setor.items(), key=lambda kv: -kv[1][0])],
        "por_beneficio": [{"nome": k[0], "tributo": k[1], "valor": round(x[0], 2), "n": len(x[1] - {""})}
                          for k, x in sorted(por_ben.items(), key=lambda kv: -kv[1][0])[:25]],
        "por_tributo": par(por_tributo, 12),
        "top": [{"cnpj": doc, "nome": e["nome"], "uf": e["uf"], "municipio": e["municipio"], "setor": e["setor"],
                 "atividade": e["atividade"], "valor": round(e["valor"], 2), "beneficios": par(e["beneficios"], 3)}
                for doc, e in ordem[:n_top]],
    }
    por_empresa = {doc: {"valor": round(e["valor"], 2), "beneficios": par(e["beneficios"], 8)} for doc, e in ordem}
    log.info("Renúncias %d: R$ %.0f, %d empresas", ano, total, len(empresas))
    return resumo, por_empresa


# ---------------------------------------------------------------- pela API de dados do Portal

API = "https://api.portaldatransparencia.gov.br/api-de-dados/renuncias-valor"
API_TESTE = "https://api.portaldatransparencia.gov.br/api-de-dados/orgaos-siafi"  # consulta simples, para testar a chave
API_CADASTRO = "https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email"
API_EM_PARALELO = 6  # pedidos ao mesmo tempo (a API leva uns 5 segundos por página)
API_POR_MINUTO = 300  # o limite do Portal é 400 por minuto (700 de madrugada); acima disso a chave fica suspensa por 8 horas
API_REFAZER_DIAS = 30  # a Receita atualiza a renúncia uma ou duas vezes por ano; relemos tudo uma vez por mês
REGRAS_API = {**REGRAS_DET, **{k: v for k, v in REGRAS_BEN.items() if k not in REGRAS_DET},
              "nome": [["razao", "social"], ["nome", "beneficiario"], ["nome", "empresa"]],
              "fantasia": [["nome", "fantasia"]],
              "cnae_cod": [["cnae", "codigo"], ["codigo", "cnae"], ["codigo", "atividade"]],
              "cnae": [["cnae", "descricao"], ["cnae", "denominacao"], ["cnae", "nome"], ["cnae"]],
              "municipio": [["municipio", "nome"], ["municipio"]],
              "uf": [["uf", "sigla"], ["sigla", "uf"], ["uf"]],
              "valor": [["valor", "renunciado"], ["valor", "renuncia"], ["valor"]]}


def _camel(k: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", k)


def _achatar(d: dict, pre: str = "") -> dict[str, str]:
    """{"municipio": {"nomeIBGE": "X", "uf": {"sigla": "SP"}}} -> {"municipio nome IBGE": "X", "municipio uf sigla": "SP"}"""
    out: dict[str, str] = {}
    for k, v in d.items():
        chave = f"{pre} {_camel(k)}".strip()
        if isinstance(v, dict):
            out.update(_achatar(v, chave))
        elif not isinstance(v, list):
            out[chave] = "" if v is None else str(v)
    return out


def _valor_api(v: str) -> str:
    """A API devolve número com ponto (1234.5) ou texto com vírgula (1.234,50); to_float espera o formato do CSV."""
    v = v.strip()
    return v.replace(".", ",") if re.fullmatch(r"-?\d+(\.\d+)?", v) else v


class ApiRenuncia:
    """Lê a consulta de valores renunciados página por página, guardando cada página no cache. A leitura completa pode
    levar algumas execuções; enquanto não termina, nada da API vai para o site."""

    def __init__(self, cache: Path, chave: str):
        # "api": a última leitura completa (é a que vai para o site); "api-lendo": a leitura em andamento
        self.pasta = cache / "api"
        self.lendo = cache / "api-lendo"
        self.lendo.mkdir(parents=True, exist_ok=True)
        self.estado_f = self.lendo / "estado.json"
        self.chave = chave
        self.motivo = ""

    def _completa_em(self) -> float | None:
        try:
            return json.loads((self.pasta / "estado.json").read_text())["fim_em"]
        except (OSError, ValueError, KeyError):
            return None

    def _estado(self) -> dict:
        self.lendo.mkdir(parents=True, exist_ok=True)
        try:
            e = json.loads(self.estado_f.read_text())
        except (OSError, ValueError):
            e = {}
        if not e:
            for f in self.lendo.glob("p*.json.gz"):
                f.unlink()
            e = {"filtros": [{}], "i": 0, "pagina": 1, "fim": False, "paginas": 0}
        return e

    def _pedir(self, filtro: dict, pagina: int) -> tuple[list | None, str]:
        """(linhas, motivo da falha). Roda em paralelo: não mexe em self, só devolve."""
        motivo = ""
        for tentativa in range(4):
            try:
                r = _session.get(API, params={**filtro, "pagina": pagina}, timeout=120,
                                 headers={"chave-api-dados": self.chave, "Accept": "application/json"})
            except SiteForaDoAr as e:
                return None, str(e)[:120]
            except Exception as e:  # noqa: BLE001
                motivo = str(e)[:120]
                time.sleep(2 ** (tentativa + 1))
                continue
            if r.status_code == 200:
                try:
                    d = r.json()
                except ValueError:
                    return None, f"resposta não é JSON ({r.headers.get('content-type')})"
                return (d, "") if isinstance(d, list) else (None, "resposta não é uma lista")
            corpo = re.sub(r"\s+", " ", (r.text or "")[:160]).strip()
            motivo = f"HTTP {r.status_code}{_servidor(r)}" + (f": {corpo}" if corpo else "")
            if r.status_code in (429,) or r.status_code >= 500:
                time.sleep(2 ** (tentativa + 2))
                continue
            return None, motivo
        return None, motivo

    def _testar_chave(self) -> str:
        """A recusa é da chave ou só desta consulta? Pergunta uma consulta simples da mesma API."""
        try:
            r = _session.get(API_TESTE, params={"pagina": 1}, timeout=60,
                             headers={"chave-api-dados": self.chave, "Accept": "application/json"})
            return f"a mesma chave em {API_TESTE.rsplit('/', 1)[-1]}: HTTP {r.status_code}; chave com {len(self.chave)} caracteres"
        except Exception as e:  # noqa: BLE001
            return f"teste da chave falhou: {str(e)[:80]}"

    def coletar(self, minutos: float) -> bool:
        """True quando há uma leitura completa para o site. Uma nova leitura começa a cada API_REFAZER_DIAS dias;
        enquanto ela não termina, o site continua com a anterior."""
        feita = self._completa_em()
        if feita and time.time() - feita < API_REFAZER_DIAS * 86400:
            return True
        e = self._estado()
        inicio = time.time()
        # Cada resposta da API demora alguns segundos; por isso pedimos API_EM_PARALELO páginas de uma vez,
        # sem passar de API_POR_MINUTO pedidos por minuto
        with ThreadPoolExecutor(API_EM_PARALELO) as pool:
            while not e["fim"] and time.time() - inicio < minutos * 60:
                t0, filtro = time.time(), e["filtros"][e["i"]]
                lote = list(pool.map(self._pedir, [filtro] * API_EM_PARALELO, range(e["pagina"], e["pagina"] + API_EM_PARALELO)))
                if not self._guardar_lote(e, filtro, lote):
                    break
                self.estado_f.write_text(json.dumps(e))
                time.sleep(max(0.0, API_EM_PARALELO * 60 / API_POR_MINUTO - (time.time() - t0)))
        self.estado_f.write_text(json.dumps(e))
        if e["fim"]:
            shutil.rmtree(self.pasta, ignore_errors=True)
            self.lendo.rename(self.pasta)
        log.info("Renúncias (API): %d páginas lidas%s", e["paginas"], ", completa" if e["fim"] else
                 f", leitura continua na próxima execução (filtro {e['i'] + 1} de {len(e['filtros'])}, página {e['pagina']})")
        return e["fim"] or bool(feita)

    def _guardar_lote(self, e: dict, filtro: dict, lote: list[tuple[list | None, str]]) -> bool:
        """Guarda as páginas do lote em ordem, até a primeira vazia (fim do filtro). False: parar a leitura."""
        for linhas, motivo in lote:
            if linhas is None:
                self.motivo = motivo
                if motivo.startswith(("HTTP 401", "HTTP 403")):
                    self.motivo += f" ({self._testar_chave()})"
                if e["paginas"] == 0 and not filtro and motivo.startswith("HTTP 400"):
                    # a consulta sem filtro não é aceita: lê estado por estado
                    log.info("Renúncias (API): consulta sem filtro recusada (%s); lendo por UF", motivo)
                    e.update(filtros=[{"nomeSiglaUF": uf} for uf in sorted(SIGLAS)], i=0, pagina=1)
                    return True
                log.warning("Renúncias (API): parou em %s, página %d (%s)", filtro or "sem filtro", e["pagina"], self.motivo)
                return False
            if not linhas:  # página vazia: acabou este filtro
                e["i"] += 1
                e["pagina"] = 1
                if e["i"] >= len(e["filtros"]):
                    e.update(fim=True, fim_em=time.time())
                return True
            f = self.lendo / f"p{e['paginas']:06d}.json.gz"
            f.write_bytes(gzip.compress(json.dumps([_achatar(x) for x in linhas if isinstance(x, dict)],
                                                   ensure_ascii=False).encode()))
            e["paginas"] += 1
            e["pagina"] += 1
        return True

    def anos(self, n_anos: int) -> dict[int, tuple[dict, dict]]:
        """Os resumos por ano, do mesmo jeito que os do arquivo .zip."""
        det_por_ano: dict[int, list[dict]] = defaultdict(list)
        col = None
        for f in sorted(self.pasta.glob("p*.json.gz")):
            for r in json.loads(gzip.decompress(f.read_bytes())):
                if col is None:
                    col = achar_colunas(list(r.keys()), REGRAS_API)
                    log.info("Renúncias (API): colunas %s", {k: v for k, v in col.items() if v})
                    if not col["valor"] or not col["cnpj"] or not col["ano"]:
                        log.error("Renúncias (API): campos essenciais não encontrados (%s)", list(r.keys()))
                        self.motivo = "a API mudou o formato"
                        return {}
                g = {k: (r.get(c) or "").strip() if c else "" for k, c in col.items()}
                g["valor"] = _valor_api(g["valor"])
                a = digits(g["ano"])[:4]
                if a:
                    det_por_ano[int(a)].append(g)
        out = {}
        for ano in sorted(det_por_ano, reverse=True)[:n_anos]:
            det = det_por_ano[ano]
            ben: dict[str, dict] = {}
            for g in det:  # o total por CNPJ é a soma dos benefícios
                doc = cnpj_de(g["cnpj"]) or f"sem-{len(ben)}"
                b = ben.setdefault(doc, {**g, "valor": 0.0})
                b["valor"] += to_float(g["valor"])
            linhas_ben = [{**b, "valor": f"{b['valor']:.2f}".replace(".", ",")} for b in ben.values()]
            out[ano] = resumir(ano, linhas_ben, det)
            out[ano][0]["url"] = CONSULTA
        return out


def coletar(cache: Path, ano_atual: int, n_anos: int = N_ANOS, chave: str | None = None, minutos_api: float = 20) -> dict:
    """Os anos-calendário mais recentes que o Portal tiver. {"anos": {ano: resumo}, "empresas": {cnpj: {ano: {...}}}}

    A API de dados do Portal vem primeiro (pede uma chave, cadastro grátis por e-mail). Enquanto a primeira leitura
    pela API não termina, ou se ela falhar, usamos os arquivos de download."""
    cache.mkdir(parents=True, exist_ok=True)
    anos: dict[int, dict] = {}
    _falhas.clear()
    por_emp: dict[str, dict] = defaultdict(dict)
    chave = chave if chave is not None else chave_portal()
    api_motivo = ""
    if chave:
        api = ApiRenuncia(cache, chave)
        if api.coletar(minutos_api):
            for ano, (r, emps) in api.anos(n_anos).items():
                anos[ano] = r
                for doc, x in emps.items():
                    por_emp[doc][ano] = x
        if not anos:
            api_motivo = f"API: {api.motivo}" if api.motivo else "API: leitura em andamento, continua na próxima execução"
            log.info("Renúncias: %s; tentando os arquivos de download", api_motivo)
    if not anos:
        for ano in range(ano_atual, ano_atual - n_anos - 3, -1):
            if len(anos) >= n_anos:
                break
            z = baixar(ano, cache)
            if not z:
                continue
            try:
                r = ler_ano(z, ano)
            except (zipfile.BadZipFile, OSError, ValueError) as e:
                log.warning("Renúncias %d: arquivo com problema (%s)", ano, e)
                r = None
            if not r:
                continue
            anos[ano], emps = r
            for doc, x in emps.items():
                por_emp[doc][ano] = x
    if not anos:
        motivos = "; ".join([f"{a}: {m}" for a, m in sorted(_falhas.items(), reverse=True)[:3]] + ([api_motivo] if api_motivo else []))
        dica = "" if chave else f"; para usar a API, cadastre uma chave em {API_CADASTRO} e guarde no secret PORTAL_TRANSPARENCIA_CHAVE"
        avisar("Renúncia fiscal: o Portal da Transparência não respondeu; a parte de renúncias da página de incentivos "
               f"não foi atualizada ({motivos or 'sem resposta'}){dica}")
    # Ano incompleto: a Receita ainda não processou todas as declarações (fica bem abaixo do ano anterior)
    for ano, r in anos.items():
        ant = anos.get(ano - 1)
        r["parcial"] = bool(ant and r["total"] < 0.6 * ant["total"])
    return {"anos": anos, "empresas": dict(por_emp)}
