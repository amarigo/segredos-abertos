"""Quanto cada empresa e entidade recebeu do governo federal, mês a mês, pela API oficial do Portal da Transparência.

Fonte: API de dados do Portal da Transparência (CGU), consulta "Recebimento de recursos por favorecido":
    https://api.portaldatransparencia.gov.br/api-de-dados/despesas/recursos-recebidos?mesAnoInicio=01/2026&mesAnoFim=01/2026&pagina=1
É a mesma consulta da página https://portaldatransparencia.gov.br/despesas/recursos-recebidos: cada linha é o que
um favorecido (CNPJ, CPF ou código) recebeu de uma unidade gestora num mês, com o órgão que pagou.

Por que a API, e não mais os arquivos diários: desde 29/10/2026 o Portal recusa o download dos arquivos para quem
não é navegador (HTTP 405 do CloudFront em portaldatransparencia.gov.br/download-de-dados e HTTP 403 do S3 em
dadosabertos-download.cgu.gov.br), e a leitura parou. A API responde com a chave (secret PORTAL_TRANSPARENCIA_CHAVE).
A consulta de documentos (despesas/documentos) não serve: pede uma unidade gestora por consulta (são milhares por dia).

A API devolve 15 linhas por página e aceita 400 pedidos por minuto (700 de madrugada, 0h às 6h de Brasília); acima
disso a chave fica suspensa por 8 horas. A leitura completa tem centenas de milhares de páginas, por isso roda num
workflow próprio, uma vez por semana (pagamentos-empresas.yml), e continua de onde parou na execução seguinte.
Os meses mais recentes primeiro. Um mês fechado é lido uma vez; os dois últimos meses são lidos de novo toda semana.

Só guardamos quem tem CNPJ (empresas, entidades e órgãos públicos). CPF vem mascarado e não vai para o site: somamos
o valor pago a pessoas físicas só como total do mês.

Uso (no workflow semanal):
    python -m sa_etl.recursos_recebidos --cache .cache --anos 2023 2024 2025 2026 --minutos 300
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import gzip
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .util import SiteForaDoAr, _session, chave_portal, digits, to_float

log = logging.getLogger("sa_etl.recursos_recebidos")

API = "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/recursos-recebidos"
API_ORGAOS = "https://api.portaldatransparencia.gov.br/api-de-dados/orgaos-siafi"
CONSULTA = "https://portaldatransparencia.gov.br/despesas/recursos-recebidos"
PASTA = "recursos"
VERSAO = 1
EM_PARALELO = 8
POR_MINUTO_DIA = 330  # abaixo do limite de 400 por minuto
POR_MINUTO_MADRUGADA = 600  # abaixo do limite de 700 por minuto (0h às 6h de Brasília)
GRAVAR_A_CADA = 200  # páginas entre um salvamento e outro da leitura em andamento
REFAZER_DIAS = 6  # meses recentes: relidos se a última leitura tem mais de 6 dias
MESES_RECENTES = 2  # o mês atual e o anterior ainda recebem pagamentos e correções


def por_minuto(agora: dt.datetime | None = None) -> int:
    """Pedidos por minuto permitidos agora (Brasília é UTC-3, sem horário de verão desde 2019)."""
    agora = agora or dt.datetime.now(dt.timezone.utc)
    hora_brasilia = (agora - dt.timedelta(hours=3)).hour
    return POR_MINUTO_MADRUGADA if hora_brasilia < 6 else POR_MINUTO_DIA


def _mes(am: str) -> tuple[int, int]:
    return int(am[:4]), int(am[4:6])


def meses_a_ler(anos: list[int], hoje: dt.date) -> list[str]:
    """AAAAMM de janeiro do primeiro ano até o mês atual, do mais novo para o mais velho."""
    out = []
    for ano in sorted(anos):
        for m in range(1, 13):
            if dt.date(ano, m, 1) <= hoje:
                out.append(f"{ano}{m:02d}")
    return sorted(out, reverse=True)


def recente(am: str, hoje: dt.date) -> bool:
    a, m = _mes(am)
    return (hoje.year * 12 + hoje.month) - (a * 12 + m) < MESES_RECENTES


def eh_cnpj(codigo: str) -> str:
    d = digits(codigo)
    return d if len(d) == 14 and "*" not in (codigo or "") else ""


class Leitor:
    """Lê a consulta mês a mês, página por página, guardando no cache. Continua de onde parou na execução seguinte."""

    def __init__(self, cache: Path, chave: str, hoje: dt.date | None = None):
        self.pasta = cache / PASTA
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.chave = chave
        self.hoje = hoje or dt.date.today()
        self.motivo = ""
        self.paginas = 0
        self._orgaos: list[str] | None = None

    # ------------------------------------------------------------ arquivos

    def final(self, am: str) -> Path:
        return self.pasta / f"{am}-v{VERSAO}.json.gz"

    def _lendo(self, am: str) -> Path:
        return self.pasta / f"{am}-lendo-v{VERSAO}.json.gz"

    @staticmethod
    def _abrir(f: Path) -> dict | None:
        try:
            return json.loads(gzip.decompress(f.read_bytes()))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _gravar(f: Path, d: dict) -> None:
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode()))
        tmp.replace(f)

    def precisa_ler(self, am: str) -> bool:
        d = self._abrir(self.final(am)) if self.final(am).exists() else None
        if not d:
            return True
        if not recente(am, self.hoje):
            # mês fechado: basta uma leitura feita depois que ele acabou
            a, m = _mes(am)
            fim_mes = dt.date(a, m, calendar.monthrange(a, m)[1])
            return dt.date.fromisoformat(d["lido_em"]) <= fim_mes
        return (self.hoje - dt.date.fromisoformat(d["lido_em"])).days > REFAZER_DIAS

    # ------------------------------------------------------------ API

    def _pedir(self, params: dict) -> tuple[list | None, str]:
        """(linhas, motivo da falha). Roda em paralelo: não mexe em self."""
        motivo = ""
        for tentativa in range(4):
            try:
                r = _session.get(API, params=params, timeout=120, headers={"chave-api-dados": self.chave, "Accept": "application/json"})
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
            motivo = f"HTTP {r.status_code}" + (f": {corpo}" if corpo else "")
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** (tentativa + 2))
                continue
            return None, motivo
        return None, motivo

    def orgaos_superiores(self) -> list[str]:
        """Códigos SIAFI dos órgãos superiores (terminam em 000, como 26000, Ministério da Educação), para dividir um
        mês grande demais em consultas menores."""
        if self._orgaos is None:
            cods: set[str] = set()
            for p in range(1, 200):
                try:
                    r = _session.get(API_ORGAOS, params={"pagina": p}, timeout=120,
                                     headers={"chave-api-dados": self.chave, "Accept": "application/json"})
                    linhas = r.json() if r.status_code == 200 else None
                except Exception:  # noqa: BLE001
                    linhas = None
                if not linhas:
                    break
                for o in linhas:
                    c = digits(str(o.get("codigo") or ""))
                    if len(c) == 5 and c.endswith("000"):
                        cods.add(c)
            self._orgaos = sorted(cods)
        return self._orgaos

    # ------------------------------------------------------------ leitura de um mês

    def _estado(self, am: str) -> dict:
        e = self._abrir(self._lendo(am)) if self._lendo(am).exists() else None
        if e:
            return e
        e = {"filtros": [{}], "i": 0, "pagina": 1, "agg": {}, "linhas": 0, "repetidas": 0, "pessoas": 0.0,
             "outros": 0.0, "inicio": self.hoje.isoformat()}
        antes = self._abrir(self.final(am)) if self.final(am).exists() else None
        if antes and antes.get("por_orgao") and self.orgaos_superiores():
            # da última vez o mês só foi lido órgão por órgão: começa assim
            e.update(filtros=[{}] + [{"orgaoSuperior": c} for c in self.orgaos_superiores()], i=1)
        return e

    @staticmethod
    def _somar(e: dict, linhas: list[dict]) -> None:
        """Junta as linhas no total do mês. A chave (CNPJ, unidade gestora) é única no mês: se a mesma linha voltar
        (páginas que se repetem, ou o mesmo mês lido por órgão depois de começar sem filtro), não soma duas vezes."""
        agg = e["agg"]
        for x in linhas:
            if not isinstance(x, dict):
                continue
            e["linhas"] += 1
            v = round(to_float(x.get("valor")), 2)  # número (1234.5) ou texto (1.234,50)
            doc = eh_cnpj(str(x.get("codigoPessoa") or ""))
            if not doc:
                cod = str(x.get("codigoPessoa") or "")
                if "*" in cod or len(digits(cod)) == 11:
                    e["pessoas"] = round(e["pessoas"] + v, 2)  # CPF: só o total, sem nome
                else:
                    e["outros"] = round(e["outros"] + v, 2)  # código SIAFI, exterior, sem identificação
                continue
            k = f"{doc}|{x.get('codigoUG') or ''}"
            if k in agg:
                e["repetidas"] += 1
            agg[k] = [v, str(x.get("nomeOrgaoSuperior") or x.get("nomeOrgao") or "Não informado").strip(),
                      str(x.get("nomePessoa") or "").strip(), str(x.get("siglaUFPessoa") or "").strip()]

    def _condensar(self, am: str, e: dict) -> dict:
        """Do detalhe por unidade gestora para o total de cada CNPJ no mês, com os órgãos que pagaram."""
        orgaos: dict[str, int] = {}
        favs: dict[str, list] = {}
        for k, (v, org, nome, uf) in e["agg"].items():
            doc = k.split("|", 1)[0]
            i = orgaos.setdefault(org, len(orgaos))
            f = favs.setdefault(doc, [nome, 0.0, 0, {}, uf])
            f[1] = round(f[1] + v, 2)
            f[2] += 1
            f[3][str(i)] = round(f[3].get(str(i), 0.0) + v, 2)
            if nome and not f[0]:
                f[0] = nome
        return {"am": am, "f": favs, "o": sorted(orgaos, key=orgaos.get), "linhas": e["linhas"], "repetidas": e["repetidas"],
                "pessoas": e["pessoas"], "outros": e["outros"], "lido_em": self.hoje.isoformat(),
                "por_orgao": len(e["filtros"]) > 1}

    def ler_mes(self, am: str, ate: float, pool: ThreadPoolExecutor) -> bool | None:
        """True: mês completo. None: acabou o tempo (continua depois). False: a API recusou."""
        a, m = _mes(am)
        e = self._estado(am)
        desde_gravou = 0
        while time.time() < ate:
            if e["i"] >= len(e["filtros"]):
                self._gravar(self.final(am), self._condensar(am, e))
                self._lendo(am).unlink(missing_ok=True)
                log.info("Recursos recebidos %s: completo (%d linhas, %d CNPJs, %d repetidas)", am, e["linhas"],
                         len({k.split('|')[0] for k in e['agg']}), e["repetidas"])
                return True
            t0 = time.time()
            base = {"mesAnoInicio": f"{m:02d}/{a}", "mesAnoFim": f"{m:02d}/{a}", **e["filtros"][e["i"]]}
            lote = list(pool.map(self._pedir, [{**base, "pagina": p} for p in range(e["pagina"], e["pagina"] + EM_PARALELO)]))
            for linhas, motivo in lote:
                if linhas is None:
                    self.motivo = motivo
                    if motivo.startswith("HTTP 400") and len(e["filtros"]) == 1 and e["pagina"] > 50:
                        # A consulta sem filtro não consegue pular tantas linhas (a de renúncias para na página 14289):
                        # o resto do mês é lido órgão por órgão. O que já foi lido fica (a chave evita somar duas vezes).
                        cods = self.orgaos_superiores()
                        if cods:
                            log.info("Recursos recebidos %s: a consulta parou na página %d (%s); lendo por órgão (%d órgãos)",
                                     am, e["pagina"], motivo, len(cods))
                            e.update(filtros=[{}] + [{"orgaoSuperior": c} for c in cods], i=1, pagina=1)
                            break
                    log.warning("Recursos recebidos %s: parou na página %d (%s)", am, e["pagina"], motivo)
                    self._gravar(self._lendo(am), e)
                    return False
                if not linhas:  # página vazia: acabou este filtro
                    e["i"] += 1
                    e["pagina"] = 1
                    break
                self._somar(e, linhas)
                e["pagina"] += 1
                self.paginas += 1
                desde_gravou += 1
            if desde_gravou >= GRAVAR_A_CADA:
                self._gravar(self._lendo(am), e)
                desde_gravou = 0
            time.sleep(max(0.0, EM_PARALELO * 60 / por_minuto() - (time.time() - t0)))
        self._gravar(self._lendo(am), e)
        return None

    def coletar(self, anos: list[int], minutos: float) -> dict:
        """Lê os meses que faltam, do mais novo para o mais velho, até o limite de tempo."""
        ate = time.time() + minutos * 60
        feitos, falhou = [], []
        with ThreadPoolExecutor(EM_PARALELO) as pool:
            for am in meses_a_ler(anos, self.hoje):
                if time.time() >= ate:
                    break
                if not self.precisa_ler(am):
                    continue
                r = self.ler_mes(am, ate, pool)
                if r:
                    feitos.append(am)
                elif r is False:
                    falhou.append(am)
                    if self.motivo.startswith(("HTTP 401", "HTTP 403")):
                        break  # chave recusada: não adianta tentar os outros meses
        faltam = [am for am in meses_a_ler(anos, self.hoje) if self.precisa_ler(am)]
        log.info("Recursos recebidos: %d páginas lidas; meses completos agora: %s; faltam %d meses%s", self.paginas,
                 ", ".join(feitos) or "nenhum", len(faltam), f" ({self.motivo})" if falhou else "")
        return {"feitos": feitos, "falhou": falhou, "faltam": faltam, "motivo": self.motivo}


# ---------------------------------------------------------------- resumo para o site

def resumir(cache: Path, anos: list[int], hoje: dt.date | None = None) -> dict:
    """Os meses já lidos, somados por ano, no mesmo formato de pagamentos.resumir_geral:
    {"anos": {ano: {cnpj: {"nome", "valor", "n", "cats", "orgaos"}}}, "publicos": {...}, "cobertura": {ano: {...}}}.
    Órgãos públicos, estados, municípios e estatais (pelo nome) vão para "publicos"."""
    from .pagamentos import eh_publico_geral  # aqui, para não criar import circular

    hoje = hoje or dt.date.today()
    pasta = cache / PASTA
    out: dict[int, dict[str, dict]] = {a: {} for a in anos}
    pub: dict[int, dict[str, dict]] = {a: {} for a in anos}
    meses: dict[int, list[dict]] = {a: [] for a in anos}
    for f in sorted(pasta.glob(f"[0-9][0-9][0-9][0-9][0-9][0-9]-v{VERSAO}.json.gz")):
        am = f.name[:6]
        ano = int(am[:4])
        if ano not in out:
            continue
        d = Leitor._abrir(f)
        if not d:
            log.warning("Recursos recebidos: arquivo com defeito %s", f.name)
            continue
        a, m = _mes(am)
        fim_mes = dt.date(a, m, calendar.monthrange(a, m)[1])
        lido = dt.date.fromisoformat(d["lido_em"])
        meses[ano].append({"am": am, "ate": min(fim_mes, lido - dt.timedelta(days=1)), "pessoas": d.get("pessoas", 0.0),
                           "outros": d.get("outros", 0.0), "linhas": d.get("linhas", 0)})
        orgs = d.get("o") or []
        for doc, (nome, valor, n, por_org, _uf) in (d.get("f") or {}).items():
            destino = pub[ano] if eh_publico_geral(nome) else out[ano]
            e = destino.get(doc)
            if e is None:
                e = destino[doc] = {"nome": nome, "valor": 0.0, "n": 0, "cats": {}, "orgaos": {}}
            e["valor"] += valor
            e["n"] += n
            e["cats"]["pago"] = e["cats"].get("pago", 0.0) + valor
            for i, v in por_org.items():
                o = orgs[int(i)] if int(i) < len(orgs) else "Não informado"
                e["orgaos"][o] = e["orgaos"].get(o, 0.0) + v

    def cob(ano: int) -> dict:
        ms = sorted(meses[ano], key=lambda x: x["am"])
        fim = min(dt.date(ano, 12, 31), hoje - dt.timedelta(days=1))
        total = max(0, (fim - dt.date(ano, 1, 1)).days + 1)
        dias = sum(max(0, (x["ate"] - dt.date(ano, int(x["am"][4:]), 1)).days + 1) for x in ms)
        # completo: todos os meses do ano até o mês passado lidos, sem buraco
        esperados = {f"{ano}{m:02d}" for m in range(1, 13) if dt.date(ano, m, 1) <= fim}
        tem = {x["am"] for x in ms}
        return {"dias": dias, "dias_ano": total, "de": f"{ms[0]['am'][:4]}-{ms[0]['am'][4:]}-01" if ms else "",
                "ate": ms[-1]["ate"].isoformat() if ms else "", "completo": bool(esperados) and esperados <= tem and dias >= total - 10,
                "origem": "api", "meses": len(ms), "faltam": sorted(esperados - tem),
                "pessoas_fisicas": round(sum(x["pessoas"] for x in ms), 2), "sem_cnpj": round(sum(x["outros"] for x in ms), 2)}
    cobertura = {a: cob(a) for a in anos}
    for a in anos:
        log.info("Recursos recebidos %s: %d meses, %d empresas e entidades, %d públicos", a, cobertura[a]["meses"], len(out[a]), len(pub[a]))
    return {"anos": out, "publicos": pub, "cobertura": cobertura, "cobertura_publicos": cobertura}


def juntar(arquivos: dict | None, api: dict | None, anos: list[int]) -> dict | None:
    """Ano a ano, fica a fonte que cobre mais dias: os arquivos diários (que separam compras, repasses e subsídios)
    ou a API (que tem o total de cada favorecido, sem essa divisão). Nunca soma as duas no mesmo ano."""
    if not api:
        return arquivos
    if not arquivos:
        return api
    out = {"anos": {}, "publicos": {}, "cobertura": {}, "cobertura_publicos": {}}
    for a in anos:
        ca = (arquivos.get("cobertura") or {}).get(a) or {}
        cp = (api.get("cobertura") or {}).get(a) or {}
        src = api if cp.get("dias", 0) >= ca.get("dias", 0) and cp.get("dias", 0) > 0 else arquivos
        for k in out:
            out[k][a] = (src.get(k) or {}).get(a) or {}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path(".cache"))
    ap.add_argument("--anos", type=int, nargs="+", default=list(range(2023, dt.date.today().year + 1)))
    ap.add_argument("--minutos", type=float, default=300, help="tempo máximo de leitura nesta execução")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    chave = chave_portal()
    if not chave:
        raise SystemExit("Falta a chave da API do Portal (secret PORTAL_TRANSPARENCIA_CHAVE)")
    r = Leitor(a.cache, chave).coletar(a.anos, a.minutos)
    res = resumir(a.cache, a.anos)
    for ano, c in sorted(res["cobertura"].items()):
        tot = sum(e["valor"] for e in res["anos"][ano].values())
        print(f"- {ano}: {c['meses']} meses lidos (até {c['ate'] or '-'}), {len(res['anos'][ano])} empresas e entidades, "
              f"R$ {tot:,.2f}{'' if c['completo'] else ' (incompleto)'}")
    if r["falhou"] and r["motivo"]:
        print(f"::warning title=Pagamentos a empresas (API)::{r['motivo']}")
    if r["falhou"] and not r["feitos"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
