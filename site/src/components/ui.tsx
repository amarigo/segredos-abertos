import { Component, Fragment, createContext, isValidElement, useContext, useEffect, useState, type ReactNode } from "react";
import { COR_OUTROS, ComRosca, prepararFatias } from "./graficos";
import { Link } from "react-router-dom";
import { linkSeguro, load, reais, MESES, type Grupo } from "../data";

export function useData<T>(path: string | null): { data: T | null; error: string | null } {
  const [state, set] = useState<{ data: T | null; error: string | null }>({ data: null, error: null });
  useEffect(() => {
    if (!path) return;
    let vivo = true;
    set({ data: null, error: null });
    load<T>(path).then((d) => vivo && set({ data: d, error: null })).catch((e) => vivo && set({ data: null, error: String(e.message || e) }));
    return () => { vivo = false; };
  }, [path]);
  return state;
}

/** Vários arquivos de uma vez (por exemplo, um por ano, para comparar). Arquivo que falha fica de fora. */
export function useVarios<T>(paths: string[] | null): Record<string, T> {
  const [dados, set] = useState<Record<string, T>>({});
  const chave = paths ? paths.join("|") : "";
  useEffect(() => {
    if (!paths || !paths.length) return;
    let vivo = true;
    Promise.all(paths.map((p) => load<T>(p).then((d) => [p, d] as const).catch(() => null))).then((r) => {
      if (vivo) set(Object.fromEntries(r.filter((x): x is readonly [string, Awaited<T>] => !!x)) as Record<string, T>);
    });
    return () => { vivo = false; };
  }, [chave]); // eslint-disable-line
  return dados;
}

/** Fica true quando o elemento chega perto da tela: para baixar dados extras só quando a pessoa rolar até lá.
 *  Devolve um ref de função: funciona mesmo quando o elemento só aparece depois que os dados chegam. */
export function useVisivel<E extends Element>(): [(el: E | null) => void, boolean] {
  const [el, setEl] = useState<E | null>(null);
  const [v, setV] = useState(false);
  useEffect(() => {
    if (v || !el) return;
    if (typeof IntersectionObserver === "undefined") { setV(true); return; }
    const o = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { setV(true); o.disconnect(); } }, { rootMargin: "600px" });
    o.observe(el);
    return () => o.disconnect();
  }, [v, el]);
  return [setEl, v];
}

/* Ano escolhido no topo do site, compartilhado por todas as páginas */
export const AnoCtx = createContext<{ ano: string; anos: string[]; setAno: (a: string) => void }>({ ano: "", anos: [], setAno: () => {} });
export const useAno = () => useContext(AnoCtx);

export function AnoSeletor() {
  const { ano, anos, setAno } = useAno();
  if (!anos.length) return null;
  return (
    <label className="ano-sel">
      <span className="muted small">Ano</span>
      <select id="ano" value={ano} onChange={(e) => setAno(e.target.value)}>
        {anos.slice().reverse().map((a) => <option key={a} value={a}>{a}</option>)}
      </select>
    </label>
  );
}

/* Se um arquivo de dados vier com defeito e a página quebrar, mostra um aviso no lugar da tela em branco.
   O resto do site (menu, outras páginas) continua funcionando. */
export class ErroNaPagina extends Component<{ children: ReactNode }, { erro: boolean }> {
  state = { erro: false };
  static getDerivedStateFromError() { return { erro: true }; }
  componentDidCatch(e: unknown) { console.error("Erro ao mostrar a página:", e); }
  render() {
    if (this.state.erro) {
      return <div className="empty" role="alert">Não foi possível mostrar esta página. Os dados podem estar sendo atualizados: tente de novo em alguns minutos. <a href="#/">Voltar ao início</a></div>;
    }
    return this.props.children;
  }
}

export function Loading({ error }: { error?: string | null }) {
  if (error) return <div className="empty">Não foi possível carregar estes dados. {error}</div>;
  return <div className="empty">Carregando…</div>;
}

export function Explain({ children }: { children: ReactNode }) {
  return <p className="explain">{children}</p>;
}

/* Abertura: um bloco que abre e fecha para mostrar o detalhe (a lista de viagens de um ano, as indicações de um deputado...).
   O conteúdo só é montado quando a pessoa abre, então pode carregar um arquivo sob demanda. */
export function Abrir({ titulo, children, aberto = false }: { titulo: ReactNode; children: ReactNode; aberto?: boolean }) {
  const [open, setOpen] = useState(aberto);
  return (
    <details className="abrir" open={open} onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>{titulo}</summary>
      {open && <div className="abrir-corpo">{children}</div>}
    </details>
  );
}

/* "Onde ver tudo": os links das páginas e arquivos oficiais de onde vêm os dados de uma seção */
export function OndeVer({ links, titulo = "Onde ver tudo nos sites oficiais" }: { links: { nome: string; url: string; explica?: string }[]; titulo?: string }) {
  const ok = links.filter((l) => linkSeguro(l.url));
  if (!ok.length) return null;
  return (
    <div className="onde-ver">
      <strong className="small">{titulo}</strong>
      <ul>{ok.map((l) => (
        <li key={l.url + l.nome}><a href={linkSeguro(l.url)} target="_blank" rel="noreferrer">{l.nome} ↗</a>{l.explica && <span className="muted"> · {l.explica}</span>}</li>
      ))}</ul>
    </div>
  );
}

/* Colunas por categoria (por ano, por exemplo), com uma ou mais partes empilhadas (diárias + passagens, pago + a pagar).
   Embaixo, uma abertura com a tabela de valores, para quem não enxerga o gráfico ou quer o número exato. */
export function Colunas({ itens, partes, rotulo, fmt = (v: number) => reais(v, true) }: { itens: { label: string; valores: number[] }[]; partes: { nome: string; cor: string }[]; rotulo: string; fmt?: (v: number) => string }) {
  const tip = useTip();
  if (!itens.length) return null;
  const W = 640, H = 200, padL = 56, padB = 24, padT = 8;
  const total = (v: number[]) => v.reduce((a, b) => a + b, 0);
  const max = Math.max(...itens.map((i) => total(i.valores)));
  const passo = niceStep(max);
  const topo = Math.ceil(max / passo) * passo || 1;
  const bw = Math.min(90, (W - padL) / itens.length);
  const x0 = padL + ((W - padL) - bw * itens.length) / 2;
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / topo);
  const ticks = Array.from({ length: Math.round(topo / passo) + 1 }, (_, i) => i * passo);
  const curto = (t: number) => (t >= 1e9 ? `${(t / 1e9).toLocaleString("pt-BR")} bi` : t >= 1e6 ? `${(t / 1e6).toLocaleString("pt-BR")} mi` : t >= 1000 ? `${Math.round(t / 1000)} mil` : `${t}`);
  return (
    <div className="gm colunas" style={{ overflowX: "auto" }}>
      {partes.length > 1 && <div className="legend">{partes.map((p) => <span key={p.nome}><i style={{ background: p.cor }} />{p.nome}</span>)}</div>}
      {/* Com poucas colunas o gráfico encolhe no celular; com muitas, rola para o lado dentro do quadro */}
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={rotulo} style={itens.length <= 6 ? { minWidth: 0 } : undefined}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={padL - 6} y={y(t) + 4} textAnchor="end">{curto(t)}</text>
          </g>
        ))}
        {itens.map((it, i) => {
          const x = x0 + i * bw + 4;
          let base = 0;
          const texto = `${it.label}: ${fmt(total(it.valores))}${partes.length > 1 ? ` (${partes.map((p, k) => `${p.nome.toLowerCase()} ${fmt(it.valores[k] || 0)}`).join(", ")})` : ""}`;
          return (
            <g key={it.label} onMouseMove={(e) => tip.show(e, texto)} onMouseLeave={tip.hide}>
              {it.valores.map((v, k) => {
                const r = <rect key={k} x={x} y={y(base + v)} width={Math.max(1, bw - 8)} height={Math.max(0, y(base) - y(base + v))} fill={partes[k]?.cor || "var(--s1)"} />;
                base += v;
                return r;
              })}
              <text x={x + (bw - 8) / 2} y={H - 6} textAnchor="middle">{it.label}</text>
            </g>
          );
        })}
        <line x1={padL} x2={W} y1={y(0)} y2={y(0)} stroke="var(--muted)" />
      </svg>
      {tip.el}
      <details className="small">
        <summary>Ver os valores</summary>
        <div className="table-wrap" style={{ maxWidth: 520, marginTop: 8 }}>
          <table>
            <thead><tr><th></th>{partes.length > 1 && partes.map((p) => <th key={p.nome} className="r">{p.nome}</th>)}<th className="r">Total</th></tr></thead>
            <tbody>{itens.map((it) => (
              <tr key={it.label}><td>{it.label}</td>{partes.length > 1 && partes.map((p, k) => <td key={p.nome} className="r num">{fmt(it.valores[k] || 0)}</td>)}<td className="r num">{fmt(total(it.valores))}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/* Dica flutuante usada pelos gráficos */
export function useTip() {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const el = tip ? <div className="tip" style={{ left: tip.x + 12, top: tip.y + 12 }}>{tip.text}</div> : null;
  return { el, show: (e: React.MouseEvent, text: string) => setTip({ x: e.clientX, y: e.clientY, text }), hide: () => setTip(null) };
}

export const COR_GRUPO: Record<Grupo, string> = { pessoal: "var(--s1)", escritorio: "var(--s2)", servicos: "var(--s3)" };

/* Barras horizontais com rótulo e valor.
   rosca: quando as barras são partes de um todo, mostra em cima a barra das partes (com as mesmas cores) e a parte
   de cada linha em %; passar o mouse numa linha acende o pedaço e vice-versa. total: o todo, quando a lista mostra só as maiores. */
export function Barras({ itens, cor, max, rosca, formato, fmt: fmtAntigo }: {
  itens: { label: ReactNode; valor: number; cor?: string; nota?: string; nome?: string }[]; cor?: string; max?: number;
  rosca?: { titulo: string; total?: number; centroRotulo?: string; maxFatias?: number; paleta?: boolean }; formato?: (v: number) => string;
  /** o mesmo que formato (nome usado nas páginas do Minas Nossa) */
  fmt?: (v: number) => string;
}) {
  const [ativo, setAtivo] = useState<string | null>(null);
  const m = max ?? Math.max(1, ...itens.map((i) => i.valor));
  const fmt = formato || fmtAntigo || ((v: number) => reais(v));
  // Uma cor só na lista: cada parte ganha a sua, na ordem da paleta. Cores com sentido (partido, lado, grupo) ficam.
  const umaCor = !!rosca?.paleta || new Set(itens.map((i) => i.cor || cor)).size <= 1;
  const nomeDe = (i: { label: ReactNode; nome?: string }, k: number) => i.nome || (typeof i.label === "string" ? i.label : textoDe(i.label)) || `Item ${k + 1}`;
  const soma = rosca ? rosca.total ?? itens.reduce((a, i) => a + Math.max(0, i.valor), 0) : 0;
  const fatias = rosca ? prepararFatias(itens.map((i, k) => ({ nome: nomeDe(i, k), valor: i.valor, cor: umaCor ? undefined : i.cor || cor })), rosca.maxFatias, rosca.total) : [];
  const corDe = (k: number, i: { cor?: string }) => {
    if (!rosca) return i.cor || cor || "var(--s1)";
    return fatias.find((f) => f.nome === nomeDe(itens[k], k))?.cor || COR_OUTROS;
  };
  const lista = (
    <div className="bars">
      {itens.map((i, k) => {
        const nome = rosca ? nomeDe(i, k) : "";
        const dono = rosca && (fatias.some((f) => f.nome === nome) ? nome : "Outros");
        return (
          <div className={`bar-row ${rosca && ativo && ativo !== dono ? "apagado" : ""}`} key={k}
            onMouseEnter={rosca ? () => setAtivo(dono || null) : undefined} onMouseLeave={rosca ? () => setAtivo(null) : undefined}>
            <div style={{ minWidth: 0 }}>{i.label}{i.nota && <div className="muted small">{i.nota}</div>}</div>
            <div className="num">{fmt(i.valor)}{rosca && soma > 0 && <span className="pct-linha">{porcentoCurto(i.valor / soma)}</span>}</div>
            <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(i.valor / m) * 100}%`, background: corDe(k, i) }} /></div>
          </div>
        );
      })}
    </div>
  );
  if (!rosca || fatias.length < 2) return lista;
  return <ComRosca fatias={fatias} titulo={rosca.titulo} centroRotulo={rosca.centroRotulo} formato={formato || fmtAntigo} ativo={ativo} onAtivo={setAtivo}>{lista}</ComRosca>;
}

const porcentoCurto = (p: number) => (p < 0.01 ? "<1%" : `${(p * 100).toLocaleString("pt-BR", { maximumFractionDigits: p < 0.1 ? 1 : 0 })}%`);

/** Texto de um rótulo em JSX (para o nome da fatia da rosca) */
function textoDe(n: ReactNode): string {
  if (n == null || typeof n === "boolean") return "";
  if (typeof n === "string" || typeof n === "number") return String(n);
  if (Array.isArray(n)) return n.map(textoDe).join("");
  if (isValidElement(n)) return textoDe((n.props as { children?: ReactNode }).children);
  return "";
}

/* Colunas de gasto por mês (um ano) */
export function GastoMensal({ meses, ano, cor = "var(--s1)" }: { meses: { mes: number; valor: number }[]; ano: string; cor?: string }) {
  const tip = useTip();
  if (!meses.length) return <div className="empty">Sem gastos registrados em {ano}.</div>;
  const valores = Array.from({ length: 12 }, (_, i) => meses.find((m) => m.mes === i + 1)?.valor || 0);
  const W = 640, H = 200, padL = 52, padB = 24, padT = 8;
  const max = Math.max(...valores);
  const passo = niceStep(max);
  const topo = Math.ceil(max / passo) * passo || 1;
  const bw = (W - padL) / 12;
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / topo);
  const ticks = Array.from({ length: Math.round(topo / passo) + 1 }, (_, i) => i * passo);
  return (
    <div className="gm" style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Gasto por mês em ${ano}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={padL - 6} y={y(t) + 4} textAnchor="end">{t >= 1000 ? `${Math.round(t / 1000)} mil` : t}</text>
          </g>
        ))}
        {valores.map((v, i) => {
          const x = padL + i * bw + 2;
          return (
            <g key={i}>
              <rect x={x} y={y(v)} width={Math.max(1, bw - 4)} height={Math.max(0, y(0) - y(v))} rx={4} fill={cor}
                onMouseMove={(e) => tip.show(e, `${MESES[i]}/${ano}: ${reais(v)}`)} onMouseLeave={tip.hide} />
              <text x={x + (bw - 4) / 2} y={H - 6} textAnchor="middle">{MESES[i]}</text>
            </g>
          );
        })}
        <line x1={padL} x2={W} y1={y(0)} y2={y(0)} stroke="var(--muted)" />
      </svg>
      {tip.el}
      <details className="small">
        <summary>Ver os valores de cada mês</summary>
        <div className="kv" style={{ maxWidth: 360, marginTop: 8 }}>
          {valores.map((v, i) => <Fragment key={i}><span>{MESES[i]}/{ano}</span><span>{reais(v, true)}</span></Fragment>)}
          <strong>Total</strong><strong>{reais(valores.reduce((a, b) => a + b, 0), true)}</strong>
        </div>
      </details>
    </div>
  );
}

function niceStep(max: number): number {
  if (max <= 0) return 1;
  const raw = max / 4;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}

/* Régua esquerda–direita com pontos. O ponto em destaque fica dourado, maior, por cima dos outros e com o nome acima. */
export function Espectro({ pontos, destaque, nomeDestaque }: { pontos: { id: string; pos: number; label: string; href?: string }[]; destaque?: string; nomeDestaque?: string }) {
  const tip = useTip();
  const cor = (p: number) => (p < -0.15 ? "var(--esq)" : p > 0.15 ? "var(--dir)" : "var(--centro)");
  // Recuo de 11px nas pontas: os pontos dos extremos ficam inteiros dentro da régua
  const x = (pos: number) => { const t = (pos + 1) / 2; return `calc(${t * 100}% + ${(0.5 - t) * 22}px)`; };
  const eu = pontos.find((p) => p.id === destaque);
  // Perto das pontas, o nome fica alinhado pela borda para não sair da tela; a seta continua em cima do ponto
  const ancora = !eu ? "meio" : eu.pos < -0.6 ? "esq" : eu.pos > 0.6 ? "dir" : "meio";
  return (
    <div>
      {eu && (
        <div className="spectrum-eu" aria-hidden="true">
          <span className={`spectrum-eu-nome ${ancora}`} style={{ left: x(eu.pos) }}>{nomeDestaque || eu.label}</span>
        </div>
      )}
      <div className="spectrum" role="img" aria-label={eu ? `Posição de esquerda a direita. ${nomeDestaque || eu.label} está no ponto dourado.` : "Posição de esquerda a direita"}>
        {pontos.map((p, i) => {
          if (p.id === destaque) return null;
          const jitter = ((i * 37) % 30) - 15;
          const style = { left: x(p.pos), top: `calc(50% + ${jitter}px)`, background: cor(p.pos) };
          const dot = <span className="dot" style={style} onMouseMove={(e) => tip.show(e, p.label)} onMouseLeave={tip.hide} />;
          return p.href ? <Link key={p.id} to={p.href} aria-label={p.label}>{dot}</Link> : <span key={p.id}>{dot}</span>;
        })}
        {eu && <span className="dot me" style={{ left: x(eu.pos) }} onMouseMove={(e) => tip.show(e, eu.label)} onMouseLeave={tip.hide} />}
      </div>
      <div className="spectrum-labels"><span>◀ Esquerda</span><span>Centro</span><span>Direita ▶</span></div>
      {tip.el}
    </div>
  );
}

/* Barra empilhada Sim / Não / outros */
export function VotoBarra({ c }: { c: Record<string, number> }) {
  const sim = c["Sim"] || 0, nao = c["Não"] || 0;
  const outros = Object.entries(c).filter(([k]) => k !== "Sim" && k !== "Não").reduce((a, [, v]) => a + v, 0);
  const t = sim + nao + outros || 1;
  return (
    <div className="stack" title={`Sim ${sim} · Não ${nao} · Outros ${outros}`}>
      {sim > 0 && <span style={{ width: `${(sim / t) * 100}%`, background: "var(--sim)" }} />}
      {nao > 0 && <span style={{ width: `${(nao / t) * 100}%`, background: "var(--nao)" }} />}
      {outros > 0 && <span style={{ width: `${(outros / t) * 100}%`, background: "var(--outro)" }} />}
    </div>
  );
}

export function VotoLegenda() {
  return (
    <div className="legend">
      <span><i style={{ background: "var(--sim)" }} />Sim</span>
      <span><i style={{ background: "var(--nao)" }} />Não</span>
      <span><i style={{ background: "var(--outro)" }} />Abstenção, obstrução ou ausência</span>
    </div>
  );
}

export function VotoChip({ voto }: { voto: string }) {
  const cls = voto === "Sim" ? "chip ok" : voto === "Não" ? "chip nao" : "chip";
  return <span className={cls}>{voto}</span>;
}

/* Se a proposta foi aprovada ou rejeitada na votação */
export function ResultadoChip({ aprovada }: { aprovada: boolean }) {
  return <span className={`chip ${aprovada ? "ok" : "nao"}`}>{aprovada ? "Aprovado" : "Rejeitado"}</span>;
}

/* Link oficial de uma despesa. Nem toda despesa tem a imagem da nota: passagens compradas pelo sistema da Câmara
   e telefonia têm uma página de detalhe; o Senado só publica a lista de despesas de cada senador. "sem_pdf" é uma nota
   cujo PDF dá erro 404 no site da Câmara (a coleta confere todo dia): o link vai para a página de detalhe. */
export function LinkNota({ url: bruto, link }: { url?: string; link?: string }) {
  const url = linkSeguro(bruto);
  if (!url) return <span className="muted">Sem link oficial</span>;
  const senado = url.includes("senado.leg.br");
  const texto = link === "detalhe" ? "Ver detalhe na Câmara" : link === "sem_pdf" ? "Ver detalhe (a Câmara não publicou o PDF)"
    : link === "lista" ? (senado ? "Ver na lista do Senado" : "Ver o mês na Câmara") : "Abrir nota";
  const dica = link === "detalhe" ? "Página oficial da despesa no site da Câmara (para passagens e telefonia não há imagem de nota)"
    : link === "sem_pdf" ? "A nota está nos dados da Câmara, mas o PDF dela dá erro 404 no site oficial. O link abre a página oficial da despesa. Conferimos de novo a cada atualização e voltamos a mostrar a nota se o PDF aparecer."
    : link === "lista" ? (senado ? "O Senado não publica a imagem das notas: o link abre a lista oficial de despesas do senador, por tipo e ano" : "Resumo oficial das despesas do mês no site da Câmara")
    : "Imagem da nota fiscal no site oficial";
  return <a href={url} target="_blank" rel="noreferrer" title={dica}>{texto} ↗</a>;
}
