"""Transforma os dados publicados dos sites em tabelas CSV para o painel de análises (analises/painel.html).

De onde vêm os dados: dos mesmos arquivos JSON que o site usa (site/public/data, site/public-mg/data),
dos resultados oficiais do TSE já baixados (eleicao2026/dados/tse) e das planilhas de Terras Raras
(terras-raras/dados). Esses arquivos já foram coletados das APIs oficiais (Câmara, Senado, Portal da
Transparência, Tesouro, TSE...) pelo coletor em etl/. Aqui não buscamos nada de novo na internet: só
achatamos o JSON em tabelas simples, que o painel desenha e que qualquer pessoa pode baixar e abrir no
Excel, LibreOffice ou Google Planilhas. Cada tabela guarda o link da fonte original sempre que o dado tem um.

Uso:
    python analises/tabelas.py --nacional site/public/data --mg site/public-mg/data \\
        --eleicao eleicao2026/dados/tse --terras terras-raras/dados --saida site/dist/analises/tabelas

A lista de tabelas e colunas (TABELAS) vira o arquivo catalogo.json, que o painel lê para saber o tipo de
cada coluna e mostrar a lista de downloads.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

SITE = "https://amarigo.github.io/segredos-abertos/"
SITE_MG = SITE + "mg/"
PORTAL_PJ = "https://portaldatransparencia.gov.br/pessoa-juridica/"
TSE_RESULTADOS = "https://resultados.tse.jus.br/oficial/ele2026/{e}/dados/{u}/{u}-c0001-e00{e}-u.json"
TURNO_TSE = {"6257": 1, "6258": 2}

# Tipos de coluna. "link" é texto que o painel mostra como link clicável.
TEXTO, INTEIRO, DECIMAL, DATA, LOGICO, LINK = "texto", "inteiro", "decimal", "data", "logico", "link"


@dataclass
class Tabela:
    nome: str
    grupo: str  # seção do painel
    descricao: str
    fonte: str  # link da fonte oficial dos dados
    colunas: list[tuple[str, str]]
    gerar: Callable[["Dados"], Iterable[dict]] = field(repr=False, default=lambda d: [])


# ---------------------------------------------------------------- leitura


class Dados:
    """Lê os arquivos publicados. Arquivo que não existe vira vazio (a tabela sai só com o cabeçalho)."""

    def __init__(self, nacional: Path | None, mg: Path | None, eleicao: Path | None, terras: Path | None):
        self.nacional, self.mg, self.eleicao, self.terras = nacional, mg, eleicao, terras
        self._cache: dict[Path, Any] = {}

    def ler(self, base: Path | None, rel: str, padrao: Any = None) -> Any:
        if base is None:
            return padrao
        p = base / rel
        if p not in self._cache:
            try:
                self._cache[p] = json.loads(p.read_text(encoding="utf-8"))
            except FileNotFoundError:
                self._cache[p] = padrao
        return self._cache[p]

    def varios(self, base: Path | None, pasta: str) -> Iterable[tuple[str, Any]]:
        """(nome do arquivo sem .json, conteúdo) de cada arquivo da pasta, em ordem."""
        if base is None or not (base / pasta).is_dir():
            return
        for p in sorted((base / pasta).glob("*.json")):
            yield p.stem, json.loads(p.read_text(encoding="utf-8"))

    # atalhos
    def n(self, rel: str, padrao: Any = None) -> Any:
        return self.ler(self.nacional, rel, padrao)

    def m(self, rel: str, padrao: Any = None) -> Any:
        return self.ler(self.mg, rel, padrao)

    def anos_de(self, base: Path | None, pasta: str, prefixo: str = "") -> list[int]:
        if base is None or not (base / pasta).is_dir():
            return []
        anos = []
        for p in (base / pasta).glob(f"{prefixo}*.json"):
            s = p.stem[len(prefixo):]
            if s.isdigit():
                anos.append(int(s))
        return sorted(anos)


def _pares(lista: Any) -> list:
    return [x for x in (lista or []) if isinstance(x, (list, tuple)) and len(x) >= 2]


def _data(s: Any) -> str | None:
    """Datas sempre como AAAA-MM-DD (o resto, como horário, fica de fora)."""
    if not s or not isinstance(s, str):
        return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    if len(s) >= 10 and s[2] == "/" and s[5] == "/":  # DD/MM/AAAA, como o TSE
        return f"{s[6:10]}-{s[3:5]}-{s[0:2]}"
    return None


def _num_br(s: Any) -> float | None:
    """Número do TSE ("48,24") para float."""
    if s in (None, ""):
        return None
    try:
        return float(str(s).replace(".", "").replace(",", ".")) if "," in str(s) else float(s)
    except ValueError:
        return None


def _site(rota: str, mg: bool = False) -> str:
    return (SITE_MG if mg else SITE) + "#/" + rota


# ---------------------------------------------------------------- Segredos Abertos (nacional)


def g_atualizacao(d: Dados):
    for site, meta, base in (("Segredos Abertos", d.n("meta.json"), SITE), ("Minas Nossa", d.m("meta.json"), SITE_MG)):
        if meta:
            c = meta.get("contagens") or {}
            yield {"site": site, "atualizado_em": _data(meta.get("atualizado_em")), "politicos": c.get("politicos"),
                   "despesas": c.get("despesas"), "votacoes": c.get("votacoes"), "empresas_com_socios": c.get("empresas_com_socios"),
                   "total_gasto_cota": meta.get("total_gasto"), "avisos": " | ".join(meta.get("avisos") or []), "link_site": base}


def g_politicos(d: Dados):
    for p in d.n("politicos.json", []):
        yield {"politico_id": p["id"], "casa": p.get("casa"), "cargo": p.get("cargo"), "nome": p.get("nome"),
               "partido": p.get("partido"), "uf": p.get("uf"), "bloco": p.get("bloco") or "",
               "lado": p.get("rotulo") or "Sem posição", "posicao_esquerda_direita": p.get("posicao"),
               "governo_ou_oposicao": p.get("campo") or "", "alinhamento_governo": p.get("alinhamento_governo"),
               "fidelidade_partido": p.get("fidelidade_partido"), "n_votos": p.get("n_votos"),
               "gasto_cota_total": p.get("total"), "foto": p.get("foto"), "fonte_oficial": p.get("fonte"),
               "pagina_no_site": _site(f"p/{p['id']}")}


def g_custos_ano(d: Dados):
    for p in d.n("politicos.json", []):
        for ano, a in sorted((p.get("por_ano") or {}).items()):
            g = a.get("grupos") or {}
            yield {"politico_id": p["id"], "ano": int(ano), "cota_total": a.get("total"),
                   "cota_com_o_parlamentar": g.get("pessoal"), "cota_com_o_gabinete": g.get("escritorio"),
                   "cota_com_servicos": g.get("servicos"), "salario": a.get("salario"), "verba_gabinete": a.get("verba_gabinete"),
                   "outros_gastos": a.get("outros_gastos"), "custo_total": a.get("custo_total"),
                   "cota_oficial_limite": a.get("cota_oficial"), "funcionarios_gabinete": a.get("n_pessoal")}


def _detalhes(d: Dados):
    for pid, p in d.varios(d.nacional, "p"):
        yield pid, p


def g_gastos_categoria(d: Dados):
    for pid, p in _detalhes(d):
        for ano, a in sorted((p.get("anos") or {}).items()):
            for c in a.get("categorias") or []:
                yield {"politico_id": pid, "ano": int(ano), "categoria": c.get("categoria"), "grupo": c.get("grupo"), "valor": c.get("valor")}


def g_gastos_mes(d: Dados):
    for pid, p in _detalhes(d):
        for ano, a in sorted((p.get("anos") or {}).items()):
            for m in a.get("meses") or []:
                yield {"politico_id": pid, "ano": int(ano), "mes": m.get("mes"),
                       "data": f"{int(ano):04d}-{int(m.get('mes') or 1):02d}-01", "valor": m.get("valor")}


def g_fornecedores(d: Dados):
    for pid, p in _detalhes(d):
        for ano, a in sorted((p.get("anos") or {}).items()):
            for f in a.get("fornecedores") or []:
                doc = f.get("doc") or ""
                cnpj = doc if f.get("tipo") == "cnpj" else ""
                yield {"politico_id": pid, "ano": int(ano), "cnpj": cnpj, "documento": doc, "tipo": f.get("tipo"),
                       "fornecedor": f.get("nome"), "valor": f.get("valor"), "n_notas": f.get("n"),
                       "donos": "; ".join(f.get("socios") or []),
                       "pagina_da_empresa": _site(f"e/{cnpj}") if cnpj and f.get("ficha") else ""}


def g_maiores_notas(d: Dados):
    for pid, p in _detalhes(d):
        for ano, a in sorted((p.get("anos") or {}).items()):
            for n in a.get("maiores_notas") or []:
                yield {"politico_id": pid, "ano": int(ano), "data": _data(n.get("data")), "categoria": n.get("categoria"),
                       "fornecedor": n.get("fornecedor"), "documento": n.get("doc"), "valor": n.get("valor"),
                       "nota_original": n.get("url")}


def g_equipe(d: Dados):
    for pid, p in _detalhes(d):
        for ano, a in sorted((p.get("anos") or {}).items()):
            for e in ((a.get("recursos") or {}).get("equipe") or []):
                yield {"politico_id": pid, "ano": int(ano), "nome": e.get("nome"), "grupo": e.get("grupo"),
                       "cargo": e.get("cargo"), "periodo": e.get("periodo")}


def g_temas_voto(d: Dados):
    for pid, p in _detalhes(d):
        for tema, t in sorted((p.get("temas") or {}).items()):
            yield {"politico_id": pid, "tema": tema, "sim": t.get("Sim") or 0, "nao": t.get("Não") or 0,
                   "outros": t.get("Outros") or 0, "contra_o_partido": t.get("contra_partido") or 0}


def g_votacoes(d: Dados):
    for v in d.n("votacoes.json", []):
        pr = v.get("proposicao") or {}
        pc = v.get("placar_casa") or {}
        det = d.n(f"v/{v['id']}.json", {}) or {}
        yield {"votacao_id": v["id"], "casa": v.get("casa"), "data": _data(v.get("data")), "descricao": v.get("descricao"),
               "aprovada": bool(v.get("aprovada")), "proposta": pr.get("titulo") or "", "tipo_proposta": pr.get("sigla") or "",
               "ementa": pr.get("ementa") or "", "temas": "; ".join(v.get("temas") or []), "sim": v.get("sim"), "nao": v.get("nao"),
               "placar_oficial_sim": pc.get("sim"), "placar_oficial_nao": pc.get("nao"),
               "proposta_original": pr.get("url") or "", "fonte_oficial": det.get("fonte") or "",
               "pagina_no_site": _site(f"v/{v['id']}")}


def g_votos(d: Dados):
    for vid, v in d.varios(d.nacional, "v"):
        for x in v.get("votos") or []:
            yield {"votacao_id": vid, "politico_id": x.get("politico"), "partido": x.get("partido"), "uf": x.get("uf"),
                   "voto": x.get("voto")}


def g_orientacoes(d: Dados):
    for vid, v in d.varios(d.nacional, "v"):
        for quem, o in sorted((v.get("orientacoes") or {}).items()):
            yield {"votacao_id": vid, "partido_ou_bloco": quem, "orientacao": o}


def g_votos_lado(d: Dados):
    for vid, v in d.varios(d.nacional, "v"):
        for lado, c in sorted((v.get("por_lado") or {}).items()):
            for voto, n in sorted(c.items()):
                yield {"votacao_id": vid, "lado": lado, "voto": voto, "quantidade": n}


def g_partidos(d: Dados):
    for p in d.n("partidos.json", []):
        yield {"casa": p.get("casa"), "partido": p.get("sigla"), "membros": p.get("n"),
               "posicao_esquerda_direita": p.get("posicao"), "alinhamento_governo": p.get("alinhamento_governo"),
               "fidelidade": p.get("fidelidade"), "gasto_cota_total": p.get("total")}


def g_partidos_ano(d: Dados):
    for p in d.n("partidos.json", []):
        for ano, a in sorted((p.get("por_ano") or {}).items()):
            yield {"casa": p.get("casa"), "partido": p.get("sigla"), "ano": int(ano), "membros": a.get("n"),
                   "cota": a.get("cota"), "cota_por_membro": a.get("cota_por_membro"), "custo_total": a.get("custo_total"),
                   "custo_por_membro": a.get("custo_por_membro")}


def _empresas_detalhe(d: Dados):
    for cnpj, e in d.varios(d.nacional, "e"):
        yield cnpj, e


def g_empresas(d: Dados):
    resumo = {e["cnpj"]: e for e in d.n("empresas.json", []) or []}
    vistos = set()
    for cnpj, e in _empresas_detalhe(d):
        vistos.add(cnpj)
        r = resumo.get(cnpj, {})
        emp = e.get("empresa") or {}
        yield {"cnpj": cnpj, "nome": e.get("nome") or emp.get("razao_social"), "nome_fantasia": emp.get("nome_fantasia") or "",
               "situacao": emp.get("situacao") or "", "abertura": _data(emp.get("abertura")), "atividade": emp.get("atividade") or "",
               "municipio": emp.get("municipio") or "", "uf": emp.get("uf") or "", "capital_social": emp.get("capital_social"),
               "porte": emp.get("porte") or "", "natureza": emp.get("natureza") or "",
               "recebido_cota": e.get("total") or 0, "politicos_que_pagaram": e.get("n_politicos") or 0,
               "recebido_emendas": (e.get("emendas") or {}).get("total") or r.get("emendas") or 0,
               "recebido_governo": (e.get("governo") or {}).get("total") or r.get("governo") or 0,
               "renuncia_fiscal": (e.get("renuncia") or {}).get("total") or r.get("renuncia") or 0,
               "empresas_no_mesmo_endereco": e.get("n_mesmo_endereco") or 0, "tem_holding": bool(e.get("tem_holding")),
               "alertas": " | ".join(e.get("alertas") or []), "portal_da_transparencia": PORTAL_PJ + cnpj,
               "pagina_no_site": _site(f"e/{cnpj}")}
    for cnpj, r in resumo.items():  # empresas da lista sem página própria
        if cnpj in vistos:
            continue
        yield {"cnpj": cnpj, "nome": r.get("nome"), "recebido_cota": r.get("total") or 0,
               "politicos_que_pagaram": r.get("n_politicos") or 0, "recebido_emendas": r.get("emendas") or 0,
               "recebido_governo": r.get("governo") or 0, "renuncia_fiscal": r.get("renuncia") or 0,
               "empresas_no_mesmo_endereco": r.get("n_mesmo_endereco") or 0, "tem_holding": bool(r.get("tem_holding")),
               "portal_da_transparencia": PORTAL_PJ + cnpj, "pagina_no_site": ""}


def g_socios(d: Dados):
    for cnpj, e in _empresas_detalhe(d):
        for s in e.get("socios") or []:
            yield {"cnpj": cnpj, "socio": s.get("nome"), "documento_socio": s.get("doc"), "qualificacao": s.get("qualificacao"),
                   "entrada": _data(s.get("entrada")), "faixa_etaria": s.get("faixa_etaria") or "", "tipo": s.get("tipo") or "",
                   "outras_empresas": len(s.get("outras_empresas") or [])}


def g_socios_outras(d: Dados):
    for cnpj, e in _empresas_detalhe(d):
        for s in e.get("socios") or []:
            for o in s.get("outras_empresas") or []:
                yield {"cnpj": cnpj, "socio": s.get("nome"), "outra_cnpj": o.get("cnpj"), "outra_nome": o.get("nome"),
                       "outra_recebeu_cota": o.get("total") or 0, "outra_recebeu_emendas": o.get("emendas") or 0,
                       "outra_recebeu_governo": o.get("governo") or 0, "outra_renuncia_fiscal": o.get("renuncia") or 0,
                       "portal_da_transparencia": PORTAL_PJ + (o.get("cnpj") or "")}


def g_donos_finais(d: Dados):
    for cnpj, e in _empresas_detalhe(d):
        for f in e.get("donos_finais") or []:
            yield {"cnpj": cnpj, "dono_final": f.get("nome"), "documento": f.get("doc"), "tipo": f.get("tipo"),
                   "qualificacao": f.get("qualificacao"), "pais": f.get("pais") or "", "como_termina": f.get("fim"),
                   "camadas": len(f.get("cadeia") or []),
                   "cadeia": " > ".join(c.get("nome") or c.get("cnpj") or "" for c in f.get("cadeia") or []),
                   "outras_empresas": len(f.get("outras_empresas") or [])}


def g_pagadores(d: Dados):
    for cnpj, e in _empresas_detalhe(d):
        for p in e.get("pagadores") or []:
            yield {"cnpj": cnpj, "politico_id": p.get("politico"), "nome": p.get("nome"), "partido": p.get("partido"),
                   "uf": p.get("uf"), "valor": p.get("valor")}


def g_mesmo_endereco(d: Dados):
    for cnpj, e in _empresas_detalhe(d):
        for o in e.get("mesmo_endereco") or []:
            yield {"cnpj": cnpj, "outra_cnpj": o.get("cnpj"), "outra_nome": o.get("nome"), "mesmos_socios": bool(o.get("mesmos_socios")),
                   "outra_recebeu_cota": o.get("total") or 0}


def g_notas_empresas(d: Dados):
    if d.nacional is None or not (d.nacional / "e" / "notas").is_dir():
        return
    for p in sorted((d.nacional / "e" / "notas").glob("*.json")):
        cnpj = p.stem.split("-")[0]
        for n in json.loads(p.read_text(encoding="utf-8")) or []:
            n = list(n) + [None] * 7
            yield {"cnpj": cnpj, "data": _data(n[0]), "politico_id": n[1], "categoria": n[2], "valor": n[3], "nota_original": n[4]}


# ---------------------------------------------------------------- Emendas


def _anos_emendas(d: Dados):
    for ano in d.anos_de(d.nacional, "emendas"):
        e = d.n(f"emendas/{ano}.json")
        if e:
            yield ano, e


def g_emendas_autores(d: Dados):
    for ano, e in _anos_emendas(d):
        for a in e.get("autores") or []:
            yield {"ano": ano, "autor": a.get("nome"), "politico_id": a.get("politico") or "", "partido": a.get("partido") or "",
                   "uf": a.get("uf") or "", "casa": a.get("casa") or "", "tipo": "individual", "emendas": a.get("n"),
                   "empenhado": a.get("empenhado"), "pago": a.get("pago"), "pago_emenda_pix": a.get("pix") or 0, "fonte_oficial": e.get("fonte")}
        for a in e.get("coletivos") or []:
            yield {"ano": ano, "autor": a.get("nome"), "politico_id": "", "partido": "", "uf": "", "casa": "",
                   "tipo": a.get("tipo"), "emendas": a.get("n"), "empenhado": a.get("empenhado"), "pago": a.get("pago"),
                   "pago_emenda_pix": a.get("pix") or 0, "fonte_oficial": e.get("fonte")}


def g_emendas_area(d: Dados):
    for ano, e in _anos_emendas(d):
        for a in e.get("por_area") or []:
            yield {"ano": ano, "area": a.get("area"), "empenhado": a.get("empenhado"), "pago": a.get("pago")}


def g_emendas_tipo(d: Dados):
    for ano, e in _anos_emendas(d):
        for a in e.get("por_tipo") or []:
            yield {"ano": ano, "tipo": a.get("rotulo") or a.get("tipo"), "emendas": a.get("n"), "empenhado": a.get("empenhado"), "pago": a.get("pago")}


def g_emendas_partido(d: Dados):
    for ano, e in _anos_emendas(d):
        for a in e.get("partidos") or []:
            yield {"ano": ano, "partido": a.get("sigla"), "emendas": a.get("n"), "empenhado": a.get("empenhado"),
                   "pago": a.get("pago"), "pago_emenda_pix": a.get("pix") or 0}


def g_emendas_favorecidos(d: Dados):
    for ano, e in _anos_emendas(d):
        for f in ((e.get("favorecidos") or {}).get("lista") or []):
            doc = f.get("doc") or ""
            yield {"ano": ano, "documento": doc, "favorecido": f.get("nome"), "categoria": f.get("cat"), "natureza": f.get("natureza"),
                   "uf": f.get("uf"), "municipio": f.get("municipio"), "valor": f.get("valor"),
                   "autores": "; ".join(str(a[0]) for a in _pares(f.get("autores"))),
                   "portal_da_transparencia": PORTAL_PJ + doc if len(doc) == 14 else ""}


def g_emendas_municipios(d: Dados):
    for ano, e in _anos_emendas(d):
        for m in ((e.get("favorecidos") or {}).get("municipios") or []):
            yield {"ano": ano, "municipio": m.get("nome"), "uf": m.get("uf"), "valor": m.get("valor"), "favorecidos": m.get("n")}


def g_emendas_pagamentos(d: Dados):
    """Cada pagamento (ordem bancária) de emenda, com o link do documento no Portal da Transparência."""
    for ano in d.anos_de(d.nacional, "emendas"):
        for _, a in d.varios(d.nacional, f"emendas/docs/{ano}"):
            for x in a.get("docs") or []:
                yield {"ano": ano, "autor": a.get("nome"), "data": _data(x.get("data")), "orgao": x.get("orgao"), "unidade": x.get("ug"),
                       "favorecido": x.get("favorecido"), "cnpj": x.get("cnpj") or "", "valor": x.get("valor"),
                       "descricao": x.get("descricao"), "documento": x.get("codigo"), "pagamento_original": x.get("url"),
                       "empenho_original": x.get("url_empenho")}


# ---------------------------------------------------------------- Incentivos (pagamentos do governo e renúncia fiscal)


def g_governo_pagamentos(d: Dados):
    for ano in d.anos_de(d.nacional, "incentivos"):
        pg = (d.n(f"incentivos/{ano}.json") or {}).get("pagamentos") or {}
        for t in pg.get("top") or []:
            cnpj = t.get("cnpj") or ""
            yield {"ano": ano, "cnpj": cnpj, "nome": t.get("nome"), "tipo": t.get("tipo"), "uf": t.get("uf"), "valor": t.get("valor"),
                   "pagamentos": t.get("n"), "categorias": "; ".join(str(c[0]) for c in _pares(t.get("cats"))),
                   "orgaos": "; ".join(str(c[0]) for c in _pares(t.get("orgaos"))), "donos": "; ".join(t.get("donos") or []),
                   "outras_empresas_dos_donos": t.get("n_outras") or 0, "portal_da_transparencia": PORTAL_PJ + cnpj}


def g_governo_orgaos(d: Dados):
    for ano in d.anos_de(d.nacional, "incentivos"):
        pg = (d.n(f"incentivos/{ano}.json") or {}).get("pagamentos") or {}
        for o in _pares(pg.get("orgaos")):
            yield {"ano": ano, "orgao": o[0], "valor": o[1]}


def g_renuncia_empresas(d: Dados):
    for ano in d.anos_de(d.nacional, "incentivos", "renuncia-"):
        r = d.n(f"incentivos/renuncia-{ano}.json") or {}
        for t in r.get("top") or []:
            cnpj = t.get("cnpj") or ""
            yield {"ano": ano, "cnpj": cnpj, "nome": t.get("nome"), "tipo": t.get("tipo"), "uf": t.get("uf"),
                   "municipio": t.get("municipio"), "setor": t.get("setor"), "atividade": t.get("atividade"), "valor": t.get("valor"),
                   "beneficios": "; ".join(str(b[0]) for b in _pares(t.get("beneficios"))), "donos": "; ".join(t.get("donos") or []),
                   "ano_parcial": bool(r.get("parcial")), "portal_da_transparencia": PORTAL_PJ + cnpj, "fonte_oficial": r.get("fonte")}


def g_renuncia_beneficios(d: Dados):
    for ano in d.anos_de(d.nacional, "incentivos", "renuncia-"):
        r = d.n(f"incentivos/renuncia-{ano}.json") or {}
        for b in r.get("por_beneficio") or []:
            yield {"ano": ano, "beneficio": b.get("nome"), "tributo": b.get("tributo"), "valor": b.get("valor"), "empresas": b.get("n")}


def g_renuncia_setores(d: Dados):
    for ano in d.anos_de(d.nacional, "incentivos", "renuncia-"):
        r = d.n(f"incentivos/renuncia-{ano}.json") or {}
        for s in r.get("por_setor") or []:
            yield {"ano": ano, "setor": s.get("setor"), "valor": s.get("valor"), "empresas": s.get("n")}


# ---------------------------------------------------------------- Dinheiro do Brasil (finanças federais)


def _anos_fin(d: Dados):
    for ano in d.anos_de(d.nacional, "financas"):
        f = d.n(f"financas/{ano}.json")
        if f:
            yield ano, f


def g_fin_serie(d: Dados):
    idx = d.n("financas/indice.json") or {}
    fonte = (idx.get("fontes") or {}).get("siconfi", "")
    for s in idx.get("serie") or []:
        yield {"ano": s.get("ano"), "ano_parcial": bool(s.get("parcial")), "ate": s.get("ate"), "impostos": s.get("impostos"),
               "receita_propria": s.get("receita_propria"), "divida_nova": s.get("divida_nova"), "rolagem_da_divida": s.get("rolagem"),
               "despesa": s.get("despesa"), "pessoal": s.get("pessoal"), "juros": s.get("juros"), "inss": s.get("inss"),
               "investimentos": s.get("investimentos"), "administracao_geral": s.get("adm_geral"),
               "arrecadacao_receita_federal": s.get("arrecadacao_rfb"), "fonte_oficial": fonte}


def g_fin_receitas(d: Dados):
    for ano, f in _anos_fin(d):
        for r in ((f.get("rreo") or {}).get("receitas") or []):
            yield {"ano": ano, "receita": r.get("nome"), "tipo": r.get("tipo"), "valor": r.get("valor"), "previsto": r.get("previsto"),
                   "explicacao": r.get("explica"), "fonte_oficial": (f.get("fontes_ano") or {}).get("rreo1")}


def g_fin_despesas(d: Dados):
    for ano, f in _anos_fin(d):
        for r in ((f.get("rreo") or {}).get("despesas") or []):
            yield {"ano": ano, "despesa": r.get("nome"), "empenhado": r.get("empenhado"), "liquidado": r.get("liquidado"),
                   "pago": r.get("pago"), "dotacao": r.get("dotacao"), "explicacao": r.get("explica"),
                   "fonte_oficial": (f.get("fontes_ano") or {}).get("rreo1")}


def g_fin_funcoes(d: Dados):
    for ano, f in _anos_fin(d):
        for r in ((f.get("funcoes") or {}).get("funcoes") or []):
            yield {"ano": ano, "funcao": r.get("nome"), "liquidado": r.get("liquidado"), "dotacao": r.get("dotacao"),
                   "explicacao": r.get("explica"), "fonte_oficial": (f.get("fontes_ano") or {}).get("rreo2")}


def g_fin_tributos(d: Dados):
    idx = d.n("financas/indice.json") or {}
    fonte = (idx.get("fontes") or {}).get("receita", "")
    for ano, f in _anos_fin(d):
        arr = f.get("arrecadacao") or {}
        for g in arr.get("grupos") or []:
            trib = _pares(g.get("tributos"))
            if not trib:
                yield {"ano": ano, "grupo": g.get("nome"), "tributo": g.get("nome"), "valor": g.get("valor"), "ate_mes": arr.get("ate_mes"), "fonte_oficial": fonte}
            for t in trib:
                yield {"ano": ano, "grupo": g.get("nome"), "tributo": t[0], "valor": t[1], "ate_mes": arr.get("ate_mes"), "fonte_oficial": fonte}


def g_fin_uf(d: Dados):
    for ano, f in _anos_fin(d):
        for u in _pares((f.get("arrecadacao") or {}).get("por_uf")):
            yield {"ano": ano, "uf": u[0], "arrecadacao": u[1]}


def g_fin_orgaos(d: Dados):
    for ano, f in _anos_fin(d):
        for o in ((f.get("executivo") or {}).get("orgaos") or []):
            yield {"ano": ano, "codigo": o.get("cod"), "orgao": o.get("nome"), "realizado": o.get("realizado"),
                   "orcamento_atualizado": o.get("atualizado"), "fonte_oficial": o.get("url")}


def g_fin_programas(d: Dados):
    for ano, f in _anos_fin(d):
        for p in ((f.get("executivo") or {}).get("programas") or []):
            yield {"ano": ano, "codigo": p.get("cod"), "programa": p.get("nome"), "funcao": p.get("funcao"),
                   "realizado": p.get("realizado"), "orcamento_atualizado": p.get("atualizado"), "fonte_oficial": p.get("url")}


def g_fin_pessoal_poderes(d: Dados):
    for ano, f in _anos_fin(d):
        for pd in f.get("pessoal_poderes") or []:
            for o in pd.get("orgaos") or []:
                yield {"ano": ano, "poder": pd.get("nome"), "quadrimestre": pd.get("quadrimestre"), "orgao": o.get("nome"),
                       "despesa_bruta": o.get("bruta"), "ativos": o.get("ativos"), "inativos": o.get("inativos"),
                       "despesa_total_pessoal": o.get("dtp"), "pct_da_receita": o.get("pct_rcl"), "limite_maximo": o.get("limite_max"),
                       "fonte_oficial": pd.get("url")}


def g_fin_indicadores(d: Dados):
    for ano, f in _anos_fin(d):
        for k in f.get("kpis") or []:
            yield {"ano": ano, "indicador": k.get("titulo"), "valor": k.get("valor") if isinstance(k.get("valor"), (int, float)) else None,
                   "formato": k.get("formato"), "situacao": k.get("nivel"), "regra": k.get("regra"), "explicacao": k.get("explica"),
                   "fonte_oficial": k.get("fonte")}


# ---------------------------------------------------------------- Projetos em andamento e verificação


def _projetos(d: Dados):
    for base, mg, rel in ((d.nacional, False, "tramitacao.json"), (d.mg, True, "almg/tramitacao.json")):
        t = d.ler(base, rel) or {}
        for p in t.get("itens") or []:
            if mg and p.get("casa") != "almg":
                continue
            yield p


def g_projetos(d: Dados):
    for p in _projetos(d):
        pauta = p.get("pauta") or []
        yield {"projeto_id": p.get("id"), "casa": p.get("casa"), "proposta": f"{p.get('sigla')} {p.get('numero')}/{p.get('ano')}",
               "tipo": p.get("sigla"), "ementa": p.get("ementa"), "resumo": p.get("resumo") or "",
               "apresentada": _data(p.get("apresentada")), "atualizada": _data(p.get("atualizada")), "situacao": p.get("situacao"),
               "onde_esta": p.get("onde"), "etapa": p.get("etapa_nome") or p.get("etapa"), "regime": p.get("regime") or "",
               "temas": "; ".join(p.get("temas") or []), "autores": p.get("n_autores"),
               "primeiro_autor": ((p.get("autores") or [{}])[0]).get("nome", ""),
               "proxima_pauta": _data(pauta[0].get("data")) if pauta else None, "prazo": _data(p.get("prazo")),
               "tranca_a_pauta": bool(p.get("tranca_pauta")), "grupos": "; ".join(p.get("grupos") or []),
               "proposta_original": p.get("url"), "texto_original": p.get("texto") or ""}


def g_projetos_autores(d: Dados):
    for p in _projetos(d):
        for a in p.get("autores") or []:
            yield {"projeto_id": p.get("id"), "autor": a.get("nome"), "partido": a.get("partido"), "uf": a.get("uf"),
                   "politico_id": a.get("id") or ""}


def g_verificacao(d: Dados):
    v = d.n("verificacao.json") or {}
    for c in v.get("checagens") or []:
        yield {"data": _data(v.get("data") or v.get("gerado_em")), "secao": c.get("secao"), "checagem": c.get("titulo"),
               "status": c.get("status"), "conferidos": c.get("conferidos"), "divergentes": c.get("divergentes"),
               "nao_conferidos": c.get("nao_conferidos"), "como_conferimos": c.get("como"), "fonte_oficial": c.get("fonte")}


# ---------------------------------------------------------------- Minas Nossa (Minas Gerais)


def _almg(d: Dados):
    for i, dep in d.varios(d.mg, "almg/d"):
        yield i, dep


def g_mg_deputados(d: Dados):
    for dep in ((d.m("almg/deputados.json") or {}).get("deputados") or []):
        yield {"deputado_id": str(dep.get("id")), "nome": dep.get("nome"), "partido": dep.get("partido"),
               "pagina_oficial": dep.get("url"), "verba_oficial": dep.get("url_verba") or "",
               "pagina_no_site": _site(f"deputado-estadual/{dep.get('id')}", mg=True)}


def g_mg_deputados_ano(d: Dados):
    for dep in ((d.m("almg/deputados.json") or {}).get("deputados") or []):
        for ano, a in sorted((dep.get("por_ano") or {}).items()):
            yield {"deputado_id": str(dep.get("id")), "ano": int(ano), "verba_indenizatoria": a.get("verba"), "projetos": a.get("projetos"),
                   "requerimentos": a.get("requerimentos"), "aprovadas": a.get("aprovadas"),
                   "emendas_indicado": a.get("emendas_indicado"), "emendas_pago": a.get("emendas_pago")}


def g_mg_verba_notas(d: Dados):
    for i, dep in _almg(d):
        for ano, a in sorted((dep.get("anos") or {}).items()):
            for n in ((a.get("verba") or {}).get("notas") or []):
                yield {"deputado_id": i, "ano": int(ano), "data": _data(n.get("data")), "tipo": n.get("tipo"),
                       "fornecedor": n.get("fornecedor"), "cnpj_cpf": n.get("cnpj"), "pessoa_fisica": bool(n.get("pf")),
                       "valor": n.get("valor"), "fonte_oficial": dep.get("url_verba") or dep.get("url")}


def g_mg_verba_fornecedores(d: Dados):
    for i, dep in _almg(d):
        for ano, a in sorted((dep.get("anos") or {}).items()):
            for f in ((a.get("verba") or {}).get("fornecedores") or []):
                yield {"deputado_id": i, "ano": int(ano), "fornecedor": f.get("nome"), "cnpj_cpf": f.get("cnpj"),
                       "pessoa_fisica": bool(f.get("pf")), "valor": f.get("valor"), "n_notas": f.get("n")}


def g_mg_proposicoes(d: Dados):
    for i, dep in _almg(d):
        for ano, a in sorted((dep.get("anos") or {}).items()):
            for p in ((a.get("proposicoes") or {}).get("lista") or []):
                yield {"deputado_id": i, "ano": int(ano), "proposta": f"{p.get('sigla')} {p.get('numero')}/{p.get('ano')}",
                       "ementa": p.get("ementa"), "situacao": p.get("situacao"), "aprovada": bool(p.get("aprovada")),
                       "data": _data(p.get("data")), "proposta_original": p.get("url")}


def g_mg_emendas_municipios(d: Dados):
    e = d.m("estado/emendas.json") or {}
    for ano, a in sorted((e.get("anos") or {}).items()):
        for m in a.get("municipios") or []:
            yield {"ano": int(ano), "municipio": m.get("nome"), "indicado": m.get("indicado"), "pago": m.get("pago"),
                   "emendas": m.get("n"), "fonte_oficial": e.get("fonte")}


def g_mg_emendas_autores(d: Dados):
    e = d.m("estado/emendas.json") or {}
    for ano, a in sorted((e.get("anos") or {}).items()):
        for x in a.get("autores") or []:
            yield {"ano": int(ano), "autor": x.get("nome"), "deputado_id": str(x.get("deputado") or ""), "indicado": x.get("indicado"),
                   "pago": x.get("pago"), "emendas": x.get("n"), "fonte_oficial": e.get("fonte")}


def g_mg_governo_eleicoes(d: Dados):
    g = d.m("estado/governo.json") or {}
    for el in g.get("eleicoes") or []:
        for c in el.get("candidatos") or []:
            yield {"eleicao": el.get("eleicao"), "mandato": f"{el.get('inicio')}-{el.get('fim')}", "candidato": c.get("nome"),
                   "partido": c.get("partido"), "votos": c.get("votos"), "pct_votos": c.get("pct"), "eleito": bool(c.get("eleito")),
                   "fonte_oficial": g.get("fonte_tse")}


def g_mg_governo_equipe(d: Dados):
    g = d.m("estado/governo.json") or {}
    eq = g.get("equipe") or {}
    fonte = (eq.get("fontes") or {}).get("salarios", "")
    for p in eq.get("pessoas") or []:
        via = p.get("viagens") or {}
        yield {"nome": p.get("nome"), "cargo": p.get("cargo"), "orgao": p.get("orgao"), "mes": eq.get("mes_salarios"),
               "salario_bruto": p.get("bruto"), "descontos": p.get("descontos"), "salario_liquido": p.get("liquido"),
               "jetons": p.get("jetons"), "viagens": sum(a.get("viagens") or 0 for a in via.get("anos") or []),
               "gasto_viagens": sum((a.get("diarias") or 0) + (a.get("passagens") or 0) for a in via.get("anos") or []),
               "fonte_oficial": fonte}


def g_mg_cidades(d: Dados):
    for c in d.m("cidades.json", []) or []:
        pf = c.get("prefeito") or {}
        yield {"cidade_id": c.get("id"), "cidade": c.get("nome"), "uf": c.get("uf"), "prefeito": pf.get("nome", ""),
               "partido_prefeito": pf.get("partido", ""), "desde": c.get("desde"), "vereadores": c.get("vereadores"),
               "pagina_no_site": _site(f"cidade/{c.get('id')}", mg=True)}


def g_mg_cidades_emendas_federais(d: Dados):
    for cid, c in d.varios(d.mg, "cidades/dinheiro"):
        fed = c.get("federais") or {}
        for f in fed.get("favorecidos") or []:
            yield {"cidade_id": cid, "favorecido": f.get("nome"), "cnpj": f.get("cnpj"), "valor": f.get("valor"),
                   "anos": "; ".join(str(a) for a in f.get("anos") or []),
                   "autores": "; ".join(a.get("nome", "") for a in f.get("autores") or []), "fonte_oficial": f.get("url") or fed.get("fonte")}


def g_mg_cidades_contas(d: Dados):
    for cid, c in d.varios(d.mg, "cidades/dinheiro"):
        ct = c.get("contas") or {}
        for a in ct.get("anos") or []:
            for f in a.get("funcoes") or []:
                yield {"cidade_id": cid, "ano": a.get("ano"), "funcao": f.get("funcao"), "empenhado": f.get("empenhado"),
                       "liquidado": f.get("liquidado"), "pago": f.get("pago"), "fonte_oficial": ct.get("fonte")}


# ---------------------------------------------------------------- Eleição 2026 (TSE)


def _tse(d: Dados):
    if d.eleicao is None or not d.eleicao.is_dir():
        return
    for p in sorted(d.eleicao.glob("*-*.json")):
        uf, el = p.stem.split("-", 1)
        if el not in TURNO_TSE:
            continue
        yield uf.upper(), el, json.loads(p.read_text(encoding="utf-8"))


def g_eleicao_candidatos(d: Dados):
    for uf, el, j in _tse(d):
        for cargo in j.get("carg") or []:
            for agr in cargo.get("agr") or []:
                for par in agr.get("par") or []:
                    for c in par.get("cand") or []:
                        yield {"turno": TURNO_TSE[el], "uf": uf, "candidato": c.get("nmu"), "numero": c.get("n"), "partido": par.get("sg"),
                               "coligacao": agr.get("nm") if agr.get("tp") == "c" else par.get("sg"), "votos": int(c.get("vap") or 0),
                               "pct_validos": _num_br(c.get("pvapn") or c.get("pvap")), "situacao": c.get("st"),
                               "fonte_oficial": TSE_RESULTADOS.format(e=el, u=uf.lower())}


def g_eleicao_comparecimento(d: Dados):
    for uf, el, j in _tse(d):
        e, v = j.get("e") or {}, j.get("v") or {}
        yield {"turno": TURNO_TSE[el], "uf": uf, "eleitores": int(e.get("te") or 0), "compareceram": int(e.get("c") or 0),
               "abstencoes": int(e.get("a") or 0), "votos_validos": int(v.get("vv") or 0), "brancos": int(v.get("vb") or 0),
               "nulos": int(v.get("tvn") or 0), "secoes_apuradas_pct": _num_br(j.get("s", {}).get("psan") or j.get("s", {}).get("psa")),
               "fonte_oficial": TSE_RESULTADOS.format(e=el, u=uf.lower())}


# ---------------------------------------------------------------- Terras raras (planilhas escritas à mão, cada linha com fonte)

TERRAS = {
    "terras_raras_projetos": ("projetos.csv", "Projetos de mineração de terras raras em Minas Gerais."),
    "terras_raras_empresas": ("empresas.csv", "Empresas, donos e países por trás dos projetos."),
    "terras_raras_donos_terra": ("donos_terra.csv", "Quem tem o direito de minerar e quem é dono da terra."),
    "terras_raras_licencas": ("licencas.csv", "Licenças ambientais pendentes."),
    "terras_raras_numeros": ("numeros.csv", "Números econômicos dos projetos."),
    "terras_raras_noticias": ("processos_noticias.csv", "Processos e notícias, por data."),
    "terras_raras_leis": ("leis.csv", "Leis e normas que valem para as terras raras."),
    "terras_raras_impactos": ("impactos.csv", "Impactos ambientais conhecidos."),
    "terras_raras_areas": ("areas_potencial.csv", "Áreas com potencial de terras raras."),
    "terras_raras_propostas": ("propostas.csv", "Propostas para legisladores."),
}


def _cabecalho_csv(caminho: Path) -> list[str]:
    with caminho.open(encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def _gerar_terras(arquivo: str) -> Callable[[Dados], Iterable[dict]]:
    def g(d: Dados):
        if d.terras is None or not (d.terras / arquivo).exists():
            return
        with (d.terras / arquivo).open(encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)
    return g


# ---------------------------------------------------------------- catálogo

PJ = "Portal da Transparência"
TABELAS: list[Tabela] = [
    Tabela("atualizacao", "0 Sobre os dados", "Quando cada site foi atualizado e quantos registros tem.", SITE,
           [("site", TEXTO), ("atualizado_em", DATA), ("politicos", INTEIRO), ("despesas", INTEIRO), ("votacoes", INTEIRO),
            ("empresas_com_socios", INTEIRO), ("total_gasto_cota", DECIMAL), ("avisos", TEXTO), ("link_site", LINK)], g_atualizacao),
    Tabela("politicos", "1 Políticos e gastos", "Deputados federais e senadores, com partido, bloco, lado (esquerda/direita) e governo ou oposição.",
           "https://dadosabertos.camara.leg.br/api/v2",
           [("politico_id", TEXTO), ("casa", TEXTO), ("cargo", TEXTO), ("nome", TEXTO), ("partido", TEXTO), ("uf", TEXTO), ("bloco", TEXTO),
            ("lado", TEXTO), ("posicao_esquerda_direita", DECIMAL), ("governo_ou_oposicao", TEXTO), ("alinhamento_governo", DECIMAL),
            ("fidelidade_partido", DECIMAL), ("n_votos", INTEIRO), ("gasto_cota_total", DECIMAL), ("foto", LINK), ("fonte_oficial", LINK),
            ("pagina_no_site", LINK)], g_politicos),
    Tabela("custos_ano", "1 Políticos e gastos", "Quanto cada um custou por ano: cota parlamentar por grupo, salário e verba de gabinete.",
           "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("politico_id", TEXTO), ("ano", INTEIRO), ("cota_total", DECIMAL), ("cota_com_o_parlamentar", DECIMAL), ("cota_com_o_gabinete", DECIMAL),
            ("cota_com_servicos", DECIMAL), ("salario", DECIMAL), ("verba_gabinete", DECIMAL), ("outros_gastos", DECIMAL), ("custo_total", DECIMAL),
            ("cota_oficial_limite", DECIMAL), ("funcionarios_gabinete", INTEIRO)], g_custos_ano),
    Tabela("gastos_categoria", "1 Políticos e gastos", "Gasto da cota por tipo de despesa (passagens, combustível, divulgação...).",
           "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("politico_id", TEXTO), ("ano", INTEIRO), ("categoria", TEXTO), ("grupo", TEXTO), ("valor", DECIMAL)], g_gastos_categoria),
    Tabela("gastos_mes", "1 Políticos e gastos", "Gasto da cota mês a mês.", "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("politico_id", TEXTO), ("ano", INTEIRO), ("mes", INTEIRO), ("data", DATA), ("valor", DECIMAL)], g_gastos_mes),
    Tabela("fornecedores", "1 Políticos e gastos", "Empresas e pessoas que receberam da cota de cada político, com os donos.",
           "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("politico_id", TEXTO), ("ano", INTEIRO), ("cnpj", TEXTO), ("documento", TEXTO), ("tipo", TEXTO), ("fornecedor", TEXTO),
            ("valor", DECIMAL), ("n_notas", INTEIRO), ("donos", TEXTO), ("pagina_da_empresa", LINK)], g_fornecedores),
    Tabela("maiores_notas", "1 Políticos e gastos", "As maiores notas fiscais de cada político, com o link da nota original.",
           "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("politico_id", TEXTO), ("ano", INTEIRO), ("data", DATA), ("categoria", TEXTO), ("fornecedor", TEXTO), ("documento", TEXTO),
            ("valor", DECIMAL), ("nota_original", LINK)], g_maiores_notas),
    Tabela("equipe_gabinete", "1 Políticos e gastos", "Pessoas que trabalham no gabinete (quando a Casa publica).",
           "https://dadosabertos.camara.leg.br/arquivos/funcionarios/json/funcionarios.json",
           [("politico_id", TEXTO), ("ano", INTEIRO), ("nome", TEXTO), ("grupo", TEXTO), ("cargo", TEXTO), ("periodo", TEXTO)], g_equipe),
    Tabela("votacoes", "2 Votações", "Votações nominais da Câmara e do Senado, com a proposta e o link oficial.",
           "https://dadosabertos.camara.leg.br/api/v2/votacoes",
           [("votacao_id", TEXTO), ("casa", TEXTO), ("data", DATA), ("descricao", TEXTO), ("aprovada", LOGICO), ("proposta", TEXTO),
            ("tipo_proposta", TEXTO), ("ementa", TEXTO), ("temas", TEXTO), ("sim", INTEIRO), ("nao", INTEIRO), ("placar_oficial_sim", INTEIRO),
            ("placar_oficial_nao", INTEIRO), ("proposta_original", LINK), ("fonte_oficial", LINK), ("pagina_no_site", LINK)], g_votacoes),
    Tabela("votos", "2 Votações", "Como cada político votou em cada votação.", "https://dadosabertos.camara.leg.br/api/v2/votacoes",
           [("votacao_id", TEXTO), ("politico_id", TEXTO), ("partido", TEXTO), ("uf", TEXTO), ("voto", TEXTO)], g_votos),
    Tabela("orientacoes", "2 Votações", "Como cada partido, bloco e o governo mandou votar.", "https://dadosabertos.camara.leg.br/api/v2/votacoes",
           [("votacao_id", TEXTO), ("partido_ou_bloco", TEXTO), ("orientacao", TEXTO)], g_orientacoes),
    Tabela("votos_por_lado", "2 Votações", "Votos somados por lado: esquerda, centro e direita.", "https://dadosabertos.camara.leg.br/api/v2/votacoes",
           [("votacao_id", TEXTO), ("lado", TEXTO), ("voto", TEXTO), ("quantidade", INTEIRO)], g_votos_lado),
    Tabela("temas_voto", "2 Votações", "Quantas vezes cada político votou Sim e Não por tema, e contra o próprio partido.",
           "https://dadosabertos.camara.leg.br/api/v2/votacoes",
           [("politico_id", TEXTO), ("tema", TEXTO), ("sim", INTEIRO), ("nao", INTEIRO), ("outros", INTEIRO), ("contra_o_partido", INTEIRO)], g_temas_voto),
    Tabela("partidos", "3 Partidos", "Cada partido: membros, lado, alinhamento com o governo, fidelidade e gasto.", SITE,
           [("casa", TEXTO), ("partido", TEXTO), ("membros", INTEIRO), ("posicao_esquerda_direita", DECIMAL), ("alinhamento_governo", DECIMAL),
            ("fidelidade", DECIMAL), ("gasto_cota_total", DECIMAL)], g_partidos),
    Tabela("partidos_ano", "3 Partidos", "Gasto de cada partido por ano e por membro.", SITE,
           [("casa", TEXTO), ("partido", TEXTO), ("ano", INTEIRO), ("membros", INTEIRO), ("cota", DECIMAL), ("cota_por_membro", DECIMAL),
            ("custo_total", DECIMAL), ("custo_por_membro", DECIMAL)], g_partidos_ano),
    Tabela("empresas", "4 Empresas e donos", "Empresas que receberam dinheiro público: cota, emendas, governo e renúncia fiscal.",
           "https://minhareceita.org",
           [("cnpj", TEXTO), ("nome", TEXTO), ("nome_fantasia", TEXTO), ("situacao", TEXTO), ("abertura", DATA), ("atividade", TEXTO),
            ("municipio", TEXTO), ("uf", TEXTO), ("capital_social", DECIMAL), ("porte", TEXTO), ("natureza", TEXTO), ("recebido_cota", DECIMAL),
            ("politicos_que_pagaram", INTEIRO), ("recebido_emendas", DECIMAL), ("recebido_governo", DECIMAL), ("renuncia_fiscal", DECIMAL),
            ("empresas_no_mesmo_endereco", INTEIRO), ("tem_holding", LOGICO), ("alertas", TEXTO), ("portal_da_transparencia", LINK),
            ("pagina_no_site", LINK)], g_empresas),
    Tabela("socios", "4 Empresas e donos", "Sócios de cada empresa (CPF mascarado, como a Receita publica).", "https://minhareceita.org",
           [("cnpj", TEXTO), ("socio", TEXTO), ("documento_socio", TEXTO), ("qualificacao", TEXTO), ("entrada", DATA), ("faixa_etaria", TEXTO),
            ("tipo", TEXTO), ("outras_empresas", INTEIRO)], g_socios),
    Tabela("socios_outras_empresas", "4 Empresas e donos", "Outras empresas dos mesmos donos e quanto elas receberam.", "https://minhareceita.org",
           [("cnpj", TEXTO), ("socio", TEXTO), ("outra_cnpj", TEXTO), ("outra_nome", TEXTO), ("outra_recebeu_cota", DECIMAL),
            ("outra_recebeu_emendas", DECIMAL), ("outra_recebeu_governo", DECIMAL), ("outra_renuncia_fiscal", DECIMAL),
            ("portal_da_transparencia", LINK)], g_socios_outras),
    Tabela("donos_finais", "4 Empresas e donos", "Dono final de cada empresa, seguindo a cadeia de empresas sócias.", "https://minhareceita.org",
           [("cnpj", TEXTO), ("dono_final", TEXTO), ("documento", TEXTO), ("tipo", TEXTO), ("qualificacao", TEXTO), ("pais", TEXTO),
            ("como_termina", TEXTO), ("camadas", INTEIRO), ("cadeia", TEXTO), ("outras_empresas", INTEIRO)], g_donos_finais),
    Tabela("empresa_pagadores", "4 Empresas e donos", "Quais políticos pagaram cada empresa com a cota.", "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("cnpj", TEXTO), ("politico_id", TEXTO), ("nome", TEXTO), ("partido", TEXTO), ("uf", TEXTO), ("valor", DECIMAL)], g_pagadores),
    Tabela("empresas_mesmo_endereco", "4 Empresas e donos", "Empresas registradas no mesmo endereço.", "https://minhareceita.org",
           [("cnpj", TEXTO), ("outra_cnpj", TEXTO), ("outra_nome", TEXTO), ("mesmos_socios", LOGICO), ("outra_recebeu_cota", DECIMAL)], g_mesmo_endereco),
    Tabela("notas_empresas", "4 Empresas e donos", "Cada nota fiscal paga com a cota às empresas com página no site, com o link da nota.",
           "https://dadosabertos.camara.leg.br/swagger/api.html",
           [("cnpj", TEXTO), ("data", DATA), ("politico_id", TEXTO), ("categoria", TEXTO), ("valor", DECIMAL), ("nota_original", LINK)], g_notas_empresas),
    Tabela("emendas_autores", "5 Emendas", "Emendas parlamentares por autor: empenhado, pago e emenda Pix.",
           "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("ano", INTEIRO), ("autor", TEXTO), ("politico_id", TEXTO), ("partido", TEXTO), ("uf", TEXTO), ("casa", TEXTO), ("tipo", TEXTO),
            ("emendas", INTEIRO), ("empenhado", DECIMAL), ("pago", DECIMAL), ("pago_emenda_pix", DECIMAL), ("fonte_oficial", LINK)], g_emendas_autores),
    Tabela("emendas_area", "5 Emendas", "Emendas por área (saúde, educação...).", "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("ano", INTEIRO), ("area", TEXTO), ("empenhado", DECIMAL), ("pago", DECIMAL)], g_emendas_area),
    Tabela("emendas_tipo", "5 Emendas", "Emendas por tipo: individual, Pix, bancada, comissão, relator.",
           "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("ano", INTEIRO), ("tipo", TEXTO), ("emendas", INTEIRO), ("empenhado", DECIMAL), ("pago", DECIMAL)], g_emendas_tipo),
    Tabela("emendas_partido", "5 Emendas", "Emendas por partido.", "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("ano", INTEIRO), ("partido", TEXTO), ("emendas", INTEIRO), ("empenhado", DECIMAL), ("pago", DECIMAL), ("pago_emenda_pix", DECIMAL)], g_emendas_partido),
    Tabela("emendas_favorecidos", "5 Emendas", "Quem recebeu o dinheiro das emendas: prefeituras, entidades, empresas.",
           "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("ano", INTEIRO), ("documento", TEXTO), ("favorecido", TEXTO), ("categoria", TEXTO), ("natureza", TEXTO), ("uf", TEXTO),
            ("municipio", TEXTO), ("valor", DECIMAL), ("autores", TEXTO), ("portal_da_transparencia", LINK)], g_emendas_favorecidos),
    Tabela("emendas_municipios", "5 Emendas", "Dinheiro de emendas por município.", "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("ano", INTEIRO), ("municipio", TEXTO), ("uf", TEXTO), ("valor", DECIMAL), ("favorecidos", INTEIRO)], g_emendas_municipios),
    Tabela("emendas_pagamentos", "5 Emendas", "Cada pagamento de emenda, com o link do documento no Portal da Transparência.",
           "https://portaldatransparencia.gov.br/download-de-dados/despesas",
           [("ano", INTEIRO), ("autor", TEXTO), ("data", DATA), ("orgao", TEXTO), ("unidade", TEXTO), ("favorecido", TEXTO), ("cnpj", TEXTO),
            ("valor", DECIMAL), ("descricao", TEXTO), ("documento", TEXTO), ("pagamento_original", LINK), ("empenho_original", LINK)], g_emendas_pagamentos),
    Tabela("governo_pagamentos", "6 Incentivos", "Empresas e entidades que mais receberam pagamentos do governo federal.",
           "https://portaldatransparencia.gov.br/download-de-dados/despesas",
           [("ano", INTEIRO), ("cnpj", TEXTO), ("nome", TEXTO), ("tipo", TEXTO), ("uf", TEXTO), ("valor", DECIMAL), ("pagamentos", INTEIRO),
            ("categorias", TEXTO), ("orgaos", TEXTO), ("donos", TEXTO), ("outras_empresas_dos_donos", INTEIRO), ("portal_da_transparencia", LINK)], g_governo_pagamentos),
    Tabela("governo_orgaos", "6 Incentivos", "Pagamentos do governo federal por órgão.", "https://portaldatransparencia.gov.br/download-de-dados/despesas",
           [("ano", INTEIRO), ("orgao", TEXTO), ("valor", DECIMAL)], g_governo_orgaos),
    Tabela("renuncia_empresas", "6 Incentivos", "Empresas que mais deixaram de pagar impostos (renúncia fiscal).",
           "https://portaldatransparencia.gov.br/download-de-dados/renuncias",
           [("ano", INTEIRO), ("cnpj", TEXTO), ("nome", TEXTO), ("tipo", TEXTO), ("uf", TEXTO), ("municipio", TEXTO), ("setor", TEXTO),
            ("atividade", TEXTO), ("valor", DECIMAL), ("beneficios", TEXTO), ("donos", TEXTO), ("ano_parcial", LOGICO),
            ("portal_da_transparencia", LINK), ("fonte_oficial", LINK)], g_renuncia_empresas),
    Tabela("renuncia_beneficios", "6 Incentivos", "Renúncia fiscal por benefício e imposto.", "https://portaldatransparencia.gov.br/download-de-dados/renuncias",
           [("ano", INTEIRO), ("beneficio", TEXTO), ("tributo", TEXTO), ("valor", DECIMAL), ("empresas", INTEIRO)], g_renuncia_beneficios),
    Tabela("renuncia_setores", "6 Incentivos", "Renúncia fiscal por setor da economia.", "https://portaldatransparencia.gov.br/download-de-dados/renuncias",
           [("ano", INTEIRO), ("setor", TEXTO), ("valor", DECIMAL), ("empresas", INTEIRO)], g_renuncia_setores),
    Tabela("brasil_serie", "7 Dinheiro do Brasil", "Arrecadação e gastos do governo federal, ano a ano.", "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("ano", INTEIRO), ("ano_parcial", LOGICO), ("ate", TEXTO), ("impostos", DECIMAL), ("receita_propria", DECIMAL), ("divida_nova", DECIMAL),
            ("rolagem_da_divida", DECIMAL), ("despesa", DECIMAL), ("pessoal", DECIMAL), ("juros", DECIMAL), ("inss", DECIMAL),
            ("investimentos", DECIMAL), ("administracao_geral", DECIMAL), ("arrecadacao_receita_federal", DECIMAL), ("fonte_oficial", LINK)], g_fin_serie),
    Tabela("brasil_receitas", "7 Dinheiro do Brasil", "Receitas do governo federal (RREO, Tesouro).", "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("ano", INTEIRO), ("receita", TEXTO), ("tipo", TEXTO), ("valor", DECIMAL), ("previsto", DECIMAL), ("explicacao", TEXTO), ("fonte_oficial", LINK)], g_fin_receitas),
    Tabela("brasil_despesas", "7 Dinheiro do Brasil", "Despesas do governo federal por grupo (RREO, Tesouro).", "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("ano", INTEIRO), ("despesa", TEXTO), ("empenhado", DECIMAL), ("liquidado", DECIMAL), ("pago", DECIMAL), ("dotacao", DECIMAL),
            ("explicacao", TEXTO), ("fonte_oficial", LINK)], g_fin_despesas),
    Tabela("brasil_funcoes", "7 Dinheiro do Brasil", "Gasto por área (saúde, educação, previdência...).", "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("ano", INTEIRO), ("funcao", TEXTO), ("liquidado", DECIMAL), ("dotacao", DECIMAL), ("explicacao", TEXTO), ("fonte_oficial", LINK)], g_fin_funcoes),
    Tabela("brasil_tributos", "7 Dinheiro do Brasil", "Arrecadação por imposto (Receita Federal).",
           "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao",
           [("ano", INTEIRO), ("grupo", TEXTO), ("tributo", TEXTO), ("valor", DECIMAL), ("ate_mes", INTEIRO), ("fonte_oficial", LINK)], g_fin_tributos),
    Tabela("brasil_arrecadacao_uf", "7 Dinheiro do Brasil", "Arrecadação federal por estado.",
           "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao",
           [("ano", INTEIRO), ("uf", TEXTO), ("arrecadacao", DECIMAL)], g_fin_uf),
    Tabela("brasil_orgaos", "7 Dinheiro do Brasil", "Gasto do Executivo por órgão (ministérios).", "https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa",
           [("ano", INTEIRO), ("codigo", TEXTO), ("orgao", TEXTO), ("realizado", DECIMAL), ("orcamento_atualizado", DECIMAL), ("fonte_oficial", LINK)], g_fin_orgaos),
    Tabela("brasil_programas", "7 Dinheiro do Brasil", "Gasto do Executivo por programa.", "https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa",
           [("ano", INTEIRO), ("codigo", TEXTO), ("programa", TEXTO), ("funcao", TEXTO), ("realizado", DECIMAL), ("orcamento_atualizado", DECIMAL),
            ("fonte_oficial", LINK)], g_fin_programas),
    Tabela("brasil_pessoal_poderes", "7 Dinheiro do Brasil", "Gasto com pessoal de cada Poder e o limite da Lei de Responsabilidade Fiscal.",
           "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("ano", INTEIRO), ("poder", TEXTO), ("quadrimestre", INTEIRO), ("orgao", TEXTO), ("despesa_bruta", DECIMAL), ("ativos", DECIMAL),
            ("inativos", DECIMAL), ("despesa_total_pessoal", DECIMAL), ("pct_da_receita", DECIMAL), ("limite_maximo", DECIMAL), ("fonte_oficial", LINK)], g_fin_pessoal_poderes),
    Tabela("brasil_indicadores", "7 Dinheiro do Brasil", "Sinais de alerta das contas (verde, amarelo, vermelho).", "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("ano", INTEIRO), ("indicador", TEXTO), ("valor", DECIMAL), ("formato", TEXTO), ("situacao", TEXTO), ("regra", TEXTO),
            ("explicacao", TEXTO), ("fonte_oficial", LINK)], g_fin_indicadores),
    Tabela("projetos_andamento", "8 Projetos em andamento", "Projetos de lei e PECs em andamento na Câmara, no Senado e na ALMG.",
           "https://dadosabertos.camara.leg.br/api/v2/proposicoes",
           [("projeto_id", TEXTO), ("casa", TEXTO), ("proposta", TEXTO), ("tipo", TEXTO), ("ementa", TEXTO), ("resumo", TEXTO), ("apresentada", DATA),
            ("atualizada", DATA), ("situacao", TEXTO), ("onde_esta", TEXTO), ("etapa", TEXTO), ("regime", TEXTO), ("temas", TEXTO), ("autores", INTEIRO),
            ("primeiro_autor", TEXTO), ("proxima_pauta", DATA), ("prazo", DATA), ("tranca_a_pauta", LOGICO), ("grupos", TEXTO),
            ("proposta_original", LINK), ("texto_original", LINK)], g_projetos),
    Tabela("projetos_autores", "8 Projetos em andamento", "Autores de cada projeto em andamento.", "https://dadosabertos.camara.leg.br/api/v2/proposicoes",
           [("projeto_id", TEXTO), ("autor", TEXTO), ("partido", TEXTO), ("uf", TEXTO), ("politico_id", TEXTO)], g_projetos_autores),
    Tabela("verificacao", "0 Sobre os dados", "Conferência independente dos números do site com a fonte oficial.", SITE + "#/verificacao",
           [("data", DATA), ("secao", TEXTO), ("checagem", TEXTO), ("status", TEXTO), ("conferidos", INTEIRO), ("divergentes", INTEIRO),
            ("nao_conferidos", INTEIRO), ("como_conferimos", TEXTO), ("fonte_oficial", LINK)], g_verificacao),
    Tabela("mg_deputados_estaduais", "9 Minas Gerais", "Deputados estaduais de Minas Gerais (ALMG).", "https://dadosabertos.almg.gov.br/",
           [("deputado_id", TEXTO), ("nome", TEXTO), ("partido", TEXTO), ("pagina_oficial", LINK), ("verba_oficial", LINK), ("pagina_no_site", LINK)], g_mg_deputados),
    Tabela("mg_deputados_ano", "9 Minas Gerais", "Verba indenizatória, projetos e emendas de cada deputado estadual por ano.", "https://dadosabertos.almg.gov.br/",
           [("deputado_id", TEXTO), ("ano", INTEIRO), ("verba_indenizatoria", DECIMAL), ("projetos", INTEIRO), ("requerimentos", INTEIRO), ("aprovadas", INTEIRO),
            ("emendas_indicado", DECIMAL), ("emendas_pago", DECIMAL)], g_mg_deputados_ano),
    Tabela("mg_verba_notas", "9 Minas Gerais", "Cada nota da verba indenizatória dos deputados estaduais.", "https://dadosabertos.almg.gov.br/",
           [("deputado_id", TEXTO), ("ano", INTEIRO), ("data", DATA), ("tipo", TEXTO), ("fornecedor", TEXTO), ("cnpj_cpf", TEXTO), ("pessoa_fisica", LOGICO),
            ("valor", DECIMAL), ("fonte_oficial", LINK)], g_mg_verba_notas),
    Tabela("mg_verba_fornecedores", "9 Minas Gerais", "Fornecedores pagos com a verba indenizatória.", "https://dadosabertos.almg.gov.br/",
           [("deputado_id", TEXTO), ("ano", INTEIRO), ("fornecedor", TEXTO), ("cnpj_cpf", TEXTO), ("pessoa_fisica", LOGICO), ("valor", DECIMAL), ("n_notas", INTEIRO)],
           g_mg_verba_fornecedores),
    Tabela("mg_proposicoes", "9 Minas Gerais", "Projetos e requerimentos dos deputados estaduais.", "https://dadosabertos.almg.gov.br/",
           [("deputado_id", TEXTO), ("ano", INTEIRO), ("proposta", TEXTO), ("ementa", TEXTO), ("situacao", TEXTO), ("aprovada", LOGICO), ("data", DATA),
            ("proposta_original", LINK)], g_mg_proposicoes),
    Tabela("mg_emendas_municipios", "9 Minas Gerais", "Emendas estaduais por município.", "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/",
           [("ano", INTEIRO), ("municipio", TEXTO), ("indicado", DECIMAL), ("pago", DECIMAL), ("emendas", INTEIRO), ("fonte_oficial", LINK)], g_mg_emendas_municipios),
    Tabela("mg_emendas_autores", "9 Minas Gerais", "Emendas estaduais por deputado.", "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/",
           [("ano", INTEIRO), ("autor", TEXTO), ("deputado_id", TEXTO), ("indicado", DECIMAL), ("pago", DECIMAL), ("emendas", INTEIRO), ("fonte_oficial", LINK)],
           g_mg_emendas_autores),
    Tabela("mg_governo_eleicoes", "9 Minas Gerais", "Eleições para governador de Minas Gerais.", "https://dadosabertos.tse.jus.br/",
           [("eleicao", INTEIRO), ("mandato", TEXTO), ("candidato", TEXTO), ("partido", TEXTO), ("votos", INTEIRO), ("pct_votos", DECIMAL), ("eleito", LOGICO),
            ("fonte_oficial", LINK)], g_mg_governo_eleicoes),
    Tabela("mg_governo_equipe", "9 Minas Gerais", "Governador, vice e secretários: salário e viagens.", "https://www.transparencia.mg.gov.br/",
           [("nome", TEXTO), ("cargo", TEXTO), ("orgao", TEXTO), ("mes", TEXTO), ("salario_bruto", DECIMAL), ("descontos", DECIMAL), ("salario_liquido", DECIMAL),
            ("jetons", DECIMAL), ("viagens", INTEIRO), ("gasto_viagens", DECIMAL), ("fonte_oficial", LINK)], g_mg_governo_equipe),
    Tabela("mg_cidades", "9 Minas Gerais", "Cidades acompanhadas, com prefeito e câmara.", "https://dadosabertos.tse.jus.br/",
           [("cidade_id", TEXTO), ("cidade", TEXTO), ("uf", TEXTO), ("prefeito", TEXTO), ("partido_prefeito", TEXTO), ("desde", INTEIRO), ("vereadores", INTEIRO),
            ("pagina_no_site", LINK)], g_mg_cidades),
    Tabela("mg_cidades_emendas_federais", "9 Minas Gerais", "Emendas federais que chegaram a cada cidade.",
           "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares",
           [("cidade_id", TEXTO), ("favorecido", TEXTO), ("cnpj", TEXTO), ("valor", DECIMAL), ("anos", TEXTO), ("autores", TEXTO), ("fonte_oficial", LINK)],
           g_mg_cidades_emendas_federais),
    Tabela("mg_cidades_contas", "9 Minas Gerais", "Gasto de cada prefeitura por área (Siconfi).", "https://apidatalake.tesouro.gov.br/docs/siconfi/",
           [("cidade_id", TEXTO), ("ano", INTEIRO), ("funcao", TEXTO), ("empenhado", DECIMAL), ("liquidado", DECIMAL), ("pago", DECIMAL), ("fonte_oficial", LINK)],
           g_mg_cidades_contas),
    Tabela("eleicao2026_candidatos", "10 Eleição 2026", "Votos de cada candidato a presidente, por estado e turno (TSE).", "https://resultados.tse.jus.br/",
           [("turno", INTEIRO), ("uf", TEXTO), ("candidato", TEXTO), ("numero", TEXTO), ("partido", TEXTO), ("coligacao", TEXTO), ("votos", INTEIRO),
            ("pct_validos", DECIMAL), ("situacao", TEXTO), ("fonte_oficial", LINK)], g_eleicao_candidatos),
    Tabela("eleicao2026_comparecimento", "10 Eleição 2026", "Eleitores, comparecimento, abstenção, brancos e nulos por estado e turno (TSE).",
           "https://resultados.tse.jus.br/",
           [("turno", INTEIRO), ("uf", TEXTO), ("eleitores", INTEIRO), ("compareceram", INTEIRO), ("abstencoes", INTEIRO), ("votos_validos", INTEIRO),
            ("brancos", INTEIRO), ("nulos", INTEIRO), ("secoes_apuradas_pct", DECIMAL), ("fonte_oficial", LINK)], g_eleicao_comparecimento),
]


def _colunas_terras(arquivo: str) -> list[tuple[str, str]]:
    caminho = Path(__file__).resolve().parent.parent / "terras-raras" / "dados" / arquivo
    cols = _cabecalho_csv(caminho) if caminho.exists() else []
    return [(c, LINK if c.endswith("_url") else TEXTO) for c in cols]


for _nome, (_arq, _desc) in TERRAS.items():
    TABELAS.append(Tabela(_nome, "11 Terras raras", _desc + " Planilha conferida à mão, cada linha com o link da fonte.",
                          "https://github.com/amarigo/segredos-abertos/tree/main/terras-raras/dados", _colunas_terras(_arq), _gerar_terras(_arq)))


# ---------------------------------------------------------------- escrita


def _valor(v: Any, tipo: str) -> str:
    if v is None:
        return ""
    if tipo == LOGICO:
        return "true" if v in (True, "true", "True", 1) else "false"
    if tipo == INTEIRO:
        try:
            return str(int(v))
        except (TypeError, ValueError):
            return ""
    if tipo == DECIMAL:
        try:
            return repr(float(v))
        except (TypeError, ValueError):
            return ""
    if tipo == DATA:
        return _data(v) or ""
    return str(v).replace("\r", " ").replace("\n", " ")


def exportar(d: Dados, saida: Path) -> dict[str, int]:
    saida.mkdir(parents=True, exist_ok=True)
    contagem: dict[str, int] = {}
    for t in TABELAS:
        nomes = [c for c, _ in t.colunas]
        tipos = dict(t.colunas)
        n = 0
        with (saida / f"{t.nome}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(nomes)
            for linha in t.gerar(d):
                w.writerow([_valor(linha.get(c), tipos[c]) for c in nomes])
                n += 1
        contagem[t.nome] = n
    catalogo = {
        "gerado_por": "analises/tabelas.py",
        "atualizado_em": ((d.n("meta.json") or {}).get("atualizado_em")),
        "tabelas": [{"nome": t.nome, "grupo": t.grupo, "descricao": t.descricao, "fonte": t.fonte, "linhas": contagem[t.nome],
                     "arquivo": f"{t.nome}.csv", "colunas": [{"nome": c, "tipo": k} for c, k in t.colunas]} for t in TABELAS],
    }
    (saida / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    return contagem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nacional", type=Path, help="pasta de dados do Segredos Abertos (site/public/data)")
    ap.add_argument("--mg", type=Path, help="pasta de dados do Minas Nossa (site/public-mg/data)")
    ap.add_argument("--eleicao", type=Path, help="pasta com os resultados do TSE (eleicao2026/dados/tse)")
    ap.add_argument("--terras", type=Path, help="pasta das planilhas de Terras Raras (terras-raras/dados)")
    ap.add_argument("--saida", type=Path, required=True)
    a = ap.parse_args(argv)
    contagem = exportar(Dados(a.nacional, a.mg, a.eleicao, a.terras), a.saida)
    total = sum(contagem.values())
    print(f"Análises: {len(contagem)} tabelas, {total:,} linhas em {a.saida}".replace(",", "."))
    vazias = [k for k, v in contagem.items() if v == 0]
    if vazias:
        print("Tabelas sem linhas (o dado não veio nesta coleta): " + ", ".join(vazias))
    return 0


if __name__ == "__main__":
    sys.exit(main())
