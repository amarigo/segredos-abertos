import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Explain, Loading, useData } from "../components/ui";
import { cnpjFmt, reais, type EmpresaResumo } from "../data";
import { norm } from "./Home";

export default function Empresas() {
  const { data, error } = useData<EmpresaResumo[]>("empresas.json");
  const [q, setQ] = useState("");
  const lista = useMemo(() => (data || []).filter((e) => !q || norm(e.nome).includes(norm(q)) || e.cnpj.includes(q.replace(/\D/g, "") || "x")), [data, q]);
  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Empresas</h1>
      <Explain>As empresas que mais receberam dinheiro da cota parlamentar. Em cada uma você vê quem são os donos (pela Receita Federal) e quais parlamentares pagaram.</Explain>
      <div className="search"><input id="busca-empresa" aria-label="Buscar empresa" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou CNPJ" /></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Empresa</th><th className="r">Parlamentares</th><th className="r">Recebeu</th></tr></thead>
          <tbody>
            {lista.slice(0, 300).map((e) => (
              <tr key={e.cnpj}>
                <td><Link to={`/e/${e.cnpj}`}>{e.nome}</Link><div className="muted small mono">{cnpjFmt(e.cnpj)}</div></td>
                <td className="r num">{e.n_politicos}</td>
                <td className="r num">{reais(e.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
