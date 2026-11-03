"""Imita a API do Transferegov, módulo de Transferências Especiais (sa_etl/transferegov.py).

As emendas Pix são as mesmas do arquivo de emendas do FakeGov (deputados 0, 3, 6 e 9 de cada ano), todas para a
Prefeitura de São Paulo. Cada uma tem um executor, uma meta, um relatório de gestão e três pagamentos: dois para
empresas (um deles repetido num segundo relatório) e um para uma pessoa física, com o CPF mascarado como na API.
"""
from __future__ import annotations

import json

HOST = "api-publica.transferegov.gestao.gov.br"
CNPJ_SP = "46395000000139"


class Transferegov:
    def __init__(self, anos, deputados):
        self.anos = list(anos)
        self.tabelas: dict[str, list[dict]] = {k: [] for k in (
            "planos-acao-especiais", "beneficiarios-especiais", "executores-especiais", "relatorios-gestao-novos-especiais",
            "relatorios-gestao-documento-liquidacao-especiais", "meta-especiais")}
        self.pedidos = 0
        self.tabelas["beneficiarios-especiais"] = [
            {"id_beneficiario": 1, "uf_beneficiario": "SP", "nome_beneficiario": "MUNICIPIO DE SAO PAULO", "cnpj_beneficiario": CNPJ_SP, "id_ente": 1},
            {"id_beneficiario": 2, "uf_beneficiario": "SP", "nome_beneficiario": "MUNICIPIO DE CAMPINAS", "cnpj_beneficiario": "51885242000140", "id_ente": 2},
        ]
        dl = 0
        for ano in self.anos:
            for i, d in enumerate(deputados[:10]):
                if i % 3:
                    continue
                pid, eid, rid = ano * 1000 + i, ano * 1000 + i + 500, ano * 1000 + i + 700
                self.tabelas["planos-acao-especiais"].append({
                    "id_plano_acao": pid, "codigo_plano_acao": f"09032{ano}-{i:06d}", "ano_plano_acao": ano,
                    "situacao_plano_acao": "CIENTE", "nome_parlamentar_emenda_plano_acao": d["nome"].upper(),
                    "ano_emenda_parlamentar_plano_acao": ano, "codigo_parlamentar_emenda_plano_acao": 1000 + i,
                    "numero_emenda_parlamentar_plano_acao": i, "codigo_emenda_parlamentar_formatado_plano_acao": str(ano * 100 + i),
                    "valor_custeio_plano_acao": 600.0, "valor_investimento_plano_acao": 400.0, "id_beneficiario": 1,
                    "nome_objeto": "Pavimentação", "detalhamento_objeto": f"Pavimentação da Rua {i} e compra de ambulância",
                    "codigo_descricao_areas_politicas_publicas_plano_acao": "15 - Urbanismo",
                    "descricao_programacao_orcamentaria_plano_acao": "Transferências Especiais", "motivo_impedimento_plano_acao": None,
                    "numero_conta_plano_acao": "99999-9",  # a API traz a conta bancária; o coletor não guarda
                })
                self.tabelas["executores-especiais"].append({
                    "id_executor": eid, "id_plano_acao": pid, "cnpj_executor": CNPJ_SP, "nome_executor": "MUNICIPIO DE SAO PAULO",
                    "objeto_executor": f"Pavimentação da Rua {i}", "vl_custeio_executor": 600.0, "vl_investimento_executor": 400.0})
                self.tabelas["meta-especiais"].append({
                    "id_executor": eid, "id_meta": eid * 10, "sequencial_meta": 1, "nome_meta": "Pavimentar ruas",
                    "desc_meta": f"Asfalto novo na Rua {i}", "un_medida_meta": "m²", "qt_unidade_meta": 1200,
                    "vl_custeio_emenda_especial_meta": 600.0, "vl_investimento_emenda_especial_meta": 400.0})
                for k, data in ((0, f"{ano}-06-30"), (1, f"{ano}-12-31")):
                    self.tabelas["relatorios-gestao-novos-especiais"].append({
                        "id_relatorio_gestao_novo": rid + k, "id_plano_acao": pid, "id_executor": eid,
                        "data_relatorio_gestao_novo": data, "situacao_relatorio_gestao_novo": "DISPONIBILIZADO",
                        "valor_executado_relatorio_gestao_novo": 300.0 if k == 0 else 450.0, "valor_pendente_relatorio_gestao_novo": 550.0})
                gastos = [
                    (rid, "CNPJ", "12.345.678/0001-95", "OBRAS X LTDA", 300.0, f"{ano}-05-10", "Nota fiscal 123 - asfalto"),
                    (rid + 1, "CNPJ", "12.345.678/0001-95", "OBRAS X LTDA", 300.0, f"{ano}-05-10", "Nota fiscal 123 - asfalto"),  # repetido
                    (rid + 1, "CNPJ", "98.765.432/0001-10", "AMBULANCIAS Y SA", 100.0, f"{ano}-11-02", "Nota fiscal 77 - ambulância"),
                    (rid + 1, "CPF", "***.456.789-**", "FULANO DA SILVA", 50.0, f"{ano}-11-20", "Serviço de topografia"),
                ]
                for rel, tipo, doc, nome, valor, data, desc in gastos:
                    dl += 1
                    self.tabelas["relatorios-gestao-documento-liquidacao-especiais"].append({
                        "id_relatorio_gestao_dl": dl, "id_relatorio_gestao_novo": rel, "tx_descricao_relatorio_gestao_dl": desc,
                        "tp_doc_recebedor_relatorio_gestao_dl": tipo, "tx_identificacao_recebedor_mascarado_relatorio_gestao_dl": doc,
                        "tx_nome_recebedor_relatorio_gestao_dl": nome, "vl_pagamento_relatorio_gestao_dl": valor,
                        "dt_pagamento_relatorio_gestao_dl": data, "tx_natureza_relatorio_gestao_dl": "INVESTIMENTO"})

    def rota(self, netloc: str, path: str, q: dict) -> tuple[int, bytes, str] | None:
        if netloc != HOST or not path.startswith("/especiais/"):
            return None
        nome = path.split("/especiais/", 1)[1].strip("/")
        if nome not in self.tabelas:
            return 404, b'{"detail":"Not Found"}', "application/json"
        self.pedidos += 1
        linhas = self.tabelas[nome]
        filtros = {k: v for k, v in q.items() if k not in ("pagina", "tamanho_da_pagina")}
        for k, v in filtros.items():
            aceitos = {x.strip() for x in str(v).split(",")}
            linhas = [x for x in linhas if str(x.get(k)) in aceitos]
        tam = min(int(q.get("tamanho_da_pagina", 200)), 200)
        pag = int(q.get("pagina", 1))
        fatia = linhas[(pag - 1) * tam: pag * tam]
        corpo = {"data": fatia, "total_items": len(linhas), "total_pages": max(1, -(-len(linhas) // tam)),
                 "page_number": pag, "page_size": tam}
        return 200, json.dumps(corpo, ensure_ascii=False).encode(), "application/json"
