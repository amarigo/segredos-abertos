import { Fragment, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Abrir, Barras, Explain, GastoMensal, Loading, OndeVer, useData } from "../components/ui";
import { norm } from "./Home";
import { cnpjFmt, dataBR, linkSeguro, reais, type AlmgIndice, type DeputadoEstadual, type NotaAlmg, type ProposicaoAlmg, type VerbaAno } from "../data";
import { Metrica } from "./Atuacao";
import { FotoPerfil } from "../components/Foto";
import { AvisosFim } from "../components/Selo";

type Aba = "gastos" | "atuacao" | "emendas";
const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

/** Página de um deputado estadual: verba indenizatória, projetos e emendas, com link para a ALMG */
export default function DeputadoEstadualPage() {
  const { id = "" } = useParams();
  const { data: d, error } = useData<DeputadoEstadual>(/^\d{1,10}$/.test(id) ? `almg/d/${id}.json` : null);
  const { data: idx } = useData<AlmgIndice>("almg/deputados.json");
  const [params, setParams] = useSearchParams();
  const aba = (["atuacao", "emendas"].includes(params.get("aba") || "") ? params.get("aba") : "gastos") as Aba;
  const anosDep = Object.keys(d?.anos || {}).sort();
  const anoSel = params.get("ano") || "";
  const ano = anosDep.includes(anoSel) ? anoSel : anosDep[anosDep.length - 1] || "";
  const mudar = (k: string, v: string) => { const p = new URLSearchParams(params); p.set(k, v); setParams(p, { replace: true }); };
  if (!/^\d{1,10}$/.test(id)) return <div className="empty">Deputado não encontrado. <Link to="/assembleia">Ver todos os deputados estaduais</Link>.</div>;
  if (!d) return <Loading error={error} />;
  const a = d.anos[ano];
  // Comparação só com quem está no cargo hoje (quem saiu tem meses sem mandato), como a mediana da lista
  const colegas = (idx?.deputados || []).filter((x) => x.em_exercicio !== false).map((x) => x.por_ano[ano]).filter(Boolean);
  const primeiro = d.nome.split(" ")[0];
  return (
    <>
      <section className="profile">
        <FotoPerfil url={d.foto} nome={d.nome} />
        <div>
          <span className="eyebrow">Deputado estadual · Assembleia de Minas Gerais</span>
          <h1>{d.nome}</h1>
          <div className="tags">
            <span className="chip">{d.partido}</span>
            <a className="chip" href={linkSeguro(d.url)} target="_blank" rel="noreferrer">Página na ALMG ↗</a>
          </div>
          {d.em_exercicio === false && <p className="small muted" role="note">
            <strong className="fora-cargo">Fora do cargo hoje</strong>
            <br /><span>Teve mandato nesta legislatura e já saiu do cargo. Os gastos, projetos e emendas abaixo são do período em que esteve no cargo.</span>
          </p>}
          {d.outros_nomes?.length ? <p className="small muted"><span>Também aparece nos dados oficiais como</span> {d.outros_nomes.join(", ")}</p> : null}
        </div>
      </section>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={aba === "gastos"} onClick={() => mudar("aba", "gastos")}>Gastos</button>
          <button role="tab" aria-selected={aba === "atuacao"} onClick={() => mudar("aba", "atuacao")}>Atuação</button>
          <button role="tab" aria-selected={aba === "emendas"} onClick={() => mudar("aba", "emendas")}>Emendas</button>
        </div>
        {anosDep.length > 0 && (
          <label className="ano-sel"><span className="muted small">Ano</span>
            <select id="ano-deputado" value={ano} onChange={(e) => mudar("ano", e.target.value)}>
              {anosDep.slice().reverse().map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
        )}
      </div>
      {!a ? <div className="empty">Não há dados de {d.nome} nesta legislatura.</div>
        : aba === "gastos" ? <Gastos d={d} ano={ano} colegas={colegas.map((c) => c.verba)} primeiro={primeiro} />
        : aba === "atuacao" ? <AtuacaoAlmg d={d} ano={ano} colegas={colegas} primeiro={primeiro} />
        : <EmendasDep d={d} ano={ano} colegas={colegas.map((c) => c.emendas_indicado)} primeiro={primeiro} />}
    </>
  );
}

const linkCnpj = (cnpj: string) => `https://portaldatransparencia.gov.br/pessoa-juridica/${cnpj}`;

function Gastos({ d, ano, colegas, primeiro }: { d: DeputadoEstadual; ano: string; colegas: number[]; primeiro: string }) {
  const [tipo, setTipo] = useState("");
  const [mes, setMes] = useState(0);
  const [busca, setBusca] = useState("");
  const [todasMaiores, setTodasMaiores] = useState(false);
  // Nota aberta para ver o detalhe aqui mesmo (sem ir ao site da ALMG) e o jeito de agrupar a lista completa
  const [aberta, setAberta] = useState<NotaAlmg | null>(null);
  const [agrupar, setAgrupar] = useState<"mes" | "tipo">("mes");
  const v = d.anos[ano]?.verba;
  if (!v) return <div className="empty">A ALMG não publicou gastos da verba indenizatória de {d.nome} em {ano}.</div>;
  const urlAlmg = linkSeguro(d.url_verba || `https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/detalhe.html?id=${d.id}`);
  // Filtros: tipo de despesa, mês e nome ou CNPJ de quem emitiu a nota. Valem para as duas listas e para os grupos.
  const notas = v.notas.filter((n) => (!tipo || n.tipo === tipo) && (!mes || n.mes === mes)
    && (!busca || norm(`${n.fornecedor} ${n.cnpj} ${n.numero || ""}`).includes(norm(busca))));
  const filtrando = !!(tipo || mes || busca);
  // "Quem recebeu" recalculado das notas filtradas; sem filtro, usa a lista pronta (que conta todas as notas, mesmo se as notas vierem cortadas)
  const forn = filtrando ? Object.values(notas.reduce((acc, n) => {
    const k = n.cnpj || `${n.pf ? "pf" : "nome"}:${n.fornecedor}`;
    const f = (acc[k] ||= { nome: n.fornecedor, cnpj: n.cnpj, pf: n.pf, valor: 0, n: 0 });
    f.valor += n.valor; f.n += 1;
    return acc;
  }, {} as Record<string, VerbaAno["fornecedores"][number]>)).sort((a, b) => b.valor - a.valor) : v.fornecedores;
  const totalFiltrado = notas.reduce((a, n) => a + n.valor, 0);
  const porData = (a: NotaAlmg, b: NotaAlmg) => a.data.localeCompare(b.data) || a.tipo.localeCompare(b.tipo);
  // Lista completa: mês a mês, como a prestação de contas da ALMG (o mês mais novo primeiro), ou por tipo de despesa
  const grupos = agrupar === "mes"
    ? [...new Set(notas.map((n) => n.mes))].sort((a, b) => b - a).map((m) => ({ chave: `m${m}`, nome: `${MESES[m - 1][0].toUpperCase()}${MESES[m - 1].slice(1)} de ${ano}`, notas: notas.filter((n) => n.mes === m).sort(porData) }))
    : v.tipos.map((t) => ({ chave: t.tipo, nome: t.tipo, notas: notas.filter((n) => n.tipo === t.tipo).sort(porData) })).filter((g) => g.notas.length);
  const abrir = (n: NotaAlmg) => setAberta(aberta === n ? null : n);
  const detalhe = (n: NotaAlmg, colunas: number) => aberta === n && (
    <tr className="nota-aberta"><td colSpan={colunas}><NotaDetalhe n={n} ano={ano} todas={v.notas} procurar={(x) => { setBusca(x); setAberta(null); }} /></td></tr>
  );
  const mesesNotas = [...new Set(v.notas.map((n) => n.mes))].sort((a, b) => a - b);
  const notasCortadas = v.notas.length < v.n_notas;
  return (
    <>
      <section>
        <h2>Verba indenizatória em {ano}</h2>
        <Explain>Além do salário, cada deputado estadual pode pedir reembolso de despesas do mandato: aluguel de escritório, combustível, divulgação, consultorias. Ele apresenta a nota fiscal e a Assembleia devolve o dinheiro. É o equivalente estadual da cota parlamentar dos deputados federais.</Explain>
        <div className="atu-grade">
          <Metrica nome="Total reembolsado" quem="deputados estaduais" eu={primeiro} v={v.total} todos={colegas} tipico="Deputado típico" fmt={(x) => reais(x)}
            explica={`${v.n_notas} notas pagas a ${v.n_fornecedores} fornecedores.`} />
        </div>
      </section>
      <section>
        <h2>Em que gastou</h2>
        <p className="muted small">Clique num tipo de despesa para ver só as notas dele.</p>
        <Barras rosca={{ titulo: `Verba indenizatória em ${ano}, por tipo de gasto`, total: v.total, paleta: true }}
          itens={v.tipos.map((t) => ({ nome: t.tipo, label: <button className="link" onClick={() => setTipo(tipo === t.tipo ? "" : t.tipo)} aria-pressed={tipo === t.tipo} style={tipo === t.tipo ? { fontWeight: 800 } : undefined}>{t.tipo}</button>, valor: t.valor }))} />
      </section>
      <section>
        <h2>Procurar nas notas</h2>
        <div className="search">
          <input id="busca-nota" aria-label="Fornecedor, CNPJ ou número da nota" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Fornecedor, CNPJ ou número da nota" />
          <select id="filtro-tipo-nota" aria-label="Tipo de despesa" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="">Todos os tipos de despesa</option>{v.tipos.map((t) => <option key={t.tipo}>{t.tipo}</option>)}
          </select>
          <select id="filtro-mes-nota" aria-label="Mês" value={mes} onChange={(e) => setMes(Number(e.target.value))}>
            <option value={0}>O ano todo</option>{mesesNotas.map((m) => <option key={m} value={m}>{MESES[m - 1]}</option>)}
          </select>
        </div>
        {filtrando && <p className="small">{notas.length} nota{notas.length === 1 ? "" : "s"}, <strong className="num">{reais(totalFiltrado, true)}</strong>. <button className="link" onClick={() => { setTipo(""); setMes(0); setBusca(""); }}>Limpar filtros</button></p>}
        <div className="grid grid-2 lado-a-lado">
          <div>
            <h3>Quem recebeu</h3>
            <p className="muted small">Empresas e pessoas que emitiram as notas. De pessoa física não mostramos o CPF.</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Fornecedor</th><th className="r">Valor</th></tr></thead>
                <tbody>
                  {forn.slice(0, 15).map((f, i) => (
                    <tr key={i}>
                      <td><button className="link" onClick={() => setBusca(f.cnpj || f.nome)}>{f.nome}</button>
                        <div className="muted small mono">{f.cnpj ? <a href={linkCnpj(f.cnpj)} target="_blank" rel="noreferrer">CNPJ {cnpjFmt(f.cnpj)} ↗</a> : f.pf ? <span className="pf-tag">Pessoa física</span> : ""}</div></td>
                      <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(f.valor)}<div className="muted small">{f.n} nota{f.n > 1 ? "s" : ""}</div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {forn.length > 15 && <p className="muted small">Mostrando os 15 que mais receberam, de {filtrando ? forn.length : v.n_fornecedores}. Use a busca para achar outro.</p>}
          </div>
          <div>
            <h3>Maiores despesas</h3>
            <p className="muted small">As notas de maior valor. Clique numa nota para ver todos os dados dela.</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Nota</th><th className="r">Valor</th></tr></thead>
                <tbody>
                  {notas.slice(0, todasMaiores ? 100 : 15).map((n, i) => (
                    <Fragment key={i}>
                      <tr>
                        <td><button className="link nota-abrir" aria-expanded={aberta === n} onClick={() => abrir(n)}>{n.fornecedor}</button>{n.pf && <span className="pf-tag small"> (pessoa física)</span>}
                          <div className="small muted">{n.tipo}</div>
                          <div className="small muted num">{dataBR(n.data)}{n.numero ? ` · nota nº ${n.numero}` : ""}</div></td>
                        <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(n.valor, true)}</td>
                      </tr>
                      {detalhe(n, 2)}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            {notas.length > 15 && <button className="link small" onClick={() => setTodasMaiores(!todasMaiores)}>{todasMaiores ? "Mostrar menos" : `Mostrar mais (${Math.min(100, notas.length)})`}</button>}
          </div>
        </div>
        <h3>Gasto mês a mês</h3>
        <GastoMensal meses={filtrando ? Array.from({ length: 12 }, (_, k) => ({ mes: k + 1, valor: notas.filter((n) => n.mes === k + 1).reduce((a, n) => a + n.valor, 0) })) : v.meses} ano={ano} cor="var(--s2)" />
      </section>
      <section id="todas-as-notas">
        <h2>Todas as notas de {ano}</h2>
        <Explain>Cada nota que {primeiro} apresentou à Assembleia em {ano}, com quem emitiu, o CNPJ, a data, o número e o valor reembolsado. Clique numa nota para ver todos os dados dela aqui mesmo. A busca e os filtros acima valem também para esta lista.</Explain>
        <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
          <div className="toggle" role="group" aria-label="Agrupar as notas">
            <button aria-pressed={agrupar === "mes"} onClick={() => setAgrupar("mes")}>Mês a mês</button>
            <button aria-pressed={agrupar === "tipo"} onClick={() => setAgrupar("tipo")}>Por tipo de despesa</button>
          </div>
          <button className="btn alt" onClick={() => baixarNotas(notas, `verba-indenizatoria-almg-${d.id}-${ano}${filtrando ? "-filtrada" : ""}.csv`)}>Baixar {filtrando ? "estas" : "todas as"} notas (planilha)</button>
        </div>
        {notasCortadas && <p className="muted small">Este arquivo traz só as {v.notas.length} maiores notas do ano. A lista completa aparece na próxima atualização.</p>}
        {!grupos.length && <p className="muted small">Nenhuma nota com esses filtros.</p>}
        {grupos.map((g, gi) => {
          const soma = g.notas.reduce((a, n) => a + n.valor, 0);
          return (
            <Abrir key={`${agrupar}-${g.chave}-${filtrando}`} aberto={gi === 0} titulo={<span className="row" style={{ justifyContent: "space-between", gap: 8, display: "inline-flex", width: "calc(100% - 24px)" }}><span>{g.nome} <span className="muted small">({g.notas.length} nota{g.notas.length === 1 ? "" : "s"})</span></span><span className="num chip">{reais(soma, true)}</span></span>}>
              <div className="table-wrap">
                <table className="small">
                  <thead><tr><th>Emitente</th><th className="so-largo">{agrupar === "mes" ? "Tipo" : "CNPJ"}</th><th>Data</th><th className="so-largo">Número</th><th className="r">Valor</th></tr></thead>
                  <tbody>{g.notas.map((n, i) => (
                    <Fragment key={i}>
                      <tr>
                        <td><button className="link nota-abrir" aria-expanded={aberta === n} onClick={() => abrir(n)}>{n.fornecedor}</button>{n.pf && <span className="pf-tag"> (pessoa física)</span>}
                          <div className="so-celular muted mono">{n.cnpj ? cnpjFmt(n.cnpj) : ""}{n.numero ? ` · nº ${n.numero}` : ""}</div>
                          {agrupar === "mes" && <div className="muted so-celular">{n.tipo}</div>}</td>
                        <td className="so-largo">{agrupar === "mes" ? n.tipo : <span className="mono">{n.cnpj ? cnpjFmt(n.cnpj) : n.pf ? "Pessoa física" : "—"}</span>}</td>
                        <td className="num" style={{ whiteSpace: "nowrap" }}>{dataBR(n.data)}</td>
                        <td className="so-largo mono">{n.numero || "—"}</td>
                        <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(n.valor, true)}</td>
                      </tr>
                      {detalhe(n, 5)}
                    </Fragment>
                  ))}</tbody>
                </table>
              </div>
            </Abrir>
          );
        })}
        <p className="muted small fonte-linha">Fonte: <a href="https://dadosabertos.almg.gov.br/" target="_blank" rel="noreferrer">API de dados abertos da ALMG ↗</a> (prestação de contas da verba indenizatória, nota por nota), consultada mês a mês para cada deputado.</p>
        <OndeVer titulo="Para conferir no site oficial" links={[
          { nome: `Prestação de contas de ${primeiro} na ALMG`, url: urlAlmg || "", explica: "a mesma lista no site oficial, para conferir. A Assembleia não publica a imagem das notas" },
          { nome: "Verba indenizatória de todos os deputados (ALMG)", url: "https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/" },
          { nome: "API de dados abertos da ALMG", url: "https://dadosabertos.almg.gov.br/", explica: "de onde vêm estes dados" },
        ]} />
      </section>
      <AvisosFim assunto={`${d.nome}, deputado estadual, ${ano}`} resposta>
      {!!v.meses_faltando?.length && (
        <p className="alert small" role="note">Ainda estamos baixando da Assembleia os meses de {v.meses_faltando.map((m) => MESES[m - 1]).join(", ")} de {ano}. A ALMG só deixa consultar um mês por vez; o histórico completo aparece nos próximos dias.</p>
      )}
      </AvisosFim>
    </>
  );
}

/** Tudo o que a ALMG publica sobre uma nota, mostrado aqui mesmo, e as outras notas do mesmo fornecedor no ano */
function NotaDetalhe({ n, ano, todas, procurar }: { n: NotaAlmg; ano: string; todas: NotaAlmg[]; procurar: (x: string) => void }) {
  const mesma = (x: NotaAlmg) => (n.cnpj ? x.cnpj === n.cnpj : !n.pf && x.fornecedor === n.fornecedor);
  const outras = n.pf ? [] : todas.filter((x) => x !== n && mesma(x));
  const somaOutras = outras.reduce((a, x) => a + x.valor, 0);
  return (
    <div className="nota-detalhe" role="region" aria-label={`Nota de ${n.fornecedor}`}>
      <div className="kv small" style={{ gridTemplateColumns: "auto 1fr" }}>
        <strong>Emitente</strong><span style={{ textAlign: "left" }}>{n.fornecedor}{n.pf ? " (pessoa física: o CPF não é mostrado)" : ""}</span>
        <strong>CNPJ</strong><span style={{ textAlign: "left" }} className="mono">{n.cnpj ? <>{cnpjFmt(n.cnpj)} · <a href={linkCnpj(n.cnpj)} target="_blank" rel="noreferrer">empresa no Portal da Transparência ↗</a></> : n.pf ? "Não se aplica" : "Não informado pela ALMG"}</span>
        <strong>Tipo de despesa</strong><span style={{ textAlign: "left" }}>{n.tipo}</span>
        <strong>Data da nota</strong><span style={{ textAlign: "left" }} className="num">{dataBR(n.data) || "Não informada"}</span>
        <strong>Prestação de contas</strong><span style={{ textAlign: "left" }}>{MESES[n.mes - 1]} de {ano}</span>
        <strong>Número da nota</strong><span style={{ textAlign: "left" }} className="mono">{n.numero || "Não informado"}</span>
        <strong>Valor reembolsado</strong><span style={{ textAlign: "left" }} className="num"><strong>{reais(n.valor, true)}</strong></span>
      </div>
      {outras.length > 0 && <p className="small">Em {ano}, {outras.length} outra{outras.length > 1 ? "s" : ""} nota{outras.length > 1 ? "s" : ""} de {n.fornecedor}, somando <span className="num">{reais(somaOutras, true)}</span>. <button className="link" onClick={() => procurar(n.cnpj || n.fornecedor)}>Ver todas as notas deste fornecedor</button></p>}
    </div>
  );
}

/** Planilha (CSV) com as notas que estão na tela, para abrir no Excel ou no LibreOffice: separada por ponto e vírgula, valores com vírgula */
function baixarNotas(notas: NotaAlmg[], nome: string) {
  const cel = (x: string) => (/[";\n]/.test(x) ? `"${x.replace(/"/g, '""')}"` : x);
  const linhas = [["Mês", "Data da nota", "Tipo de despesa", "Emitente", "CNPJ", "Número da nota", "Valor reembolsado (R$)"].join(";"),
    ...notas.slice().sort((a, b) => a.mes - b.mes || a.data.localeCompare(b.data)).map((n) => [
      MESES[n.mes - 1], dataBR(n.data), n.tipo, n.fornecedor, n.cnpj ? cnpjFmt(n.cnpj) : n.pf ? "pessoa física" : "", n.numero || "",
      n.valor.toFixed(2).replace(".", ","),
    ].map((x) => cel(String(x))).join(";"))];
  const url = URL.createObjectURL(new Blob(["\ufeff" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url; a.download = nome;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function AtuacaoAlmg({ d, ano, colegas, primeiro }: { d: DeputadoEstadual; ano: string; colegas: { projetos: number; requerimentos: number; aprovadas: number }[]; primeiro: string }) {
  const p = d.anos[ano]?.proposicoes;
  const quem = "deputados estaduais";
  return (
    <>
      <section>
        <h2>Atuação em {ano}</h2>
        <Explain>Propostas que {primeiro} apresentou como primeiro autor, comparadas com os outros deputados estaduais em exercício. Quantidade não mede qualidade, mas mostra quem participa. A ALMG não publica nos dados abertos o voto de cada deputado nem a presença no Plenário, por isso essas partes não aparecem aqui.</Explain>
        <div className="atu-grade atu-grade-4">
          <Metrica nome="Projetos apresentados" quem={quem} eu={primeiro} tipico="Deputado típico" v={p?.projetos || 0} todos={colegas.map((c) => c.projetos)}
            explica="Projetos de lei, de lei complementar, de emenda à Constituição do estado e de resolução, como primeiro autor." />
          <Metrica nome="Projetos aprovados" quem={quem} eu={primeiro} tipico="Deputado típico" v={p?.aprovadas || 0} todos={colegas.map((c) => c.aprovadas)}
            explica="Dos projetos apresentados no ano, quantos já viraram lei ou foram aprovados, pela situação informada pela ALMG." />
          <Metrica nome="Requerimentos" quem={quem} eu={primeiro} tipico="Deputado típico" v={p?.requerimentos || 0} todos={colegas.map((c) => c.requerimentos)}
            explica="Pedidos de informação ao governo, de audiência pública, homenagens e outros pedidos, como primeiro autor." />
        </div>
        {p && p.coautor > 0 && <p className="muted small">Também assinou {p.coautor} proposta{p.coautor > 1 ? "s" : ""} de colegas como coautor.</p>}
      </section>
      {p && p.lista.length > 0 && <ProjetosAlmg lista={p.lista} ano={ano} />}
      <p className="muted small">Fonte: <a href="https://dadosabertos.almg.gov.br/documentacao/arquivos/proposicoes" target="_blank" rel="noreferrer">arquivo de proposições dos dados abertos da ALMG ↗</a>, com os autores e a situação de cada proposta.</p>
    </>
  );
}

function EmendasDep({ d, ano, colegas, primeiro }: { d: DeputadoEstadual; ano: string; colegas: number[]; primeiro: string }) {
  const e = d.anos[ano]?.emendas;
  if (!e) return <div className="empty">Não encontramos emendas estaduais indicadas por {d.nome} em {ano}. <Link to="/emendas-estaduais">Ver todas as emendas estaduais</Link>.</div>;
  return (
    <>
      <section>
        <h2>Emendas ao orçamento de Minas em {ano}</h2>
        <Explain>Todo ano, cada deputado estadual pode indicar para onde vai uma parte do orçamento do estado: uma obra numa cidade, equipamentos para um hospital, dinheiro para uma associação. O governo é obrigado a pagar boa parte dessas indicações. "Indicado" é o valor reservado; "pago" é o que já saiu do caixa do estado.</Explain>
        <div className="atu-grade">
          <Metrica nome="Valor indicado" quem="deputados estaduais" eu={primeiro} tipico="Deputado típico" v={e.indicado} todos={colegas} fmt={(x) => reais(x)}
            explica={`${e.n} indicações para ${e.n_municipios} município${e.n_municipios === 1 ? "" : "s"}. Já pago: ${reais(e.pago)}.`} />
        </div>
      </section>
      <section>
        <h2>Para quais cidades</h2>
        <Barras rosca={{ titulo: `Emendas estaduais indicadas em ${ano}, por cidade`, total: e.indicado }} itens={e.municipios.map((m) => ({ label: m.nome, nota: `${m.n} indicaç${m.n === 1 ? "ão" : "ões"}, ${reais(m.pago)} pago`, valor: m.indicado, cor: "var(--s3)" }))} />
      </section>
      <section>
        <h2>Quem recebe</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Quem recebe e para quê</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
            <tbody>
              {e.beneficiarios.map((b, i) => (
                <tr key={i}>
                  <td>{b.nome}<div className="small muted">{[b.municipio, b.area, b.orgao].filter(Boolean).join(" · ")}</div>{b.descricao && <div className="small">{b.descricao}</div>}
                    <div className="small so-celular">Pago: <span className="num">{reais(b.pago)}</span></div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(b.indicado)}</td>
                  <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(b.pago)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small"><Link to={`/emendas-estaduais?ano=${ano}&dep=${d.id}`}>Ver cada indicação de {d.nome} em {ano}: para quê, quem executa, tipo de despesa e situação ›</Link></p>
        <p className="muted small fonte-linha">Fonte: <a href="https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/" target="_blank" rel="noreferrer">emendas parlamentares na ALMG ↗</a> e <a href="https://dados.mg.gov.br/dataset/portal_emendas_estaduais" target="_blank" rel="noreferrer">execução das emendas no Dados MG ↗</a>.</p>
      </section>
    </>
  );
}

/** Os projetos do deputado: o que cada um propõe, em palavras simples, com filtros e o link para o texto e a justificativa */
function ProjetosAlmg({ lista, ano }: { lista: ProposicaoAlmg[]; ano: string }) {
  const [busca, setBusca] = useState("");
  const [sit, setSit] = useState("");
  const [tema, setTema] = useState("");
  const temas = [...new Set(lista.flatMap((x) => x.temas || []))].sort();
  const vis = lista.filter((x) => (!sit || (sit === "aprovado" ? x.aprovada : !x.aprovada)) && (!tema || x.temas?.includes(tema))
    && (!busca || norm(`${x.sigla} ${x.numero} ${x.ementa} ${x.resumo || ""}`).includes(norm(busca))));
  return (
    <section>
      <h2>Projetos de {ano}</h2>
      <Explain>Um projeto de lei é uma proposta de regra nova para Minas. Ele só vira lei se for aprovado pelos deputados e sancionado pelo governador. Abra cada projeto para ver o que ele propõe e o motivo (a justificação), escrito pelo próprio deputado.</Explain>
      <div className="search">
        <input id="busca-projeto" aria-label="Procurar projeto" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Assunto ou número" />
        <select id="filtro-situacao" aria-label="Situação" value={sit} onChange={(e) => setSit(e.target.value)}>
          <option value="">Todos</option><option value="aprovado">Aprovados</option><option value="andamento">Ainda não aprovados</option>
        </select>
        {temas.length > 0 && <select id="filtro-tema" aria-label="Tema" value={tema} onChange={(e) => setTema(e.target.value)}>
          <option value="">Todos os temas</option>{temas.map((t) => <option key={t}>{t}</option>)}
        </select>}
      </div>
      <p className="muted small">{vis.length} de {lista.length} projeto{lista.length === 1 ? "" : "s"}</p>
      {vis.map((x) => (
        <Abrir key={`${x.sigla}${x.numero}${x.ano}`} titulo={<>{x.sigla} {x.numero}/{x.ano}{x.aprovada && <> <span className="chip txt-sim">Aprovado</span></>}<span className="small" style={{ display: "block", fontWeight: 400, color: "var(--ink)" }}>{x.ementa}</span></>}>
          <div className="kv small" style={{ gridTemplateColumns: "auto 1fr" }}>
            <strong>O que é</strong><span style={{ textAlign: "left" }}>{x.resumo || x.ementa}</span>
            {x.justificativa && <><strong>Por quê</strong><span style={{ textAlign: "left" }}>{x.justificativa}</span></>}
            {!!x.temas?.length && <><strong>Temas</strong><span style={{ textAlign: "left" }}>{x.temas.join(" · ")}</span></>}
            <strong>Situação</strong><span style={{ textAlign: "left" }}>{x.situacao}{x.fase ? ` (fase: ${x.fase})` : ""}</span>
            {x.data && <><strong>Apresentado</strong><span style={{ textAlign: "left" }} className="num">{dataBR(x.data)}</span></>}
          </div>
          {linkSeguro(x.url) && <p className="small"><a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">Ler o texto completo e a justificação na ALMG ↗</a></p>}
        </Abrir>
      ))}
    </section>
  );
}
