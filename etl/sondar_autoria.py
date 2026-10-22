"""Sonda temporária: autoria própria x coautoria, na Câmara e no Senado."""
import collections
import csv
import io
import json
import re
import time

import requests

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (segredos-abertos; sonda)"
ANO = 2025


def get(url, **kw):
    t = time.time()
    try:
        r = S.get(url, timeout=180, **kw)
        print(f"GET {url} -> {r.status_code} {len(r.content)}B {time.time() - t:.1f}s", flush=True)
        return r
    except Exception as e:  # noqa: BLE001
        print("ERRO", url, repr(e), flush=True)
        return None


def csv_rows(url):
    r = get(url)
    if not r or r.status_code != 200:
        return None
    txt = r.content.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(txt), delimiter=";"))


def camara():
    print("\n===== CÂMARA =====")
    autores = csv_rows(f"https://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/csv/proposicoesAutores-{ANO}.csv")
    props = csv_rows(f"https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-{ANO}.csv")
    if not autores:
        return
    print("colunas autores:", list(autores[0].keys()))
    print("exemplo:", autores[0])
    print("tipoAutor:", collections.Counter(a.get("tipoAutor") for a in autores).most_common(8))
    print("proponente:", collections.Counter(a.get("proponente") for a in autores).most_common(5))
    print("ordemAssinatura:", collections.Counter(a.get("ordemAssinatura") for a in autores).most_common(8))
    tipo = {}
    if props:
        print("colunas proposições:", list(props[0].keys()))
        tipo = {p.get("id"): p.get("siglaTipo") for p in props}
        print("siglaTipo:", collections.Counter(tipo.values()).most_common(25))
        print("datas:", min(p.get("dataApresentacao", "") for p in props), max(p.get("dataApresentacao", "") for p in props))
    dep = collections.defaultdict(lambda: collections.Counter())
    for a in autores:
        d = a.get("idDeputadoAutor")
        if not d:
            continue
        c = dep[d]
        c["total"] += 1
        c["ordem1"] += a.get("ordemAssinatura") == "1"
        c["proponente1"] += a.get("proponente") == "1"
        c["ordem1_prop1"] += a.get("ordemAssinatura") == "1" and a.get("proponente") == "1"
        c["tipo:" + str(tipo.get(a.get("idProposicao")))] += 1
        if a.get("ordemAssinatura") == "1":
            c["principal:" + str(tipo.get(a.get("idProposicao")))] += 1
    # quantos autores principais por proposição
    por_prop = collections.Counter(a["idProposicao"] for a in autores if a.get("ordemAssinatura") == "1")
    print("autores com ordem 1 por proposição:", collections.Counter(por_prop.values()).most_common(5))
    print("deputados:", len(dep))
    top = sorted(dep.items(), key=lambda x: -x[1]["total"])
    amostra = [x[0] for x in top[:4]] + [x[0] for x in top[200:203]] + [x[0] for x in top[450:452]]
    for d in amostra:
        c = dep[d]
        pag = get(f"https://www.camara.leg.br/deputados/{d}?ano={ANO}")
        site = None
        if pag is not None and pag.status_code == 200:
            t = re.sub(r"<[^>]+>", " ", pag.text)
            t = re.sub(r"\s+", " ", t)
            m = re.search(r"de sua autoria\D*?(\d[\d.]*)", t)
            site = m.group(1) if m else None
        tipos = {k[5:]: v for k, v in c.most_common() if k.startswith("tipo:")}
        princ = {k[10:]: v for k, v in c.most_common() if k.startswith("principal:")}
        print(f"dep {d}: site={site} total={c['total']} ordem1={c['ordem1']} prop1={c['proponente1']} o1p1={c['ordem1_prop1']}")
        print("   tipos:", dict(list(tipos.items())[:10]))
        print("   principal:", dict(list(princ.items())[:10]))


def senado():
    print("\n===== SENADO =====")
    L = "https://legis.senado.leg.br/dadosabertos"
    h = {"Accept": "application/json"}
    for doc in (L + "/v3/api-docs", L + "/api-docs", L + "/v3/api-docs/swagger-config"):
        r = get(doc, headers=h)
        if r is not None and r.status_code == 200 and r.text.lstrip().startswith("{"):
            try:
                d = r.json()
                for path, ops in (d.get("paths") or {}).items():
                    if path.startswith("/processo") or "autoria" in path.lower():
                        for _, op in ops.items():
                            nomes = [p.get("name") for p in op.get("parameters", [])]
                            print("  ", path, nomes)
            except Exception as e:  # noqa: BLE001
                print("  api-docs erro", e)
            break
    for cod, nome in (("5894", ""), ("5012", ""), ("4981", ""), ("5953", "")):
        r = get(f"{L}/processo?codigoParlamentarAutor={cod}&ano={ANO}", headers=h)
        if r is not None and r.status_code == 200:
            try:
                lst = r.json()
            except ValueError:
                lst = []
            print(f"sen {cod}: {len(lst)} processos")
            if lst:
                print("   chaves:", list(lst[0].keys()))
                for x in lst[:3]:
                    print("   ", json.dumps(x, ensure_ascii=False)[:600])
                print("   tipos:", collections.Counter(x.get("sigla") or x.get("siglaTipoMateria") for x in lst).most_common(10))
                print("   autoria (início):", collections.Counter((x.get("autoria") or "")[:40] for x in lst).most_common(5))
        r = get(f"{L}/senador/{cod}/autorias.json?ano={ANO}", headers=h)
        if r is not None and r.status_code == 200:
            print("   legado autorias:", r.text[:1500])


if __name__ == "__main__":
    for f in (camara, senado):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            print("FALHOU", f.__name__, repr(e))
