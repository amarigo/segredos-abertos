"""Imita o Portal de Dados Abertos do TSE (API CKAN e CDN) para sa_etl/campanha.py.

As colunas, o separador (;), a codificação (latin-1), os valores com vírgula, os "#NULO" e os nomes dos arquivos dentro
do ZIP seguem o arquivo "prestacao_de_contas_eleitorais_candidatos_2022.zip" baixado em 10/11/2026. O conjunto de 2022
tem no portal um nome diferente dos outros anos, como no portal de verdade.

Casos de propósito (deputado 00, SP, em 2022):
- doa "DONO FICTICIO 3", com os 6 dígitos do meio do CPF iguais aos do sócio das fornecedoras 3 e 8: liga;
- doa "DONO FICTICIO 4", homônimo de um sócio, mas com outros dígitos: não liga;
- a campanha pagou a fornecedora 5, que a cota do mesmo deputado também pagou: liga;
- um fornecedor pessoa física tem o CPF dentro do nome (acontece no arquivo do TSE): o CPF não pode ir ao site.
O senador 00 é achado pelo nome civil (a API do Senado não tem CPF). O deputado 01 trocou de nome civil depois da
eleição: é achado pelo CPF.
"""
from __future__ import annotations

import io
import json
import zipfile

PORTAL = "dadosabertos.tse.jus.br"
CDN = "cdn.tse.jus.br"
ANOS = (2018, 2022, 2026)
ETAG = {2018: '"e-2018"', 2022: '"e-2022"', 2026: '"e-2026"'}

CAB_REC = ["DT_GERACAO", "HH_GERACAO", "AA_ELEICAO", "CD_ELEICAO", "ST_TURNO", "TP_PRESTACAO_CONTAS", "DT_PRESTACAO_CONTAS",
           "SQ_PRESTADOR_CONTAS", "SG_UF", "NR_CNPJ_PRESTADOR_CONTA", "CD_CARGO", "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO",
           "NM_CANDIDATO", "NR_CPF_CANDIDATO", "SG_PARTIDO", "DS_FONTE_RECEITA", "DS_ORIGEM_RECEITA", "DS_NATUREZA_RECEITA",
           "NR_CPF_CNPJ_DOADOR", "NM_DOADOR", "NM_DOADOR_RFB", "DS_ESFERA_PARTIDARIA_DOADOR", "SG_PARTIDO_DOADOR",
           "SQ_RECEITA", "DT_RECEITA", "DS_RECEITA", "VR_RECEITA"]
CAB_ORI = ["DT_GERACAO", "AA_ELEICAO", "SQ_PRESTADOR_CONTAS", "SG_UF", "NR_CPF_CNPJ_DOADOR_ORIGINARIO", "NM_DOADOR_ORIGINARIO",
           "NM_DOADOR_ORIGINARIO_RFB", "TP_DOADOR_ORIGINARIO", "SQ_RECEITA", "DT_RECEITA", "DS_RECEITA", "VR_RECEITA"]
CAB_DESP = ["DT_GERACAO", "AA_ELEICAO", "TP_PRESTACAO_CONTAS", "SQ_PRESTADOR_CONTAS", "SG_UF", "CD_CARGO", "DS_CARGO",
            "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO", "NR_CPF_CANDIDATO", "SG_PARTIDO", "DS_TIPO_FORNECEDOR",
            "NR_CPF_CNPJ_FORNECEDOR", "NM_FORNECEDOR", "NM_FORNECEDOR_RFB", "DS_ORIGEM_DESPESA", "SQ_DESPESA", "DT_DESPESA",
            "DS_DESPESA", "VR_DESPESA_CONTRATADA"]

CPF_DOADOR_SOCIO = "99910000311"  # meio 100003 = sócio "DONO FICTICIO 3" (***100003**)
CPF_HOMONIMO = "99955555511"  # "DONO FICTICIO 4" na Receita é ***100004**: não pode ligar
CPF_FORNECEDOR_PF = "12345678909"


def cpf_deputado(i: int) -> str:
    return f"{91827364500 + i:011d}"


def nome_civil_deputado(i: int) -> str:
    return f"Deputado Ficticio {i:02d} da Silva"


def nome_civil_senador(i: int) -> str:
    return f"Senador Ficticio {i:02d} de Souza"


def pacote(ano: int) -> str:
    return ("dadosabertos-tse-jus-br-dataset-prestacao-de-contas-eleitorais-2022" if ano == 2022
            else f"prestacao-de-contas-eleitorais-{ano}")


def url_zip(ano: int) -> str:
    return f"https://{CDN}/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip"


def _csv(cab: list[str], linhas: list[list]) -> bytes:
    def campo(x) -> str:
        s = str(x)
        return '"' + s.replace('"', '""') + '"'
    return ("\n".join([";".join(campo(c) for c in cab)] + [";".join(campo(x) for x in li) for li in linhas]) + "\n").encode("latin-1")


def _v(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def montar_zip(ano: int, deputados: list[dict], senadores: list[dict], fornecedoras: list[str]) -> bytes:
    rec, ori, desp = [], [], []
    ger = "08/11/2026"
    sqr = [1000]

    def receita(c: dict, origem: str, fonte: str, doc: str, nome: str, v: float, esfera: str = "#NULO", partido: str = "#NULO",
                natureza: str = "Financeiro") -> str:
        sqr[0] += 1
        rec.append([ger, "15:00:10", ano, "546", "1", "FINAL", f"01/11/{ano}", c["sqp"], c["uf"], c["cnpj"], c["cd"], c["cargo"],
                    c["sq"], c["num"], c["nome"], c["cpf"], c["partido"], fonte, origem, natureza, doc, nome.title(), nome,
                    esfera, partido, sqr[0], f"10/09/{ano}", "#NULO#", _v(v)])
        return str(sqr[0])

    def despesa(c: dict, doc: str, nome: str, tipo: str, v: float) -> None:
        desp.append([ger, ano, "Final", c["sqp"], c["uf"], c["cd"], c["cargo"], c["sq"], c["num"], c["nome"], c["cpf"],
                     c["partido"], "PESSOA JURÍDICA" if len(doc) == 14 else "PESSOA FÍSICA", doc, nome.title(), nome, tipo,
                     len(desp) + 1, f"15/09/{ano}", "#NULO#", _v(v)])

    cands = []
    for i, d in enumerate(deputados[:4]):
        nome = nome_civil_deputado(i).upper()
        if i == 1:
            nome = "DEPUTADO FICTICIO 01 DE SOLTEIRA"  # nome de antes do casamento: só o CPF acha
        cands.append({"sq": f"{ano}0000{i:04d}", "sqp": f"{ano}9{i:04d}", "uf": d["siglaUf"], "cnpj": f"{47414202000143 + i}",
                      "cd": "6", "cargo": "Deputado Federal", "num": f"{1000 + i}", "nome": nome, "cpf": cpf_deputado(i),
                      "partido": d["siglaPartido"], "i": i})
    s0 = senadores[0]
    cands.append({"sq": f"{ano}00005000", "sqp": f"{ano}95000", "uf": s0["uf"], "cnpj": "47414202000999", "cd": "5",
                  "cargo": "Senador", "num": "131", "nome": nome_civil_senador(0).upper(), "cpf": "77700011122",
                  "partido": s0["partido"], "i": "s0"})
    # homônimo de um deputado em outro estado (não pode ser confundido)
    cands.append({"sq": f"{ano}00009999", "sqp": f"{ano}99999", "uf": "AC", "cnpj": "47414202000888", "cd": "6",
                  "cargo": "Deputado Federal", "num": "9999", "nome": nome_civil_deputado(2).upper(), "cpf": "55500011122",
                  "partido": "PP", "i": "homonimo"})
    # candidata a deputada estadual: o cargo 7 não é lido
    cands.append({"sq": f"{ano}00007777", "sqp": f"{ano}97777", "uf": "SP", "cnpj": "47414202000777", "cd": "7",
                  "cargo": "Deputado Estadual", "num": "77777", "nome": "ESTADUAL FICTICIA", "cpf": "44400011122",
                  "partido": "PP", "i": "estadual"})
    for c in cands:
        receita(c, "Recursos de partido político", "FUNDO ESPECIAL", "59933952000100", "PARTIDO FICTICIO DIRETORIO NACIONAL",
                150000.0, "Nacional", c["partido"])
        sq_vaq = receita(c, "Recursos de Financiamento Coletivo", "OUTROS RECURSOS", "11222333000181", "VAQUINHA FICTICIA LTDA", 3000.0)
        receita(c, "Recursos próprios", "OUTROS RECURSOS", c["cpf"], c["nome"], 5000.0)
        receita(c, "Recursos de partido político", "FUNDO PARTIDARIO", "59933952000100", "PARTIDO FICTICIO DIRETORIO NACIONAL",
                1234.56, "Nacional", c["partido"], natureza="Estimado")
        ori.append([ger, ano, c["sqp"], c["uf"], "33344455566", "Apoiadora Da Vaquinha", "APOIADORA DA VAQUINHA", "F", sq_vaq,
                    f"10/09/{ano}", "Recursos de Financiamento Coletivo", _v(3000.0)])
        despesa(c, "60701190000104", "GRAFICA FICTICIA LTDA", "Publicidade por materiais impressos", 40000.0)
        if c["i"] == 0 and ano == 2022:
            receita(c, "Recursos de pessoas físicas", "OUTROS RECURSOS", CPF_DOADOR_SOCIO, "DONO FICTICIO 3", 50000.0)
            receita(c, "Recursos de pessoas físicas", "OUTROS RECURSOS", CPF_DOADOR_SOCIO, "DONO FICTICIO 3", 25000.0)
            receita(c, "Recursos de pessoas físicas", "OUTROS RECURSOS", CPF_HOMONIMO, "DONO FICTICIO 4", 9000.0)
            despesa(c, fornecedoras[5], "FORNECEDORA FICTICIA 05 LTDA", "Despesas com transporte ou deslocamento", 12345.67)
            despesa(c, CPF_FORNECEDOR_PF, f"JOAO FICTICIO {CPF_FORNECEDOR_PF}", "Atividades de militância e mobilização de rua", 800.0)
    arq = io.BytesIO()
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"receitas_candidatos_{ano}_BRASIL.csv", _csv(CAB_REC, rec))
        z.writestr(f"receitas_candidatos_{ano}_SP.csv", _csv(CAB_REC, [r for r in rec if r[8] == "SP"]))  # por UF: não é lido
        z.writestr(f"receitas_candidatos_doador_originario_{ano}_BRASIL.csv", _csv(CAB_ORI, ori))
        z.writestr(f"despesas_contratadas_candidatos_{ano}_BRASIL.csv", _csv(CAB_DESP, desp))
        z.writestr("leiame_receitas-candidatos.pdf", b"%PDF-1.4 leiame")
    return arq.getvalue()


def rota(netloc: str, path: str, q: dict, gov) -> tuple[int, bytes, str] | None:
    if netloc == PORTAL and path == "/api/3/action/package_show":
        pid = q.get("id", "")
        ano = next((a for a in ANOS if pacote(a) == pid), None)
        if ano is None:
            return 404, json.dumps({"success": False, "error": {"message": "Não encontrado"}}).encode(), "application/json"
        return 200, json.dumps({"success": True, "result": {"name": pid, "resources": [
            {"name": "Prestação de contas de órgãos partidários",
             "url": url_zip(ano).replace("candidatos", "orgaos_partidarios")},
            {"name": "Prestação de contas de candidatos", "url": url_zip(ano)}]}}).encode(), "application/json"
    if netloc == CDN and path.startswith("/estatistica/sead/odsele/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_"):
        ano = int(path.rsplit("_", 1)[1].removesuffix(".zip"))
        if ano not in ANOS:
            return 404, b"", "text/html"
        gov.tse_baixados.append(ano)
        return 200, montar_zip(ano, gov.deputados, gov.senadores, gov.fornecedoras), "application/zip"
    return None
