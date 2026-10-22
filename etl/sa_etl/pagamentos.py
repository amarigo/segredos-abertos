"""Pagamentos feitos com dinheiro de emendas: quem pagou, para quem e com qual documento.

Fonte: arquivos diários de despesas do Portal da Transparência (CGU):
    https://portaldatransparencia.gov.br/download-de-dados/despesas/AAAAMMDD

Cada dia traz, entre outras, três tabelas que usamos:
- Despesas_Empenho: a reserva do dinheiro (nota de empenho). Tem a coluna "Autor Emenda", o órgão que paga
  (ministério e unidade), quem vai receber e a descrição.
- Despesas_Pagamento_EmpenhosImpactados: qual empenho cada pagamento (ordem bancária) quitou.
- Despesas_Pagamento: o pagamento em si: data, órgão, quem recebeu e valor.

Ligamos pagamento → empenho → emenda. Cada dia é lido uma vez e guardado em cache, só com o que é de emenda.
Os dias são lidos em ordem, para que o empenho já seja conhecido quando chega o pagamento.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import logging
import re
import time
import zipfile
from pathlib import Path

from .util import _session, digits, norm_name, to_float

log = logging.getLogger("sa_etl.pagamentos")

URL = "https://portaldatransparencia.gov.br/download-de-dados/despesas/{dia}"
DOC = "https://portaldatransparencia.gov.br/despesas/documento/{fase}/{codigo}"
VERSAO = 1
SEM_AUTOR = {"", "SEM INFORMACAO", "SEM EMENDA", "NAO SE APLICA", "-1", "0", "-8"}


def url_documento(codigo: str) -> str:
    """Página oficial do documento no Portal (empenho, liquidação ou pagamento)."""
    tipo = codigo[11:13] if len(codigo) > 13 else ""
    fase = "empenho" if tipo == "NE" else "liquidacao" if tipo in ("NS", "NL") else "pagamento"
    return DOC.format(fase=fase, codigo=codigo)


def autor_da_emenda(valor: str) -> tuple[str, str] | None:
    """'FULANO DE TAL / EMENDA 12' → ('FULANO DE TAL', '12'). Sem emenda → None."""
    v = (valor or "").strip()
    if norm_name(v) in SEM_AUTOR or norm_name(v).startswith("SEM "):
        return None
    m = re.match(r"^(.*?)\s*/\s*EMENDA\s*(\d+)\s*$", v, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2)
    return v, ""


def _tabela(z: zipfile.ZipFile, fim: str):
    nome = next((n for n in z.namelist() if n.endswith(fim)), None)
    if not nome:
        return
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", errors="replace", newline=""), delimiter=";")


def _curto(t: str, n: int = 240) -> str:
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def ler_dia(zip_path: Path, empenhos_emenda: set[str]) -> dict:
    """Lê um dia. Devolve os empenhos de emenda emitidos no dia e os pagamentos que quitaram empenhos de emenda
    (deste dia ou de dias anteriores, que vêm em empenhos_emenda). Atualiza empenhos_emenda."""
    out = {"empenhos": [], "pagamentos": []}
    with zipfile.ZipFile(zip_path) as z:
        for r in _tabela(z, "_Despesas_Empenho.csv"):
            a = autor_da_emenda(r.get("Autor Emenda", ""))
            if not a:
                continue
            cod = r.get("Código Empenho", "")
            empenhos_emenda.add(cod)
            out["empenhos"].append({
                "codigo": cod, "data": _data(r.get("Data Emissão")), "autor": a[0], "emenda": a[1],
                "orgao_sup": r.get("Órgão Superior", ""), "orgao": r.get("Órgão", ""), "ug": r.get("Unidade Gestora", ""),
                "doc": digits(r.get("Código Favorecido")), "favorecido": (r.get("Favorecido") or "").strip(),
                "funcao": r.get("Função", ""), "modalidade": r.get("Modalidade de Aplicação", ""),
                "descricao": _curto(r.get("Observação", "")),
                "valor": round(to_float(r.get("Valor do Empenho Convertido pra R$") or r.get("Valor Original do Empenho")), 2),
            })
        # pagamento → empenhos quitados (um pagamento pode quitar mais de um empenho)
        quitou: dict[str, list[list]] = {}
        for r in _tabela(z, "_Despesas_Pagamento_EmpenhosImpactados.csv"):
            emp = r.get("Código Empenho", "")
            if emp in empenhos_emenda:
                v = to_float(r.get("Valor Pago (R$)")) + to_float(r.get("Valor Restos a Pagar Pagos (R$)"))
                if v:
                    quitou.setdefault(r.get("Código Pagamento", ""), []).append([emp, round(v, 2)])
        if quitou:
            for r in _tabela(z, "_Despesas_Pagamento.csv"):
                cod = r.get("Código Pagamento", "")
                if cod not in quitou:
                    continue
                out["pagamentos"].append({
                    "codigo": cod, "data": _data(r.get("Data Emissão")), "tipo": r.get("Tipo Documento", ""),
                    "orgao_sup": r.get("Órgão Superior", ""), "ug": r.get("Unidade Gestora", ""),
                    "doc": digits(r.get("Código Favorecido")), "favorecido": (r.get("Favorecido") or "").strip(),
                    "descricao": _curto(r.get("Observação", "")), "empenhos": quitou[cod],
                })
    return out


def _data(s: str | None) -> str:
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else (s or "")[:10]


def _baixar_dia(dia: str, dest: Path) -> bool | None:
    """True: baixou. None: o Portal não tem arquivo para o dia (fim de semana, feriado). False: falhou."""
    for tentativa in range(3):
        try:
            r = _session.get(URL.format(dia=dia), timeout=300, stream=True, allow_redirects=True,
                             headers={"Accept": "application/zip,*/*"})
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            with dest.open("wb") as f:
                for b in r.iter_content(1 << 20):
                    f.write(b)
            if zipfile.is_zipfile(dest):
                return True
            return None  # página de erro em vez de arquivo: o dia não existe
        except Exception as e:  # noqa: BLE001
            log.debug("Pagamentos: falha em %s (%s)", dia, e)
            time.sleep(2 ** (tentativa + 1))
    return False


def coletar(anos: list[int], cache: Path, minutos: float = 30, hoje: dt.date | None = None) -> list[Path]:
    """Lê os dias ainda não lidos, em ordem, até o limite de tempo. Devolve os arquivos de todos os dias já lidos.

    O primeiro uso lê milhares de dias e leva algumas execuções; depois, só os dias novos. Os 5 dias mais recentes
    são lidos de novo, porque o Portal às vezes publica o arquivo do dia com atraso.
    """
    hoje = hoje or dt.date.today()
    cache.mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    dia = dt.date(min(anos), 1, 1)
    empenhos_emenda: set[str] = set()
    lidos, novos, falhas = [], 0, 0
    tmp = cache / "dia.zip"
    while dia < hoje:
        nome = dia.strftime("%Y%m%d")
        f = cache / f"{nome}-v{VERSAO}.json.gz"
        recente = (hoje - dia).days <= 5
        if f.exists() and not recente:
            d = json.loads(gzip.decompress(f.read_bytes()))
            empenhos_emenda.update(e["codigo"] for e in d["empenhos"])
            lidos.append(f)
        elif time.time() - inicio > minutos * 60:
            break  # limite de tempo: continua na próxima execução, a partir deste dia
        else:
            ok = _baixar_dia(nome, tmp)
            if ok:
                d = ler_dia(tmp, empenhos_emenda)
            elif ok is None:
                d = {"empenhos": [], "pagamentos": [], "sem_arquivo": True}
            else:
                falhas += 1
                if f.exists():
                    lidos.append(f)
                    d = json.loads(gzip.decompress(f.read_bytes()))
                    empenhos_emenda.update(e["codigo"] for e in d["empenhos"])
                    dia += dt.timedelta(days=1)
                    continue
                if falhas >= 5:
                    log.warning("Pagamentos: Portal falhou em %d dias seguidos; para em %s", falhas, nome)
                    break
                dia += dt.timedelta(days=1)
                continue
            falhas = 0
            if not (ok is None and recente):  # dia recente sem arquivo ainda pode aparecer depois
                f.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False).encode()))
                lidos.append(f)
                novos += 1
        dia += dt.timedelta(days=1)
    tmp.unlink(missing_ok=True)
    falta = (hoje - dia).days
    log.info("Pagamentos de emendas: %d dias lidos agora, %d no total, %d empenhos de emenda; %s",
             novos, len(lidos), len(empenhos_emenda),
             "tudo em dia" if falta <= 0 else f"faltam {falta} dias (continua na próxima execução)")
    return lidos
