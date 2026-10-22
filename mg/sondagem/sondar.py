"""Fase 0 do Minas Nossa: sonda as fontes de MG e grava um relatório. Não publica nada.

Para cada fonte: status, tipo, tamanho, colunas ou chaves, número de linhas e amostra (CPF mascarado).
Páginas HTML: lista os links que parecem dados (csv, json, xls, api, votação, presença...).

Uso: python mg/sondagem/sondar.py saida/
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

UA = "MinasNossa-sondagem/0.1 (+https://github.com/amarigo/segredos-abertos)"
S = requests.Session()
S.headers["User-Agent"] = UA
LIMITE = 40 * 1024 * 1024  # não baixa mais que isso por fonte
CPF = re.compile(r"(?<!\d)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)")
PALAVRAS = re.compile(r"csv|json|xls|xml|zip|api|dados|download|vota|presen|frequ|sess|materia|proposi|parlament|"
                      r"vereador|diaria|despes|empenh|folha|remunera|emenda|swagger|sapl|ws/", re.I)

ALMG = "https://dadosabertos.almg.gov.br"
ALMG_WS = ALMG + "/ws"
CKAN_MG = "https://dados.mg.gov.br/api/3/action/package_show?id="
CKAN_TSE = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id="

relatorio: list[str] = []


def p(s: str = "") -> None:
    print(s, flush=True)
    relatorio.append(s)


def mascara(t: str) -> str:
    return CPF.sub(lambda m: f"***.{m.group(2)}.***-**", t)


class Links(HTMLParser):
    def __init__(self, base: str):
        super().__init__()
        self.base, self.links, self._href, self._txt = base, [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        href = a.get("href") or a.get("src") if tag in ("a", "iframe", "frame") else None
        if href:
            self._href, self._txt = urljoin(self.base, href), []
        if tag == "form" and a.get("action"):
            self.links.append(("form", urljoin(self.base, a["action"])))

    def handle_data(self, d):
        if self._href:
            self._txt.append(d.strip())

    def handle_endtag(self, tag):
        if tag in ("a", "iframe", "frame") and self._href:
            self.links.append((" ".join(t for t in self._txt if t)[:60], self._href))
            self._href = None


def baixar(url: str, timeout: int = 90, **kw) -> tuple[requests.Response | None, bytes, str]:
    try:
        r = S.get(url, timeout=timeout, stream=True, **kw)
        buf = io.BytesIO()
        for ch in r.iter_content(1 << 16):
            buf.write(ch)
            if buf.tell() > LIMITE:
                break
        return r, buf.getvalue(), ""
    except Exception as e:  # noqa: BLE001 - sondagem: registra qualquer falha
        return None, b"", f"{type(e).__name__}: {str(e)[:160]}"


def texto(raw: bytes) -> str:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def resumir_csv(t: str, nome: str = "") -> None:
    amostra = t[:20000]
    try:
        sep = csv.Sniffer().sniff(amostra.split("\n", 1)[0] + "\n", delimiters=";,\t|").delimiter
    except csv.Error:
        sep = ";"
    linhas = list(csv.reader(io.StringIO(t), delimiter=sep))
    if not linhas:
        p("    (vazio)")
        return
    p(f"    CSV{(' ' + nome) if nome else ''}: separador {sep!r}, {len(linhas) - 1} linhas lidas, {len(linhas[0])} colunas")
    p(f"    colunas: {linhas[0]}")
    for ln in linhas[1:4]:
        p(f"    ex: {mascara(str([c[:60] for c in ln]))[:600]}")


def resumir_json(obj, nivel: int = 0, prefixo: str = "    ") -> None:
    if nivel > 3:
        return
    if isinstance(obj, dict):
        p(f"{prefixo}{{}} chaves: {list(obj)[:30]}")
        for k, v in list(obj.items())[:8]:
            if isinstance(v, (dict, list)):
                p(f"{prefixo}  .{k}:")
                resumir_json(v, nivel + 1, prefixo + "    ")
    elif isinstance(obj, list):
        p(f"{prefixo}[] {len(obj)} itens")
        if obj:
            if isinstance(obj[0], (dict, list)):
                resumir_json(obj[0], nivel + 1, prefixo + "  ")
            else:
                p(f"{prefixo}  ex: {mascara(str(obj[:5]))[:300]}")


def sondar(nome: str, url: str, *, html_links: bool = True, salvar: Path | None = None, **kw):
    """Baixa e descreve. Devolve o conteúdo (bytes) para quem quiser seguir links."""
    p(f"\n### {nome}\n  {url}")
    r, raw, erro = baixar(url, **kw)
    if r is None:
        p(f"  FALHA: {erro}")
        return None, b""
    ct = r.headers.get("content-type", "")
    p(f"  HTTP {r.status_code} | {ct} | {len(raw)} bytes{' (cortado no limite)' if len(raw) > LIMITE else ''}"
      f"{' | final: ' + r.url if r.url != url else ''}")
    if salvar:
        salvar.write_bytes(raw[:5_000_000])
    if r.status_code >= 400:
        p(f"  corpo: {mascara(texto(raw[:300]))!r}")
        return r, raw
    descrever(raw, ct, r.url, html_links)
    return r, raw


def descrever(raw: bytes, ct: str, url: str, html_links: bool = True) -> None:
    if raw[:2] == b"\x1f\x8b":
        # decompressobj aguenta arquivo cortado no limite de download
        raw = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, 3_000_000)
        p("  (gzip)")
        resumir_csv(texto(raw))
        return
    if raw[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(raw))
            p(f"  ZIP: {[(i.filename, i.file_size) for i in z.infolist()][:20]}")
            for i in z.infolist():
                if i.filename.lower().endswith((".csv", ".txt")):
                    with z.open(i) as f:
                        resumir_csv(texto(f.read(300_000)), i.filename)
                    break
        except zipfile.BadZipFile:
            p("  ZIP incompleto (cortado no limite); só o começo foi lido")
        return
    t = texto(raw)
    s = t.lstrip()[:1]
    if s in "{[" and s:
        try:
            resumir_json(json.loads(t))
            return
        except ValueError:
            p("  parece JSON mas não leu (cortado?)")
    if s == "<" and ("xml" in ct or t.lstrip().startswith("<?xml")) and "<html" not in t[:500].lower():
        tags = re.findall(r"<([A-Za-z_][\w:.-]*)[\s>]", t[:20000])
        vistos = list(dict.fromkeys(tags))
        p(f"  XML: tags {vistos[:60]}")
        p(f"  início: {mascara(re.sub(r'\s+', ' ', t[:900]))}")
        return
    if "html" in ct or s == "<":
        titulo = re.search(r"<title[^>]*>(.*?)</title>", t, re.I | re.S)
        p(f"  HTML: título {(titulo.group(1).strip()[:100] if titulo else '-')!r}")
        if html_links:
            lk = Links(url)
            try:
                lk.feed(t)
            except Exception:  # noqa: BLE001
                pass
            bons = [(a, h) for a, h in dict.fromkeys(lk.links) if PALAVRAS.search(h + " " + a)]
            for a, h in bons[:60]:
                p(f"    link: {a!r} -> {h}")
            if not bons:
                p(f"    (nenhum link de dados; {len(lk.links)} links no total)")
        return
    if "csv" in ct or ";" in t[:500] or "," in t[:500]:
        resumir_csv(t)
        return
    p(f"  início: {mascara(t[:400])!r}")


def ckan(nome: str, base: str, pacote: str) -> list[dict]:
    p(f"\n### {nome} (CKAN {pacote})")
    r, raw, erro = baixar(base + pacote)
    if r is None or r.status_code >= 400:
        p(f"  FALHA: {erro or r.status_code}")
        return []
    try:
        res = json.loads(raw)["result"]
    except (ValueError, KeyError):
        p("  resposta não é CKAN")
        return []
    p(f"  título: {res.get('title')!r} | atualizado: {res.get('metadata_modified')} | licença: {res.get('license_title')}")
    recursos = res.get("resources") or []
    p(f"  {len(recursos)} recursos")
    for rc in recursos[:200]:
        p(f"    - {rc.get('name')!r} [{rc.get('format')}] {rc.get('url')}")
    return recursos


def primeiro_id_almg(raw: bytes) -> str | None:
    t = texto(raw)
    m = re.search(r'"id"\s*:\s*(\d+)', t) or re.search(r"<id>(\d+)</id>", t)
    return m.group(1) if m else None


def main(saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    p("# Sondagem das fontes de MG")

    p("\n## ALMG: arquivos (CSV)")
    for nome, caminho in [
        ("Deputados", "/arquivo/deputados/download"),
        ("Deputados da atual legislatura", "/arquivo/deputados-da-atual-legislatura/download"),
        ("Verbas indenizatórias", "/arquivo/verbas-indenizatorias/download"),
        ("Proposições 2025 (sem tipo)", "/arquivo/proposicoes/download?ano=2025"),
        ("Proposições 2025 PL", "/arquivo/proposicoes/download?ano=2025&tipo=PL"),
        ("Tramitação 2025", "/arquivo/tramitacao-de-proposicoes/download?ano=2025"),
        ("Contratos", "/arquivo/contratos/download"),
    ]:
        sondar(nome, ALMG + caminho, salvar=saida / f"almg_{re.sub(r'\W+', '_', nome)}.bin")
    for doc in ["verbas-indenizatorias", "proposicoes", "tramitacao-de-proposicoes", "deputados-da-atual-legislatura"]:
        sondar(f"Documentação {doc}", f"{ALMG}/documentacao/arquivos/{doc}")

    p("\n## ALMG: páginas de ajuda dos webservices (para achar os caminhos)")
    for serv in ["prestacao_contas/verbas_indenizatorias", "pronunciamentos", "representacao_partidaria", "plenario",
                 "comissoes", "deputados", "proposicoes"]:
        r, raw = sondar(f"Ajuda {serv}", f"{ALMG_WS}/{serv}/ajuda", html_links=False)
        if raw:
            t = re.sub(r"<[^>]+>", " ", texto(raw))
            caminhos = sorted(set(re.findall(r"/ws/[\w/{}\-.]+", t)))
            p(f"  caminhos citados: {caminhos[:80]}")
    for u in [ALMG + "/api/ajuda/swagger/view/lastest", ALMG + "/api/swagger/docs/v1", ALMG + "/api/ajuda/swagger/docs/lastest",
              ALMG + "/api/swagger.json", ALMG + "/documentacao/index"]:
        sondar("API nova da ALMG", u)

    p("\n## ALMG: webservices (JSON)")
    r, raw = sondar("Deputados em exercício", f"{ALMG_WS}/deputados/em_exercicio?formato=json")
    dep = primeiro_id_almg(raw) if raw else None
    p(f"  id de exemplo: {dep}")
    if dep:
        for nome, caminho in [
            ("Ficha do deputado", f"/deputados/{dep}"),
            ("Partido em 2025", f"/deputados/{dep}/partidos/2025"),
            ("Comissões do deputado", f"/deputados/{dep}/participacoes_comissoes"),
            ("Verba: meses com dados", f"/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados/{dep}/datas"),
            ("Verba: jan/2025", f"/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados/{dep}/2025/1"),
            ("Verba: lista de deputados", "/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados"),
            ("Pronunciamentos do deputado", f"/pronunciamentos/pesquisa/direcionada?autor={dep}&ini=20250101&fim=20251231"),
            ("Comissões: reuniões do deputado", f"/comissoes/reunioes/pesquisa?idDeputado={dep}&ini=20250901&fim=20250930"),
        ]:
            sondar(nome, f"{ALMG_WS}{caminho}{'&' if '?' in caminho else '?'}formato=json")
    for nome, caminho in [
        ("Proposições: sumário por deputado 2025", "/deputados/proposicoes/sumario?ini=20250101&fim=20251231"),
        ("Plenário: reuniões set/2025", "/plenario/reunioes/pesquisa?ini=20250901&fim=20250930&tp=5"),
        ("Plenário: tipos de quórum", "/plenario/reunioes/tipos_quorum"),
        ("Representação partidária", "/representacao_partidaria/ajuda"),
        ("Proposição PL 1/2025: reuniões e resultados", "/comissoes/proposicao/PL/1/2025/reunioes/resultados"),
        ("Pronunciamentos: pesquisa", "/pronunciamentos/pesquisa/direcionada?ini=20250901&fim=20250930&tp=5"),
    ]:
        sondar(nome, f"{ALMG_WS}{caminho}{'&' if '?' in caminho else '?'}formato=json")

    p("\n## ALMG: portal (votações nominais, presença, emendas, gabinete)")
    for nome, u in [
        ("Emendas parlamentares", "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/"),
        ("Plenário: resultados", "https://www.almg.gov.br/atividade-parlamentar/plenario/"),
        ("Deputados: lista no portal", "https://www.almg.gov.br/deputados/conheca_deputados/"),
        ("Prestação de contas", "https://www.almg.gov.br/transparencia/prestacao-de-contas/"),
        ("Verba: página de um deputado", "https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/detalhe.html?id=28859"),
        ("Remuneração e custeio", "https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/remuneracao-dos-deputados-e-custeio/"),
        ("Pessoal", "https://www.almg.gov.br/transparencia/prestacao-de-contas/despesa-com-pessoal/"),
        ("Diário do Legislativo", "https://www.almg.gov.br/transparencia/diario-do-legislativo/"),
    ]:
        sondar(nome, u)
    if dep:
        for u in [f"https://www.almg.gov.br/deputados/conheca_deputados/deputados-info.html?idDep={dep}",
                  f"https://www.almg.gov.br/deputados/{dep}/"]:
            sondar("Perfil do deputado no portal", u)

    p("\n## Dados MG (CKAN)")
    for pacote in ["despesa", "portal_emendas_estaduais", "remuneracao-servidores-ativos", "relacao_nominal_servidores",
                   "diarias", "viagens"]:
        recursos = ckan(pacote, CKAN_MG, pacote)
        alvo = [rc for rc in recursos if re.search(r"datapackage|execu|2026|_2025|setembro de 2026|agosto de 2026",
                                                   (rc.get("name") or "") + (rc.get("url") or ""), re.I)]
        for rc in alvo[:4]:
            sondar(f"  recurso {rc.get('name')}", rc["url"], html_links=False)
    r, raw = sondar("Dados MG: busca 'emenda'", "https://dados.mg.gov.br/api/3/action/package_search?q=emenda&rows=20")
    r, raw = sondar("Dados MG: busca 'diária'", "https://dados.mg.gov.br/api/3/action/package_search?q=di%C3%A1rias&rows=20")

    p("\n## TSE (CKAN)")
    for pacote in ["candidatos-2024", "resultados-2024", "candidatos-1996", "resultados-1996", "candidatos-2022"]:
        recursos = ckan(f"TSE {pacote}", CKAN_TSE, pacote)
        for rc in [rc for rc in recursos if re.search(r"consulta_cand_2024|votacao_candidato_munzona_2024", rc.get("url") or "")][:1]:
            try:
                h = S.head(rc["url"], timeout=30, allow_redirects=True)
                p(f"  HEAD {rc['url']}: {h.status_code} {h.headers.get('content-length')} bytes")
            except Exception as e:  # noqa: BLE001
                p(f"  HEAD falhou: {e}")

    p("\n## TCE-MG")
    for u in ["https://dadosabertos.tce.mg.gov.br/", "https://www.tce.mg.gov.br/dadosabertos",
              "https://fiscalizandocomtce.tce.mg.gov.br/"]:
        sondar("TCE-MG", u)

    p("\n## Itajubá")
    for nome, u in [
        ("Prefeitura: transparência", "https://www.itajuba.mg.gov.br/transparencia"),
        ("Câmara: site", "https://itajuba.cam.mg.gov.br/site/"),
        ("Câmara: despesas", "https://itajuba.cam.mg.gov.br/site/despesas/"),
        ("Câmara: SisCam sessões", "https://itajuba.siscam.com.br/sessoes"),
        ("Câmara: SisCam início", "https://itajuba.siscam.com.br/"),
        ("Câmara: portal mg.leg.br", "https://www.itajuba.mg.leg.br/"),
        ("Câmara: SAPL", "https://sapl.itajuba.mg.leg.br/api/"),
    ]:
        sondar(nome, u)

    p("\n## Paraisópolis")
    for nome, u in [
        ("Prefeitura: página do portal", "https://www.paraisopolis.mg.gov.br/servicos/portal-da-transparencia/"),
        ("Prefeitura: portal SGP", "https://portal.sgpcloud.net:9116/transparencia/"),
        ("Prefeitura: portal antigo", "http://www.transparenciafacil.com.br/0189102"),
        ("Câmara: site", "https://www.paraisopolis.mg.leg.br/"),
        ("Câmara: transparência", "https://www.paraisopolis.mg.leg.br/transparencia"),
        ("Câmara: legislaturas", "https://www.paraisopolis.mg.leg.br/vereadores/legislaturas"),
        ("Câmara: uma matéria", "https://www.paraisopolis.mg.leg.br/atividade-legislativa/proposicoes/materia/734"),
        ("Câmara: SAPL", "https://sapl.paraisopolis.mg.leg.br/api/"),
    ]:
        sondar(nome, u)

    (saida / "relatorio.md").write_text("\n".join(relatorio), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "sondagem"))
