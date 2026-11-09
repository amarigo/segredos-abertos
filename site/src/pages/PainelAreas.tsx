import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Barras, Colunas, Explain, Loading, OndeVer, useData, useVarios } from "../components/ui";
import { COR_OUTROS, PALETA, curto } from "../components/graficos";
import { DetalheEmendaEstadual } from "../components/EmendaEstadual";
import { dataBR, indicacoesEstaduais, linkSeguro, reais, type EmendasEstado, type EmendasEstadoLista, type IndicacaoEstadual, type Meta } from "../data";
import { norm } from "./Home";
import "./painel.css";

/* Painel das emendas estaduais por área (saúde, educação, cultura...): quanto foi para cada área, para onde e em quê.
   A pessoa junta quantas áreas quiser, escolhe um ou mais anos e cruza com cidade, quem indicou e um texto livre
   (por exemplo "festa" ou "carnaval"). Tudo é somado aqui, a partir dos mesmos arquivos da página de emendas
   (uma linha por indicação, da ALMG); o endereço guarda os filtros para mandar o link. */

type Medida = "indicado" | "empenhado" | "pago";
const MEDIDAS: { id: Medida; nome: string; explica: string }[] = [
  { id: "indicado", nome: "Indicado", explica: "o que os deputados indicaram no orçamento" },
  { id: "empenhado", nome: "Empenhado", explica: "o que o estado já reservou para pagar" },
  { id: "pago", nome: "Pago", explica: "o que o estado já pagou" },
];
type Linha = IndicacaoEstadual & { ano: string };
type Soma = { nome: string; indicado: number; empenhado: number; pago: number; n: number };
const SEM_AREA = "Não informada";

function somar(rows: Linha[], chave: (x: Linha) => string): Soma[] {
  const m = new Map<string, Soma>();
  for (const x of rows) {
    const k = chave(x);
    const s = m.get(k) || { nome: k, indicado: 0, empenhado: 0, pago: 0, n: 0 };
    s.indicado += x.indicado; s.empenhado += x.empenhado; s.pago += x.pago; s.n += 1;
    m.set(k, s);
  }
  return [...m.values()];
}
const areaDe = (x: { area: string }) => x.area || SEM_AREA;
/** "1 indicação", "2.345 indicações": a frase inteira num texto só, para o tradutor achar no dicionário */
const indicacoes = (n: number) => `${n.toLocaleString("pt-BR")} ${n === 1 ? "indicação" : "indicações"}`;
const pct = (a: number, b: number) => (b > 0 ? `${Math.round((a / b) * 100)}%` : "—");

export default function PainelAreas() {
  const { data: resumo, error } = useData<EmendasEstado>("estado/emendas.json");
  const { data: meta } = useData<Meta>("meta.json");
  const [params, setParams] = useSearchParams();
  const todosAnos = useMemo(() => Object.keys(resumo?.anos || {}).sort(), [resumo]);
  const pedidos = params.getAll("ano").filter((a) => todosAnos.includes(a));
  const anos = pedidos.length ? [...new Set(pedidos)].sort() : todosAnos.slice(-1);
  const areas = params.getAll("area");
  const cidade = params.get("cidade") || "";
  const autor = params.get("autor") || "";
  const q = params.get("q") || "";
  const medida: Medida = (MEDIDAS.find((m) => m.id === params.get("medida"))?.id) || "indicado";

  const arquivos = useVarios<EmendasEstadoLista>(anos.length ? anos.map((a) => `estado/emendas/${a}.json`) : null);
  const carregados = anos.filter((a) => arquivos[`estado/emendas/${a}.json`]);
  const pronto = carregados.length === anos.length;
  const linhas = useMemo<Linha[]>(() => carregados.flatMap((a) => indicacoesEstaduais(arquivos[`estado/emendas/${a}.json`]).map((x) => ({ ...x, ano: a }))),
    [arquivos, carregados.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const deputados = useMemo(() => Object.assign({}, ...carregados.map((a) => arquivos[`estado/emendas/${a}.json`].deputados || {})) as Record<string, string>,
    [arquivos, carregados.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Troca um ou mais filtros no endereço (vazio apaga). Listas (anos e áreas) entram repetidas: ?area=Saúde&area=Cultura */
  const mudar = (f: Record<string, string | string[]>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(f)) {
      p.delete(k);
      (Array.isArray(v) ? v : [v]).filter(Boolean).forEach((x) => p.append(k, x));
    }
    setParams(p, { replace: true });
  };
  const alternar = (lista: string[], item: string) => (lista.includes(item) ? lista.filter((x) => x !== item) : [...lista, item]);

  const nq = norm(q.trim());
  // Os filtros de cidade, autor e texto valem para tudo; o de área fica de fora do gráfico das áreas, para ele
  // continuar mostrando todas (as escolhidas acesas) e dar para juntar mais uma.
  const base = useMemo(() => linhas.filter((x) => (!cidade || x.municipio === cidade) && (!autor || x.autor === autor)
    && (!nq || norm(`${x.beneficiario} ${x.descricao} ${x.objeto} ${x.acao} ${x.numero}`).includes(nq))), [linhas, cidade, autor, nq]);
  const porArea = useMemo(() => somar(base, areaDe).sort((a, b) => b[medida] - a[medida] || b.indicado - a.indicado), [base, medida]);
  const sel = useMemo(() => (areas.length ? base.filter((x) => areas.includes(areaDe(x))) : base), [base, areas.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  // Cor fixa de cada área, pela ordem no total do estado: a mesma área tem a mesma cor em todos os gráficos
  const corArea = useMemo(() => {
    const ordem = somar(linhas, areaDe).sort((a, b) => b.indicado - a.indicado).map((a) => a.nome);
    return (nome: string) => { const i = ordem.indexOf(nome); return i >= 0 && i < PALETA.length ? PALETA[i] : COR_OUTROS; };
  }, [linhas]);

  if (!resumo) return <Loading error={error} />;
  if (!todosAnos.length) return <div className="empty">Sem dados de emendas estaduais.</div>;

  const v = (s: { indicado: number; empenhado: number; pago: number }) => s[medida];
  const tot = sel.reduce((s, x) => ({ indicado: s.indicado + x.indicado, empenhado: s.empenhado + x.empenhado, pago: s.pago + x.pago }), { indicado: 0, empenhado: 0, pago: 0 });
  const nCidades = new Set(sel.map((x) => x.municipio)).size;
  const nomeMedida = MEDIDAS.find((m) => m.id === medida)!.nome.toLowerCase();
  const textoAnos = anos.length === 1 ? anos[0] : anos.length === todosAnos.length ? `${anos[0]} a ${anos[anos.length - 1]}` : anos.join(", ");
  const textoAreas = areas.length ? areas.join(" + ") : "todas as áreas";
  const maxArea = Math.max(1, ...porArea.map((x) => Math.max(x.indicado, v(x))));
  const algumFiltro = !!(areas.length || cidade || autor || q);
  const opcoes = (k: "municipio" | "autor") => [...new Set(linhas.map((x) => x[k]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt-BR"));

  return (
    <>
      <section>
        <p className="small"><Link to="/emendas-estaduais">‹ Emendas estaduais</Link></p>
        <h1>Painel das emendas por área</h1>
        <Explain>Veja todas as áreas de uma vez: quanto os deputados estaduais mandaram para saúde, educação, cultura, esporte, segurança e as demais, para quais cidades e em quê. Clique numa área para ver só ela, ou em várias para juntá-las. Dá para cruzar com o ano, a cidade, quem indicou e uma palavra (por exemplo "festa", "show" ou "carnaval").</Explain>

        <div className="painel-filtros">
          <div className="painel-grupo">
            <span className="muted small">Ano do orçamento (escolha um ou mais)</span>
            <div className="painel-chips" role="group" aria-label="Anos">
              {todosAnos.map((a) => (
                <button key={a} type="button" className="fchip" aria-pressed={anos.includes(a)}
                  onClick={() => { const n = alternar(anos, a); mudar({ ano: n.length ? n : [a] }); }}>{a}</button>
              ))}
              {todosAnos.length > 1 && <button type="button" className="link small" onClick={() => mudar({ ano: anos.length === todosAnos.length ? todosAnos.slice(-1) : todosAnos })}>
                {anos.length === todosAnos.length ? "Só o último ano" : "Todos os anos"}</button>}
            </div>
          </div>
          <div className="painel-grupo">
            <span className="muted small">Somar pelo valor</span>
            <div className="toggle" role="group" aria-label="Valor">
              {MEDIDAS.map((m) => <button key={m.id} type="button" aria-pressed={medida === m.id} title={m.explica}
                onClick={() => mudar({ medida: m.id === "indicado" ? "" : m.id })}>{m.nome}</button>)}
            </div>
          </div>
          <div className="filtros-emendas">
            <label><span className="muted small">Cidade</span>
              <select id="painel-cidade" value={cidade} onChange={(e) => mudar({ cidade: e.target.value })}>
                <option value="">Todas as cidades</option>
                {cidade && !opcoes("municipio").includes(cidade) && <option value={cidade}>{cidade}</option>}
                {opcoes("municipio").map((o) => <option key={o} value={o}>{o}</option>)}
              </select></label>
            <label><span className="muted small">Quem indicou</span>
              <select id="painel-autor" value={autor} onChange={(e) => mudar({ autor: e.target.value })}>
                <option value="">Todos os autores</option>
                {autor && !opcoes("autor").includes(autor) && <option value={autor}>{autor}</option>}
                {opcoes("autor").map((o) => <option key={o} value={o}>{o}</option>)}
              </select></label>
            <label><span className="muted small">Procurar palavra</span>
              <input id="painel-busca" type="search" value={q} onChange={(e) => mudar({ q: e.target.value })} placeholder="Ex.: festa, carnaval, ambulância" /></label>
          </div>
        </div>
      </section>

      {!pronto ? <Loading /> : <>
        <section aria-live="polite">
          <p className="painel-resumo">
            <strong>{textoAreas}</strong> · {textoAnos}{cidade && <> · {cidade}</>}{autor && <> · {autor}</>}{q && <> · “{q}”</>}
            {algumFiltro && <> · <button type="button" className="link" onClick={() => mudar({ area: [], cidade: "", autor: "", q: "" })}>Limpar filtros</button></>}
          </p>
          <div className="grid">
            <div className="card stat kpi"><span className="label">Indicado</span><span className="value">{curto(tot.indicado)}</span>
              <span className="hint">{`${indicacoes(sel.length)} para ${nCidades.toLocaleString("pt-BR")} ${nCidades === 1 ? "cidade" : "cidades"}`}</span></div>
            <div className="card stat kpi"><span className="label">Empenhado (reservado)</span><span className="value">{curto(tot.empenhado)}</span>
              <span className="hint">{`${pct(tot.empenhado, tot.indicado)} do indicado`}</span></div>
            <div className="card stat kpi"><span className="label">Já pago</span><span className="value">{curto(tot.pago)}</span>
              <span className="hint">{`${pct(tot.pago, tot.indicado)} do indicado`}</span>
              <span className="painel-exec" aria-hidden="true"><i style={{ width: tot.indicado ? `${Math.min(100, (tot.pago / tot.indicado) * 100)}%` : 0 }} /></span></div>
          </div>
        </section>

        <section>
          <h2>Todas as áreas</h2>
          <p className="muted small">{`Clique numa área para filtrar; clique em outras para juntar. A barra clara é o total indicado e a escura, o que já foi pago. Ordenado pelo valor ${nomeMedida}.`}</p>
          {!porArea.length ? <div className="empty">Nenhuma indicação com esses filtros.</div> : <>
            <div className="painel-areas" role="group" aria-label="Áreas">
              {porArea.map((a) => {
                const ligado = areas.includes(a.nome);
                return (
                  <button key={a.nome} type="button" className={`painel-area ${areas.length && !ligado ? "apagado" : ""}`} aria-pressed={ligado}
                    onClick={() => mudar({ area: alternar(areas, a.nome) })} title={ligado ? `Tirar ${a.nome} do filtro` : `Filtrar por ${a.nome}`}>
                    <span className="painel-area-nome"><i className="painel-marca" style={{ background: corArea(a.nome) }} aria-hidden="true" />{a.nome}</span>
                    <span className="num painel-area-val">{reais(v(a))}</span>
                    <span className="painel-area-barra" aria-hidden="true">
                      <i className="painel-claro" style={{ width: `${(a.indicado / maxArea) * 100}%`, background: corArea(a.nome) }} />
                      <i className="painel-escuro" style={{ width: `${(a.pago / maxArea) * 100}%`, background: corArea(a.nome) }} />
                    </span>
                    <span className="muted small painel-area-nota">{`${indicacoes(a.n)} · ${pct(a.pago, a.indicado)} pago`}</span>
                  </button>
                );
              })}
            </div>
            {areas.length > 0 && <p className="small"><button type="button" className="link" onClick={() => mudar({ area: [] })}>Ver todas as áreas de novo</button></p>}
          </>}
        </section>

        <AnoAAno resumo={resumo} areas={areas} medida={medida} corArea={corArea} outrosFiltros={!!(cidade || autor || q)} />

        <Onde sel={sel} areas={areas.length ? areas : porArea.slice(0, 6).map((a) => a.nome)} medida={medida} corArea={corArea}
          escolher={(c) => mudar({ cidade: c === cidade ? "" : c })} cidade={cidade} />

        <section>
          <h2>Em quê o dinheiro foi usado</h2>
          <p className="muted small">Pelo objeto da indicação (custeio, investimento, compra de veículo, obra, evento...). Clique para procurar só por ele.</p>
          <Barras itens={somar(sel, (x) => x.objeto || x.acao || "Não informado").sort((a, b) => v(b) - v(a)).slice(0, 15).map((o) => ({
            nome: o.nome, valor: v(o), cor: "var(--c5)", nota: indicacoes(o.n),
            label: o.nome === "Não informado" ? o.nome : <button type="button" className="link" onClick={() => mudar({ q: o.nome })}>{o.nome}</button> }))} />
        </section>

        <div className="grid painel-duas">
          <section className="card">
            <h3>Quem mais recebeu</h3>
            <Barras itens={somar(sel, (x) => `${x.beneficiario || "Não informado"}\u0000${x.municipio}`).sort((a, b) => v(b) - v(a)).slice(0, 10).map((b) => {
              const [nome, mun] = b.nome.split("\u0000");
              return { nome, valor: v(b), cor: "var(--s2)", nota: `${mun} · ${indicacoes(b.n)}`,
                label: <button type="button" className="link" onClick={() => mudar({ q: nome, cidade: mun })}>{nome}</button> };
            })} />
          </section>
          <section className="card">
            <h3>Quem indicou mais</h3>
            <Barras itens={somar(sel, (x) => x.autor || "Não informado").sort((a, b) => v(b) - v(a)).slice(0, 10).map((d) => ({
              nome: d.nome, valor: v(d), cor: "var(--s3)", nota: indicacoes(d.n),
              label: <span><button type="button" className="link" onClick={() => mudar({ autor: d.nome === autor ? "" : d.nome })}>{d.nome}</button>
                {deputados[d.nome] && <> · <Link className="small" to={`/deputado-estadual/${deputados[d.nome]}?aba=emendas`}>página</Link></>}</span> }))} />
          </section>
        </div>

        <Lista sel={sel} medida={medida} deputados={deputados} />

        <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(resumo.fonte)} target="_blank" rel="noreferrer">emendas parlamentares na ALMG ↗</a>
          {resumo.arquivo && <> (<a href={linkSeguro(resumo.arquivo)} target="_blank" rel="noreferrer">arquivo CSV ↗</a>)</>}
          {meta?.atualizado_em && <>{`, dados atualizados em ${dataBR(meta.atualizado_em)}`}</>}. <span>Só indicações aprovadas. A área é a função do orçamento informada pela ALMG; "Não informada" é quando o arquivo não traz a área.</span></p>
      </>}

      <OndeVer links={[
        { nome: "Emendas parlamentares na Assembleia de Minas (ALMG)", url: resumo.fonte, explica: "a lista oficial de indicações" },
        { nome: "Transparência das emendas no governo de Minas", url: "https://www.emendas.mg.gov.br/transparencia/", explica: "empenho, liquidação e pagamento de cada indicação" },
      ]} />
    </>
  );
}

/** Ano a ano das áreas escolhidas, com os totais já somados pela coleta (um número por área e ano, de todos os anos). */
function AnoAAno({ resumo, areas, medida, corArea, outrosFiltros }: { resumo: EmendasEstado; areas: string[]; medida: Medida; corArea: (n: string) => string; outrosFiltros: boolean }) {
  const anos = Object.keys(resumo.anos).sort();
  if (anos.length < 2) return null;
  const val = (s: { indicado: number; pago: number; empenhado?: number }) => (medida === "empenhado" ? s.empenhado || 0 : s[medida]);
  // Sem área escolhida: as 6 maiores de todos os anos e o resto junto em "Outras áreas"
  const total = new Map<string, number>();
  anos.forEach((a) => (resumo.anos[a].areas || []).forEach((x) => total.set(x.nome, (total.get(x.nome) || 0) + x.indicado)));
  const mostrar = areas.length ? areas : [...total.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([n]) => n);
  const comOutras = !areas.length && total.size > mostrar.length;
  const partes = [...mostrar.map((n) => ({ nome: n, cor: corArea(n) })), ...(comOutras ? [{ nome: "Outras áreas", cor: COR_OUTROS }] : [])];
  const itens = anos.map((a) => {
    const lista = resumo.anos[a].areas || [];
    const de = (n: string) => { const x = lista.find((y) => y.nome === n); return x ? val(x) : 0; };
    const vals = mostrar.map(de);
    if (comOutras) vals.push(lista.filter((x) => !mostrar.includes(x.nome)).reduce((s, x) => s + val(x), 0));
    return { label: a, valores: vals };
  });
  return (
    <section>
      <h2>Ano a ano{areas.length ? `: ${areas.join(" + ")}` : ""}</h2>
      <Colunas rotulo={`Emendas estaduais por ano e área (${medida})`} partes={partes} itens={itens} />
      {outrosFiltros && <p className="muted small">Este gráfico soma o estado inteiro, só com o filtro de área; cidade, autor e palavra não entram nele.</p>}
    </section>
  );
}

/** Onde o dinheiro foi: as cidades que mais receberam e, para elas, quanto foi para cada área (quanto mais forte a cor, mais dinheiro). */
function Onde({ sel, areas, medida, corArea, escolher, cidade }: { sel: Linha[]; areas: string[]; medida: Medida; corArea: (n: string) => string;
  escolher: (c: string) => void; cidade: string }) {
  const [qtd, setQtd] = useState(12);
  const cidades = useMemo(() => somar(sel, (x) => x.municipio).sort((a, b) => b[medida] - a[medida]), [sel, medida]);
  const cruz = useMemo(() => {
    const m = new Map<string, number>();
    sel.forEach((x) => { const k = `${x.municipio}\u0000${areaDe(x)}`; m.set(k, (m.get(k) || 0) + x[medida]); });
    return m;
  }, [sel, medida]);
  if (!cidades.length) return null;
  const topo = cidades.slice(0, qtd);
  const maxCel = Math.max(1, ...topo.flatMap((c) => areas.map((a) => cruz.get(`${c.nome}\u0000${a}`) || 0)));
  return (
    <section>
      <h2>Onde: as cidades</h2>
      <p className="muted small">{`${cidades.length.toLocaleString("pt-BR")} ${cidades.length === 1 ? "cidade recebeu" : "cidades receberam"} indicações com esses filtros.`} Clique numa cidade para ver só ela.</p>
      <div className="table-wrap">
        <table className="small painel-matriz">
          <thead><tr><th>Cidade</th><th className="r">Total</th>{areas.map((a) => <th key={a} className="r"><i className="painel-marca" style={{ background: corArea(a) }} aria-hidden="true" />{a}</th>)}</tr></thead>
          <tbody>{topo.map((c) => (
            <tr key={c.nome} className={cidade === c.nome ? "painel-linha-sel" : undefined}>
              <td><button type="button" className="link" onClick={() => escolher(c.nome)}>{c.nome}</button></td>
              <td className="r num"><strong>{reais(c[medida])}</strong></td>
              {areas.map((a) => {
                const x = cruz.get(`${c.nome}\u0000${a}`) || 0;
                return <td key={a} className="r num painel-cel" style={x ? { background: `color-mix(in srgb, ${corArea(a)} ${Math.round(12 + (x / maxCel) * 55)}%, transparent)` } : undefined}
                  title={`${c.nome}, ${a}: ${reais(x)}`}>{x ? curto(x) : "—"}</td>;
              })}
            </tr>
          ))}</tbody>
        </table>
      </div>
      {cidades.length > qtd && <button type="button" className="link" onClick={() => setQtd(qtd + 24)}>Mostrar mais cidades ({(cidades.length - qtd).toLocaleString("pt-BR")} restantes)</button>}
    </section>
  );
}

/** Cada indicação que entrou na soma, da maior para a menor */
function Lista({ sel, medida, deputados }: { sel: Linha[]; medida: Medida; deputados: Record<string, string> }) {
  const [qtd, setQtd] = useState(15);
  const ord = useMemo(() => [...sel].sort((a, b) => b[medida] - a[medida] || b.indicado - a.indicado), [sel, medida]);
  if (!ord.length) return null;
  return (
    <section id="painel-lista">
      <h2>Cada indicação</h2>
      <div className="table-wrap">
        <table className="small">
          <thead><tr><th>Quem recebe, para quê e quem executa</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
          <tbody>{ord.slice(0, qtd).map((x, i) => (
            <tr key={`${x.ano}-${x.numero}-${i}`}>
              <td><strong>{x.beneficiario || "Quem recebe não informado"}</strong>
                <div className="muted">{[x.municipio, x.area, x.ano].filter(Boolean).join(" · ")}{x.numero ? ` · indicação nº ${x.numero}` : ""}</div>
                <DetalheEmendaEstadual x={x} autor={deputados[x.autor] ? <Link to={`/deputado-estadual/${deputados[x.autor]}?aba=emendas&ano=${x.ano}`}>{x.autor}</Link> : x.autor} />
                <div className="so-celular">Pago: <span className="num">{reais(x.pago)}</span></div></td>
              <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.indicado)}{x.empenhado > 0 && <div className="muted">empenhado {reais(x.empenhado)}</div>}</td>
              <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(x.pago)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {ord.length > qtd && <button type="button" className="link" onClick={() => setQtd(qtd + 50)}>Mostrar mais ({(ord.length - qtd).toLocaleString("pt-BR")} restantes)</button>}
    </section>
  );
}
