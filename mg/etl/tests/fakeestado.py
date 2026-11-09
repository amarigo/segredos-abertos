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
# Outros municípios de Minas na lista de entes do Tesouro (sem contas simuladas)
OUTROS_MG = {"Belo Horizonte": 3106200, "Pouso Alegre": 3152501, "Ubá": 3169901}


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
        # Teve mandato nesta legislatura e saiu do cargo (suplente que devolveu a vaga): não está em em_exercicio,
        # mas está no arquivo 'deputados' e tem verba, projeto e emenda nos anos acompanhados
        self.saiu = [{"id": 20900, "nome": "Beltrana Que Saiu", "partido": "PV"}]
        # Quem está no arquivo com outro nome (o nome antigo também acha a pessoa na busca)
        self.nome_no_arquivo = {20005: "Professor Fulano 05"}
        self.legislaturas_saiu = "19,20"
        # A ALMG não tem foto publicada deste deputado: o site mostra as iniciais
        self.sem_foto = {20007}
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
        linhas = [{"Codigo": d["id"], "Nome": self.nome_no_arquivo.get(d["id"], d["nome"]), "Partido": d["partido"],
                   "Legislaturas": "20", "UltimaLegislatura": "20",
                   "PaginaAlmg": f"https://www.almg.gov.br/deputados/fulano-{d['id']}/{d['id']}"} for d in self.deputados]
        linhas += [{"Codigo": d["id"], "Nome": d["nome"], "Partido": d["partido"], "Legislaturas": self.legislaturas_saiu,
                    "UltimaLegislatura": self.legislaturas_saiu.split(",")[-1],
                    "PaginaAlmg": f"https://www.almg.gov.br/deputados/beltrana-{d['id']}/{d['id']}"} for d in self.saiu]
        linhas.append({"Codigo": 1, "Nome": "Antigo", "Partido": "PFL", "Legislaturas": "8", "UltimaLegislatura": "8",
                       "PaginaAlmg": "javascript:alert(1)"})
        return _csv(["Codigo", "Nome", "Partido", "Legislaturas", "UltimaLegislatura", "PaginaAlmg"], linhas).encode()

    def verba_mes(self, dep: int, ano: int, mes: int) -> bytes:
        """API da verba: os 20 primeiros deputados gastam (i+1) mil de combustível (CNPJ) e 500 de aluguel com pessoa
        física (CPF) em janeiro, fevereiro e março; os outros meses vêm vazios. Quem saiu do cargo gasta como o
        deputado 7, só em janeiro e fevereiro (depois já não estava no cargo)."""
        i = dep - 20000
        if dep in {d["id"] for d in self.saiu}:
            i = 7 if mes <= 2 else 99
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
                               "Resumo": f"Cria regras para o tema {n} nas escolas estaduais.", "Indexacao": "EDUCAÇÃO, ENSINO SUPERIOR",
                               "NomeFaseAtual": "1º turno", "Regime": "Ordinário",
                               "Legislatura": "20", "Autores": json.dumps(aut + [{"id": outro["id"], "nome": outro["nome"], "partido": ""}])})
                n += 1
            linhas.append({"Codigo": f"RQN {n}/{ano}", "SiglaTipoProposicao": "RQN", "Numero": n, "Ano": ano, "Situacao": "Aprovado",
                           "Autores": json.dumps(aut)})
            n += 1
        for d in self.saiu:
            linhas.append({"Codigo": f"PL {n}/{ano}", "TipoProposicao": "PROJETO DE LEI", "SiglaTipoProposicao": "PL", "Numero": n,
                           "Ano": ano, "Ementa": f"Dispõe sobre o tema {n}.", "Situacao": "Aguardando parecer em comissão",
                           "DataPublicacao": f"10/01/{ano}", "Legislatura": "20",
                           "Autores": json.dumps([{"id": d["id"], "nome": f"Deputada {d['nome']}", "partido": d["partido"]}])})
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
                                   # "Não há": a ALMG escreve isso quando o deputado não descreveu a indicação
                                   "Descrição da Indicação": "Não há" if c % 2 else "Custeio (SES) - compra de ambulância",
                                   "Categoria": "CUSTEIO" if c % 2 else "INVESTIMENTO", "Especificação": "-",
                                   "Tipo de Aplicação": "ATENÇÃO PRIMÁRIA À SAÚDE" if c % 2 else "AQUISIÇÃO DE VEÍCULO",
                                   "Nome da Ação": "ATENÇÃO PRIMÁRIA À SAÚDE", "Grupo de Despesa Descrição":
                                   "OUTRAS DESPESAS CORRENTES" if c % 2 else "INVESTIMENTOS", "Valor Indicado": _reais(ind),
                                   "Valor Empenhado no Ano": _reais(ind), "Valor Pago Atualizado": _reais(pago),
                                   "Status": "Pago Total" if pago == ind else "Pago Parcial",
                                   "Justificativa de Reprovação": "-", "Tipo de autoria": "Individual"})
                    num += 1
            # reprovada (não vira dinheiro), com justificativa de várias linhas dentro das aspas
            linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Status da Indicação": "REPROVADO PELO ÓRGÃO",
                           "Autor": self.deputados[0]["nome"].upper(), "Município ": "ITAJUBÁ", "Nome Beneficiário": "SANTA CASA",
                           "Valor Indicado": "R$999.999,00", "Valor Pago Atualizado": "R$0,00", "Status": "Reprovado",
                           "Justificativa de Reprovação": "Prezado(a),\r\nbeneficiário irregular; ver \"CAGEC\"."})
            num += 1
            for d in self.saiu:  # quem saiu do cargo também indicou emendas
                linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Status da Indicação": "APROVADO",
                               "Autor": d["nome"].upper(), "Município ": "ITAJUBÁ", "Nome Beneficiário": "MUNICIPIO DE ITAJUBA",
                               "Valor Indicado": "R$70.000,00", "Valor Pago Atualizado": "R$70.000,00", "Status": "Pago Total",
                               "Função Descrição": "SAÚDE", "Tipo de autoria": "Individual"})
                num += 1
            # bloco parlamentar, execução direta pelo órgão do estado (município ainda a definir)
            linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Status da Indicação": "APROVADO",
                           "Tipo de Indicação": "EXECUÇÃO DIRETA", "Autor": "BLOCO MINAS EM FRENTE",
                           "Unidade Orçamentária Descrição": "POLÍCIA MILITAR DO ESTADO DE MINAS GERAIS",
                           "Nome da Ação": "ESTRUTURAÇÃO E MODERNIZAÇÃO", "Grupo de Despesa Descrição": "INVESTIMENTOS",
                           "Município ": "A SER DEFINIDO PELO ÓRGÃO", "Nome Beneficiário": "A SER DEFINIDO PELO ÓRGÃO",
                           "Descrição da Indicação": "Aquisição de armamento para o 39º BPM de Contagem.",
                           "Valor Indicado": "R$300.000,00", "Valor Empenhado no Ano": "R$300.000,00",
                           "Valor Pago Atualizado": "R$0,00", "Status": "Empenhado", "Tipo de autoria": "Bloco/Bancada"})
            num += 1
            # cidade de nome curto, que o arquivo escreve em maiúsculas, e entidade de outro estado
            for mun, uf, ben in (("UBÁ", "MINAS GERAIS", "HOSPITAL SAO VICENTE DE PAULO DE UBA"),
                                 ("BRASÍLIA", "DISTRITO FEDERAL", "ASSOCIACAO NACIONAL DE APOIO")):
                linhas.append({"Ano da Indicação": ano, "Número da Indicação": num, "Status da Indicação": "APROVADO",
                               "Tipo de Indicação": "CELEBRAÇÃO DE CONVÊNIO", "Autor": self.deputados[1]["nome"].upper(),
                               "Município ": mun, "Estado": uf, "Nome Beneficiário": ben, "Valor Indicado": "R$40.000,00",
                               "Valor Pago Atualizado": "R$40.000,00", "Status": "Pago Total", "Função Descrição": "SAÚDE"})
                num += 1
            # autor que não está no arquivo de deputados (nome escrito de outro jeito)
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
        itens += [{"cod_ibge": c, "ente": n, "uf": "MG", "esfera": "M"} for n, c in OUTROS_MG.items()]
        itens.append({"cod_ibge": 31, "ente": "Minas Gerais", "uf": "MG", "esfera": "E"})
        itens.append({"cod_ibge": 3532405, "ente": "Itajubá", "uf": "SP", "esfera": "M"})  # mesmo nome, outro estado
        return json.dumps({"items": itens, "hasMore": False}, ensure_ascii=False).encode()

    def dca(self, ano: int, cod: int) -> bytes:
        nome = "Minas Gerais" if cod == 31 else next((n for n, c in ENTES.items() if c == cod), None)
        if not nome or ano >= 2026:
            return json.dumps({"items": []}).encode()
        inst = "Governo do Estado de Minas Gerais" if cod == 31 else f"Prefeitura Municipal de {nome.title()} - MG"
        itens = []
        fator = (1 + (ano - 2018) / 10) * (500 if cod == 31 else 1)
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

    def rreo2(self, ano: int, bim: int, cod: int) -> bytes:
        """Anexo 02 do RREO, como o Tesouro devolve: funções e subfunções na coluna "conta", na ordem do relatório.
        Publicado até o bimestre 4 em 2026 (agosto) e o ano inteiro antes."""
        nome = "Minas Gerais" if cod == 31 else next((n for n, c in ENTES.items() if c == cod), None)
        if not nome or ano > 2026 or (ano == 2026 and bim > 4):
            return json.dumps({"items": []}).encode()
        inst = "Governo do Estado de Minas Gerais" if cod == 31 else f"Prefeitura Municipal de {nome.title()} - MG"
        fator = (1 + (ano - 2018) / 10) * (500 if cod == 31 else 1) * bim / 6
        linhas = []
        for k, (_cf, nf, subs) in enumerate(FUNCOES):
            v = round(1_000_000 * (len(FUNCOES) - k) * fator, 2)
            linhas.append((nf, v))
            partes = [round(v / 2, 2)] * (len(subs) - 1)
            linhas += [(ns, x) for (_cs, ns), x in zip(subs, partes + [round(v - sum(partes), 2)])]
        total = sum(v for (n, v) in linhas if n in {f[1] for f in FUNCOES})
        linhas = [("DESPESAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)", total)] + linhas + [("DESPESAS (INTRA-ORÇAMENTÁRIAS) (II)", 7e8)]
        itens = []
        for col, k in (("DOTAÇÃO ATUALIZADA (a)", 1.6), ("DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 1.1),
                       ("DESPESAS LIQUIDADAS ATÉ O BIMESTRE (d)", 1.0)):
            itens += [{"exercicio": ano, "periodo": bim, "instituicao": inst, "cod_ibge": cod, "anexo": "RREO-Anexo 02",
                       "rotulo": "Total das Despesas Exceto Intra-Orçamentárias", "coluna": col, "cod_conta": "RREO2TotalDespesas",
                       "conta": n, "valor": round(v * k, 2)} for n, v in linhas]
        return json.dumps({"items": itens}, ensure_ascii=False).encode()

    # ------------------------------------------------------------ CGU (arquivo do coletor nacional)
    # Códigos das emendas como no Portal: ano + autor + número
    EMENDA_PIX = "202541280005"      # emenda Pix para Itajubá, com plano de ação e gastos no Transferegov
    EMENDA_SAUDE = "202512340002"    # emenda com finalidade definida, paga à Santa Casa de Itajubá
    EMENDA_SEM_PAGAR = "202541280006"  # emenda Pix para Itajubá ainda não paga
    CNPJ_ITAJUBA = "18025940000109"

    def emendas_federais_zip(self, destino: Path) -> Path:
        cab = ["Código da Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda", "Número da emenda", "Tipo de Emenda",
               "Ano/Mês", "Código do Favorecido", "Favorecido", "Natureza Jurídica", "Tipo Favorecido", "UF Favorecido",
               "Município Favorecido", "Valor Recebido"]
        fav = [
            ["202400010001", "1", "FULANO FEDERAL", "1", "Individual", "202405", "18.025.940/0001-09", "MUNICIPIO DE ITAJUBA", "Município",
             "Pessoa Jurídica", "MG", "ITAJUBÁ", "300.000,00"],
            [self.EMENDA_SAUDE, "2", "CICLANO SENADOR", "2", "Individual", "202503", "21.035.900/0001-50", "SANTA CASA DE MISERICORDIA DE ITAJUBA",
             "Entidade", "Pessoa Jurídica", "MG", "ITAJUBA", "100.000,00"],
            [self.EMENDA_SAUDE, "2", "CICLANO SENADOR", "2", "Individual", "202507", "21.035.900/0001-50", "SANTA CASA DE MISERICORDIA DE ITAJUBA",
             "Entidade", "Pessoa Jurídica", "MG", "ITAJUBA", "50.000,00"],
            ["202500010003", "1", "FULANO FEDERAL", "3", "Individual", "202503", f"***.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-**",
             "MARIA DE TAL", "", "Pessoa Física", "MG", "ITAJUBÁ", "1.000,00"],
            ["202500010004", "1", "FULANO FEDERAL", "4", "Individual", "202503", "46.395.000/0001-39", "MUNICIPIO DE ITAJUBA", "Município",
             "Pessoa Jurídica", "SP", "ITAJUBÁ", "77.000,00"],  # cidade de mesmo nome em outro estado
            [self.EMENDA_PIX, "4128", "FULANO FEDERAL", "5", "Individual - Transferências Especiais", "202504", "18.025.940/0001-09",
             "MUNICIPIO DE ITAJUBA", "Município", "Pessoa Jurídica", "MG", "ITAJUBA", "500.000,00"],
        ]
        principal_cab = ["Código da Emenda", "Ano da Emenda", "Tipo de Emenda", "Código do Autor da Emenda", "Nome do Autor da Emenda",
                         "Número da emenda", "Localidade de aplicação do recurso", "Código Município IBGE", "Município", "Código UF IBGE",
                         "UF", "Nome Função", "Nome Subfunção", "Nome Ação", "Valor Empenhado", "Valor Liquidado", "Valor Pago",
                         "Valor Restos A Pagar Pagos"]
        principal = [
            ["202400010001", "2024", "Emenda Individual - Transferências com Finalidade Definida", "1", "FULANO FEDERAL", "1",
             "ITAJUBA - MG", "3132404", "ITAJUBÁ", "31", "MINAS GERAIS", "SAUDE", "ATENCAO BASICA", "", "300.000,00", "300.000,00",
             "300.000,00", "0,00"],
            # a mesma emenda em duas linhas (duas ações do Orçamento): os valores se somam
            [self.EMENDA_SAUDE, "2025", "Emenda Individual - Transferências com Finalidade Definida", "1234", "CICLANO SENADOR", "2",
             "MINAS GERAIS (UF)", "", "", "31", "MINAS GERAIS", "SAUDE", "ASSISTENCIA HOSPITALAR E AMBULATORIAL",
             "INCREMENTO TEMPORARIO AO CUSTEIO DOS SERVICOS DE ATENCAO ESPECIALIZADA", "120.000,00", "100.000,00", "100.000,00", "0,00"],
            [self.EMENDA_SAUDE, "2025", "Emenda Individual - Transferências com Finalidade Definida", "1234", "CICLANO SENADOR", "2",
             "MINAS GERAIS (UF)", "", "", "31", "MINAS GERAIS", "SAUDE", "ASSISTENCIA HOSPITALAR E AMBULATORIAL",
             "ESTRUTURACAO DE UNIDADES DE ATENCAO ESPECIALIZADA", "30.000,00", "0,00", "0,00", "50.000,00"],
            ["202500010003", "2025", "Emenda Individual - Transferências com Finalidade Definida", "1", "FULANO FEDERAL", "3",
             "ITAJUBA - MG", "3132404", "ITAJUBÁ", "31", "MINAS GERAIS", "ASSISTENCIA SOCIAL", "", "", "1.000,00", "1.000,00",
             "1.000,00", "0,00"],
            ["202500010004", "2025", "Emenda Individual - Transferências com Finalidade Definida", "1", "FULANO FEDERAL", "4",
             "ITAJUBA - SP", "3523503", "ITAJUBÁ", "35", "SAO PAULO", "URBANISMO", "", "", "77.000,00", "77.000,00", "77.000,00", "0,00"],
            [self.EMENDA_PIX, "2025", "Emenda Individual - Transferências Especiais", "4128", "FULANO FEDERAL", "5",
             "ITAJUBA - MG", "3132404", "ITAJUBÁ", "31", "MINAS GERAIS", "ENCARGOS ESPECIAIS", "TRANSFERENCIAS", "",
             "500.000,00", "500.000,00", "500.000,00", "0,00"],
            [self.EMENDA_SEM_PAGAR, "2025", "Emenda Individual - Transferências Especiais", "4128", "FULANO FEDERAL", "6",
             "ITAJUBA - MG", "3132404", "ITAJUBÁ", "31", "MINAS GERAIS", "ENCARGOS ESPECIAIS", "TRANSFERENCIAS", "",
             "200.000,00", "0,00", "0,00", "0,00"],
        ]
        destino.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destino, "w") as z:
            z.writestr("EmendasParlamentares_PorFavorecido.csv", _csv(cab, [dict(zip(cab, f)) for f in fav], sep=";").encode("latin-1"))
            z.writestr("EmendasParlamentares.csv",
                       _csv(principal_cab, [dict(zip(principal_cab, f)) for f in principal], sep=";").encode("latin-1"))
        self.esperado["federais_itajuba"] = 951_000.0
        return destino

    # ------------------------------------------------------------ PNCP (licitações e contratos)
    def _pncp(self) -> None:
        """Compras e contratos no formato da API de consulta do PNCP (conferido na sondagem de 08/11/2026)."""
        def compra(cnpj, razao, esfera, ibge, municipio, seq, mod, data, objeto, est, hom, sit=1, amparo=None):
            nomes = {6: "Pregão - Eletrônico", 8: "Dispensa", 9: "Inexigibilidade", 4: "Concorrência - Eletrônica", 12: "Credenciamento"}
            return {"valorTotalHomologado": hom, "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": razao, "poderId": "E", "esferaId": esfera},
                    "anoCompra": int(data[:4]), "sequencialCompra": seq, "numeroCompra": str(seq), "processo": f"{seq}/{data[:4]}",
                    "objetoCompra": objeto, "dataPublicacaoPncp": f"{data}T10:00:00", "srp": False,
                    "unidadeOrgao": {"ufNome": "Minas Gerais", "ufSigla": "MG", "municipioNome": municipio, "codigoIbge": str(ibge),
                                     "codigoUnidade": "1", "nomeUnidade": razao},
                    "amparoLegal": amparo or {"codigo": 1, "nome": "Lei 14.133/2021, Art. 28, I", "descricao": "Pregão"},
                    "numeroControlePNCP": f"{cnpj}-1-{seq:06d}/{data[:4]}", "valorTotalEstimado": est, "modalidadeId": mod,
                    "modalidadeNome": nomes.get(mod, "Outra"), "situacaoCompraId": sit,
                    "situacaoCompraNome": {1: "Divulgada no PNCP", 2: "Revogada", 3: "Anulada", 4: "Suspensa"}[sit]}
        ita, par = ENTES["ITAJUBÁ"], ENTES["PARAISÓPOLIS"]
        pref, cam, unifei, see = "18025940000109", "00993308000185", "21040001000130", "18715599000105"
        dispensa = {"codigo": 19, "nome": "Lei 14.133/2021, Art. 75, II",
                    "descricao": "Dispensa de Licitação: para contratação que envolva valores inferiores a R$ 50.000,00"}
        inex = {"codigo": 24, "nome": "Lei 14.133/2021, Art. 74, II",
                "descricao": "Inexigibilidade: contratação de profissional do setor artístico"}
        self.compras_pncp = [
            compra(pref, "MUNICIPIO DE ITAJUBA", "M", ita, "Itajubá", 1, 6, "2025-03-10", "Asfalto para ruas do centro", 900000.0, 800000.0),
            compra(pref, "MUNICIPIO DE ITAJUBA", "M", ita, "Itajubá", 2, 8, "2025-03-12",
                   f"Medicamento para mandado judicial de FULANO CPF {CPF_EMITENTE[:3]}.{CPF_EMITENTE[3:6]}.{CPF_EMITENTE[6:9]}-{CPF_EMITENTE[9:]}",
                   10000.0, 9000.0, amparo=dispensa),
            compra(pref, "MUNICIPIO DE ITAJUBA", "M", ita, "Itajubá", 3, 9, "2025-07-01", "Show da festa da cidade", 150000.0, 150000.0, amparo=inex),
            compra(pref, "MUNICIPIO DE ITAJUBA", "M", ita, "Itajubá", 4, 6, "2025-08-01", "Compra cancelada de veículos", 300000.0, None, sit=2),
            compra(cam, "ITAJUBA CAMARA MUNICIPAL", "M", ita, "Itajubá", 1, 8, "2026-02-03", "Papel e material de escritório", 5000.0, None, amparo=dispensa),
            # código do IBGE que devolve outra cidade (aconteceu na sondagem: um código errado trouxe Paraopeba)
            compra("18116160000166", "MUNICIPIO DE PARAOPEBA", "M", par, "Paraopeba", 1, 8, "2025-02-04", "Compra de outra cidade", 100.0, 100.0, amparo=dispensa),
            compra(unifei, "UNIVERSIDADE FEDERAL DE ITAJUBA", "F", ita, "Itajubá", 9, 8, "2025-03-15", "Compra da universidade federal", 7000.0, 7000.0, amparo=dispensa),
            compra(see, "MINAS GERAIS SECRETARIA DE ESTADO DA EDUCACAO", "E", ita, "Itajubá", 5, 8, "2026-03-20", "Merenda escolar", 4000.0, 4000.0, amparo=dispensa),
            compra(see, "MINAS GERAIS SECRETARIA DE ESTADO DA EDUCACAO", "E", 3106200, "Belo Horizonte", 6, 4, "2026-05-05", "Reforma de escolas", 2000000.0, 1800000.0),
        ]
        # Muitas compras do estado num mês, para passar de uma página (50 linhas)
        self.compras_pncp += [compra(see, "MINAS GERAIS SECRETARIA DE ESTADO DA EDUCACAO", "E", 3106200, "Belo Horizonte", 100 + i, 6,
                                     "2026-04-15", f"Material escolar lote {i}", 1000.0, 1000.0) for i in range(60)]

        def contrato(orgao, compra_seq, ano, seq, tipo, ni, nome, valor, fim):
            return {"numeroControlePncpCompra": f"{orgao}-1-{compra_seq:06d}/{ano}", "orgaoEntidade": {"cnpj": orgao, "esferaId": "M"},
                    "anoContrato": ano, "sequencialContrato": seq, "tipoPessoa": tipo, "niFornecedor": ni, "nomeRazaoSocialFornecedor": nome,
                    "objetoContrato": "Contrato", "valorInicial": valor, "valorGlobal": valor, "dataAssinatura": f"{ano}-04-01",
                    "dataVigenciaInicio": f"{ano}-04-01", "dataVigenciaFim": fim, "tipoContrato": {"id": 1, "nome": "Contrato (termo inicial)"},
                    "numeroControlePNCP": f"{orgao}-2-{seq:06d}/{ano}"}
        self.contratos_pncp = [
            contrato(pref, 1, 2025, 1, "PJ", "11222333000181", "ASFALTOS MINAS LTDA", 800000.0, "2027-04-01"),
            contrato(pref, 3, 2025, 2, "PF", CPF_EMITENTE, f"CANTOR FULANO {CPF_EMITENTE}", 150000.0, "2025-07-02"),
            contrato(see, 6, 2026, 3, "PJ", "44555666000199", "CONSTRUTORA ESCOLAR LTDA", 1800000.0, "2027-05-05"),
        ]
        self.esperado["licitacoes_itajuba_2025"] = 4  # sem a universidade federal e sem a escola estadual

    def pncp(self, caminho: str, q: dict) -> tuple[int, bytes, str]:
        if not hasattr(self, "compras_pncp"):
            self._pncp()
        di, df = q.get("dataInicial", ""), q.get("dataFinal", "")
        no_periodo = lambda d: di <= d.replace("-", "")[:8] <= df  # noqa: E731
        if caminho.endswith("/contratacoes/publicacao"):
            ls = [x for x in self.compras_pncp if str(x["modalidadeId"]) == q.get("codigoModalidadeContratacao")
                  and x["unidadeOrgao"]["ufSigla"] == q.get("uf") and no_periodo(x["dataPublicacaoPncp"])
                  and (not q.get("codigoMunicipioIbge") or x["unidadeOrgao"]["codigoIbge"] == q["codigoMunicipioIbge"])]
        elif caminho.endswith("/contratos"):
            ls = [x for x in self.contratos_pncp if x["orgaoEntidade"]["cnpj"] == q.get("cnpjOrgao") and no_periodo(x["dataAssinatura"])]
        else:
            return 404, b"", "text/html"
        if int(q.get("tamanhoPagina", 50)) > 50:
            return 400, json.dumps({"message": "Tamanho de página inválido"}).encode(), "application/json"
        if not ls:
            return 204, b"", "application/json"  # como o PNCP: nada no período é HTTP 204, sem corpo
        pag, tam = int(q.get("pagina", 1)), int(q.get("tamanhoPagina", 50))
        total_pag = (len(ls) + tam - 1) // tam
        corpo = {"data": ls[(pag - 1) * tam: pag * tam], "totalRegistros": len(ls), "totalPaginas": total_pag,
                 "numeroPagina": pag, "paginasRestantes": max(0, total_pag - pag), "empty": False}
        return 200, json.dumps(corpo, ensure_ascii=False).encode(), "application/json"

    def destino_pix(self, nacional: Path, ano: int = 2025) -> None:
        """Acrescenta aos dados nacionais o plano de ação da emenda Pix de Itajubá, no mesmo formato que o coletor nacional
        grava a partir da API do Transferegov (sa_etl/transferegov.py: resumir + gravar)."""
        from sa_etl import transferegov as T
        pid, eid, rid = 9001, 9002, 9003
        t = {
            "beneficiarios": {"linhas": [{"id_beneficiario": 77, "uf_beneficiario": "MG", "nome_beneficiario": "MUNICIPIO DE ITAJUBA",
                                          "cnpj_beneficiario": self.CNPJ_ITAJUBA}], "completo_em": f"{ano}-11-01"},
            "planos": {ano: {"completo_em": f"{ano}-11-01", "linhas": [{
                "id_plano_acao": pid, "codigo_plano_acao": f"09032{ano}-000777", "situacao_plano_acao": "CIENTE",
                "nome_parlamentar_emenda_plano_acao": "FULANO FEDERAL",
                "codigo_emenda_parlamentar_formatado_plano_acao": f"{self.EMENDA_PIX}-Fulano Federal",
                "ano_emenda_parlamentar_plano_acao": ano, "valor_custeio_plano_acao": 500000.0, "valor_investimento_plano_acao": 0.0,
                "id_beneficiario": 77, "nome_objeto": "Eventos", "detalhamento_objeto": "Realização da Festa do Peão e do Carnaval de rua",
                "codigo_descricao_areas_politicas_publicas_plano_acao": "13 - Cultura", "motivo_impedimento_plano_acao": None}]}},
            "executores": {"completo_em": f"{ano}-11-01", "linhas": [{
                "id_executor": eid, "id_plano_acao": pid, "cnpj_executor": self.CNPJ_ITAJUBA, "nome_executor": "MUNICIPIO DE ITAJUBA",
                "objeto_executor": "Festa do Peão de Itajubá", "vl_custeio_executor": 500000.0, "vl_investimento_executor": 0.0}]},
            "metas": {"completo_em": f"{ano}-11-01", "linhas": [{
                "id_executor": eid, "id_meta": 1, "sequencial_meta": 1, "nome_meta": "Shows artísticos", "desc_meta": "Contratação de 3 shows",
                "un_medida_meta": "unidade", "qt_unidade_meta": 3, "vl_custeio_emenda_especial_meta": 500000.0,
                "vl_investimento_emenda_especial_meta": 0.0}]},
            "relatorios": {"completo_em": f"{ano}-11-01", "linhas": [{
                "id_relatorio_gestao_novo": rid, "id_plano_acao": pid, "id_executor": eid, "data_relatorio_gestao_novo": f"{ano}-10-30",
                "valor_executado_relatorio_gestao_novo": 380000.0}]},
            "gastos": {"lidos": {str(rid): f"{ano}-11-01"}, "por_relatorio": {str(rid): [
                {"id_relatorio_gestao_dl": 1, "id_relatorio_gestao_novo": rid, "tx_descricao_relatorio_gestao_dl": "Show artístico na Festa do Peão",
                 "tp_doc_recebedor_relatorio_gestao_dl": "CNPJ", "tx_identificacao_recebedor_mascarado_relatorio_gestao_dl": "11.222.333/0001-81",
                 "tx_nome_recebedor_relatorio_gestao_dl": "PRODUTORA DE SHOWS LTDA", "vl_pagamento_relatorio_gestao_dl": 300000.0,
                 "dt_pagamento_relatorio_gestao_dl": f"{ano}-06-15", "tx_natureza_relatorio_gestao_dl": "CUSTEIO"},
                {"id_relatorio_gestao_dl": 2, "id_relatorio_gestao_novo": rid, "tx_descricao_relatorio_gestao_dl": "Palco e som do Carnaval",
                 "tp_doc_recebedor_relatorio_gestao_dl": "CPF", "tx_identificacao_recebedor_mascarado_relatorio_gestao_dl": "***.456.789-**",
                 "tx_nome_recebedor_relatorio_gestao_dl": "FULANO DO SOM", "vl_pagamento_relatorio_gestao_dl": 80000.0,
                 "dt_pagamento_relatorio_gestao_dl": f"{ano}-02-20", "tx_natureza_relatorio_gestao_dl": "CUSTEIO"}]}},
            "falta": [],
        }
        res = T.resumir(t, [ano])
        pasta = nacional / "emendas" / "destino"
        idx_f = pasta / f"{ano}.json"
        antigo = json.loads(idx_f.read_text(encoding="utf-8")) if idx_f.exists() else None
        T.gravar(nacional, res, t)
        if antigo:  # junta com o que o coletor nacional já tinha gravado
            novo = json.loads(idx_f.read_text(encoding="utf-8"))
            antigo["beneficiarios"] = [b for b in antigo["beneficiarios"] if b["cnpj"] != self.CNPJ_ITAJUBA] + novo["beneficiarios"]
            antigo["emendas"] = {**antigo.get("emendas", {}), **novo["emendas"]}
            idx_f.write_text(json.dumps(antigo, ensure_ascii=False), encoding="utf-8")

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
        m = re.fullmatch(r"/export/sites/portal/a-assembleia/deputados/fotos/(\d+)\.jpg", u.path)
        if u.netloc == "www.almg.gov.br" and m:
            if int(m.group(1)) in self.sem_foto:  # como a ALMG: a página de erro vem em HTML
                return 404, b"<html>Pagina nao encontrada</html>", "text/html"
            return 200, b"\xff\xd8\xff\xe0" + b"\0" * 4000, "image/jpeg"
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
            if u.path.endswith("/rreo"):
                return 200, self.rreo2(int(q.get("an_exercicio", 0)), int(q.get("nr_periodo", 0)), int(q.get("id_ente", 0))), "application/json"
            if u.path.endswith("/dca"):
                return 200, self.dca(int(q.get("an_exercicio", 0)), int(q.get("id_ente", 0))), "application/json"
        if u.netloc == "pncp.gov.br" and u.path.startswith("/api/consulta/v1/"):
            return self.pncp(u.path, q)
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
