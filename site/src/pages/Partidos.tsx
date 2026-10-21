import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useAno, useData } from "../components/ui";
import { casaNome, reais, type Casa, type Partido } from "../data";

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
