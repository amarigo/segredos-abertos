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

from .emendas import _chave, nome_autor
from .util import _session, avisar, digits, norm_name, to_float

log = logging.getLogger("sa_etl.pagamentos")

URL = "https://portaldatransparencia.gov.br/download-de-dados/despesas/{dia}"
DOC = "https://portaldatransparencia.gov.br/despesas/{fase}/{codigo}"
VERSAO = 1
SEM_AUTOR = {"", "SEM INFORMACAO", "SEM EMENDA", "NAO SE APLICA", "-1", "0", "-8"}


def url_documento(codigo: str) -> str:
    """Página oficial do documento no Portal (empenho, liquidação ou pagamento)."""
    m = re.search(r"\d{4}([A-Z]{2})\d+$", codigo or "")  # ...2025NE002378: o tipo vem depois do ano
    tipo = m.group(1) if m else ""
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


ULTIMA_FALHA = ""  # o motivo da última falha ao baixar um dia (vai para o aviso da coleta)


def _baixar_dia(dia: str, dest: Path) -> bool | None:
    """True: baixou. None: o Portal não tem arquivo para o dia (fim de semana, feriado). False: falhou."""
    for tentativa in range(3):
        try:
            r = _session.get(URL.format(dia=dia), timeout=300, stream=True, allow_redirects=True,
                             headers={"Accept": "application/zip,*/*"})
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}" + (f", {r.headers.get('server')[:40]}" if r.headers.get("server") else ""))
            with dest.open("wb") as f:
                for b in r.iter_content(1 << 20):
                    f.write(b)
            if zipfile.is_zipfile(dest):
                return True
            return None  # página de erro em vez de arquivo: o dia não existe
        except Exception as e:  # noqa: BLE001
            global ULTIMA_FALHA
            ULTIMA_FALHA = str(e)[:120]
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
    # um ano antes: muitos pagamentos quitam empenhos (reservas) feitos no ano anterior
    dia = dt.date(min(anos) - 1, 1, 1)
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
                _gravar_geral(cache, nome, tmp)  # o mesmo arquivo serve para os pagamentos a empresas (incentivos.py)
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


# ---------------------------------------------------------------- resumo

# Quem recebe e não é empresa nem entidade: prefeituras, governos, órgãos e bancos públicos
PUBLICO = re.compile(r"\b(MUNICIPIO|PREFEITURA|FUNDO (MUNICIPAL|ESTADUAL|NACIONAL)|SECRETARIA|ESTADO D[OEA]|GOVERNO|"
                     r"MINISTERIO|TRIBUNAL|CAMARA MUNICIPAL|ASSEMBLEIA|UNIVERSIDADE FEDERAL|INSTITUTO FEDERAL|"
                     r"CAIXA ECONOMICA|BANCO DO BRASIL|BANCO DO NORDESTE|BANCO DA AMAZONIA|COMANDO D[OA]|"
                     r"FUNDACAO OSWALDO CRUZ|INSTITUTO NACIONAL|SUPERINTENDENCIA|DEPARTAMENTO NACIONAL|POLICIA|EXERCITO|"
                     r"COMPANHIA DE DESENVOLVIMENTO DOS VALES|CODEVASF|DNIT|INCRA|FUNASA|EBSERH|HOSPITAL UNIVERSITARIO)\b")
N_DOCS = 60


def eh_publico(nome: str) -> bool:
    return bool(PUBLICO.search(norm_name(nome)))


def _ler(f: Path) -> dict:
    return json.loads(gzip.decompress(f.read_bytes()))


def resumir(arquivos: list[Path], anos: list[int]) -> dict:
    """Soma os pagamentos pelo ano em que foram feitos: quem pagou, a quem e por emenda de quem.

    Devolve {"ate": última data lida, "anos": {ano: {...}}}. Os empenhos são lidos numa segunda passada,
    só os que tiveram pagamento, para não guardar centenas de milhares na memória."""
    anos_set = set(anos)
    pagos: list[dict] = []
    usados: set[str] = set()
    ate = ""
    for f in sorted(arquivos):
        d = _ler(f)
        if d.get("empenhos") or d.get("pagamentos"):
            ate = max(ate, f.name[:8])
        for p in d.get("pagamentos", []):
            if p["data"][:4].isdigit() and int(p["data"][:4]) in anos_set:
                pagos.append(p)
                usados.update(e for e, _ in p["empenhos"])
    emp: dict[str, dict] = {}
    for f in sorted(arquivos):
        for e in _ler(f).get("empenhos", []):
            if e["codigo"] in usados:
                emp[e["codigo"]] = e

    nova_ano = lambda: {"total": 0.0, "n": 0, "orgaos": {}, "autores": {}, "favorecidos": {}}  # noqa: E731
    out: dict[int, dict] = {}
    for p in pagos:
        ano = int(p["data"][:4])
        a = out.setdefault(ano, nova_ano())
        doc = p["doc"] if len(p["doc"]) == 14 else ""  # CPF (mascarado) não vai para o site
        for cod_emp, valor in p["empenhos"]:
            e = emp.get(cod_emp)
            if not e:
                continue
            chave = _chave(e["autor"])
            item = {"data": p["data"], "pag": p["codigo"], "tipo": p["tipo"], "orgao": p["orgao_sup"] or e["orgao_sup"],
                    "ug": p["ug"] or e["ug"], "fav": p["favorecido"], "doc": doc, "valor": valor, "emp": cod_emp,
                    "emenda": e["emenda"], "desc": e["descricao"] or p["descricao"]}
            a["total"] += valor
            a["n"] += 1
            o = a["orgaos"].setdefault(item["orgao"] or "Não informado", {"valor": 0.0, "n": 0, "ugs": {}})
            o["valor"] += valor; o["n"] += 1
            o["ugs"][item["ug"]] = o["ugs"].get(item["ug"], 0.0) + valor
            au = a["autores"].setdefault(chave, {"nome": e["autor"], "valor": 0.0, "n": 0, "orgaos": {}, "docs": []})
            au["valor"] += valor; au["n"] += 1
            au["orgaos"][item["orgao"]] = au["orgaos"].get(item["orgao"], 0.0) + valor
            au["docs"].append(item)
            if doc and not eh_publico(p["favorecido"]):
                fv = a["favorecidos"].setdefault(doc, {"nome": p["favorecido"], "valor": 0.0, "n": 0, "autores": {},
                                                       "orgaos": {}, "docs": []})
                fv["valor"] += valor; fv["n"] += 1
                fv["autores"][chave] = fv["autores"].get(chave, 0.0) + valor
                fv["orgaos"][item["orgao"]] = fv["orgaos"].get(item["orgao"], 0.0) + valor
                fv["docs"].append(item)
    for a in out.values():
        for grupo in (a["autores"], a["favorecidos"]):
            for x in grupo.values():
                x["docs"].sort(key=lambda i: -i["valor"])
                x["docs"] = x["docs"][:N_DOCS]
    log.info("Pagamentos de emendas: %s (dados até %s)",
             ", ".join(f"{k}: {v['n']} pagamentos, R$ {v['total']:.0f}" for k, v in sorted(out.items())) or "nenhum", ate or "-")
    return {"ate": f"{ate[:4]}-{ate[4:6]}-{ate[6:8]}" if ate else "", "anos": out}


def cnpjs_empresas(res: dict | None, n: int = 600) -> list[str]:
    """As empresas e entidades que mais receberam pagamentos de emendas, para buscar os donos na Receita."""
    soma: dict[str, float] = {}
    for a in ((res or {}).get("anos") or {}).values():
        for doc, f in a["favorecidos"].items():
            soma[doc] = soma.get(doc, 0.0) + f["valor"]
    return [c for c, _ in sorted(soma.items(), key=lambda kv: -kv[1])[:n]]


def por_empresa(res: dict | None, nomes: dict[str, dict], so: set[str]) -> dict[str, dict]:
    """Para a página de cada empresa: quanto recebeu de emendas, de quem e por qual órgão, com os documentos.
    nomes: chave do autor → {"nome", "politico", "partido"} (vem das emendas, que acham o partido)."""
    out: dict[str, dict] = {}
    brutos: dict[str, str] = {}
    for ano, a in sorted(((res or {}).get("anos") or {}).items()):
        brutos.update({k: x["nome"] for k, x in a["autores"].items()})
        for doc, f in a["favorecidos"].items():
            if doc not in so:
                continue
            e = out.setdefault(doc, {"nome": f["nome"], "total": 0.0, "por_ano": {}, "autores": {}, "orgaos": {}, "docs": []})
            e["total"] += f["valor"]
            e["por_ano"][str(ano)] = round(f["valor"], 2)
            for k, v in f["autores"].items():
                e["autores"][k] = e["autores"].get(k, 0.0) + v
            for k, v in f["orgaos"].items():
                e["orgaos"][k] = e["orgaos"].get(k, 0.0) + v
            e["docs"] += f["docs"]
    for e in out.values():
        e["total"] = round(e["total"], 2)
        e["autores"] = [{**autor_mostrado(k, nomes, brutos.get(k, "")), "valor": round(v, 2)}
                        for k, v in sorted(e["autores"].items(), key=lambda kv: -kv[1])]
        e["orgaos"] = [[k, round(v, 2)] for k, v in sorted(e["orgaos"].items(), key=lambda kv: -kv[1])]
        e["docs"] = [documento(i) for i in sorted(e["docs"], key=lambda i: -i["valor"])[:N_DOCS]]
    return out


def autor_mostrado(chave: str, nomes: dict[str, dict], bruto: str = "") -> dict:
    n = nomes.get(chave) or {}
    return {"nome": n.get("nome") or nome_autor(bruto or chave)[1], "politico": n.get("politico"), "partido": n.get("partido", "")}


def documento(i: dict) -> dict:
    """Um pagamento para o site, com os links oficiais do pagamento e do empenho."""
    return {"data": i["data"], "codigo": i["pag"], "tipo": i["tipo"], "orgao": i["orgao"], "ug": i["ug"],
            "favorecido": i["fav"], "cnpj": i["doc"], "valor": round(i["valor"], 2), "empenho": i["emp"],
            "emenda": i["emenda"], "descricao": i["desc"], "url": url_documento(i["pag"]), "url_empenho": url_documento(i["emp"])}


# ---------------------------------------------------------------- todos os pagamentos a empresas e entidades
#
# Além das emendas, os mesmos arquivos diários trazem todo pagamento do governo federal. Para a página de
# incentivos guardamos, por dia, quanto cada empresa ou entidade (CNPJ que não é órgão público) recebeu, para quê
# (pela natureza da despesa do empenho) e de qual órgão. Pessoal e dívida pública ficam de fora.

VERSAO_GERAL = 1
CATEGORIAS_GERAL = {
    "contrato": "Compras, obras e serviços contratados",
    "repasse": "Repasses a entidades (convênios, auxílios e subvenções sociais)",
    "subsidio": "Subsídios (subvenções econômicas)",
    "outro": "Outros pagamentos (indenizações, decisões judiciais, despesas de anos anteriores...)",
}
CONTRATO = {"30", "31", "32", "33", "35", "37", "39", "40", "51", "52"}
REPASSE = {"41", "42", "43"}

# Empresas públicas e de economia mista que a regra de nomes de eh_publico não pega. Pagamento a elas é dinheiro que
# fica dentro do próprio governo. As demais são reconhecidas depois pela natureza jurídica na Receita.
PUBLICO_EXTRA = re.compile(r"\b(SERVICO FEDERAL DE PROCESSAMENTO|SERPRO|DATAPREV|CORREIOS E TELEGRAFOS|EMPRESA BRASIL DE COMUNICACAO|"
                           r"EMPRESA BRASILEIRA DE PESQUISA|COMPANHIA NACIONAL DE ABASTECIMENTO|IMPRENSA NACIONAL|CASA DA MOEDA|"
                           r"BANCO NACIONAL DE DESENVOLVIMENTO|FINANCIADORA DE ESTUDOS E PROJETOS|PETROLEO BRASILEIRO|"
                           r"UNIVERSIDADE ESTADUAL|CONSELHO (FEDERAL|REGIONAL)|INSTITUTO NACIONAL DO SEGURO SOCIAL|"
                           r"AGENCIA NACIONAL|BANCO CENTRAL)\b")


def eh_publico_geral(nome: str) -> bool:
    n = norm_name(nome)
    return bool(PUBLICO.search(n) or PUBLICO_EXTRA.search(n))


def categoria_despesa(natureza: str) -> str | None:
    """Pela natureza da despesa (ex.: 33903900 = custeio, aplicação direta, serviços de pessoa jurídica).
    None: pessoal e dívida pública, que não entram na conta."""
    d = digits(natureza)
    if len(d) < 6:
        return "outro"
    grupo, modalidade, elemento = d[1], d[2:4], d[4:6]
    if grupo in ("1", "2", "6"):  # pessoal e encargos, juros e amortização da dívida
        return None
    if elemento == "45":
        return "subsidio"
    if elemento in REPASSE or modalidade in ("50", "60"):
        return "repasse"
    if elemento in CONTRATO:
        return "contrato"
    return "outro"


def ler_geral(zip_path: Path) -> dict:
    """Um dia: {"f": {cnpj: [nome, {categoria: valor}, n pagamentos, {índice do órgão: valor}]}, "o": [órgãos]}."""
    valores: dict[str, dict[str, float]] = {}
    favs: dict[str, list] = {}
    orgaos: dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as z:
        for r in _tabela(z, "_Despesas_Pagamento_EmpenhosImpactados.csv"):
            v = to_float(r.get("Valor Pago (R$)")) + to_float(r.get("Valor Restos a Pagar Pagos (R$)"))
            if not v:
                continue
            cat = categoria_despesa(r.get("Código Natureza Despesa Completa", ""))
            if cat is None:
                continue
            d = valores.setdefault(r.get("Código Pagamento", ""), {})
            d[cat] = d.get(cat, 0.0) + v
        if valores:
            for r in _tabela(z, "_Despesas_Pagamento.csv"):
                cats = valores.get(r.get("Código Pagamento", ""))
                doc = digits(r.get("Código Favorecido"))
                nome = (r.get("Favorecido") or "").strip()
                if not cats or len(doc) != 14 or eh_publico_geral(nome):
                    continue
                o = orgaos.setdefault((r.get("Órgão Superior") or "").strip() or "Não informado", len(orgaos))
                f = favs.setdefault(doc, [nome, {}, 0, {}])
                f[2] += 1
                for c, v in cats.items():
                    f[1][c] = round(f[1].get(c, 0.0) + v, 2)
                    f[3][o] = round(f[3].get(o, 0.0) + v, 2)
    return {"f": favs, "o": sorted(orgaos, key=orgaos.get)}


def _arquivo_geral(cache: Path, dia: str) -> Path:
    return cache / f"{dia}-geral-v{VERSAO_GERAL}.json.gz"


def _gravar_geral(cache: Path, dia: str, zip_path: Path | None) -> None:
    try:
        d = ler_geral(zip_path) if zip_path else {"f": {}, "o": [], "sem_arquivo": True}
    except Exception as e:  # noqa: BLE001 - um dia com defeito não derruba as emendas
        log.warning("Pagamentos gerais: não foi possível ler %s (%s)", dia, e)
        return
    _arquivo_geral(cache, dia).write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode()))


def coletar_geral(anos: list[int], cache: Path, minutos: float = 40, hoje: dt.date | None = None) -> list[Path]:
    """Lê os dias dos anos do site que ainda não têm o resumo geral, do mais recente para o mais antigo, até o
    limite de tempo. Os dias novos já vêm de coletar() (emendas), que lê o mesmo arquivo; aqui completamos o resto
    aos poucos, a cada execução."""
    hoje = hoje or dt.date.today()
    cache.mkdir(parents=True, exist_ok=True)
    inicio, novos, falhas = time.time(), 0, 0
    tmp = cache / "dia-geral.zip"
    dia = min(hoje - dt.timedelta(days=1), dt.date(max(anos), 12, 31))
    primeiro = dt.date(min(anos), 1, 1)
    while dia >= primeiro:
        nome = dia.strftime("%Y%m%d")
        if not _arquivo_geral(cache, nome).exists():
            if time.time() - inicio > minutos * 60:
                break
            ok = _baixar_dia(nome, tmp)
            if ok:
                _gravar_geral(cache, nome, tmp)
                novos += 1
                falhas = 0
            elif ok is None:
                if (hoje - dia).days > 5:  # dia recente sem arquivo ainda pode aparecer depois
                    _gravar_geral(cache, nome, None)
                falhas = 0
            else:
                falhas += 1
                if falhas >= 5:
                    log.warning("Pagamentos gerais: Portal falhou em %d dias seguidos; para em %s (%s)", falhas, nome, ULTIMA_FALHA)
                    avisar(f"Pagamentos a empresas: o Portal da Transparência falhou em {falhas} dias seguidos "
                           f"({ULTIMA_FALHA}); a leitura continua na próxima execução")
                    break
        dia -= dt.timedelta(days=1)
    tmp.unlink(missing_ok=True)
    lidos = sorted(cache.glob(f"*-geral-v{VERSAO_GERAL}.json.gz"))
    log.info("Pagamentos gerais: %d dias lidos agora, %d no total", novos, len(lidos))
    return lidos


def resumir_geral(arquivos: list[Path], anos: list[int], hoje: dt.date | None = None) -> dict:
    """Soma, por ano do pagamento, o que cada empresa ou entidade recebeu. Diz também quantos dias de cada ano
    já foram lidos (a leitura completa leva várias execuções).

    {"anos": {ano: {cnpj: {"nome", "valor", "n", "cats": {...}, "orgaos": {...}}}}, "cobertura": {ano: {...}}}"""
    hoje = hoje or dt.date.today()
    anos_set = set(anos)
    out: dict[int, dict[str, dict]] = {a: {} for a in anos}
    dias: dict[int, list[str]] = {a: [] for a in anos}
    for f in sorted(arquivos):
        dia = f.name[:8]
        if not dia.isdigit() or int(dia[:4]) not in anos_set:
            continue
        ano = int(dia[:4])
        try:
            d = json.loads(gzip.decompress(f.read_bytes()))
        except (OSError, ValueError) as e:
            log.warning("Pagamentos gerais: arquivo com defeito %s (%s)", f.name, e)
            continue
        dias[ano].append(dia)
        orgs = d.get("o") or []
        for doc, (nome, cats, n, por_org) in (d.get("f") or {}).items():
            e = out[ano].get(doc)
            if e is None:
                e = out[ano][doc] = {"nome": nome, "valor": 0.0, "n": 0, "cats": {}, "orgaos": {}}
            e["n"] += n
            for c, v in cats.items():
                e["cats"][c] = e["cats"].get(c, 0.0) + v
                e["valor"] += v
            for i, v in por_org.items():
                o = orgs[int(i)] if int(i) < len(orgs) else "Não informado"
                e["orgaos"][o] = e["orgaos"].get(o, 0.0) + v
    cobertura = {}
    for ano in anos:
        fim = min(dt.date(ano, 12, 31), hoje - dt.timedelta(days=1))
        total = max(0, (fim - dt.date(ano, 1, 1)).days + 1)
        ds = sorted(dias[ano])
        cobertura[ano] = {"dias": len(ds), "dias_ano": total, "de": _iso(ds[0]) if ds else "", "ate": _iso(ds[-1]) if ds else "",
                          "completo": total > 0 and len(ds) >= total - 5}
    log.info("Pagamentos gerais: %s", ", ".join(f"{a}: {len(out[a])} recebedores, {cobertura[a]['dias']}/{cobertura[a]['dias_ano']} dias"
                                                for a in anos))
    return {"anos": out, "cobertura": cobertura}


def _iso(dia: str) -> str:
    return f"{dia[:4]}-{dia[4:6]}-{dia[6:8]}"
