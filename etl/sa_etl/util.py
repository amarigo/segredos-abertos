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
from pathlib import Path
from typing import Any, Iterable, Iterator

import requests

log = logging.getLogger("sa_etl")

USER_AGENT = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


def get(url: str, *, params: dict | None = None, tries: int = 4, timeout: int = 120) -> requests.Response:
    """GET com espera crescente entre tentativas (2s, 4s, 8s...)."""
    last: Exception | None = None
    for attempt in range(tries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 404:
                r.raise_for_status()
            if r.status_code >= 500 or r.status_code == 429:
                raise requests.HTTPError(f"{r.status_code} em {url}")
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                raise
            last = e
        except requests.RequestException as e:
            last = e
        wait = 2 ** (attempt + 1)
        log.warning("Falha em %s (%s); nova tentativa em %ss", url, last, wait)
        time.sleep(wait)
    raise RuntimeError(f"Não foi possível baixar {url}: {last}")


def get_json(url: str, **kw) -> Any:
    return get(url, **kw).json()


def download(url: str, dest: Path) -> Path:
    """Baixa um arquivo para o cache local, se ainda não existir."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = get(url, timeout=600)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.rename(dest)
    return dest


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
