import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Barras, Explain, GastoMensal, Loading, useData } from "../components/ui";
import { cnpjFmt, corPartido, dataBR, linkSeguro, reais, type AlmgIndice, type DeputadoEstadual } from "../data";
import { Metrica } from "./Atuacao";
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
  const colegas = (idx?.deputados || []).map((x) => x.por_ano[ano]).filter(Boolean);
  const primeiro = d.nome.split(" ")[0];
  return (
    <>
      <section className="profile">
        <span className="avatar sigla-avatar" style={{ width: 96, height: 96, fontSize: "1rem", background: corPartido(d.partido) }} aria-hidden="true">{d.partido.slice(0, 5)}</span>
        <div>
          <span className="eyebrow">Deputado estadual · Assembleia de Minas Gerais</span>
          <h1>{d.nome}</h1>
          <div className="tags">
            <span className="chip">{d.partido}</span>
            <a className="chip" href={linkSeguro(d.url)} target="_blank" rel="noreferrer">Página na ALMG ↗</a>
          </div>
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

function Gastos({ d, ano, colegas, primeiro }: { d: DeputadoEstadual; ano: string; colegas: number[]; primeiro: string }) {
  const [todas, setTodas] = useState(false);
  const v = d.anos[ano]?.verba;
  if (!v) return <div className="empty">A ALMG não publicou gastos da verba indenizatória de {d.nome} em {ano}.</div>;
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
        <h2>Por mês</h2>
        <GastoMensal meses={v.meses} ano={ano} cor="var(--s2)" />
      </section>
      <section>
        <h2>Em que gastou</h2>
        <Barras itens={v.tipos.slice(0, todas ? 99 : 8).map((t) => ({ label: t.tipo, valor: t.valor, cor: "var(--s2)" }))} />
        {v.tipos.length > 8 && <button className="link" onClick={() => setTodas(!todas)}>{todas ? "Mostrar menos" : `Mostrar os ${v.tipos.length} tipos`}</button>}
      </section>
      <section>
        <h2>Quem recebeu</h2>
        <Explain>Empresas e pessoas que emitiram as notas. Quando quem recebeu é uma pessoa física, não mostramos o CPF.</Explain>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Fornecedor</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {v.fornecedores.map((f, i) => (
                <tr key={i}>
                  <td>{f.nome}<div className="muted small mono">{f.cnpj ? <a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${f.cnpj}`} target="_blank" rel="noreferrer">CNPJ {cnpjFmt(f.cnpj)} ↗</a> : f.pf ? <span className="pf-tag">Pessoa física</span> : ""}</div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(f.valor)}<div className="muted small">{f.n} nota{f.n > 1 ? "s" : ""}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {v.n_fornecedores > v.fornecedores.length && <p className="muted small">Mostrando os {v.fornecedores.length} que mais receberam, de {v.n_fornecedores}.</p>}
      </section>
      <section>
        <h2>Maiores despesas de {ano}</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="so-largo">Data</th><th>Fornecedor e tipo</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {v.notas.map((n, i) => (
                <tr key={i}>
                  <td className="num so-largo">{dataBR(n.data)}</td>
                  <td>{n.fornecedor}{n.pf && <span className="pf-tag small"> (pessoa física)</span>}<div className="small muted">{n.tipo}</div>
                    <div className="small so-celular num muted">{dataBR(n.data)}</div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(n.valor, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small fonte-linha">Cada nota, com o número do documento, está na <a href={linkSeguro(d.url_verba || `https://www.almg.gov.br/transparencia/prestacao-de-contas/deputados/verba-indenizatoria/detalhe.html?id=${d.id}`)} target="_blank" rel="noreferrer">prestação de contas de {primeiro} no site da ALMG ↗</a>. A Assembleia não publica a imagem das notas.</p>
      </section>
      <AvisosFim>
      {!!v.meses_faltando?.length && (
        <p className="alert small" role="note">Ainda estamos baixando da Assembleia os meses de {v.meses_faltando.map((m) => MESES[m - 1]).join(", ")} de {ano}. A ALMG só deixa consultar um mês por vez; o histórico completo aparece nos próximos dias.</p>
      )}
      </AvisosFim>
    </>
  );
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
      {p && p.lista.length > 0 && (
        <section>
          <h2>Projetos de {ano}</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Projeto</th><th className="so-largo">Situação</th></tr></thead>
              <tbody>
                {p.lista.map((x) => (
                  <tr key={`${x.sigla}${x.numero}${x.ano}`}>
                    <td><a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">{x.sigla} {x.numero}/{x.ano} ↗</a>{x.aprovada && <> <span className="chip txt-sim">Aprovado</span></>}
                      <div className="small">{x.ementa}</div><div className="small muted so-celular">{x.situacao}</div></td>
                    <td className="small so-largo">{x.situacao}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
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
        <Barras itens={e.municipios.map((m) => ({ label: m.nome, nota: `${m.n} indicaç${m.n === 1 ? "ão" : "ões"}, ${reais(m.pago)} pago`, valor: m.indicado, cor: "var(--s3)" }))} />
      </section>
      <section>
        <h2>Quem recebe</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Quem recebe e para quê</th><th className="r">Indicado</th><th className="r so-largo">Pago</th></tr></thead>
            <tbody>
              {e.beneficiarios.map((b, i) => (
                <tr key={i}>
                  <td>{b.nome}<div className="small muted">{b.municipio}{b.area ? ` · ${b.area}` : ""}</div>{b.descricao && <div className="small">{b.descricao}</div>}
                    <div className="small so-celular">Pago: <span className="num">{reais(b.pago)}</span></div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(b.indicado)}</td>
                  <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(b.pago)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small fonte-linha">Fonte: <a href="https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/" target="_blank" rel="noreferrer">emendas parlamentares na ALMG ↗</a> e <a href="https://dados.mg.gov.br/dataset/portal_emendas_estaduais" target="_blank" rel="noreferrer">execução das emendas no Dados MG ↗</a>.</p>
      </section>
    </>
  );
}
