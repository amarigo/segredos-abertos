"""Receitas e despesas da União pela API do Tesouro Nacional (SICONFI).

Fonte: API de dados abertos do SICONFI, https://apidatalake.tesouro.gov.br/docs/siconfi/
- RREO (Relatório Resumido da Execução Orçamentária), publicado a cada dois meses:
  Anexo 01: receitas por origem (impostos, contribuições, empréstimos...) e despesas por grupo (pessoal, juros...).
  Anexo 02: despesas por função (saúde, educação, Legislativo, Judiciário...) e subfunção.
- RGF (Relatório de Gestão Fiscal), publicado a cada quatro meses, Anexo 01: despesa com pessoal de cada Poder e
  de cada órgão (Câmara, Senado, TCU, tribunais, MPU, DPU, Executivo), com os limites da Lei de Responsabilidade
  Fiscal (LRF).

Os valores do ano corrente são acumulados até o último bimestre (RREO) ou quadrimestre (RGF) publicado.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from urllib.parse import urlencode

from .util import get_json

log = logging.getLogger("sa_etl.financas")

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/"
PAGINA_RREO = "https://siconfi.tesouro.gov.br/siconfi/pages/public/declaracao/declaracao_list.jsf"
MESES_BIMESTRE = {1: "fevereiro", 2: "abril", 3: "junho", 4: "agosto", 5: "outubro", 6: "dezembro"}
MESES_QUADRI = {1: "abril", 2: "agosto", 3: "dezembro"}


def url_api(recurso: str, **params) -> str:
    """O endereço da consulta, para o site mostrar o link do dado original."""
    return API + recurso + "?" + urlencode(params)


def consultar(recurso: str, cache: Path, completo: bool, **params) -> list[dict]:
    """Todas as linhas da consulta (a API devolve até 5000 por página). Anos fechados ficam no cache para sempre;
    o ano corrente é relido a cada 20 horas."""
    nome = "_".join(f"{k}-{v}" for k, v in sorted(params.items())).replace(" ", "")
    arq = cache / "siconfi" / f"{recurso}_{nome}.json"
    if arq.exists() and (completo or time.time() - arq.stat().st_mtime < 20 * 3600):
        return json.loads(arq.read_text(encoding="utf-8"))
    itens: list[dict] = []
    offset = 0
    while True:
        p = dict(params, offset=offset) if offset else params
        j = get_json(API + recurso, params=p, timeout=240)
        itens += j.get("items") or []
        if not j.get("hasMore"):
            break
        offset += int(j.get("limit") or 5000)
    arq.parent.mkdir(parents=True, exist_ok=True)
    if itens:  # resposta vazia não vai para o cache: o relatório pode sair amanhã
        arq.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    return itens


# ---------------------------------------------------------------- RREO

def rreo(ano: int, anexo: str, cache: Path, ano_atual: int) -> tuple[int, list[dict]] | None:
    """(bimestre, linhas) do último bimestre publicado do ano."""
    for per in range(6, 0, -1):
        params = dict(an_exercicio=ano, nr_periodo=per, co_tipo_demonstrativo="RREO", no_anexo=anexo, co_esfera="U", id_ente=1)
        try:
            itens = consultar("rreo", cache, completo=ano < ano_atual, **params)
        except Exception as e:  # noqa: BLE001
            log.warning("RREO %d %s bimestre %d: %s", ano, anexo, per, str(e)[:160])
            return None
        if itens:
            return per, itens
    return None


def _so_padrao(itens: list[dict]) -> list[dict]:
    p = [i for i in itens if i.get("rotulo") == "Padrão"]
    return p or itens


def valor(itens: list[dict], conta: str, coluna: str) -> float | None:
    """Valor de uma linha (cod_conta) numa coluna (pelo começo do nome, sem as letras entre parênteses, que mudam)."""
    achados = [i.get("valor") for i in itens if i.get("cod_conta") == conta and str(i.get("coluna", "")).upper().startswith(coluna)]
    achados = [float(v) for v in achados if v is not None]
    return achados[0] if achados else None


RECEITA = "ATÉ O BIMESTRE"
DOTACAO = "DOTAÇÃO ATUALIZADA"
LIQUIDADO = "DESPESAS LIQUIDADAS ATÉ O BIMESTRE"
PAGO = "DESPESAS PAGAS ATÉ O BIMESTRE"
EMPENHADO = "DESPESAS EMPENHADAS ATÉ O BIMESTRE"

# De onde vem o dinheiro (receitas sem as intraorçamentárias, que são um órgão federal pagando outro).
# (cod_conta, nome, explicação, tipo) tipo: "propria" (dinheiro que entra) ou "divida" (empréstimo)
RECEITAS = [
    ("Impostos", "Impostos", "Imposto de Renda (de pessoas e empresas), IPI, IOF, imposto de importação e imposto territorial rural.", "propria"),
    ("Taxas", "Taxas", "Cobradas por um serviço ou fiscalização do governo, como emissão de passaporte e fiscalização de mercados.", "propria"),
    ("ContribuicoesSociais", "Contribuições sociais", "INSS pago por trabalhadores e empresas, Cofins, PIS e CSLL. Pagam aposentadorias, saúde e assistência social.", "propria"),
    ("ContribuicaoDeIntervencaoNoDominioEconomico", "Contribuições econômicas", "Cide-Combustíveis e outras contribuições cobradas de setores específicos.", "propria"),
    ("ReceitaPatrimonial", "Petróleo, minérios, dividendos e concessões", "Royalties e participações do petróleo e da mineração, lucros (dividendos) de estatais como Petrobras, BB e Caixa, concessões e aluguéis.", "propria"),
    ("ReceitaDeServicos", "Serviços prestados", "O que órgãos federais cobram por serviços, como hospitais universitários e serviços financeiros.", "propria"),
    ("ReceitaAgropecuaria", "Atividade agropecuária", "Venda de produção agropecuária de órgãos federais.", "propria"),
    ("ReceitaIndustrial", "Atividade industrial", "Venda de produção industrial de órgãos federais.", "propria"),
    ("TransferenciasCorrentes", "Transferências recebidas", "Dinheiro que a União recebe de estados, municípios, empresas ou do exterior.", "propria"),
    ("OutrasReceitasCorrentes", "Multas, juros de mora e outras", "Multas, juros sobre impostos atrasados, indenizações e devoluções.", "propria"),
    ("ReceitasCorrentesAClassificar", "Receitas ainda sem classificação", "Valores que o Tesouro ainda não classificou.", "propria"),
    ("AlienacaoDeBens", "Venda de bens", "Venda de imóveis, ações e outros bens da União.", "propria"),
    ("AmortizacoesDeEmprestimos", "Devolução de empréstimos", "Parcelas de empréstimos que a União fez a estados, bancos e fundos e que voltaram.", "propria"),
    ("TransferenciasDeCapital", "Transferências de capital recebidas", "Repasses recebidos para investimento.", "propria"),
    ("OutrasReceitasDeCapital", "Outras receitas de capital", "Inclui o rendimento do dinheiro em caixa do Tesouro.", "propria"),
    ("ReceitasDeOperacoesDeCredito", "Empréstimos (dívida nova)", "Dinheiro que o governo pegou emprestado, principalmente vendendo títulos do Tesouro, para cobrir gastos.", "divida"),
    ("OperacoesDeCreditoRefinanciamento", "Dívida nova para pagar dívida velha", "Títulos vendidos só para pagar títulos que venceram (refinanciamento). Não é dinheiro novo para gastar.", "refinanciamento"),
]
TOTAL_RECEITA_SEM_INTRA = "ReceitasExcetoIntraOrcamentarias"

# Para onde vai (grupos de natureza da despesa, sem as intraorçamentárias)
DESPESAS_GRUPO = [
    ("PessoalEEncargosSociais", "Pessoal: salários, aposentadorias e pensões de servidores", "Salários de servidores e militares da ativa, aposentadorias e pensões de servidores, e contribuições do governo como patrão."),
    ("JurosEEncargosDaDivida", "Juros da dívida", "Juros pagos a quem emprestou dinheiro ao governo (quem tem títulos do Tesouro)."),
    ("BeneficiosPrevidenciarios", "Aposentadorias e pensões do INSS", "Benefícios do INSS (regime geral), pagos a trabalhadores do setor privado."),
    ("TransferenciasAEstadosDistritoFederalEMunicipios", "Repasses a estados e municípios", "Fundos de participação (FPE e FPM), SUS, Fundeb e outros repasses."),
    ("DemaisDespesasCorrentes", "Demais despesas do dia a dia", "Programas sociais (Bolsa Família, BPC, seguro-desemprego), hospitais, universidades, compras, serviços, aluguéis e o funcionamento dos órgãos."),
    ("Investimentos", "Investimentos", "Obras, equipamentos e outros bens que ficam para o país."),
    ("InversoesFinanceiras", "Empréstimos e participações", "Dinheiro que o governo empresta (como o Fies) ou põe em empresas e fundos."),
    ("AmortizacaoDaDivida", "Pagamento do principal da dívida", "Parte da dívida que venceu e foi paga com dinheiro do orçamento."),
    ("AmortizacaoRefinanciamentoDaDivida", "Rolagem da dívida (refinanciamento)", "Dívida que venceu e foi paga com dívida nova. Não é gasto com serviços: é trocar um título por outro."),
]
TOTAL_DESPESA_SEM_INTRA = "DespesasExcetoIntraOrcamentarias"


def _num(v: float | None) -> float:
    return round(v or 0.0, 2)


def ler_rreo1(itens: list[dict]) -> dict:
    """Receitas e despesas por grupo, do Anexo 01."""
    it = _so_padrao(itens)
    receitas = []
    for conta, nome, explica, tipo in RECEITAS:
        v = valor(it, conta, RECEITA)
        if v is None:
            continue
        receitas.append({"id": conta, "nome": nome, "explica": explica, "tipo": tipo, "valor": _num(v),
                         "previsto": _num(valor(it, conta, "PREVISÃO ATUALIZADA"))})
    despesas = []
    for conta, nome, explica in DESPESAS_GRUPO:
        liq = valor(it, conta, LIQUIDADO)
        if liq is None:
            continue
        despesas.append({"id": conta, "nome": nome, "explica": explica, "liquidado": _num(liq), "pago": _num(valor(it, conta, PAGO)),
                         "empenhado": _num(valor(it, conta, EMPENHADO)), "dotacao": _num(valor(it, conta, DOTACAO))})
    return {
        "receitas": receitas,
        "receita_total_sem_intra": _num(valor(it, TOTAL_RECEITA_SEM_INTRA, RECEITA)),
        "despesas": despesas,
        "despesa_total_sem_intra": _num(valor(it, TOTAL_DESPESA_SEM_INTRA, LIQUIDADO)),
        "deficit": _num(valor(it, "Deficit", RECEITA)),
    }


def conferir_rreo1(r: dict) -> list[str]:
    """As partes somam o total do relatório? Devolve os problemas encontrados."""
    erros = []
    soma_r = sum(x["valor"] for x in r["receitas"] if x["tipo"] != "refinanciamento")
    if r["receita_total_sem_intra"] and abs(soma_r - r["receita_total_sem_intra"]) > 1e6:
        erros.append(f"receitas: partes somam {soma_r:.0f}, total do relatório {r['receita_total_sem_intra']:.0f}")
    soma_d = sum(x["liquidado"] for x in r["despesas"] if x["id"] != "AmortizacaoRefinanciamentoDaDivida")
    if r["despesa_total_sem_intra"] and abs(soma_d - r["despesa_total_sem_intra"]) > 1e6:
        erros.append(f"despesas: partes somam {soma_d:.0f}, total do relatório {r['despesa_total_sem_intra']:.0f}")
    return erros


FUNCOES = ["Legislativa", "Judiciária", "Essencial à Justiça", "Administração", "Defesa Nacional", "Segurança Pública",
           "Relações Exteriores", "Assistência Social", "Previdência Social", "Saúde", "Trabalho", "Educação", "Cultura",
           "Direitos da Cidadania", "Urbanismo", "Habitação", "Saneamento", "Gestão Ambiental", "Ciência e Tecnologia",
           "Agricultura", "Organização Agrária", "Indústria", "Comércio e Serviços", "Comunicações", "Energia", "Transporte",
           "Desporto e Lazer", "Encargos Especiais"]
EXPLICA_FUNCAO = {
    "Legislativa": "Câmara, Senado e Tribunal de Contas da União.",
    "Judiciária": "Tribunais e a Justiça federal, do trabalho, eleitoral e militar.",
    "Essencial à Justiça": "Ministério Público da União, Defensoria Pública e Advocacia-Geral da União.",
    "Previdência Social": "Aposentadorias e pensões do INSS e dos servidores federais.",
    "Assistência Social": "Bolsa Família, BPC (idosos e pessoas com deficiência de baixa renda) e outros programas.",
    "Trabalho": "Seguro-desemprego, abono salarial e políticas de emprego.",
    "Encargos Especiais": "Juros e rolagem da dívida, repasses obrigatórios a estados e municípios e outros encargos que não são de um serviço.",
    "Administração": "Gestão do próprio governo: arrecadação, controle, planejamento, tecnologia, comunicação.",
}


def _subfuncao_nome(nome: str) -> str:
    """'FU04 - Administração Geral' -> 'Administração geral'."""
    if nome[:2] == "FU" and " - " in nome:
        nome = nome.split(" - ", 1)[1]
        return nome[:1] + nome[1:].lower()
    return nome


def ler_rreo2(itens: list[dict]) -> dict:
    """Despesa liquidada por função e subfunção (sem as intraorçamentárias), do Anexo 02."""
    def coluna(prefixo: str) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for i in itens:
            if i.get("cod_conta") == "RREO2TotalDespesas" and str(i.get("coluna", "")).upper().startswith(prefixo):
                out.append((str(i.get("conta") or "").strip(), float(i.get("valor") or 0)))
        return out
    liq = coluna("DESPESAS LIQUIDADAS ATÉ")
    dot = dict(coluna("DOTAÇÃO ATUALIZADA"))
    funcoes: list[dict] = []
    atual: dict | None = None
    total = 0.0
    for nome, v in liq:
        if nome.upper().startswith("DESPESAS (EXCETO"):
            total = v
            continue
        if nome.upper().startswith(("DESPESAS (INTRA", "TOTAL")):
            break  # daqui para baixo é intraorçamentária ou total geral
        if nome in FUNCOES or nome == "Reserva de Contingência":
            atual = {"nome": nome, "explica": EXPLICA_FUNCAO.get(nome, ""), "liquidado": round(v, 2),
                     "dotacao": round(dot.get(nome, 0.0), 2), "sub": []}
            funcoes.append(atual)
        elif atual is not None:
            atual["sub"].append([_subfuncao_nome(nome), round(v, 2)])
    for f in funcoes:  # subfunções só ficam se somarem a função (senão a ordem das linhas veio trocada)
        if f["sub"] and abs(sum(s[1] for s in f["sub"]) - f["liquidado"]) > 1e5:
            log.warning("RREO anexo 2: subfunções de %s não somam a função; ficam de fora", f["nome"])
            f["sub"] = []
        f["sub"] = sorted([s for s in f["sub"] if s[1]], key=lambda s: -s[1])
    funcoes = sorted([f for f in funcoes if f["liquidado"] or f["dotacao"]], key=lambda f: -f["liquidado"])
    soma = sum(f["liquidado"] for f in funcoes)
    return {"total": round(total, 2), "funcoes": funcoes, "confere": abs(soma - total) < 1e6}


def adm_geral(r2: dict) -> float:
    """Soma da subfunção 'Administração geral' em todas as funções: o custo de manter os órgãos funcionando
    (aluguel, limpeza, segurança, pessoal administrativo)."""
    return sum(v for f in r2["funcoes"] for n, v in f["sub"] if n.lower() == "administração geral")


# ---------------------------------------------------------------- RGF: pessoal por Poder

PODERES = {"E": "Executivo", "L": "Legislativo", "J": "Judiciário", "M": "Ministério Público da União", "D": "Defensoria Pública da União"}
ROTULO_EXECUTIVO = {"União": "Executivo federal", "Distrito Federal": "Polícias, bombeiros, saúde e educação do DF (pagos pela União)",
                    "Amapá": "Servidores do ex-território do Amapá", "Roraima": "Servidores do ex-território de Roraima"}


def rgf(ano: int, poder: str, cache: Path, ano_atual: int) -> tuple[int, list[dict]] | None:
    for per in (3, 2, 1):
        params = dict(an_exercicio=ano, in_periodicidade="Q", nr_periodo=per, co_tipo_demonstrativo="RGF",
                      no_anexo="RGF-Anexo 01", co_esfera="U", co_poder=poder, id_ente=1)
        try:
            itens = consultar("rgf", cache, completo=ano < ano_atual, **params)
        except Exception as e:  # noqa: BLE001
            log.warning("RGF %d poder %s: %s", ano, poder, str(e)[:160])
            return None
        if itens:
            return per, itens
    return None


def ler_rgf(poder: str, itens: list[dict]) -> list[dict]:
    """Um item por órgão (ou, no Executivo, por parte: União, DF, ex-territórios)."""
    grupos: dict[str, list[dict]] = {}
    for i in itens:
        chave = i.get("rotulo") if poder == "E" else i.get("instituicao")
        grupos.setdefault(str(chave), []).append(i)
    out = []
    for nome, it in grupos.items():
        doze = "TOTAL (ÚLTIMOS 12 MESES)"
        bruta = valor(it, "DespesaComPessoalBruta", doze)
        if bruta is None:
            continue
        out.append({
            "nome": ROTULO_EXECUTIVO.get(nome, nome) if poder == "E" else nome,
            "bruta": _num(bruta),
            "ativos": _num(valor(it, "DespesaComPessoalAtivoBruta", doze)),
            "inativos": _num(valor(it, "DespesaComPessoalInativoEPensionistasBruta", doze)),
            "dtp": _num(valor(it, "DespesaComPessoalTotal", "VALOR")),
            "pct_rcl": valor(it, "DespesaComPessoalTotal", "% SOBRE A RCL"),
            "limite_max": _num(valor(it, "LimiteMaximoDespesaComPessoalTotal", "VALOR")),
            "limite_pct": valor(it, "LimiteMaximoDespesaComPessoalTotal", "% SOBRE A RCL"),
            "rcl": _num(valor(it, "ReceitaCorrenteLiquida", "VALOR")),
        })
    return sorted(out, key=lambda x: -x["bruta"])
