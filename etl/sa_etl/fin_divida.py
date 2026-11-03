"""Dinheiro emprestado e dívida paga pela União desde 2018, bimestre a bimestre.

Fonte: API do SICONFI (Tesouro Nacional), RREO Anexo 01 de cada bimestre, as mesmas contas da aba de arrecadação e
gastos (fin_tesouro.py):
- receitas de operações de crédito: dinheiro que o governo pegou emprestado (quase tudo venda de títulos do Tesouro);
  "ReceitasDeOperacoesDeCredito" é a dívida nova que paga gastos e "OperacoesDeCreditoRefinanciamento" a dívida nova
  que só paga dívida velha (rolagem);
- despesas pagas com a dívida: juros ("JurosEEncargosDaDivida"), principal pago com dinheiro do orçamento
  ("AmortizacaoDaDivida") e principal pago com dívida nova ("AmortizacaoRefinanciamentoDaDivida").

O RREO é acumulado no ano (o 3º bimestre traz janeiro a junho). O valor de cada bimestre é a diferença entre um
relatório e o anterior. Anos fechados ficam no cache para sempre.
"""
from __future__ import annotations

import logging
from pathlib import Path

from . import fin_tesouro as t

log = logging.getLogger("sa_etl.financas")

ANO_INICIAL = 2018
EMPRESTIMOS = [
    ("novo", "ReceitasDeOperacoesDeCredito", "Empréstimos para pagar gastos", "Dívida nova que paga despesas do orçamento (o que os impostos não cobriram)."),
    ("rolagem", "OperacoesDeCreditoRefinanciamento", "Empréstimos para pagar dívida velha", "Títulos vendidos só para pagar títulos que venceram (rolagem). Não é dinheiro novo para gastar."),
]
PAGAMENTOS = [
    ("juros", "JurosEEncargosDaDivida", "Juros pagos", "Juros e encargos pagos a quem emprestou ao governo."),
    ("amortizacao", "AmortizacaoDaDivida", "Dívida paga com dinheiro do orçamento", "Parte do principal que venceu e foi paga sem pegar empréstimo novo."),
    ("amortizacao_rolagem", "AmortizacaoRefinanciamentoDaDivida", "Dívida paga com dívida nova", "Principal que venceu e foi pago com os empréstimos de rolagem."),
]


def _acumulado(itens: list[dict]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for k, conta, _, _ in EMPRESTIMOS:
        out[k] = t.valor_conta(itens, conta, t.RECEITA)
    for k, conta, _, _ in PAGAMENTOS:
        out[k] = t.valor_conta(itens, conta, t.PAGO)
    return out


def _menos(v: float | None, antes: float | None) -> float | None:
    """Valor do bimestre: acumulado de agora menos o do relatório anterior. Sem a conta em um dos dois, sem valor
    (nunca vira zero, que o site mostraria como "R$ 0" e "-100%")."""
    if v is None:
        return None
    return round(v - (antes or 0.0), 2)


def _params(ano: int, bim: int) -> dict:
    return dict(an_exercicio=ano, nr_periodo=bim, co_tipo_demonstrativo="RREO", no_anexo="RREO-Anexo 01", co_esfera="U", id_ente=1)


def coletar(cache: Path, ano_atual: int) -> dict | None:
    """{"bimestres": [...], "anos": [...], "contas": {...}}. None se o Tesouro não respondeu nada."""
    bimestres: list[dict] = []
    anos: list[dict] = []
    for ano in range(ANO_INICIAL, ano_atual + 1):
        anterior: dict[str, float | None] = {}
        ultimo = None
        for bim in range(1, 7):
            try:
                itens = t.consultar("rreo", cache, completo=ano < ano_atual, **_params(ano, bim))
            except Exception as e:  # noqa: BLE001
                log.warning("Dívida: RREO %d bimestre %d não respondeu (%s)", ano, bim, str(e)[:120])
                break
            if not itens:
                break  # bimestre ainda não publicado
            acum = _acumulado(itens)
            if all(v is None for v in acum.values()):
                log.warning("Dívida: RREO %d bimestre %d sem as contas da dívida", ano, bim)
                break
            no_bim = {k: _menos(v, anterior.get(k)) if bim == 1 or anterior.get(k) is not None else None for k, v in acum.items()}
            bimestres.append({"ano": ano, "bimestre": bim, "ate": t.MESES_BIMESTRE[bim], "valores": no_bim,
                              "url": t.url_api("rreo", **_params(ano, bim))})
            anterior, ultimo = acum, bim
        if ultimo:
            ac = {k: None if v is None else round(v, 2) for k, v in anterior.items()}
            faltam = [k for k, v in ac.items() if v is None]
            if faltam:
                log.warning("Dívida %d: o RREO do %dº bimestre não trouxe %s; o site mostra 'sem dado' em vez de zero",
                            ano, ultimo, ", ".join(faltam))
            anos.append({"ano": ano, "ate_bimestre": ultimo, "ate": t.MESES_BIMESTRE[ultimo], "parcial": ultimo < 6, "valores": ac,
                         "url": t.url_api("rreo", **_params(ano, ultimo))})
    if not anos:
        return None
    # Conferência: a soma dos bimestres tem que dar o acumulado do último relatório de cada ano
    for a in anos:
        for k, v in a["valores"].items():
            partes = [b["valores"][k] for b in bimestres if b["ano"] == a["ano"]]
            if v is None or any(x is None for x in partes):
                continue
            soma = sum(partes)
            if abs(soma - v) > 1:
                log.warning("Dívida %d: bimestres de %s somam %.0f, o relatório diz %.0f", a["ano"], k, soma, v)
    contas = {k: {"nome": n, "explica": e, "conta": c, "tipo": "emprestimo"} for k, c, n, e in EMPRESTIMOS}
    contas.update({k: {"nome": n, "explica": e, "conta": c, "tipo": "pagamento"} for k, c, n, e in PAGAMENTOS})
    log.info("Dívida: %d anos (%d a %d), %d bimestres", len(anos), anos[0]["ano"], anos[-1]["ano"], len(bimestres))
    return {"anos": anos, "bimestres": bimestres, "contas": contas, "fonte": "https://apidatalake.tesouro.gov.br/docs/siconfi/"}
