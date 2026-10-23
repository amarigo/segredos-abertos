"""Ajudantes para ler os arquivos do estado (ALMG, Dados MG, Tesouro) do jeito que eles vêm.

Cada fonte tem seu jeito: separador ',' ou ';', UTF-8 ou latin-1, valores "1234.56", "1.234,56" ou "R$1.234,56",
arquivos .gz. Aqui ficam as funções que lidam com isso, para os módulos de cada fonte só tratarem do conteúdo.

CPF: nenhum CPF sai daqui. `doc_publico` devolve o CNPJ (14 dígitos) ou "" e `tipo_doc` diz se era pessoa física.
"""
from __future__ import annotations

import csv
import gzip
import io
import logging
import re
import time
from pathlib import Path
from typing import Iterator

from sa_etl.util import avisar, download, norm_name

log = logging.getLogger("mg_etl.fontes")


def valor(v) -> float:
    """'R$1.234,56', '1.234,56', '1234.56', '1234,5', '-' e '' viram número (0 quando não dá)."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[R$\s ]", "", str(v))
    if not s or s in ("-", "N/A"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        x = float(s)
    except ValueError:
        return 0.0
    return -x if neg else x


def tipo_doc(doc) -> str:
    d = re.sub(r"\D", "", str(doc or ""))
    return "cnpj" if len(d) == 14 else "cpf" if len(d) == 11 else ""


def doc_publico(doc) -> str:
    """Só o CNPJ (de empresa ou entidade). CPF nunca: devolve ''."""
    d = re.sub(r"\D", "", str(doc or ""))
    return d if len(d) == 14 else ""


CPF_NO_TEXTO = re.compile(r"(?<![\d.])(\d{3}\.?\d{3}\.?\d{3}-?\d{2})(?![\d.])")


def sem_cpf(s: str) -> str:
    """Tira de um texto livre (nome, descrição, motivo) qualquer número com cara de CPF.

    Alguns arquivos oficiais trazem o CPF dentro do nome ("FULANO - 123.456.789-09"). Um número de 11 dígitos
    pode também ser um telefone; some do mesmo jeito, o que não faz falta no site."""
    s = CPF_NO_TEXTO.sub("", s or "")
    return re.sub(r"\s*[-–]\s*$", "", re.sub(r"\s{2,}", " ", s)).strip()


def chave_nome(s: str) -> str:
    """Nome para comparar: sem acento, sem 'Deputado', sem pontuação e espaços repetidos."""
    n = norm_name(s or "")
    n = re.sub(r"^(DEPUTAD[OA]|DEP\.?)\s+", "", n)
    return re.sub(r"[^A-Z0-9 ]", "", n).replace("  ", " ").strip()


# Palavras curtas que não são siglas (as outras, como SES, APAE, UBS, EE, ficam em maiúsculas)
PALAVRAS_CURTAS = {"rua", "sao", "são", "ana", "rio", "ex", "ze", "zé", "sa", "sá", "bom", "boa", "paz", "sol", "mar", "lar", "luz",
                   "dr", "dra", "sr", "sra", "sta", "sto", "eva", "ivo", "lia", "rei", "fe", "fé", "ave", "via", "vila", "nova",
                   "um", "uma", "ao", "aos", "às", "no", "na", "nos", "nas", "pelo", "pela", "por", "seu", "sua", "lt", "ltd"}


def bonito(s: str) -> str:
    """'PREFEITURA MUNICIPAL DE ITAJUBA' -> 'Prefeitura Municipal de Itajuba'. Siglas curtas ficam como estão."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s or not s.isupper():
        return s
    pal = []
    for i, w in enumerate(s.split(" ")):
        lw = w.lower()
        if i and lw in ("da", "de", "do", "das", "dos", "e", "a", "o", "em", "para", "com"):
            pal.append(lw)
        elif len(w) <= 3 and w.isalpha() and lw not in PALAVRAS_CURTAS:
            pal.append(w)
        else:
            pal.append(w[:1] + w[1:].lower())
    return " ".join(pal)


def decodificar(raw: bytes) -> str:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def separador(texto: str) -> str:
    amostra = texto[:5000]
    return ";" if amostra.count(";") > amostra.count(",") else ","


def ler_csv(texto: str, obrigatorias: set[str] = frozenset(), sep: str | None = None) -> Iterator[dict[str, str]]:
    """Linhas como dicionário, com os nomes de coluna sem espaço sobrando. Falha se faltar coluna obrigatória."""
    rd = csv.reader(io.StringIO(texto), delimiter=sep or separador(texto))
    cab = [c.strip() for c in next(rd, None) or []]
    falta = set(obrigatorias) - set(cab)
    if falta:
        raise ValueError(f"colunas faltando: {sorted(falta)} (o arquivo tem {cab[:20]})")
    for ln in rd:
        if len(ln) < len(cab):
            continue
        yield {c: (ln[i] or "").strip() for i, c in enumerate(cab)}


def parece_csv(minimo: int = 200, colunas: tuple[str, ...] = ()):
    """Validador para util.download: descarta página de erro em HTML e arquivo cortado ou sem as colunas."""
    def ok(raw: bytes) -> bool:
        if len(raw) < minimo:
            return False
        try:
            inicio = decodificar(raw[:20000] if raw[:2] != b"\x1f\x8b" else raw)[:20000]
        except (OSError, EOFError):
            return False
        if re.match(r"\s*<(!doctype|html|\?xml)", inicio, re.I):
            return False
        cab = inicio.splitlines()[0] if inicio else ""
        return all(c in cab for c in colunas)
    return ok


def baixar(url: str, dest: Path, max_horas: float, nome: str, colunas: tuple[str, ...] = (), minimo: int = 200) -> str | None:
    """Baixa (ou usa o cache) e devolve o texto. Se a fonte falhar e não houver cópia, avisa e devolve None."""
    try:
        f = download(url, dest, max_horas=max_horas, validar=parece_csv(minimo, colunas))
        return decodificar(f.read_bytes())
    except Exception as e:  # noqa: BLE001 - fonte fora do ar: o resto do site segue
        log.warning("%s: %s", nome, e)
        avisar(f"{nome}: o site oficial não respondeu e não havia cópia anterior; essa parte ficou sem atualização")
        return None


def pausa(segundos: float) -> None:
    """A API da ALMG responde 429 (muitas requisições) se formos rápidos demais."""
    time.sleep(segundos)
