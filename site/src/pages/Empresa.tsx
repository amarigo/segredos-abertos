import { Link, useParams } from "react-router-dom";
import { useMemo, useState } from "react";
import { Barras, Explain, LinkNota, Loading, useAno, useData, useTip } from "../components/ui";
import { MESES, cnpjFmt, dataBR, linkSeguro, reais, type DonoFinal, type Empresa, type NotaEmpresa, type OutraEmpresa, type Resumo } from "../data";
import { ListaDocumentos } from "../components/DocsEmendas";
import "./incentivos.css";

/** "R$ X da cota + R$ Y de emendas + R$ Z do governo federal · R$ W de renúncia fiscal" */
function recebeuTexto(o: OutraEmpresa) {
  const so = !o.emendas && !o.governo;
  const recebeu = [o.total ? `${reais(o.total)}${so ? "" : " da cota"}` : "", o.emendas ? `${reais(o.emendas)} de emendas` : "",
    o.governo ? `${reais(o.governo)} do governo federal` : ""].filter(Boolean).join(" + ");
  return [recebeu, o.renuncia ? `${reais(o.renuncia)} de renúncia fiscal` : ""].filter(Boolean).join(" · ") || reais(0);
}
import { norm } from "./Home";

export default function EmpresaPage() {
  const { cnpj = "" } = useParams();
  const { data: e, error } = useData<Empresa>(`e/${cnpj}.json`);
  if (!e) return <Loading error={error && "Esta empresa não está entre as que recebem dinheiro da cota, de emendas ou do governo federal, nem entre as que mais têm renúncia fiscal no período."} />;
  return <EmpresaAno e={e} />;
}

/** Soma de um "por_ano" e a lista dos anos, para o texto secundário dos cartões */
const somaAnos = (pa: Record<string, number>) => `${reais(Object.values(pa).reduce((a, b) => a + b, 0))} somando ${Object.keys(pa).sort().join(", ")}`;

function EmpresaAno({ e }: { e: Empresa }) {
  const { ano } = useAno();
  const emp = e.empresa;
  // O ano escolhido no topo é o número principal; o total de todos os anos aparece em segundo plano
  const cotaAno = (e.por_mes || []).filter((x) => String(x.ano) === ano);
  const cotaValor = cotaAno.reduce((a, x) => a + x.valor, 0);
  const cotaPols = new Set(cotaAno.map((x) => x.politico)).size;
  const ultimoRen = e.renuncia ? Object.keys(e.renuncia.por_ano).sort().pop() : undefined;
  return (
    <>
      <section>
        <span className="eyebrow">Empresa · CNPJ <span className="mono">{cnpjFmt(e.cnpj)}</span></span>
        <h1>{e.nome}</h1>
        {emp?.nome_fantasia && <p className="muted">Nome fantasia: {emp.nome_fantasia}</p>}
        {e.alertas.map((a) => <div className="alert" key={a} role="note"><strong>Ponto de atenção:</strong> {a}</div>)}
      </section>
      <section className="grid">
        {e.total > 0 && <div className="card stat"><span className="label">Recebeu da cota de parlamentares em {ano}</span><span className="value">{reais(cotaValor)}</span>
          <span className="hint">{cotaPols ? `de ${cotaPols} parlamentar${cotaPols > 1 ? "es" : ""}` : `nada em ${ano}`}{e.total !== cotaValor && <> · {reais(e.total)} em todos os anos</>}</span></div>}
        {e.governo && <div className="card stat"><span className="label">Recebeu do governo federal em {ano}</span><span className="value">{reais(e.governo.por_ano[ano] || 0)}</span>
          <span className="hint">compras, obras, serviços, convênios e subsídios · {somaAnos(e.governo.por_ano)}</span></div>}
        {e.renuncia && <div className="card stat"><span className="label">Deixou de pagar de impostos em {ano}</span><span className="value">{e.renuncia.por_ano[ano] != null ? reais(e.renuncia.por_ano[ano]) : "—"}</span>
          <span className="hint">{e.renuncia.por_ano[ano] == null && ultimoRen ? `A Receita ainda não publicou ${ano}. Último ano com dado: ${ultimoRen}, ${reais(e.renuncia.por_ano[ultimoRen])}. ` : "renúncia fiscal federal · "}{somaAnos(e.renuncia.por_ano)}</span></div>}
        {e.emendas && <div className="card stat"><span className="label">Recebeu de emendas parlamentares em {ano}</span><span className="value">{reais(e.emendas.por_ano[ano] || 0)}</span>
          <span className="hint">pagos pelo governo federal · {somaAnos(e.emendas.por_ano)}</span></div>}
        {emp && <>
          <div className="card stat"><span className="label">Situação na Receita</span><span className="value" style={{ fontSize: "1.3rem" }}>{emp.situacao || "—"}</span><span className="hint">Aberta em {dataBR(emp.abertura)}</span></div>
          <div className="card stat"><span className="label">Atividade</span><span style={{ fontWeight: 600 }}>{emp.atividade || "—"}</span><span className="hint">{emp.municipio}{emp.uf ? `-${emp.uf}` : ""} · {emp.porte}</span></div>
          <div className="card stat"><span className="label">Capital social</span><span className="value" style={{ fontSize: "1.3rem" }}>{reais(Number(emp.capital_social) || 0)}</span><span className="hint">{emp.natureza}</span></div>
        </>}
      </section>

      <section>
        <h2>Quem são os donos</h2>
        {!emp ? <div className="empty">Ainda não buscamos os dados desta empresa na Receita Federal.</div>
          : e.socios.length === 0 ? <Explain>A Receita não lista sócios para esta empresa. Isso é comum em empresário individual e MEI, em que o dono é a própria pessoa do nome da empresa.</Explain>
          : <Donos e={e} />}
      </section>

      {e.mesmo_endereco && e.mesmo_endereco.length > 0 && (
        <section>
          <h2>Outras fornecedoras no mesmo endereço</h2>
          <Explain>Estas empresas também recebem de parlamentares e estão registradas na Receita no mesmo endereço{emp?.endereco ? <> ({[emp.endereco.logradouro, emp.endereco.numero, emp.endereco.complemento, emp.endereco.bairro].filter(Boolean).join(", ")}, CEP {emp.endereco.cep})</> : null}. Isso pode indicar o mesmo dono ou o mesmo grupo, mas também pode ser um prédio comercial ou um escritório de contabilidade.</Explain>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Empresa</th><th>Mesmos sócios?</th><th className="r">Recebeu</th></tr></thead>
              <tbody>
                {e.mesmo_endereco.map((o) => (
                  <tr key={o.cnpj}>
                    <td><Link to={`/e/${o.cnpj}`}>{o.nome}</Link><div className="muted small mono">{cnpjFmt(o.cnpj)}</div></td>
                    <td>{o.mesmos_socios ? <strong>Sim</strong> : "Não"}</td>
                    <td className="r num">{recebeuTexto(o)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <PorAno e={e} />

      {e.governo && <Governo g={e.governo} cnpj={e.cnpj} ano={ano} />}
      {e.renuncia && <Renuncia r={e.renuncia} ano={ano} />}
      {e.emendas && <Emendas em={e.emendas} ano={ano} />}

      {e.pagadores.length > 0 && <Pagadores e={e} ano={ano} />}

      {e.total > 0 && <PorMes e={e} />}
      {e.total > 0 && <Notas e={e} />}
    </>
  );
}

/* As fontes de dinheiro público mostradas ano a ano, sempre na mesma ordem e com a mesma cor */
const SERIES = [
  { k: "governo", nome: "Pagamentos do governo federal", cor: "var(--s1)" },
  { k: "emendas", nome: "Desses, com dinheiro de emendas", cor: "var(--s3)" },
  { k: "cota", nome: "Cota de parlamentares", cor: "var(--s2)" },
  { k: "renuncia", nome: "Renúncia fiscal (imposto que deixou de pagar)", cor: "var(--c4)" },
] as const;
type Serie = (typeof SERIES)[number]["k"];

const lista = (xs: [string, number][]) => xs.map(([n, v]) => `${n} (${reais(v)})`).join(", ");

/** Quanto a empresa recebeu (ou deixou de pagar) em cada ano, com o que explica cada valor. O ano mais recente vem primeiro. */
function PorAno({ e }: { e: Empresa }) {
  const tip = useTip();
  const { ano, anos: anos_site, setAno } = useAno();
  const cota: Record<string, number> = {};
  (e.por_mes || []).forEach((x) => { cota[x.ano] = (cota[x.ano] || 0) + x.valor; });
  const valor = (a: string, k: Serie): number => k === "governo" ? e.governo?.por_ano[a] || 0 : k === "emendas" ? e.emendas?.por_ano[a] || 0
    : k === "cota" ? cota[a] || 0 : e.renuncia?.por_ano[a] || 0;
  const anos = [...new Set([...Object.keys(e.governo?.por_ano || {}), ...Object.keys(e.emendas?.por_ano || {}), ...Object.keys(cota),
    ...Object.keys(e.renuncia?.por_ano || {})])].sort().reverse();
  const series = SERIES.filter((s) => anos.some((a) => valor(a, s.k) > 0));
  if (!anos.length) return null;
  const max = Math.max(1, ...anos.flatMap((a) => series.map((s) => valor(a, s.k))));
  return (
    <section>
      <h2>Dinheiro público em {ano}</h2>
      <Explain>
        O ano escolhido no topo da página aparece primeiro; os outros anos ficam logo abaixo, cada um em separado: quanto esta empresa ou entidade recebeu e quanto deixou de pagar de impostos, e o que explica cada valor.
        As barras usam a mesma escala em todos os anos. Os pagamentos com dinheiro de emendas já fazem parte dos pagamentos do governo federal:
        aparecem à parte para mostrar qual parlamentar indicou o dinheiro. A renúncia fiscal não é um pagamento: é imposto que o governo deixou de cobrar.
      </Explain>
      <div className="legenda-anos small" aria-hidden="true">
        {series.map((s) => <span key={s.k}><i style={{ background: s.cor }} />{s.nome}</span>)}
      </div>
      {!anos.includes(ano) && <div className="empty">Nenhum dinheiro público registrado para esta empresa em {ano}. Os outros anos estão logo abaixo.</div>}
      {[ano, "outros"].map((grupo) => {
        const doGrupo = anos.filter((a) => (grupo === ano) === (a === ano));
        if (!doGrupo.length) return null;
        const blocos = doGrupo.map((a) => {
        const g = e.governo?.anos?.[a], em = e.emendas?.anos?.[a], r = e.renuncia?.anos?.[a];
        const pagadores = (e.por_mes || []).filter((x) => String(x.ano) === a);
        const porPol = new Map<string, { nome: string; valor: number }>();
        pagadores.forEach((x) => { const p = porPol.get(x.politico) || { nome: x.nome, valor: 0 }; p.valor += x.valor; porPol.set(x.politico, p); });
        const topPol = [...porPol.entries()].sort((x, y) => y[1].valor - x[1].valor).slice(0, 3);
        return (
          <div className="ano-bloco" key={a}>
            <h3>{a}</h3>
            <div className="ano-barras">
              {series.map((s) => {
                const v = valor(a, s.k);
                return (
                  <div className="ano-barra" key={s.k}>
                    <span className="small">{s.nome}</span>
                    <span className="num small">{v ? reais(v) : "–"}</span>
                    <div className="track" onMouseMove={(ev) => tip.show(ev, `${a} · ${s.nome}: ${reais(v)}`)} onMouseLeave={tip.hide}>
                      <div className="fill" style={{ width: `${(v / max) * 100}%`, background: s.cor }} />
                    </div>
                  </div>
                );
              })}
            </div>
            <ul className="ano-explica small">
              {g && g.cats.length > 0 && <li><strong>Pelo que o governo pagou:</strong> {lista(g.cats)}{g.orgaos.length > 0 && <>. Quem pagou: {lista(g.orgaos)}</>}.</li>}
              {em && em.autores.length > 0 && <li><strong>Emendas de:</strong> {em.autores.map((x, k) => (
                <span key={k}>{k > 0 && ", "}{x.politico ? <Link to={`/p/${x.politico}`}>{x.nome}</Link> : x.nome}{x.partido && ` (${x.partido})`} {reais(x.valor)}</span>
              ))}. <Link to="/emendas" onClick={() => anos_site.includes(a) && setAno(a)}>Ver as emendas de {a}</Link>.</li>}
              {topPol.length > 0 && <li><strong>Cota paga por:</strong> {topPol.map(([pid, p], k) => (
                <span key={pid}>{k > 0 && ", "}<Link to={`/p/${pid}`}>{p.nome}</Link> {reais(p.valor)}</span>
              ))}{porPol.size > 3 && ` e mais ${porPol.size - 3}`}.</li>}
              {r && r.beneficios.length > 0 && <li><strong>Benefícios fiscais:</strong> {lista(r.beneficios)}.</li>}
            </ul>
          </div>
        );
        });
        return grupo === ano ? <div key={grupo}>{blocos}</div>
          : <details key={grupo} className="anos-outros"><summary>Ver os outros anos ({doGrupo.join(", ")})</summary>{blocos}</details>;
      })}
      {tip.el}
      <details className="small">
        <summary>Ver todos os anos numa tabela, com o total</summary>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Ano</th>{series.map((s) => <th key={s.k} className="r">{s.nome}</th>)}</tr></thead>
            <tbody>{anos.map((a) => <tr key={a} className={a === ano ? "atual" : undefined}><td>{a}</td>{series.map((s) => <td key={s.k} className="r num">{reais(valor(a, s.k), true)}</td>)}</tr>)}
              <tr><td><strong>Todos os anos</strong></td>{series.map((s) => <td key={s.k} className="r num"><strong>{reais(anos.reduce((t, a) => t + valor(a, s.k), 0), true)}</strong></td>)}</tr></tbody>
          </table>
        </div>
      </details>
      <p className="small muted">
        Fontes: <a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${e.cnpj}`} target="_blank" rel="noreferrer">pagamentos e emendas no Portal da Transparência ↗</a>
        {e.renuncia && <> · <a href={linkSeguro(e.renuncia.fonte)} target="_blank" rel="noreferrer">renúncia fiscal (Receita Federal, pelo Portal) ↗</a></>}
        {e.total > 0 && <> · cota parlamentar: notas oficiais da Câmara e do Senado, listadas abaixo</>}.
        Os pagamentos do governo de um ano podem estar incompletos enquanto a leitura dos arquivos diários do Portal não termina; a página de <Link to="/incentivos">incentivos</Link> mostra quantos dias de cada ano já foram lidos.
      </p>
    </section>
  );
}

/** Linha com os valores de cada ano, o escolhido em negrito, e a soma no fim (informação secundária) */
function AnosLinha({ pa, ano }: { pa: Record<string, number>; ano: string }) {
  const anos = Object.entries(pa).sort();
  if (!anos.length) return null;
  return (
    <p className="small muted anos-linha">
      Cada ano: {anos.map(([a, v], i) => <span key={a}>{i > 0 && " · "}{a === ano ? <strong>{a}: {reais(v)}</strong> : `${a}: ${reais(v)}`}</span>)}
      {anos.length > 1 && <> · todos os anos somados: {reais(anos.reduce((t, [, v]) => t + v, 0))}</>}
    </p>
  );
}

/** O detalhe do ano escolhido; sem ele (dados antigos), o de todos os anos somados, dito no título */
function TituloAno({ base, ano, temAno }: { base: string; ano: string; temAno: boolean }) {
  return <h2>{base}{temAno ? ` em ${ano}` : ": todos os anos somados"}</h2>;
}

function Governo({ g, cnpj, ano }: { g: NonNullable<Empresa["governo"]>; cnpj: string; ano: string }) {
  const d = g.anos?.[ano];
  const temAno = !!g.anos;
  const cats = temAno ? d?.cats || [] : g.cats, orgaos = temAno ? d?.orgaos || [] : g.orgaos;
  return (
    <section>
      <TituloAno base="Pagamentos do governo federal" ano={ano} temAno={temAno} />
      <Explain>
        O que o governo federal pagou a esta empresa ou entidade por compras, obras, serviços, convênios e subsídios (salários e dívida pública não entram). <Link to="/incentivos">Comparar com as outras</Link>.
      </Explain>
      <AnosLinha pa={g.por_ano} ano={ano} />
      {temAno && !d ? <div className="empty">Nenhum pagamento do governo federal a esta empresa em {ano}.</div> : (
        <div className="two">
          <div><h3>Para quê</h3><Barras itens={cats.map(([c, v]) => ({ label: c, valor: v, cor: "var(--s1)" }))} /></div>
          <div><h3>Quem pagou</h3><Barras itens={orgaos.map(([o, v]) => ({ label: o, valor: v, cor: "var(--s3)" }))} /></div>
        </div>
      )}
      <p className="small"><a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${cnpj}`} target="_blank" rel="noreferrer">Todos os pagamentos, contratos e convênios no Portal da Transparência ↗</a></p>
    </section>
  );
}

function Renuncia({ r, ano }: { r: NonNullable<Empresa["renuncia"]>; ano: string }) {
  const d = r.anos?.[ano];
  const temAno = !!r.anos;
  const ben = temAno ? d?.beneficios || [] : r.beneficios;
  return (
    <section>
      <TituloAno base="Renúncia fiscal" ano={ano} temAno={temAno} />
      <Explain>
        Por causa de benefícios fiscais, esta empresa deixou de pagar impostos federais, segundo a Receita Federal. É dinheiro que o governo deixa de arrecadar. Os anos são anos-calendário, e a Receita publica cada ano com atraso.
      </Explain>
      <AnosLinha pa={r.por_ano} ano={ano} />
      {temAno && !d ? <div className="empty">A Receita não tem renúncia fiscal desta empresa em {ano} (ou ainda não publicou esse ano).</div> : <>
        <h3>Quais benefícios</h3>
        <Barras itens={ben.map(([b, v]) => ({ label: b, valor: v, cor: "var(--c4)" }))} />
      </>}
      <p className="small"><a href={linkSeguro(r.fonte)} target="_blank" rel="noreferrer">Consultar a renúncia por empresa no Portal da Transparência ↗</a></p>
    </section>
  );
}

function Emendas({ em, ano }: { em: NonNullable<Empresa["emendas"]>; ano: string }) {
  const d = em.anos?.[ano];
  const temAno = !!em.anos;
  const autores = temAno ? d?.autores || [] : em.autores, orgaos = temAno ? d?.orgaos || [] : em.orgaos;
  const docsAno = em.docs.filter((x) => String(x.data || "").startsWith(ano));
  return (
    <section>
      <TituloAno base="Emendas parlamentares" ano={ano} temAno={temAno} />
      <Explain>
        Esta empresa recebeu pagamentos do governo federal feitos com dinheiro de emendas: o parlamentar indica a emenda e um ministério ou órgão faz a compra ou a contratação.
      </Explain>
      <AnosLinha pa={em.por_ano} ano={ano} />
      {temAno && !d ? <div className="empty">Nenhum pagamento de emenda a esta empresa em {ano}.</div> : <>
        <h3>De quem eram as emendas</h3>
        <Barras itens={autores.slice(0, 20).map((a) => ({
          label: a.politico ? <Link to={`/p/${a.politico}`}>{a.nome} {a.partido && <span className="muted small">({a.partido})</span>}</Link>
            : <span>{a.nome} {a.partido && <span className="muted small">({a.partido})</span>}</span>,
          valor: a.valor,
        }))} />
        {orgaos.length > 0 && <>
          <h3>Quem pagou</h3>
          <Barras itens={orgaos.slice(0, 8).map(([o, v]) => ({ label: o, valor: v, cor: "var(--s3)" }))} />
        </>}
      </>}
      <h3>Documentos de pagamento de {ano}</h3>
      <ListaDocumentos docs={docsAno} comFavorecido={false} />
      {docsAno.length < em.docs.length && <details className="small">
        <summary>Ver os documentos dos outros anos ({(em.docs.length - docsAno.length).toLocaleString("pt-BR")})</summary>
        <ListaDocumentos docs={em.docs.filter((x) => !String(x.data || "").startsWith(ano))} comFavorecido={false} />
      </details>}
      <p className="muted small">Cada pagamento tem dois links oficiais do Portal da Transparência: o documento de pagamento e a nota de empenho, que é a reserva do dinheiro e diz de qual emenda ele saiu.</p>
    </section>
  );
}

/** Quem pagou com a cota no ano escolhido; o ranking de todos os anos fica num "ver mais" */
function Pagadores({ e, ano }: { e: Empresa; ano: string }) {
  const info = new Map(e.pagadores.map((p) => [p.politico, p]));
  const porPol = new Map<string, number>();
  (e.por_mes || []).filter((x) => String(x.ano) === ano).forEach((x) => porPol.set(x.politico, (porPol.get(x.politico) || 0) + x.valor));
  const doAno = [...porPol.entries()].sort((a, b) => b[1] - a[1]);
  const rotulo = (pid: string, nome: string) => { const p = info.get(pid); return <Link to={`/p/${pid}`}>{p?.nome || nome} {p && <span className="muted small">({p.partido}-{p.uf})</span>}</Link>; };
  const nomeDe = (pid: string) => (e.por_mes || []).find((x) => x.politico === pid)?.nome || pid;
  return (
    <section>
      <h2>{e.emendas ? `Quem pagou com a cota em ${ano}` : `Quem pagou em ${ano}`}</h2>
      {!e.por_mes ? null : !doAno.length ? <div className="empty">Nenhum parlamentar pagou esta empresa com a cota em {ano}.</div>
        : <Barras itens={doAno.slice(0, 30).map(([pid, v]) => ({ label: rotulo(pid, nomeDe(pid)), valor: v }))} />}
      <details className="small">
        <summary>{e.por_mes ? "Ver quem pagou somando todos os anos" : "Quem pagou (todos os anos)"}</summary>
        <Barras itens={e.pagadores.slice(0, 30).map((p) => ({ label: rotulo(p.politico, p.nome), valor: p.valor }))} />
      </details>
    </section>
  );
}

function PorMes({ e }: { e: Empresa }) {
  const { ano } = useAno();
  const linhas = useMemo(() => {
    const m = new Map<string, { nome: string; meses: number[]; total: number }>();
    (e.por_mes || []).filter((x) => String(x.ano) === ano).forEach((x) => {
      const l = m.get(x.politico) || { nome: x.nome, meses: Array(12).fill(0), total: 0 };
      l.meses[x.mes - 1] += x.valor; l.total += x.valor; m.set(x.politico, l);
    });
    return [...m.entries()].sort((a, b) => b[1].total - a[1].total);
  }, [e, ano]);
  if (!e.por_mes) return null;
  return (
    <section>
      <h2>Quanto cada parlamentar pagou por mês em {ano}</h2>
      {!linhas.length ? <div className="empty">Nenhum pagamento a esta empresa em {ano}. Escolha outro ano no topo da página.</div> : (
        <div className="table-wrap">
          <table className="small">
            <thead><tr><th>Parlamentar</th>{MESES.map((m) => <th key={m} className="r">{m}</th>)}<th className="r">Total</th></tr></thead>
            <tbody>
              {linhas.map(([pid, l]) => (
                <tr key={pid}>
                  <td><Link to={`/p/${pid}`}>{l.nome}</Link></td>
                  {l.meses.map((v, i) => <td key={i} className="r num">{v ? Math.round(v).toLocaleString("pt-BR") : <span className="muted">–</span>}</td>)}
                  <td className="r num"><strong>{reais(l.total)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small">Valores em reais, arredondados.</p>
    </section>
  );
}

function Notas({ e }: { e: Empresa }) {
  const { ano } = useAno();
  const n_ano = e.notas_por_ano?.[ano] || 0;
  const { data: notas, error } = useData<NotaEmpresa[]>(n_ano ? `e/notas/${e.cnpj}-${ano}.json` : null);
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const nomes = useMemo(() => new Map((pols || []).map((p) => [p.id, p.nome])), [pols]);
  const [q, setQ] = useState("");
  const [n, setN] = useState(100);
  const lista = useMemo(() => (notas || []).filter((x) => !q || norm(nomes.get(x[1]) || "").includes(norm(q))), [notas, q, nomes]);
  const semLink = (notas || []).filter((x) => !x[4]).length;
  return (
    <section>
      <h2>Todas as notas fiscais de {ano}{n_ano ? ` (${n_ano.toLocaleString("pt-BR")})` : ""}</h2>
      {!n_ano ? <div className="empty">Nenhuma nota desta empresa em {ano}. Escolha outro ano no topo da página.</div>
        : !notas ? <Loading error={error} /> : <>
        <div className="search"><input aria-label="Filtrar por parlamentar" value={q} onChange={(ev) => { setQ(ev.target.value); setN(100); }} placeholder="Filtrar por parlamentar" /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="so-largo">Data</th><th>Parlamentar e tipo de gasto</th><th className="r">Valor</th><th className="so-largo">Nota</th></tr></thead>
            <tbody>
              {lista.slice(0, n).map((x, i) => (
                <tr key={i}>
                  <td className="num so-largo">{dataBR(x[0])}</td>
                  <td><Link to={`/p/${x[1]}`}>{nomes.get(x[1]) || x[1]}</Link><div className="small muted">{x[2]}</div>{x[6] && <div className="small">{x[6]}</div>}
                    <div className="small so-celular"><span className="num muted">{dataBR(x[0])}</span> · <LinkNota url={x[4]} link={x[5] || (x[4] ? "nota" : "")} /></div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x[3], true)}</td>
                  <td className="small so-largo"><LinkNota url={x[4]} link={x[5] || (x[4] ? "nota" : "")} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {lista.length > n && <button className="link" onClick={() => setN(n + 200)}>Mostrar mais notas ({(lista.length - n).toLocaleString("pt-BR")} restantes)</button>}
        <p className="muted small">Cada despesa tem um link oficial. "Abrir nota" mostra a imagem da nota fiscal. Passagens compradas pelo sistema da Câmara e contas de telefone não têm imagem: "Ver detalhe na Câmara" abre a página oficial da despesa. Cerca de 1 nota em 1.000 está nos dados da Câmara sem o PDF no site dela (o link oficial dá erro 404): nesses casos o link também abre a página oficial da despesa. O Senado não publica as notas: "Ver na lista do Senado" abre a lista oficial de despesas do senador.{semLink > 0 && ` ${semLink.toLocaleString("pt-BR")} despesa${semLink > 1 ? "s" : ""} sem nenhum link oficial.`}</p>
      </>}
    </section>
  );
}

const FIM: Record<DonoFinal["fim"], string> = {
  pessoa: "",
  estrangeiro: "Sócio no exterior. A Receita não mostra quem está por trás.",
  sem_socios: "A Receita não lista os sócios desta empresa (comum em sociedade anônima, que tem acionistas em vez de sócios).",
  sem_dados: "Não encontramos esta empresa na base da Receita.",
  limite: "Caminho longo demais. Paramos depois de 5 empresas.",
  ciclo: "Esta empresa é sócia de uma empresa que já apareceu antes no caminho (participação cruzada).",
};

/* Árvore de donos: a empresa no topo; abaixo de cada empresa, quem é dono dela */
interface No { chave: string; nome: string; tipo: "raiz" | "empresa" | "pessoa" | "estrangeiro"; doc: string; papel: string; motivo?: string; filhos: No[] }

function arvore(e: Empresa): { raiz: No; donos: DonoFinal[] } {
  const donos: DonoFinal[] = e.donos_finais && e.donos_finais.length ? e.donos_finais
    : e.socios.map((s) => ({ nome: s.nome, doc: s.doc, tipo: s.tipo || "pessoa", qualificacao: s.qualificacao, pais: "",
      cadeia: s.tipo === "empresa" ? [{ cnpj: s.doc, nome: s.nome, qualificacao: s.qualificacao }] : [],
      fim: (s.tipo === "empresa" ? "sem_dados" : s.tipo === "estrangeiro" ? "estrangeiro" : "pessoa") as DonoFinal["fim"],
      outras_empresas: s.outras_empresas }));
  const raiz: No = { chave: "raiz", nome: e.nome, tipo: "raiz", doc: e.cnpj, papel: "", filhos: [] };
  for (const d of donos) {
    let atual = raiz;
    for (const c of d.cadeia) {
      let f = atual.filhos.find((x) => x.chave === `PJ${c.cnpj}`);
      if (!f) { f = { chave: `PJ${c.cnpj}`, nome: c.nome, tipo: "empresa", doc: c.cnpj, papel: c.qualificacao, filhos: [] }; atual.filhos.push(f); }
      atual = f;
    }
    if (d.fim === "pessoa" || d.fim === "estrangeiro") {
      atual.filhos.push({ chave: `${d.nome}|${d.doc}`, nome: d.nome, tipo: d.fim, doc: d.fim === "estrangeiro" ? d.pais : d.doc, papel: d.qualificacao, filhos: [] });
    } else {
      atual.motivo = FIM[d.fim];
    }
  }
  return { raiz, donos };
}

const juntar = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} e ${xs[xs.length - 1]}`);

const ROTULO: Record<No["tipo"], string> = { raiz: "Esta empresa", empresa: "Empresa sócia", pessoa: "Pessoa", estrangeiro: "No exterior" };

function NoFluxo({ n }: { n: No }) {
  return (
    <li>
      <div className={`no no-${n.tipo}${n.motivo ? " no-parou" : ""}`}>
        <span className="no-tipo">{ROTULO[n.tipo]}{n.papel ? ` · ${n.papel}` : ""}</span>
        <strong>{n.nome}</strong>
        {n.doc && <span className="no-doc mono">{n.tipo === "raiz" || n.tipo === "empresa" ? cnpjFmt(n.doc) : n.doc}</span>}
        {n.motivo && <span className="no-motivo">{n.motivo}</span>}
      </div>
      {n.filhos.length > 0 && <ul>{n.filhos.map((f) => <NoFluxo key={f.chave} n={f} />)}</ul>}
    </li>
  );
}

function Donos({ e }: { e: Empresa }) {
  const { raiz, donos } = arvore(e);
  const pessoas = donos.filter((d) => d.fim === "pessoa");
  const viaHolding = pessoas.filter((d) => d.cadeia.length > 0);
  const exterior = donos.filter((d) => d.fim === "estrangeiro").length;
  const parou = donos.some((d) => d.fim !== "pessoa" && d.fim !== "estrangeiro");
  const comOutras = pessoas.filter((d) => d.outras_empresas.length);
  return (
    <>
      <div className="lead-donos">
        <p><strong>{e.nome}</strong> pertence a {pessoas.length === 0 ? "nenhuma pessoa identificada" : <><strong>{pessoas.length} pessoa{pessoas.length > 1 ? "s" : ""}</strong>: {juntar(pessoas.map((d) => d.nome))}</>}.</p>
        {viaHolding.length > 0 && (
          <ul>
            {viaHolding.map((d) => <li key={`${d.nome}|${d.doc}`}><strong>{d.nome}</strong> é dono(a) por meio de {d.cadeia.length > 1 ? "uma sequência de empresas" : "outra empresa"}: {d.cadeia.slice().reverse().map((c) => c.nome).join(", que é dona de ")}.</li>)}
          </ul>
        )}
        {exterior > 0 && <p>Também há {exterior} sócio{exterior > 1 ? "s" : ""} no exterior. A Receita não mostra quem está por trás.</p>}
        {parou && <p>Em parte do caminho a Receita não informa os donos (caixas tracejadas).</p>}
      </div>
      <p className="muted small">Leia de cima para baixo: abaixo de cada empresa estão os donos dela. Quando o dono é outra empresa, buscamos os donos dessa empresa também, até chegar às pessoas.</p>
      <div className="fluxo" role="img" aria-label={`Organograma dos donos de ${e.nome}`}>
        <ul><NoFluxo n={raiz} /></ul>
      </div>
      <div className="fluxo-legenda small">
        <span><i className="no-empresa" />Empresa</span><span><i className="no-pessoa" />Pessoa</span><span><i className="no-estrangeiro" />No exterior</span><span><i className="no-parou" />Busca parou</span>
      </div>
      {comOutras.length > 0 && (
        <>
          <h3>Outras empresas dos mesmos donos que recebem dinheiro público</h3>
          <ul className="donos">
            {comOutras.map((d) => (
              <li key={`${d.nome}|${d.doc}`} className="card">
                <strong>{d.nome}</strong>
                <div className="small">{d.outras_empresas.map((o, k) => (
                  <span key={o.cnpj}>{k > 0 && ", "}<Link to={`/e/${o.cnpj}`}>{o.nome}</Link> <span className="muted num">({recebeuTexto(o)})</span></span>
                ))}</div>
              </li>
            ))}
          </ul>
        </>
      )}
      <details className="small">
        <summary>Ver a lista de sócios como aparece na Receita</summary>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Sócio</th><th>Função</th><th>Desde</th></tr></thead>
            <tbody>
              {e.socios.map((s, i) => (
                <tr key={i}>
                  <td>{s.nome}{s.tipo === "empresa" && <> <span className="chip">empresa</span></>}{s.tipo === "estrangeiro" && <> <span className="chip">exterior</span></>}<div className="muted small mono">{s.tipo === "empresa" ? cnpjFmt(s.doc) : s.doc}</div></td>
                  <td className="small">{s.qualificacao}</td>
                  <td className="num">{dataBR(s.entrada)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="muted small">A Receita esconde parte do CPF dos sócios. Por isso ligamos empresas pelo nome do sócio mais os dígitos visíveis do CPF. Homônimos raros podem aparecer.</p>
    </>
  );
}
