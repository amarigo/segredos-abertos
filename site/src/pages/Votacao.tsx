import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Explain, Loading, VotoBarra, VotoChip, VotoLegenda, useData } from "../components/ui";
import { casaNome, dataBR, descricaoCurta, proposicaoNome, tipoVotacao, type Votacao, type VotacaoResumo } from "../data";
import { norm } from "./Home";

const LADOS = ["Esquerda", "Centro-esquerda", "Centro", "Centro-direita", "Direita"];

export default function VotacaoPage() {
  const { id = "" } = useParams();
  const { data: v, error } = useData<Votacao>(`v/${id}.json`);
  const { data: todas } = useData<VotacaoResumo[]>("votacoes.json");
  const [q, setQ] = useState("");
  const votos = useMemo(() => (v?.votos || []).filter((x) => !q || norm(`${x.nome} ${x.partido} ${x.uf}`).includes(norm(q))), [v, q]);
  if (!v) return <Loading error={error} />;
  const nome = proposicaoNome(v.proposicao);
  const irmas = nome ? (todas || []).filter((x) => x.casa === v.casa && proposicaoNome(x.proposicao) === nome)
    .sort((a, b) => a.data.localeCompare(b.data) || a.id.localeCompare(b.id)) : [];
  const variosDias = new Set(irmas.map((x) => x.data)).size > 1;
  const partidos = Object.entries(v.por_partido).sort((a, b) => tot(b[1]) - tot(a[1]));
  const orient = Object.entries(v.orientacoes || {});
  return (
    <>
      <section>
        <span className="eyebrow">{casaNome(v.casa)} · {dataBR(v.data)}</span>
        <h1>{proposicaoNome(v.proposicao) || "Votação"}{tipoVotacao(v.descricao) && <span className="h1-sub">{tipoVotacao(v.descricao)}</span>}</h1>
        {descricaoCurta(v.descricao) && <p style={{ fontSize: "1.05rem" }}><strong>O que foi votado:</strong> {descricaoCurta(v.descricao)}</p>}
        {v.proposicao?.ementa && <p className="muted"><strong>Sobre a proposta:</strong> {v.proposicao.ementa}</p>}
        <div className="row">
          <span className={`chip ${v.aprovada ? "ok" : "no"}`}>{v.aprovada ? "Aprovado" : "Rejeitado"}</span>
          <span className="chip">Sim {v.sim} · Não {v.nao}</span>
          {v.proposicao?.url && <a className="chip" href={v.proposicao.url} target="_blank" rel="noreferrer">Ver a proposta e as votações no site {v.casa === "camara" ? "da Câmara" : "do Senado"} ↗</a>}
          {v.temas?.map((t) => <Link key={t} className="chip" to={`/votacoes?tema=${encodeURIComponent(t)}`}>{t}</Link>)}
        </div>
      </section>

      {irmas.length > 1 && (
        <section>
          <h2>Todas as votações de {nome}</h2>
          {!variosDias && <p className="muted small" style={{ marginTop: -4 }}>Todas em {dataBR(irmas[0].data)}.</p>}
          <Explain>Uma proposta costuma ter várias votações: primeiro o texto principal e depois os destaques, que são trechos que um partido pede para votar separadamente. Cada linha abaixo é uma votação diferente.</Explain>
          <div className="table-wrap">
            <table>
              <thead><tr><th>O que foi votado</th><th className="r">Sim</th><th className="r">Não</th></tr></thead>
              <tbody>
                {irmas.map((x) => (
                  <tr key={x.id} className={x.id === v.id ? "atual" : ""}>
                    <td>
                      <div className="voto-linha">
                        {x.id === v.id ? <strong>{tipoVotacao(x.descricao) || "Votação"} (esta)</strong> : <Link to={`/v/${x.id}`}>{tipoVotacao(x.descricao) || "Votação"}</Link>}
                        <span className={`chip ${x.aprovada ? "ok" : "no"}`}>{x.aprovada ? "Aprovado" : "Rejeitado"}</span>
                      </div>
                      <div className="small muted">{variosDias && <>{dataBR(x.data)} · </>}{descricaoCurta(x.descricao).slice(0, 200)}</div>
                    </td>
                    <td className="r num">{x.sim}</td>
                    <td className="r num">{x.nao}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <h2>Por tendência (esquerda e direita)</h2>
        <Explain>Agrupamos os parlamentares pela posição calculada a partir de todos os seus votos.</Explain>
        <VotoLegenda />
        <div className="bars">
          {LADOS.filter((l) => v.por_lado[l]).map((l) => (
            <div key={l} className="bar-row" style={{ gridTemplateColumns: "150px 1fr" }}>
              <span>{l}</span><VotoBarra c={v.por_lado[l]} />
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>Por partido</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Partido</th><th style={{ width: "45%" }}>Votos</th><th className="r">Sim</th><th className="r">Não</th><th>Orientação do partido</th></tr></thead>
            <tbody>
              {partidos.map(([sigla, c]) => (
                <tr key={sigla}>
                  <td><strong>{sigla}</strong></td>
                  <td><VotoBarra c={c} /></td>
                  <td className="r num">{c["Sim"] || 0}</td>
                  <td className="r num">{c["Não"] || 0}</td>
                  <td>{orientDe(v.orientacoes, sigla) ? <VotoChip voto={orientDe(v.orientacoes, sigla)!} /> : <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {orient.length > 0 && (
          <p className="small muted">Orientações de blocos: {orient.filter(([k]) => /gov|maioria|minoria|oposi/i.test(k)).map(([k, o]) => `${k}: ${o}`).join(" · ") || "—"}</p>
        )}
      </section>

      <section>
        <h2>Voto de cada um</h2>
        <div className="search"><input id="busca-voto" aria-label="Buscar parlamentar" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome, partido ou estado" /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Parlamentar</th><th>Partido</th><th>Voto</th></tr></thead>
            <tbody>
              {votos.map((x) => (
                <tr key={x.politico}>
                  <td><Link to={`/p/${x.politico}?aba=votos`}>{x.nome}</Link></td>
                  <td>{x.partido}-{x.uf}</td>
                  <td><VotoChip voto={x.voto} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {v.fonte && <p className="muted small">Para programadores: <a href={v.fonte} target="_blank" rel="noreferrer">dados brutos desta votação</a> (formato para computador).</p>}
    </>
  );
}

const tot = (c: Record<string, number>) => Object.values(c).reduce((a, b) => a + b, 0);
function orientDe(o: Record<string, string>, sigla: string): string | undefined {
  const k = Object.keys(o || {}).find((k) => k.toUpperCase() === sigla.toUpperCase() || k.toUpperCase().split(/[^A-Z]/).includes(sigla.toUpperCase()));
  return k ? o[k] : undefined;
}
