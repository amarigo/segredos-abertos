"""Respostas fictícias das fontes da comparação dos gabinetes: IBGE (estados, população e rendimento), página
"Gastos parlamentares" da Câmara, arquivo de funcionários da Câmara, página de cada deputado (só o bloco da verba
de gabinete e da equipe) e a API de recursos de cada senador.

Os números são inventados, mas coerentes: gasto mais o não utilizado dá o teto, e os meses somam o gasto.
"""
from __future__ import annotations

import json
import re

import fakegov_financas

UFS = {"35": ("SP", "São Paulo", 46_000_000, 4100.0), "31": ("MG", "Minas Gerais", 21_300_000, 3200.0),
       "33": ("RJ", "Rio de Janeiro", 17_200_000, 3900.0), "29": ("BA", "Bahia", 14_800_000, 2300.0),
       "53": ("DF", "Distrito Federal", 2_900_000, 5900.0), "51": ("MT", "Mato Grosso", 3_800_000, 3500.0)}
TETO_MES = 165806.07


def _br(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _json(x) -> tuple[int, bytes, str]:
    return 200, json.dumps(x, ensure_ascii=False).encode(), "application/json"


def _sidra(var: str, nome_var: str, periodo: str, nome_per: str, valor_de, por_sexo: bool = False) -> list:
    cab = {"NC": "Nível Territorial (Código)", "D1C": "Unidade da Federação (Código)", "D1N": "Unidade da Federação",
           "D2C": "Variável (Código)", "D2N": "Variável", "D3C": f"{nome_per} (Código)", "D3N": nome_per, "V": "Valor"}
    linhas = [{"NC": "3", "D1C": cod, "D1N": nome, "D2C": var, "D2N": nome_var, "D3C": periodo, "D3N": periodo, "V": str(valor_de(cod))}
              for cod, (_, nome, *_r) in UFS.items()]
    linhas.append({**linhas[0], "D1C": "99", "D1N": "Sem estado", "V": "..."})  # valor com sinal: fica de fora
    if por_sexo:  # como a tabela 5436: uma linha de total e uma por sexo, que devem ficar de fora
        cab = {**cab, "D4C": "Sexo (Código)", "D4N": "Sexo"}
        linhas = [y for x in linhas for y in ({**x, "D4C": "6794", "D4N": "Total"}, {**x, "D4C": "4", "D4N": "Homens", "V": "1"})]
    return [cab] + linhas


def pagina_regras() -> str:
    mapa = "".join(f'<a xlink:href="#x" title="{n}" data-original-title="{n}" class="mapa-estado" data-content="{_br(40000 + i * 1500)}">'
                   for i, (_, n, *_r) in enumerate(UFS.values()))
    return (f"<html><body><h2>Verba de Gabinete</h2><p>Cada deputado tem o limite mensal de R$ {_br(TETO_MES)} para pagar "
            "salários de até 25 secretários parlamentares, que trabalham para o mandato, em Brasília ou nos estados. Eles são "
            "indicados diretamente pelos deputados, com salários de R$ 1.710,83 a R$ 25.958,90.</p>"
            f"<svg>{mapa}</svg></body></html>")


def pagina_deputado(dep_id: int, ano: int) -> str:
    """Só o bloco da verba de gabinete e da equipe (sem o bloco da cota, que a coleta já confere pelas notas)."""
    uso = 0.55 + (dep_id % 7) * 0.06
    meses = [(m, round(TETO_MES * uso, 2)) for m in range(1, 13)]
    gasto = round(sum(v for _, v in meses), 2)
    sobra = round(TETO_MES * 12 - gasto, 2)
    linhas = "".join(f"<tr><td>{['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'][m - 1]}</td>"
                     f"<td>{_br(v)}</td><td>{uso * 100:.2f}%</td></tr>" for m, v in meses)
    return (f"<main><h3>Verba de gabinete <a>?</a></h3><table><tr><td>Gasto</td><td>{_br(gasto)}</td><td>{uso * 100:.2f}%</td></tr>"
            f"<tr><td>Não utilizado</td><td>{_br(sobra)}</td><td>x%</td></tr></table><p>Gasto mensal</p><table>{linhas}</table>"
            f"<h3>Pessoal de gabinete <a>?</a></h3> <a> {12 + dep_id % 12} pessoas </a></main>")


def rota(netloc: str, path: str, q: dict, deputados: list[dict]) -> tuple[int, bytes, str] | None:
    if netloc == "apisidra.ibge.gov.br" and path == "/values/t/6579/n3/all/v/9324/p/last":
        return _json(_sidra("9324", "População residente estimada", "2025", "Ano", lambda c: UFS[c][2]))
    if netloc == "apisidra.ibge.gov.br" and path == "/values/t/5436/n3/all/v/5932/p/last":
        return _json(_sidra("5932", "Rendimento médio mensal real", "202602", "Trimestre", lambda c: UFS[c][3], por_sexo=True))
    if netloc == "www.camara.leg.br" and path == "/transparencia/gastos-parlamentares":
        return 200, pagina_regras().encode(), "text/html"
    if netloc == "dadosabertos.camara.leg.br" and path == "/arquivos/funcionarios/json/funcionarios.json":
        # os mesmos funcionários da aba de arrecadação e gastos, mais os secretários de cada deputado
        dados = json.loads(fakegov_financas.camara())["dados"] + [{"grupo": "Secretário Parlamentar", "nome": f"PESSOA {d['id']}-{i}",
                  "uriLotacao": f"https://dadosabertos.camara.leg.br/api/v2/deputados/{d['id']}"}
                 for d in deputados for i in range(10 + d["id"] % 12)]
        return _json({"dados": dados})
    m = re.match(r"^/deputados/(\d+)$", path)
    if netloc == "www.camara.leg.br" and m and any(d["id"] == int(m.group(1)) for d in deputados):
        return 200, pagina_deputado(int(m.group(1)), int(q.get("ano", 2025))).encode(), "text/html"
    m = re.match(r"^/adm-dadosabertos/api/v1/senadores/(\d+)/recursos-utilizados$", path)
    if netloc == "adm.senado.gov.br" and m:
        n = 30 + int(m.group(1)) % 15
        return _json({"data": [{"cotas": {}, "pessoal": [{"local": "Gabinete", "quantidade": n,
                                                          "vinculos": [{"vinculo": "Comissionado", "quantidade": n - 3},
                                                                       {"vinculo": "Efetivo", "quantidade": 3}]}]}]})
    return None
