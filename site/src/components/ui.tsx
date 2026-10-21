import { useEffect, useState, type ReactNode } from "react";
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

/* Colunas de gasto por mês */
export function GastoMensal({ meses }: { meses: { ano: number; mes: number; valor: number }[] }) {
  const tip = useTip();
  if (!meses.length) return <div className="empty">Sem gastos registrados no período.</div>;
  const W = 640, H = 200, padL = 52, padB = 24, padT = 8;
  const max = Math.max(...meses.map((m) => m.valor));
  const passo = niceStep(max);
  const topo = Math.ceil(max / passo) * passo || 1;
  const bw = (W - padL) / meses.length;
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / topo);
  const ticks = Array.from({ length: Math.round(topo / passo) + 1 }, (_, i) => i * passo);
  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Gasto por mês">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={padL - 6} y={y(t) + 4} textAnchor="end">{t >= 1000 ? `${Math.round(t / 1000)} mil` : t}</text>
          </g>
        ))}
        {meses.map((m, i) => {
          const h = Math.max(0, y(0) - y(m.valor));
          const x = padL + i * bw + 1;
          return (
            <g key={i}>
              <rect x={x} y={y(m.valor)} width={Math.max(1, bw - 2)} height={h} rx={Math.min(4, bw / 3)} fill="var(--s1)"
                onMouseMove={(e) => tip.show(e, `${MESES[m.mes - 1]}/${m.ano}: ${reais(m.valor)}`)} onMouseLeave={tip.hide} />
              {m.mes === 1 || i === 0 ? <text x={x} y={H - 6}>{`${MESES[m.mes - 1]}/${String(m.ano).slice(2)}`}</text> : null}
            </g>
          );
        })}
        <line x1={padL} x2={W} y1={y(0)} y2={y(0)} stroke="var(--muted)" />
      </svg>
      {tip.el}
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
export function Espectro({ pontos, destaque, rotulos }: { pontos: { id: string; pos: number; label: string; href?: string }[]; destaque?: string; rotulos?: boolean }) {
  const tip = useTip();
  const cor = (p: number) => (p < -0.15 ? "var(--esq)" : p > 0.15 ? "var(--dir)" : "var(--centro)");
  return (
    <div>
      <div className={`spectrum ${rotulos ? "labeled" : ""}`} role="img" aria-label="Posição de esquerda a direita">
        {rotulos && pontos.slice().sort((a, b) => a.pos - b.pos).map((p, i) => (
          <span key={`t-${p.id}`} className="tag" style={{ left: `clamp(16px, ${((p.pos + 1) / 2) * 100}%, calc(100% - 16px))`, top: i % 2 ? 54 : 4 }}>{p.id}</span>
        ))}
        {pontos.map((p, i) => {
          const left = `${((p.pos + 1) / 2) * 100}%`;
          const jitter = destaque === p.id || rotulos ? 0 : ((i * 37) % 30) - 15;
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
