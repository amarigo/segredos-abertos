import { Link, useParams } from "react-router-dom";
import { Barras, Explain, Loading, useData } from "../components/ui";
import { cnpjFmt, dataBR, reais, type Empresa } from "../data";

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
        <div className="card stat"><span className="label">Recebeu de parlamentares</span><span className="value">{reais(e.total)}</span><span className="hint">de {e.n_politicos} parlamentar{e.n_politicos > 1 ? "es" : ""}</span></div>
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

      <section>
        <h2>Quem pagou</h2>
        <Barras itens={e.pagadores.slice(0, 30).map((p) => ({ label: <Link to={`/p/${p.politico}`}>{p.nome} <span className="muted small">({p.partido}-{p.uf})</span></Link>, valor: p.valor }))} />
      </section>
    </>
  );
}
