"""Funções de apoio: download com novas tentativas, leitura de CSV, gravação de JSON."""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import urlsplit

import requests

log = logging.getLogger("sa_etl")

USER_AGENT = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"

# Site fora do ar: quanto esperar para ele aceitar a conexão, e depois de quantas esperas seguidas sem resposta
# desistimos dele até o fim da coleta. Sem isso, um site parado custa minutos em cada endereço e a coleta
# inteira estoura o tempo do GitHub Actions sem publicar nada.
ESPERA_CONEXAO = 30
QUEDAS_PARA_DESISTIR = 3
_quedas: dict[str, int] = {}
FORA_DO_AR: set[str] = set()


class SiteForaDoAr(requests.ConnectionError):
    """O site já deixou de responder nesta coleta; nem tentamos de novo."""


def reiniciar_quedas() -> None:
    _quedas.clear()
    FORA_DO_AR.clear()


class _Sessao(requests.Session):
    def request(self, method, url, *args, **kw):
        site = urlsplit(url).hostname or ""
        if site in FORA_DO_AR:
            raise SiteForaDoAr(f"{site} não respondeu nesta coleta; pulamos {url}")
        t = kw.get("timeout")
        if isinstance(t, (int, float)):
            kw["timeout"] = (min(ESPERA_CONEXAO, t), t)  # (para conectar, para receber os dados)
        try:
            r = super().request(method, url, *args, **kw)
        except requests.ConnectTimeout:
            _quedas[site] = _quedas.get(site, 0) + 1
            if _quedas[site] >= QUEDAS_PARA_DESISTIR and site not in FORA_DO_AR:
                FORA_DO_AR.add(site)
                log.warning("%s não aceita conexão (%s vezes seguidas); pulamos esse site até o fim da coleta",
                            site, _quedas[site])
            raise
        _quedas.pop(site, None)
        return r


_session = _Sessao()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


def get(url: str, *, params: dict | None = None, tries: int = 4, timeout: int = 120,
        headers: dict | None = None) -> requests.Response:
    """GET com espera crescente entre tentativas (2s, 4s, 8s...)."""
    last: Exception | None = None
    for attempt in range(tries):
        try:
            r = _session.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"{r.status_code} em {url}")
            r.raise_for_status()  # outros erros 4xx não melhoram com nova tentativa
            return r
        except requests.HTTPError as e:
            if e.response is not None and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                raise
            last = e
        except SiteForaDoAr as e:
            last = e
            break
        except requests.RequestException as e:
            last = e
            if urlsplit(url).hostname in FORA_DO_AR:
                break
        wait = 2 ** (attempt + 1)
        log.warning("Falha em %s (%s); nova tentativa em %ss", url, last, wait)
        time.sleep(wait)
    raise RuntimeError(f"Não foi possível baixar {url}: {last}")


def get_json(url: str, *, tries: int = 4, **kw) -> Any:
    """GET de um JSON. Resposta cortada ou página de erro no lugar do JSON também ganha nova tentativa."""
    last: Exception | None = None
    for attempt in range(tries):
        r = get(url, tries=tries, **kw)
        try:
            return r.json()
        except ValueError as e:  # JSON cortado no meio, HTML de erro, corpo vazio
            last = e
            log.warning("JSON inválido em %s (%s); nova tentativa", url, str(e)[:80])
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"JSON inválido em {url}: {last}")


def download(url: str, dest: Path, max_horas: float | None = None, validar=None,
             headers: dict | None = None) -> Path:
    """Baixa um arquivo para o cache local, se ainda não existir (ou se for mais velho que max_horas).

    Se o site do governo falhar e já houver uma cópia antiga no cache, usa a cópia antiga (e avisa), em vez de
    deixar o ano inteiro de fora do site. `validar(bytes) -> bool` descarta respostas que não são o arquivo
    esperado (por exemplo uma página de erro em HTML no lugar do .zip).
    """
    tem_copia = dest.exists() and dest.stat().st_size > 0
    if tem_copia:
        idade = (time.time() - dest.stat().st_mtime) / 3600
        if max_horas is None or idade < max_horas:
            return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = get(url, timeout=600, headers=headers)
        if not r.content or (validar and not validar(r.content)):
            raise ValueError(f"resposta inválida de {url} ({len(r.content)} bytes)")
    except Exception as e:  # noqa: BLE001
        if tem_copia:
            log.warning("Usando cópia antiga de %s (%s)", dest.name, e)
            avisar(f"{dest.name}: o site oficial não respondeu; usamos a última cópia baixada, de {data_do_arquivo(dest)}")
            return dest
        raise
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(dest)
    return dest


def eh_zip(raw: bytes) -> bool:
    return zipfile.is_zipfile(io.BytesIO(raw))


def eh_csv(raw: bytes) -> bool:
    """Um CSV de verdade, não uma página de erro em HTML."""
    inicio = raw[:512].lstrip(b"\xef\xbb\xbf").lstrip().lower()
    return bool(inicio) and not inicio.startswith((b"<!doctype", b"<html", b"{"))


# ---------------------------------------------------------------- avisos da coleta

AVISOS: list[str] = []

_BRASILIA = timezone(timedelta(hours=-3))


def data_do_arquivo(f: Path) -> str:
    """Dia em que a cópia do cache foi baixada (horário de Brasília), para o aviso dizer de quando é o dado."""
    return datetime.fromtimestamp(f.stat().st_mtime, _BRASILIA).strftime("%d/%m/%Y")


def avisar(msg: str) -> None:
    """Registra um problema da coleta que o site deve mostrar (dados faltando, cópia antiga em uso...)."""
    if msg not in AVISOS:
        AVISOS.append(msg)


# ---------------------------------------------------------------- segurança dos dados publicados

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def id_seguro(x: Any) -> str | None:
    """Ids viram nomes de arquivo (p/{id}.json, v/{id}.json): só letras, números, _ e -, para nunca sair da pasta."""
    s = str(x if x is not None else "").strip()
    return s if _ID.match(s) else None


def url_segura(u: Any) -> str:
    """Só links http(s). Um link "javascript:" ou "data:" vindo de uma fonte adulterada vira texto vazio."""
    s = str(u or "").strip()
    return s if re.match(r"^https?://[^\s<>\"']+$", s, re.I) else ""


def read_csv_text(text: str, delimiter: str = ";") -> Iterator[dict[str, str]]:
    text = text.lstrip("﻿")
    yield from csv.DictReader(io.StringIO(text), delimiter=delimiter)


def read_csv_file(path: Path, delimiter: str = ";") -> Iterator[dict[str, str]]:
    raw = path.read_bytes()
    if path.suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            raw = z.read(name)
    yield from read_csv_text(_decode(raw), delimiter)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def digits(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def doc_kind(doc: str) -> str:
    """Classifica o documento do fornecedor: cnpj, cpf ou outro."""
    d = digits(doc)
    if len(d) == 14:
        return "cnpj"
    if len(d) == 11:
        return "cpf"
    return "outro"


def cnpj_valido(doc: str) -> bool:
    """Confere os dígitos verificadores do CNPJ (descarta códigos fictícios como 00000000000001)."""
    d = digits(doc)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    def dv(base: str) -> int:
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
        r = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return 0 if r < 2 else 11 - r
    return dv(d[:12]) == int(d[12]) and dv(d[:13]) == int(d[13])


def mask_cpf(doc: str) -> str:
    """Esconde o CPF de pessoas físicas, como faz a Receita (***.456.789-**)."""
    d = digits(doc)
    if len(d) != 11:
        return doc
    return f"***.{d[3:6]}.{d[6:9]}-**"


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.upper()).strip()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def chunked(it: Iterable, n: int) -> Iterator[list]:
    buf: list = []
    for x in it:
        buf.append(x)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf
