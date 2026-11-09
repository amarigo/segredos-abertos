/* Desenho da rede em SVG, sem biblioteca: posições por simulação de forças (molas nas ligações, repulsão entre
 * todos os pontos), calculadas de uma vez e sempre iguais para a mesma rede. Dá para arrastar um ponto. */
import { useEffect, useMemo, useRef, useState } from "react";
import { corTipo, nomeTipo, type Ligacao, type Objeto } from "./modelo";

type Pos = Record<string, { x: number; y: number }>;
const L = 1000, A = 720;

/** Posições dos objetos. Sementes fixas (a partir do id), para o desenho não pular a cada visita. */
export function posicionar(objetos: Objeto[], ligacoes: Ligacao[], centro?: string): Pos {
  const n = objetos.length;
  const pos: Pos = {};
  const hash = (s: string) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967296; };
  objetos.forEach((o, i) => {
    const ang = 2 * Math.PI * (i / Math.max(n, 1)) + hash(o.id);
    const r = o.id === centro ? 0 : 150 + 200 * hash(o.id + "r");
    pos[o.id] = { x: L / 2 + r * Math.cos(ang), y: A / 2 + r * Math.sin(ang) };
  });
  // Fruchterman-Reingold: repulsão k²/d entre todos, atração d²/k nas ligações, passo que esfria a cada rodada
  const ids = objetos.map((o) => o.id);
  const k = 0.75 * Math.sqrt((L * A) / Math.max(n, 1));
  const voltas = 300;
  for (let it = 0; it < voltas; it++) {
    const temp = 60 * (1 - it / voltas) + 1;
    const d: Pos = Object.fromEntries(ids.map((id) => [id, { x: 0, y: 0 }]));
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const a = pos[ids[i]], b = pos[ids[j]];
      const dx = a.x - b.x, dy = a.y - b.y;
      const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const f = (k * k) / dist / dist;
      d[ids[i]].x += dx * f; d[ids[i]].y += dy * f; d[ids[j]].x -= dx * f; d[ids[j]].y -= dy * f;
    }
    for (const l of ligacoes) {
      const a = pos[l.de], b = pos[l.para];
      if (!a || !b) continue;
      const dx = b.x - a.x, dy = b.y - a.y, dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
      const f = dist / k;
      d[l.de].x += dx * f; d[l.de].y += dy * f; d[l.para].x -= dx * f; d[l.para].y -= dy * f;
    }
    for (const id of ids) {
      if (id === centro) continue;
      const p = pos[id];
      // Um pouco de gravidade para o meio: pedaços soltos não fogem da tela
      d[id].x += (L / 2 - p.x) * 0.05; d[id].y += (A / 2 - p.y) * 0.05;
      const m = Math.sqrt(d[id].x ** 2 + d[id].y ** 2) || 1;
      p.x += (d[id].x / m) * Math.min(m, temp);
      p.y += (d[id].y / m) * Math.min(m, temp);
      p.x = Math.min(L - 40, Math.max(40, p.x));
      p.y = Math.min(A - 25, Math.max(20, p.y));
    }
  }
  return pos;
}

export function Grafo({ objetos, ligacoes, centro, selecionado, onSelecionar }: {
  objetos: Objeto[]; ligacoes: Ligacao[]; centro?: string; selecionado?: string; onSelecionar: (id: string) => void;
}) {
  const inicial = useMemo(() => posicionar(objetos, ligacoes, centro), [objetos, ligacoes, centro]);
  const [pos, setPos] = useState<Pos>(inicial);
  useEffect(() => setPos(inicial), [inicial]);
  const [sobre, setSobre] = useState<string | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const arrasto = useRef<{ id: string; moveu: boolean } | null>(null);
  const grau = useMemo(() => {
    const g: Record<string, number> = {};
    for (const l of ligacoes) { g[l.de] = (g[l.de] || 0) + 1; g[l.para] = (g[l.para] || 0) + 1; }
    return g;
  }, [ligacoes]);
  const foco = sobre || selecionado;
  const perto = useMemo(() => {
    const s = new Set<string>(foco ? [foco] : []);
    for (const l of ligacoes) { if (l.de === foco) s.add(l.para); if (l.para === foco) s.add(l.de); }
    return s;
  }, [foco, ligacoes]);

  const ponto = (e: React.PointerEvent) => {
    const r = svg.current!.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * L, y: ((e.clientY - r.top) / r.height) * A };
  };
  const mover = (e: React.PointerEvent) => {
    if (!arrasto.current) return;
    arrasto.current.moveu = true;
    const p = ponto(e);
    setPos((v) => ({ ...v, [arrasto.current!.id]: { x: Math.min(L - 10, Math.max(10, p.x)), y: Math.min(A - 10, Math.max(10, p.y)) } }));
  };
  if (!objetos.length) return <div className="empty">Nada para desenhar ainda.</div>;

  return (
    <figure className="rede-grafo">
      <svg ref={svg} viewBox={`0 0 ${L} ${A}`} role="group" aria-label={`Rede com ${objetos.length} objetos e ${ligacoes.length} ligações`}
        onPointerMove={mover} onPointerUp={() => (arrasto.current = null)} onPointerLeave={() => (arrasto.current = null)}>
        {ligacoes.map((l) => {
          const a = pos[l.de], b = pos[l.para];
          if (!a || !b) return null;
          const forte = foco && (l.de === foco || l.para === foco);
          return (
            <line key={l.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={l.manual ? "lig manual" : "lig"}
              strokeOpacity={foco ? (forte ? 0.9 : 0.12) : 0.45} strokeWidth={forte ? 2 : 1}>
              <title>{`${objetos.find((o) => o.id === l.de)?.nome} ${l.tipo} ${objetos.find((o) => o.id === l.para)?.nome}`}</title>
            </line>
          );
        })}
        {objetos.map((o) => {
          const p = pos[o.id];
          if (!p) return null;
          const r = o.id === centro ? 16 : Math.min(14, 6 + Math.sqrt(grau[o.id] || 1) * 1.6);
          const apagado = foco && !perto.has(o.id);
          const rotulo = o.id === centro || o.id === foco || (!!sobre && perto.has(o.id)) || (grau[o.id] || 0) >= 3 || objetos.length <= 25;
          return (
            <g key={o.id} transform={`translate(${p.x},${p.y})`} className="no" opacity={apagado ? 0.25 : 1}
              tabIndex={0} role="button" aria-label={`${nomeTipo(o.tipo)}: ${o.nome}`} aria-pressed={o.id === selecionado}
              onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); arrasto.current = { id: o.id, moveu: false }; }}
              onPointerUp={() => { if (!arrasto.current?.moveu) onSelecionar(o.id); arrasto.current = null; }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelecionar(o.id); } }}
              onMouseEnter={() => setSobre(o.id)} onMouseLeave={() => setSobre(null)}>
              <circle r={r} fill={corTipo(o.tipo)} stroke={o.id === selecionado ? "var(--ink)" : "var(--surface)"} strokeWidth={o.id === selecionado ? 3 : 1.5} />
              {rotulo && <text y={r + 13} textAnchor="middle">{o.nome.length > 34 ? o.nome.slice(0, 32) + "…" : o.nome}</text>}
            </g>
          );
        })}
      </svg>
      <figcaption className="rede-legenda">
        {[...new Set(objetos.map((o) => o.tipo))].map((t) => (
          <span key={t}><i style={{ background: corTipo(t) }} />{nomeTipo(t)}</span>
        ))}
        <span><i className="tracejado" />ligação feita por você</span>
      </figcaption>
    </figure>
  );
}
