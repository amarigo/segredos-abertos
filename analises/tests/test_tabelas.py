"""Testes do painel de análises: as tabelas saem certas a partir dos arquivos do site."""
import csv
import json
import re
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "analises"))

import publicar  # noqa: E402
from tabelas import TABELAS, Dados, exportar  # noqa: E402


def _json(p: Path, dado) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dado, ensure_ascii=False), encoding="utf-8")


def _ler(pasta: Path, nome: str) -> list[dict]:
    with (pasta / f"{nome}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _nacional(base: Path) -> Path:
    d = base / "data"
    _json(d / "meta.json", {"atualizado_em": "2026-11-02", "contagens": {"politicos": 2, "despesas": 3, "votacoes": 1, "empresas_com_socios": 1},
                            "total_gasto": 300.5, "avisos": []})
    pol = [
        {"id": "dep-1", "casa": "camara", "cargo": "Deputado(a) Federal", "nome": "Ana", "partido": "PT", "uf": "SP", "foto": "", "fonte": "https://www.camara.leg.br/deputados/1",
         "total": 200.5, "rotulo": "Esquerda", "posicao": 0.2, "campo": "Governo", "alinhamento_governo": 0.9, "fidelidade_partido": 0.95, "n_votos": 1,
         "por_ano": {"2025": {"total": 200.5, "grupos": {"pessoal": 100, "escritorio": 50.5, "servicos": 50}, "custo_total": 200.5}}},
        {"id": "sen-2", "casa": "senado", "cargo": "Senador(a)", "nome": "Bia", "partido": "PL", "uf": "MG", "foto": "", "fonte": "https://www25.senado.leg.br/web/senadores/senador/-/perfil/2",
         "total": 100, "rotulo": "Direita", "posicao": 0.8, "campo": "Oposição", "alinhamento_governo": 0.1, "fidelidade_partido": 0.9, "n_votos": 1,
         "por_ano": {"2025": {"total": 100, "grupos": {"pessoal": 100, "escritorio": 0, "servicos": 0}, "custo_total": 100}}},
    ]
    _json(d / "politicos.json", pol)
    _json(d / "p" / "dep-1.json", {**pol[0], "anos": {"2025": {
        "categorias": [{"categoria": "Passagens", "grupo": "pessoal", "valor": 100}],
        "meses": [{"mes": 3, "valor": 200.5}],
        "fornecedores": [{"doc": "11222333000181", "tipo": "cnpj", "nome": "Posto, \"Bom\" Ltda", "valor": 150, "n": 2, "ficha": True, "socios": ["JOSE"]}],
        "maiores_notas": [{"data": "2025-03-05", "categoria": "Passagens", "fornecedor": "Posto", "doc": "11222333000181", "valor": 150,
                           "url": "https://www.camara.leg.br/cota-parlamentar/documentos/publ/1/2025/1.pdf"}],
        "recursos": None}}, "votos": [], "temas": {"Saúde": {"Sim": 2, "Não": 1, "contra_partido": 1}}})
    _json(d / "votacoes.json", [{"id": "cd-1", "casa": "camara", "data": "2025-05-01T10:00", "descricao": "Aprovado o PL 1", "aprovada": True,
                                 "proposicao": {"sigla": "PL", "numero": "1", "ano": "2025", "ementa": "Dispõe\nsobre algo", "titulo": "PL 1/2025",
                                                "url": "https://www.camara.leg.br/propostas-legislativas/1"}, "sim": 1, "nao": 1, "temas": ["Saúde"]}])
    _json(d / "v" / "cd-1.json", {"id": "cd-1", "fonte": "https://dadosabertos.camara.leg.br/api/v2/votacoes/1", "orientacoes": {"Governo": "Sim", "PL": "Não"},
                                  "por_lado": {"Esquerda": {"Sim": 1}, "Direita": {"Não": 1}},
                                  "votos": [{"politico": "dep-1", "partido": "PT", "uf": "SP", "voto": "Sim"}, {"politico": "sen-2", "partido": "PL", "uf": "MG", "voto": "Não"}]})
    _json(d / "partidos.json", [{"casa": "camara", "sigla": "PT", "n": 1, "posicao": 0.2, "alinhamento_governo": 0.9, "fidelidade": 0.95, "total": 200.5,
                                 "por_ano": {"2025": {"n": 1, "cota": 200.5, "cota_por_membro": 200.5, "custo_total": 200.5, "custo_por_membro": 200.5}}}])
    _json(d / "empresas.json", [{"cnpj": "11222333000181", "nome": "Posto Bom Ltda", "total": 150, "n_politicos": 1, "tem_socios": True},
                                {"cnpj": "99888777000166", "nome": "Sem Página SA", "total": 10, "n_politicos": 1, "tem_socios": False}])
    _json(d / "e" / "11222333000181.json", {"cnpj": "11222333000181", "nome": "Posto Bom Ltda", "total": 150, "n_politicos": 1,
                                            "empresa": {"razao_social": "Posto Bom Ltda", "abertura": "2001-02-03", "uf": "MG", "capital_social": 1000},
                                            "socios": [{"nome": "JOSE", "doc": "***111222**", "qualificacao": "Sócio", "outras_empresas": [
                                                {"cnpj": "55444333000122", "nome": "Outra do José", "total": 0, "emendas": 5000}]}],
                                            "donos_finais": [], "pagadores": [{"politico": "dep-1", "nome": "Ana", "partido": "PT", "uf": "SP", "valor": 150}],
                                            "emendas": {"total": 5000}, "governo": None, "renuncia": None, "alertas": []})
    _json(d / "e" / "notas" / "11222333000181-2025.json", [["2025-03-05", "dep-1", "Passagens", 150, "https://www.camara.leg.br/x.pdf", "nota", ""]])
    _json(d / "emendas" / "2025.json", {"ano": 2025, "fonte": "https://portaldatransparencia.gov.br/emendas",
                                        "autores": [{"nome": "Ana", "politico": "dep-1", "partido": "PT", "uf": "SP", "casa": "camara", "n": 1, "empenhado": 10, "pago": 7, "pix": 7}],
                                        "coletivos": [{"nome": "Bancada de SP", "tipo": "bancada", "n": 1, "empenhado": 5, "pago": 2}],
                                        "por_area": [{"area": "Saúde", "empenhado": 15, "pago": 9}], "por_tipo": [], "partidos": [],
                                        "favorecidos": {"lista": [{"doc": "46395000000139", "nome": "Município de São Paulo", "valor": 7, "autores": [["Ana", 7]]}], "municipios": []}})
    _json(d / "financas" / "indice.json", {"serie": [{"ano": 2025, "parcial": False, "impostos": 10.0, "despesa": 20.0}], "fontes": {"siconfi": "https://apidatalake.tesouro.gov.br/docs/siconfi/"}})
    return d


def _exportar(tmp_path: Path) -> Path:
    d = _nacional(tmp_path)
    saida = tmp_path / "out"
    exportar(Dados(d, None, RAIZ / "eleicao2026" / "dados" / "tse", RAIZ / "terras-raras" / "dados"), saida)
    return saida


def test_todas_as_tabelas_saem_com_cabecalho(tmp_path):
    saida = tmp_path / "vazio"
    contagem = exportar(Dados(None, None, None, None), saida)
    assert set(contagem) == {t.nome for t in TABELAS}
    for t in TABELAS:
        with (saida / f"{t.nome}.csv").open(encoding="utf-8") as f:
            assert next(csv.reader(f)) == [c for c, _ in t.colunas]


def test_nomes_e_tipos_de_colunas(tmp_path):
    tipos = {"texto", "inteiro", "decimal", "data", "logico", "link"}
    nomes = [t.nome for t in TABELAS]
    assert len(nomes) == len(set(nomes))
    for t in TABELAS:
        assert re.fullmatch(r"[a-z0-9_]+", t.nome)
        assert t.fonte.startswith("https://"), t.nome
        assert t.colunas, t.nome
        for c, k in t.colunas:
            assert k in tipos, (t.nome, c)


def test_gastos_somam_igual_ao_site(tmp_path):
    saida = _exportar(tmp_path)
    custos = _ler(saida, "custos_ano")
    assert round(sum(float(r["cota_total"]) for r in custos), 2) == 300.5  # igual ao total_gasto do meta.json
    pol = {r["politico_id"]: r for r in _ler(saida, "politicos")}
    assert pol["dep-1"]["lado"] == "Esquerda" and pol["sen-2"]["governo_ou_oposicao"] == "Oposição"
    assert pol["dep-1"]["pagina_no_site"] == "https://amarigo.github.io/segredos-abertos/#/p/dep-1"


def test_aspas_virgulas_e_quebras_de_linha(tmp_path):
    saida = _exportar(tmp_path)
    forn = _ler(saida, "fornecedores")
    assert forn[0]["fornecedor"] == 'Posto, "Bom" Ltda'
    vot = _ler(saida, "votacoes")
    assert vot[0]["ementa"] == "Dispõe sobre algo" and vot[0]["data"] == "2025-05-01" and vot[0]["aprovada"] == "true"


def test_votos_orientacoes_e_lados(tmp_path):
    saida = _exportar(tmp_path)
    assert {(r["politico_id"], r["voto"]) for r in _ler(saida, "votos")} == {("dep-1", "Sim"), ("sen-2", "Não")}
    assert {(r["partido_ou_bloco"], r["orientacao"]) for r in _ler(saida, "orientacoes")} == {("Governo", "Sim"), ("PL", "Não")}
    assert sum(int(r["quantidade"]) for r in _ler(saida, "votos_por_lado")) == 2


def test_empresas_socios_e_outras_empresas_dos_donos(tmp_path):
    saida = _exportar(tmp_path)
    emp = {r["cnpj"]: r for r in _ler(saida, "empresas")}
    assert set(emp) == {"11222333000181", "99888777000166"}  # inclusive a que não tem página própria
    assert emp["11222333000181"]["recebido_emendas"] == "5000.0"
    assert emp["11222333000181"]["portal_da_transparencia"] == "https://portaldatransparencia.gov.br/pessoa-juridica/11222333000181"
    assert _ler(saida, "socios")[0]["documento_socio"] == "***111222**"  # CPF continua mascarado
    outras = _ler(saida, "socios_outras_empresas")
    assert outras[0]["outra_nome"] == "Outra do José" and outras[0]["outra_recebeu_emendas"] == "5000.0"
    assert _ler(saida, "notas_empresas")[0]["politico_id"] == "dep-1"


def test_emendas_individuais_e_coletivas(tmp_path):
    saida = _exportar(tmp_path)
    aut = _ler(saida, "emendas_autores")
    assert {r["tipo"] for r in aut} == {"individual", "bancada"}
    assert round(sum(float(r["pago"]) for r in aut), 2) == 9.0
    assert _ler(saida, "emendas_favorecidos")[0]["autores"] == "Ana"


def test_eleicao_bate_com_o_tse():
    """Os votos por candidato no Brasil somam os votos válidos que o próprio TSE informa."""
    out = {}
    d = Dados(None, None, RAIZ / "eleicao2026" / "dados" / "tse", None)
    t = {x.nome: x for x in TABELAS}
    cand = list(t["eleicao2026_candidatos"].gerar(d))
    comp = {(r["turno"], r["uf"]): r for r in t["eleicao2026_comparecimento"].gerar(d)}
    for turno in (1, 2):
        out[turno] = sum(r["votos"] for r in cand if r["turno"] == turno and r["uf"] == "BR")
        assert out[turno] == comp[(turno, "BR")]["votos_validos"]
    assert all(r["fonte_oficial"].startswith("https://resultados.tse.jus.br/") for r in cand)


def test_terras_raras_mantem_todas_as_colunas_e_linhas(tmp_path):
    saida = _exportar(tmp_path)
    with (RAIZ / "terras-raras" / "dados" / "projetos.csv").open(encoding="utf-8", newline="") as f:
        original = list(csv.DictReader(f))
    assert _ler(saida, "terras_raras_projetos") == original


def test_publicar_monta_pagina_e_zip(tmp_path):
    d = _nacional(tmp_path)
    saida = tmp_path / "site"
    publicar.publicar(Dados(d, None, None, None), saida)
    html = (saida / "index.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "<title>Análises Segredos Abertos</title>" in html
    assert re.search(r'src="https://cdn\.jsdelivr\.net/npm/echarts@\d+\.\d+\.\d+/dist/echarts\.min\.js"', html)  # versão fixa
    with zipfile.ZipFile(saida / "tabelas.zip") as z:
        assert "politicos.csv" in z.namelist() and "catalogo.json" in z.namelist()
    cat = json.loads((saida / "tabelas" / "catalogo.json").read_text(encoding="utf-8"))
    assert cat["atualizado_em"] == "2026-11-02" and len(cat["tabelas"]) == len(TABELAS)


def test_painel_usa_so_tabelas_e_colunas_que_existem():
    """Cada tabela que o painel pede existe no catálogo."""
    html = (RAIZ / "analises" / "painel.html").read_text(encoding="utf-8")
    pedidas = set(re.findall(r'tabela\("([a-z0-9_]+)"\)', html))
    for grupo in re.findall(r'fontes\(([^)]*)\)', html):
        pedidas |= set(re.findall(r'"([a-z0-9_]+)"', grupo))
    existentes = {t.nome for t in TABELAS}
    assert pedidas and pedidas <= existentes, pedidas - existentes
