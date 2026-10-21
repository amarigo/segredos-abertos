import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Explain, Loading, useData } from "../components/ui";
import { casaNome, dataBR, proposicaoNome, type VotacaoResumo } from "../data";
import { norm } from "./Home";

export default function Votacoes() {
  const { data, error } = useData<VotacaoResumo[]>("votacoes.json");
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [tipo, setTipo] = useState("");
  const tipos = useMemo(() => [...new Set((data || []).map((v) => v.proposicao?.sigla).filter(Boolean) as string[])].sort(), [data]);
  const lista = useMemo(() => (data || []).filter((v) => (!casa || v.casa === casa) && (!tipo || v.proposicao?.sigla === tipo)
    && (!q || norm(`${proposicaoNome(v.proposicao)} ${v.proposicao?.ementa || ""} ${v.descricao}`).includes(norm(q)))), [data, q, casa, tipo]);
  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Votações</h1>
      <Explain>Votações nominais do plenário, em que cada parlamentar registra o próprio voto. PEC é proposta de emenda à Constituição, PL é projeto de lei, MPV é medida provisória e PLP é projeto de lei complementar.</Explain>
      <div className="search">
        <input id="busca-votacao" aria-label="Buscar votação" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Assunto ou número (ex.: PEC 45)" />
        <select id="filtro-casa-v" aria-label="Casa" value={casa} onChange={(e) => setCasa(e.target.value)}>
          <option value="">Câmara e Senado</option><option value="camara">Câmara</option><option value="senado">Senado</option>
        </select>
        <select id="filtro-tipo" aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos os tipos</option>{tipos.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>
      <p className="muted small">{lista.length} votações</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Data</th><th>Casa</th><th>O que foi votado</th><th className="r">Sim</th><th className="r">Não</th><th>Resultado</th></tr></thead>
          <tbody>
            {lista.slice(0, 400).map((v) => (
              <tr key={v.id}>
                <td className="num">{dataBR(v.data)}</td>
                <td>{casaNome(v.casa)}</td>
                <td><Link to={`/v/${v.id}`}>{proposicaoNome(v.proposicao) || "Votação"}</Link><div className="small muted">{(v.proposicao?.ementa || v.descricao).slice(0, 200)}</div></td>
                <td className="r num">{v.sim}</td>
                <td className="r num">{v.nao}</td>
                <td><span className={`chip ${v.aprovada ? "ok" : "no"}`}>{v.aprovada ? "Aprovado" : "Rejeitado"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
