"""A mesma pessoa em duas fontes oficiais: candidato do TSE e parlamentar da Câmara ou do Senado.

Nenhuma das fontes publica um código comum (o TSE tem o CPF, mas a Câmara e o Senado não). Ligamos pelo dia de
nascimento e pelo nome civil, com a mesma regra do site da Eleição 2026 (eleicao2026/etl/el_etl/eleitos.py,
mesma_pessoa). A regra fica copiada aqui porque aquele site roda sozinho, sem este pacote.
"""
from __future__ import annotations

import re
import unicodedata

PARTICULAS = {"DE", "DA", "DO", "DAS", "DOS", "E", "D"}


def normal(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return " ".join(re.sub(r"[^A-Z ]", " ", s).split())


def data_iso(s: str) -> str:
    """'30/04/1981' ou '1981-04-30' (ou '1981-04-30T00:00:00') -> '1981-04-30'."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else (s or "")[:10]


def _parecido(a: str, b: str) -> bool:
    """Mesmo nome, abreviado ("A" e "ALVES") ou com uma letra trocada ("MURILO" e "MURILLO")."""
    if a == b or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    curto, longo = sorted((a, b), key=len)
    return any(longo[:i] + longo[i + 1:] == curto for i in range(len(longo)))


def mesma_pessoa(nome_a: str, nasc_a: str, nome_b: str, nasc_b: str) -> bool:
    """Mesmo dia de nascimento, o mesmo primeiro nome e pelo menos 75% dos nomes do mais curto no mais longo (sem
    contar "de", "da", "dos"...). Gêmeos têm o mesmo nascimento e quase o mesmo nome: o primeiro nome os separa."""
    if not nasc_a or data_iso(nasc_a) != data_iso(nasc_b):
        return False
    a = [w for w in normal(nome_a).split() if w not in PARTICULAS]
    b = [w for w in normal(nome_b).split() if w not in PARTICULAS]
    if not a or not b or not _parecido(a[0], b[0]) or min(len(a[0]), len(b[0])) < 2:
        return False
    if a == b or "".join(a) == "".join(b):
        return True
    curto, longo = sorted((a, b), key=len)
    iguais = sum(1 for w in curto if any(_parecido(w, x) for x in longo))
    return len(curto) >= 2 and iguais >= 2 and iguais / len(curto) >= 0.75
