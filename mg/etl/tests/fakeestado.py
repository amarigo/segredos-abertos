"""Fontes do estado simuladas: ALMG (deputados, verba, proposições, emendas), Tesouro (SICONFI) e o TSE.

Os dados são fictícios, mas no formato real (conferido na sondagem): a lista de deputados em JSON, os arquivos da
ALMG em CSV com ',' e UTF-8, o de emendas em latin-1 com ';', valores "R$1.234,56", CNPJ estragado pelo Excel
("2,10359E+13"), justificativa com quebra de linha dentro das aspas, indicação repetida, indicação reprovada,
autor que já saiu da Assembleia. Tudo que um CPF poderia vazar está aqui de propósito (emitente pessoa física
na verba, favorecido pessoa física na emenda federal), para os testes provarem que não vaza.

Também falha de propósito (caos): `falhar(pedaco_da_url, modo)` com modo fora, 500, 429, html, vazio, cortado,
sem_coluna.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from faketse import FakeTSE

CPF_EMITENTE = "52998224725"  # CPF válido de teste: não pode aparecer em nenhum arquivo gerado
CIDADES_EMENDAS = ["ITAJUBÁ", "PARAISÓPOLIS", "BELO HORIZONTE", "POUSO ALEGRE"]
PARTIDOS = ["PT", "PL", "PSD", "MDB", "PSDB", "UNIÃO", "NOVO", "PP", "REDE", "PSB"]

EMENDAS_COLS = ["Ano da Indicação", "Número da Indicação", "Indicador de Impositividade", "Tipo de Indicação",
                "Status da Indicação", "Autor", "Genêro", "Categoria", "Especificação", "Tipo de Aplicação",
                "Unidade Orçamentária Código", "Unidade Orçamentária Sigla", "Unidade Orçamentária Descrição",
                "Função Código", "Função Descrição", "Número da Ação", "Nome da Ação", "Grupo de Despesa Código",
                "Grupo de Despesa Descrição", "Município ", "Macrorregião de Planejamento", "Estado", "País",
                "Descrição do Tipo de Beneficiário", "Nome Beneficiário", "Número do CNPJ do Beneficiário", "Código Escola",
                "Minímo Saúde ou Educação", "Descrição da Indicação", "Valor Indicado", "Valor Utilizado",
                "Valor Empenhado no Ano", "Valor Pago Atualizado", "Classificação do IOT", "Justificativa de Reprovação",
                "Status", "Número do Instrumento", "Status do Instrumento", "Código SIAFI do Instrumento",
                "Data de Publicação do Instrumento", "Data de Validade do Instrumento", "Agência", "Agência Dígito",
                "Conta", "Conta Dígito", "Tipo de autoria"]
PROP_COLS = ["Codigo", "TipoProposicao", "SiglaTipoProposicao", "Numero", "Ano", "Ementa", "Indexacao", "Situacao",
             "DataPublicacao", "DataAtualizacao", "DataUltimaAcao", "Regime", "Resumo", "Origem", "Local", "NomeFaseAtual",
             "Legislatura", "Autores", "LinkTextos"]
FUNCOES = [("10", "Saúde", [("301", "Atenção Básica"), ("302", "Assistência Hospitalar e Ambulatorial")]),
           ("12", "Educação", [("361", "Ensino Fundamental"), ("365", "Educação Infantil")]),
           ("04", "Administração", [("122", "Administração Geral")]),
           ("01", "Legislativa", [("031", "Ação Legislativa")])]
ENTES = {"ITAJUBÁ": 3132404, "PARAISÓPOLIS": 3147303}


def _reais(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R${s}"


def _csv(cols: list[str], linhas: list[dict], sep: str = ",", quoting=csv.QUOTE_MINIMAL) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=sep, quoting=quoting, lineterminator="\r\n")
    w.writerow(cols)
    for ln in linhas:
        w.writerow([ln.get(c, "") for c in cols])
    return buf.getvalue()


class FakeEstado:
    def __init__(self, n_deputados: int = 60, anos=(2023, 2024, 2025, 2026), tse: FakeTSE | None = None):
        self.anos = list(anos)
        self.tse = tse or FakeTSE()
        self.falhas: dict[str, str] = {}
        self.chamadas: list[str] = []
        self.deputados = [{"id": 20000 + i, "nome": f"Fulano Estadual {i:02d}", "partido": PARTIDOS[i % len(PARTIDOS)]}
                          for i in range(n_deputados)]
        self.esperado: dict = {}
        self._emendas()

    # ------------------------------------------------------------ caos
    def falhar(self, pedaco: str, modo: str) -> "FakeEstado":
        self.falhas[pedaco] = modo
        return self

    def consertar(self) -> "FakeEstado":
        self.falhas.clear()
        return self

    # ------------------------------------------------------------ ALMG
    def em_exercicio(self) -> bytes:
        return json.dumps({"list": [{**d, "tagLocalizacao": 0} for d in self.deputados]}, ensure_ascii=False).encode()

    def deputados_csv(self) -> bytes:
        linhas = [{"Codigo": d["id"], "Nome": d["nome"], "Partido": d["partido"], "Legislaturas": "20", "UltimaLegislatura": "20",
                   "PaginaAlmg": f"https://www.almg.gov.br/deputados/fulano-{d['id']}/{d['id']}"} for d in self.deputados]
        linhas.append({"Codigo": 1, "Nome": "Antigo", "Partido": "PFL", "Legislaturas": "8", "UltimaLegislatura": "8",
                       "PaginaAlmg": "javascript:alert(1)"})
        return _csv(["Codigo", "Nome", "Partido", "Legislaturas", "UltimaLegislatura", "PaginaAlmg"], linhas).encode()

    def verba_mes(self, dep: int, ano: int, mes: int) -> bytes:
        """API da verba: os 20 primeiros deputados gastam (i+1) mil de combustível (CNPJ) e 500 de aluguel com pessoa
        física (CPF) em janeiro, fevereiro e março; os outros meses vêm vazios."""
        i = dep - 20000
        if i >= 20 or mes > 3 or ano not in self.anos:
            return json.dumps({"list": []}).encode()
        ref = {"@class": "sql-timestamp", "$": f"{ano}-{mes:02d}-01"}
        comb = (i + 1) * 1000.0
        lista = [
            {"idDeputado": dep, "dataReferencia": ref, "codTipoDespesa": 32, "valor": comb, "descTipoDespesa": "Combustível e lubrificante",
             "listaDetalheVerba": [{"id": 1, "idDeputado": dep, "dataReferencia": ref, "valorReembolsado": comb / 2, "valorDespesa": comb / 2,
                                    "dataEmissao": {"@class": "sql-timestamp", "$": f"{ano}-{mes:02d}-05"}, "cpfCnpj": "11222333000181",
                                    "nomeEmitente": "POSTO DO FULANO LTDA", "descDocumento": "123"},
                                   {"id": 2, "idDeputado": dep, "dataReferencia": ref, "valorReembolsado": comb / 2, "valorDespesa": comb / 2,
                                    "dataEmissao": {"@class": "sql-timestamp", "$": f"{ano}-{mes:02d}-06"}, "cpfCnpj": "11222333000181",
                                    "nomeEmitente": "POSTO DO FULANO LTDA", "descDocumento": "124"}]},
            {"idDeputado": dep, "dataReferencia": ref, "codTipoDespesa": 40, "valor": 500.0,
             "descTipoDespesa": "Locação de imóvel e despesas a ele concernentes",
             # um item só vem como objeto, não lista; e o nome traz o CPF junto, como em alguns arquivos oficiais
             "listaDetalheVerba": {"id": 3, "valorReembolsado": 500.0, "cpfCnpj": CPF_EMITENTE,
                                   "dataEmissao": {"@class": "sql-timestamp", "$": f"{ano}-{mes:02d}-10"},
                                   "nomeEmitente": f"JOSE DA SILVA - {CPF_EMITENTE[:3]}.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-{CPF_EMITENTE[9:]}"}},
        ]
        return json.dumps({"list": lista}, ensure_ascii=False).encode()

    # ------------------------------------------------------------ Dados MG (salários e viagens)
    SAL_COLS = ["mes_ano", "numero_admissao", "masp", "nome", "cpf", "situacao_servidor", "orgao_origem", "orgao_exercicio",
                "unidade_exercicio", "carga_horaria_semanal", "cargo_efetivo", "simbolo_cargo", "nivel_carreira", "grau_carreira",
                "cargo_comissao", "data_ingresso", "data_desligamento", "data_aposentadoria", "remuneracao", "abate_teto", "judic",
                "ferias", "decimo_terceiro", "premio", "ferias_premio", "jetons", "verba_indenizatoria", "eventual", "imposto_renda",
                "previdencia", "remuneracao_liquida", "bdmg", "cemig", "codemig", "cohab", "copasa", "emater", "epamig", "funpemg",
                "gasmig", "mgi", "mgs", "prodemge", "prominas", "emip", "codemge", "emc"]
    EQUIPE = [("GOVERNADORA DE TESTE", "GOVERNADOR DO ESTADO", "SECRETARIA GERAL DO ESTADO DE MINAS GERAIS", "41845,49", "27697,17", "0,00"),
              ("SECRETARIO DA SAUDE", "SECRETARIO DE ESTADO", "SECRETARIA DE ESTADO DE SAUDE", "34774,64", "26978,98", "0,00"),
              ("SECRETARIA DA FAZENDA", "SECRETARIO DE ESTADO", "SECRETARIA DE ESTADO DE FAZENDA", "34774,64", "26959,66", "6724,29")]

    def salarios_csv(self) -> bytes:
        base = {c: "0,00" for c in self.SAL_COLS}
        linhas = []
        for nome, cargo, orgao, bruto, liq, jet in self.EQUIPE:
            linhas.append({**base, "mes_ano": "82026", "masp": "123", "nome": nome, "cpf": "***.982.247-**", "orgao_exercicio": orgao,
                           "cargo_comissao": cargo, "cargo_efetivo": "", "remuneracao": bruto, "remuneracao_liquida": liq, "cemig": jet,
                           "imposto_renda": "8382,57", "previdencia": "988,09", "unidade_exercicio": "GABINETE"})
        for nome, cargo, unidade in (("ASSESSOR QUALQUER", "ASSESSOR DE SECRETARIO DE ESTADO II", "GABINETE"),
                                     ("ADJUNTO QUALQUER", "SECRETARIO-GERAL ADJUNTO", "GOVERNADORIA"),
                                     ("SERVIDOR DE GV", "", "UNIDADE REGIONAL - GOVERNADOR VALADARES")):
            linhas.append({**base, "mes_ano": "82026", "nome": nome, "cpf": "***.111.222-**", "cargo_comissao": cargo,
                           "cargo_efetivo": "AUXILIAR", "unidade_exercicio": unidade, "remuneracao": "9.756,79"})
        return _csv(self.SAL_COLS, linhas, sep=";").encode()

    def ckan(self, pacote: str) -> bytes:
        base = "https://dados.mg.gov.br/dataset/x/resource/"
        if pacote == "remuneracao-servidores-ativos":
            rec = [{"name": "Remuneração de Julho de 2026", "url": base + "a/download/servidores-2026-07.csv"},
                   {"name": "Remuneração de Agosto de 2026", "url": base + "b/download/servidores-2026-08.csv"},
                   {"name": "Dicionário de dados", "url": base + "c/download/dicionario.pdf"}]
        elif pacote == "viagens":
            rec = [{"name": n, "url": base + f"{n}/download/{n}.csv.gz"} for n in
                   ("dm_funcao_scdp", "dm_favorecido_scdp", "dm_cidade", "dm_documento_viagem", "ft_diarias_scdp", "ft_diarias_scdp_liqpag")]
        else:
            return json.dumps({"success": False}).encode()
        return json.dumps({"success": True, "result": {"resources": rec}}, ensure_ascii=False).encode()

    def scdp(self, nome: str) -> bytes:
        if nome == "dm_funcao_scdp":
            cols, linhas = ["\ufeffid_funcao", "nome"], [{"\ufeffid_funcao": a, "nome": b} for a, b in (
                ("12186", "GOVERNADOR DO ESTADO"), ("12605", "SECRETARIO DE ESTADO"), ("11282", "VICE  GOVERNADOR DO ESTADO"),
                ("12280", "ASSESSOR DE SECRETARIO DE ESTADO II"), ("11597", "CHEFE DE GABINETE DO GOVERNADOR DO ESTADO"))]
        elif nome == "dm_favorecido_scdp":
            cols = ["id_favorecido", "nr_cpf_anonimizado", "masp", "nome_anonimizado"]
            linhas = [{"id_favorecido": "1", "nr_cpf_anonimizado": "***.982.247-**", "nome_anonimizado": "GOVERNADORA DE TESTE"},
                      {"id_favorecido": "2", "nr_cpf_anonimizado": "***.982.247-**",
                       "nome_anonimizado": f"SECRETARIO DA SAUDE - {CPF_EMITENTE[:3]}.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-{CPF_EMITENTE[9:]}"},
                      {"id_favorecido": "3", "nome_anonimizado": "ASSESSOR QUALQUER"}]
        elif nome == "dm_cidade":
            cols, linhas = ["id_cidade", "nome"], [{"id_cidade": "1", "nome": "BELO HORIZONTE"}, {"id_cidade": "2", "nome": "BRASILIA"},
                                                   {"id_cidade": "3", "nome": "ITAJUBA"}]
        elif nome == "dm_documento_viagem":
            cols = ["id_documento_viagem", "nr_documento", "dt_viagem_inicio", "dt_viagem_fim", "motivo"]
            linhas = [{"id_documento_viagem": str(k), "motivo": f"Reunião de trabalho {k}, contato 35999998888"} for k in range(1, 6)]
        elif nome == "ft_diarias_scdp":
            cols = ["id_tempo", "id_favorecido", "id_cargo", "id_funcao_scdp", "id_orgao", "id_cidade_origem", "id_cidade_destino",
                    "id_documento_viagem", "ordem_trecho", "ano_particao", "dt_inicio_trecho", "dt_fim_trecho", "qt_diaria", "vr_diaria", "vr_passagem"]
            linhas = []
            for doc, fav, fun, dest, dia, d, ps in ((1, "1", "12186", "2", "2026-03-10", "1410.00", "1245.23"),
                                                    (2, "1", "12186", "3", "2026-05-02", "470.00", "0.00"),
                                                    (3, "2", "12605", "2", "2025-09-18", "665.00", "853.48"),
                                                    (4, "3", "12280", "2", "2025-09-18", "300.00", "853.48"),  # assessor: fora
                                                    (5, "2", "12605", "1", "2026-01-15", "0.00", "0.00")):
                linhas.append({"id_favorecido": fav, "id_funcao_scdp": fun, "id_cidade_origem": "1", "id_cidade_destino": dest,
                               "id_documento_viagem": str(doc), "ordem_trecho": "1", "dt_inicio_trecho": dia, "dt_fim_trecho": dia,
                               "qt_diaria": "1.00", "vr_diaria": d, "vr_passagem": ps})
                # trecho de volta da mesma viagem
                linhas.append({"id_favorecido": fav, "id_funcao_scdp": fun, "id_cidade_origem": dest, "id_cidade_destino": "1",
                               "id_documento_viagem": str(doc), "ordem_trecho": "2", "dt_inicio_trecho": dia, "dt_fim_trecho": dia,
                               "qt_diaria": "0.00", "vr_diaria": "0.00", "vr_passagem": "0.00"})
        else:
            return b""
        import gzip as _gz
        return _gz.compress(_csv(cols, linhas, sep=";").encode("utf-8"))

    def proposicoes_csv(self, ano: int) -> bytes:
        """Deputado i apresenta i % 5 projetos por ano; o 1º de cada um vira lei. Também requerimentos aprovados
        (não contam como projeto aprovado) e coautoria (não conta como autor)."""
        linhas, n = [], 1
        for d in self.deputados:
            i = d["id"] - 20000
            aut = [{"id": d["id"], "nome": f"Deputado {d['nome']}", "partido": d["partido"]}]
            outro = self.deputados[(i + 1) % len(self.deputados)]
            for k in range(i % 5):
                sit = "Transformado em norma jurídica" if k == 0 else "Aguardando parecer em comissão"
                linhas.append({"Codigo": f"PL {n}/{ano}", "TipoProposicao": "PROJETO DE LEI", "SiglaTipoProposicao": "PL", "Numero": n,
                               "Ano": ano, "Ementa": f"Dispõe sobre o tema {n}.", "Situacao": sit, "DataPublicacao": f"0{1 + k}/03/{ano}",
                               "Legislatura": "20", "Autores": json.dumps(aut + [{"id": outro["id"], "nome": outro["nome"], "partido": ""}])})
                n += 1
            linhas.append({"Codigo": f"RQN {n}/{ano}", "SiglaTipoProposicao": "RQN", "Numero": n, "Ano": ano, "Situacao": "Aprovado",
                           "Autores": json.dumps(aut)})
            n += 1
        linhas.append({"Codigo": f"MSG 1/{ano}", "SiglaTipoProposicao": "MSG", "Numero": 1, "Ano": ano, "Situacao": "Publicado", "Autores": ""})
        return _csv(PROP_COLS, linhas).encode()

    def _emendas(self) -> None:
        linhas = []
        num = 1000
        for ano in self.anos[:-1]:
            for i, d in enumerate(self.deputados[:10]):
                for c, cidade in enumerate(CIDADES_EMENDAS):
                    ind = 100_000.0 * (i + 1) + 1000 * c
                    pago = ind if c % 2 == 0 else ind / 2
                    linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Tipo de Indicação": "CELEBRAÇÃO DE CONVÊNIO",
                                   "Status da Indicação": "APROVADO", "Autor": d["nome"].upper(), "Unidade Orçamentária Sigla": "SES",
                                   "Unidade Orçamentária Descrição": "FUNDO ESTADUAL DE SAÚDE", "Função Descrição": "SAÚDE",
                                   "Município ": cidade, "Estado": "MINAS GERAIS", "Descrição do Tipo de Beneficiário": "MUNICÍPIO",
                                   "Nome Beneficiário": f"MUNICIPIO DE {cidade}", "Número do CNPJ do Beneficiário": "1,80259E+13",
                                   "Descrição da Indicação": "Custeio (SES) - compra de ambulância", "Valor Indicado": _reais(ind),
                                   "Valor Pago Atualizado": _reais(pago), "Status": "Pago Total" if pago == ind else "Pago Parcial",
                                   "Justificativa de Reprovação": "-", "Tipo de autoria": "Individual"})
                    num += 1
            # reprovada (não vira dinheiro), com justificativa de várias linhas dentro das aspas
            linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Status da Indicação": "REPROVADO PELO ÓRGÃO",
                           "Autor": self.deputados[0]["nome"].upper(), "Município ": "ITAJUBÁ", "Nome Beneficiário": "SANTA CASA",
                           "Valor Indicado": "R$999.999,00", "Valor Pago Atualizado": "R$0,00", "Status": "Reprovado",
                           "Justificativa de Reprovação": "Prezado(a),\r\nbeneficiário irregular; ver \"CAGEC\"."})
            num += 1
            # autor que não está mais em exercício
            linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Status da Indicação": "APROVADO", "Autor": "EX DEPUTADO ANTIGO",
                           "Município ": "PARAISÓPOLIS", "Nome Beneficiário": "ASSOCIACAO DE MORADORES", "Valor Indicado": "R$50.000,00",
                           "Valor Pago Atualizado": "-", "Status": "-", "Função Descrição": "ASSISTÊNCIA SOCIAL"})
            num += 1
        linhas.append(dict(linhas[0]))  # repetida: entra uma vez só
        self.emendas_linhas = linhas
        val = {}
        for r in linhas[:-1]:
            if r["Status da Indicação"] != "APROVADO":
                continue
            k = (int(r["Ano da Indicação"]), r["Município "])
            v = val.setdefault(k, [0.0, 0.0])
            v[0] += float(r["Valor Indicado"][2:].replace(".", "").replace(",", "."))
            pg = r["Valor Pago Atualizado"]
            v[1] += float(pg[2:].replace(".", "").replace(",", ".")) if pg.startswith("R$") else 0
        self.esperado["emendas"] = val

    def emendas_csv(self) -> bytes:
        return _csv(EMENDAS_COLS, self.emendas_linhas, sep=";", quoting=csv.QUOTE_MINIMAL).encode("latin-1")

    def pagina_emendas(self) -> bytes:
        return (b'<!doctype html><html><body><a href="https://mediaserver.almg.gov.br/acervo/1/2/999.csv">Baixar emendas (CSV)</a>'
                b'</body></html>')

    # ------------------------------------------------------------ Tesouro (SICONFI)
    def entes(self) -> bytes:
        itens = [{"cod_ibge": c, "ente": n.title().replace("Itajubá", "Itajubá"), "uf": "MG", "esfera": "M", "exercicio": 2026}
                 for n, c in ENTES.items()]
        itens.append({"cod_ibge": 31, "ente": "Minas Gerais", "uf": "MG", "esfera": "E"})
        itens.append({"cod_ibge": 3532405, "ente": "Itajubá", "uf": "SP", "esfera": "M"})  # mesmo nome, outro estado
        return json.dumps({"items": itens, "hasMore": False}, ensure_ascii=False).encode()

    def dca(self, ano: int, cod: int) -> bytes:
        nome = next((n for n, c in ENTES.items() if c == cod), None)
        if not nome or ano >= 2026:
            return json.dumps({"items": []}).encode()
        inst = f"Prefeitura Municipal de {nome.title()} - MG"
        itens = []
        fator = 1 + (ano - 2018) / 10
        for col, f in (("Despesas Empenhadas", 1.1), ("Despesas Liquidadas", 1.0), ("Despesas Pagas", 0.9),
                       ("Inscrição de Restos a Pagar Processados", 0.05), ("Inscrição de Restos a Pagar Não Processados", 0.07)):
            for k, (cf, nf, subs) in enumerate(FUNCOES):
                v = round(1_000_000 * (len(FUNCOES) - k) * fator * f, 2)
                itens.append({"exercicio": ano, "instituicao": inst, "cod_ibge": cod, "anexo": "DCA-Anexo I-E", "coluna": col,
                              "rotulo": "Total Geral da Despesa por Função", "conta": f"{cf} - {nf}", "valor": v})
                for j, (cs, ns) in enumerate(subs):
                    itens.append({"exercicio": ano, "instituicao": inst, "cod_ibge": cod, "coluna": col, "rotulo": "Total Geral da Despesa por Função",
                                  "conta": f"{cf}.{cs} - {ns}", "valor": round(v / (j + 2), 2)})
            itens.append({"exercicio": ano, "instituicao": inst, "coluna": col, "conta": "Despesas Exceto Intraorçamentárias", "valor": 9e9})
            itens.append({"exercicio": ano, "instituicao": inst, "coluna": col, "rotulo": "Despesas Intraorçamentárias",
                          "conta": "10 - Saúde", "valor": 7e8})
        return json.dumps({"items": itens}, ensure_ascii=False).encode()

    # ------------------------------------------------------------ CGU (arquivo do coletor nacional)
    def emendas_federais_zip(self, destino: Path) -> Path:
        cab = ["Código da Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda", "Número da emenda", "Tipo de Emenda",
               "Ano/Mês", "Código do Favorecido", "Favorecido", "Natureza Jurídica", "Tipo Favorecido", "UF Favorecido",
               "Município Favorecido", "Valor Recebido"]
        fav = [
            ["1", "1", "FULANO FEDERAL", "1", "Individual", "202405", "18.025.940/0001-09", "MUNICIPIO DE ITAJUBA", "Município",
             "Pessoa Jurídica", "MG", "ITAJUBÁ", "300.000,00"],
            ["2", "2", "CICLANO SENADOR", "2", "Individual", "202503", "21.035.900/0001-50", "SANTA CASA DE MISERICORDIA DE ITAJUBA",
             "Entidade", "Pessoa Jurídica", "MG", "ITAJUBA", "150.000,00"],
            ["3", "1", "FULANO FEDERAL", "3", "Individual", "202503", f"***.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-**",
             "MARIA DE TAL", "", "Pessoa Física", "MG", "ITAJUBÁ", "1.000,00"],
            ["4", "1", "FULANO FEDERAL", "4", "Individual", "202503", "46.395.000/0001-39", "MUNICIPIO DE ITAJUBA", "Município",
             "Pessoa Jurídica", "SP", "ITAJUBÁ", "77.000,00"],  # cidade de mesmo nome em outro estado
        ]
        destino.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destino, "w") as z:
            z.writestr("EmendasParlamentares_PorFavorecido.csv", _csv(cab, [dict(zip(cab, f)) for f in fav], sep=";").encode("latin-1"))
            z.writestr("EmendasParlamentares.csv", "Código da Emenda;Ano da Emenda\r\n1;2024\r\n".encode("latin-1"))
        self.esperado["federais_itajuba"] = 451_000.0
        return destino

    # ------------------------------------------------------------ roteador
    def _rota(self, url: str, params: dict) -> tuple[int, bytes, str]:
        u = urlparse(url)
        q = {**{k: v[0] for k, v in parse_qs(u.query).items()}, **{k: str(v) for k, v in (params or {}).items()}}
        if "tse.jus.br" in u.netloc:
            try:
                return 200, self.tse.responder(url), "application/zip"
            except requests.HTTPError:
                return 404, b"", "text/html"
        if u.netloc == "dadosabertos.almg.gov.br":
            m = re.search(r"/verbas_indenizatorias/deputados/(\d+)/(\d{4})/(\d{1,2})$", u.path)
            if m:
                return 200, self.verba_mes(int(m.group(1)), int(m.group(2)), int(m.group(3))), "application/json"
            if u.path.endswith("/deputados/em_exercicio"):
                return 200, self.em_exercicio(), "application/json"
            if u.path == "/arquivo/deputados/download":
                return 200, self.deputados_csv(), "text/csv"
            if u.path == "/arquivo/proposicoes/download":
                return 200, self.proposicoes_csv(int(q.get("ano", 0))), "text/csv"
        if u.netloc == "www.almg.gov.br" and "emendas-parlamentares" in u.path:
            return 200, self.pagina_emendas(), "text/html"
        if u.netloc == "mediaserver.almg.gov.br" and u.path.endswith(".csv"):
            return 200, self.emendas_csv(), "text/csv"
        if u.netloc == "dados.mg.gov.br":
            if u.path == "/api/3/action/package_show":
                return 200, self.ckan(q.get("id", "")), "application/json"
            if u.path.endswith(".csv") and "servidores-" in u.path:
                return 200, self.salarios_csv(), "text/csv"
            if u.path.endswith(".csv.gz"):
                nome = u.path.rsplit("/", 1)[-1][: -len(".csv.gz")]
                corpo = self.scdp(nome)
                return (200, corpo, "application/gzip") if corpo else (404, b"", "text/html")
        if u.netloc == "apidatalake.tesouro.gov.br":
            if u.path.endswith("/entes"):
                return 200, self.entes(), "application/json"
            if u.path.endswith("/dca"):
                return 200, self.dca(int(q.get("an_exercicio", 0)), int(q.get("id_ente", 0))), "application/json"
        return 404, b"", "text/html"

    def responder(self, method: str, url: str, params=None) -> requests.Response:
        full = url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")
        self.chamadas.append(full)
        modo = next((m for p, m in self.falhas.items() if p in full), None)
        if modo == "fora":
            raise requests.ConnectionError(f"caos: fora do ar {full}")
        if modo in ("500", "429"):
            return _resp(int(modo), b"erro", full)
        if modo == "html":
            return _resp(200, b"<!DOCTYPE html><html><body>Em manutencao</body></html>", full, "text/html")
        if modo == "vazio":
            return _resp(200, b"", full)
        status, corpo, tipo = self._rota(url, params or {})
        if modo == "cortado":
            corpo = corpo[: len(corpo) // 2]
        if modo == "sem_coluna":
            primeira, _, resto = corpo.partition(b"\n")
            corpo = primeira.replace(b"Autor", b"Quem").replace(b"Valor", b"Montante").replace(b"Autores", b"Quem") + b"\n" + resto
        return _resp(status, corpo, full, tipo)


def _resp(status: int, corpo: bytes, url: str, tipo: str = "application/json") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = corpo
    r._content_consumed = True
    r.url = url
    r.headers["content-type"] = tipo
    r.encoding = "utf-8"
    return r


def instalar(monkeypatch, fake: FakeEstado) -> FakeEstado:
    """Troca a internet pelo FakeEstado (e o TSE simulado) e tira as esperas entre tentativas."""
    def request(self, method, url, params=None, **kw):
        cab = {**self.headers, **(kw.get("headers") or {})}
        if "/arquivo/" in url and "json" in cab.get("Accept", ""):
            # como a ALMG em 23/10/2026: os arquivos não vêm com o cabeçalho padrão da coleta
            return _resp(406, b"<html>Not Acceptable</html>", url, "text/html")
        return fake.responder(method.upper(), url, params)
    monkeypatch.setattr(requests.Session, "request", request)
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    return fake
