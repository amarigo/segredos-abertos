import { Link, useParams } from "react-router-dom";
import { useMemo, useState } from "react";
import { Barras, Explain, LinkNota, Loading, useAno, useData } from "../components/ui";
import { MESES, cnpjFmt, dataBR, reais, type DonoFinal, type Empresa, type NotaEmpresa, type Resumo } from "../data";
import { norm } from "./Home";

export default function EmpresaPage() {
  const { cnpj = "" } = useParams();
  const { data: e, error } = useData<Empresa>(`e/${cnpj}.json`);
  if (!e) return <Loading error={error && "Esta empresa não está entre as que recebem dinheiro da cota no período."} />;
  const emp = e.empresa;
  return (
    <>
      <section>
        <span className="eyebrow">Empresa · CNPJ <span className="mono">{cnpjFmt(e.cnpj)}</span></span>
        <h1>{e.nome}</h1>
        {emp?.nome_fantasia && <p className="muted">Nome fantasia: {emp.nome_fantasia}</p>}
        {e.alertas.map((a) => <div className="alert" key={a} role="note"><strong>Ponto de atenção:</strong> {a}</div>)}
      </section>
      <section className="grid">
        <div className="card stat"><span className="label">Recebeu de parlamentares (todos os anos)</span><span className="value">{reais(e.total)}</span><span className="hint">de {e.n_politicos} parlamentar{e.n_politicos > 1 ? "es" : ""}</span></div>
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
                    <td className="r num">{reais(o.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <h2>Quem pagou (todos os anos)</h2>
        <Barras itens={e.pagadores.slice(0, 30).map((p) => ({ label: <Link to={`/p/${p.politico}`}>{p.nome} <span className="muted small">({p.partido}-{p.uf})</span></Link>, valor: p.valor }))} />
      </section>

      <PorMes e={e} />
      <Notas e={e} />
    </>
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
            <thead><tr><th>Data</th><th>Parlamentar e tipo de gasto</th><th className="r">Valor</th><th>Nota</th></tr></thead>
            <tbody>
              {lista.slice(0, n).map((x, i) => (
                <tr key={i}>
                  <td className="num">{dataBR(x[0])}</td>
                  <td><Link to={`/p/${x[1]}`}>{nomes.get(x[1]) || x[1]}</Link><div className="small muted">{x[2]}</div>{x[6] && <div className="small">{x[6]}</div>}</td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x[3], true)}</td>
                  <td className="small"><LinkNota url={x[4]} link={x[5] || (x[4] ? "nota" : "")} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {lista.length > n && <button className="link" onClick={() => setN(n + 200)}>Mostrar mais notas ({(lista.length - n).toLocaleString("pt-BR")} restantes)</button>}
        <p className="muted small">Cada despesa tem um link oficial. "Abrir nota" mostra a imagem da nota fiscal. Passagens compradas pelo sistema da Câmara e contas de telefone não têm imagem: "Ver detalhe na Câmara" abre a página oficial da despesa. O Senado não publica as notas: "Ver na lista do Senado" abre a lista oficial de despesas do senador.{semLink > 0 && ` ${semLink.toLocaleString("pt-BR")} despesa${semLink > 1 ? "s" : ""} sem nenhum link oficial.`}</p>
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
          <h3>Outras empresas dos mesmos donos que recebem de parlamentares</h3>
          <ul className="donos">
            {comOutras.map((d) => (
              <li key={`${d.nome}|${d.doc}`} className="card">
                <strong>{d.nome}</strong>
                <div className="small">{d.outras_empresas.map((o, k) => (
                  <span key={o.cnpj}>{k > 0 && ", "}<Link to={`/e/${o.cnpj}`}>{o.nome}</Link> <span className="muted num">({reais(o.total)})</span></span>
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
