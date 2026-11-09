import { dataBR } from "../data";

const MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const SEMANA = ["D", "S", "T", "Q", "Q", "S", "S"];
export const diaISO = (a: number, m: number, d: number) => `${a}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

/** Como pintar um dia: classe CSS (cor) e texto da dica. Dia sem marca fica cinza e não é clicável. */
export interface MarcaDia { classe: string; titulo: string }

/** Os 12 meses de um ano, dia a dia. Usado nas viagens do governo de MG e no dia a dia de cada parlamentar. */
export function CalendarioAno({ ano, marcas, sel, onSel, rotulo }: {
  ano: number; marcas: Map<string, MarcaDia>; sel: string | null; onSel: (d: string | null) => void; rotulo: string;
}) {
  const hoje = new Date().toISOString().slice(0, 10);
  return (
    <div className="calendario" aria-label={rotulo}>
      {MESES.map((nome, m) => {
        const primeiro = new Date(Date.UTC(ano, m, 1)).getUTCDay();
        const n = new Date(Date.UTC(ano, m + 1, 0)).getUTCDate();
        return (
          <div key={m} className="cal-mes">
            <div className="cal-nome">{nome}</div>
            <div className="cal-dias">
              {SEMANA.map((s, i) => <span key={`s${i}`} className="cal-sem" aria-hidden="true">{s}</span>)}
              {Array.from({ length: primeiro }, (_, i) => <span key={`v${i}`} />)}
              {Array.from({ length: n }, (_, i) => {
                const d = diaISO(ano, m, i + 1);
                const mk = marcas.get(d);
                return mk
                  ? <button key={d} className={`cal-dia ${mk.classe}${sel === d ? " sel" : ""}`} title={mk.titulo} aria-label={mk.titulo}
                      aria-pressed={sel === d} onClick={() => onSel(sel === d ? null : d)}>{i + 1}</button>
                  : <span key={d} className={`cal-dia${d > hoje ? " futuro" : ""}`} title={dataBR(d)}>{i + 1}</span>;
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
