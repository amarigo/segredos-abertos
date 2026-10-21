import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Barras, COR_GRUPO, Espectro, Explain, Loading, useData } from "../components/ui";
import { GRUPO_CURTO, GRUPO_EXPLICA, reais, reaisCurto, type EmpresaResumo, type Grupo, type Meta, type Partido, type Resumo } from "../data";

export default function Home() {
  const { data: meta, error } = useData<Meta>("meta.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const { data: emps } = useData<EmpresaResumo[]>("empresas.json");
  const { data: partidos } = useData<Partido[]>("partidos.json");
  const [q, setQ] = useState("");
  const nav = useNavigate();

  const grupos = useMemo(() => {
    const g: Record<Grupo, number> = { pessoal: 0, escritorio: 0, servicos: 0 };
    pols?.forEach((p) => (Object.keys(g) as Grupo[]).forEach((k) => (g[k] += p.grupos[k] || 0)));
    return g;
  }, [pols]);

  if (!meta) return <Loading error={error} />;
  const anos = meta.anos.length > 1 ? `${meta.anos[0]} a ${meta.anos[meta.anos.length - 1]}` : String(meta.anos[0]);
  const top = (pols || []).slice().sort((a, b) => b.total - a.total).slice(0, 8);
  const resultados = q.trim().length >= 2 && pols
    ? pols.filter((p) => norm(`${p.nome} ${p.partido} ${p.uf}`).includes(norm(q))).slice(0, 8) : [];

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Cota parlamentar · {anos}</span>
        <div className="big">{reaisCurto(meta.total_gasto)}</div>
        <p>foi o que {meta.contagens.politicos} deputados federais e senadores em exercício pediram de reembolso com dinheiro público. Veja quanto cada um gastou, com quais empresas, quem são os donos dessas empresas e como cada um vota.</p>
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
          <h2>Quem mais gastou</h2>
          <div className="list">{top.map((p) => <PessoaLinha key={p.id} p={p} />)}</div>
          <Link to="/politicos">Ver todos os políticos</Link>
        </section>
        <section>
          <h2>Empresas que mais receberam</h2>
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
      <p className="muted small">Média por deputado federal: {reais(meta.medias.camara)} · por senador: {reais(meta.medias.senado)} no período.</p>
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
