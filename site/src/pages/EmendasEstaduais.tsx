import { Kpi } from "../components/graficos";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { norm } from "./Home";
import { Link, useSearchParams } from "react-router-dom";
import { Barras, Colunas, Explain, Loading, OndeVer, useData } from "../components/ui";
import { DetalheEmendaEstadual } from "../components/EmendaEstadual";
import { indicacoesEstaduais, linkSeguro, reais, type EmendasEstado, type EmendasEstadoLista, type SomaEmenda } from "../data";

type Filtro = "autor" | "cidade" | "orgao" | "q" | "dep";
const FILTROS: Filtro[] = ["autor", "cidade", "orgao", "q", "dep"];

/** Emendas estaduais: quem indicou, para onde, quem executa, como o dinheiro é gasto e quem mais recebeu */
export default function EmendasEstaduais() {
  const { data, error } = useData<EmendasEstado>("estado/emendas.json");
  const [params, setParams] = useSearchParams();
  const anos = Object.keys(data?.anos || {}).sort();
  const [todos, setTodos] = useState(false);
  const sel = params.get("ano") || "";
  const ano = anos.includes(sel) ? sel : anos[anos.length - 1];
  /** Muda os filtros da lista (ficam no endereço, para dar para mandar o link) e leva até ela */
  const filtrar = (f: Partial<Record<Filtro | "ano", string>>, rolar = true) => {
    const p = new URLSearchParams(params);
    if (rolar) FILTROS.forEach((k) => p.delete(k));
    Object.entries(f).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    setParams(p, { replace: true });
    if (rolar) setTimeout(() => document.getElementById("indicacoes")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };
  if (!data) return <Loading error={error} />;
  const a = data.anos[ano];
  if (!a) return <div className="empty">Sem dados de emendas estaduais.</div>;
  const filtro = (rotulo: string, f: Partial<Record<Filtro, string>>, nome: string): ReactNode =>
    <button className="link" title={`Ver as indicações de ${nome}`} onClick={() => filtrar(f)}>{rotulo}</button>;
  const nota = (x: SomaEmenda, extra = "") => `${extra}${x.n.toLocaleString("pt-BR")} indicaç${x.n === 1 ? "ão" : "ões"} · ${reais(x.pago)} pago`;
  return (
    <>
      <section>
        <h1>Emendas estaduais</h1>
        <Explain>Todo ano, os deputados estaduais indicam para onde vai uma parte do orçamento de Minas: obras, equipamentos, hospitais, escolas, associações. O governo é obrigado a pagar boa parte dessas indicações. Aqui está quem indicou, para quais cidades e entidades, qual órgão do estado executa, em que o dinheiro é gasto e quanto já foi pago.</Explain>
        <div className="row" style={{ gap: 8 }}>
          <label className="ano-sel"><span className="muted small">Ano do orçamento</span>
            <select id="ano-emendas" value={ano} onChange={(e) => filtrar({ ano: e.target.value }, false)}>{anos.slice().reverse().map((x) => <option key={x}>{x}</option>)}</select>
          </label>
        </div>
        <div className="grid">
          <Kpi rotulo={`Indicado em ${ano}`} valor={a.indicado} serie={anos.map((x) => [x, data.anos[x]?.indicado || 0] as [string, number])} ano={ano}
            dica={`${a.n.toLocaleString("pt-BR")} indicações para ${a.n_municipios} municípios${a.reprovadas ? `; outras ${a.reprovadas.toLocaleString("pt-BR")} foram reprovadas pelo governo` : ""}`} />
          {a.empenhado != null && <Kpi rotulo="Empenhado (reservado para pagar)" valor={a.empenhado} ano={ano} dica={`${a.indicado ? Math.round((a.empenhado / a.indicado) * 100) : 0}% do indicado`} />}
          <Kpi rotulo="Já pago" valor={a.pago} serie={anos.map((x) => [x, data.anos[x]?.pago || 0] as [string, number])} ano={ano} dica={`${a.indicado ? Math.round((a.pago / a.indicado) * 100) : 0}% do indicado`} />
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
        <Explain>Cada deputado indica a sua parte, e os blocos e bancadas da Assembleia indicam juntos uma parte maior. Clique em "ver indicações" para ver cada uma.</Explain>
        <Barras rosca={{ titulo: `Emendas estaduais indicadas em ${ano}, por autor`, total: a.indicado }} itens={a.autores.slice(0, todos ? 200 : 15).map((x) => ({ nome: x.nome,
          label: <span>{x.deputado ? <Link to={`/deputado-estadual/${x.deputado}?aba=emendas&ano=${ano}`}>{x.nome}</Link> : <span>{x.nome}</span>}{" "}
            <span className="small">· {filtro("ver indicações", { autor: x.nome }, x.nome)}</span></span>,
          nota: nota(x), valor: x.indicado, cor: "var(--s3)" }))} />
        {a.autores.length > 15 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${a.autores.length}`}</button>}
        <p className="muted small">Nomes sem link são de blocos, bancadas e comissões, ou de quem não está mais em exercício na Assembleia.</p>
      </section>
      {!!a.beneficiarios?.length && <section>
        <h2>Quem mais recebeu</h2>
        <Explain>As prefeituras, fundos, hospitais e entidades que mais receberam indicações em {ano}, somando todos os deputados. "A ser definido pelo órgão" é dinheiro que o próprio órgão do estado gasta e ainda não disse onde.</Explain>
        <Barras itens={a.beneficiarios.map((b) => ({ nome: b.nome, label: filtro(b.nome, { q: b.nome, cidade: b.municipio }, b.nome),
          nota: nota(b, `${[b.municipio, b.tipo].filter(Boolean).join(" · ")} · `), valor: b.indicado, cor: "var(--s2)" }))} />
        {a.n_beneficiarios != null && <p className="muted small">Os 30 maiores, de {a.n_beneficiarios.toLocaleString("pt-BR")} que receberam indicações em {ano}.</p>}
      </section>}
      <section>
        <h2>Cidades que mais receberam indicações</h2>
        <Barras rosca={{ titulo: `Emendas estaduais indicadas em ${ano}, por cidade`, total: a.indicado }} itens={a.municipios.map((m) => ({ nome: m.nome, label: filtro(m.nome, { cidade: m.nome }, m.nome), nota: nota(m), valor: m.indicado, cor: "var(--s1)" }))} />
        <p className="small">Veja também a aba Dinheiro das <Link to="/cidades">cidades acompanhadas</Link>, com cada indicação.</p>
      </section>
      {!!a.orgaos?.length && <section>
        <h2>Quem executa: os órgãos do estado</h2>
        <Explain>O dinheiro da emenda sai do orçamento de um órgão do estado, que faz o convênio, a transferência ou a compra. O Fundo Estadual de Saúde, por exemplo, repassa para os fundos municipais de saúde.</Explain>
        <Barras rosca={{ titulo: `Emendas estaduais indicadas em ${ano}, por órgão que executa`, total: a.indicado }} itens={a.orgaos.slice(0, 20).map((o) => ({ nome: o.nome, label: filtro(o.nome, { orgao: o.nome }, o.nome), nota: nota(o), valor: o.indicado, cor: "var(--c4)" }))} />
      </section>}
      {(!!a.tipos?.length || !!a.grupos?.length || !!a.areas?.length) && <section>
        <h2>Como o dinheiro é usado</h2>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 340px), 1fr))" }}>
          {!!a.tipos?.length && <div className="card"><h3>Forma de execução</h3>
            <p className="muted small">Convênio com a prefeitura ou entidade, transferência direta para o fundo municipal, ou compra feita pelo próprio estado.</p>
            <Barras itens={a.tipos.map((t) => ({ label: t.nome, nota: nota(t), valor: t.indicado, cor: "var(--c5)" }))} /></div>}
          {!!a.grupos?.length && <div className="card"><h3>Tipo de despesa</h3>
            <p className="muted small">Investimento é obra e equipamento, que fica; despesa corrente é custeio do dia a dia, como remédio, salário e manutenção.</p>
            <Barras itens={a.grupos.map((t) => ({ label: t.nome, nota: nota(t), valor: t.indicado, cor: "var(--c6)" }))} /></div>}
          {!!a.areas?.length && <div className="card"><h3>Área</h3>
            <Barras itens={a.areas.slice(0, 12).map((t) => ({ label: t.nome, nota: nota(t), valor: t.indicado, cor: "var(--s1)" }))} /></div>}
        </div>
      </section>}
      <Indicacoes ano={ano} params={params} filtrar={filtrar} />
      <OndeVer links={[
        { nome: "Emendas parlamentares na Assembleia de Minas (ALMG)", url: data.fonte, explica: "a lista oficial de indicações, com filtros por deputado e cidade" },
        ...(data.arquivo ? [{ nome: "Arquivo de emendas da ALMG (CSV)", url: data.arquivo, explica: "o arquivo usado aqui, com todas as indicações desde 2019" }] : []),
        { nome: "Transparência das emendas no governo de Minas", url: "https://www.emendas.mg.gov.br/transparencia/", explica: "empenho, liquidação e pagamento de cada indicação, com mapa" },
        { nome: "Execução das emendas estaduais no Dados MG", url: "https://dados.mg.gov.br/dataset/portal_emendas_estaduais", explica: "empenhos e pagamentos, para baixar" },
      ]} />
    </>
  );
}

/** Cada indicação do ano, com filtros por autor, cidade, órgão e texto. O arquivo do ano só é lido aqui. */
function Indicacoes({ ano, params, filtrar }: { ano: string; params: URLSearchParams; filtrar: (f: Partial<Record<Filtro, string>>, rolar?: boolean) => void }) {
  const { data, error } = useData<EmendasEstadoLista>(/^\d{4}$/.test(ano) ? `estado/emendas/${ano}.json` : null);
  const [qtd, setQtd] = useState(20);
  const lista = useMemo(() => (data ? indicacoesEstaduais(data) : []), [data]);
  const opcoes = useMemo(() => {
    const conta = (k: "autor" | "municipio" | "orgao_nome") => [...new Set(lista.map((x) => x[k]).filter(Boolean))].sort((x, y) => x.localeCompare(y, "pt-BR"));
    return { autor: conta("autor"), cidade: conta("municipio"), orgao: conta("orgao_nome") };
  }, [lista]);
  // ?dep=<id> vem da página do deputado: acha o nome dele como está no arquivo
  const dep = params.get("dep") || "";
  const autorDep = dep && data ? Object.entries(data.deputados || {}).find(([, id]) => id === dep)?.[0] || "" : "";
  const autor = params.get("autor") || autorDep;
  const cidade = params.get("cidade") || "";
  const orgao = params.get("orgao") || "";
  const q = params.get("q") || "";
  const algum = !!(autor || cidade || orgao || q);
  useEffect(() => { setQtd(20); }, [autor, cidade, orgao, q, ano]);
  useEffect(() => {
    if (data && algum) document.getElementById("indicacoes")?.scrollIntoView({ block: "start" });
    // só na primeira vez que a lista chega (quando alguém abre um link já filtrado)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  const nq = norm(q);
  const vis = lista.filter((x) => (!autor || x.autor === autor) && (!cidade || x.municipio === cidade) && (!orgao || x.orgao_nome === orgao)
    && (!nq || norm(`${x.beneficiario} ${x.descricao} ${x.objeto} ${x.acao} ${x.numero}`).includes(nq)));
  const soma = vis.reduce((s, x) => [s[0] + x.indicado, s[1] + x.pago], [0, 0]);
  const sel = (id: Filtro, rot: string, valor: string, ops: string[], todos: string) => (
    <label><span className="muted small">{rot}</span>
      <select id={`filtro-${id}`} value={valor} onChange={(e) => filtrar({ [id]: e.target.value, ...(id === "autor" ? { dep: "" } : {}) }, false)}>
        <option value="">{todos}</option>
        {valor && !ops.includes(valor) && <option value={valor}>{valor}</option>}
        {ops.map((o) => <option key={o} value={o}>{o}</option>)}
      </select></label>
  );
  return (
    <section id="indicacoes">
      <h2>Cada indicação de {ano}</h2>
      <Explain>Escolha um deputado, uma cidade ou um órgão, ou procure pelo nome de quem recebe. Cada indicação mostra para quê é o dinheiro, quem executa, a forma de execução, o tipo de despesa e quanto já foi pago.</Explain>
      {!data ? <Loading error={error} /> : <>
        <div className="filtros-emendas">
          {sel("autor", "Quem indicou", autor, opcoes.autor, "Todos os autores")}
          {sel("cidade", "Cidade", cidade, opcoes.cidade, "Todas as cidades")}
          {sel("orgao", "Órgão que executa", orgao, opcoes.orgao, "Todos os órgãos")}
          <label><span className="muted small">Procurar</span>
            <input id="busca-emenda" aria-label="Procurar quem recebe ou o que é" value={q} onChange={(e) => filtrar({ q: e.target.value }, false)} placeholder="Quem recebe, o que é, nº" /></label>
        </div>
        <p className="small">
          <strong>{vis.length.toLocaleString("pt-BR")}</strong> indicaç{vis.length === 1 ? "ão" : "ões"}: <span className="num">{reais(soma[0])}</span> indicado, <span className="num">{reais(soma[1])}</span> pago.
          {algum && <> <button className="link" onClick={() => filtrar(Object.fromEntries(FILTROS.map((k) => [k, ""])), false)}>Limpar filtros</button></>}
          {autor && data.deputados?.[autor] && <> · <Link to={`/deputado-estadual/${data.deputados[autor]}?aba=emendas&ano=${ano}`}>página de {autor} ›</Link></>}
        </p>
        {!vis.length ? <div className="empty">Nenhuma indicação com esses filtros.</div> : <div className="table-wrap">
          <table className="small">
            <thead><tr><th>Quem recebe, para quê e quem executa</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
            <tbody>{vis.slice(0, qtd).map((x, i) => (
              <tr key={`${x.numero}-${i}`}>
                <td><strong>{x.beneficiario || "Quem recebe não informado"}</strong>
                  <div className="muted">{[x.municipio, x.tipo_beneficiario].filter(Boolean).join(" · ")}{x.numero ? ` · indicação nº ${x.numero}` : ""}</div>
                  <DetalheEmendaEstadual x={x} autor={autor ? undefined : <>{data.deputados?.[x.autor]
                    ? <Link to={`/deputado-estadual/${data.deputados[x.autor]}?aba=emendas&ano=${ano}`}>{x.autor}</Link> : x.autor}{x.autoria ? <span className="muted"> ({x.autoria.toLowerCase()})</span> : null}</>} />
                  <div className="so-celular">Pago: <span className="num">{reais(x.pago)}</span></div></td>
                <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.indicado)}{x.empenhado > 0 && <div className="muted">empenhado {reais(x.empenhado)}</div>}</td>
                <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(x.pago)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>}
        {vis.length > qtd && <button className="link" onClick={() => setQtd(qtd + 50)}>Mostrar mais ({(vis.length - qtd).toLocaleString("pt-BR")} restantes)</button>}
        <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(data.fonte)} target="_blank" rel="noreferrer">emendas parlamentares na ALMG ↗</a>. Só indicações aprovadas; "empenhado" é o valor que o estado já reservou para pagar.</p>
      </>}
    </section>
  );
}
