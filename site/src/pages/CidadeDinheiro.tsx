import { useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useData } from "../components/ui";
import { cnpjFmt, linkSeguro, reais, reaisCurto, type DinheiroCidade as Dinheiro } from "../data";

/* Aba "Dinheiro" da cidade: onde a prefeitura gasta (contas entregues ao Tesouro) e o dinheiro que chega por
   emendas de deputados e senadores (federais) e de deputados estaduais. Cada bloco termina com o link da fonte. */
export function DinheiroCidade({ id, nome }: { id: string; nome: string }) {
  const { data: d, error } = useData<Dinheiro>(`cidades/dinheiro/${id}.json`);
  if (!d) return <Loading error={error} />;
  return (
    <>
      <section>
        <Explain>De onde vem e para onde vai o dinheiro público de {nome}: o que a prefeitura gastou em cada área, e o dinheiro que deputados e senadores mandaram para a cidade por emendas ao orçamento. Cada bloco tem o link para a fonte oficial.</Explain>
      </section>
      <Contas d={d} nome={nome} />
      <Federais d={d} nome={nome} />
      <Estaduais d={d} nome={nome} />
    </>
  );
}

function Contas({ d, nome }: { d: Dinheiro; nome: string }) {
  const anos = d.contas?.anos || [];
  const [ano, setAno] = useState(anos[0]?.ano);
  const a = anos.find((x) => x.ano === ano) || anos[0];
  return (
    <section>
      <h2>Onde a prefeitura gasta</h2>
      {!a ? <div className="empty">As contas de {nome} não puderam ser baixadas do Tesouro Nacional nesta atualização.</div> : <>
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
          <Explain>Despesas da prefeitura (e da Câmara Municipal, na área "Legislativa") por área, como a própria prefeitura informou ao Tesouro Nacional. "Liquidado" é o que foi entregue: a obra feita, o serviço prestado.</Explain>
          {anos.length > 1 && (
            <select id="ano-contas" aria-label="Ano das contas" value={a.ano} onChange={(e) => setAno(Number(e.target.value))}>
              {anos.map((x) => <option key={x.ano} value={x.ano}>{x.ano}</option>)}
            </select>
          )}
        </div>
        <div className="grid">
          <div className="card stat"><span className="label">Gasto em {a.ano} (liquidado)</span><span className="value">{reaisCurto(a.total_liquidado)}</span>
            <span className="hint">Pago até o fim do ano: {reaisCurto(a.total_pago)}</span></div>
          {a.funcoes.slice(0, 2).map((f) => (
            <div className="card stat" key={f.codigo}><span className="label">{f.funcao}</span><span className="value">{pctDe(f.liquidado, a.total_liquidado)}</span>
              <span className="hint">{reais(f.liquidado)} em {a.ano}</span></div>
          ))}
        </div>
        <Barras itens={a.funcoes.map((f) => ({ label: f.funcao, valor: f.liquidado, cor: "var(--s1)",
          nota: f.principais.length ? `Principalmente: ${f.principais.map((p) => p.nome).join(", ")}` : undefined }))} />
        <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(d.contas!.fonte)} target="_blank" rel="noreferrer">SICONFI, Tesouro Nacional ↗</a> (Declaração de Contas Anuais, despesas por função{a.instituicao ? `, ${a.instituicao}` : ""}). <a href={linkSeguro(d.contas!.api)} target="_blank" rel="noreferrer">Dados brutos ↗</a></p>
      </>}
    </section>
  );
}

const pctDe = (v: number, t: number) => (t ? `${Math.round((v / t) * 100)}%` : "—");

function Federais({ d, nome }: { d: Dinheiro; nome: string }) {
  const f = d.federais;
  const [todos, setTodos] = useState(false);
  return (
    <section>
      <h2>Emendas federais que chegaram a {nome}</h2>
      <Explain>Dinheiro do orçamento da União que deputados federais e senadores (de qualquer estado) indicaram e que foi pago a órgãos e entidades com endereço em {nome}: a prefeitura, o fundo de saúde, hospitais, associações.</Explain>
      {!f ? <div className="empty">O arquivo de emendas do Portal da Transparência não estava disponível nesta atualização.</div>
        : !f.por_ano.length ? <div className="empty">Nenhum pagamento de emenda federal a quem tem endereço em {nome} no arquivo do Portal da Transparência.</div> : <>
          <p className="dinheiro-total small">{f.por_ano.slice(0, 6).map((x) => <span key={x.ano}><strong>{x.ano}:</strong> <span className="num">{reais(x.valor)}</span></span>)}</p>
          <h3>Quem mandou</h3>
          <Barras itens={f.autores.slice(0, todos ? 40 : 10).map((a) => ({
            label: a.politico ? <Link to={`/p/${a.politico}`}>{a.nome}</Link> : <span>{a.nome}</span>,
            nota: `${a.partido ? a.partido + " · " : ""}${a.n} pagamento${a.n === 1 ? "" : "s"}`, valor: a.valor, cor: "var(--s2)" }))} />
          {f.autores.length > 10 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${f.autores.length}`}</button>}
          <h3>Quem recebeu</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Quem recebeu</th><th className="r">Valor</th></tr></thead>
              <tbody>
                {f.favorecidos.map((x, i) => (
                  <tr key={i}>
                    <td>{x.cnpj && linkSeguro(x.url) ? <a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">{x.nome} ↗</a> : x.nome}
                      {x.cnpj && <div className="muted small mono">CNPJ {cnpjFmt(x.cnpj)}</div>}
                      <div className="small muted">{x.anos.join(", ")}{x.autores.length ? ` · ${x.autores.slice(0, 3).map((a) => a.nome).join(", ")}` : ""}</div></td>
                    <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>}
      <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(f?.fonte || "https://portaldatransparencia.gov.br/emendas")} target="_blank" rel="noreferrer">Portal da Transparência (CGU), emendas parlamentares ↗</a>. O nome de quem recebeu leva à página oficial com todos os pagamentos.</p>
    </section>
  );
}

function Estaduais({ d, nome }: { d: Dinheiro; nome: string }) {
  const lista = d.estaduais?.lista || [];
  const [todos, setTodos] = useState(false);
  const porAno = new Map<number, [number, number]>();
  lista.forEach((x) => { const v = porAno.get(x.ano) || [0, 0]; porAno.set(x.ano, [v[0] + x.indicado, v[1] + x.pago]); });
  return (
    <section>
      <h2>Emendas estaduais para {nome}</h2>
      <Explain>Dinheiro do orçamento de Minas que deputados estaduais indicaram para {nome}. "Indicado" é o valor reservado; "pago" é o que já saiu do caixa do estado.</Explain>
      {!d.estaduais ? <div className="empty">O arquivo de emendas da Assembleia não estava disponível nesta atualização.</div>
        : !lista.length ? <div className="empty">Nenhuma emenda estadual para {nome} no arquivo da Assembleia.</div> : <>
          <p className="dinheiro-total small">{[...porAno.entries()].sort((a, b) => b[0] - a[0]).slice(0, 6).map(([a, v]) => (
            <span key={a}><strong>{a}:</strong> <span className="num">{reais(v[0])}</span> indicado, <span className="num">{reais(v[1])}</span> pago</span>))}</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Ano e deputado</th><th>Para quem e para quê</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
              <tbody>
                {lista.slice(0, todos ? 999 : 25).map((x, i) => (
                  <tr key={i}>
                    <td className="small"><span className="num">{x.ano}</span><div>{x.deputado ? <Link to={`/deputado-estadual/${x.deputado}`}>{x.autor}</Link> : x.autor}</div></td>
                    <td>{x.beneficiario}<div className="small muted">{[x.area, x.orgao, x.situacao].filter(Boolean).join(" · ")}</div>{x.descricao && <div className="small">{x.descricao}</div>}
                      <div className="small so-celular">Pago: <span className="num">{reais(x.pago)}</span></div></td>
                    <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.indicado)}</td>
                    <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(x.pago)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {lista.length > 25 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar as ${lista.length} indicações`}</button>}
        </>}
      <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(d.estaduais?.fonte || "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/")} target="_blank" rel="noreferrer">emendas parlamentares na Assembleia de Minas (ALMG) ↗</a>.</p>
    </section>
  );
}
