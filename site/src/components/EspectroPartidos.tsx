/* Partidos espalhados na régua da esquerda para a direita, pelos votos das bancadas.
   Em cima, cada partido é uma bolha no ponto exato da régua (tamanho = número de parlamentares). Embaixo, a tabela em
   cinco colunas, uma por lado, alinhadas com a régua. Cada lado ocupa a mesma largura, para a tabela caber; dentro de
   cada lado, a posição é proporcional (os cortes são os de partidos.ts e de etl/sa_etl/ideologia.py). */
import { Link } from "react-router-dom";
import { corPartido, type Partido } from "../data";
import { COR_LADO, LADOS, ladoPelosVotos } from "../partidos";
import { useTip } from "./ui";

const CORTES = [-1, -0.5, -0.15, 0.15, 0.5, 1];

/** Posição na régua (0 a 100%): cada um dos cinco lados ocupa 20% */
export function xRegua(pos: number): number {
  const p = Math.max(-1, Math.min(1, pos));
  const i = Math.min(4, CORTES.findIndex((c, k) => k > 0 && p <= c) - 1);
  const k = i < 0 ? 0 : i;
  return (k + (p - CORTES[k]) / (CORTES[k + 1] - CORTES[k])) * 20;
}

export function EspectroPartidos({ partidos, rotulo = "dep." }: { partidos: Partido[]; rotulo?: string }) {
  const tip = useTip();
  const com = partidos.filter((p) => p.posicao != null && p.n > 0).sort((a, b) => a.posicao! - b.posicao!);
  const sem = partidos.filter((p) => p.posicao == null && p.n > 0).sort((a, b) => b.n - a.n);
  const maxN = Math.max(1, ...com.map((p) => p.n));
  // Bolhas que ficariam em cima umas das outras sobem para outra faixa
  const faixas: number[] = [];
  const pontos = com.map((p) => {
    const x = xRegua(p.posicao!);
    const r = 5 + 11 * Math.sqrt(p.n / maxN);
    let f = 0;
    while (faixas[f] != null && x - faixas[f] < 4.2) f++;
    faixas[f] = x;
    return { p, x, r, f };
  });
  const nFaixas = Math.max(1, faixas.length);
  const total = com.reduce((a, p) => a + p.n, 0);
  return (
    <div className="esp-partidos">
      <div className="esp-rolar">
        <div className="esp-quadro">
          <div className="esp-bolhas" style={{ height: 24 + nFaixas * 46 }} role="group"
            aria-label={`Partidos da esquerda para a direita: ${com.map((p) => `${p.sigla} (${p.n})`).join(", ")}`}>
            {LADOS.map((l, i) => <span key={l} className="esp-faixa" style={{ left: `${i * 20}%`, background: COR_LADO[l] }} />)}
            <span className="esp-meio" />
            {pontos.map(({ p, x, r, f }) => (
              <Link key={p.sigla} to={`/politicos?partido=${encodeURIComponent(p.sigla)}`} className="esp-bolha"
                style={{ left: `${x}%`, bottom: 6 + f * 46, width: r * 2, height: r * 2, marginLeft: -r, background: corPartido(p.sigla) }}
                aria-label={`${p.sigla}: ${p.n} ${rotulo}, ${ladoPelosVotos(p.posicao!)}`}
                onMouseMove={(e) => tip.show(e, `${p.sigla}: ${p.n} ${rotulo} · ${ladoPelosVotos(p.posicao!)} (posição ${p.posicao!.toLocaleString("pt-BR", { maximumFractionDigits: 2 })})`)}
                onMouseLeave={tip.hide}>
                <span className="esp-sigla">{p.sigla}</span>
              </Link>
            ))}
          </div>
          <div className="esp-tabela">
            {LADOS.map((l) => {
              const ps = com.filter((p) => ladoPelosVotos(p.posicao!) === l);
              const n = ps.reduce((a, p) => a + p.n, 0);
              return (
                <div key={l} className="esp-col">
                  <h3 style={{ borderTopColor: COR_LADO[l] }}>{l}<small>{`${n} ${rotulo}${total ? ` · ${Math.round((n / total) * 100)}%` : ""}`}</small></h3>
                  {ps.length ? (
                    <ul>
                      {ps.map((p) => (
                        <li key={p.sigla}>
                          <Link to={`/politicos?partido=${encodeURIComponent(p.sigla)}`}><i className="partido-cor" style={{ background: corPartido(p.sigla) }} /><strong>{p.sigla}</strong></Link>
                          <small className="num">{p.n}</small>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="small muted">Nenhum partido</p>}
                </div>
              );
            })}
          </div>
          <div className="spectrum-labels"><span>◀ Mais à esquerda</span><span>Centro</span><span>Mais à direita ▶</span></div>
        </div>
      </div>
      {sem.length > 0 && (
        <p className="small muted">Sem votos suficientes para ter posição: {sem.map((p, i) => <span key={p.sigla}>{i ? ", " : ""}<Link to={`/politicos?partido=${encodeURIComponent(p.sigla)}`}>{p.sigla}</Link> ({p.n})</span>)}.</p>
      )}
      {tip.el}
    </div>
  );
}
