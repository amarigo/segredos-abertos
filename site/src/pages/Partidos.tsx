import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useAno, useData, useTip } from "../components/ui";
import { casaNome, reais, reaisCurto, type Casa, type Partido } from "../data";

type Medida = "total" | "membro";
type Base = "cota" | "custo";

/* Ranking de gasto por partido, com o total e o valor por parlamentar (proporcional ao tamanho da bancada) */
export function GastoPartidos({ partidos, ano, limite }: { partidos: Partido[]; ano: string; limite?: number }) {
  const [medida, setMedida] = useState<Medida>("membro");
  const [base, setBase] = useState<Base>("cota");
  const [casa, setCasa] = useState<Casa>("camara");
  const linhas = useMemo(() => partidos
    .filter((p) => p.casa === casa && p.por_ano?.[ano])
    .map((p) => {
      const a = p.por_ano[ano];
      const total = base === "cota" ? a.cota : a.custo_total;
      return { sigla: p.sigla, n: a.n, total, membro: total / a.n };
    })
    .filter((x) => x.total > 0)
    .sort((a, b) => (medida === "total" ? b.total - a.total : b.membro - a.membro)), [partidos, ano, base, casa, medida]);
  const mostrar = limite ? linhas.slice(0, limite) : linhas;
  // A cor segue o partido (pela ordem do gasto em todos os anos), não a posição no ano escolhido
  const corDe = useMemo(() => {
    const ordem = partidos.filter((p) => p.casa === casa).sort((a, b) => b.total - a.total).slice(0, CORES.length).map((p) => p.sigla);
    return (sigla: string) => { const i = ordem.indexOf(sigla); return i >= 0 ? CORES[i] : "var(--c-outros)"; };
  }, [partidos, casa]);
  return (
    <section>
      <h2>Gasto por partido em {ano}</h2>
      <Explain>O <strong>total</strong> mostra quanto a bancada inteira gastou. O valor <strong>por parlamentar</strong> divide esse total pelo número de membros, para comparar partidos grandes e pequenos de forma justa.</Explain>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <div className="toggle" role="group" aria-label="Casa">
          {(["camara", "senado"] as Casa[]).map((c) => <button key={c} aria-pressed={casa === c} onClick={() => setCasa(c)}>{casaNome(c)}</button>)}
        </div>
        <div className="toggle" role="group" aria-label="Medida">
          <button aria-pressed={medida === "membro"} onClick={() => setMedida("membro")}>Por parlamentar</button>
          <button aria-pressed={medida === "total"} onClick={() => setMedida("total")}>Total</button>
        </div>
        <div className="toggle" role="group" aria-label="O que somar">
          <button aria-pressed={base === "cota"} onClick={() => setBase("cota")}>Só a cota</button>
          <button aria-pressed={base === "custo"} onClick={() => setBase("custo")}>Cota, salário e equipe</button>
        </div>
      </div>
      <Pizza fatias={linhas.map((x) => ({ sigla: x.sigla, valor: x.total, cor: corDe(x.sigla) }))} titulo={`${base === "cota" ? "Cota" : "Custo total"} por partido na ${casaNome(casa)} em ${ano}`} />
      <h3>{medida === "total" ? "Total por partido" : "Por parlamentar"}</h3>
      <Barras itens={mostrar.map((x) => ({
        label: <Link to={`/politicos?partido=${encodeURIComponent(x.sigla)}`}><strong>{x.sigla}</strong></Link>,
        nota: medida === "total" ? `${x.n} parlamentar${x.n > 1 ? "es" : ""} · ${reais(x.membro)} por parlamentar` : `${x.n} parlamentar${x.n > 1 ? "es" : ""} · ${reais(x.total)} no total`,
        valor: medida === "total" ? x.total : x.membro,
        cor: "var(--s1)",
      }))} />
      {limite && linhas.length > limite && <Link to="/partidos">Ver todos os {linhas.length} partidos</Link>}
    </section>
  );
}

const CORES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--c4)", "var(--c5)", "var(--c6)", "var(--c7)"];

/* Pizza (rosca) com o total de cada partido; partidos sem cor própria entram em "Outros" */
function Pizza({ fatias, titulo }: { fatias: { sigla: string; valor: number; cor: string }[]; titulo: string }) {
  const tip = useTip();
  const proprias = fatias.filter((f) => f.cor !== "var(--c-outros)").sort((a, b) => b.valor - a.valor);
  const resto = fatias.filter((f) => f.cor === "var(--c-outros)");
  const itens = [...proprias, ...(resto.length ? [{ sigla: `Outros (${resto.length})`, valor: resto.reduce((a, f) => a + f.valor, 0), cor: "var(--c-outros)" }] : [])];
  const total = itens.reduce((a, f) => a + f.valor, 0);
  if (!total) return null;
  const R = 100, r = 58;
  let ang = -Math.PI / 2;
  const arcos = itens.map((f) => {
    const a0 = ang, a1 = ang + (f.valor / total) * Math.PI * 2;
    ang = a1;
    const grande = a1 - a0 > Math.PI ? 1 : 0;
    const p = (rad: number, raio: number) => `${(R + raio * Math.cos(rad)).toFixed(2)} ${(R + raio * Math.sin(rad)).toFixed(2)}`;
    const d = itens.length === 1
      ? `M ${p(0, R)} A ${R} ${R} 0 1 1 ${p(Math.PI, R)} A ${R} ${R} 0 1 1 ${p(0, R)} M ${p(0, r)} A ${r} ${r} 0 1 0 ${p(Math.PI, r)} A ${r} ${r} 0 1 0 ${p(0, r)} Z`
      : `M ${p(a0, R)} A ${R} ${R} 0 ${grande} 1 ${p(a1, R)} L ${p(a1, r)} A ${r} ${r} 0 ${grande} 0 ${p(a0, r)} Z`;
    return { ...f, d };
  });
  const pct = (v: number) => `${((v / total) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  return (
    <figure className="pizza" style={{ margin: 0 }}>
      <svg viewBox="0 0 200 200" width="100%" role="img" aria-label={titulo}>
        {arcos.map((f) => (
          <path key={f.sigla} d={f.d} fill={f.cor} stroke="var(--surface)" strokeWidth={2} fillRule="evenodd"
            onMouseMove={(e) => tip.show(e, `${f.sigla}: ${reais(f.valor)} (${pct(f.valor)})`)} onMouseLeave={tip.hide} />
        ))}
        <text x={100} y={96} textAnchor="middle" style={{ fontSize: 11, fill: "var(--muted)" }}>Total</text>
        <text x={100} y={114} textAnchor="middle" style={{ fontSize: 15, fontWeight: 700, fill: "var(--ink)" }}>{reaisCurto(total)}</text>
      </svg>
      <figcaption className="leg">
        {itens.map((f) => (
          <Fragment key={f.sigla}><i style={{ background: f.cor }} /><span>{f.sigla}</span><span className="num muted">{pct(f.valor)}</span><span className="num">{reaisCurto(f.valor)}</span></Fragment>
        ))}
      </figcaption>
      {tip.el}
    </figure>
  );
}

export default function Partidos() {
  const { data, error } = useData<Partido[]>("partidos.json");
  const { ano } = useAno();
  if (!data) return <Loading error={error} />;
  return (
    <>
      <h1>Partidos</h1>
      <GastoPartidos partidos={data} ano={ano} />
      <p className="muted small">Conta cada parlamentar no partido atual. Quem mudou de partido aparece no partido de hoje, com todos os gastos do ano.</p>
    </>
  );
}
