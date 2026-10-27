"""Respostas fictícias (mas coerentes: as partes somam o total) das fontes da aba de arrecadação e gastos.

Ano corrente: Tesouro até o 4º bimestre (agosto) e 2º quadrimestre; Receita até julho; SIAPE de agosto.
Anos anteriores: completos.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import zipfile
from urllib.parse import urlparse

ANO = dt.date.today().year


def _csv(cab, linhas, sep=";") -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, quoting=csv.QUOTE_ALL)
    w.writerow(cab)
    w.writerows(linhas)
    return buf.getvalue()


def _br(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _fator(ano: int) -> float:
    return 1 + (ano - 2019) * 0.06


def _item(ano, per, anexo, conta, nome, coluna, valor, rotulo="Padrão", **extra):
    return {"exercicio": ano, "periodo": per, "instituicao": "Governo Federal", "anexo": anexo, "rotulo": rotulo,
            "coluna": coluna, "cod_conta": conta, "conta": nome, "valor": valor, **extra}


RECEITAS = {"Impostos": 900e9, "Taxas": 10e9, "ContribuicoesSociais": 1100e9, "ContribuicaoDeIntervencaoNoDominioEconomico": 5e9,
            "ReceitaPatrimonial": 150e9, "ReceitaDeServicos": 40e9, "OutrasReceitasCorrentes": 60e9, "AlienacaoDeBens": 2e9,
            "ReceitasDeOperacoesDeCredito": 350e9, "OperacoesDeCreditoRefinanciamento": 1200e9}
DESPESAS = {"PessoalEEncargosSociais": 400e9, "JurosEEncargosDaDivida": 360e9, "BeneficiosPrevidenciarios": 950e9,
            "TransferenciasAEstadosDistritoFederalEMunicipios": 500e9, "DemaisDespesasCorrentes": 450e9, "Investimentos": 60e9,
            "InversoesFinanceiras": 100e9, "AmortizacaoDaDivida": 300e9, "AmortizacaoRefinanciamentoDaDivida": 1200e9}
FUNCOES = [("Legislativa", [("Ação Legislativa", 3e9), ("FU01 - Administração Geral", 9e9)]),
           ("Judiciária", [("Ação Judiciária", 5e9), ("FU02 - Administração Geral", 45e9)]),
           ("Administração", [("FU04 - Administração Geral", 25e9), ("Tecnologia da Informação", 3e9)]),
           ("Assistência Social", [("Assistência ao Idoso", 50e9), ("FU08 - Demais Subfunções", 170e9)]),
           ("Previdência Social", [("Previdência Básica", 950e9), ("Previdência do Regime Estatutário", 150e9)]),
           ("Saúde", [("Atenção Básica", 60e9), ("FU10 - Administração Geral", 20e9), ("Assistência Hospitalar e Ambulatorial", 100e9)]),
           ("Educação", [("Ensino Superior", 50e9), ("FU12 - Administração Geral", 30e9)]),
           ("Encargos Especiais", [("Serviço da Dívida Interna", 660e9), ("Transferências", 500e9)])]


def _per(ano: int) -> tuple[int, int, float]:
    """(bimestre, quadrimestre, parte do ano) publicados."""
    return (4, 2, 8 / 12) if ano == ANO else (6, 3, 1.0)


def rreo(ano: int, per: int, anexo: str) -> list[dict]:
    bim, _, parte = _per(ano)
    if ano > ANO or ano < 2015 or per > bim:
        return []
    f = _fator(ano) * (per / 6 if ano < ANO else parte * per / bim)
    out = []
    if anexo == "RREO-Anexo 01":
        tot = 0.0
        for conta, v in RECEITAS.items():
            out += [_item(ano, per, anexo, conta, conta, "PREVISÃO ATUALIZADA (a)", round(v * _fator(ano), 2)),
                    _item(ano, per, anexo, conta, conta, "Até o Bimestre (c)", round(v * f, 2))]
            if conta != "OperacoesDeCreditoRefinanciamento":
                tot += round(v * f, 2)
        out.append(_item(ano, per, anexo, "ReceitasExcetoIntraOrcamentarias", "RECEITAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)", "Até o Bimestre (c)", round(tot, 2)))
        tot = 0.0
        for conta, v in DESPESAS.items():
            for col, x in (("DOTAÇÃO ATUALIZADA (e)", v * _fator(ano)), ("DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)", v * f * 1.05),
                           ("DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)", v * f), ("DESPESAS PAGAS ATÉ O BIMESTRE (j)", v * f * 0.98)):
                out.append(_item(ano, per, anexo, conta, conta, col, round(x, 2)))
            if conta != "AmortizacaoRefinanciamentoDaDivida":
                tot += round(v * f, 2)
        out.append(_item(ano, per, anexo, "DespesasExcetoIntraOrcamentarias", "DESPESAS (EXCETO INTRA-ORÇAMENTÁRIAS) (IX)",
                         "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)", round(tot, 2)))
        return out
    if anexo == "RREO-Anexo 02":
        linhas = []
        for fn, subs in FUNCOES:
            linhas.append((fn, sum(v for _, v in subs) * f))
            linhas += [(n, v * f) for n, v in subs]
        total = sum(sum(v for _, v in subs) * f for _, subs in FUNCOES)
        linhas = [("DESPESAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)", total)] + linhas + [("DESPESAS (INTRA-ORÇAMENTÁRIAS) (II)", 1e9)]
        for col, k in (("DOTAÇÃO ATUALIZADA (a)", 1.3), ("DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)", 1.0)):
            out += [_item(ano, per, anexo, "RREO2TotalDespesas", n, col, round(v * k, 2), rotulo="Total das Despesas Exceto Intra-Orçamentárias") for n, v in linhas]
        return out
    return []


RGF = {"L": [("Câmara dos Deputados", 7e9, 0.012), ("Senado Federal", 5e9, 0.0086), ("Tribunal de Contas da União", 2.5e9, 0.0042)],
       "J": [("Supremo Tribunal Federal", 0.8e9, 0.00145), ("Tribunal Regional do Trabalho - 2ª Região", 3e9, 0.0035)],
       "M": [("Ministério Público da União", 9e9, 0.006)],
       "E": [("União", 350e9, 0.379), ("Distrito Federal", 22e9, 0.022)]}


def rgf(ano: int, per: int, poder: str) -> list[dict]:
    _, q, _ = _per(ano)
    if ano > ANO or per > q or poder not in RGF:
        return []
    rcl = 1500e9 * _fator(ano)
    out = []
    for nome, bruta, lim in RGF[poder]:
        b = bruta * _fator(ano)
        rot, inst = (nome, "Governo Federal") if poder == "E" else ("Padrão", nome)
        doze = "TOTAL (ÚLTIMOS 12 MESES) (a)"
        dtp = b * 0.92
        for conta, col, v in (("DespesaComPessoalBruta", doze, b), ("DespesaComPessoalAtivoBruta", doze, b * 0.6),
                              ("DespesaComPessoalInativoEPensionistasBruta", doze, b * 0.4), ("DespesaComPessoalTotal", "VALOR", dtp),
                              ("DespesaComPessoalTotal", "% SOBRE A RCL", dtp / rcl * 100), ("LimiteMaximoDespesaComPessoalTotal", "VALOR", rcl * lim),
                              ("LimiteMaximoDespesaComPessoalTotal", "% SOBRE A RCL", lim * 100), ("ReceitaCorrenteLiquida", "VALOR", rcl)):
            out.append(_item(ano, per, "RGF-Anexo 01", conta, conta, col, round(v, 2), rotulo=rot, instituicao=inst, co_poder=poder))
    return out


UFS = ["SP", "RJ", "MG", "DF"]
MESES_UF = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def receita_uf() -> bytes:
    cab = ["Ano", "Mês", "UF", "IRPF", "IRPJ - DEMAIS EMPRESAS", "IRRF - RENDIMENTOS DO TRABALHO", "COFINS", "COFINS - FINANCEIRAS",
           "COFINS - DEMAIS", "CSLL - DEMAIS", "RECEITA PREVIDENCIÁRIA", "PAGAMENTO UNIFICADO", "IMPOSTO SOBRE IMPORTAÇÃO", "OUTRAS RECEITAS ADMINISTRADAS"]
    linhas = []
    for ano in range(2019, ANO + 1):
        for m in range(1, (7 if ano == ANO else 12) + 1):
            for i, uf in enumerate(UFS):
                k = _fator(ano) * (4 - i)
                # COFINS geral vazio quando há o detalhe (como nos arquivos de hoje)
                linhas.append([str(ano), MESES_UF[m - 1], uf, _br(3e9 * k), "1.234.567,89" if uf == "DF" else _br(5e9 * k), _br(4e9 * k), "",
                               _br(1e9 * k), _br(9e9 * k), _br(3e9 * k), _br(20e9 * k), _br(2e9 * k), _br(1e9 * k), _br(0.5e9 * k)])
    return _csv(cab, linhas).encode("latin-1")


def receita_cnae() -> bytes:
    cab = ["Ano", "Mês", "Seção - Sigla", "Seção - Nome", "IRPJ", "Cofins", "Contribuição Previdenciária", "IRPF"]
    linhas = []
    for ano in range(2019, ANO + 1):
        for m in ["Jan", "Fev", "Mar", "Abr ", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"][: 7 if ano == ANO else 12]:
            for sec, nome, k in (("C", "Indústrias de transformação", 5), ("K", "Atividades financeiras", 4), ("PF", "Pessoa Física", 3)):
                linhas.append([str(ano), m, sec, nome, _br(1e9 * k), _br(2e9 * k), _br(3e9 * k), _br(1e9 if sec == "PF" else 0)])
    return _csv(cab, linhas).encode("latin-1")


def sidra() -> bytes:
    dados = [{"V": "Valor", "D3C": "Mês (Código)"}]
    idx = 5000.0
    for ano in range(2018, ANO + 1):
        for m in range(1, 13):
            idx *= 1.004
            dados.append({"V": f"{idx:.2f}", "D3C": f"{ano}{m:02d}"})
    return json.dumps(dados).encode()


COLS_ORC = ["EXERCÍCIO", "CÓDIGO ÓRGÃO SUPERIOR", "NOME ÓRGÃO SUPERIOR", "CÓDIGO ÓRGÃO SUBORDINADO", "NOME ÓRGÃO SUBORDINADO",
            "CÓDIGO UNIDADE ORÇAMENTÁRIA", "NOME UNIDADE ORÇAMENTÁRIA", "CÓDIGO FUNÇÃO", "NOME FUNÇÃO", "CÓDIGO SUBFUNÇÃO", "NOME SUBFUNÇÃO",
            "CÓDIGO PROGRAMA ORÇAMENTÁRIO", "NOME PROGRAMA ORÇAMENTÁRIO", "CÓDIGO AÇÃO", "NOME AÇÃO", "CÓDIGO CATEGORIA ECONÔMICA",
            "NOME CATEGORIA ECONÔMICA", "CÓDIGO GRUPO DE DESPESA", "NOME GRUPO DE DESPESA", "CÓDIGO ELEMENTO DE DESPESA",
            "NOME ELEMENTO DE DESPESA", "ORÇAMENTO INICIAL (R$)", "ORÇAMENTO ATUALIZADO (R$)", "ORÇAMENTO EMPENHADO (R$)",
            "ORÇAMENTO REALIZADO (R$)", "% REALIZADO DO ORÇAMENTO (COM RELAÇÃO AO ORÇAMENTO ATUALIZADO)"]
ORC = [  # órgão, sub, função, subfunção, programa, ação, gnd, elemento, valor
    ("55000", "Ministério do Desenvolvimento e Assistência Social", "Fundo Nacional de Assistência Social", "08", "244", "5128",
     "BOLSA FAMILIA: PROTECAO SOCIAL", "8442", "TRANSFERENCIA DE RENDA DIRETAMENTE AS FAMILIAS", "3", "48", "Outros Auxílios Financeiros a Pessoas Físicas", 160e9),
    ("55000", "Ministério do Desenvolvimento e Assistência Social", "Fundo Nacional de Assistência Social", "08", "241", "5131",
     "PROTECAO SOCIAL NO AMBITO DO SUAS", "00H5", "BENEFICIO DE PRESTACAO CONTINUADA (BPC) A PESSOA IDOSA", "3", "06", "Benefício Mensal ao Deficiente e ao Idoso", 50e9),
    ("33000", "Ministério da Previdência Social", "Fundo do Regime Geral de Previdência Social", "09", "271", "2304",
     "PREVIDENCIA SOCIAL", "0E81", "BENEFICIOS PREVIDENCIARIOS URBANOS", "3", "01", "Aposentadorias do RGPS", 700e9),
    ("26000", "Ministério da Educação", "Ministério da Educação", "12", "122", "0032",
     "PROGRAMA DE GESTAO E MANUTENCAO DO PODER EXECUTIVO", "2000", "ADMINISTRACAO DA UNIDADE", "3", "37", "Locação de Mão-de-Obra", 3e9),
    ("26000", "Ministério da Educação", "Universidade Federal Fictícia", "12", "364", "5113",
     "EDUCACAO SUPERIOR", "20RK", "FUNCIONAMENTO DE INSTITUICOES FEDERAIS DE ENSINO SUPERIOR", "3", "39", "Outros Serviços de Terceiros - Pessoa Jurídica", 6e9),
    ("26000", "Ministério da Educação", "Universidade Federal Fictícia", "12", "364", "0032",
     "PROGRAMA DE GESTAO E MANUTENCAO DO PODER EXECUTIVO", "20TP", "ATIVOS CIVIS DA UNIAO", "1", "11", "Vencimentos e Vantagens Fixas - Pessoal Civil", 40e9),
    ("26000", "Ministério da Educação", "Universidade Federal Fictícia", "09", "272", "0033",
     "PROGRAMA DE GESTAO E MANUTENCAO DO PODER EXECUTIVO", "0181", "APOSENTADORIAS E PENSOES CIVIS DA UNIAO", "1", "01", "Aposentadorias", 20e9),
    ("39000", "Ministério dos Transportes", "DNIT", "26", "782", "3106", "TRANSPORTE RODOVIARIO", "7XYZ", "CONSTRUCAO DE RODOVIA", "4", "51", "Obras e Instalações", 8e9),
    ("25000", "Ministério da Fazenda", "Encargos Financeiros da União", "28", "843", "0905", "OPERACOES ESPECIAIS: SERVICO DA DIVIDA",
     "0455", "JUROS DA DIVIDA", "2", "21", "Juros sobre a Dívida por Contrato", 360e9),
]


def orcamento(ano: int) -> bytes | None:
    if ano > ANO or ano < 2015:
        return None
    _, _, parte = _per(ano)
    linhas = []
    for o, on, sub, fn, sf, pc, pn, ac, an, g, el, en, v in ORC:
        x = v * _fator(ano)
        linhas.append([str(ano), o, on, o, sub, o, sub, fn, "", sf, "", pc, pn, ac, an, "3", "", g, "", el, en,
                       _br(x), _br(x * 1.02), _br(x * parte), _br(x * parte * 0.97), "0,00%"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{ano}_OrcamentoDespesa.csv", _csv(COLS_ORC, linhas).encode("latin-1"))
    return buf.getvalue()


def siape(am: str) -> bytes | None:
    ano, mes = int(am[:4]), int(am[4:])
    if ano > ANO or (ano == ANO and mes > 8):
        return None
    cad = ["Id_SERVIDOR_PORTAL", "NOME", "CPF", "FUNCAO", "SITUACAO_VINCULO", "ORGSUP_EXERCICIO", "ORGSUP_LOTACAO"]
    rem = ["ANO", "MES", "Id_SERVIDOR_PORTAL", "CPF", "NOME", "REMUNERAÇÃO BÁSICA BRUTA (R$)", "ABATE-TETO (R$)", "GRATIFICAÇÃO NATALINA (R$)",
           "FÉRIAS (R$)", "OUTRAS REMUNERAÇÕES EVENTUAIS (R$)", "TOTAL DE VERBAS INDENIZATÓRIAS (R$)(*)"]
    pessoas = ([("NOMEADO CARGO COMIS.", "CARGO COMISSIONADO EXECUTIVO", 18000)] * 2
               + [("ATIVO PERMANENTE", "FUNCÃO COMISSIONADA EXECUTIVA", 15000)] * 6
               + [("ATIVO PERMANENTE", "Sem informação", 9000)] * 40
               + [("CONTRATO TEMPORARIO", "Sem informação", 5000)] * 4 + [("Sigiloso", "Sigiloso", 0)])
    lc, lr = [], []
    for i, (sit, fun, sal) in enumerate(pessoas):
        pid = str(1000 + i)
        org = "Ministério da Educação" if i % 2 else "Ministério da Saúde"
        lc.append([pid, f"SERVIDOR {i}", "***.000.000-**", fun, sit, org, org])
        if i == 10:  # mesma pessoa com dois vínculos: conta uma vez
            lc.append([pid, f"SERVIDOR {i}", "***.000.000-**", "Sem informação", "ATIVO PERMANENTE", org, org])
        if sal:
            lr.append([str(ano), f"{mes:02d}", pid, "***.000.000-**", f"SERVIDOR {i}", _br(sal * _fator(ano)), "0,00", "0,00", "0,00", "0,00", _br(1000)])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{am}_Cadastro.csv", _csv(cad, lc).encode("latin-1"))
        z.writestr(f"{am}_Remuneracao.csv", _csv(rem, lr).encode("latin-1"))
    return buf.getvalue()


def camara() -> bytes:
    dados = ([{"grupo": "Secretário Parlamentar", "funcao": ""}] * 20 + [{"grupo": "Cargo de Natureza Especial", "funcao": ""}] * 4
             + [{"grupo": "Quadro Efetivo - RJU", "funcao": "FC-2"}] * 3 + [{"grupo": "Quadro Efetivo - RJU", "funcao": ""}] * 5
             + [{"grupo": "Parlamentar", "funcao": ""}] * 3)
    return json.dumps({"dados": dados}).encode()


def senado() -> bytes:
    out = []
    for i, (v, sit) in enumerate([("COMISSIONADO", "ATIVO")] * 6 + [("EFETIVO", "ATIVO")] * 4 + [("EFETIVO", "APOSENTADO")] * 2
                                 + [("PARLAMENTAR", "ATIVO")] * 2 + [("COMISSIONADO", "DESLIGADO")] * 3):
        out.append({"sequencial": i, "vinculo": v, "situacao": sit, "funcao": {"nome": "Chefe"} if i == 6 else None})
    return json.dumps(out).encode()


def senado_rem(ano: int, mes: int) -> bytes:
    if ano > ANO or (ano == ANO and mes > 9):
        return b"[]"
    return json.dumps([{"sequencial": i, "remuneracao_basica": "10.000,00", "funcao_comissionada": "1.500,50" if i < 6 else "0,00"}
                       for i in range(17)]).encode()


def rota(netloc: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
    """(status, corpo, tipo) ou None se a URL não é de uma fonte da aba."""
    if netloc == "apidatalake.tesouro.gov.br":
        ano = int(q.get("an_exercicio", 0))
        per = int(q.get("nr_periodo", 0))
        if path.endswith("/rreo"):
            itens = rreo(ano, per, q.get("no_anexo", ""))
        elif path.endswith("/rgf"):
            itens = rgf(ano, per, q.get("co_poder", ""))
        else:
            return 404, b"", "text/html"
        return 200, json.dumps({"items": itens, "hasMore": False, "limit": 5000, "count": len(itens)}).encode(), "application/json"
    if netloc == "www.gov.br" and path == "/receitafederal/dados/arrecadacao-estado.csv":
        return 200, receita_uf(), "text/csv"
    if netloc == "www.gov.br" and path == "/receitafederal/dados/arrecadacao-cnae.csv":
        return 200, receita_cnae(), "text/csv"
    if netloc == "apisidra.ibge.gov.br":
        return 200, sidra(), "application/json"
    if netloc == "portaldatransparencia.gov.br" and path.startswith("/download-de-dados/orcamento-despesa/"):
        z = orcamento(int(path.rsplit("/", 1)[1]))
        return (200, z, "application/zip") if z else (404, b"", "text/html")
    if netloc == "portaldatransparencia.gov.br" and path.startswith("/download-de-dados/servidores/"):
        am = path.rsplit("/", 1)[1][:6]
        z = siape(am) if am.isdigit() else None
        return (200, z, "application/zip") if z else (404, b"", "text/html")
    if netloc == "dadosabertos.camara.leg.br" and path == "/arquivos/funcionarios/json/funcionarios.json":
        return 200, camara(), "application/json"
    if netloc == "adm.senado.gov.br" and path == "/adm-dadosabertos/api/v1/servidores/servidores":
        return 200, senado(), "application/json"
    if netloc == "adm.senado.gov.br" and path.startswith("/adm-dadosabertos/api/v1/servidores/remuneracoes/"):
        a, m = path.rsplit("/", 2)[1:]
        return 200, senado_rem(int(a), int(m)), "application/json"
    return None


def montar_url(url: str, params: dict) -> tuple[str, str, dict]:
    u = urlparse(url)
    return u.netloc, u.path, params
