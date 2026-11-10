"""Punições e condenações oficiais: empresas, donos e deputados nas listas oficiais de punidos.

Só entram decisões oficiais, publicadas por quem puniu ou condenou. Nada de notícia, denúncia ou investigação.

Fontes (API primeiro):
1. API de dados do Portal da Transparência (CGU), com a chave do secret PORTAL_TRANSPARENCIA_CHAVE:
   - CEIS, Cadastro de Empresas Inidôneas e Suspensas (/ceis): empresas e pessoas proibidas de contratar com o governo,
     inclusive condenações por improbidade que a Justiça manda para o cadastro (CNJ).
   - CNEP, Cadastro Nacional de Empresas Punidas (/cnep): punições da Lei Anticorrupção (Lei 12.846/2013), com multa e
     acordos de leniência.
   - CEAF, Cadastro de Expulsões da Administração Federal (/ceaf): servidores federais demitidos, destituídos ou com
     aposentadoria cassada.
   A API devolve 15 linhas por página. Em 10/11/2026 eram 1.581 páginas do CEIS, 124 do CNEP e 268 do CEAF. Há filtro
   por CNPJ (codigoSancionado), mas são milhares de fornecedoras e sócios: ler a lista inteira gasta menos pedidos. Lemos aos poucos, com limite de tempo por
   coleta e no máximo POR_MINUTO pedidos por minuto (o limite do Portal é 400; acima disso a chave fica suspensa 8 horas,
   e a leitura semanal dos pagamentos a empresas usa a mesma chave). Cada lista completa vale DIAS_LISTA dias; enquanto a
   nova leitura não termina, fica a cópia anterior.
2. TCU, serviço oficial da Plataforma de Certidões (certidoes.apps.tcu.gov.br/api/publico/...), o mesmo que alimenta
   as páginas certidoes.apps.tcu.gov.br/lista-*. O TCU não publica estas listas em API documentada; o serviço é o que a
   página oficial chama (POST com paginaAtual e tamanhoPagina) e traz o link do acórdão e do processo de cada linha:
   - contas julgadas irregulares (48.281 linhas em 10/11/2026): quem teve as contas reprovadas pelo TCU, pessoas e
     empresas, com condenação a devolver dinheiro ou multa;
   - contas irregulares para fins eleitorais (9.679 linhas para 2026): a lista que o TCU manda à Justiça Eleitoral
     (Lei da Ficha Limpa, LC 64/1990, art. 1º, I, g);
   - inabilitados: pessoas proibidas de ocupar cargo em comissão ou função de confiança (Lei 8.443/92, art. 60);
   - inidôneos: empresas proibidas de participar de licitação federal (Lei 8.443/92, art. 46).
   Também há os serviços ORDS (contas.tcu.gov.br/ords/condenacao/consulta/inabilitados e /inidoneos), mas só com as
   duas listas menores e sem os links; a Plataforma de Certidões traz as quatro.

Como ligamos uma punição a alguém do site:
- Empresa: o CNPJ da lista é igual ao CNPJ da fornecedora (14 dígitos). Sem aproximação por nome.
- Sócio pessoa física: a Receita mostra o CPF do sócio com máscara (***123456**). Ligamos só quando o NOME COMPLETO é
  igual E os 6 dígitos do meio do CPF são iguais. Nome parecido não basta.
- Deputado federal: a API da Câmara (/deputados/{id}) traz o CPF. Nas listas do TCU e no CEIS (que trazem o CPF
  inteiro em sancionado.codigoFormatado) o CPF tem de ser igual; no CEAF (só com máscara), o nome civil e os 6 dígitos
  do meio.
- Senador: a API do Senado não traz CPF; sem CPF não ligamos ninguém (nome igual não prova que é a mesma pessoa).

O CPF nunca sai daqui sem máscara: no site vai só ***.456.789-** (validar.py barra CPF à mostra).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .util import SiteForaDoAr, _session, avisar, chave_portal, com_copia, digits, get_json, norm_name, url_segura, write_json

log = logging.getLogger("sa_etl.sancoes")

API = "https://api.portaldatransparencia.gov.br/api-de-dados"
PORTAL = "https://portaldatransparencia.gov.br"
TCU = "https://certidoes.apps.tcu.gov.br/api/publico"
TCU_PAGINA = 10000   # linhas por pedido (o serviço aceitou 50.000 num pedido só)
CAMARA = "https://dadosabertos.camara.leg.br/api/v2/deputados/{id}"

POR_MINUTO = 200
EM_PARALELO = 4
MINUTOS = 8          # tempo máximo de leitura da API do Portal por coleta
DIAS_LISTA = 3       # uma lista completa do Portal vale 3 dias; depois começa uma leitura nova
DIAS_AVISO = 10      # cópia mais velha que isso: aviso no site
DIAS_CPF = 90        # o CPF de um deputado não muda; o detalhe é relido a cada 90 dias
MAX_PAGINAS = 5000   # trava contra uma API que nunca devolve página vazia

CADASTROS = {
    "ceis": {"nome": "CEIS", "titulo": "Cadastro de Empresas Inidôneas e Suspensas",
             "quem": "Controladoria-Geral da União (CGU), Portal da Transparência",
             "explica": "Empresas e pessoas proibidas de fazer contratos com o governo, por decisão de um órgão público ou "
                        "da Justiça (inclui condenações por improbidade administrativa).",
             "pagina": f"{PORTAL}/sancoes/ceis", "api": f"{API}/ceis"},
    "cnep": {"nome": "CNEP", "titulo": "Cadastro Nacional de Empresas Punidas",
             "quem": "Controladoria-Geral da União (CGU), Portal da Transparência",
             "explica": "Empresas punidas pela Lei Anticorrupção (Lei 12.846/2013): multa, publicação da decisão e "
                        "acordos de leniência.",
             "pagina": f"{PORTAL}/sancoes/cnep", "api": f"{API}/cnep"},
    "ceaf": {"nome": "CEAF", "titulo": "Cadastro de Expulsões da Administração Federal",
             "quem": "Controladoria-Geral da União (CGU), Portal da Transparência",
             "explica": "Servidores federais expulsos do serviço público: demissão, destituição do cargo em comissão ou "
                        "aposentadoria cassada.",
             "pagina": f"{PORTAL}/sancoes/ceaf", "api": f"{API}/ceaf"},
    "tcu_irregulares": {"nome": "TCU: contas irregulares", "titulo": "Responsáveis com contas julgadas irregulares",
                        "quem": "Tribunal de Contas da União (TCU)",
                        "explica": "Pessoas e empresas que tiveram as contas reprovadas pelo TCU, em decisão final, por "
                                   "mau uso de dinheiro federal (com condenação a devolver o dinheiro ou multa).",
                        "pagina": "https://certidoes.apps.tcu.gov.br/lista-responsaveis",
                        "api": f"{TCU}/responsaveis-contas-irregulares-com-paginacao"},
    "tcu_eleitoral": {"nome": "TCU: lista eleitoral", "titulo": "Contas julgadas irregulares para fins eleitorais",
                      "quem": "Tribunal de Contas da União (TCU)",
                      "explica": "A lista que o TCU manda à Justiça Eleitoral: contas reprovadas nos últimos 8 anos. Quem "
                                 "está nela pode ser barrado pela Lei da Ficha Limpa; quem decide é a Justiça Eleitoral.",
                      "pagina": "https://certidoes.apps.tcu.gov.br/lista-implicacao-eleitoral",
                      "api": f"{TCU}/responsaveis-fins-eleitorais-com-paginacao"},
    "tcu_inabilitados": {"nome": "TCU: inabilitados", "titulo": "Inabilitados para cargo em comissão ou função de confiança",
                         "quem": "Tribunal de Contas da União (TCU)",
                         "explica": "Pessoas que o TCU proibiu de ocupar cargo em comissão ou função de confiança no "
                                    "governo federal por 5 a 8 anos (Lei 8.443/1992, art. 60), por irregularidade grave.",
                         "pagina": "https://certidoes.apps.tcu.gov.br/lista-inabilitados",
                         "api": f"{TCU}/responsaveis-inabilitados-com-paginacao"},
    "tcu_inidoneos": {"nome": "TCU: inidôneos", "titulo": "Licitantes inidôneos",
                      "quem": "Tribunal de Contas da União (TCU)",
                      "explica": "Empresas que o TCU declarou inidôneas: não podem participar de licitação federal por "
                                 "até 5 anos (Lei 8.443/1992, art. 46), por fraude comprovada em licitação.",
                      "pagina": "https://certidoes.apps.tcu.gov.br/lista-inidoneos",
                      "api": f"{TCU}/responsaveis-inidoneos-com-paginacao"},
}
PORTAL_CADS = ("ceis", "cnep", "ceaf")
TCU_CADS = ("tcu_irregulares", "tcu_eleitoral", "tcu_inabilitados", "tcu_inidoneos")
TIPO_TCU = {"tcu_irregulares": "Contas julgadas irregulares pelo TCU",
            "tcu_eleitoral": "Contas irregulares na lista enviada à Justiça Eleitoral",
            "tcu_inabilitados": "Inabilitado para cargo em comissão ou função de confiança",
            "tcu_inidoneos": "Declarada inidônea para licitar com o governo federal"}


# ------------------------------------------------------------------ ajudantes

def _txt(x: Any) -> str:
    s = re.sub(r"\s+", " ", str(x or "")).strip()
    return "" if s.lower() in ("sem informação", "sem informacao", "null", "none", "-1", "s/i") else s


def _data(s: Any) -> str:
    """dd/mm/aaaa ou aaaa-mm-ddT... -> aaaa-mm-dd (vazio se não for data)."""
    s = _txt(s)
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else ""


def _g(d: Any, *caminho: str) -> Any:
    for k in caminho:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def valor_br(v: Any) -> float:
    """"1.234,56" (como a API manda a multa do CNEP) ou número -> 1234.56; 0 se não for valor."""
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = _txt(v).replace("R$", "").strip()
    if not re.match(r"^-?[\d.]+(,\d+)?$", s):
        return 0.0
    return round(float(s.replace(".", "").replace(",", ".")), 2)


def meio_cpf(doc: str) -> str:
    """Os 6 dígitos do meio do CPF (posições 4 a 9), os únicos que a Receita e o Portal mostram.

    Aceita CPF inteiro (11 dígitos), a máscara do Portal (***.456.789-**) e a da Receita (***456789**)."""
    s = str(doc or "")
    d = digits(s)
    if len(d) == 11 and "*" not in s:
        return d[3:9]
    return d if len(d) == 6 and "*" in s else ""


def cpf_mascarado(doc: str) -> str:
    """Sempre ***.456.789-**, venha a máscara da Receita, do Portal ou o CPF inteiro do TCU."""
    m = meio_cpf(doc)
    return f"***.{m[:3]}.{m[3:]}-**" if m else ""


def chave_pessoa(nome: str, doc: str) -> tuple[str, str] | None:
    m = meio_cpf(doc)
    n = norm_name(nome)
    return (n, m) if m and len(n.split()) >= 2 else None


def vigente(fim: str, hoje: dt.date) -> bool:
    return not fim or fim >= hoje.isoformat()


def nome_acordao(n: str) -> str:
    """738/2022-PL -> Acórdão 738/2022 (Plenário); 10367/2023-1C -> Acórdão 10367/2023 (1ª Câmara)."""
    m = re.match(r"^0*(\d+)/(\d{4})-(PL|1C|2C)$", _txt(n))
    if not m:
        return _txt(n)
    return f"Acórdão {m.group(1)}/{m.group(2)} ({ {'PL': 'Plenário', '1C': '1ª Câmara', '2C': '2ª Câmara'}[m.group(3)] })"


# ------------------------------------------------------------------ registros: cada linha das listas, no mesmo formato

def registro_portal(cad: str, x: dict) -> dict | None:
    """Uma linha do CEIS, CNEP ou CEAF no formato do site. CPF só com máscara."""
    if cad == "ceaf":
        pessoa = x.get("pessoa") or {}
        nome = _txt(_g(x, "punicao", "nomePunido") or pessoa.get("nome"))
        cpf = _txt(_g(x, "punicao", "cpfPunidoFormatado") or pessoa.get("cpfFormatado"))
        orgao = _txt(_g(x, "orgaoLotacao", "nome"))
        r = {"cad": cad, "id": x.get("id"), "nome": nome, "pf": True, "cnpj": "", "doc": cpf_mascarado(cpf),
             "meio": meio_cpf(cpf), "tipo": _txt(_g(x, "tipoPunicao", "descricao")),
             "orgao": orgao, "inicio": _data(x.get("dataPublicacao")), "fim": "",
             "processo": _txt(_g(x, "punicao", "processo")), "portaria": _txt(_g(x, "punicao", "portaria")),
             "cargo": _txt(x.get("cargoEfetivo")) or _txt(x.get("cargoComissao")),
             "fundamento": [_txt(f.get("codigo") or f.get("descricao"))[:200] for f in x.get("fundamentacao") or []][:3],
             "referencia": _data(x.get("dataReferencia"))}
    else:
        pessoa = x.get("pessoa") or {}
        sanc = x.get("sancionado") or {}
        nome = _txt(sanc.get("nome") or pessoa.get("nome") or pessoa.get("razaoSocialReceita"))
        codigo = _txt(sanc.get("codigoFormatado"))
        cnpj = digits(_txt(pessoa.get("cnpjFormatado")) or (codigo if "*" not in codigo else ""))
        cpf = _txt(pessoa.get("cpfFormatado")) or (codigo if "*" in codigo else "")
        # O CEIS traz o CPF inteiro em sancionado.codigoFormatado (106.996.817-07); fica só na memória da coleta
        cpf_inteiro = digits(codigo) if "*" not in codigo and len(digits(codigo)) == 11 else ""
        pf = len(cnpj) != 14
        orgao = x.get("orgaoSancionador") or {}
        r = {"cad": cad, "id": x.get("id"), "nome": nome, "pf": pf, "cnpj": "" if pf else cnpj,
             "doc": cpf_mascarado(cpf or cpf_inteiro) if pf else cnpj, "meio": meio_cpf(cpf or cpf_inteiro) if pf else "",
             "_cpf": cpf_inteiro if pf else "",
             "tipo": _txt(_g(x, "tipoSancao", "descricaoPortal") or _g(x, "tipoSancao", "descricaoResumida")),
             "orgao": " - ".join(p for p in (_txt(orgao.get("nome")), _txt(orgao.get("siglaUf"))) if p)
             or _txt(_g(x, "fonteSancao", "nomeExibicao")),
             "inicio": _data(x.get("dataInicioSancao")), "fim": _data(x.get("dataFimSancao")),
             "transito": _data(x.get("dataTransitadoJulgado")),
             "processo": _txt(x.get("numeroProcesso")),
             "fundamento": [_txt(f.get("codigo") or f.get("descricao"))[:200] for f in x.get("fundamentacao") or []][:3],
             "referencia": _data(x.get("dataReferencia"))}
        multa = valor_br(x.get("valorMulta"))
        if cad == "cnep" and multa:
            r["multa"] = multa
    if not r["nome"] or not (r["cnpj"] or r["meio"]):
        return None
    # O Portal não tem página por punição (/sancoes/ceis/{id} dá 404, conferido em 10/11/2026). Empresa: a página dela
    # no Portal, que mostra as sanções. Pessoa: a consulta do cadastro (o CPF não vai no link).
    r["link"] = f"{PORTAL}/pessoa-juridica/{r['cnpj']}" if r["cnpj"] else CADASTROS[cad]["pagina"]
    return r


def registro_tcu(cad: str, x: dict) -> dict | None:
    """Uma linha das listas do TCU (Plataforma de Certidões). O CPF vem inteiro: fica só em `_cpf`, nunca é gravado."""
    d = digits(_txt(x.get("numeroRegistro")))
    tipo = _txt(x.get("tipoRegistro")).upper()
    pf = len(d) == 11 and tipo != "CNPJ"
    if not (pf or len(d) == 14):
        return None
    nome = _txt(x.get("nome")).strip("'\" ")
    if not nome:
        return None
    acordao = _txt(x.get("numeroAcordaoFormatado"))
    link = url_segura(x.get("linkDeliberacoesProcesso")) or url_segura(x.get("linkAcompanhamentoProcesso"))
    return {"cad": cad, "id": f"{_txt(x.get('numeroProcessoFormatado'))}|{acordao}", "nome": nome, "pf": pf,
            "cnpj": "" if pf else d, "doc": cpf_mascarado(d) if pf else d, "meio": d[3:9] if pf else "",
            "_cpf": d if pf else "", "tipo": TIPO_TCU[cad], "orgao": "Tribunal de Contas da União (TCU)",
            "inicio": _data(x.get("dataTransitoEmJulgado")),
            "fim": _data(x.get("dataFinalFinsEleitorais") or x.get("dataFinalSancao")),
            "transito": _data(x.get("dataTransitoEmJulgado")), "processo": _txt(x.get("numeroProcessoFormatado")),
            "decisao": nome_acordao(acordao), "data_decisao": _data(x.get("dataAcordao")),
            "uf": _txt(x.get("uf")), "link": link or CADASTROS[cad]["pagina"],
            "acompanhar": url_segura(x.get("linkAcompanhamentoProcesso"))}


# ------------------------------------------------------------------ leitura do Portal, aos poucos

class LeitorPortal:
    """Lê as listas do Portal página por página, guardando o andamento. Continua de onde parou na coleta seguinte."""

    def __init__(self, pasta: Path, chave: str, hoje: dt.date, minutos: float = MINUTOS):
        self.pasta = pasta
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.chave = chave
        self.hoje = hoje
        self.fim = time.monotonic() + minutos * 60
        self.pedidos: list[float] = []

    def final(self, cad: str) -> Path:
        return self.pasta / f"{cad}.json"

    def lendo(self, cad: str) -> Path:
        return self.pasta / f"{cad}-lendo.json"

    @staticmethod
    def _abrir(f: Path) -> dict | None:
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def em_dia(self, cad: str) -> bool:
        d = self._abrir(self.final(cad))
        return bool(d) and (self.hoje - dt.date.fromisoformat(d["lida_em"])).days < DIAS_LISTA

    def _esperar(self) -> None:
        agora = time.monotonic()
        self.pedidos = [t for t in self.pedidos if agora - t < 60]
        if len(self.pedidos) >= POR_MINUTO:
            time.sleep(max(0.0, 60 - (agora - self.pedidos[0])))
        self.pedidos.append(time.monotonic())

    def pagina(self, cad: str, n: int) -> list[dict] | None:
        """Linhas da página n; None se a API não respondeu direito (a leitura para e continua na próxima coleta)."""
        for tentativa in range(3):
            try:
                r = _session.get(CADASTROS[cad]["api"], params={"pagina": n}, timeout=90,
                                 headers={"chave-api-dados": self.chave, "Accept": "application/json"})
            except SiteForaDoAr:
                return None
            except Exception as e:  # noqa: BLE001
                log.warning("Sanções %s página %d: %s", cad, n, str(e)[:120])
                time.sleep(2 ** (tentativa + 1))
                continue
            if r.status_code == 200:
                try:
                    d = r.json()
                except ValueError:
                    d = None
                if isinstance(d, list):
                    return d
            elif r.status_code in (401, 403):
                log.warning("Sanções %s: a API recusou a chave (HTTP %d)", cad, r.status_code)
                return None
            time.sleep(2 ** (tentativa + 1))
        return None

    def ler(self, cad: str) -> str:
        """Continua a leitura de `cad`. Devolve "pronta", "parcial" ou "falhou"."""
        est = self._abrir(self.lendo(cad)) or {"inicio": self.hoje.isoformat(), "proxima": 1, "linhas": {}}
        proxima, linhas = est["proxima"], est["linhas"]
        situacao = "parcial"
        while time.monotonic() < self.fim and proxima <= MAX_PAGINAS:
            lote = list(range(proxima, proxima + EM_PARALELO))
            for _ in lote:
                self._esperar()
            with ThreadPoolExecutor(EM_PARALELO) as ex:
                res = list(ex.map(lambda n: self.pagina(cad, n), lote))
            parar = False
            for n, pg in zip(lote, res):
                if pg is None:
                    situacao, parar = "falhou", True
                    break
                for x in pg:
                    reg = registro_portal(cad, x)
                    if reg:
                        linhas[str(reg["id"])] = reg
                proxima = n + 1
                if not pg:  # página vazia: chegou ao fim da lista
                    situacao, parar = "pronta", True
                    break
            if parar:
                break
        if situacao == "pronta":
            write_json(self.final(cad), {"lida_em": self.hoje.isoformat(), "inicio": est["inicio"],
                                         "paginas": proxima - 1, "linhas": list(linhas.values())})
            self.lendo(cad).unlink(missing_ok=True)
            log.info("Sanções %s: lista completa, %d linhas em %d páginas", cad, len(linhas), proxima - 1)
        else:
            write_json(self.lendo(cad), {"inicio": est["inicio"], "proxima": proxima, "linhas": linhas})
            log.info("Sanções %s: leitura %s na página %d (%d linhas até aqui)", cad, situacao, proxima, len(linhas))
        return situacao

    def coletar(self) -> tuple[dict[str, list[dict]], dict[str, dict]]:
        """Listas do Portal (a última completa de cada uma) e a situação de cada uma."""
        listas, situacao = {}, {}
        for cad in PORTAL_CADS:
            sit = "ok"
            if not self.em_dia(cad):
                if not self.chave:
                    sit = "sem_chave"
                elif time.monotonic() >= self.fim:
                    sit = "parcial"
                else:
                    r = self.ler(cad)
                    sit = "ok" if r == "pronta" else r
            d = self._abrir(self.final(cad))
            if d:
                listas[cad] = d["linhas"]
                idade = (self.hoje - dt.date.fromisoformat(d["lida_em"])).days
                situacao[cad] = {"situacao": sit if sit != "ok" or idade < DIAS_LISTA else "copia",
                                 "lida_em": d["lida_em"], "n": len(d["linhas"]),
                                 "referencia": max((x.get("referencia") or "" for x in d["linhas"]), default="")}
                if idade >= DIAS_AVISO:
                    avisar(f"Punições oficiais: a lista {CADASTROS[cad]['nome']} do Portal da Transparência é de "
                           f"{dt.date.fromisoformat(d['lida_em']).strftime('%d/%m/%Y')}; a leitura nova ainda não terminou")
            else:
                situacao[cad] = {"situacao": "faltando" if sit == "ok" else sit, "lida_em": "", "n": 0, "referencia": ""}
        return listas, situacao


# ------------------------------------------------------------------ TCU

def ano_eleicao(hoje: dt.date) -> int:
    """A lista eleitoral do TCU é por ano de eleição (2026, 2024...): a eleição deste ano ou a próxima."""
    return hoje.year if hoje.year % 2 == 0 else hoje.year + 1


def ler_tcu(cad: str, hoje: dt.date) -> list[dict]:
    """Lista inteira, página por página (POST, como a página oficial faz)."""
    itens: list[dict] = []
    pagina, total = 1, 1
    while pagina <= total:
        params = {"paginaAtual": pagina, "tamanhoPagina": TCU_PAGINA}
        if cad == "tcu_eleitoral":
            params["anoEleicao"] = ano_eleicao(hoje)
        r = _session.post(CADASTROS[cad]["api"], params=params, json={}, timeout=180,
                          headers={"Accept": "application/json", "Content-Type": "application/json"})
        r.raise_for_status()
        d = r.json()
        if not isinstance(d, dict) or not isinstance(d.get("elementos"), list):
            raise ValueError(f"TCU {cad}: resposta sem a lista de elementos")
        itens += d["elementos"]
        total = int(d.get("totalPaginas") or 1)
        pagina += 1
        if pagina > 100:
            raise ValueError(f"TCU {cad}: páginas demais ({total})")
    esperado = d.get("totalElementos")
    if not itens or (isinstance(esperado, int) and len(itens) != esperado):
        raise ValueError(f"TCU {cad}: {len(itens)} linhas, o serviço disse {esperado}")
    return itens


def coletar_tcu(pasta: Path, hoje: dt.date | None = None) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    hoje = hoje or dt.date.today()
    listas, situacao = {}, {}
    for cad in TCU_CADS:
        f = pasta / f"{cad}.json"
        try:
            itens = com_copia(f, lambda cad=cad: ler_tcu(cad, hoje), f"Punições oficiais ({CADASTROS[cad]['nome']})")
        except Exception as e:  # noqa: BLE001
            log.warning("Sanções: lista %s do TCU indisponível e sem cópia (%s)", cad, e)
            situacao[cad] = {"situacao": "faltando", "lida_em": "", "n": 0, "referencia": ""}
            continue
        regs = [r for r in (registro_tcu(cad, x) for x in itens) if r]
        listas[cad] = regs
        lida = dt.date.fromtimestamp(f.stat().st_mtime).isoformat() if f.exists() else hoje.isoformat()
        situacao[cad] = {"situacao": "ok" if lida == hoje.isoformat() or (hoje - dt.date.fromisoformat(lida)).days < 2 else "copia",
                         "lida_em": lida, "n": len(regs), "referencia": lida}
    return listas, situacao


# ------------------------------------------------------------------ CPF dos deputados (API da Câmara)

def cpfs_deputados(politicos: list[dict], pasta: Path, hoje: dt.date) -> dict[str, dict]:
    """id do deputado -> {"cpf", "nome_civil"}, pela API da Câmara. Fica só no cache; nunca vai para o site."""
    pasta.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}

    def um(p: dict) -> tuple[str, dict | None]:
        num = p["id"].removeprefix("dep-")
        f = pasta / f"{num}.json"
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if (hoje - dt.date.fromisoformat(d["lido_em"])).days < DIAS_CPF:
                return p["id"], d
        except (OSError, ValueError, KeyError):
            d = None
        try:
            x = get_json(CAMARA.format(id=num), tries=5, timeout=60)["dados"]
            novo = {"cpf": digits(x.get("cpf") or ""), "nome_civil": _txt(x.get("nomeCivil")), "lido_em": hoje.isoformat()}
            write_json(f, novo)
            return p["id"], novo
        except Exception as e:  # noqa: BLE001
            log.warning("Sanções: CPF do deputado %s indisponível (%s)", num, str(e)[:120])
            return p["id"], d

    deps = [p for p in politicos if p.get("casa") == "camara" and str(p.get("id", "")).startswith("dep-")]
    # Com 6 pedidos ao mesmo tempo a API da Câmara devolveu 503 para 1 em cada 6 deputados (10/11/2026); com 3 e mais
    # tentativas, quase todos passam. Quem falhar entra na próxima execução (o CPF fica guardado por 90 dias).
    with ThreadPoolExecutor(3) as ex:
        for pid, d in ex.map(um, deps):
            if d and len(d.get("cpf") or "") == 11:
                out[pid] = d
    return out


# ------------------------------------------------------------------ ligar as listas às pessoas e empresas do site

def _publico(r: dict, hoje: dt.date) -> dict:
    """O registro como vai para o site: sem campos internos e com a situação de hoje."""
    out = {k: v for k, v in r.items() if not k.startswith("_") and k not in ("meio", "pf", "referencia") and v not in ("", None, [])}
    out["vigente"] = vigente(r.get("fim") or "", hoje)
    return out


def _ordem(r: dict) -> tuple:
    return (not r["vigente"], "".join(chr(255 - ord(c)) for c in (r.get("inicio") or "")))


def ligar(listas: dict[str, list[dict]], empresas: list[dict], politicos: list[dict], cpfs: dict[str, dict],
          hoje: dt.date) -> tuple[list[dict], list[dict]]:
    """Empresas (pelo CNPJ e pelos sócios) e deputados (pelo CPF) que aparecem nas listas."""
    por_cnpj: dict[str, list[dict]] = {}
    por_pessoa: dict[tuple[str, str], list[dict]] = {}
    por_cpf: dict[str, list[dict]] = {}
    for regs in listas.values():
        for r in regs:
            if r["cnpj"]:
                por_cnpj.setdefault(r["cnpj"], []).append(r)
            else:
                n = norm_name(r["nome"])
                k = (n, r["meio"]) if r.get("meio") and len(n.split()) >= 2 else None
                if k:
                    por_pessoa.setdefault(k, []).append(r)
                if r.get("_cpf"):
                    por_cpf.setdefault(r["_cpf"], []).append(r)

    def regs(rs: list[dict]) -> list[dict]:
        vistos, out = set(), []
        for r in rs:
            if (r["cad"], str(r["id"])) not in vistos:
                vistos.add((r["cad"], str(r["id"])))
                out.append(_publico(r, hoje))
        return sorted(out, key=_ordem)

    saida_emp = []
    for e in empresas:
        cnpj = digits(e.get("cnpj") or "")
        propria = regs(por_cnpj.get(cnpj, []))
        socios = []
        vistos_soc: set[str] = set()
        for s in list(e.get("socios") or []) + list(e.get("donos_finais") or []):
            doc = str(s.get("doc") or "")
            nome = s.get("nome") or ""
            if len(digits(doc)) == 14 and "*" not in doc:  # sócio que é empresa
                rs = por_cnpj.get(digits(doc), [])
                chave = digits(doc)
            else:
                k = chave_pessoa(nome, doc)
                rs = por_pessoa.get(k, []) if k else []
                chave = f"{norm_name(nome)}|{meio_cpf(doc)}"
            if rs and chave not in vistos_soc:
                vistos_soc.add(chave)
                socios.append({"nome": nome, "doc": cpf_mascarado(doc) if "*" in doc or len(digits(doc)) == 11 else digits(doc),
                               "qualificacao": s.get("qualificacao") or "", "registros": regs(rs)})
        if propria or socios:
            saida_emp.append({"cnpj": cnpj, "nome": e.get("nome") or "", "registros": propria, "socios": socios,
                              "vigente": any(r["vigente"] for r in propria) or any(r["vigente"] for s in socios for r in s["registros"])})

    saida_pol = []
    for p in politicos:
        c = cpfs.get(p["id"])
        if not c:
            continue
        rs = list(por_cpf.get(c["cpf"], []))
        k = chave_pessoa(c.get("nome_civil") or "", c["cpf"])
        if k:
            rs += [r for r in por_pessoa.get(k, []) if not r.get("_cpf")]  # Portal: nome civil e meio do CPF
        if rs:
            saida_pol.append({"id": p["id"], "nome": p.get("nome") or "", "partido": p.get("partido") or "",
                              "uf": p.get("uf") or "", "casa": p.get("casa") or "", "registros": regs(rs),
                              "vigente": any(r["vigente"] for r in regs(rs))})
    saida_emp.sort(key=lambda x: (not x["vigente"], x["nome"]))
    saida_pol.sort(key=lambda x: (not x["vigente"], x["nome"]))
    return saida_emp, saida_pol


# ------------------------------------------------------------------ coleta

def _empresas_do_site(saida: Path) -> list[dict]:
    out = []
    for f in sorted((saida / "e").glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"cnpj": d.get("cnpj") or f.stem, "nome": d.get("nome") or "",
                    "socios": d.get("socios") or [], "donos_finais": d.get("donos_finais") or []})
    return out


def coletar(saida: Path, cache: Path, hoje: dt.date | None = None, minutos: float = MINUTOS) -> dict:
    """Lê as listas, liga às empresas (e/*.json) e aos deputados (politicos.json) já gravados, e grava sancoes.json."""
    hoje = hoje or dt.date.today()
    pasta = cache / "sancoes"
    politicos = json.loads((saida / "politicos.json").read_text(encoding="utf-8"))
    chave = chave_portal()
    listas, situacao = LeitorPortal(pasta / "portal", chave, hoje, minutos).coletar()
    if not chave:  # sem aviso geral: a página de punições diz quais listas não foram lidas (situacao "sem_chave")
        log.warning("Punições oficiais: sem a chave PORTAL_TRANSPARENCIA_CHAVE, CEIS, CNEP e CEAF não foram lidos")
    l_tcu, s_tcu = coletar_tcu(pasta / "tcu", hoje)
    listas.update(l_tcu)
    situacao.update(s_tcu)
    faltando = [CADASTROS[c]["nome"] for c, s in situacao.items() if s["situacao"] == "faltando"]
    if faltando:
        avisar(f"Punições oficiais: as listas {', '.join(faltando)} não responderam e não há cópia anterior")
    cpfs = cpfs_deputados(politicos, pasta / "camara", hoje)
    empresas = _empresas_do_site(saida)
    emp, pol = ligar(listas, empresas, politicos, cpfs, hoje)
    n_socios = sum(1 for e in empresas for s in (e["socios"] + e["donos_finais"]) if chave_pessoa(s.get("nome") or "", str(s.get("doc") or "")))
    out = {
        "atualizado_em": hoje.isoformat(),
        "fontes": {c: {**CADASTROS[c], **situacao.get(c, {"situacao": "faltando", "lida_em": "", "n": 0, "referencia": ""})}
                   for c in CADASTROS},
        "cobertura": {"empresas": len(empresas), "socios": n_socios,
                      "deputados": sum(1 for p in politicos if p.get("casa") == "camara"), "deputados_com_cpf": len(cpfs),
                      "senadores": sum(1 for p in politicos if p.get("casa") == "senado")},
        "empresas": emp,
        "politicos": pol,
    }
    write_json(saida / "sancoes.json", out)
    log.info("Punições oficiais: %d empresas e %d parlamentares nas listas (%s)", len(emp), len(pol),
             ", ".join(f"{c} {s['n']}" for c, s in situacao.items()))
    return out
