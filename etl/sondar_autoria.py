"""Sonda temporária 2: nomes dos tipos e autor principal no Senado."""
import collections, csv, io, json, re, time, unicodedata
import requests
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (segredos-abertos; sonda)"

def get(url, **kw):
    t = time.time()
    try:
        r = S.get(url, timeout=180, **kw); print(f"GET {url} -> {r.status_code} {len(r.content)}B {time.time()-t:.1f}s", flush=True); return r
    except Exception as e:
        print("ERRO", url, repr(e), flush=True)

def norm(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()

def camara():
    r = get("https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-2025.csv")
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", "replace")), delimiter=";"))
    c = collections.Counter((x["siglaTipo"], x["descricaoTipo"]) for x in rows)
    for (s, d), n in c.most_common(70):
        print(f"  {s:8} {n:6}  {d}")
    print("ano:", collections.Counter(x["ano"] for x in rows).most_common(6))
    print("ano apresentação:", collections.Counter(x["dataApresentacao"][:4] for x in rows).most_common(6))
    for s in ("PL", "PEC", "PLP", "PDL", "REQ", "RIC"):
        ex = [x for x in rows if x["siglaTipo"] == s][:1]
        for x in ex:
            print(" exemplo", s, x["numero"], x["ano"], x["dataApresentacao"], x["ementa"][:100])
    for s in ("RPD", "PRL", "INC", "RDF", "DOC", "SBT", "EMC", "EMP", "DTQ"):
        ex = [x for x in rows if x["siglaTipo"] == s][:2]
        for x in ex:
            print(" exemplo", s, x["ementa"][:140])
    r = get("https://dadosabertos.camara.leg.br/api/v2/deputados?itens=5&ordem=ASC&ordenarPor=nome")
    print("dep api:", r.text[:300] if r is not None else None)

def senado():
    L = "https://legis.senado.leg.br/dadosabertos"; h = {"Accept": "application/json"}
    nomes = {"5894": "Flávio Bolsonaro", "5012": "Randolfe Rodrigues", "5953": "Fabiano Contarato", "6331": "", "5718": "", "4639": ""}
    lst = get(f"{L}/senador/lista/atual.json", headers=h)
    try:
        ps = lst.json()["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
        for p in ps[:80:9]:
            i = p["IdentificacaoParlamentar"]; nomes[i["CodigoParlamentar"]] = i["NomeParlamentar"]
    except Exception as e:
        print("lista erro", e)
    for cod, nome in nomes.items():
        if not nome:
            continue
        r = get(f"{L}/processo?codigoParlamentarAutor={cod}&ano=2025", headers=h)
        novos = r.json() if r is not None and r.status_code == 200 else []
        tipos = collections.Counter(x.get("identificacao", "").split(" ")[0] for x in novos)
        def primeiro(a):
            seg = re.split(r"\)\s*,\s*", a or "")[0]
            return norm(nome) in norm(seg)
        princ_novo = {x.get("codigoMateria") for x in novos if primeiro(x.get("autoria"))}
        r = get(f"{L}/senador/{cod}/autorias.json?ano=2025", headers=h)
        leg = []
        try:
            a = r.json()["MateriasAutoriaParlamentar"]["Parlamentar"].get("Autorias", {}).get("Autoria", [])
            leg = a if isinstance(a, list) else [a]
        except Exception as e:
            print("legado erro", e)
        princ_leg = {int(x["Materia"]["Codigo"]) for x in leg if x.get("IndicadorAutorPrincipal") == "Sim"}
        todos_leg = {int(x["Materia"]["Codigo"]) for x in leg}
        todos_novo = {x.get("codigoMateria") for x in novos}
        print(f"sen {cod} {nome}: novo={len(novos)} princ_novo={len(princ_novo)} | legado={len(leg)} princ_leg={len(princ_leg)} | só novo={len(todos_novo - todos_leg)} só legado={len(todos_leg - todos_novo)} princ diferente={len(princ_novo ^ princ_leg)}")
        print("   tipos:", tipos.most_common(12))
        dif = list(princ_novo ^ princ_leg)[:3]
        for d in dif:
            x = next((y for y in novos if y.get("codigoMateria") == d), None)
            print("   dif:", d, d in princ_leg, (x or {}).get("identificacao"), ((x or {}).get("autoria") or "")[:120])

for f in (camara, senado):
    try:
        f()
    except Exception as e:
        print("FALHOU", f.__name__, repr(e))
