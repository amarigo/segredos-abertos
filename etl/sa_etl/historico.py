"""Histórico da cota parlamentar desde 2008: quanto a Câmara e o Senado gastaram por ano, e quanto cada parlamentar
gastou em cada ano em que teve mandato.

A coleta principal (build.py) lê as notas uma a uma só dos anos recentes. Aqui lemos todos os anos desde 2008, mas
guardamos só as somas: por Casa, por mês, por tipo de despesa e por parlamentar.

Fontes (as mesmas da coleta principal):
- Câmara: arquivo anual da cota, https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip. A API (/deputados/{id}/despesas)
  dá um deputado por vez, 100 notas por página: seriam centenas de milhares de pedidos para 18 anos. O arquivo é a
  mesma publicação, um por ano.
- Senado: API administrativa, https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}.
- Inflação: IPCA pela API SIDRA do IBGE (tabela 1737), para mostrar os anos antigos em reais de hoje.

O resumo de cada ano fica no cache (historico/{casa}-{ano}.json). O arquivo baixado é apagado depois de somado.
Anos fechados mudam pouco (nota lançada com atraso): somamos de novo a cada 30 dias. O ano atual e o anterior, a
cada 20 horas, como na coleta principal.

Grava data/historico.json (totais por ano) e data/h/{id}.json (cada parlamentar, ano a ano).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from . import camara, senado
from .categorias import categoria_curta
from .util import avisar, com_copia, download, eh_zip, get_json, id_seguro, read_csv_file, to_float, write_json

log = logging.getLogger("sa_etl.historico")

INICIO = 2008  # primeiro ano dos arquivos da cota da Câmara e da API do Senado
DIAS_ANO_FECHADO = 30
URL_IPCA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/{de}-{ate}"
PAGINA_IPCA = "https://sidra.ibge.gov.br/tabela/1737"
FONTES = {
    "camara": "https://www.camara.leg.br/transparencia/gastos-parlamentares",
    "camara_arquivo": camara.COTA_URL,
    "senado": "https://www12.senado.leg.br/transparencia/sen/",
    "senado_api": senado.CEAPS,
    "ipca": PAGINA_IPCA,
}


def anos(hoje: dt.date | None = None) -> list[int]:
    hoje = hoje or dt.date.today()
    return list(range(INICIO, hoje.year + 1))


def _validade_horas(ano: int, hoje: dt.date | None = None) -> float:
    hoje = hoje or dt.date.today()
    return 20 if ano >= hoje.year - 1 else DIAS_ANO_FECHADO * 24


def _categoria(bruto: str | None) -> str:
    """O nome do tipo de despesa muda pouco de um ano para outro ("Divulgação da atividade parlamentar." com ponto,
    espaços dobrados): tiramos essas diferenças para o mesmo tipo somar junto em todos os anos."""
    return re.sub(r"\s+", " ", categoria_curta(bruto or "Não informado")).strip().rstrip(" .") or "Não informado"


def _novo() -> dict:
    return {"total": 0.0, "notas": 0, "meses": defaultdict(float), "categorias": defaultdict(float), "pessoas": {}}


def _pessoa(r: dict, i: str) -> dict:
    return r["pessoas"].setdefault(i, {"nome": "", "uf": "", "partido": "", "total": 0.0, "meses": set(),
                                       "por_mes": defaultdict(float), "sem_data": defaultdict(float),
                                       "cat": defaultdict(float)})


def _fechar(r: dict, ano: int, casa: str) -> dict:
    """Arredonda e transforma os defaultdicts em dicts comuns (para gravar em JSON)."""
    pessoas = {}
    for i, p in r["pessoas"].items():
        pessoas[i] = {**p, "total": round(p["total"], 2), "meses": sorted(p["meses"]),
                      "por_mes": {str(m): round(v, 2) for m, v in sorted(p["por_mes"].items())},
                      "sem_data": {str(m): round(v, 2) for m, v in sorted(p["sem_data"].items()) if abs(v) > 0.005},
                      "cat": {c: round(v, 2) for c, v in p["cat"].items()}}
    return {
        "ano": ano, "casa": casa, "total": round(r["total"], 2), "notas": r["notas"],
        "meses": {str(m): round(v, 2) for m, v in sorted(r["meses"].items())},
        "categorias": {c: round(v, 2) for c, v in sorted(r["categorias"].items(), key=lambda x: -x[1])},
        "fora_parlamentares": round(r.get("fora", 0.0), 2),
        "pessoas": pessoas,
    }


def resumir_camara(linhas, ano: int) -> dict:
    """Somas de um ano do arquivo da cota da Câmara.

    Linhas sem ideCadastro são notas das lideranças dos partidos (LIDERANÇA DO PT...) e de alguns deputados antigos
    sem o código: entram no total da Casa, mas não na conta de nenhum deputado ("fora_parlamentares")."""
    r = _novo()
    r["fora"] = 0.0
    for ln in linhas:
        try:
            if int(to_float(ln.get("numAno"))) != ano:
                continue
        except (TypeError, ValueError):
            continue
        v = camara.valor_da_nota(ln)
        if v == 0:
            continue
        mes = int(to_float(ln.get("numMes")))
        r["total"] += v
        r["notas"] += 1
        r["meses"][mes] += v
        cat = _categoria(ln.get("txtDescricao"))
        r["categorias"][cat] += v
        ide = (ln.get("ideCadastro") or "").strip()
        if not ide.isdigit():
            r["fora"] += v
            continue
        p = _pessoa(r, camara.pid(ide))
        p["total"] += v
        p["cat"][cat] += v
        if 1 <= mes <= 12:
            p["meses"].add(mes)
            p["por_mes"][mes] += v
            if not (ln.get("datEmissao") or "").strip():
                # notas sem data (telefonia paga pela Câmara, complementação do auxílio-moradia): a API de despesas
                # não as lista (build.nao_esta_na_api); a verificação tira esta parte da comparação
                p["sem_data"][mes] += v
        # nome, estado e partido da última nota do ano (quem trocou de partido aparece com o mais recente)
        p["nome"] = (ln.get("txNomeParlamentar") or p["nome"]).strip()
        p["uf"] = (ln.get("sgUF") or p["uf"]).strip()
        p["partido"] = (ln.get("sgPartido") or p["partido"]).strip()
    return _fechar(r, ano, "camara")


def resumir_senado(linhas: list[dict], ano: int) -> dict:
    """Somas de um ano da API da cota do Senado (CEAPS)."""
    r = _novo()
    r["fora"] = 0.0
    for ln in linhas:
        if int(to_float(ln.get("ano")) or ano) != ano:
            continue
        v = to_float(ln.get("valorReembolsado"))
        if v == 0:
            continue
        mes = int(to_float(ln.get("mes")))
        r["total"] += v
        r["notas"] += 1
        r["meses"][mes] += v
        cat = _categoria(ln.get("tipoDespesa"))
        r["categorias"][cat] += v
        cod = str(ln.get("codSenador") or "").strip()
        if not cod.isdigit():
            r["fora"] += v
            continue
        p = _pessoa(r, senado.pid(cod))
        p["total"] += v
        p["cat"][cat] += v
        if 1 <= mes <= 12:
            p["meses"].add(mes)
            p["por_mes"][mes] += v
        p["nome"] = (ln.get("nomeSenador") or p["nome"]).strip()
    return _fechar(r, ano, "senado")


def _ano_camara(ano: int, cache: Path) -> dict:
    # O arquivo que a coleta principal já baixou nesta execução serve; senão baixa numa pasta temporária e apaga.
    principal = cache / f"camara-cota-{ano}.csv.zip"
    if principal.exists() and principal.stat().st_size > 0 and \
            (dt.datetime.now().timestamp() - principal.stat().st_mtime) / 3600 < 20:
        return resumir_camara(read_csv_file(principal), ano)
    with tempfile.TemporaryDirectory() as tmp:
        f = download(camara.COTA_URL.format(ano=ano), Path(tmp) / f"camara-cota-{ano}.csv.zip", validar=eh_zip)
        return resumir_camara(read_csv_file(f), ano)


def _ano_senado(ano: int) -> dict:
    linhas = get_json(senado.CEAPS.format(ano=ano), timeout=300)
    if not isinstance(linhas, list):
        raise ValueError(f"resposta inesperada da API do Senado ({type(linhas).__name__})")
    return resumir_senado(linhas, ano)


def coletar_anos(cache: Path, hoje: dt.date | None = None, lista: list[int] | None = None) -> list[dict]:
    """Resumo de cada Casa em cada ano. Ano que falha sem cópia guardada fica de fora, com aviso."""
    pasta = cache / "historico"
    out = []
    for ano in lista or anos(hoje):
        for casa, buscar in (("camara", lambda a=ano: _ano_camara(a, cache)), ("senado", lambda a=ano: _ano_senado(a))):
            nome = "Câmara" if casa == "camara" else "Senado"
            try:
                r = com_copia(pasta / f"{casa}-{ano}.json", buscar, f"Histórico da cota do {nome} em {ano}",
                              max_horas=_validade_horas(ano, hoje))
            except Exception as e:  # noqa: BLE001 - um ano faltando não para os outros
                log.warning("Histórico: %s %s indisponível (%s)", casa, ano, e)
                avisar(f"Histórico da cota: {nome} em {ano} não pôde ser lido na fonte oficial; o ano ficou de fora")
                continue
            if r.get("total"):
                out.append(r)
    return out


def usar_numeros_do_site(resumos: list[dict], saida: Path) -> int:
    """Nos anos da coleta principal, cada deputado fica com o número do perfil dele no site (p/{id}.json).

    Desde agosto de 2025 o arquivo anual da Câmara não traz as passagens compradas pelo sistema da própria Câmara
    (oficial.MOTIVOS["camara_sigepa"]). A coleta principal busca cada bilhete na lista oficial e completa o mês com a
    página oficial do deputado; só o arquivo anual daria um número menor que o do perfil. Conferido em 10/11/2026 com
    a página oficial: 22 meses de 2025 e 2026 com o arquivo abaixo da página, todos de agosto de 2025 em diante.
    O Senado fica como está: a API do Senado é a mesma fonte do perfil. Devolve quantos deputados-ano mudaram."""
    mudou = 0
    for r in resumos:
        if r["casa"] != "camara":
            continue
        ano = str(r["ano"])
        for f in sorted((saida / "p").glob("dep-*.json")) if (saida / "p").exists() else []:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            a = (d.get("anos") or {}).get(ano)
            if not a or not a.get("meses"):
                continue
            p = r["pessoas"].setdefault(f.stem, {"nome": d.get("nome", ""), "uf": d.get("uf", ""), "partido": d.get("partido", ""),
                                                 "total": 0.0, "meses": [], "por_mes": {}, "sem_data": {}, "cat": {}})
            novo_mes = {str(m["mes"]): round(m["valor"], 2) for m in a["meses"]}
            novo_cat: dict[str, float] = defaultdict(float)
            for c in a.get("categorias") or []:
                novo_cat[_categoria(c["categoria"])] += c["valor"]
            for m in set(novo_mes) | set(p["por_mes"]):
                r["meses"][m] = round(r["meses"].get(m, 0.0) + novo_mes.get(m, 0.0) - p["por_mes"].get(m, 0.0), 2)
            for c in set(novo_cat) | set(p.get("cat") or {}):
                v = r["categorias"].get(c, 0.0) + novo_cat.get(c, 0.0) - (p.get("cat") or {}).get(c, 0.0)
                if abs(v) > 0.005:
                    r["categorias"][c] = round(v, 2)
                else:
                    r["categorias"].pop(c, None)
            total = round(sum(novo_mes.values()), 2)
            if abs(total - p["total"]) > 0.005:
                mudou += 1
            r["total"] = round(r["total"] + total - p["total"], 2)
            p.update({"total": total, "por_mes": novo_mes, "cat": novo_cat,
                      "meses": sorted(int(m) for m, v in novo_mes.items() if v),
                      "sem_data": {str(m["mes"]): m["fora_api"] for m in a["meses"] if m.get("fora_api")},
                      "do_site": True})
    if mudou:
        log.info("Histórico: %d deputados-ano com o número do perfil (passagens e meses completados)", mudou)
    return mudou


def ipca(hoje: dt.date | None = None) -> dict[str, float]:
    """Número-índice do IPCA por mês ('AAAAMM' -> índice), desde dezembro do ano anterior ao primeiro."""
    hoje = hoje or dt.date.today()
    try:
        dados = get_json(URL_IPCA.format(de=f"{INICIO - 1}12", ate=f"{hoje.year}12"), timeout=120)
    except Exception as e:  # noqa: BLE001
        log.warning("IPCA indisponível (%s); o histórico sai só em valores da época", e)
        avisar("Histórico da cota: a API do IPCA (IBGE) não respondeu; os valores corrigidos pela inflação ficaram de fora")
        return {}
    out = {}
    for d in dados[1:] if isinstance(dados, list) else []:
        try:
            out[str(d["D3C"])] = float(d["V"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def corrigido(meses: dict[str, float], ano: int, idx: dict[str, float]) -> tuple[float | None, str]:
    """Soma dos meses do ano, cada mês levado ao último mês com IPCA publicado. Sem índice de algum mês, None."""
    if not idx:
        return None, ""
    ultimo = max(idx)
    base = idx[ultimo]
    soma = 0.0
    for m, v in meses.items():
        mi = idx.get(f"{ano}{int(m):02d}")
        if not mi:
            return None, ultimo
        soma += v * base / mi
    return round(soma, 2), ultimo


def meses_fracos(meses: dict[str, float]) -> list[int]:
    """Meses com menos de um quarto do mês típico (mediana) do ano: poucas notas no arquivo oficial. Em 2008 e no começo
    de 2009 a Câmara tem bem menos notas que nos anos seguintes; a página avisa em vez de comparar como se fosse igual."""
    vals = sorted(v for v in meses.values() if v > 0)
    if len(vals) < 3:
        return sorted(int(m) for m in meses)
    med = vals[len(vals) // 2]
    return sorted(int(m) for m, v in meses.items() if v < med / 4)


def montar(resumos: list[dict], idx: dict[str, float], saida: Path, hoje: dt.date | None = None) -> dict:
    """Grava historico.json e h/{id}.json. Devolve o conteúdo de historico.json."""
    hoje = hoje or dt.date.today()
    linhas = []
    pessoas: dict[str, dict] = {}
    base_ipca = ""
    for r in sorted(resumos, key=lambda x: (x["ano"], x["casa"])):
        real, base_ipca = corrigido(r["meses"], r["ano"], idx)
        n = len(r["pessoas"])
        linhas.append({
            "ano": r["ano"], "casa": r["casa"], "total": r["total"], "total_hoje": real, "notas": r["notas"],
            "parlamentares": n, "por_parlamentar": round((r["total"] - r["fora_parlamentares"]) / n, 2) if n else 0,
            "meses": sorted(int(m) for m in r["meses"]), "meses_fracos": meses_fracos(r["meses"]),
            "fora_parlamentares": r["fora_parlamentares"],
            "categorias": r["categorias"],
        })
        fator = (real / r["total"]) if real and r["total"] else None
        for i, p in r["pessoas"].items():
            if not id_seguro(i):
                continue
            x = pessoas.setdefault(i, {"id": i, "casa": r["casa"], "nome": p["nome"], "anos": {}})
            x["nome"] = p["nome"] or x["nome"]
            x["anos"][str(r["ano"])] = {"total": p["total"], "meses": len(p["meses"]), "uf": p["uf"],
                                        "partido": p["partido"], "por_mes": p.get("por_mes") or {},
                                        **({"sem_data": p["sem_data"]} if p.get("sem_data") else {}),
                                        **({"do_site": True} if p.get("do_site") else {}),
                                        # correção aproximada: o fator do ano inteiro da Casa
                                        **({"total_hoje": round(p["total"] * fator, 2)} if fator else {})}
    for casa in ("camara", "senado"):
        # ano com bem menos gasto por parlamentar que o normal da Casa (2008 na Câmara): poucas notas no arquivo oficial
        vals = sorted(x["por_parlamentar"] for x in linhas if x["casa"] == casa and x["por_parlamentar"] > 0)
        med = vals[len(vals) // 2] if vals else 0
        for x in linhas:
            if x["casa"] == casa and med and x["por_parlamentar"] < med / 4:
                x["poucas_notas"] = True
    for i, x in pessoas.items():
        tot = sum(a["total"] for a in x["anos"].values())
        write_json(saida / "h" / f"{i}.json", {**x, "total": round(tot, 2), "fontes": FONTES,
                                                "atualizado": hoje.isoformat()})
    out = {
        "atualizado": hoje.isoformat(), "inicio": INICIO, "ipca_base": base_ipca, "fontes": FONTES,
        "anos": linhas,
        "maiores": _maiores(pessoas),
    }
    write_json(saida / "historico.json", out)
    log.info("Histórico da cota: %d anos-Casa, %d parlamentares", len(linhas), len(pessoas))
    return out


def _maiores(pessoas: dict[str, dict], n: int = 30) -> dict:
    """Quem mais gastou na soma de todos os anos, em cada Casa (em reais de hoje quando houver IPCA)."""
    out = {}
    for casa in ("camara", "senado"):
        lista = []
        for x in pessoas.values():
            if x["casa"] != casa:
                continue
            nom = sum(a["total"] for a in x["anos"].values())
            hoje = [a.get("total_hoje") for a in x["anos"].values()]
            ult = x["anos"][max(x["anos"])]
            lista.append({"id": x["id"], "nome": x["nome"], "uf": ult["uf"], "partido": ult["partido"],
                          "anos": len(x["anos"]), "de": int(min(x["anos"])), "ate": int(max(x["anos"])),
                          "total": round(nom, 2),
                          "total_hoje": round(sum(hoje), 2) if all(v is not None for v in hoje) else None})
        lista.sort(key=lambda y: -(y["total_hoje"] or y["total"]))
        out[casa] = lista[:n]
    return out


def coletar(saida: Path, cache: Path, hoje: dt.date | None = None, anos: list[int] | None = None) -> dict | None:
    """anos: só nos testes (o governo simulado tem poucos anos); na coleta de verdade, de 2008 até hoje."""
    resumos = coletar_anos(cache, hoje, anos)
    if not resumos:
        avisar("Histórico da cota: nenhum ano pôde ser lido; a página ficou de fora desta atualização")
        return None
    usar_numeros_do_site(resumos, saida)
    return montar(resumos, ipca(hoje), saida, hoje)
