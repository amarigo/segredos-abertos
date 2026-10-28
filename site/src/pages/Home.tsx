import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Barras, COR_GRUPO, Explain, Loading, useAno, useData } from "../components/ui";
import { corPartido, cotaNoAno, GRUPO_CURTO, GRUPO_EXPLICA, linkSeguro, reais, reaisCurto, type EmpresaResumo, type Grupo, type Meta, type Partido, type Resumo } from "../data";
import { GastoPartidos } from "./Partidos";
import { LADOS, ladoPelosVotos } from "../partidos";
import { MG, SITE } from "../recorte";
import type { CidadeResumo } from "../data";
import { AvisosFim, SelosResumo } from "../components/Selo";

export default function Home() {
  const { data: meta, error } = useData<Meta>("meta.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const { data: emps } = useData<EmpresaResumo[]>("empresas.json");
  const { data: partidos } = useData<Partido[]>("partidos.json");
  const { data: cidades } = useData<CidadeResumo[]>(MG ? "cidades.json" : null);
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
  // Empresas do ano escolhido (dados antigos, sem detalhe por ano: total de todos os anos)
  const empsAno = !!emps?.some((e) => e.por_ano);
  const topEmps = (emps || []).map((e) => ({ e, v: cotaNoAno(e, ano) || { valor: e.total, n_politicos: e.n_politicos } }))
    .filter((x) => x.v.valor > 0).sort((a, b) => b.v.valor - a.v.valor).slice(0, 8);
  const resultados = q.trim().length >= 2 && pols
    ? pols.filter((p) => norm(`${p.nome} ${p.partido} ${p.uf}`).includes(norm(q))).slice(0, 8) : [];

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Cota parlamentar · {ano}</span>
        <h1 className="big">{reaisCurto(meta.total_por_ano?.[ano] || 0)}</h1>
        <p>foi o que os {meta.contagens.politicos} {SITE.quem} pediram de reembolso com dinheiro público em {ano}.{meta.custo_por_ano?.[ano] ? <> Somando salários e equipe dos gabinetes, o custo conhecido chega a <strong>{reaisCurto(meta.custo_por_ano[ano])}</strong>.</> : null} Veja quanto cada um gastou, com quais empresas, quem são os donos dessas empresas e como cada um vota.</p>
        <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); if (resultados[0]) nav(`/p/${resultados[0].id}`); }}>
          <label htmlFor="busca" className="muted small" style={{ flexBasis: "100%" }}>{SITE.busca}</label>
          <input id="busca" value={q} onChange={(e) => setQ(e.target.value)} placeholder={SITE.buscaExemplo} autoComplete="off" />
        </form>
        {resultados.length > 0 && (
          <div className="list">{resultados.map((p) => <PessoaLinha key={p.id} p={p} />)}</div>
        )}
      </section>

      {MG && (
        <section>
          <h2>Minas em um só lugar</h2>
          <Explain>Quem governa o estado, quem faz as leis na Assembleia, para onde vai o dinheiro das emendas e quanto cada um gasta. Tudo com o link da fonte oficial.</Explain>
          <div className="grid">
            <Link to="/governo" className="card cidade-card"><strong>Governo do estado</strong><span className="small muted">Governador e vice eleitos, quem está no cargo hoje, salários e viagens do governador e dos secretários.</span></Link>
            <Link to="/assembleia" className="card cidade-card"><strong>Deputados estaduais</strong><span className="small muted">{meta.estado?.deputados_estaduais ? `${meta.estado.deputados_estaduais} deputados: ` : ""}gastos da verba indenizatória nota por nota, projetos apresentados e aprovados.</span></Link>
            <Link to="/emendas-estaduais" className="card cidade-card"><strong>Emendas estaduais</strong><span className="small muted">Quanto cada deputado estadual indicou do orçamento de Minas, para quais cidades e quem recebeu.</span></Link>
            <Link to="/politicos" className="card cidade-card"><strong>Deputados federais e senadores</strong><span className="small muted">Os {meta.contagens.politicos} que representam Minas em Brasília: cota parlamentar, empresas e votos.</span></Link>
          </div>
        </section>
      )}

      {MG && cidades && cidades.length > 0 && (
        <section>
          <h2>Sua cidade</h2>
          <Explain>Quem foi prefeito e quais partidos tiveram vereadores desde 1997, para saber de quem cobrar. E o dinheiro: onde a prefeitura gasta e quanto chegou por emendas de deputados e senadores.</Explain>
          <div className="grid">
            {cidades.map((c) => (
              <Link key={c.id} to={`/cidade/${c.id}`} className="card cidade-card">
                <strong className="cidade-nome">{c.nome}</strong>
                {c.prefeito && <span className="small"><i className="partido-cor" style={{ background: corPartido(c.prefeito.partido_hoje) }} />Prefeito: {c.prefeito.nome} ({c.prefeito.partido})</span>}
              </Link>
            ))}
          </div>
        </section>
      )}

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
          <h2>{empsAno ? `Empresas que mais receberam em ${ano}` : `Empresas que mais receberam (${meta.anos[0]} a ${meta.anos[meta.anos.length - 1]})`}</h2>
          <div className="list">
            {topEmps.map(({ e, v }) => (
              <Link key={e.cnpj} to={`/e/${e.cnpj}`} className="person" style={{ gridTemplateColumns: "1fr auto" }}>
                <div style={{ minWidth: 0 }}><div className="pname">{e.nome}</div><div className="meta">paga por {v.n_politicos} parlamentar{v.n_politicos > 1 ? "es" : ""}</div></div>
                <div className="num">{reaisCurto(v.valor)}</div>
              </Link>
            ))}
            {empsAno && emps && !topEmps.length && <div className="empty">Nenhuma empresa recebeu da cota em {ano} até agora.</div>}
          </div>
          <Link to="/empresas">Ver todas as empresas</Link>
        </section>
      </div>

      {!MG && (
        <section>
          <h2>Quem ganha com o dinheiro público</h2>
          <Explain>Empresas, ONGs e entidades que mais recebem do governo federal, as que deixam de pagar impostos por benefícios fiscais e os parlamentares, partidos e estados que mais mandaram emendas para elas. Com os donos de cada empresa.</Explain>
          <Link to="/incentivos" className="card cidade-card"><strong>Incentivos e dinheiro para empresas</strong><span className="small muted">Pagamentos, renúncia fiscal e emendas: quem recebeu mais e quem deu mais.</span></Link>
        </section>
      )}
      {partidos && partidos.some((p) => p.casa === "camara") && (
        <section>
          <h2>Onde cada partido está, pelos votos</h2>
          <Explain>Cada partido da Câmara aparece no lado em que fica pelo voto dos seus deputados nas votações nominais. É o mesmo critério para todos. Não usamos o que o partido diz de si, porque nem todos se colocam num lado em documento oficial, como estatuto ou programa. Em cada grupo, os partidos vão do mais à esquerda para o mais à direita. <Link to="/sobre">Entenda o cálculo</Link>.</Explain>
          <PartidosPelosVotos partidos={partidos.filter((p) => p.casa === "camara")} />
        </section>
      )}
      {partidos && <GastoPartidos partidos={partidos} ano={ano} limite={10} />}
      <p className="muted small">Média de cota por deputado federal: {reais(medias.camara)} · por senador: {reais(medias.senado)} em {ano}.</p>
      <AvisosFim>
        {meta.avisos && meta.avisos.length > 0 && (
          <div className="alert" role="note">
            <div>
              <strong>Dados incompletos nesta atualização.</strong> Alguns sites oficiais não responderam na última coleta:
              <ul>{meta.avisos.map((a) => <li key={a}>{a}</li>)}</ul>
              {!MG && <p className="alert-nota">Tentamos de novo sozinhos a cada 2 horas, até todos os sites responderem.</p>}
            </div>
          </div>
        )}
        {!MG && <SelosResumo />}
      </AvisosFim>
    </>
  );
}

/* Partidos agrupados pelo lado em que ficam pelos votos dos seus deputados */
function PartidosPelosVotos({ partidos }: { partidos: Partido[] }) {
  const grupos = [
    ...LADOS.map((l) => ({ titulo: l as string, itens: partidos.filter((p) => p.posicao != null && ladoPelosVotos(p.posicao) === l) })),
    { titulo: "Sem votos suficientes", itens: partidos.filter((p) => p.posicao == null) },
  ];
  return (
    <div className="lados">
      {grupos.filter((g) => g.itens.length > 0).map((g) => {
        const itens = g.itens.slice().sort((a, b) => (a.posicao ?? 0) - (b.posicao ?? 0) || b.n - a.n);
        const deps = itens.reduce((s, p) => s + p.n, 0);
        return (
          <div key={g.titulo} className="lados-grupo">
            <h3>{g.titulo} <small>{deps} deputado{deps === 1 ? "" : "s"}</small></h3>
            <ul>
              {itens.map((p) => (
                <li key={p.sigla}>
                  <span><i className="partido-cor" style={{ background: corPartido(p.sigla) }} /><Link to={`/politicos?partido=${encodeURIComponent(p.sigla)}`}><strong>{p.sigla}</strong></Link></span>
                  <small>{p.n} dep.</small>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export function PessoaLinha({ p, extra }: { p: Resumo; extra?: React.ReactNode }) {
  return (
    <Link to={`/p/${p.id}`} className="person">
      {linkSeguro(p.foto) ? <img src={linkSeguro(p.foto)} alt="" loading="lazy" /> : <span className="avatar" />}
      <div style={{ minWidth: 0 }}>
        <div className="pname">{p.nome}</div>
        <div className="meta">{p.cargo} · {p.partido}-{p.uf}</div>
      </div>
      <div className="num">{extra ?? reaisCurto(p.total)}</div>
    </Link>
  );
}

export const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
