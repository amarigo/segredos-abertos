"""Sondagem temporária (Fase 2): formato real das fontes do estado e das cidades. Não publica nada."""
import csv
import gzip
import io
import json
import re
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) segredos-abertos/1.0 (+https://github.com/amarigo/segredos-abertos)"
OUT = []


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    OUT.append(s)


def baixar(url, limite=None, **kw):
    for t in range(3):
        try:
            r = S.get(url, timeout=180, stream=True, **kw)
            buf = io.BytesIO()
            for ch in r.iter_content(1 << 20):
                buf.write(ch)
                if limite and buf.tell() > limite:
                    break
            return r, buf.getvalue()
        except Exception as e:  # noqa: BLE001
            p(f"  falha {url}: {e}")
            time.sleep(5 * (t + 1))
    return None, b""


def texto(raw):
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        except (EOFError, OSError):
            d = __import__("zlib").decompressobj(16 + 15)
            raw = d.decompress(raw)
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1", "replace"), "latin-1?"


def csv_info(nome, raw, n=4, contar=(), filtro=None, maxlinhas=None):
    t, enc = texto(raw)
    sep = ";" if t[:2000].count(";") > t[:2000].count(",") else ","
    rd = csv.reader(io.StringIO(t), delimiter=sep)
    cab = next(rd, [])
    p(f"  {nome}: enc={enc} sep={sep!r} {len(cab)} colunas: {cab}")
    cont = {c: Counter() for c in contar}
    linhas = 0
    achados = []
    for ln in rd:
        linhas += 1
        if linhas <= n:
            p(f"    ex: {ln[:40]}")
        d = dict(zip(cab, ln))
        for c in contar:
            cont[c][(d.get(c) or "")[:60]] += 1
        if filtro and filtro(d) and len(achados) < 15:
            achados.append(ln[:40])
        if maxlinhas and linhas >= maxlinhas:
            break
    p(f"    {linhas} linhas")
    for c, k in cont.items():
        p(f"    {c}: {k.most_common(25)}")
    for a in achados:
        p(f"    achado: {a}")
    return cab


def ckan(pacote):
    for t in range(4):
        r, raw = baixar(f"https://dados.mg.gov.br/api/3/action/package_show?id={pacote}")
        if r is not None and r.status_code == 200:
            try:
                return json.loads(raw)["result"]["resources"]
            except (ValueError, KeyError):
                pass
        time.sleep(10)
    p(f"  CKAN {pacote}: sem resposta")
    return []


def verba_almg():
    p("\n## ALMG: verba indenizatória com valores")
    base = "https://dadosabertos.almg.gov.br"
    dep = 12193
    urls = [
        f"{base}/api/v2/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados/{dep}/datas?formato=json",
        f"{base}/api/v2/prestacao_contas/verbas_indenizatorias/deputados/{dep}/2026/3?formato=json",
        f"{base}/api/v2/prestacao_contas/verbas_indenizatorias/deputados/{dep}/2025/10?formato=json",
        f"{base}/ws/prestacao_contas/verbas_indenizatorias/deputados/{dep}/2025/10?formato=json",
        f"{base}/api/v2/prestacao_contas/verbas_indenizatorias/deputados/{dep}/2025/10",
        f"{base}/arquivo/verbas-indenizatorias/download?ano=2025",
        f"{base}/arquivo/verbas-indenizatorias/download?formato=json",
        "https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/",
        f"https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/detalhe.html?id={dep}",
        f"https://www.almg.gov.br/deputados/conheca_deputados/deputados-info.html?idDep={dep}&aba=js_tabVerba",
    ]
    for u in urls:
        time.sleep(8)
        r, raw = baixar(u, limite=8_000_000)
        st = r.status_code if r is not None else "?"
        t, _ = texto(raw)
        p(f"  {st} {len(raw)}B {u}")
        p(f"    início: {t[:700]!r}")
        if "valor" in t.lower():
            for m in list(re.finditer(r"(?i)valor", t))[:3]:
                p(f"    trecho: {t[max(0, m.start()-300):m.start()+300]!r}")
        links = sorted(set(re.findall(r"""["'](/?[^"'\s<>]*(?:verba|prestacao|api)[^"'\s<>]*)["']""", t)))[:40]
        if links:
            p(f"    links: {links}")


def remuneracao_cargos():
    p("\n## Dados MG: governador e secretários na remuneração")
    rec = ckan("remuneracao-servidores-ativos")
    alvo = [rc for rc in rec if re.search(r"2026", rc.get("name") or "")]
    if not alvo:
        return
    rc = alvo[-1]
    p(f"  lendo {rc['name']} {rc['url']}")
    r, raw = baixar(rc["url"])
    t, _ = texto(raw)
    rd = csv.DictReader(io.StringIO(t), delimiter=";")
    com, efe, org = Counter(), Counter(), Counter()
    ex = []
    cargo_alvo = re.compile(r"\bGOVERNADOR\b(?!\s+VALADARES)|SECRETARI[OA] DE ESTADO|SECRETARI[OA]-GERAL|VICE.GOVERNADOR|ADVOGADO.GERAL|CONTROLADOR.GERAL")
    for d in rd:
        cc, ce = (d.get("cargo_comissao") or "").strip(), (d.get("cargo_efetivo") or "").strip()
        if cargo_alvo.search(cc) or cargo_alvo.search(ce):
            com[cc] += 1
            efe[ce] += 1
            org[(d.get("orgao_exercicio") or "").strip()] += 1
            if len(ex) < 40:
                ex.append({k: (v or "").strip() for k, v in d.items() if k not in ("cpf", "masp", "numero_admissao") and (v or "").strip() not in ("", "0", "0,00")})
    p(f"  cargo_comissao: {com.most_common(40)}")
    p(f"  cargo_efetivo: {efe.most_common(20)}")
    p(f"  órgãos: {org.most_common(40)}")
    for e in ex:
        p(f"    {e}")


def scdp():
    p("\n## Dados MG: diárias e viagens (SCDP)")
    base = "https://dados.mg.gov.br/dataset/315840b0-49b5-45b6-8352-2fe3179a2b6d/resource/"
    arqs = {
        "funcao": base + "8472781b-84c5-41ca-981d-cc1f1c2c91fe/download/dm_funcao_scdp.csv.gz",
        "favorecido": base + "ab8f386b-84ec-4ebc-9698-99f3fa06db2f/download/dm_favorecido_scdp.csv.gz",
        "doc": base + "375b470f-0136-4fd9-918a-8fadc2099278/download/dm_documento_viagem.csv.gz",
        "orgao": base + "05a282b5-60bc-471d-80b8-09016836a483/download/dm_orgao_scdp.csv.gz",
        "cidade": base + "3fd7422c-1fb4-46f1-bc4f-06ab9e8b3520/download/dm_cidade.csv.gz",
        "diarias": base + "c1d9d278-c828-4347-82d4-1e88dbddd6e0/download/ft_diarias_scdp.csv.gz",
        "liqpag": base + "a35b5364-2b25-49e7-9081-d92a6b8112fd/download/ft_diarias_scdp_liqpag.csv.gz",
    }
    funcoes = {"12186", "12193", "11282", "12605", "15816"}
    for k, u in arqs.items():
        r, raw = baixar(u)
        p(f"  {k}: {len(raw)} bytes")
        t, enc = texto(raw)
        sep = ";" if t[:2000].count(";") > t[:2000].count(",") else ","
        rd = csv.reader(io.StringIO(t), delimiter=sep)
        cab = [c.lstrip("﻿") for c in next(rd, [])]
        p(f"    {len(cab)} colunas: {cab}")
        n, ach = 0, 0
        anos = Counter()
        for ln in rd:
            n += 1
            if n <= 3:
                p(f"    ex: {ln[:30]}")
            d = dict(zip(cab, ln))
            for c in cab:
                if "ano" in c.lower() or "data" in c.lower() or c.startswith("dt"):
                    anos[(d.get(c) or "")[:4] if not re.match(r"\d\d/", d.get(c) or "") else (d.get(c) or "")[-4:]] += 1
                    break
            if k in ("diarias", "liqpag", "favorecido") and any((d.get(c) or "") in funcoes for c in cab if "funcao" in c.lower()):
                ach += 1
                if ach <= 6:
                    p(f"    governador/secretário: {d}")
            if k == "funcao" and re.search(r"GOVERNADOR|SECRETARIO DE ESTADO", " ".join(ln)):
                p(f"    função: {ln}")
        p(f"    {n} linhas; achados {ach}; anos {sorted(anos.items())[-12:]}")


def paginas_proposicao():
    p("\n## ALMG: página pública de uma proposição")
    for u in ("https://www.almg.gov.br/proposicoes/PL/3221/2025/",
              "https://www.almg.gov.br/atividade-parlamentar/projetos-de-lei/texto/?tipo=PL&num=3221&ano=2025",
              "https://www.almg.gov.br/atividade-parlamentar/projetos-de-lei/projetos/?tipo=PL&num=3221&ano=2025",
              "https://www.almg.gov.br/deputados/conheca_deputados/deputados-info.html?idDep=12193"):
        time.sleep(4)
        r, raw = baixar(u, limite=3_000_000)
        t, _ = texto(raw)
        tit = re.search(r"<title>(.*?)</title>", t, re.S)
        p(f"  {r.status_code if r is not None else '?'} {r.url if r is not None else ''} título={tit.group(1).strip()[:120] if tit else ''!r} cita3221={'3221' in t}")


if __name__ == "__main__":
    saida = Path(sys.argv[1])
    saida.mkdir(parents=True, exist_ok=True)
    for etapa in (paginas_proposicao, verba_almg, scdp, remuneracao_cargos):
        try:
            etapa()
        except Exception as e:  # noqa: BLE001
            p(f"ERRO em {etapa.__name__}: {e!r}")
    (saida / "relatorio.md").write_text("\n".join(OUT), encoding="utf-8")
