"""Confere os dados do Minas Nossa antes de publicar.

Primeiro passa tudo pela mesma conferência do nacional (sa_etl.validar): somas, votos repetidos, CPF exposto,
links que não são http(s), nomes de arquivo, queda brusca. Depois confere o que é só de MG:

- todos os políticos são de MG, e o placar da Casa inteira nunca é menor que o da bancada de MG;
- estado: deputados estaduais (cada um com o seu arquivo, verba somando por tipo e por mês, aprovados nunca mais
  que apresentados), emendas estaduais, governador eleito, salários sem valor negativo, e o dinheiro de cada cidade
  (contas somando por área, CNPJ com 14 dígitos). Nenhum número com cara de CPF em nenhum texto;
- cidades: cada eleição aparece uma vez, um prefeito por eleição, mandato de 4 anos, percentuais entre 0 e
  100 e somando 100 em cada turno; na Câmara, a soma das cadeiras por partido é igual ao número de vagas e ao
  número de eleitos; o resumo bate com a lista de mandatos.

Erros bloqueiam a publicação: o site de MG continua com a versão anterior.

Uso:
    PYTHONPATH=../../etl python -m mg_etl.validar ../../site/public-mg/data [--anterior URL do meta.json publicado]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from sa_etl import validar as nacional
from sa_etl.validar import Resultado, _baixar_anterior, _ler, _perto

# Valores de produção. MG tem 53 deputados federais e 3 senadores; os testes usam números menores.
MINIMOS = {"camara": 40, "senado": 3, "votacoes": 50, "mandatos": 6}
ID_SEGURO = re.compile(r"^[a-z0-9-]+$")
CPF_EM_TEXTO = re.compile(r"(?<!\d)(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})(?!\d)")


def _textos(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _textos(v)
    elif isinstance(x, list):
        for v in x:
            yield from _textos(v)
    elif isinstance(x, str):
        yield x


def validar(saida: Path, minimos: dict | None = None, anterior: dict | None = None, ignorar_queda: bool = False) -> Resultado:
    minimos = {**MINIMOS, **(minimos or {})}
    r = nacional.validar(saida, minimos={k: minimos[k] for k in ("camara", "senado", "votacoes")},
                         anterior=anterior, ignorar_queda=ignorar_queda)
    pols = _ler(saida / "politicos.json", r) or []
    fora = [p["id"] for p in pols if p.get("uf") != "MG"]
    if fora:
        r.erro(f"Políticos de fora de MG no recorte: {fora[:5]}")
    for v in _ler(saida / "votacoes.json", r) or []:
        casa = v.get("placar_casa")
        if not casa:
            r.erro(f"Votação {v['id']}: sem o placar da Casa inteira")
        elif casa["sim"] < v["sim"] or casa["nao"] < v["nao"]:
            r.erro(f"Votação {v['id']}: placar da Casa menor que o da bancada de MG")
    conferir_cidades(saida, r, minimos["mandatos"])
    conferir_estado(saida, r)
    return r


def _sem_cpf(x, onde: str, r: Resultado) -> None:
    for s in _textos(x):
        if CPF_EM_TEXTO.search(s):
            r.erro(f"{onde}: número com cara de CPF ({s[:40]!r}...)")
            return


def _cnpjs(x, onde: str, r: Resultado) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "cnpj" and v not in ("", None) and not (isinstance(v, str) and re.fullmatch(r"\d{14}", v)):
                r.erro(f"{onde}: CNPJ inválido ({str(v)[:20]!r}); CPF nunca pode estar nesse campo")
            else:
                _cnpjs(v, onde, r)
    elif isinstance(x, list):
        for v in x:
            _cnpjs(v, onde, r)


def conferir_estado(saida: Path, r: Resultado) -> None:
    """Deputados estaduais, emendas estaduais, governo e dinheiro das cidades. Cada parte é opcional (a fonte pode
    ter falhado e o site diz isso), mas o que existe tem de estar certo."""
    idx_f = saida / "almg" / "deputados.json"
    if idx_f.exists():
        idx = _ler(idx_f, r) or {}
        ids = Counter(d["id"] for d in idx.get("deputados", []))
        for i, n in ids.items():
            if n > 1:
                r.erro(f"Deputado estadual repetido: {i}")
            if not re.fullmatch(r"\d+", str(i)):
                r.erro(f"Identificador de deputado estadual inseguro: {i!r}")
                continue
            d = _ler(saida / "almg" / "d" / f"{i}.json", r)
            if d is None:
                continue
            onde = f"Deputado estadual {d.get('nome', i)}"
            _sem_cpf(d, onde, r)
            _cnpjs(d, onde, r)
            for ano, a in (d.get("anos") or {}).items():
                v, pr = a.get("verba"), a.get("proposicoes")
                if v:
                    if not _perto(sum(x["valor"] for x in v["tipos"]), v["total"], len(v["tipos"])):
                        r.erro(f"{onde} {ano}: verba por tipo não soma o total")
                    if not _perto(sum(x["valor"] for x in v["meses"]), v["total"], len(v["meses"])):
                        r.erro(f"{onde} {ano}: verba por mês não soma o total")
                    if any(x["valor"] < 0 for x in v["notas"]):
                        r.erro(f"{onde} {ano}: nota com valor negativo")
                if pr and pr["aprovadas"] > pr["projetos"]:
                    r.erro(f"{onde} {ano}: mais projetos aprovados que apresentados")
                if d.get("por_ano", {}).get(ano, {}).get("verba", 0) != (v or {}).get("total", 0):
                    r.erro(f"{onde} {ano}: verba do resumo diferente da página")
    em_f = saida / "estado" / "emendas.json"
    if em_f.exists():
        em = _ler(em_f, r) or {}
        _sem_cpf(em, "Emendas estaduais", r)
        for ano, e in (em.get("anos") or {}).items():
            if e["indicado"] < 0 or e["pago"] < 0:
                r.erro(f"Emendas estaduais {ano}: valor negativo")
            if sum(a["indicado"] for a in e["autores"]) > e["indicado"] + 1:
                r.erro(f"Emendas estaduais {ano}: soma por deputado maior que o total")
            if e["pago"] > e["indicado"] * 1.5 + 1:
                r.alerta(f"Emendas estaduais {ano}: pago bem maior que o indicado")
    gov_f = saida / "estado" / "governo.json"
    if gov_f.exists():
        gov = _ler(gov_f, r) or {}
        _sem_cpf(gov, "Governo", r)
        for e in gov.get("eleicoes") or []:
            eleitos = [c for c in e["candidatos"] if c["eleito"]]
            if len(eleitos) != 1 or eleitos[0]["nome"] != e["governador"]["nome"]:
                r.erro(f"Governo {e['eleicao']}: deveria haver um eleito, o próprio governador")
            _pcts(e["candidatos"], f"Governo {e['eleicao']}", r)
        for p in ((gov.get("equipe") or {}).get("pessoas") or []):
            if any((p.get(k) or 0) < 0 for k in ("bruto", "liquido", "jetons")):
                r.erro(f"Governo: salário negativo ({p['nome']})")
    for c in _ler(saida / "cidades.json", r) or []:
        if not ID_SEGURO.match(c["id"]):
            continue
        f = saida / "cidades" / "dinheiro" / f"{c['id']}.json"
        if not f.exists():
            continue
        d = _ler(f, r) or {}
        onde = f"Dinheiro de {d.get('nome', c['id'])}"
        _sem_cpf(d, onde, r)
        _cnpjs(d, onde, r)
        for a in ((d.get("contas") or {}).get("anos") or []):
            if not _perto(sum(x["liquidado"] for x in a["funcoes"]), a["total_liquidado"], len(a["funcoes"])):
                r.erro(f"{onde} {a['ano']}: gasto por área não soma o total")
        fed = d.get("federais") or {}
        for x in fed.get("favorecidos") or []:
            if x.get("url") and not x["url"].startswith("https://portaldatransparencia.gov.br/"):
                r.erro(f"{onde}: link de favorecido fora do Portal da Transparência")
            if not x.get("cnpj") and x.get("nome") != "Pessoa física":
                r.erro(f"{onde}: favorecido sem CNPJ com nome (pessoa física não aparece com nome)")


def conferir_cidades(saida: Path, r: Resultado, min_mandatos: int) -> None:
    lista = _ler(saida / "cidades.json", r)
    if lista is None:
        return
    ids = Counter(c["id"] for c in lista)
    for i, n in ids.items():
        if n > 1:
            r.erro(f"Cidade repetida em cidades.json: {i}")
        if not ID_SEGURO.match(i):
            r.erro(f"Identificador de cidade inseguro: {i!r}")
    for c in lista:
        if not ID_SEGURO.match(c["id"]):
            continue
        d = _ler(saida / "cidades" / f"{c['id']}.json", r)
        if d is None:
            continue
        try:
            _conferir_cidade(d, r, min_mandatos)
        except (KeyError, TypeError, AttributeError) as e:
            r.erro(f"Cidade {c['id']}: arquivo em formato inesperado ({type(e).__name__}: {e})")


def _pcts(cs: list[dict], onde: str, r: Resultado) -> None:
    for x in cs:
        if x.get("pct") is not None and not 0 <= x["pct"] <= 100:
            r.erro(f"{onde}: percentual fora de 0 a 100 ({x['nome']}: {x['pct']})")
        if x["votos"] < 0:
            r.erro(f"{onde}: votos negativos ({x['nome']})")


def _conferir_cidade(d: dict, r: Resultado, min_mandatos: int) -> None:
    nome = d["nome"]
    # Os arquivos do TSE trazem CPF dos candidatos. Nenhum texto da página da cidade pode ter um.
    if any(CPF_EM_TEXTO.search(t) for t in _textos(d)):
        r.erro(f"{nome}: número com cara de CPF na página da cidade")
    exe, cam = d.get("executivo") or [], d.get("camara") or []
    if len(exe) < min_mandatos:
        r.erro(f"{nome}: só {len(exe)} mandatos de prefeito (mínimo {min_mandatos}); o TSE pode ter falhado")
    for rotulo, lista in (("prefeito", exe), ("Câmara", cam)):
        anos = [m["eleicao"] for m in lista]
        rep = [a for a, n in Counter(anos).items() if n > 1]
        if rep:
            r.erro(f"{nome}: eleição de {rotulo} repetida: {rep}")
        if anos != sorted(anos, reverse=True):
            r.erro(f"{nome}: eleições de {rotulo} fora de ordem (deveria ser da mais nova para a mais antiga)")
        for m in lista:
            if (m["inicio"], m["fim"]) != (m["eleicao"] + 1, m["eleicao"] + 4):
                r.erro(f"{nome} {m['eleicao']}: mandato de {rotulo} com datas erradas ({m['inicio']}-{m['fim']})")
    for m in exe:
        onde = f"{nome} {m['eleicao']} prefeito"
        _pcts(m["candidatos"], onde, r)
        ultimo = [x for x in m["candidatos"] if x["turno"] == m["turnos"]]
        eleitos = [x for x in ultimo if x["eleito"]]
        if len(eleitos) != 1 or eleitos[0]["nome"] != m["prefeito"]["nome"]:
            r.erro(f"{onde}: deveria haver um eleito, o próprio prefeito ({len(eleitos)} eleitos)")
        for t in {x["turno"] for x in m["candidatos"]}:
            soma = sum(x["pct"] or 0 for x in m["candidatos"] if x["turno"] == t)
            if not _perto(soma, 100, 50) and soma:
                r.erro(f"{onde}: percentuais do {t}º turno somam {soma:.2f}, não 100")
    for c in cam:
        onde = f"{nome} {c['eleicao']} Câmara"
        soma = sum(x["cadeiras"] for x in c["por_partido"])
        if not soma == c["vagas"] == len(c["eleitos"]):
            r.erro(f"{onde}: cadeiras por partido ({soma}), vagas ({c['vagas']}) e eleitos ({len(c['eleitos'])}) não batem")
        if not 0 <= c["do_partido_do_prefeito"] <= c["vagas"] or not 0 <= c["da_coligacao_do_prefeito"] <= c["vagas"]:
            r.erro(f"{onde}: cadeiras do partido ou da coligação do prefeito fora de 0 a {c['vagas']}")
        elif c["do_partido_do_prefeito"] > c["da_coligacao_do_prefeito"]:
            r.alerta(f"{onde}: o partido do prefeito não aparece na composição da coligação")
        rep = [k for k, n in Counter(x["partido"] for x in c["por_partido"]).items() if n > 1]
        if rep:
            r.erro(f"{onde}: partido repetido na composição: {rep}")
    for g in d.get("gerais") or []:
        for cargo in g["cargos"]:
            _pcts(cargo["candidatos"], f"{nome} {g['eleicao']} {cargo['cargo']}", r)
            if sum(x["votos"] for x in cargo["candidatos"]) > cargo["total_votos"]:
                r.erro(f"{nome} {g['eleicao']} {cargo['cargo']}: votos dos mais votados maiores que o total")
    res = d.get("resumo") or {}
    if res.get("mandatos") != len(exe) or res.get("camaras") != len(cam):
        r.erro(f"{nome}: resumo com número de mandatos diferente da lista")
    if sum(x["anos"] for x in res.get("anos_por_partido") or []) != sum(m["fim"] - m["inicio"] + 1 for m in exe):
        r.erro(f"{nome}: anos por partido não somam os anos de mandato")
    if sum(x["cadeiras"] for x in res.get("cadeiras_por_partido") or []) != sum(c["vagas"] for c in cam):
        r.erro(f"{nome}: cadeiras por partido no resumo não somam as vagas")
    for a in d.get("avisos") or []:
        r.alerta(f"{nome}: {a}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--anterior", default="", help="meta.json publicado antes (URL ou arquivo)")
    ap.add_argument("--ignorar-queda", action="store_true", help="queda grande vira alerta, não erro")
    a = ap.parse_args(argv)
    ant = _baixar_anterior(a.anterior)
    r = validar(a.saida, anterior=ant, ignorar_queda=a.ignorar_queda)
    print("## Conferência dos dados do Minas Nossa\n")
    if a.anterior and ant is None:
        r.alerta("Não foi possível ler a versão publicada antes; a comparação de quedas ficou de fora")
    print(f"- {len(r.erros)} erros, {len(r.alertas)} alertas\n")
    for e in r.erros[:60]:
        print(f"- ERRO: {e}")
    for x in r.alertas[:60]:
        print(f"- alerta: {x}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
