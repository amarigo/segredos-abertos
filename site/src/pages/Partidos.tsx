import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, OndeVer, useAno, useData } from "../components/ui";
import { MG } from "../recorte";
import { casaNome, corPartido, reais, reaisCurto, type Casa, type Partido } from "../data";
import { CompararAnos, Rosca, prepararFatias, type Fatia, type FatiaPronta } from "../components/graficos";
import { COR_LADO, LADOS, ladoPelosVotos } from "../partidos";

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
  // Na pizza, os 7 partidos que mais gastaram em todos os anos têm fatia própria; os demais entram em "Outros".
  // A cor é sempre a do partido (PT vermelho, PL azul...), em todos os gráficos.
  const principais = useMemo(() => new Set(partidos.filter((p) => p.casa === casa).sort((a, b) => b.total - a.total).slice(0, 7).map((p) => p.sigla)), [partidos, casa]);
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
      <Pizza fatias={linhas.map((x) => ({ sigla: x.sigla, valor: x.total, cor: corPartido(x.sigla), outros: !principais.has(x.sigla) }))} titulo={`${base === "cota" ? "Cota" : "Custo total"} por partido na ${casaNome(casa)} em ${ano}`} />
      <h3>{medida === "total" ? "Total por partido" : "Por parlamentar"}</h3>
      <Barras itens={mostrar.map((x) => ({
        label: <Link to={`/politicos?partido=${encodeURIComponent(x.sigla)}`}><i className="partido-cor" style={{ background: corPartido(x.sigla) }} /><strong>{x.sigla}</strong></Link>,
        nota: medida === "total" ? `${x.n} parlamentar${x.n > 1 ? "es" : ""} · ${reais(x.membro)} por parlamentar` : `${x.n} parlamentar${x.n > 1 ? "es" : ""} · ${reais(x.total)} no total`,
        valor: medida === "total" ? x.total : x.membro,
        cor: corPartido(x.sigla),
      }))} />
      {limite && linhas.length > limite && <Link to="/partidos">Ver todos os {linhas.length} partidos</Link>}
    </section>
  );
}


/* Pizza (rosca) com o total de cada partido; os partidos menores entram juntos em "Outros". Usa a rosca do site inteiro. */
export function Pizza({ fatias, titulo }: { fatias: { sigla: string; valor: number; cor: string; outros?: boolean }[]; titulo: string }) {
  const proprias = fatias.filter((f) => !f.outros && f.valor > 0).sort((a, b) => b.valor - a.valor);
  const resto = fatias.filter((f) => f.outros).reduce((a, f) => a + f.valor, 0);
  const total = proprias.reduce((a, f) => a + f.valor, 0) + resto;
  if (!total) return null;
  const itens: FatiaPronta[] = proprias.map((f) => ({ nome: f.sigla, valor: f.valor, cor: f.cor, pct: f.valor / total }));
  if (resto > 0) itens.push({ nome: "Outros", valor: resto, cor: "var(--c-outros)", pct: resto / total, outros: true });
  return <div className="pizza-nova"><Rosca fatias={itens} titulo={titulo} formato={reaisCurto} /></div>;
}

export default function Partidos() {
  const { data, error } = useData<Partido[]>("partidos.json");
  const { ano } = useAno();
  if (!data) return <Loading error={error} />;
  return (
    <>
      <h1>Partidos</h1>
      <Bancadas partidos={data} />
      <GastoPartidos partidos={data} ano={ano} />
      <PartidosAnos partidos={data} ano={ano} />
      <p className="muted small">Conta cada parlamentar no partido atual. Quem mudou de partido aparece no partido de hoje, com todos os gastos do ano. Para ver cada parlamentar de um partido, use o filtro de partido em <Link to="/politicos">{MG ? "Federais" : "Políticos"}</Link>.</p>
      <OndeVer links={[
        { nome: "Gastos da cota parlamentar na Câmara", url: "https://www.camara.leg.br/transparencia/gastos-parlamentares", explica: "cada nota de cada deputado federal" },
        { nome: "Dados abertos da Câmara", url: "https://dadosabertos.camara.leg.br/swagger/api.html", explica: "a API oficial de deputados, despesas e votações" },
        { nome: "Dados abertos do Senado", url: "https://www12.senado.leg.br/dados-abertos", explica: "senadores, gastos (CEAPS) e votações" },
      ]} />
    </>
  );
}

/* Tamanho das bancadas: cadeiras por partido e por lado (esquerda a direita, pelos votos) */
function Bancadas({ partidos }: { partidos: Partido[] }) {
  return (
    <section>
      <h2>Quem tem mais cadeiras</h2>
      <p className="small muted">Parlamentares no mandato hoje, pelo partido atual. O lado vem dos votos da bancada nas votações nominais, o mesmo critério para todos.</p>
      <div className="secao-graficos">
        {(["camara", "senado"] as Casa[]).map((c) => {
          const ps = partidos.filter((p) => p.casa === c && p.n > 0).sort((a, b) => b.n - a.n);
          if (!ps.length) return null;
          const total = ps.reduce((a, p) => a + p.n, 0);
          const porLado: Record<string, number> = {};
          ps.forEach((p) => { const l = p.posicao == null ? "Sem posição" : ladoPelosVotos(p.posicao); porLado[l] = (porLado[l] || 0) + p.n; });
          const fmt = (v: number) => `${v} cadeira${v === 1 ? "" : "s"}`;
          return (
            <div key={c} className="card">
              <h3>{casaNome(c)}</h3>
              <div className="secao-graficos">
                <Rosca fatias={prepararFatias(ps.map((p) => ({ nome: p.sigla, valor: p.n, cor: corPartido(p.sigla) })), 7)} titulo={`Cadeiras por partido na ${casaNome(c)}`} formato={fmt} centroRotulo="Cadeiras" centro={String(total)} />
                <Rosca fatias={prepararFatias([...LADOS, "Sem posição"].map((l) => ({ nome: l, valor: porLado[l] || 0, cor: COR_LADO[l] })), 9)} titulo={`Cadeiras por lado na ${casaNome(c)}`} formato={fmt} centroRotulo="Por lado" centro={String(total)} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* Gasto de cada partido ano a ano, com a animação e a comparação de dois anos */
function PartidosAnos({ partidos, ano }: { partidos: Partido[]; ano: string }) {
  const [casa, setCasa] = useState<Casa>("camara");
  const porAno = useMemo(() => {
    const r: Record<string, Fatia[]> = {};
    partidos.filter((p) => p.casa === casa).forEach((p) => Object.entries(p.por_ano || {}).forEach(([a, x]) => {
      (r[a] ||= []).push({ nome: p.sigla, valor: x.cota_por_membro, cor: corPartido(p.sigla) });
    }));
    return r;
  }, [partidos, casa]);
  if (Object.keys(porAno).length < 2) return null;
  return (
    <section>
      <h2>Como o gasto de cada partido mudou</h2>
      <div className="toggle" role="group" aria-label="Casa">
        {(["camara", "senado"] as Casa[]).map((c) => <button key={c} aria-pressed={casa === c} onClick={() => setCasa(c)}>{casaNome(c)}</button>)}
      </div>
      <CompararAnos porAno={porAno} titulo="Cota por parlamentar, por partido" anoInicial={ano} limite={12}
        nota="Cota dividida pelo número de parlamentares do partido em cada ano, para comparar bancadas grandes e pequenas. O ano em andamento vai só até a última nota publicada." />
    </section>
  );
}
