import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Explain, Loading, ResultadoChip, VotoBarra, VotoChip, VotoLegenda, useData } from "../components/ui";
import { casaNome, dataBR, descricaoCurta, linkSeguro, proposicaoNome, tipoVotacao, type Votacao, type VotacaoResumo } from "../data";
import { norm } from "./Home";
import { MG } from "../recorte";
import { AvisosFim, EmRevisao } from "../components/Selo";
import { Rosca, prepararFatias } from "../components/graficos";
import { COR_LADO } from "../partidos";

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
          <ResultadoChip aprovada={v.aprovada} />
          {v.placar_casa && MG
            ? <><span className="chip">{casaNome(v.casa)}: Sim {v.placar_casa.sim} · Não {v.placar_casa.nao}</span><span className="chip">Bancada de MG: Sim {v.sim} · Não {v.nao}</span></>
            : v.placar_casa
              ? <span className="chip">Placar oficial: Sim {v.placar_casa.sim} · Não {v.placar_casa.nao}</span>
              : <span className="chip">Sim {v.sim} · Não {v.nao}</span>}
          {linkSeguro(v.proposicao?.url) && <a className="chip" href={linkSeguro(v.proposicao?.url)} target="_blank" rel="noreferrer">Ver a proposta e as votações no site {v.casa === "camara" ? "da Câmara" : "do Senado"} ↗</a>}
          {v.temas?.map((t) => <Link key={t} className="chip" to={`/votacoes/ja-votadas?tema=${encodeURIComponent(t)}`}>{t}</Link>)}
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
                        <ResultadoChip aprovada={x.aprovada} />
                      </div>
                      <div className="small muted">{variosDias && <>{dataBR(x.data)} · </>}{descricaoCurta(x.descricao).slice(0, 200)}</div>
                    </td>
                    <td className="r num">{(x.placar_casa || x).sim}</td>
                    <td className="r num">{(x.placar_casa || x).nao}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {v.por_partido_mg && Object.keys(v.por_partido_mg).length > 0 && (
        <section>
          <h2>Como votou a bancada de Minas Gerais</h2>
          <VotoLegenda />
          <div className="bars">
            {Object.entries(v.por_partido_mg).sort((a, b) => tot(b[1]) - tot(a[1])).map(([sigla, c]) => (
              <div key={sigla} className="bar-row" style={{ gridTemplateColumns: "150px 1fr" }}>
                <span><strong>{sigla}</strong> <span className="muted small">{c["Sim"] || 0} Sim · {c["Não"] || 0} Não</span></span><VotoBarra c={c} />
              </div>
            ))}
          </div>
        </section>
      )}

      <PlacarGraficos v={v} />

      <section>
        <h2>Por tendência (esquerda e direita){MG && ", na Casa inteira"}</h2>
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
        <h2>Por partido{MG && ", na Casa inteira"}</h2>
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
        <h2>{MG ? "Voto de cada um de Minas" : "Voto de cada um"}</h2>
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
      {linkSeguro(v.fonte) && <p className="muted small">Para programadores: <a href={linkSeguro(v.fonte)} target="_blank" rel="noreferrer">dados brutos desta votação</a> (formato para computador).</p>}
      <AvisosFim secao="votacoes">
        {v.placar_casa?.fonte === "ata" && v.placar_casa.painel &&
          <p className="small muted" role="note" data-testid="placar-ata">O placar oficial é o da ata da sessão (Sim {v.placar_casa.sim} · Não {v.placar_casa.nao}). O painel eletrônico registrou Sim {v.placar_casa.painel.sim} · Não {v.placar_casa.painel.nao}: algum voto foi corrigido depois da votação. <Link to="/verificacao#motivo-senado_painel_ata">Por quê</Link>.</p>}
        {!MG && v.placar_casa && (v.placar_casa.sim !== v.sim || v.placar_casa.nao !== v.nao) &&
          <p className="small muted">A lista de votos mostra só quem está no mandato hoje (Sim {v.sim} · Não {v.nao}). A diferença para o placar oficial são votos de {v.casa === "camara" ? "deputados" : "senadores"} que saíram do cargo depois desta votação{v.placar_casa.fonte === "ata" ? " ou correções registradas na ata" : ""}.</p>}
        <EmRevisao campo="votacao" valor={v.id} />
      </AvisosFim>
    </>
  );
}

const tot = (c: Record<string, number>) => Object.values(c).reduce((a, b) => a + b, 0);
function orientDe(o: Record<string, string>, sigla: string): string | undefined {
  const k = Object.keys(o || {}).find((k) => k.toUpperCase() === sigla.toUpperCase() || k.toUpperCase().split(/[^A-Z]/).includes(sigla.toUpperCase()));
  return k ? o[k] : undefined;
}

/* Placar em rosca e de que lado vieram os votos Sim e os votos Não */
function PlacarGraficos({ v }: { v: Votacao }) {
  const fmt = (n: number) => `${n} voto${n === 1 ? "" : "s"}`;
  const c = v.contagem || {};
  const outros = Object.entries(c).filter(([k]) => k !== "Sim" && k !== "Não").reduce((a, [, n]) => a + n, 0);
  const placar = prepararFatias([{ nome: "Sim", valor: c["Sim"] || 0, cor: "var(--sim)" }, { nome: "Não", valor: c["Não"] || 0, cor: "var(--nao)" },
    { nome: "Abstenção, obstrução ou ausência", valor: outros, cor: "var(--outro)" }]);
  const deLado = (voto: string) => prepararFatias(LADOS.map((l) => ({ nome: l, valor: v.por_lado[l]?.[voto] || 0, cor: COR_LADO[l] })), 9);
  const sim = deLado("Sim"), nao = deLado("Não");
  if (!placar.length) return null;
  return (
    <section>
      <h2>O placar em gráficos</h2>
      <p className="small muted">{MG ? "Como votou a bancada de Minas Gerais. Ao lado, na Casa inteira," : "Votos registrados de quem está no mandato hoje. Ao lado,"} de que lado (esquerda a direita, pelos votos de cada um) vieram os votos Sim e os votos Não.</p>
      <div className="secao-graficos">
        <div><h3 className="graf-titulo">{MG ? "Como votou a bancada de MG" : "Como votaram"}</h3><Rosca fatias={placar} titulo="Placar da votação" formato={fmt} centroRotulo="Votos" centro={String(placar.reduce((a, f) => a + f.valor, 0))} /></div>
        {sim.length > 0 && <div><h3 className="graf-titulo">De onde vieram os Sim</h3><Rosca fatias={sim} titulo="Votos Sim por lado" formato={fmt} centroRotulo="Sim" centro={String(c["Sim"] || 0)} /></div>}
        {nao.length > 0 && <div><h3 className="graf-titulo">De onde vieram os Não</h3><Rosca fatias={nao} titulo="Votos Não por lado" formato={fmt} centroRotulo="Não" centro={String(c["Não"] || 0)} /></div>}
      </div>
    </section>
  );
}
