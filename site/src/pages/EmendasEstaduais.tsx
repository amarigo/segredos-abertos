import { Kpi } from "../components/graficos";
import { useState } from "react";
import { norm } from "./Home";
import { Link } from "react-router-dom";
import { Abrir, Barras, Colunas, Explain, Loading, OndeVer, useData } from "../components/ui";
import { reais, type DeputadoEstadual, type EmendasEstado } from "../data";

/** Emendas estaduais: quanto os deputados estaduais indicaram do orçamento de Minas, para quais cidades */
export default function EmendasEstaduais() {
  const { data, error } = useData<EmendasEstado>("estado/emendas.json");
  const anos = Object.keys(data?.anos || {}).sort();
  const [sel, setSel] = useState("");
  const [todos, setTodos] = useState(false);
  const [busca, setBusca] = useState("");
  if (!data) return <Loading error={error} />;
  const ano = anos.includes(sel) ? sel : anos[anos.length - 1];
  const a = data.anos[ano];
  if (!a) return <div className="empty">Sem dados de emendas estaduais.</div>;
  return (
    <>
      <section>
        <h1>Emendas estaduais</h1>
        <Explain>Todo ano, os deputados estaduais indicam para onde vai uma parte do orçamento de Minas: obras, equipamentos, hospitais, escolas, associações. O governo é obrigado a pagar boa parte dessas indicações. Aqui está quanto cada deputado indicou, para quais cidades, e quanto já foi pago.</Explain>
        <div className="row" style={{ gap: 8 }}>
          <label className="ano-sel"><span className="muted small">Ano do orçamento</span>
            <select id="ano-emendas" value={ano} onChange={(e) => setSel(e.target.value)}>{anos.slice().reverse().map((x) => <option key={x}>{x}</option>)}</select>
          </label>
        </div>
        <div className="grid">
          <Kpi rotulo={`Indicado em ${ano}`} valor={a.indicado} serie={anos.slice().sort().map((x) => [x, data.anos[x]?.indicado || 0] as [string, number])} ano={ano} dica={`${a.n.toLocaleString("pt-BR")} indicações para ${a.n_municipios} municípios`} />
          <Kpi rotulo="Já pago" valor={a.pago} serie={anos.slice().sort().map((x) => [x, data.anos[x]?.pago || 0] as [string, number])} ano={ano} dica={`${a.indicado ? Math.round((a.pago / a.indicado) * 100) : 0}% do indicado`} />
        </div>
      </section>
      {anos.length > 1 && <section>
        <h2>Ano a ano</h2>
        <Colunas rotulo="Emendas estaduais indicadas por ano, pago e a pagar" partes={[{ nome: "Pago", cor: "var(--s3)" }, { nome: "Ainda não pago", cor: "var(--grid)" }]}
          itens={anos.map((x) => ({ label: x, valores: [data.anos[x].pago, Math.max(0, data.anos[x].indicado - data.anos[x].pago)] }))} />
        <p className="muted small">A altura da coluna é o total indicado no orçamento de cada ano; a parte verde é o que o estado já pagou.</p>
      </section>}
      <section>
        <h2>Quem indicou mais</h2>
        <Barras rosca={{ titulo: `Emendas estaduais indicadas em ${ano}, por deputado`, total: a.indicado }} itens={a.autores.slice(0, todos ? 100 : 15).map((x) => ({ nome: x.nome,
          label: x.deputado ? <Link to={`/deputado-estadual/${x.deputado}?aba=emendas&ano=${ano}`}>{x.nome}</Link> : <span>{x.nome}</span>,
          nota: `${x.n} indicações · ${reais(x.pago)} pago`, valor: x.indicado, cor: "var(--s3)" }))} />
        {a.autores.length > 15 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${a.autores.length}`}</button>}
        <p className="muted small">Nomes sem link são de quem não está mais em exercício na Assembleia, ou de blocos e comissões.</p>
      </section>
      <section>
        <h2>Cada indicação, deputado por deputado</h2>
        <Explain>Abra um deputado para ver cada indicação que ele fez em {ano}: quem recebe, em qual cidade, para quê, quanto foi indicado e quanto já foi pago.</Explain>
        <div className="search"><input id="busca-autor" aria-label="Procurar deputado" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Nome do deputado" /></div>
        {a.autores.filter((x) => x.deputado && (!busca || norm(x.nome).includes(norm(busca)))).map((x) => (
          <Abrir key={x.deputado} titulo={<>{x.nome} · <span className="num">{reais(x.indicado)}</span> <span className="muted small">({x.n} indicaç{x.n === 1 ? "ão" : "ões"})</span></>}>
            <IndicacoesDeputado id={x.deputado!} ano={ano} />
          </Abrir>
        ))}
      </section>
      <section>
        <h2>Cidades que mais receberam indicações</h2>
        <Barras rosca={{ titulo: `Emendas estaduais indicadas em ${ano}, por cidade`, total: a.indicado }} itens={a.municipios.map((m) => ({ label: m.nome, nota: `${m.n} indicações · ${reais(m.pago)} pago`, valor: m.indicado, cor: "var(--s1)" }))} />
        <p className="small">Veja também a aba Dinheiro das <Link to="/cidades">cidades acompanhadas</Link>, com cada indicação.</p>
      </section>
      <OndeVer links={[
        { nome: "Emendas parlamentares na Assembleia de Minas (ALMG)", url: data.fonte, explica: "a lista oficial de indicações, com filtros por deputado e cidade" },
        { nome: "Execução das emendas estaduais no Dados MG", url: "https://dados.mg.gov.br/dataset/portal_emendas_estaduais", explica: "empenhos e pagamentos, para baixar" },
        { nome: "Portal da Transparência de MG", url: "https://www.transparencia.mg.gov.br/", explica: "pagamentos do governo a cada município e entidade" },
      ]} />
    </>
  );
}

/** As indicações de um deputado num ano, lidas do arquivo do deputado só quando alguém abre */
function IndicacoesDeputado({ id, ano }: { id: string; ano: string }) {
  const { data: d, error } = useData<DeputadoEstadual>(/^\d{1,10}$/.test(id) ? `almg/d/${id}.json` : null);
  if (!d) return <Loading error={error} />;
  const e = d.anos[ano]?.emendas;
  if (!e || !e.beneficiarios.length) return <p className="small muted">Sem o detalhe das indicações deste ano. <Link to={`/deputado-estadual/${id}?aba=emendas&ano=${ano}`}>Ver a página do deputado</Link>.</p>;
  return (
    <>
      <div className="table-wrap">
        <table className="small">
          <thead><tr><th>Quem recebe e para quê</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
          <tbody>{e.beneficiarios.map((b, i) => (
            <tr key={i}>
              <td>{b.nome}<div className="muted">{b.municipio}{b.area ? ` · ${b.area}` : ""}</div>{b.descricao && <div>{b.descricao}</div>}
                <div className="so-celular">Pago: <span className="num">{reais(b.pago)}</span></div></td>
              <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(b.indicado)}</td>
              <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(b.pago)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="small"><Link to={`/deputado-estadual/${id}?aba=emendas&ano=${ano}`}>Página completa de {d.nome} ›</Link></p>
    </>
  );
}
