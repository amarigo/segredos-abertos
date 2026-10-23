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


def almg():
    p("\n## ALMG")
    r, raw = baixar("https://dadosabertos.almg.gov.br/api/v2/deputados/em_exercicio?formato=json")
    if raw:
        try:
            lst = json.loads(raw)["list"]
            p(f"  em exercício: {len(lst)}; ex: {lst[:3]}")
            dep = lst[0]["id"]
        except Exception as e:  # noqa: BLE001
            p(f"  em_exercicio: {r.status_code if r is not None else ''} {e} {raw[:200]!r}")
            dep = 12193
    time.sleep(3)
    r, raw = baixar(f"https://dadosabertos.almg.gov.br/api/v2/deputados/{dep}?formato=json")
    try:
        d = json.loads(raw)["deputado"]
        p("  ficha: " + json.dumps({k: v for k, v in d.items() if k not in ("vidaProfissionalPolitica", "atuacaoParlamentar", "condecoracao")}, ensure_ascii=False)[:2500])
    except Exception as e:  # noqa: BLE001
        p(f"  ficha: {e}")
    r, raw = baixar("https://dadosabertos.almg.gov.br/arquivo/deputados/download")
    csv_info("deputados", raw, contar=("UltimaLegislatura", "Partido"))
    r, raw = baixar("https://dadosabertos.almg.gov.br/arquivo/verbas-indenizatorias/download")
    cab = csv_info("verbas", raw, n=3, contar=("DescricaoTipoDespesa",), filtro=lambda d: d.get("ValorReembolso"))
    t, _ = texto(raw)
    rd = csv.DictReader(io.StringIO(t))
    tam, ref, val, anos, vazias = Counter(), Counter(), Counter(), Counter(), 0
    exemplos = []
    for d in rd:
        doc = re.sub(r"\D", "", d.get("CpfCnpj") or "")
        tam[len(doc)] += 1
        ref[re.sub(r"\d", "9", d.get("Referencia") or "")] += 1
        val[re.sub(r"\d", "9", d.get("ValorReembolso") or "")[:12]] += 1
        anos[(d.get("Referencia") or "")[-4:]] += 1
        if not d.get("ValorReembolso"):
            vazias += 1
        elif len(exemplos) < 5 and d.get("Emitente"):
            exemplos.append({k: v for k, v in d.items() if k != "CpfCnpj"})
    p(f"    tamanho do doc: {tam.most_common()}; formatos ref {ref.most_common(5)}; valores {val.most_common(8)}; anos {sorted(anos.items())}; vazias {vazias}")
    for e in exemplos:
        p(f"    nota: {e}")
    for ano in (2025, 2026):
        r, raw = baixar(f"https://dadosabertos.almg.gov.br/arquivo/proposicoes/download?ano={ano}")
        csv_info(f"proposições {ano}", raw, n=2, contar=("SiglaTipoProposicao", "Situacao", "NomeFaseAtual", "Origem"))
        t, _ = texto(raw)
        aut = Counter()
        for d in csv.DictReader(io.StringIO(t)):
            try:
                a = json.loads(d.get("Autores") or "[]")
                aut[len(a)] += 1
                if len(a) and aut[len(a)] <= 2:
                    p(f"    autores: {a[:3]}")
            except ValueError:
                aut["erro"] += 1
        p(f"    nº de autores: {aut.most_common(8)}")
    # página da emenda e CSV
    r, raw = baixar("https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/")
    t, _ = texto(raw)
    LINK = re.compile(r"""href=["']([^"']+[.](?:csv|xlsx?|zip))""")
    MEDIA = re.compile(r"""https?://mediaserver[^"'\s<>]+""")
    p(f"  página de emendas: links {sorted(set(LINK.findall(t)))[:20]}")
    p(f"  links mediaserver {sorted(set(MEDIA.findall(t)))[:20]}")
    r, raw = baixar("https://mediaserver.almg.gov.br/acervo/497/469/2497469.csv")
    alvo = lambda d: any(re.search(r"ITAJUB|PARAIS[OÓ]POLIS", v or "", re.I) for v in d.values())  # noqa: E731
    csv_info("emendas ALMG", raw, n=2, contar=("Ano da Indicação", "Status da Indicação", "Tipo de Indicação", "Status", "Indicador de Impositividade"), filtro=alvo)
    t, _ = texto(raw)
    rd = csv.reader(io.StringIO(t), delimiter=";")
    cab = next(rd)
    p(f"  colunas finais: {cab[30:]}")
    for ln in rd:
        if alvo(dict(zip(cab, ln))):
            p(f"  linha completa: {dict(zip(cab, ln))}")
            break


def dados_mg():
    p("\n## Dados MG")
    for pac in ("despesa", "remuneracao-servidores-ativos", "viagens", "diarias", "portal_emendas_estaduais"):
        rec = ckan(pac)
        p(f"\n### {pac}: {len(rec)} recursos")
        for rc in rec:
            if not re.search(r"Remunera.*20(1|20|21|22|23|24)|Despesa 20(0|1|20|21|22|23|24)|Empenho", rc.get("name") or ""):
                p(f"    - {rc.get('name')!r} {rc.get('url')}")
        if pac == "despesa":
            for rc in rec:
                if re.search(r"^(Favorecido|Despesa - Ordem de Pagamento|Unidade Orçamentária|Situação Ordem)", rc.get("name") or ""):
                    r, raw = baixar(rc["url"], limite=30_000_000)
                    csv_info(rc["name"], raw, n=4, filtro=lambda d: any(re.search(r"ITAJUB|PARAISOPOL", v or "", re.I) for v in d.values()), maxlinhas=400000)
        if pac == "remuneracao-servidores-ativos":
            alvo = [rc for rc in rec if re.search(r"2026", rc.get("name") or "")]
            if alvo:
                rc = alvo[-1]
                p(f"  lendo {rc['name']} {rc['url']}")
                r, raw = baixar(rc["url"])
                p(f"  {len(raw)} bytes")
                csv_info(rc["name"], raw, n=3, filtro=lambda d: any(re.search(r"GOVERNADOR|SECRETARIO DE ESTADO|SECRETÁRIO DE ESTADO", v or "", re.I) for v in d.values()))
        if pac in ("viagens", "diarias"):
            for rc in rec[:12]:
                if (rc.get("format") or "").upper() in ("CSV", "") and not rc["url"].endswith(".json"):
                    r, raw = baixar(rc["url"], limite=20_000_000)
                    csv_info(rc.get("name"), raw, n=2, filtro=lambda d: any(re.search(r"GOVERNADOR|SECRET[AÁ]RIO DE ESTADO", v or "", re.I) for v in d.values()), maxlinhas=300000)
        if pac == "portal_emendas_estaduais":
            for rc in rec:
                if re.search(r"Execução$|Indicações$", rc.get("name") or ""):
                    r, raw = baixar(rc["url"])
                    csv_info(rc["name"], raw, n=2, filtro=lambda d: any(re.search(r"ITAJUB|PARAISOPOL", v or "", re.I) for v in d.values()))


def siconfi():
    p("\n## SICONFI (Tesouro)")
    base = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
    r, raw = baixar(f"{base}/entes")
    try:
        entes = json.loads(raw)["items"]
        ach = [e for e in entes if re.search(r"Itajub|Paraisópolis|Paraisopolis", e.get("ente") or "") and e.get("uf") == "MG"]
        p(f"  entes: {len(entes)}; achados {ach}")
    except Exception as e:  # noqa: BLE001
        p(f"  entes: {e} {raw[:300]!r}")
        ach = [{"cod_ibge": 3132404}]
    for e in ach:
        cod = e["cod_ibge"]
        for anexo in ("DCA-Anexo I-E", "DCA-Anexo I-C"):
            r, raw = baixar(f"{base}/dca", params={"an_exercicio": 2024, "no_anexo": anexo, "id_ente": cod})
            try:
                it = json.loads(raw)["items"]
                p(f"  {cod} {anexo}: {len(it)} itens; colunas {Counter(i.get('coluna') for i in it)}")
                for i in it[:3]:
                    p(f"    {i}")
                contas = Counter(i.get("conta") for i in it)
                p(f"    contas: {list(contas)[:60]}")
            except Exception as ex:  # noqa: BLE001
                p(f"  {anexo}: {ex} {raw[:300]!r}")
            time.sleep(1.5)
        r, raw = baixar(f"{base}/rreo", params={"an_exercicio": 2026, "nr_periodo": 4, "co_tipo_demonstrativo": "RREO", "no_anexo": "RREO-Anexo 02", "id_ente": cod})
        try:
            it = json.loads(raw)["items"]
            p(f"  {cod} RREO 2026/4 anexo 2: {len(it)} itens; colunas {Counter(i.get('coluna') for i in it)}")
        except Exception as ex:  # noqa: BLE001
            p(f"  rreo: {ex} {raw[:300]!r}")


def cgu():
    p("\n## CGU: emendas federais por cidade")
    r, raw = baixar("https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO")
    p(f"  {r.status_code if r is not None else '?'} {len(raw)} bytes")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return
    for n in z.namelist():
        with z.open(n) as f:
            t = io.TextIOWrapper(f, encoding="latin-1")
            rd = csv.reader(t, delimiter=";")
            cab = next(rd)
            p(f"  {n}: {cab}")
            k = 0
            for ln in rd:
                if any(re.search(r"ITAJUB|PARAIS[OÓ]POLIS", v, re.I) for v in ln):
                    k += 1
                    if k <= 4:
                        p(f"    {ln}")
            p(f"    linhas com as cidades: {k}")


if __name__ == "__main__":
    saida = Path(sys.argv[1])
    saida.mkdir(parents=True, exist_ok=True)
    for etapa in (almg, dados_mg, siconfi, cgu):
        try:
            etapa()
        except Exception as e:  # noqa: BLE001
            p(f"ERRO em {etapa.__name__}: {e!r}")
    (saida / "relatorio.md").write_text("\n".join(OUT), encoding="utf-8")
