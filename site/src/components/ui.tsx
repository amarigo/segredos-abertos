import { Fragment, createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { load, reais, MESES, type Grupo } from "../data";

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

export function Loading({ error }: { error?: string | null }) {
  if (error) return <div className="empty">Não foi possível carregar estes dados. {error}</div>;
  return <div className="empty">Carregando…</div>;
}

export function Explain({ children }: { children: ReactNode }) {
  return <p className="explain">{children}</p>;
}

/* Dica flutuante usada pelos gráficos */
export function useTip() {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const el = tip ? <div className="tip" style={{ left: tip.x + 12, top: tip.y + 12 }}>{tip.text}</div> : null;
  return { el, show: (e: React.MouseEvent, text: string) => setTip({ x: e.clientX, y: e.clientY, text }), hide: () => setTip(null) };
}

export const COR_GRUPO: Record<Grupo, string> = { pessoal: "var(--s1)", escritorio: "var(--s2)", servicos: "var(--s3)" };

/* Barras horizontais com rótulo e valor */
export function Barras({ itens, cor, max }: { itens: { label: ReactNode; valor: number; cor?: string; nota?: string }[]; cor?: string; max?: number }) {
  const m = max ?? Math.max(1, ...itens.map((i) => i.valor));
  return (
    <div className="bars">
      {itens.map((i, k) => (
        <div className="bar-row" key={k}>
          <div style={{ minWidth: 0 }}>{i.label}{i.nota && <div className="muted small">{i.nota}</div>}</div>
          <div className="num">{reais(i.valor)}</div>
          <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(i.valor / m) * 100}%`, background: i.cor || cor || "var(--s1)" }} /></div>
        </div>
      ))}
    </div>
  );
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
    <div style={{ overflowX: "auto" }}>
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

/* Régua esquerda–direita com pontos */
export function Espectro({ pontos, destaque }: { pontos: { id: string; pos: number; label: string; href?: string }[]; destaque?: string }) {
  const tip = useTip();
  const cor = (p: number) => (p < -0.15 ? "var(--esq)" : p > 0.15 ? "var(--dir)" : "var(--centro)");
  return (
    <div>
      <div className="spectrum" role="img" aria-label="Posição de esquerda a direita">
        {pontos.map((p, i) => {
          const left = `${((p.pos + 1) / 2) * 100}%`;
          const jitter = destaque === p.id ? 0 : ((i * 37) % 30) - 15;
          const style = { left, top: `calc(50% + ${jitter}px)`, background: cor(p.pos) };
          const dot = <span className={`dot ${destaque === p.id ? "me" : ""}`} style={style} onMouseMove={(e) => tip.show(e, p.label)} onMouseLeave={tip.hide} />;
          return p.href ? <Link key={p.id} to={p.href} aria-label={p.label}>{dot}</Link> : <span key={p.id}>{dot}</span>;
        })}
      </div>
      <div className="spectrum-labels"><span>◀ Esquerda</span><span>Centro</span><span>Direita ▶</span></div>
      {tip.el}
    </div>
  );
}

/* Uma linha por partido, em ordem da esquerda para a direita: nenhum nome fica por cima de outro */
export function EspectroPartidos({ partidos }: { partidos: { sigla: string; pos: number; n: number; href?: string }[] }) {
  const cor = (p: number) => (p < -0.15 ? "var(--esq)" : p > 0.15 ? "var(--dir)" : "var(--centro)");
  const ordem = partidos.slice().sort((a, b) => a.pos - b.pos);
  return (
    <div className="esp-partidos">
      <ol aria-label="Partidos da esquerda para a direita">
        {ordem.map((p) => (
          <li key={p.sigla}>
            <span className="esp-nome">
              {p.href ? <Link to={p.href}><strong>{p.sigla}</strong></Link> : <strong>{p.sigla}</strong>}
              <small>{p.n} dep.</small>
            </span>
            <span className="esp-trilho" title={`${p.sigla}: posição ${p.pos.toFixed(2)} (de -1 a +1), ${p.n} deputados`}>
              <i style={{ left: `${((p.pos + 1) / 2) * 100}%`, background: cor(p.pos) }} />
            </span>
          </li>
        ))}
        <li className="esp-eixo" aria-hidden="true"><span /><span className="spectrum-labels"><span>◀ Esquerda</span><span>Centro</span><span>Direita ▶</span></span></li>
      </ol>
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
  const cls = voto === "Sim" ? "chip ok" : voto === "Não" ? "chip no" : "chip";
  return <span className={cls}>{voto}</span>;
}
