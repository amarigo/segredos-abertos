import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Explain, Loading, OndeVer, useData } from "../components/ui";
import { AvisosFim } from "../components/Selo";
import { dataBR, type Julgamento, type LadoVoto, type Tribunais } from "../data";
import { norm } from "./Home";
import { VotacoesAbas } from "./Votacoes";
import { numero } from "../components/graficos";

/* Julgamentos do Plenário do STF: como cada ministro votou nas ações que derrubam ou mantêm leis.
   Os dados vêm de etl/sa_etl/tribunais.py (serviços do portal do STF), com link para a página oficial de cada processo. */

const LADO: Record<LadoVoto, { nome: string; cor: string }> = {
  relator: { nome: "Com o relator", cor: "var(--s1)" },
  divergencia: { nome: "Divergiu do relator", cor: "var(--s2)" },
  vista: { nome: "Pediu vista (mais tempo)", cor: "var(--c6)" },
  fora: { nome: "Não votou (impedido ou suspeito)", cor: "var(--outro)" },
  outro: { nome: "Outro voto", cor: "var(--c5)" },
};
const ORDEM: LadoVoto[] = ["relator", "divergencia", "vista", "outro", "fora"];

function Placar({ j }: { j: Julgamento }) {
  const t = ORDEM.reduce((a, k) => a + (j.placar[k] || 0), 0) || 1;
  const txt = ORDEM.filter((k) => j.placar[k]).map((k) => `${LADO[k].nome}: ${j.placar[k]}`).join(" · ");
  return (
    <div>
      <div className="stack" role="img" aria-label={`Placar: ${txt}`} title={txt}>
        {ORDEM.filter((k) => j.placar[k]).map((k) => <span key={k} style={{ width: `${(j.placar[k] / t) * 100}%`, background: LADO[k].cor }} />)}
      </div>
      <p className="small" style={{ margin: "4px 0 0" }}>{txt}</p>
    </div>
  );
}

function situacao(j: Julgamento): { texto: string; cls: string } {
  if (j.situacao === "em_julgamento") return { texto: "Em julgamento", cls: "chip" };
  if (j.situacao === "vista") return { texto: "Parado: pedido de vista", cls: "chip" };
  if (j.situacao === "destaque") return { texto: "Vai ao plenário presencial", cls: "chip" };
  if (j.situacao === "sem_maioria") return { texto: "Sem maioria na sessão", cls: "chip" };
  const unanime = !j.placar.divergencia && j.maioria === "relator";
  return { texto: unanime ? "Todos com o relator" : j.maioria === "relator" ? "Relator venceu" : "Divergência venceu", cls: j.maioria === "relator" ? "chip ok" : "chip nao" };
}

function CartaoJulgamento({ j, explica }: { j: Julgamento; explica?: string }) {
  const s = situacao(j);
  const autores = j.partes.filter((p) => /REQTE|AUTOR/i.test(p.tipo)).map((p) => p.nome);
  return (
    <article className="card proj" data-testid="julgamento">
      <div className="row" style={{ flexWrap: "wrap", gap: 6, alignItems: "center" }}>
        <span className="chip" title={explica}>{j.classe}</span>
        <span className={s.cls}>{s.texto}</span>
        {j.resultado && <span className="chip">{j.resultado}</span>}
        <span className="small muted">Sessão virtual de {dataBR(j.inicio)} a {dataBR(j.fim)}</span>
      </div>
      <h3 className="proj-titulo"><a href={j.link} target="_blank" rel="noreferrer">{j.processo}</a>{j.uf && <span className="muted small"> ({j.uf})</span>}</h3>
      <p className="small" style={{ margin: 0 }}>
        Relator: <strong>{j.relator || "não informado"}</strong>
        {autores.length > 0 && <> · Quem pediu: {autores.join(", ")}</>}
        {j.vista && <> · Pedido de vista: {j.vista}</>}
        {j.destaque && <> · Destaque (vai ao plenário presencial): {j.destaque}</>}
      </p>
      <Placar j={j} />
      {j.decisao && <Abrir titulo="O que o STF decidiu (texto oficial)"><p className="small" style={{ margin: 0 }}>{j.decisao}</p></Abrir>}
      <Abrir titulo={`Voto de cada ministro (${j.votos.length})`}>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Ministro</th><th>Voto</th><th>Lado</th><th>Íntegra</th></tr></thead>
            <tbody>
              {j.votos.map((v) => (
                <tr key={v.ministro}>
                  <td>{v.ministro}</td>
                  <td className="small">{v.voto}{v.acompanha && <span className="muted"> (acompanhou {v.acompanha})</span>}</td>
                  <td><span className="small" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <i aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 999, background: LADO[v.lado].cor, display: "inline-block" }} />{LADO[v.lado].nome}</span></td>
                  <td className="small">{v.link ? <a href={v.link} target="_blank" rel="noreferrer">Ler o voto</a> : <span className="muted">Não publicado</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Abrir>
      <p className="small muted" style={{ margin: 0 }}>
        Fonte: <a href={j.link} target="_blank" rel="noreferrer">página do processo no STF</a> e <a href={j.fonte} target="_blank" rel="noreferrer">placar oficial da sessão virtual</a>.
      </p>
    </article>
  );
}

export default function TribunaisPage() {
  const { data, error } = useData<Tribunais>("tribunais.json");
  const [q, setQ] = useState("");
  const [classe, setClasse] = useState("");
  const [ministro, setMinistro] = useState("");
  const [sit, setSit] = useState<"" | "decidido" | "aberto" | "dividido">("");
  const [limite, setLimite] = useState(30);
  const lista = useMemo(() => (data?.julgamentos || []).filter((j) => (!classe || j.classe === classe)
    && (!ministro || j.votos.some((v) => v.ministro === ministro))
    && (!sit || (sit === "decidido" ? j.situacao === "decidido" : sit === "aberto" ? j.situacao !== "decidido" : j.placar.divergencia > 0))
    && (!q || norm(`${j.processo} ${j.relator} ${j.decisao} ${j.partes.map((p) => p.nome).join(" ")}`).includes(norm(q)))),
  [data, q, classe, ministro, sit]);

  if (!data) return <section><VotacoesAbas /><Loading error={error} /></section>;
  const classes = Object.keys(data.classes);
  const faltando = data.situacao_fontes?.stf && data.situacao_fontes.stf !== "ok" ? data.situacao_fontes.stf : "";
  const decididos = data.julgamentos.filter((j) => j.situacao === "decidido").length;
  const filtrado = !!(q || classe || ministro || sit);
  return (
    <section>
      <VotacoesAbas />
      <h1>Julgamentos do STF</h1>
      <Explain>
        Como cada ministro do Supremo Tribunal Federal votou nas ações que pedem para derrubar ou manter leis e atos do
        governo, e nos recursos que viram regra para todos os casos iguais (repercussão geral), julgados pelo Plenário
        (os 11 ministros) em sessão virtual nos últimos {data.meses} meses. O relator
        apresenta o voto primeiro; cada ministro acompanha o relator ou abre uma divergência. Dados do portal do STF,
        atualizados em {dataBR(data.atualizado_em)}.
      </Explain>
      <Abrir titulo="O que é cada tipo de ação">
        <ul className="small">{classes.map((c) => <li key={c}><strong>{c}</strong>: {data.classes[c]}</li>)}</ul>
      </Abrir>

      <div className="grid" style={{ margin: "12px 0" }}>
        <div className="card"><span className="small muted">Julgamentos na lista</span><strong className="num" style={{ fontSize: "1.6rem" }}>{numero(data.julgamentos.length)}</strong></div>
        <div className="card"><span className="small muted">Decididos</span><strong className="num" style={{ fontSize: "1.6rem" }}>{numero(decididos)}</strong></div>
        <div className="card"><span className="small muted">Com divergência</span><strong className="num" style={{ fontSize: "1.6rem" }}>{numero(data.julgamentos.filter((j) => j.placar.divergencia > 0).length)}</strong></div>
      </div>

      {data.ministros.length > 0 && (
        <>
          <h2>Como cada ministro votou</h2>
          <p className="small muted">"Ficou com a maioria" e "Ficou vencido" contam só os julgamentos decididos: a sessão terminou e um lado teve
            6 votos ou mais (maioria dos 11). O STF publica o resultado oficial alguns dias depois. Clique no nome para ver os julgamentos do ministro.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Ministro</th><th className="r">Votos</th><th className="r">Relator</th><th className="r">Divergiu do relator</th><th className="r">Ficou com a maioria</th><th className="r">Ficou vencido</th><th>Com a maioria</th></tr></thead>
              <tbody>
                {data.ministros.map((m) => {
                  const base = m.com_maioria + m.vencido;
                  const pct = base ? (m.com_maioria / base) * 100 : 0;
                  return (
                    <tr key={m.nome}>
                      <td><button className="link" aria-pressed={ministro === m.nome} onClick={() => { setMinistro(ministro === m.nome ? "" : m.nome); setLimite(30); }}>{m.nome}</button></td>
                      <td className="r num">{numero(m.votos)}</td>
                      <td className="r num">{numero(m.relator)}</td>
                      <td className="r num">{numero(m.divergencias)}</td>
                      <td className="r num">{numero(m.com_maioria)}</td>
                      <td className="r num">{numero(m.vencido)}</td>
                      <td style={{ minWidth: 120 }}>{base > 0 && <div className="stack" role="img" aria-label={`${Math.round(pct)}% com a maioria`} title={`${Math.round(pct)}% com a maioria`}>
                        <span style={{ width: `${pct}%`, background: "var(--s1)" }} /><span style={{ width: `${100 - pct}%`, background: "var(--s2)" }} /></div>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2>Julgamentos <span className="muted small">({lista.length})</span></h2>
      <div className="search">
        <input id="busca-julgamento" aria-label="Buscar julgamento" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Número, assunto ou quem pediu (ex.: ADI 7001)" />
        <select aria-label="Tipo de ação" value={classe} onChange={(e) => setClasse(e.target.value)}>
          <option value="">Todos os tipos</option>{classes.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select aria-label="Ministro" value={ministro} onChange={(e) => setMinistro(e.target.value)}>
          <option value="">Todos os ministros</option>{data.ministros.map((m) => <option key={m.nome}>{m.nome}</option>)}
        </select>
      </div>
      <div className="filtros">
        <fieldset><legend>Situação</legend>
          {([["", "Todos"], ["decidido", "Decididos"], ["aberto", "Ainda sem decisão"], ["dividido", "Com divergência"]] as const).map(([k, n]) => (
            <button key={k} className="fchip" aria-pressed={sit === k} onClick={() => { setSit(k); setLimite(30); }}>{n}</button>
          ))}
        </fieldset>
        {filtrado && <button className="link small" onClick={() => { setQ(""); setClasse(""); setMinistro(""); setSit(""); }}>Limpar filtros ✕</button>}
      </div>
      {lista.length === 0 && <div className="empty">Nenhum julgamento com esses filtros.</div>}
      <div className="proj-col">{lista.slice(0, limite).map((j) => <CartaoJulgamento key={j.id} j={j} explica={data.classes[j.classe]} />)}</div>
      {lista.length > limite && <button className="btn" onClick={() => setLimite(limite + 30)}>Mostrar mais ({lista.length - limite} restantes)</button>}

      <OndeVer links={[
        { nome: "Plenário Virtual do STF", url: "https://portal.stf.jus.br/hotsites/plenariovirtual/", explica: "pauta e placar de cada sessão" },
        { nome: "Corte Aberta (painéis do STF)", url: "https://transparencia.stf.jus.br/extensions/corte_aberta/corte_aberta.html", explica: "estatísticas oficiais de julgamentos" },
      ]} />
      <p className="small muted">
        Ficam de fora as Turmas, os habeas corpus e os recursos de casos individuais: são milhares por semana e decidem a
        situação de uma pessoa, não uma lei. Os julgamentos no plenário presencial ainda não entram. <Link to="/sobre">Como funciona</Link>.
      </p>
      <AvisosFim>
        {faltando && <p className="alert">{faltando === "parcial" ? "Parte das sessões do STF ainda não foi lida; a próxima atualização continua."
          : faltando === "reserva" ? "O portal do STF não respondeu hoje; mostramos os julgamentos já lidos antes."
            : "O portal do STF não respondeu e ainda não há julgamentos guardados."}</p>}
      </AvisosFim>
    </section>
  );
}
