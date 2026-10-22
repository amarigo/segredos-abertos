import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Explain, Loading, ResultadoChip, useData } from "../components/ui";
import { TEMAS, casaNome, dataBR, descricaoCurta, proposicaoNome, tipoVotacao, type VotacaoResumo } from "../data";
import { norm } from "./Home";
import { MG } from "../recorte";

export default function Votacoes() {
  const { data, error } = useData<VotacaoResumo[]>("votacoes.json");
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [tipo, setTipo] = useState("");
  const [params, setParams] = useSearchParams();
  const tema = params.get("tema") || "";
  const setTema = (t: string) => setParams(t ? { tema: t } : {}, { replace: true });
  const contTema = useMemo(() => { const c: Record<string, number> = {}; (data || []).forEach((v) => v.temas?.forEach((t) => (c[t] = (c[t] || 0) + 1))); return c; }, [data]);
  const tipos = useMemo(() => [...new Set((data || []).map((v) => v.proposicao?.sigla).filter(Boolean) as string[])].sort(), [data]);
  const lista = useMemo(() => (data || []).filter((v) => (!casa || v.casa === casa) && (!tipo || v.proposicao?.sigla === tipo) && (!tema || !!v.temas?.includes(tema))
    && (!q || norm(`${proposicaoNome(v.proposicao)} ${v.proposicao?.ementa || ""} ${v.descricao}`).includes(norm(q)))), [data, q, casa, tipo, tema]);
  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Votações</h1>
      <Explain>Votações nominais do plenário, em que cada parlamentar registra o próprio voto.{MG && " Sim e Não mostram o placar da Casa inteira; ao lado, como votou a bancada de Minas Gerais."} PEC é proposta de emenda à Constituição, PL é projeto de lei, MPV é medida provisória e PLP é projeto de lei complementar.</Explain>
      <div className="search">
        <input id="busca-votacao" aria-label="Buscar votação" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Assunto ou número (ex.: PEC 45)" />
        <select id="filtro-casa-v" aria-label="Casa" value={casa} onChange={(e) => setCasa(e.target.value)}>
          <option value="">Câmara e Senado</option><option value="camara">Câmara</option><option value="senado">Senado</option>
        </select>
        <select id="filtro-tipo" aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos os tipos</option>{tipos.map((t) => <option key={t}>{t}</option>)}
        </select>
      </div>
      <div className="row" style={{ flexWrap: "wrap", gap: 6, margin: "8px 0" }} role="group" aria-label="Temas">
        <button className={`chip ${!tema ? "ok" : ""}`} onClick={() => setTema("")}>Todos os temas</button>
        {TEMAS.filter((t) => contTema[t]).map((t) => (
          <button key={t} className={`chip ${tema === t ? "ok" : ""}`} aria-pressed={tema === t} onClick={() => setTema(tema === t ? "" : t)}>{t} ({contTema[t]})</button>
        ))}
      </div>
      <p className="muted small">{lista.length} votações{tema ? ` sobre ${tema.toLowerCase()}` : ""}. Os temas são definidos por palavras da ementa. <Link to="/sobre">Entenda</Link>.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Data</th><th>Casa</th><th>O que foi votado</th><th className="r">Sim</th><th className="r">Não</th>{MG && <th>Bancada de MG</th>}<th>Resultado</th></tr></thead>
          <tbody>
            {lista.slice(0, 400).map((v) => (
              <tr key={v.id}>
                <td className="num">{dataBR(v.data)}</td>
                <td>{casaNome(v.casa)}</td>
                <td><Link to={`/v/${v.id}`}>{proposicaoNome(v.proposicao) || "Votação"}</Link>{tipoVotacao(v.descricao) && <> <span className="chip">{tipoVotacao(v.descricao)}</span></>}
                  {descricaoCurta(v.descricao) && <div className="small">{descricaoCurta(v.descricao).slice(0, 220)}</div>}
                  {v.proposicao?.ementa && <div className="small muted">{v.proposicao.ementa.slice(0, 160)}</div>}
                  {v.temas && v.temas.length > 0 && <div className="small" style={{ marginTop: 2 }}>{v.temas.join(" · ")}</div>}</td>
                <td className="r num">{(v.placar_casa || v).sim}</td>
                <td className="r num">{(v.placar_casa || v).nao}</td>
                {MG && <td className="small num" style={{ whiteSpace: "nowrap" }}>{v.sim} Sim · {v.nao} Não</td>}
                <td><ResultadoChip aprovada={v.aprovada} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
