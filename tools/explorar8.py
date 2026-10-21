"""Por que, em 2023, algumas notas da Câmara somam mais que a página oficial? E os totais negativos de 2024?"""
import sys, zipfile, io, csv, glob
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, "etl")
from sa_etl.util import to_float, read_csv_file, download
from sa_etl.recursos import parse_camara_resumo, _get_text, CAMARA
print(glob.glob("etl/.cache/camara-cota-*"))
for ano, nomes in ((2023, ["VICENTINHO JÚNIOR", "ZECA DIRCEU", "AMARO NETO"]), (2024, ["CARLOS GOMES", "ANDRÉ FUFUCA"])):
    f = download(f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", Path(f"etl/.cache/camara-cota-{ano}.csv.zip"))
    rows = list(read_csv_file(f))
    print("\n=====", ano, "colunas", list(rows[0].keys()))
    sem_ide = [r for r in rows if not (r.get("ideCadastro") or "").strip()]
    print("linhas sem ideCadastro:", len(sem_ide), "exemplos de nome:", sorted({r.get("txNomeParlamentar") for r in sem_ide})[:10])
    print("nuDeputadoId exemplos:", sorted({r.get("nuDeputadoId") for r in rows})[:5], "ideCadastro exemplos:", sorted({r.get("ideCadastro") for r in rows if r.get("ideCadastro")})[:5])
    for nome in nomes:
        mine = [r for r in rows if (r.get("txNomeParlamentar") or "").upper() == nome]
        if not mine:
            print("sem linhas para", nome); continue
        ide = {r.get("ideCadastro") for r in mine}
        print("\n--", nome, "ideCadastro", ide, "nuDeputadoId", {r.get("nuDeputadoId") for r in mine}, "legislaturas", {r.get("codLegislatura") for r in mine})
        por = defaultdict(float); por_leg = defaultdict(float); tipos = defaultdict(float)
        for r in mine:
            v = to_float(r.get("vlrLiquido"))
            por[int(to_float(r.get("numMes")))] += v
            por_leg[r.get("codLegislatura")] += v
            tipos[r.get("indTipoDocumento")] += v
        print("  por mês (CSV):", {k: round(v, 2) for k, v in sorted(por.items())}, "total", round(sum(por.values()), 2))
        print("  por legislatura:", {k: round(v, 2) for k, v in por_leg.items()}, "por tipo doc:", {k: round(v, 2) for k, v in tipos.items()})
        neg = [r for r in mine if to_float(r.get("vlrLiquido")) < 0]
        for r in neg[:8]:
            print("  NEG", {k: r.get(k) for k in ("numMes", "txtDescricao", "txtFornecedor", "vlrDocumento", "vlrGlosa", "vlrLiquido", "vlrRestituicao", "indTipoDocumento", "numRessarcimento")})
        for i in ide:
            h = _get_text(CAMARA.format(id=i, sub="", ano=ano))
            if h:
                o = parse_camara_resumo(h)
                print("  OFICIAL", i, o.get("cota_oficial"), {m["mes"]: m["valor"] for m in o.get("cota_meses", [])})
