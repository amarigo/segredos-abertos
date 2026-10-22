"""Confere se o PDF de cada nota fiscal da Câmara está mesmo no site dela.

O arquivo da cota traz, para cada nota digitalizada, um link para o PDF
(https://www.camara.leg.br/cota-parlamentar/documentos/publ/{deputado}/{ano}/{documento}.pdf).
Quase sempre o PDF abre, mas algumas notas entram nos dados sem o arquivo, e o link dá erro 404 também no
site da Câmara. Nessas, o site mostra a página oficial de detalhe da despesa no lugar do PDF, e avisa.

Cada link que abriu fica guardado no cache e não é conferido de novo. Os que deram 404 são conferidos a cada
coleta, porque o PDF pode aparecer depois. Para a coleta não demorar, cada rodada confere no máximo `minutos`
de links, das notas mais recentes para as mais antigas; as mais antigas vão sendo conferidas nas rodadas seguintes.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from .camara import link_detalhe
from .util import USER_AGENT

log = logging.getLogger("sa_etl.links_notas")

PDF = re.compile(r"/cota-parlamentar/documentos/publ/(\d+/\d+/\d+)\.pdf$")
FALTANDO = {404, 410}


def chave(url: str) -> str | None:
    """Parte do link que identifica a nota ("deputado/ano/documento"), ou None se não for um PDF da Câmara."""
    m = PDF.search(url or "")
    return m.group(1) if m else None


def conferir(despesas: list[dict], cache: Path, minutos: float = 20, workers: int = 16) -> dict:
    """Confere os PDFs das notas e troca o link das que não têm PDF pela página oficial de detalhe.

    Muda as despesas no lugar e devolve um resumo com as contagens.
    """
    arq = cache / "links-notas.json"
    try:
        guardado = json.loads(arq.read_text()) if arq.exists() else {}
    except ValueError:
        guardado = {}
    ok: set[str] = set(guardado.get("ok", []))
    faltando: dict[str, str] = dict(guardado.get("faltando", {}))  # chave -> data em que deu 404 pela primeira vez

    notas = [(d, chave(d["url"])) for d in despesas if d.get("link") == "nota"]
    notas = [(d, k) for d, k in notas if k]
    datas: dict[str, str] = {}
    for d, k in notas:
        datas[k] = max(datas.get(k, ""), d.get("data") or "")
    # Primeiro as que deram 404 (o PDF pode ter aparecido), depois as nunca conferidas, das mais novas para as mais velhas
    pendentes = sorted((k for k in datas if k not in ok), key=lambda k: (k in faltando, datas[k]), reverse=True)

    sessao = requests.Session()
    sessao.headers["User-Agent"] = USER_AGENT
    sessao.mount("https://", HTTPAdapter(pool_maxsize=workers))
    limite = time.monotonic() + minutos * 60
    erros_seguidos = 0
    trava = threading.Lock()
    hoje = dt.date.today().isoformat()
    conferidas = 0

    def parar() -> bool:
        return time.monotonic() >= limite or erros_seguidos >= 30  # sem tempo, ou o site da Câmara está fora do ar

    def status(k: str) -> int | None:
        nonlocal erros_seguidos, conferidas
        if parar():
            return None
        for tentativa in range(2):
            try:
                r = sessao.head(f"https://www.camara.leg.br/cota-parlamentar/documentos/publ/{k}.pdf",
                                timeout=20, allow_redirects=True)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(str(r.status_code))
                with trava:
                    erros_seguidos = 0
                    conferidas += 1
                return r.status_code
            except requests.RequestException:
                time.sleep(2 * (tentativa + 1))
        with trava:
            erros_seguidos += 1
        return None

    with ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(pendentes), 2000):
            if parar():
                break
            lote = pendentes[i:i + 2000]
            for k, st in zip(lote, ex.map(status, lote)):
                if st is not None and st < 400:
                    ok.add(k)
                    faltando.pop(k, None)
                elif st in FALTANDO:
                    faltando.setdefault(k, hoje)
    if erros_seguidos >= 30:
        log.warning("Links das notas: o site da Câmara não respondeu; o resto fica para a próxima coleta")

    cache.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(".part")
    tmp.write_text(json.dumps({"ok": sorted(ok), "faltando": faltando}))
    tmp.replace(arq)

    trocadas = 0
    for d, k in notas:
        if k in faltando:
            ide = k.rsplit("/", 1)[1]
            d["url"] = link_detalhe(d.get("nu"), d["ano"], d["mes"], d.get("sub"), d.get("doc"), d.get("num"), ide) or d["url"]
            d["link"] = "sem_pdf"
            trocadas += 1
    resumo = {"notas": len(datas), "conferidas_agora": conferidas, "abrem": sum(1 for k in datas if k in ok),
              "sem_pdf": sum(1 for k in datas if k in faltando), "falta_conferir": sum(1 for k in datas if k not in ok and k not in faltando),
              "despesas_trocadas": trocadas}
    log.info("Links das notas da Câmara: %s", resumo)
    return resumo
