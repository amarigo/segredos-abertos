import { Link, useParams } from "react-router-dom";
import { useMemo, useState } from "react";
import { Barras, Explain, Loading, useAno, useData } from "../components/ui";
import { MESES, cnpjFmt, dataBR, reais, type Empresa, type NotaEmpresa, type Resumo } from "../data";
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
          : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Sócio</th><th>Função</th><th>Desde</th><th>Outras empresas dele que recebem de parlamentares</th></tr></thead>
                <tbody>
                  {e.socios.map((s, i) => (
                    <tr key={i}>
                      <td>{s.nome}<div className="muted small mono">{s.doc}</div></td>
                      <td className="small">{s.qualificacao}</td>
                      <td className="num">{dataBR(s.entrada)}</td>
                      <td>{s.outras_empresas.length ? s.outras_empresas.map((o) => (
                        <div key={o.cnpj}><Link to={`/e/${o.cnpj}`}>{o.nome}</Link> <span className="muted small num">{reais(o.total)}</span></div>
                      )) : <span className="muted">Nenhuma encontrada</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        <p className="muted small">A Receita esconde parte do CPF dos sócios. Por isso ligamos empresas pelo nome do sócio mais os dígitos visíveis do CPF. Homônimos raros podem aparecer.</p>
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
                  <td><Link to={`/p/${x[1]}`}>{nomes.get(x[1]) || x[1]}</Link><div className="small muted">{x[2]}</div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x[3], true)}</td>
                  <td className="small">{x[4] ? <a href={x[4]} target="_blank" rel="noreferrer">Abrir nota ↗</a> : <span className="muted">Sem link oficial</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {lista.length > n && <button className="link" onClick={() => setN(n + 200)}>Mostrar mais notas ({(lista.length - n).toLocaleString("pt-BR")} restantes)</button>}
        {semLink > 0 && <p className="muted small">{semLink.toLocaleString("pt-BR")} nota{semLink > 1 ? "s" : ""} sem link: o Senado não publica a imagem das notas, e algumas notas antigas da Câmara também não têm.</p>}
      </>}
    </section>
  );
}
