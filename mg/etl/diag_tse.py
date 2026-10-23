"""Diagnóstico temporário: o que o cache do TSE tem para os casos suspeitos (vereadores de Itajubá em 2004,
vices de 1996 e 2000). Uso: python mg/etl/diag_tse.py mg/etl/.cache"""
import json
import sys
from collections import Counter
from pathlib import Path


def main(cache: Path) -> None:
    def ler(nome):
        f = cache / "tse" / nome
        if not f.exists():
            print(f"(sem {nome})")
            return []
        return json.loads(f.read_text(encoding="utf-8"))["linhas"]

    print("### Diagnóstico TSE")
    for ano in (2000, 2004, 2008):
        rows = [r for r in ler(f"votacao_{ano}_MG.json") if "ITAJUB" in (r.get("NM_MUNICIPIO") or r.get("NM_UE") or "").upper()
                and (r.get("DS_CARGO") or "").upper() == "VEREADOR"]
        print(f"\n{ano} Itajubá vereador: {len(rows)} linhas; situações {Counter(r.get('DS_SIT_TOT_TURNO') for r in rows)}")
        print(f"  tipos {Counter((r.get('CD_TIPO_ELEICAO'), r.get('NM_TIPO_ELEICAO')) for r in rows)}; turnos {Counter(r.get('NR_TURNO') for r in rows)}")
        el = [r for r in rows if (r.get("DS_SIT_TOT_TURNO") or "").upper().startswith("ELEITO") or (r.get("DS_SIT_TOT_TURNO") or "").upper() in ("MÉDIA", "MEDIA")]
        for r in sorted(el, key=lambda r: r.get("NM_URNA_CANDIDATO") or ""):
            print(f"  {r.get('SQ_CANDIDATO')} {r.get('NR_CANDIDATO')} {r.get('NM_URNA_CANDIDATO')} {r.get('SG_PARTIDO')} "
                  f"{r.get('DS_SIT_TOT_TURNO')} votos={r.get('QT_VOTOS_NOMINAIS')} mun={r.get('NM_MUNICIPIO')} ue={r.get('NM_UE')}")
    for ano in (1996, 2000, 2004):
        rows = ler(f"cand_{ano}_MG.json")
        print(f"\ncand {ano}: {len(rows)} linhas; cargos {Counter(r.get('DS_CARGO') for r in rows)}")
        print(f"  colunas {sorted(rows[0]) if rows else []}")
        for r in rows:
            c = (r.get("DS_CARGO") or "").upper()
            if "PREFEITO" in c:
                print(f"  {r.get('NM_MUNICIPIO') or r.get('NM_UE')} | {c} | nr={r.get('NR_CANDIDATO')!r} | {r.get('NM_URNA_CANDIDATO')} | "
                      f"{r.get('SG_PARTIDO')} | {r.get('DS_SITUACAO_CANDIDATURA')} | {r.get('DS_DETALHE_SITUACAO_CAND')} | tipo={r.get('CD_TIPO_ELEICAO')} {r.get('NM_TIPO_ELEICAO')}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
