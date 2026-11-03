/* Gráficos do site: rosca (pizza) ao lado de uma lista, mapa do Brasil por estado, comparação entre anos com
   animação e números grandes com a variação contra o ano anterior. Tudo em SVG, sem bibliotecas: o site continua
   leve no celular e funciona sem internet depois de aberto.
   Cores: as do site (styles.css), na mesma ordem em todos os gráficos. A paleta passou no validador de cores
   (daltonismo e contraste) no claro e no escuro; onde o contraste é menor, a lista ao lado traz o nome e o valor. */
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { reais } from "../data";
import { useTip } from "./ui";

export const PALETA = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--c7)", "var(--c8)"];
export const COR_OUTROS = "var(--c-outros)";

/** R$ com a escala certa: tri, bi, mi, mil. */
export function curto(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  const a = Math.abs(v), s = v < 0 ? "−" : "";
  const f = (x: number) => x.toLocaleString("pt-BR", { maximumFractionDigits: x >= 100 ? 0 : 1 });
  if (a >= 1e12) return `${s}R$ ${f(a / 1e12)} tri`;
  if (a >= 1e9) return `${s}R$ ${f(a / 1e9)} bi`;
  if (a >= 1e6) return `${s}R$ ${f(a / 1e6)} mi`;
  if (a >= 1e3) return `${s}R$ ${f(a / 1e3)} mil`;
  return `${s}${reais(a)}`;
}
export const numero = (v: number) => v.toLocaleString("pt-BR");
export const porcento = (v: number, casas = 1) => `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`;

/** Sem animação para quem pediu menos movimento no sistema */
function poucoMovimento(): boolean {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
}

/* ------------------------------------------------------------------ rosca */

export interface Fatia { nome: string; valor: number; cor?: string }
export type FatiaPronta = { nome: string; valor: number; cor: string; pct: number; outros?: boolean };

/** As maiores fatias (até max) têm cor própria, na ordem fixa da paleta; as demais entram juntas em "Outros".
 *  total: quando a lista mostra só uma parte, o que falta para o total também vira "Outros". */
export function prepararFatias(fatias: Fatia[], max = 7, total?: number): FatiaPronta[] {
  const pos = fatias.filter((f) => f.valor > 0);
  const proprias = pos.slice(0, pos.length > max + 1 ? max : max + 1);
  const resto = pos.slice(proprias.length).reduce((a, f) => a + f.valor, 0) + Math.max(0, (total ?? 0) - pos.reduce((a, f) => a + f.valor, 0));
  const soma = proprias.reduce((a, f) => a + f.valor, 0) + resto || 1;
  const itens: FatiaPronta[] = proprias.map((f, i) => ({ nome: f.nome, valor: f.valor, cor: f.cor || PALETA[i % PALETA.length], pct: f.valor / soma }));
  if (resto > soma * 0.0005) itens.push({ nome: "Outros", valor: resto, cor: COR_OUTROS, pct: resto / soma, outros: true });
  return itens;
}

const RAIO = 78, GROSSURA = 40, CIRC = 2 * Math.PI * RAIO;

/** Rosca animada. As fatias crescem ao abrir e mudam de tamanho suavemente quando o ano muda. */
export function Rosca({ fatias, titulo, formato = curto, centro, centroRotulo = "Total", ativo, onAtivo }: {
  fatias: FatiaPronta[]; titulo: string; formato?: (v: number) => string; centro?: string; centroRotulo?: string;
  ativo?: string | null; onAtivo?: (nome: string | null) => void;
}) {
  const tip = useTip();
  const [aberto, setAberto] = useState(poucoMovimento());
  const [sobre, setSobre] = useState<string | null>(null);
  useEffect(() => { const t = requestAnimationFrame(() => setAberto(true)); return () => cancelAnimationFrame(t); }, []);
  const foco = ativo ?? sobre;
  const total = fatias.reduce((a, f) => a + f.valor, 0);
  if (!total) return null;
  let ini = 0;
  const marca = (n: string | null) => { setSobre(n); onAtivo?.(n); };
  const atual = fatias.find((f) => f.nome === foco);
  return (
    <figure className="rosca" style={{ margin: 0 }}>
      <svg viewBox="0 0 200 200" role="img" aria-label={`${titulo}. ${fatias.map((f) => `${f.nome}: ${porcento(f.pct)}`).join("; ")}`}>
        <circle cx={100} cy={100} r={RAIO} fill="none" stroke="var(--grid)" strokeWidth={GROSSURA} />
        <g transform="rotate(-90 100 100)">
          {fatias.map((f) => {
            const comp = f.pct * CIRC;
            const vao = fatias.length > 1 && comp > 3 ? 1.6 : 0; // 2px de fundo entre as fatias
            const el = (
              <circle key={f.nome} className="rosca-fatia" cx={100} cy={100} r={RAIO} fill="none" stroke={f.cor} strokeWidth={GROSSURA}
                strokeDasharray={`${aberto ? Math.max(0, comp - vao) : 0} ${CIRC}`} strokeDashoffset={-ini}
                opacity={foco && foco !== f.nome ? 0.35 : 1} tabIndex={0} aria-label={`${f.nome}: ${formato(f.valor)}, ${porcento(f.pct)}`}
                onMouseMove={(e) => { tip.show(e, `${f.nome}: ${formato(f.valor)} (${porcento(f.pct)})`); if (sobre !== f.nome) marca(f.nome); }}
                onMouseLeave={() => { tip.hide(); marca(null); }} onFocus={() => marca(f.nome)} onBlur={() => marca(null)} />
            );
            ini += comp;
            return el;
          })}
        </g>
        {atual ? (
          <>
            <text x={100} y={88} textAnchor="middle" className="rosca-rot">{atual.nome.length > 22 ? `${atual.nome.slice(0, 21)}…` : atual.nome}</text>
            <text x={100} y={110} textAnchor="middle" className="rosca-num">{porcento(atual.pct)}</text>
            <text x={100} y={126} textAnchor="middle" className="rosca-rot">{formato(atual.valor)}</text>
          </>
        ) : (
          <>
            <text x={100} y={95} textAnchor="middle" className="rosca-rot">{centroRotulo}</text>
            <text x={100} y={116} textAnchor="middle" className="rosca-num">{centro ?? formato(total)}</text>
          </>
        )}
      </svg>
      <figcaption className="rosca-leg">
        {fatias.map((f) => (
          <span key={f.nome} className={foco && foco !== f.nome ? "apagado" : ""} onMouseEnter={() => marca(f.nome)} onMouseLeave={() => marca(null)}>
            <i style={{ background: f.cor }} />{f.nome} <b className="num">{f.pct < 0.01 ? "<1%" : porcento(f.pct, 0)}</b>
          </span>
        ))}
      </figcaption>
      {tip.el}
    </figure>
  );
}

/** Lista de um lado, rosca do outro (no celular, a rosca vem primeiro e menor). */
export function ComRosca({ fatias, titulo, formato, centro, centroRotulo, children, ativo, onAtivo }: {
  fatias: FatiaPronta[]; titulo: string; formato?: (v: number) => string; centro?: string; centroRotulo?: string; children: ReactNode;
  ativo?: string | null; onAtivo?: (n: string | null) => void;
}) {
  return (
    <div className="caixa-graf">
      <div className="com-rosca">
        <div className="com-rosca-lista">{children}</div>
        <Rosca fatias={fatias} titulo={titulo} formato={formato} centro={centro} centroRotulo={centroRotulo} ativo={ativo} onAtivo={onAtivo} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ variação e números grandes */

/** "▲ 12%" ou "▼ 3%" contra outro valor. Subir não é bom nem ruim por si: a cor é neutra, a seta diz o sentido. */
export function Variacao({ de, para, rotulo }: { de: number | null | undefined; para: number | null | undefined; rotulo?: string }) {
  if (de == null || para == null || !de) return null;
  const v = para / de - 1;
  if (!isFinite(v)) return null;
  const igual = Math.abs(v) < 0.005;
  return (
    <span className={`variacao ${igual ? "igual" : v > 0 ? "sobe" : "desce"}`} title={rotulo ? `Contra ${rotulo}` : undefined}>
      <span aria-hidden="true">{igual ? "＝" : v > 0 ? "▲" : "▼"}</span> {igual ? "igual" : `${v > 0 ? "+" : "−"}${porcento(Math.abs(v), Math.abs(v) < 0.1 ? 1 : 0)}`}{rotulo ? <span className="muted"> vs {rotulo}</span> : null}
    </span>
  );
}

/** Linha pequena com a série dos anos; o ano escolhido fica marcado. */
export function Faisca({ serie, marcado, cor = "var(--hot)" }: { serie: [string, number][]; marcado?: string; cor?: string }) {
  if (serie.length < 2) return null;
  const W = 120, H = 30, p = 4;
  const vs = serie.map(([, v]) => v), max = Math.max(...vs), min = Math.min(0, ...vs);
  const x = (i: number) => p + (i * (W - 2 * p)) / (serie.length - 1);
  const y = (v: number) => H - p - ((v - min) / (max - min || 1)) * (H - 2 * p);
  const pts = serie.map(([, v], i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg className="faisca" viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden="true">
      <polyline points={pts} fill="none" stroke={cor} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {serie.map(([a, v], i) => a === marcado && <circle key={a} cx={x(i)} cy={y(v)} r={4} fill={cor} stroke="var(--surface)" strokeWidth={2} />)}
    </svg>
  );
}

/** Número grande com a variação contra o ano anterior e a linha dos anos. */
export function Kpi({ rotulo, valor, formato = curto, serie, ano, dica, anterior: ant }: {
  rotulo: string; valor: number | null | undefined; formato?: (v: number) => string; serie?: [string, number][]; ano?: string; dica?: ReactNode;
  /** Base da variação quando não é o ano anterior inteiro (por exemplo, o mesmo período do ano anterior) */
  anterior?: { rotulo: string; valor: number | null | undefined; atual?: number | null } | null;
}) {
  const i = serie && ano ? serie.findIndex(([a]) => a === ano) : -1;
  const anterior: [string, number | null | undefined] | null = ant !== undefined ? (ant ? [ant.rotulo, ant.valor] : null) : serie && i > 0 ? serie[i - 1] : null;
  // No mesmo período, a seta compara o valor do período (ant.atual), que pode ser menor que o número grande do ano
  const comparado = ant && ant.atual != null ? ant.atual : valor;
  return (
    <div className="card stat kpi">
      <span className="label">{rotulo}</span>
      <span className="value">{valor == null ? "—" : formato(valor)}</span>
      {anterior && <Variacao de={anterior[1]} para={comparado} rotulo={anterior[0]} />}
      {serie && <Faisca serie={serie} marcado={ano} />}
      {dica && <span className="hint">{dica}</span>}
    </div>
  );
}

/* ------------------------------------------------------------------ mapa do Brasil por estado */

export const NOME_UF: Record<string, string> = {
  AC: "Acre", AL: "Alagoas", AM: "Amazonas", AP: "Amapá", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal", ES: "Espírito Santo",
  GO: "Goiás", MA: "Maranhão", MG: "Minas Gerais", MS: "Mato Grosso do Sul", MT: "Mato Grosso", PA: "Pará", PB: "Paraíba",
  PE: "Pernambuco", PI: "Piauí", PR: "Paraná", RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RO: "Rondônia", RR: "Roraima",
  RS: "Rio Grande do Sul", SC: "Santa Catarina", SE: "Sergipe", SP: "São Paulo", TO: "Tocantins",
};
type Desenho = { vb: string; p: Record<string, string> };
let desenho: Promise<Desenho> | null = null;
/** Contorno dos estados: o mesmo desenho do mapa da Eleição 2026, carregado só quando um mapa aparece. */
function useDesenho(): Desenho | null {
  const [d, setD] = useState<Desenho | null>(null);
  useEffect(() => {
    let vivo = true;
    desenho = desenho || import("./mapa-uf.json").then((m) => (m.default || m) as Desenho);
    desenho.then((x) => vivo && setD(x)).catch(() => { desenho = null; });
    return () => { vivo = false; };
  }, []);
  return d;
}

/** Cor de cada estado. Valor: um tom só, do claro ao escuro. Mudança: laranja sobe, azul desce, cinza no meio. */
function corMapa(v: number | undefined, max: number, divergente: boolean): string {
  if (v == null || !isFinite(v)) return "var(--grid)";
  if (divergente) {
    const t = Math.min(1, Math.abs(v) / (max || 1));
    if (t < 0.02) return "var(--centro)";
    return `color-mix(in oklab, ${v > 0 ? "var(--s2)" : "var(--s1)"} ${Math.round(25 + 75 * t)}%, var(--centro))`;
  }
  if (!v) return "var(--grid)";
  const t = Math.sqrt(Math.max(0, v) / (max || 1)); // raiz: estados pequenos não somem perto de SP
  return `color-mix(in oklab, var(--hot) ${Math.round(12 + 88 * t)}%, var(--surface))`;
}

export function MapaUF({ valores, max, titulo, formato = curto, divergente = false, onUf, ufAtiva, rotuloValor }: {
  valores: Record<string, number>; max?: number; titulo: string; formato?: (v: number) => string; divergente?: boolean;
  onUf?: (uf: string) => void; ufAtiva?: string; rotuloValor?: (uf: string) => string;
}) {
  const d = useDesenho();
  const tip = useTip();
  const m = max ?? Math.max(0, ...Object.values(valores).map((v) => Math.abs(v)));
  const texto = (uf: string) => rotuloValor ? rotuloValor(uf) : `${NOME_UF[uf] || uf}: ${valores[uf] == null ? "sem dado" : formato(valores[uf])}`;
  if (!d) return <div className="mapa-uf mapa-vazio" aria-hidden="true" />;
  return (
    <div className="mapa-uf">
      <svg viewBox={d.vb} role="group" aria-label={titulo}>
        {Object.entries(d.p).map(([uf, path]) => (
          <path key={uf} d={path} fill={corMapa(valores[uf], m, divergente)} className={`${ufAtiva === uf ? "ativa" : ""} ${onUf ? "clicavel" : ""}`}
            role={onUf ? "button" : "img"} tabIndex={0} aria-label={texto(uf)}
            onMouseMove={(e) => tip.show(e, texto(uf))} onMouseLeave={tip.hide}
            onClick={() => onUf?.(uf)} onKeyDown={(e) => { if (onUf && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onUf(uf); } }} />
        ))}
      </svg>
      {tip.el}
    </div>
  );
}

function LegendaMapa({ max, formato, divergente }: { max: number; formato: (v: number) => string; divergente?: boolean }) {
  return divergente ? (
    <div className="mapa-leg" aria-hidden="true">
      <span>Caiu {formato(max)}</span><i className="div" /><span>Subiu {formato(max)}</span>
    </div>
  ) : (
    <div className="mapa-leg" aria-hidden="true"><span>Menos</span><i className="seq" /><span>Mais · {formato(max)}</span></div>
  );
}

/** Mapa por estado com os anos: um ano por vez (com animação passando pelos anos), dois anos lado a lado,
 *  ou o que mudou entre eles. Todos os anos usam a mesma escala de cor, para comparar de verdade. */
export function MapaAnos({ porAno, titulo, formato = curto, anoInicial, explica, onUf, ufAtiva, porQue }: {
  porAno: Record<string, Record<string, number>>; titulo: string; formato?: (v: number) => string; anoInicial?: string;
  explica?: ReactNode; onUf?: (uf: string) => void; ufAtiva?: string; porQue?: string;
}) {
  const anos = Object.keys(porAno).filter((a) => Object.values(porAno[a]).some((v) => v)).sort();
  const [modo, setModo] = useState<"ano" | "lado" | "mudou">("ano");
  const [ano0, setAno] = useState(anoInicial || "");
  const ano = anos.includes(ano0) ? ano0 : anoInicial && anos.includes(anoInicial) ? anoInicial : anos[anos.length - 1];
  const [a0, setA] = useState("");
  const [b0, setB] = useState("");
  // Os dados dos outros anos podem chegar depois: até a pessoa escolher, compara os dois últimos anos
  const a = anos.includes(a0) ? a0 : anos[Math.max(0, anos.length - 2)];
  const b = anos.includes(b0) ? b0 : anos[anos.length - 1];
  const tocando = useTocar(anos, ano, setAno);
  useEffect(() => { if (anoInicial) setAno(anoInicial); }, [anoInicial]);
  if (!anos.length) return null;
  const anoV = anos.includes(ano) ? ano : anos[anos.length - 1];
  const max = Math.max(0, ...anos.flatMap((x) => Object.values(porAno[x])));
  const atual = porAno[anoV] || {};
  const ranking = Object.entries(atual).filter(([uf, v]) => v > 0 && NOME_UF[uf]).sort((x, y) => y[1] - x[1]);
  const anterior = anos[anos.indexOf(anoV) - 1];
  const totalAno = ranking.reduce((s, [, v]) => s + v, 0);
  const mud: Record<string, number> = {};
  if (modo === "mudou") for (const uf of new Set([...Object.keys(porAno[a] || {}), ...Object.keys(porAno[b] || {})])) mud[uf] = (porAno[b]?.[uf] || 0) - (porAno[a]?.[uf] || 0);
  const maxMud = Math.max(0, ...Object.values(mud).map(Math.abs));
  const fmtMud = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${formato(Math.abs(v))}`;
  return (
    <div className="mapa-anos caixa-graf">
      {explica && <p className="small muted">{explica}</p>}
      {anos.length > 1 && (
        <div className="row graf-controles">
          <div className="toggle" role="group" aria-label="Como comparar">
            <button aria-pressed={modo === "ano"} onClick={() => setModo("ano")}>Ano a ano</button>
            <button aria-pressed={modo === "lado"} onClick={() => setModo("lado")}>Dois anos lado a lado</button>
            <button aria-pressed={modo === "mudou"} onClick={() => setModo("mudou")}>O que mudou</button>
          </div>
        </div>
      )}
      {modo === "ano" && (
        <>
          <SeletorAnos anos={anos} ano={anoV} setAno={setAno} tocando={tocando} />
          <div className="mapa-com-lista">
            <div>
              <div className="mapa-ano-grande num" aria-live="polite">{anoV}</div>
              <MapaUF valores={atual} max={max} titulo={`${titulo} em ${anoV}`} formato={formato} onUf={onUf} ufAtiva={ufAtiva} />
              <LegendaMapa max={max} formato={formato} />
            </div>
            <ol className="mapa-ranking">
              {ranking.slice(0, 10).map(([uf, v]) => (
                <li key={uf} className={ufAtiva === uf ? "ativa" : ""}>
                  {onUf ? <button className="link" onClick={() => onUf(uf)}>{NOME_UF[uf] || uf}</button> : <span>{NOME_UF[uf] || uf}</span>}
                  <span className="num">{formato(v)}{totalAno ? <small className="muted"> · {porcento(v / totalAno, 0)}</small> : null}</span>
                  {anterior && <Variacao de={porAno[anterior]?.[uf]} para={v} />}
                </li>
              ))}
              {!ranking.length && <li className="muted">Sem valores em {anoV}.</li>}
            </ol>
          </div>
        </>
      )}
      {modo === "lado" && (
        <div className="mapa-lado">
          {[[a, setA], [b, setB]].map(([x, set], i) => (
            <div key={i}>
              <label className="graf-ano"><span className="muted small">{i ? "Comparar com" : "Ano"}</span>
                <select value={x as string} onChange={(e) => (set as (v: string) => void)(e.target.value)}>{anos.map((y) => <option key={y}>{y}</option>)}</select>
              </label>
              <MapaUF valores={porAno[x as string] || {}} max={max} titulo={`${titulo} em ${x}`} formato={formato} onUf={onUf} ufAtiva={ufAtiva} />
            </div>
          ))}
          <div style={{ gridColumn: "1 / -1" }}><LegendaMapa max={max} formato={formato} /></div>
        </div>
      )}
      {modo === "mudou" && (
        <>
          <div className="row graf-controles">
            <label className="graf-ano"><span className="muted small">De</span><select value={a} onChange={(e) => setA(e.target.value)}>{anos.map((y) => <option key={y}>{y}</option>)}</select></label>
            <label className="graf-ano"><span className="muted small">para</span><select value={b} onChange={(e) => setB(e.target.value)}>{anos.map((y) => <option key={y}>{y}</option>)}</select></label>
          </div>
          <div className="mapa-com-lista">
            <div>
              <MapaUF valores={mud} max={maxMud} divergente titulo={`O que mudou de ${a} para ${b}: ${titulo}`} formato={fmtMud} onUf={onUf} ufAtiva={ufAtiva}
                rotuloValor={(uf) => `${NOME_UF[uf] || uf}: ${formato(porAno[a]?.[uf] || 0)} em ${a} → ${formato(porAno[b]?.[uf] || 0)} em ${b}`} />
              <LegendaMapa max={maxMud} formato={formato} divergente />
            </div>
            <ol className="mapa-ranking">
              {Object.entries(mud).filter(([uf, v]) => v && NOME_UF[uf]).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1])).slice(0, 10).map(([uf, v]) => (
                <li key={uf}>
                  <span>{NOME_UF[uf] || uf}</span><span className="num">{fmtMud(v)}</span>
                  <Variacao de={porAno[a]?.[uf]} para={porAno[b]?.[uf]} />
                </li>
              ))}
            </ol>
          </div>
        </>
      )}
      {porQue && <p className="small muted">{porQue}</p>}
      <details className="small">
        <summary>Ver a tabela de todos os estados</summary>
        <div className="table-wrap">
          <table className="graf-tabela">
            <thead><tr><th>Estado</th>{anos.map((y) => <th key={y} className="r">{y}</th>)}</tr></thead>
            <tbody>
              {Object.keys(NOME_UF).filter((uf) => anos.some((y) => porAno[y]?.[uf])).sort((x, y) => (porAno[anoV]?.[y] || 0) - (porAno[anoV]?.[x] || 0)).map((uf) => (
                <tr key={uf}><td>{NOME_UF[uf]}</td>{anos.map((y) => <td key={y} className="r num">{porAno[y]?.[uf] ? formato(porAno[y][uf]) : "—"}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/* ------------------------------------------------------------------ anos: botões e animação */

/** Passa pelos anos sozinho, um por segundo e meio, e para no último. */
function useTocar(anos: string[], ano: string, setAno: (a: string) => void) {
  const [tocando, setTocando] = useState(false);
  const ref = useRef<number | null>(null);
  useEffect(() => {
    if (!tocando) return;
    ref.current = window.setTimeout(() => {
      const i = anos.indexOf(ano);
      if (i < 0 || i >= anos.length - 1) { setTocando(false); return; }
      setAno(anos[i + 1]);
    }, 1500);
    return () => { if (ref.current) clearTimeout(ref.current); };
  }, [tocando, ano, anos.join()]); // eslint-disable-line
  return {
    tocando,
    tocar: () => { if (tocando) { setTocando(false); return; } if (anos.indexOf(ano) >= anos.length - 1) setAno(anos[0]); setTocando(true); },
  };
}

function SeletorAnos({ anos, ano, setAno, tocando }: { anos: string[]; ano: string; setAno: (a: string) => void; tocando: { tocando: boolean; tocar: () => void } }) {
  if (anos.length < 2) return null;
  return (
    <div className="row graf-controles">
      <button className="btn alt graf-play" onClick={tocando.tocar} aria-pressed={tocando.tocando}>
        <span aria-hidden="true">{tocando.tocando ? "❚❚" : "▶"}</span> {tocando.tocando ? "Pausar" : "Ver os anos passando"}
      </button>
      <div className="toggle graf-anos" role="group" aria-label="Ano">
        {anos.map((y) => <button key={y} aria-pressed={y === ano} onClick={() => setAno(y)}>{y}</button>)}
      </div>
    </div>
  );
}

/** Compara as mesmas categorias em anos diferentes. "Ano a ano" anima as barras passando pelos anos;
 *  "Dois anos" mostra um ano em cima do outro com a diferença. A escala é a mesma em todos os anos. */
export function CompararAnos({ porAno, titulo, formato = curto, limite = 10, anoInicial, nota }: {
  porAno: Record<string, Fatia[]>; titulo: string; formato?: (v: number) => string; limite?: number; anoInicial?: string; nota?: ReactNode;
}) {
  const anos = Object.keys(porAno).filter((a) => porAno[a]?.some((f) => f.valor > 0)).sort();
  const [modo, setModo] = useState<"dois" | "ano">("dois");
  const [ano0, setAno] = useState(anoInicial || "");
  const ano = anos.includes(ano0) ? ano0 : anoInicial && anos.includes(anoInicial) ? anoInicial : anos[anos.length - 1];
  const [a0, setA] = useState("");
  const [b0, setB] = useState("");
  const a = anos.includes(a0) ? a0 : anos[Math.max(0, anos.length - 2)];
  const b = anos.includes(b0) ? b0 : anos[anos.length - 1];
  const tocando = useTocar(anos, ano, setAno);
  // Ordem e cor fixas: pela soma de todos os anos. Assim nada troca de lugar nem de cor durante a animação.
  const nomes = useMemo(() => {
    const s = new Map<string, number>();
    anos.forEach((y) => porAno[y].forEach((f) => s.set(f.nome, (s.get(f.nome) || 0) + f.valor)));
    return [...s.entries()].sort((x, y) => y[1] - x[1]).map(([n]) => n);
  }, [porAno, anos.join()]); // eslint-disable-line
  if (anos.length < 2) return null;
  const val = (y: string, n: string) => porAno[y]?.find((f) => f.nome === n)?.valor || 0;
  const cor = (n: string) => { const i = nomes.indexOf(n); return anos.map((y) => porAno[y]?.find((f) => f.nome === n)?.cor).find(Boolean) || (i < PALETA.length ? PALETA[i] : COR_OUTROS); };
  const mostrar = (modo === "dois" ? nomes.slice().sort((x, y) => Math.max(val(b, y), val(a, y)) - Math.max(val(b, x), val(a, x))) : nomes).slice(0, limite);
  const max = Math.max(1, ...anos.flatMap((y) => mostrar.map((n) => val(y, n))));
  const tA = porAno[a]?.reduce((s, f) => s + f.valor, 0) || 0, tB = porAno[b]?.reduce((s, f) => s + f.valor, 0) || 0;
  const anoV = anos.includes(ano) ? ano : anos[anos.length - 1];
  return (
    <div className="comparar">
      <h3 className="graf-titulo">{titulo}</h3>
      <div className="row graf-controles">
        <div className="toggle" role="group" aria-label="Como comparar">
          <button aria-pressed={modo === "dois"} onClick={() => setModo("dois")}>Dois anos</button>
          <button aria-pressed={modo === "ano"} onClick={() => setModo("ano")}>Ano a ano</button>
        </div>
        {modo === "dois" && (
          <>
            <label className="graf-ano"><span className="muted small">De</span><select value={a} onChange={(e) => setA(e.target.value)}>{anos.map((y) => <option key={y}>{y}</option>)}</select></label>
            <label className="graf-ano"><span className="muted small">para</span><select value={b} onChange={(e) => setB(e.target.value)}>{anos.map((y) => <option key={y}>{y}</option>)}</select></label>
          </>
        )}
      </div>
      {modo === "ano" && <SeletorAnos anos={anos} ano={anoV} setAno={setAno} tocando={tocando} />}
      {modo === "dois" ? (
        <>
          <div className="comparar-leg small"><span><i className="claro" />{a} · {formato(tA)}</span><span><i />{b} · {formato(tB)}</span><Variacao de={tA} para={tB} rotulo={a} /></div>
          <div className="comparar-linhas">
            {mostrar.map((n) => (
              <div key={n} className="comparar-linha">
                <div className="comparar-nome"><span>{n}</span><Variacao de={val(a, n)} para={val(b, n)} /></div>
                <div className="comparar-barras" role="img" aria-label={`${n}: ${formato(val(a, n))} em ${a}, ${formato(val(b, n))} em ${b}`}>
                  <div className="comparar-barra claro"><span style={{ width: `${(val(a, n) / max) * 100}%`, background: cor(n) }} /><em className="num">{formato(val(a, n))}</em></div>
                  <div className="comparar-barra"><span style={{ width: `${(val(b, n) / max) * 100}%`, background: cor(n) }} /><em className="num">{formato(val(b, n))}</em></div>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="comparar-linhas">
          <div className="mapa-ano-grande num" aria-live="polite">{anoV}</div>
          {mostrar.map((n) => (
            <div key={n} className="comparar-linha">
              <div className="comparar-nome"><span>{n}</span>{anos.indexOf(anoV) > 0 && <Variacao de={val(anos[anos.indexOf(anoV) - 1], n)} para={val(anoV, n)} />}</div>
              <div className="comparar-barras"><div className="comparar-barra"><span style={{ width: `${(val(anoV, n) / max) * 100}%`, background: cor(n) }} /><em className="num">{formato(val(anoV, n))}</em></div></div>
            </div>
          ))}
        </div>
      )}
      {nota && <p className="small muted">{nota}</p>}
    </div>
  );
}

/** Colunas, uma por ano, com a animação de passar pelos anos e a variação de cada ano contra o anterior. */
export function ColunasAnos({ serie, titulo, formato = curto, cor = "var(--hot)", parcial, ano, setAno }: {
  serie: [string, number][]; titulo: string; formato?: (v: number) => string; cor?: string; parcial?: Set<string>; ano?: string; setAno?: (a: string) => void;
}) {
  const tip = useTip();
  const max = Math.max(1, ...serie.map(([, v]) => v));
  return (
    <div className="colunas-anos" role="img" aria-label={`${titulo}: ${serie.map(([a, v]) => `${a}: ${formato(v)}`).join("; ")}`}>
      {serie.map(([a, v], i) => (
        <button key={a} type="button" className={`coluna-ano ${ano === a ? "ativa" : ""}`} onClick={() => setAno?.(a)} disabled={!setAno}
          onMouseMove={(e) => tip.show(e, `${a}${parcial?.has(a) ? " (ano ainda em andamento)" : ""}: ${formato(v)}`)} onMouseLeave={tip.hide}>
          <span className="coluna-valor num">{formato(v)}</span>
          {i > 0 ? <Variacao de={serie[i - 1][1]} para={v} /> : <span className="variacao igual">&nbsp;</span>}
          <span className="coluna-trilho"><span className="coluna-barra" style={{ height: `${(v / max) * 100}%`, background: cor, opacity: parcial?.has(a) ? 0.5 : 1 }} /></span>
          <span className="coluna-rot">{a}{parcial?.has(a) ? "*" : ""}</span>
        </button>
      ))}
      {tip.el}
    </div>
  );
}
