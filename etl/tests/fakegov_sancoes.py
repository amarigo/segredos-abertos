"""Listas oficiais de punidos simuladas: CEIS, CNEP e CEAF (API do Portal da Transparência) e as listas do TCU.

Os campos seguem o que as fontes devolveram em 10/11/2026 (sonda no GitHub Actions): 15 linhas por página no Portal,
página vazia no fim, CPF inteiro em sancionado.codigoFormatado no CEIS e só com máscara no CEAF; no TCU, o envelope do
Oracle REST (items, hasMore, limit, offset, links) e o CPF inteiro.

Casos que os testes conferem:
- fornecedora 3 no CEIS (vigente) e fornecedora 4 no CEIS (já terminou): ligam pelo CNPJ;
- fornecedora 5 no CNEP, com multa "1.500.000,00";
- fornecedora 6 nos inidôneos do TCU;
- DONO FICTICIO 1 (sócio, CPF da Receita ***100001**) no CEIS: liga pelo nome e pelo meio do CPF;
- DONO FICTICIO 2 no CEAF, mas com outro CPF (homônimo): NÃO pode ligar;
- deputado 1002 no CEIS (CPF inteiro), 1003 no CEAF (nome civil e meio do CPF), 1004 nos inabilitados e na lista
  eleitoral do TCU;
- deputado 1005 tem homônimo nos inabilitados do TCU com outro CPF: NÃO pode ligar;
- fornecedora 7 nas contas irregulares do TCU (empresa, pelo CNPJ).
"""
from __future__ import annotations

import json

import fakegov_tse  # noqa: E402  (mesma pasta dos testes)

PORTAL = "api.portaldatransparencia.gov.br"
TCU = "certidoes.apps.tcu.gov.br"
SERVICOS = {"responsaveis-contas-irregulares-com-paginacao": "irregulares", "responsaveis-fins-eleitorais-com-paginacao": "eleitoral",
            "responsaveis-inabilitados-com-paginacao": "inabilitados", "responsaveis-inidoneos-com-paginacao": "inidoneos"}
POR_PAGINA = 15


def cpf_deputado(id_: int) -> str:
    """CPF fictício (11 dígitos) do deputado, o mesmo que o FakeGov devolve em /deputados/{id} e o mesmo das contas
    de campanha (fakegov_tse): os ids dos deputados fictícios começam em 1000."""
    return fakegov_tse.cpf_deputado(id_ - 1000)


def nome_civil(id_: int) -> str:
    return fakegov_tse.nome_civil_deputado(id_ - 1000).upper()


def _fmt_cpf(d: str) -> str:
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def _mascara(d: str) -> str:
    return f"***.{d[3:6]}.{d[6:9]}-**"


def _fmt_cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def _br(data: str) -> str:
    a, m, d = data.split("-")
    return f"{d}/{m}/{a}"


def _ceis(i: int, nome: str, doc: str, pj: bool, ini: str, fim: str, cad: str = "ceis") -> dict:
    x = {"id": 900000 + i, "dataReferencia": "09/11/2026", "dataInicioSancao": _br(ini), "dataFimSancao": _br(fim) if fim else "Sem informação",
         "dataPublicacaoSancao": "Sem informação", "dataTransitadoJulgado": _br(ini), "dataOrigemInformacao": _br(ini),
         "tipoSancao": {"descricaoResumida": "Impedimento/proibição de contratar com prazo determinado",
                        "descricaoPortal": "Impedimento/proibição de contratar com prazo determinado"},
         "fonteSancao": {"nomeExibicao": "Conselho Nacional de Justiça (CNJ-DF)"},
         "orgaoSancionador": {"nome": "Tribunal de Justiça Ficticio", "siglaUf": "SP", "poder": "Judiciário", "esfera": "ESTADUAL"},
         "sancionado": {"nome": nome, "codigoFormatado": _fmt_cnpj(doc) if pj else _fmt_cpf(doc)},
         "pessoa": {"id": 1 + i, "cpfFormatado": "" if pj else _mascara(doc), "cnpjFormatado": _fmt_cnpj(doc) if pj else "",
                    "nome": nome, "tipo": "Entidades Empresariais Privadas" if pj else "Pessoa Física"},
         "numeroProcesso": f"0000{i:04d}20248260000", "linkPublicacao": "",
         "fundamentacao": [{"codigo": "LEI 8429 - ART. 12 - IMPROBIDADE", "descricao": "LEI 8429 - ART. 12 - IMPROBIDADE"}]}
    if cad == "cnep":
        x["valorMulta"] = "1.500.000,00"
        x["tipoSancao"] = {"descricaoResumida": "Multa - Lei Anticorrupção", "descricaoPortal": "Multa - Lei Anticorrupção"}
    return x


def _ceaf(i: int, nome: str, cpf: str) -> dict:
    return {"id": 800000 + i, "dataPublicacao": "21/07/2021", "dataReferencia": "09/11/2026",
            "punicao": {"cpfPunidoFormatado": _mascara(cpf), "nomePunido": nome, "portaria": "270", "processo": f"0862.{i}/2015-02"},
            "tipoPunicao": {"descricao": "Demissão"},
            "pessoa": {"id": 5000 + i, "cpfFormatado": _mascara(cpf), "cnpjFormatado": "", "nome": nome, "tipo": "Pessoa Física"},
            "orgaoLotacao": {"nome": "MINISTÉRIO FICTICIO"}, "cargoEfetivo": "AGENTE ADMINISTRATIVO",
            "fundamentacao": [{"codigo": "LEI 8112 - ART. 132, IV - IMPROBIDADE ADMINISTRATIVA"}]}


def _tcu(nome: str, doc: str, i: int, fim: str | None = "2030-07-16", eleitoral: bool = False) -> dict:
    x = {"numeroProcessoFormatado": f"026.{i:03d}/2020-7", "nome": nome, "tipoRegistro": "CPF" if len(doc) == 11 else "CNPJ",
         "numeroRegistro": _fmt_cpf(doc) if len(doc) == 11 else _fmt_cnpj(doc), "municipio": "SAO PAULO", "uf": "SP",
         "numeroAcordaoFormatado": f"{700 + i}/2022-PL", "dataAcordao": "06/04/2022", "dataTransitoEmJulgado": "16/07/2022",
         "linkDeliberacoesProcesso": f"https://contas.tcu.gov.br/pesquisaJurisprudencia/#/resultado/acordao-completo/026{i:03d}20207.PROC",
         "linkAcompanhamentoProcesso": f"https://conecta-tcu.apps.tcu.gov.br/tvp/{65000000 + i}", "codigoProcesso": 65000000 + i}
    if fim:
        x["dataFinalFinsEleitorais" if eleitoral else "dataFinalSancao"] = _br(fim)
    return x


class Sancoes:
    def __init__(self, fornecedoras: list[str], deputados: list[dict]):
        f = fornecedoras
        dep = {d["id"]: d for d in deputados}
        ceis = [_ceis(i, f"EMPRESA SEM LIGACAO {i:03d} LTDA", f"{11000000 + i:08d}000199", True, "2024-01-01", "2029-01-01")
                for i in range(40)]  # enche as páginas
        ceis.append(_ceis(100, "FORNECEDORA FICTICIA 03 LTDA", f[3], True, "2025-03-01", "2030-03-01"))
        ceis.append(_ceis(101, "FORNECEDORA FICTICIA 04 LTDA", f[4], True, "2019-01-01", "2021-01-01"))
        ceis.append(_ceis(102, "DONO FICTICIO 1", "55510000112", False, "2024-05-01", "2032-05-01"))
        if 1002 in dep:
            ceis.append(_ceis(103, nome_civil(1002), cpf_deputado(1002), False, "2023-02-01", "2031-02-01"))
        self.listas = {
            "ceis": ceis,
            "cnep": [_ceis(200 + i, f"OUTRA EMPRESA {i:02d} SA", f"{22000000 + i:08d}000188", True, "2024-01-01", "2027-01-01", "cnep")
                     for i in range(5)] + [_ceis(210, "FORNECEDORA FICTICIA 05 LTDA", f[5], True, "2025-06-01", "", "cnep")],
            "ceaf": [_ceaf(1, "DONO FICTICIO 2", "44499999901")]  # homônimo do sócio, com outro CPF
            + ([_ceaf(2, nome_civil(1003), cpf_deputado(1003))] if 1003 in dep else []),
        }
        self.tcu = {
            "inabilitados": ([_tcu(nome_civil(1004), cpf_deputado(1004), 1)] if 1004 in dep else [])
            + ([_tcu(nome_civil(1005), "12345678900", 2)] if 1005 in dep else []),
            "eleitoral": ([_tcu(nome_civil(1004), cpf_deputado(1004), 1, "2030-07-16", True)] if 1004 in dep else [])
            + [_tcu(f"PESSOA SEM LIGACAO {i}", f"{30000000000 + i}", 10 + i, "2031-01-01", True) for i in range(5)],
            "irregulares": [_tcu("FORNECEDORA FICTICIA 07 LTDA", f[7], 3, None)]
            + [_tcu(f"PESSOA SEM LIGACAO {i}", f"{30000000000 + i}", 10 + i, None) for i in range(5)],
            "inidoneos": [_tcu("FORNECEDORA FICTICIA 06 LTDA", f[6], 4, "2028-02-01")],
        }
        self.pedidos: dict[str, int] = {}

    def rota(self, host: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
        if host == PORTAL and path.startswith("/api-de-dados/"):
            cad = path.rsplit("/", 1)[-1]
            if cad not in self.listas:
                return None
            self.pedidos[cad] = self.pedidos.get(cad, 0) + 1
            p = int(q.get("pagina", 1))
            linhas = self.listas[cad][(p - 1) * POR_PAGINA: p * POR_PAGINA]
            return 200, json.dumps(linhas, ensure_ascii=False).encode(), "application/json"
        if host == TCU and path.startswith("/api/publico/"):
            nome = SERVICOS.get(path.rsplit("/", 1)[-1])
            if nome is None:
                return 500, b'{"mensagem":"No static resource"}', "application/json"
            if nome == "eleitoral" and not q.get("anoEleicao"):
                return 400, b'{"mensagem":"Ano da eleicao e obrigatorio"}', "application/json"
            itens = self.tcu[nome]
            tam, pag = int(q.get("tamanhoPagina", 10)), int(q.get("paginaAtual", 1))
            return 200, json.dumps({"totalPaginas": max(1, -(-len(itens) // tam)), "totalElementos": len(itens), "paginaAtual": pag,
                                    "tamanhoPagina": tam, "elementos": itens[(pag - 1) * tam: pag * tam]},
                                   ensure_ascii=False).encode(), "application/json"
        return None
