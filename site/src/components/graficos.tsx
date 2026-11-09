/* Gráficos do site: barra de partes de um todo (no lugar da antiga rosca) com uma lista, mapa do Brasil por estado, comparação entre anos com
   animação e números grandes com a variação contra o ano anterior. Tudo em SVG, sem bibliotecas: o site continua
   leve no celular e funciona sem internet depois de aberto.
   Cores: as do site (styles.css), na mesma ordem em todos os gráficos. A paleta passou no validador de cores
   (daltonismo e contraste) no claro e no escuro; onde o contraste é menor, a lista ao lado traz o nome e o valor. */
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
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

/** O pedaço em destaque, dividido entre a barra das partes e a lista embaixo (ComRosca).
 *  Passar o mouse mostra o pedaço; clicar (na barra ou na linha) fixa até clicar de novo. A linha em destaque ganha
 *  fundo e a cor do pedaço; as outras ficam apagadas. Use `linha(dono, cor)` em cada linha da lista e `classe(dono)` no
 *  className dela: assim todas as listas do site se comportam igual. */
export interface Realce {
  foco: string | null; fixo: string | null;
  marca: (nome: string | null) => void; fixa: (nome: string) => void;
  classe: (dono: string | null | undefined) => string;
  linha: (dono: string, cor?: string) => { "data-fatia": string; style?: CSSProperties; onMouseEnter: () => void; onMouseLeave: () => void; onClick: () => void };
}
export function useRealce(): Realce {
  const [sobre, setSobre] = useState<string | null>(null);
  const [fixo, setFixo] = useState<string | null>(null);
  const foco = sobre ?? fixo;
  // Ao fixar, esquece o "mouse em cima": no celular o toque também conta como mouse em cima e nunca sai.
  const fixa = (n: string) => { setFixo(fixo === n ? null : n); setSobre(null); };
  return {
    foco, fixo, marca: setSobre, fixa,
    classe: (dono) => (!foco || !dono ? "" : foco === dono ? "realce" : "apagado"),
    linha: (dono, cor) => ({ "data-fatia": dono, style: cor ? ({ "--cor-fatia": cor } as CSSProperties) : undefined,
      onMouseEnter: () => setSobre(dono), onMouseLeave: () => setSobre(null), onClick: () => fixa(dono) }),
  };
}

/** Partes de um todo: uma barra única dividida em pedaços (do maior para o menor), com o número grande em cima e a
 *  lista de cores embaixo. Substitui a antiga rosca (pizza): comparar comprimentos numa linha é mais fácil que comparar
 *  ângulos, os nomes não ficam espremidos e nada se sobrepõe em tela pequena.
 *  Passar o mouse (ou o teclado) mostra o pedaço; clicar fixa o pedaço até clicar de novo.
 *  realce: quando há uma lista fora do gráfico (ComRosca), o destaque é dividido com ela.
 *  O nome Rosca ficou para não mudar as páginas que já usam o gráfico. */
export function Rosca({ fatias, titulo, formato = curto, centro, centroRotulo = "Total", realce, legenda = true }: {
  fatias: FatiaPronta[]; titulo: string; formato?: (v: number) => string; centro?: string; centroRotulo?: string;
  realce?: Realce; legenda?: boolean;
}) {
  const [aberto, setAberto] = useState(poucoMovimento());
  const proprio = useRealce();
  const r = realce ?? proprio;
  useEffect(() => { const t = requestAnimationFrame(() => setAberto(true)); return () => cancelAnimationFrame(t); }, []);
  const total = fatias.reduce((a, f) => a + f.valor, 0);
  if (!total) return null;
  const { foco, fixo, marca, fixa } = r;
  const atual = fatias.find((f) => f.nome === foco);
  const pctTxt = (p: number) => (p < 0.01 ? "<1%" : porcento(p, p < 0.1 ? 1 : 0));
  return (
    <figure className="compo">
      <div className="compo-topo" aria-live="polite">
        <span className="compo-rot">{atual ? atual.nome : centroRotulo}</span>
        <span className="compo-num num">{atual ? formato(atual.valor) : centro ?? formato(total)}</span>
        {atual && <span className="compo-pct num">{`${pctTxt(atual.pct)} do total`}</span>}
      </div>
      <div className="compo-barra" role="group" aria-label={`${titulo}. ${fatias.map((f) => `${f.nome}: ${formato(f.valor)}, ${porcento(f.pct)}`).join("; ")}`}>
        {fatias.map((f) => (
          <button key={f.nome} type="button" data-nome={f.nome} className={`compo-seg ${foco && foco !== f.nome ? "apagado" : ""} ${fixo === f.nome ? "fixo" : ""}`}
            style={{ width: aberto ? `${f.pct * 100}%` : 0, background: f.cor }} aria-pressed={fixo === f.nome}
            aria-label={`${f.nome}: ${formato(f.valor)}, ${porcento(f.pct)}`} title={`${f.nome}: ${formato(f.valor)} (${porcento(f.pct)})`}
            onMouseEnter={() => marca(f.nome)} onMouseLeave={() => marca(null)} onFocus={() => marca(f.nome)} onBlur={() => marca(null)} onClick={() => fixa(f.nome)}>
            {f.pct >= 0.07 && <span className="num">{porcento(f.pct, 0)}</span>}
          </button>
        ))}
      </div>
      {legenda && (
        <ul className="compo-leg">
          {fatias.map((f) => (
            <li key={f.nome}>
              <button type="button" className={foco && foco !== f.nome ? "apagado" : ""} aria-pressed={fixo === f.nome}
                onMouseEnter={() => marca(f.nome)} onMouseLeave={() => marca(null)} onClick={() => fixa(f.nome)}>
                <i style={{ background: f.cor }} /><span className="compo-nome">{f.nome}</span>
                <span className="num compo-val">{formato(f.valor)}</span><b className="num">{pctTxt(f.pct)}</b>
              </button>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}

/** A barra das partes em cima e a lista embaixo. A lista deve vir na mesma ordem das fatias (do maior para o menor),
 *  com a cor de cada fatia, e ligar cada linha ao realce (`realce.linha` e `realce.classe`). Clicar num pedaço destaca
 *  a linha e, se ela estiver fora da tela, rola até ela. */
export function ComRosca({ fatias, titulo, formato, centro, centroRotulo, children, realce }: {
  fatias: FatiaPronta[]; titulo: string; formato?: (v: number) => string; centro?: string; centroRotulo?: string; children: ReactNode;
  realce: Realce;
}) {
  const lista = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!realce.fixo || !lista.current) return;
    const el = lista.current.querySelector(`[data-fatia="${CSS.escape(realce.fixo)}"]`);
    el?.scrollIntoView?.({ block: "nearest", behavior: poucoMovimento() ? "auto" : "smooth" });
  }, [realce.fixo]);
  return (
    <div className="caixa-graf com-rosca">
      <Rosca fatias={fatias} titulo={titulo} formato={formato} centro={centro} centroRotulo={centroRotulo} realce={realce} legenda={false} />
      <div className="com-rosca-lista" ref={lista}>{children}</div>
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

/** Cortes da escala do mapa: 5 degraus com o mesmo número de estados em cada um (quintis de todos os valores de todos
 *  os anos). Com degraus fixos, a diferença entre estados e entre anos fica visível; com um degradê contínuo quase todos
 *  os estados saíam do mesmo azul. */
export function quebrasMapa(valores: number[]): number[] {
  const v = valores.filter((x) => x > 0 && isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return [];
  const q = [0.2, 0.4, 0.6, 0.8].map((p) => v[Math.min(v.length - 1, Math.floor(p * v.length))]);
  return [...new Set(q)];
}
const DEGRAU = ["var(--q1)", "var(--q2)", "var(--q3)", "var(--q4)", "var(--q5)"];

/** Cor de cada estado. Valor: 5 degraus de um tom só, do claro ao escuro. Mudança: laranja sobe, azul desce, cinza no meio. */
function corMapa(v: number | undefined, max: number, divergente: boolean, quebras: number[]): string {
  if (v == null || !isFinite(v)) return "var(--grid)";
  if (divergente) {
    const t = Math.min(1, Math.abs(v) / (max || 1));
    if (t < 0.02) return "var(--centro)";
    return `color-mix(in oklab, ${v > 0 ? "var(--s2)" : "var(--s1)"} ${Math.round(25 + 75 * t)}%, var(--centro))`;
  }
  if (!v) return "var(--grid)";
  const i = quebras.filter((q) => v >= q).length;
  return DEGRAU[Math.round((i * 4) / Math.max(1, quebras.length))];
}

export function MapaUF({ valores, max, titulo, formato = curto, divergente = false, onUf, ufAtiva, rotuloValor, quebras }: {
  valores: Record<string, number>; max?: number; titulo: string; formato?: (v: number) => string; divergente?: boolean;
  onUf?: (uf: string) => void; ufAtiva?: string; rotuloValor?: (uf: string) => string;
  /** cortes dos degraus de cor; os mapas de anos diferentes usam os mesmos, para comparar de verdade */
  quebras?: number[];
}) {
  const d = useDesenho();
  const tip = useTip();
  const m = max ?? Math.max(0, ...Object.values(valores).map((v) => Math.abs(v)));
  const q = useMemo(() => quebras ?? quebrasMapa(Object.values(valores)), [quebras, valores]);
  const texto = (uf: string) => rotuloValor ? rotuloValor(uf) : `${NOME_UF[uf] || uf}: ${valores[uf] == null ? "sem dado" : formato(valores[uf])}`;
  if (!d) return <div className="mapa-uf mapa-vazio" aria-hidden="true" />;
  return (
    <div className="mapa-uf">
      <svg viewBox={d.vb} role="group" aria-label={titulo}>
        {Object.entries(d.p).map(([uf, path]) => (
          <path key={uf} d={path} fill={corMapa(valores[uf], m, divergente, q)} className={`${ufAtiva === uf ? "ativa" : ""} ${onUf ? "clicavel" : ""}`}
            role={onUf ? "button" : "img"} tabIndex={0} aria-label={texto(uf)}
            onMouseMove={(e) => tip.show(e, texto(uf))} onMouseLeave={tip.hide}
            onClick={() => onUf?.(uf)} onKeyDown={(e) => { if (onUf && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onUf(uf); } }} />
        ))}
      </svg>
      {tip.el}
    </div>
  );
}

function LegendaMapa({ max, formato, divergente, quebras = [] }: { max: number; formato: (v: number) => string; divergente?: boolean; quebras?: number[] }) {
  if (divergente) return (
    <div className="mapa-leg" aria-hidden="true">
      <span>Caiu {formato(max)}</span><i className="div" /><span>Subiu {formato(max)}</span>
    </div>
  );
  const faixas = quebras.length ? [`até ${formato(quebras[0])}`, ...quebras.slice(1).map((q, i) => `${formato(quebras[i])} a ${formato(q)}`), `mais de ${formato(quebras[quebras.length - 1])}`] : [`até ${formato(max)}`];
  return (
    <ul className="mapa-degraus" aria-label="Legenda do mapa">
      {faixas.map((f, i) => <li key={f}><i style={{ background: DEGRAU[Math.round((i * 4) / Math.max(1, faixas.length - 1))] }} />{f}</li>)}
    </ul>
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
  const quebras = quebrasMapa(anos.flatMap((x) => Object.entries(porAno[x]).filter(([uf]) => NOME_UF[uf]).map(([, v]) => v)));
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
              <MapaUF valores={atual} max={max} quebras={quebras} titulo={`${titulo} em ${anoV}`} formato={formato} onUf={onUf} ufAtiva={ufAtiva} />
              <LegendaMapa max={max} formato={formato} quebras={quebras} />
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
      {modo === "lado" && (() => {
        const soma = (y: string) => Object.entries(porAno[y] || {}).filter(([uf]) => NOME_UF[uf]).reduce((t, [, v]) => t + v, 0);
        const pctDe = (de?: number, para?: number) => (de && para != null ? para / de - 1 : null);
        const linhas = Object.keys(NOME_UF).filter((uf) => porAno[a]?.[uf] || porAno[b]?.[uf])
          .map((uf) => ({ uf, va: porAno[a]?.[uf] || 0, vb: porAno[b]?.[uf] || 0, p: pctDe(porAno[a]?.[uf], porAno[b]?.[uf] || 0) }))
          .sort((x, y) => (y.p ?? -Infinity) - (x.p ?? -Infinity));
        const maxP = Math.max(0.01, ...linhas.map((l) => Math.abs(l.p ?? 0)));
        return (
          <>
            <div className="mapa-lado">
              {[[a, setA, b], [b, setB, a]].map(([x, set, outro], i) => (
                <div key={i}>
                  <label className="graf-ano"><span className="muted small">{i ? "Comparar com" : "Ano"}</span>
                    <select value={x as string} onChange={(e) => (set as (v: string) => void)(e.target.value)}>{anos.map((y) => <option key={y}>{y}</option>)}</select>
                  </label>
                  <div className="mapa-lado-total"><span className="num">{formato(soma(x as string) / Math.max(1, Object.keys(porAno[x as string] || {}).length))}</span> <span className="muted small">média dos estados</span>
                    {i === 1 && <> <Variacao de={soma(a)} para={soma(b)} rotulo={a} /></>}</div>
                  <MapaUF valores={porAno[x as string] || {}} max={max} quebras={quebras} titulo={`${titulo} em ${x}`} formato={formato} onUf={onUf} ufAtiva={ufAtiva}
                    rotuloValor={(uf) => {
                      const v = porAno[x as string]?.[uf], o = porAno[outro as string]?.[uf];
                      const p = i ? pctDe(o, v) : pctDe(v, o);
                      return `${NOME_UF[uf] || uf}: ${v == null ? "sem dado" : formato(v)} em ${x}${p != null ? ` (${i ? "" : `${outro}: `}${p > 0 ? "+" : p < 0 ? "−" : ""}${porcento(Math.abs(p), 0)}${i ? ` contra ${outro}` : ""})` : ""}`;
                    }} />
                </div>
              ))}
              <div style={{ gridColumn: "1 / -1" }}><LegendaMapa max={max} formato={formato} quebras={quebras} /></div>
            </div>
            <h4 className="graf-titulo">Quanto mudou em cada estado, de {a} para {b}</h4>
            <ol className="mapa-mudanca">
              {linhas.map((l) => (
                <li key={l.uf} className={ufAtiva === l.uf ? "ativa" : ""}>
                  {onUf ? <button className="link" onClick={() => onUf(l.uf)}>{NOME_UF[l.uf]}</button> : <span>{NOME_UF[l.uf]}</span>}
                  <span className="num small muted">{formato(l.va)} → {formato(l.vb)}</span>
                  <span className="mapa-mudanca-barra" aria-hidden="true">
                    {l.p != null && <i className={l.p >= 0 ? "sobe" : "desce"} style={{ width: `${(Math.abs(l.p) / maxP) * 50}%` }} />}
                  </span>
                  <strong className={`num ${l.p == null ? "muted" : l.p >= 0 ? "sobe" : "desce"}`}>{l.p == null ? "novo" : `${l.p > 0 ? "+" : l.p < 0 ? "−" : ""}${porcento(Math.abs(l.p), 0)}`}</strong>
                </li>
              ))}
            </ol>
          </>
        );
      })()}
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

/** Colunas, uma por ano, com a animação de passar pelos anos e a variação de cada ano contra o anterior.
 * Valor `null` é ano sem dado na fonte: a coluna mostra "sem dado" e não entra na variação (nunca vira zero). */
export function ColunasAnos({ serie, titulo, formato = curto, cor = "var(--hot)", parcial, ano, setAno }: {
  serie: [string, number | null][]; titulo: string; formato?: (v: number) => string; cor?: string; parcial?: Set<string>; ano?: string; setAno?: (a: string) => void;
}) {
  const tip = useTip();
  const max = Math.max(1, ...serie.map(([, v]) => v ?? 0));
  const txt = (v: number | null) => (v == null ? "sem dado" : formato(v));
  return (
    <div className="colunas-anos" role="img" aria-label={`${titulo}: ${serie.map(([a, v]) => `${a}: ${txt(v)}`).join("; ")}`}>
      {serie.map(([a, v], i) => (
        <button key={a} type="button" className={`coluna-ano ${ano === a ? "ativa" : ""} ${v == null ? "sem-dado" : ""}`} onClick={() => setAno?.(a)} disabled={!setAno}
          aria-pressed={setAno ? ano === a : undefined}
          onMouseMove={(e) => tip.show(e, `${a}${parcial?.has(a) ? " (ano ainda em andamento)" : ""}: ${txt(v)}`)} onMouseLeave={tip.hide}>
          <span className="coluna-valor num">{txt(v)}</span>
          {/* A variação fica sempre num espaço próprio: sem ela (ano anterior zerado ou sem dado), a coluna não sobe */}
          <span className="coluna-var">{i > 0 ? <Variacao de={serie[i - 1][1]} para={v} /> : null}</span>
          <span className="coluna-trilho">{v != null && <span className="coluna-barra" style={{ height: `${(v / max) * 100}%`, background: cor, opacity: parcial?.has(a) ? 0.5 : 1 }} />}</span>
          <span className="coluna-rot">{a}{parcial?.has(a) ? "*" : ""}</span>
        </button>
      ))}
      {tip.el}
    </div>
  );
}
