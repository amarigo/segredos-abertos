"""Fase 0, 2ª rodada: aprofunda o que a 1ª rodada deixou em aberto. Não publica nada.

- ALMG: votos nominais no Plenário, presença nas comissões, verba pela API, discursos, partidos (com pausa entre
  pedidos, porque a ALMG responde 429 quando são muitos seguidos)
- ALMG: arquivo de emendas (CSV do portal)
- Dados MG: viagens (diárias com meio de transporte e cargo), favorecidos da despesa, secretários e governador na folha
- Itajubá (SisCam), Paraisópolis, TCE-MG: com navegador comum no cabeçalho, para ver se o bloqueio é por robô

Uso: python mg/sondagem/sondar2.py saida/
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import zlib
from pathlib import Path

import sondar
from sondar import S, baixar, ckan, mascara, p, sondar as sondar_url, texto

ALMG = "https://dadosabertos.almg.gov.br/api/v2"
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "pt-BR,pt;q=0.9"}
_ultimo = [0.0]


def almg(caminho: str) -> object | None:
    """GET JSON na API da ALMG, com pausa de 2 s entre pedidos e espera longa no 429."""
    url = f"{ALMG}{caminho}{'&' if '?' in caminho else '?'}formato=json"
    for tentativa in range(4):
        espera = 2 - (time.time() - _ultimo[0])
        if espera > 0:
            time.sleep(espera)
        _ultimo[0] = time.time()
        r, raw, erro = baixar(url)
        if r is not None and r.status_code == 429:
            p(f"  429 em {caminho}; espera {30 * (tentativa + 1)} s")
            time.sleep(30 * (tentativa + 1))
            continue
        if r is None or r.status_code >= 400:
            p(f"  {caminho}: {erro or r.status_code} {mascara(texto(raw[:200]))!r}")
            return None
        try:
            return json.loads(raw)
        except ValueError:
            p(f"  {caminho}: não é JSON: {mascara(texto(raw[:200]))!r}")
            return None
    return None


def mostra(rotulo: str, obj, n: int = 1500) -> None:
    p(f"  {rotulo}: {mascara(json.dumps(obj, ensure_ascii=False))[:n]}")


def trechos(t: str, padrao: str, n: int = 8, largura: int = 220) -> None:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    achou = 0
    for m in re.finditer(padrao, t, re.I):
        p(f"    …{mascara(t[max(0, m.start() - largura // 2): m.end() + largura // 2])}…")
        achou += 1
        if achou >= n:
            break
    if not achou:
        p(f"    (nenhum trecho com /{padrao}/)")


def lista_de(obj) -> list:
    """Acha a primeira lista dentro de um JSON da ALMG."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = lista_de(v)
            if r:
                return r
    return []


def rodada_almg() -> None:
    p("\n## ALMG: Plenário, votos nominais")
    reun = almg("/plenario/reunioes/pesquisa?ini=20250301&fim=20250630&tp=60")
    itens = [x for x in lista_de(reun) if isinstance(x, dict)]
    p(f"  {len(itens)} reuniões de mar a jun/2025")
    if itens:
        mostra("exemplo de reunião", itens[0], 900)
    com_resultado = [x for x in itens if x.get("resultadoCompleto") or x.get("resultadosImportados")]
    p(f"  com resultado: {len(com_resultado)}")
    for x in com_resultado[:3]:
        dia = str(x.get("dia") or "")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", dia) or re.match(r"(\d{2})/(\d{2})/(\d{4})", dia)
        if not m:
            mostra("data não reconhecida", x.get("dia"))
            continue
        a, me, d = (m.group(1), m.group(2), m.group(3)) if len(m.group(1)) == 4 else (m.group(3), m.group(2), m.group(1))
        hora = str(x.get("hora") or "14:00")[:5]
        det = almg(f"/plenario/reunioes/{a}/{me}/{d}/{hora}")
        if det is None:
            continue
        t = json.dumps(det, ensure_ascii=False)
        p(f"\n  Reunião {d}/{me}/{a} {hora}: {len(t)} caracteres; chaves {list(det)[:10] if isinstance(det, dict) else type(det)}")
        trechos(t, r"nominal|votaram|votos? favor|sim:|placar|painel", 6)
        trechos(t, r"presen", 3)
        r, raw, _ = baixar(f"https://www.almg.gov.br/atividade-parlamentar/plenario/reuniao/?dia={d}&mes={me}&ano={a}&hr={hora}")
        if raw:
            p(f"  página da reunião no portal: HTTP {r.status_code if r else '-'}")
            trechos(texto(raw), r"nominal|votaram|resultado da vota|registraram|presentes", 6)

    p("\n## ALMG: comissões, presença e resultados")
    res = almg("/comissoes/proposicao/PL/1/2025/reunioes/resultados")
    for x in lista_de(res)[:1]:
        if isinstance(x, dict):
            mostra("presencas", x.get("presencas"), 900)
            mostra("proposicoes[0]", (x.get("proposicoes") or [None])[0], 900)
            mostra("acoes[0]", (x.get("acoes") or [None])[0], 900)

    p("\n## ALMG: deputados (ficha, partidos, verba, discursos)")
    deps = [x for x in lista_de(almg("/deputados/em_exercicio")) if isinstance(x, dict)]
    p(f"  {len(deps)} em exercício")
    dep = deps[1]["id"] if len(deps) > 1 else 12193
    ficha = almg(f"/deputados/{dep}")
    if isinstance(ficha, dict):
        f = ficha.get("deputado", ficha)
        for k in ("candidaturas", "filiacoes", "partidosLegislatura", "legislaturas", "situacaoLegislaturas"):
            mostra(k, f.get(k), 700)
    for cam in [f"/deputados/{dep}/partidos/2026/1", f"/deputados/{dep}/partidos/2024/6/1",
                "/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados",
                f"/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados/{dep}/datas",
                f"/prestacao_contas/verbas_indenizatorias/legislatura_atual/deputados/{dep}/2025/3",
                "/representacao_partidaria/blocos", "/representacao_partidaria/liderancas", "/representacao_partidaria/bancadas"]:
        mostra(cam, almg(cam), 1200)
    disc = almg(f"/pronunciamentos/pesquisa/direcionada?autor={dep}&ini=20250101&fim=20251231&tp=2")
    if isinstance(disc, dict):
        r0 = disc.get("resultado", {})
        p(f"  discursos 2025 do deputado {dep}: noOcorrencias={r0.get('noOcorrencias')}")
        mostra("discurso[0] (sem o texto)", {k: v for k, v in ((r0.get("listaItem") or [{}])[0]).items()
                                          if not isinstance(v, str) or len(v) < 300}, 1200)

    p("\n## ALMG: documentação nova (swagger)")
    for u in ["https://dadosabertos.almg.gov.br/api/ajuda/swagger/docs/lastest", "https://dadosabertos.almg.gov.br/api/v2/swagger.json",
              "https://dadosabertos.almg.gov.br/api/ajuda/swagger/view/lastest"]:
        time.sleep(3)
        r, raw, erro = baixar(u)
        p(f"  {u}: {r.status_code if r is not None else erro} {len(raw)} bytes")
        t = texto(raw)
        caminhos = sorted(set(re.findall(r'"(/api/v2/[^"]+)"', t)))
        if caminhos:
            p(f"  {len(caminhos)} caminhos:")
            for c in caminhos:
                p(f"    {c}")
            break
        trechos(t, r"swagger.*?\.json|api-docs|url:", 4)


def rodada_dados_mg() -> None:
    p("\n## ALMG: arquivo de emendas (portal)")
    sondar_url("Emendas ALMG (CSV)", "https://mediaserver.almg.gov.br/acervo/497/469/2497469.csv", html_links=False)

    p("\n## Dados MG: viagens")
    rec = {r.get("name"): r["url"] for r in ckan("viagens", sondar.CKAN_MG, "viagens")}
    for nome in ["Diárias SCDP", "Favorecido SCDP", "Cargo", "Cargo em Comissão", "Meio Transporte", "Tipo Viajante",
                 "Documento Viagem", "Motivo Viagem", "Cidade"]:
        if nome in rec:
            sondar_url(f"viagens: {nome}", rec[nome], html_links=False)
            if nome in ("Cargo", "Cargo em Comissão"):
                _, raw, _ = baixar(rec[nome])
                t = texto(zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw)) if raw[:2] == b"\x1f\x8b" else texto(raw)
                linhas = [ln for ln in t.splitlines() if re.search(r"GOVERNADOR|SECRET[AÁ]RIO DE ESTADO", ln, re.I)]
                p(f"    linhas com governador/secretário de Estado: {len(linhas)}; ex: {linhas[:6]}")

    p("\n## Dados MG: despesa, favorecido e ordem de pagamento")
    rec = {r.get("name"): r["url"] for r in ckan("despesa", sondar.CKAN_MG, "despesa")}
    for nome in rec:
        if re.search(r"Favorecido|Ordem de Pagamento|Unidade Or|Tipo Documento", nome or ""):
            sondar_url(f"despesa: {nome}", rec[nome], html_links=False)

    p("\n## Dados MG: governador, vice e secretários na folha")
    recs = ckan("remuneracao", sondar.CKAN_MG, "remuneracao-servidores-ativos")
    alvo = [r for r in recs if re.search(r"2026", r.get("name") or "")]
    if alvo:
        url = alvo[-1]["url"]
        p(f"  lendo inteiro: {alvo[-1].get('name')} {url}")
        achados, total, cab = [], 0, None
        try:
            with S.get(url, stream=True, timeout=300) as r:
                dec, resto = zlib.decompressobj(16 + zlib.MAX_WBITS), ""
                for ch in r.iter_content(1 << 20):
                    resto += dec.decompress(ch).decode("utf-8", "replace") if url.endswith(".gz") else ch.decode("utf-8", "replace")
                    *linhas, resto = resto.split("\n")
                    for ln in csv.reader(linhas, delimiter=";"):
                        if cab is None:
                            cab = ln
                            continue
                        total += 1
                        reg = dict(zip(cab, ln))
                        if re.search(r"GOVERNADOR|SECRETARIO DE ESTADO|SECRETÁRIO DE ESTADO",
                                     (reg.get("cargo_comissao") or "") + " " + (reg.get("cargo_efetivo") or ""), re.I):
                            achados.append({k: reg.get(k) for k in ("nome", "cargo_comissao", "cargo_efetivo", "orgao_exercicio",
                                                                   "remuneracao", "jetons", "remuneracao_liquida")})
        except Exception as e:  # noqa: BLE001
            p(f"  falhou: {e}")
        p(f"  {total} linhas; {len(achados)} com governador ou secretário de Estado")
        for a in achados[:45]:
            p(f"    {mascara(str(a))}")


def rodada_cidades() -> None:
    p("\n## Itajubá: SisCam (sessões, votos, proposituras)")
    for nome, u in [("Sessão 1164", "https://itajuba.siscam.com.br/Sessoes/Sessao/1164"),
                    ("Sessão 1150", "https://itajuba.siscam.com.br/Sessoes/Sessao/1150"),
                    ("Vereadores", "https://itajuba.siscam.com.br/vereadores"),
                    ("Proposituras", "https://itajuba.siscam.com.br/index/80/8")]:
        r, raw = sondar_url(nome, u)
        if raw:
            trechos(texto(raw), r"vota|nominal|favor|contr|presen|ausen|aprovad|rejeitad", 10)

    p("\n## Bloqueios: tentar com cabeçalho de navegador comum")
    for nome, u in [("Itajubá: prefeitura", "https://www.itajuba.mg.gov.br/transparencia"),
                    ("Paraisópolis: câmara", "https://www.paraisopolis.mg.leg.br/"),
                    ("Paraisópolis: câmara, legislaturas", "https://www.paraisopolis.mg.leg.br/vereadores/legislaturas"),
                    ("Paraisópolis: prefeitura, emendas", "https://www.paraisopolis.mg.gov.br/servicos/emendas-parlamentares/"),
                    ("TCE-MG: dados abertos", "https://dadosabertos.tce.mg.gov.br/"),
                    ("TCE-MG: portal", "https://www.tce.mg.gov.br/"),
                    ("TCE-MG: Fiscalizando", "https://fiscalizandocomtce.tce.mg.gov.br/")]:
        sondar_url(nome, u, headers=NAVEGADOR, timeout=60)


def main(saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    p("# Sondagem MG, 2ª rodada")
    for etapa in (rodada_almg, rodada_dados_mg, rodada_cidades):
        try:
            etapa()
        except Exception as e:  # noqa: BLE001 - uma etapa com erro não impede as outras
            p(f"\n!! {etapa.__name__} parou: {type(e).__name__}: {e}")
    (saida / "relatorio.md").write_text("\n".join(sondar.relatorio), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "sondagem"))
