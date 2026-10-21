import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Barras, COR_GRUPO, Espectro, Explain, Loading, useAno, useData } from "../components/ui";
import { GRUPO_CURTO, GRUPO_EXPLICA, reais, reaisCurto, type EmpresaResumo, type Grupo, type Meta, type Partido, type Resumo } from "../data";
import { GastoPartidos } from "./Partidos";

export default function Home() {
  const { data: meta, error } = useData<Meta>("meta.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const { data: emps } = useData<EmpresaResumo[]>("empresas.json");
  const { data: partidos } = useData<Partido[]>("partidos.json");
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const { ano } = useAno();

  const grupos = useMemo(() => {
    const g: Record<Grupo, number> = { pessoal: 0, escritorio: 0, servicos: 0 };
    pols?.forEach((p) => (Object.keys(g) as Grupo[]).forEach((k) => (g[k] += p.por_ano[ano]?.grupos[k] || 0)));
    return g;
  }, [pols, ano]);

  if (!meta) return <Loading error={error} />;
  const totalAno = (p: Resumo) => p.por_ano[ano]?.total || 0;
  const top = (pols || []).slice().sort((a, b) => totalAno(b) - totalAno(a)).slice(0, 8);
  const medias = meta.medias[ano] || { camara: 0, senado: 0 };
  const resultados = q.trim().length >= 2 && pols
    ? pols.filter((p) => norm(`${p.nome} ${p.partido} ${p.uf}`).includes(norm(q))).slice(0, 8) : [];

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Cota parlamentar · {ano}</span>
        <div className="big">{reaisCurto(meta.total_por_ano?.[ano] || 0)}</div>
        <p>foi o que os {meta.contagens.politicos} deputados federais e senadores em exercício pediram de reembolso com dinheiro público em {ano}.{meta.custo_por_ano?.[ano] ? <> Somando salários e equipe dos gabinetes, o custo conhecido chega a <strong>{reaisCurto(meta.custo_por_ano[ano])}</strong>.</> : null} Veja quanto cada um gastou, com quais empresas, quem são os donos dessas empresas e como cada um vota.</p>
        <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); if (resultados[0]) nav(`/p/${resultados[0].id}`); }}>
          <label htmlFor="busca" className="muted small" style={{ flexBasis: "100%" }}>Procure seu deputado ou senador</label>
          <input id="busca" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome, partido ou estado (ex.: SP)" autoComplete="off" />
        </form>
        {resultados.length > 0 && (
          <div className="list">{resultados.map((p) => <PessoaLinha key={p.id} p={p} />)}</div>
        )}
      </section>

      <section>
        <h2>Para onde vai o dinheiro</h2>
        <Explain>Além do salário, cada parlamentar tem uma <strong>cota</strong> mensal para pagar despesas do mandato. Ele paga e pede reembolso apresentando a nota fiscal. Separamos esses gastos em três grupos.</Explain>
        <Barras itens={(Object.keys(grupos) as Grupo[]).map((g) => ({ label: <strong>{GRUPO_CURTO[g]}</strong>, nota: GRUPO_EXPLICA[g], valor: grupos[g], cor: COR_GRUPO[g] }))} />
      </section>

      <div className="two">
        <section>
          <h2>Quem mais gastou em {ano}</h2>
          <div className="list">{top.map((p) => <PessoaLinha key={p.id} p={p} extra={reaisCurto(totalAno(p))} />)}</div>
          <Link to="/politicos">Ver todos os políticos</Link>
        </section>
        <section>
          <h2>Empresas que mais receberam ({meta.anos[0]} a {meta.anos[meta.anos.length - 1]})</h2>
          <div className="list">
            {(emps || []).slice(0, 8).map((e) => (
              <Link key={e.cnpj} to={`/e/${e.cnpj}`} className="person" style={{ gridTemplateColumns: "1fr auto" }}>
                <div style={{ minWidth: 0 }}><div className="pname">{e.nome}</div><div className="meta">paga por {e.n_politicos} parlamentar{e.n_politicos > 1 ? "es" : ""}</div></div>
                <div className="num">{reaisCurto(e.total)}</div>
              </Link>
            ))}
          </div>
          <Link to="/empresas">Ver todas as empresas</Link>
        </section>
      </div>

      {partidos && partidos.some((p) => p.posicao != null) && (
        <section>
          <h2>Onde cada partido está, pelos votos</h2>
          <Explain>Cada ponto é um partido na Câmara. A posição é calculada a partir de como seus deputados votaram de fato, não pelo que o partido diz de si. <Link to="/sobre">Entenda o cálculo</Link>.</Explain>
          <Espectro rotulos pontos={partidos.filter((p) => p.casa === "camara" && p.posicao != null).map((p) => ({ id: p.sigla, pos: p.posicao!, label: `${p.sigla}: ${p.n} deputados` }))} />
        </section>
      )}
      {partidos && <GastoPartidos partidos={partidos} ano={ano} limite={10} />}
      <p className="muted small">Média de cota por deputado federal: {reais(medias.camara)} · por senador: {reais(medias.senado)} em {ano}.</p>
    </>
  );
}

export function PessoaLinha({ p, extra }: { p: Resumo; extra?: React.ReactNode }) {
  return (
    <Link to={`/p/${p.id}`} className="person">
      {p.foto ? <img src={p.foto} alt="" loading="lazy" /> : <span className="avatar" />}
      <div style={{ minWidth: 0 }}>
        <div className="pname">{p.nome}</div>
        <div className="meta">{p.cargo} · {p.partido}-{p.uf}</div>
      </div>
      <div className="num">{extra ?? reaisCurto(p.total)}</div>
    </Link>
  );
}

export const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
