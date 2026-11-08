import { useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Colunas, Explain, Loading, useAno, useData } from "../components/ui";
import { anoContas, cnpjFmt, linkSeguro, reais, reaisCurto, type DinheiroCidade as Dinheiro } from "../data";
import { DetalheEmendaEstadual } from "../components/EmendaEstadual";

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
      <p className="small">Para comparar os anos e abrir cada área, veja <Link to={`/dinheiro?onde=${d.id}`}>o dinheiro de {nome}, passo a passo</Link>.</p>
      {!a ? <div className="empty">As contas de {nome} não puderam ser baixadas do Tesouro Nacional nesta atualização.</div> : <>
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
          <Explain>Despesas da prefeitura (e da Câmara Municipal, na área "Legislativa") por área, como a própria prefeitura informou ao Tesouro Nacional. "Liquidado" é o que foi entregue: a obra feita, o serviço prestado.</Explain>
          {anos.length > 1 && (
            <select id="ano-contas" aria-label="Ano das contas" value={a.ano} onChange={(e) => setAno(Number(e.target.value))}>
              {anos.map((x) => <option key={x.ano} value={x.ano}>{anoContas(x)}</option>)}
            </select>
          )}
        </div>
        <div className="grid">
          <div className="card stat"><span className="label">Gasto em {anoContas(a)} (liquidado)</span><span className="value">{reaisCurto(a.total_liquidado)}</span>
            <span className="hint">{a.total_pago != null ? `Pago até o fim do ano: ${reaisCurto(a.total_pago)}` : `Parcial: o ano ainda não acabou`}</span></div>
          {a.funcoes.slice(0, 2).map((f) => (
            <div className="card stat" key={f.codigo}><span className="label">{f.funcao}</span><span className="value">{pctDe(f.liquidado, a.total_liquidado)}</span>
              <span className="hint">{reais(f.liquidado)} em {anoContas(a)}</span></div>
          ))}
        </div>
        <Barras rosca={{ titulo: `Gasto da prefeitura em ${anoContas(a)}, por área`, total: a.total_liquidado }} itens={a.funcoes.map((f) => ({ label: f.funcao, valor: f.liquidado, cor: "var(--s1)",
          nota: f.principais.length ? `Principalmente: ${f.principais.map((p) => p.nome).join(", ")}` : undefined }))} />
        <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(d.contas!.fonte)} target="_blank" rel="noreferrer">SICONFI, Tesouro Nacional ↗</a> ({a.parcial ? `Relatório Resumido da Execução Orçamentária, até ${a.ate_mes}` : "Declaração de Contas Anuais"}, despesas por função{a.instituicao ? `, ${a.instituicao}` : ""}). <a href={linkSeguro(a.api || d.contas!.api)} target="_blank" rel="noreferrer">Dados brutos ↗</a></p>
      </>}
    </section>
  );
}

const pctDe = (v: number, t: number) => (t ? `${Math.round((v / t) * 100)}%` : "—");

/** Ano das emendas: começa no ano escolhido no topo do site (ou no mais recente com dados); "todos" soma tudo. */
function useAnoEmendas(anos: number[]): [string, (a: string) => void] {
  const { ano: global } = useAno();
  const inicial = anos.includes(Number(global)) ? global : anos.length ? String(Math.max(...anos)) : "todos";
  const [ano, setAno] = useState<string | null>(null);
  return [ano ?? inicial, setAno];
}

function EscolherAno({ id, anos, ano, setAno }: { id: string; anos: number[]; ano: string; setAno: (a: string) => void }) {
  return (
    <label className="ano-sel"><span className="muted small">Ano</span>
      <select id={id} value={ano} onChange={(e) => setAno(e.target.value)}>
        <option value="todos">Todos os anos</option>
        {anos.slice().sort((a, b) => b - a).map((a) => <option key={a} value={a}>{a}</option>)}
      </select></label>
  );
}

function Federais({ d, nome }: { d: Dinheiro; nome: string }) {
  const f = d.federais;
  const [todos, setTodos] = useState(false);
  const anosF = (f?.por_ano || []).map((x) => x.ano);
  const [ano, setAno] = useAnoEmendas(anosF);
  const doAno = ano !== "todos";
  // Arquivos antigos não têm o valor de cada ano: aí o filtro vale só para o gráfico e os totais
  const temPorAno = !!f && f.autores.every((a) => a.por_ano) && f.favorecidos.every((x) => x.por_ano);
  const autores = !f ? [] : !doAno || !temPorAno ? f.autores
    : f.autores.filter((a) => a.por_ano?.[ano]).map((a) => ({ ...a, valor: a.por_ano![ano].valor, n: a.por_ano![ano].n })).sort((a, b) => b.valor - a.valor);
  const favorecidos = !f ? [] : !doAno || !temPorAno ? f.favorecidos
    : f.favorecidos.filter((x) => x.por_ano?.[ano]).map((x) => ({ ...x, valor: x.por_ano![ano].valor, autores: x.por_ano![ano].autores })).sort((a, b) => b.valor - a.valor);
  const totalAno = doAno ? f?.por_ano.find((x) => String(x.ano) === ano)?.valor || 0 : (f?.por_ano || []).reduce((s, x) => s + x.valor, 0);
  const quando = doAno ? `em ${ano}` : "em todos os anos";
  return (
    <section>
      <h2>Emendas federais que chegaram a {nome}</h2>
      <Explain>Dinheiro do orçamento da União que deputados federais e senadores (de qualquer estado) indicaram e que foi pago a órgãos e entidades com endereço em {nome}: a prefeitura, o fundo de saúde, hospitais, associações.</Explain>
      {!f ? <div className="empty">O arquivo de emendas do Portal da Transparência não estava disponível nesta atualização.</div>
        : !f.por_ano.length ? <div className="empty">Nenhum pagamento de emenda federal a quem tem endereço em {nome} no arquivo do Portal da Transparência.</div> : <>
          <p className="muted small">Pago por ano. Toque numa coluna para ver só aquele ano.</p>
          <Colunas rotulo={`Emendas federais pagas em ${nome}, por ano`} partes={[{ nome: "Pago", cor: "var(--s2)" }]}
            ativo={doAno ? ano : undefined} onEscolher={(a) => setAno(a === ano ? "todos" : a)}
            itens={f.por_ano.slice().sort((a, b) => a.ano - b.ano).map((x) => ({ label: String(x.ano), valores: [x.valor] }))} />
          <div className="search"><EscolherAno id="ano-federais" anos={anosF} ano={ano} setAno={setAno} /></div>
          <div className="grid">
            <div className="card stat"><span className="label">Pago {quando}</span><span className="value">{reaisCurto(totalAno)}</span>
              <span className="hint">{autores.length} {autores.length === 1 ? "autor" : "autores"} de emenda, {favorecidos.length} {favorecidos.length === 1 ? "quem recebeu" : "que receberam"}</span></div>
          </div>
          {doAno && !temPorAno && <p className="muted small">As listas abaixo somam todos os anos: esta atualização ainda não separou os valores por ano.</p>}
          <h3>Quem mandou {quando}</h3>
          {!autores.length ? <div className="empty">Nenhum pagamento {quando}.</div> : <>
            <Barras rosca={{ titulo: `Emendas federais pagas em ${nome} ${quando}, por quem mandou` }} itens={autores.slice(0, todos ? 40 : 10).map((a) => ({ nome: a.nome,
              label: a.politico ? <Link to={`/p/${a.politico}`}>{a.nome}</Link> : <span>{a.nome}</span>,
              nota: `${a.partido ? a.partido + " · " : ""}${a.n} pagamento${a.n === 1 ? "" : "s"}`, valor: a.valor, cor: "var(--s2)" }))} />
            {autores.length > 10 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${autores.length}`}</button>}
          </>}
          <h3>Quem recebeu {quando}</h3>
          {!favorecidos.length ? <div className="empty">Nenhum pagamento {quando}.</div> :
          <div className="table-wrap">
            <table>
              <thead><tr><th>Quem recebeu</th><th className="r">Valor</th></tr></thead>
              <tbody>
                {favorecidos.map((x, i) => (
                  <tr key={i}>
                    <td>{x.cnpj && linkSeguro(x.url) ? <a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">{x.nome} ↗</a> : x.nome}
                      {x.cnpj && <div className="muted small mono">CNPJ {cnpjFmt(x.cnpj)}</div>}
                      <div className="small muted">{doAno && temPorAno ? "" : `${x.anos.join(", ")}${x.autores.length ? " · " : ""}`}{x.autores.slice(0, 3).map((a) => a.nome).join(", ")}</div></td>
                    <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
        </>}
      <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(f?.fonte || "https://portaldatransparencia.gov.br/emendas")} target="_blank" rel="noreferrer">Portal da Transparência (CGU), emendas parlamentares ↗</a>. O nome de quem recebeu leva à página oficial com todos os pagamentos.</p>
    </section>
  );
}

function Estaduais({ d, nome }: { d: Dinheiro; nome: string }) {
  const tudo = d.estaduais?.lista || [];
  const [todos, setTodos] = useState(false);
  const porAno = new Map<number, [number, number]>();
  tudo.forEach((x) => { const v = porAno.get(x.ano) || [0, 0]; porAno.set(x.ano, [v[0] + x.indicado, v[1] + x.pago]); });
  const anosE = [...porAno.keys()];
  const [ano, setAno] = useAnoEmendas(anosE);
  const doAno = ano !== "todos";
  const lista = doAno ? tudo.filter((x) => String(x.ano) === ano) : tudo;
  const soma = lista.reduce((s, x) => [s[0] + x.indicado, s[1] + x.pago], [0, 0]);
  const quando = doAno ? `em ${ano}` : "em todos os anos";
  return (
    <section>
      <h2>Emendas estaduais para {nome}</h2>
      <Explain>Dinheiro do orçamento de Minas que deputados estaduais indicaram para {nome}. "Indicado" é o valor reservado; "pago" é o que já saiu do caixa do estado.</Explain>
      {!d.estaduais ? <div className="empty">O arquivo de emendas da Assembleia não estava disponível nesta atualização.</div>
        : !tudo.length ? <div className="empty">Nenhuma emenda estadual para {nome} no arquivo da Assembleia.</div> : <>
          <p className="muted small">Indicado e pago por ano. Toque numa coluna para ver só aquele ano.</p>
          <Colunas rotulo={`Emendas estaduais para ${nome}, por ano`} partes={[{ nome: "Pago", cor: "var(--s1)" }, { nome: "Indicado e ainda não pago", cor: "var(--q2)" }]}
            ativo={doAno ? ano : undefined} onEscolher={(a) => setAno(a === ano ? "todos" : a)}
            itens={[...porAno.entries()].sort((a, b) => a[0] - b[0]).map(([a, v]) => ({ label: String(a), valores: [v[1], Math.max(0, v[0] - v[1])] }))} />
          <div className="search"><EscolherAno id="ano-estaduais" anos={anosE} ano={ano} setAno={setAno} /></div>
          <div className="grid">
            <div className="card stat"><span className="label">Indicado {quando}</span><span className="value">{reaisCurto(soma[0])}</span>
              <span className="hint">{lista.length} indicaç{lista.length === 1 ? "ão" : "ões"}</span></div>
            <div className="card stat"><span className="label">Pago {quando}</span><span className="value">{reaisCurto(soma[1])}</span>
              <span className="hint">{soma[0] ? Math.round((soma[1] / soma[0]) * 100) : 0}% do indicado</span></div>
          </div>
          {!lista.length ? <div className="empty">Nenhuma emenda estadual para {nome} {quando}.</div> : <>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Ano e deputado</th><th>Para quem e para quê</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
              <tbody>
                {lista.slice(0, todos ? 999 : 25).map((x, i) => (
                  <tr key={i}>
                    <td className="small"><span className="num">{x.ano}</span><div>{x.deputado ? <Link to={`/deputado-estadual/${x.deputado}`}>{x.autor}</Link> : x.autor}</div></td>
                    <td>{x.beneficiario}<DetalheEmendaEstadual x={x} />
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
          <p className="small"><Link to={`/emendas-estaduais?cidade=${encodeURIComponent(tudo[0]?.municipio || nome)}`}>Comparar com as outras cidades e ver quem mais recebeu emendas estaduais ›</Link></p>
        </>}
      <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(d.estaduais?.fonte || "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/")} target="_blank" rel="noreferrer">emendas parlamentares na Assembleia de Minas (ALMG) ↗</a>.</p>
    </section>
  );
}
