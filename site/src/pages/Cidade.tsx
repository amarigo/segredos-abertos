import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Explain, Loading, useData } from "../components/ui";
import {
  corPartido, linkSeguro, numero, partidoComHoje, type Candidato, type Cidade, type EleicaoGeral, type Legislatura, type MandatoPrefeito,
} from "../data";

/* Página da cidade: quem governou (prefeito e vice) e quem legislou (vereadores) desde 1997, por partido,
   e como a cidade votou nas eleições gerais. Tudo do TSE. O objetivo é saber de qual partido cobrar. */
export default function CidadePage() {
  const { id = "" } = useParams();
  const { data: c, error } = useData<Cidade>(/^[a-z0-9-]+$/.test(id) ? `cidades/${id}.json` : null);
  const [foco, setFoco] = useState("");
  const partidos = useMemo(() => {
    const s = new Set<string>();
    c?.executivo.forEach((m) => s.add(m.prefeito.partido_hoje));
    c?.camara.forEach((l) => l.por_partido.forEach((x) => s.add(x.partido_hoje)));
    return [...s].sort();
  }, [c]);
  if (!/^[a-z0-9-]+$/.test(id)) return <div className="empty">Cidade não encontrada. <Link to="/cidades">Ver as cidades</Link></div>;
  if (!c) return <Loading error={error} />;
  const atual = c.executivo[0];
  const camaraAtual = c.camara[0];
  const desde = c.executivo.length ? c.executivo[c.executivo.length - 1].inicio : null;
  const fonteTSE = "https://dadosabertos.tse.jus.br/dataset/?groups=resultados";

  return (
    <>
      <section>
        <span className="eyebrow">Cidade · {c.uf}</span>
        <h1>{c.nome}</h1>
        <p style={{ fontSize: "1.05rem", maxWidth: 760 }}>
          Quem governou e quem legislou em {c.nome}{desde ? ` desde ${desde}` : ""}, e de qual partido. Prefeito e vereadores são eleitos juntos,
          a cada quatro anos. O prefeito executa: cuida da saúde, das escolas, das ruas e do orçamento da cidade. Os vereadores fazem as leis
          municipais, aprovam o orçamento e fiscalizam o prefeito.
        </p>
      </section>

      {c.avisos.length > 0 && (
        <div className="alert" role="note"><div><strong>Dados incompletos.</strong><ul>{c.avisos.map((a) => <li key={a}>{a}</li>)}</ul></div></div>
      )}

      {atual && (
        <section>
          <h2>De quem cobrar hoje</h2>
          <div className="grid">
            <div className="card stat">
              <span className="label">Prefeito ({atual.inicio} a {atual.fim})</span>
              <span className="value cidade-quem">{atual.prefeito.nome}</span>
              <span><PartidoTag p={atual.prefeito.partido} hoje={atual.prefeito.partido_hoje} /></span>
              <span className="hint">Eleito em {atual.eleicao}{atual.prefeito.pct != null ? ` com ${pctTxt(atual.prefeito.pct)} dos votos válidos` : ""}{atual.turnos > 1 ? ", no 2º turno" : ""}.</span>
            </div>
            <div className="card stat">
              <span className="label">Vice-prefeito</span>
              {atual.vice ? (
                <>
                  <span className="value cidade-quem">{atual.vice.nome}</span>
                  <span><PartidoTag p={atual.vice.partido} hoje={atual.vice.partido_hoje} /></span>
                </>
              ) : <span className="muted">Não encontrado na lista de candidatos do TSE</span>}
              {atual.coligacao.partidos.length > 1 && <span className="hint">Coligação: {atual.coligacao.partidos.join(", ")}</span>}
            </div>
            {camaraAtual && camaraAtual.eleicao === atual.eleicao && (
              <div className="card stat">
                <span className="label">Câmara Municipal ({camaraAtual.inicio} a {camaraAtual.fim})</span>
                <span className="value">{camaraAtual.vagas} vereadores</span>
                <Maioria l={camaraAtual} m={atual} />
              </div>
            )}
          </div>
        </section>
      )}

      <section>
        <h2>Em resumo</h2>
        <Resumo c={c} />
      </section>

      {partidos.length > 1 && (
        <section className="cidade-foco">
          <label htmlFor="foco-partido"><strong>Ver a história de um partido:</strong></label>{" "}
          <select id="foco-partido" value={foco} onChange={(e) => setFoco(e.target.value)}>
            <option value="">Todos os partidos</option>
            {partidos.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          {foco && <HistoriaPartido c={c} p={foco} />}
        </section>
      )}

      <section>
        <h2>Quem foi prefeito</h2>
        <Explain>Cada faixa é um mandato de quatro anos, na cor do partido do prefeito. Partidos que mudaram de nome ou se juntaram a outro aparecem com o nome de hoje entre parênteses: o PMDB, por exemplo, hoje se chama MDB.</Explain>
        <LinhaDoTempo mandatos={c.executivo} foco={foco} />
        <ol className="mandatos">
          {c.executivo.map((m) => <Mandato key={m.eleicao} m={m} apagado={!!foco && m.prefeito.partido_hoje !== foco} />)}
        </ol>
        <TempoPorPartido c={c} />
      </section>

      <section>
        <h2>Quem esteve na Câmara Municipal</h2>
        <Explain>Cada quadradinho é uma cadeira de vereador, na cor do partido. As cadeiras com borda escura são de partidos da coligação que elegeu o prefeito naquela eleição: quando passam da metade, o prefeito começou o mandato com maioria para aprovar o que quisesse.</Explain>
        <div className="legislaturas">
          {c.camara.map((l) => <Camara key={l.eleicao} l={l} m={c.executivo.find((m) => m.eleicao === l.eleicao)} foco={foco} />)}
        </div>
        <CadeirasPorPartido c={c} />
      </section>

      {c.gerais.length > 0 && <ComoVotou nome={c.nome} gerais={c.gerais} />}

      <section>
        <h2>Limites destes dados</h2>
        <ul className="small">
          <li>Os dados são do <a href={fonteTSE} target="_blank" rel="noreferrer">Tribunal Superior Eleitoral (TSE)</a>, com os resultados de cada eleição desde 1996.</li>
          <li>O partido é o do dia da eleição. Trocas de partido durante o mandato, cassações, renúncias e suplentes que assumiram a cadeira não aparecem aqui.</li>
          <li>Eleições suplementares (quando a eleição é refeita no meio do mandato) ficam de fora.</li>
          <li>Os percentuais são dos votos dados aos candidatos (votos válidos), sem brancos e nulos.</li>
          <li>Ter maioria na eleição não garante maioria o mandato todo: vereadores mudam de lado e de partido.</li>
        </ul>
        {c.links.length > 0 && (
          <p className="small">Sites oficiais: {c.links.filter((x) => linkSeguro(x.url)).map((x, i) => (
            <span key={x.url}>{i > 0 && " · "}<a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">{x.nome} ↗</a></span>
          ))}</p>
        )}
      </section>
    </>
  );
}

const pctTxt = (v: number | null | undefined) => (v == null ? "—" : `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`);

function PartidoTag({ p, hoje }: { p: string; hoje?: string | null }) {
  return <span className="partido-tag"><i className="partido-cor" style={{ background: corPartido(hoje || p) }} />{partidoComHoje(p, hoje)}</span>;
}

function Maioria({ l, m }: { l: Legislatura; m?: MandatoPrefeito }) {
  if (!m) return null;
  const maioria = l.da_coligacao_do_prefeito * 2 > l.vagas;
  return (
    <span className="hint">
      O partido do prefeito ({m.prefeito.partido}) elegeu {l.do_partido_do_prefeito} {l.do_partido_do_prefeito === 1 ? "vereador" : "vereadores"}
      {m.coligacao.partidos.length > 1 ? `; a coligação dele, ${l.da_coligacao_do_prefeito}` : ""} de {l.vagas}.{" "}
      <strong className={maioria ? "txt-sim" : "txt-nao"}>{maioria ? "Começou com maioria." : "Começou sem maioria."}</strong>
    </span>
  );
}

function Resumo({ c }: { c: Cidade }) {
  const r = c.resumo;
  const frases: React.ReactNode[] = [];
  const lider = r.anos_por_partido[0];
  if (lider && c.executivo.length) {
    const desde = c.executivo[c.executivo.length - 1].inicio, ate = c.executivo[0].fim;
    const antigas = lider.siglas.filter((s) => s !== lider.partido);
    const empate = r.anos_por_partido.filter((x) => x.anos === lider.anos);
    frases.push(empate.length > 1
      ? <>De {desde} a {ate}, nenhum partido ficou mais tempo que os outros na prefeitura de {c.nome}: {empate.map((x) => x.partido).join(", ")} governaram {lider.anos} anos cada.</>
      : <>De {desde} a {ate}, o partido que mais tempo governou {c.nome} foi o <strong>{lider.partido}</strong>: {lider.anos} anos{antigas.length ? `, contando quando se chamava ${antigas.join(" e ")}` : ""}.</>);
    frases.push(<>{r.anos_por_partido.length} {r.anos_por_partido.length === 1 ? "partido elegeu" : "partidos diferentes elegeram"} prefeito em {r.mandatos} eleições.</>);
  }
  const top = r.cadeiras_por_partido[0];
  if (top) frases.push(<>Na Câmara, somando todas as eleições, o partido que mais elegeu vereadores foi o <strong>{top.partido}</strong>, com {top.cadeiras} cadeiras.</>);
  if (r.camaras) {
    frases.push(<>Em {r.coligacao_do_prefeito_com_maioria} de {r.camaras} eleições, a coligação do prefeito eleito também elegeu a maioria dos vereadores.</>);
  }
  return <ul className="resumo-cidade">{frases.map((f, i) => <li key={i}>{f}</li>)}</ul>;
}

function HistoriaPartido({ c, p }: { c: Cidade; p: string }) {
  const mandatos = c.executivo.filter((m) => m.prefeito.partido_hoje === p).slice().reverse();
  const vices = c.executivo.filter((m) => m.vice?.partido_hoje === p && m.prefeito.partido_hoje !== p).slice().reverse();
  const cadeiras = c.camara.slice().reverse().map((l) => ({ l, n: l.por_partido.filter((x) => x.partido_hoje === p).reduce((a, x) => a + x.cadeiras, 0) }));
  const total = cadeiras.reduce((a, x) => a + x.n, 0);
  const siglas = new Set<string>();
  c.executivo.forEach((m) => m.prefeito.partido_hoje === p && siglas.add(m.prefeito.partido));
  c.camara.forEach((l) => l.por_partido.forEach((x) => x.partido_hoje === p && siglas.add(x.partido)));
  const antigas = [...siglas].filter((s) => s !== p);
  return (
    <div className="card historia">
      <h3><i className="partido-cor" style={{ background: corPartido(p) }} />{p}{antigas.length > 0 && <span className="muted small"> (antes {antigas.join(", ")})</span>}</h3>
      <p>{mandatos.length
        ? <>Governou {c.nome} em {mandatos.map((m) => `${m.inicio}–${m.fim}`).join(", ")}, com {mandatos.map((m) => m.prefeito.nome).join(", ")}.</>
        : <>Não elegeu prefeito em {c.nome} no período.</>}
        {vices.length > 0 && <> Teve o vice-prefeito em {vices.map((m) => `${m.inicio}–${m.fim}`).join(", ")}.</>}
      </p>
      <p>Elegeu {total} {total === 1 ? "vereador" : "vereadores"} somando todas as eleições: {cadeiras.map(({ l, n }) => `${n} em ${l.eleicao}`).join(", ")}.</p>
    </div>
  );
}

function LinhaDoTempo({ mandatos, foco }: { mandatos: MandatoPrefeito[]; foco: string }) {
  if (!mandatos.length) return <div className="empty">Sem dados de prefeitos.</div>;
  const ord = mandatos.slice().reverse();
  return (
    <div className="linha-tempo" role="img" aria-label={`Partido de cada prefeito: ${ord.map((m) => `${m.inicio} a ${m.fim}, ${m.prefeito.partido}`).join("; ")}`}>
      <div className="linha-faixas">
        {ord.map((m) => (
          <span key={m.eleicao} title={`${m.inicio}–${m.fim}: ${m.prefeito.nome} (${partidoComHoje(m.prefeito.partido, m.prefeito.partido_hoje)})`}
            style={{ background: corPartido(m.prefeito.partido_hoje), opacity: foco && m.prefeito.partido_hoje !== foco ? 0.18 : 1 }} />
        ))}
      </div>
      <div className="linha-rotulos" aria-hidden="true">
        {ord.map((m) => <span key={m.eleicao}><strong>{m.prefeito.partido}</strong><small>{m.inicio}</small></span>)}
      </div>
    </div>
  );
}

function Mandato({ m, apagado }: { m: MandatoPrefeito; apagado: boolean }) {
  const ultimo = m.candidatos.filter((x) => x.turno === m.turnos);
  return (
    <li className={`mandato${apagado ? " apagado" : ""}`} style={{ borderLeftColor: corPartido(m.prefeito.partido_hoje) }}>
      <div className="mandato-topo">
        <span className="num">{m.inicio}–{m.fim}</span>
        <strong>{m.prefeito.nome}</strong>
        <PartidoTag p={m.prefeito.partido} hoje={m.prefeito.partido_hoje} />
      </div>
      <div className="small muted">
        {m.vice ? <>Vice: {m.vice.nome} ({partidoComHoje(m.vice.partido, m.vice.partido_hoje)}). </> : null}
        Eleito em {m.eleicao}{m.prefeito.pct != null ? ` com ${pctTxt(m.prefeito.pct)} dos votos válidos` : ""}{m.turnos > 1 ? " no 2º turno" : ""}.
        {m.coligacao.partidos.length > 1 && <> Coligação{m.coligacao.nome ? ` "${m.coligacao.nome}"` : ""}: {m.coligacao.partidos.join(", ")}.</>}
      </div>
      {m.prefeito.mudou && <div className="small muted">O {m.prefeito.partido} {m.prefeito.mudou}.</div>}
      <details className="small">
        <summary>Ver todos os candidatos de {m.eleicao}</summary>
        {[...new Set(m.candidatos.map((x) => x.turno || 1))].map((t) => (
          <div key={t} style={{ marginTop: 8 }}>
            {m.turnos > 1 && <strong>{t}º turno</strong>}
            <BarrasPct itens={m.candidatos.filter((x) => (x.turno || 1) === t)} />
          </div>
        ))}
        {ultimo.length === 0 && <p className="muted">Sem a lista de candidatos.</p>}
      </details>
    </li>
  );
}

function TempoPorPartido({ c }: { c: Cidade }) {
  const max = Math.max(1, ...c.resumo.anos_por_partido.map((x) => x.anos));
  if (!c.resumo.anos_por_partido.length) return null;
  return (
    <>
      <h3 style={{ marginTop: 20 }}>Anos no comando da prefeitura, por partido</h3>
      <div className="bars" style={{ marginTop: 8 }}>
        {c.resumo.anos_por_partido.map((x) => (
          <div className="bar-row" key={x.partido}>
            <span><i className="partido-cor" style={{ background: corPartido(x.partido) }} /><strong>{x.partido}</strong>
              {x.siglas.some((s) => s !== x.partido) && <span className="muted small"> (inclui {x.siglas.filter((s) => s !== x.partido).join(", ")})</span>}</span>
            <span className="num">{x.anos} anos</span>
            <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(x.anos / max) * 100}%`, background: corPartido(x.partido) }} /></div>
          </div>
        ))}
      </div>
    </>
  );
}

function Camara({ l, m, foco }: { l: Legislatura; m?: MandatoPrefeito; foco: string }) {
  const cadeiras = l.por_partido.flatMap((x) => Array.from({ length: x.cadeiras }, () => x));
  return (
    <div className="card legislatura">
      <div className="mandato-topo"><span className="num">{l.inicio}–{l.fim}</span><strong>{l.vagas} vereadores</strong>
        {m && <span className="small muted">prefeito: {m.prefeito.nome} ({m.prefeito.partido})</span>}</div>
      <div className="cadeiras" role="img" aria-label={`Cadeiras por partido: ${l.por_partido.map((x) => `${x.partido} ${x.cadeiras}`).join(", ")}`}>
        {cadeiras.map((x, i) => (
          <span key={i} className={`cadeira${x.da_coligacao ? " colig" : ""}`} title={partidoComHoje(x.partido, x.partido_hoje)}
            style={{ background: corPartido(x.partido_hoje), opacity: foco && x.partido_hoje !== foco ? 0.18 : 1 }} />
        ))}
      </div>
      <div className="legend">
        {l.por_partido.map((x) => (
          <span key={x.partido}><i style={{ background: corPartido(x.partido_hoje) }} />{partidoComHoje(x.partido, x.partido_hoje)}: {x.cadeiras}</span>
        ))}
      </div>
      <Maioria l={l} m={m} />
      <details className="small">
        <summary>Ver os vereadores eleitos</summary>
        <ul className="eleitos">{l.eleitos.map((e) => <li key={e.nome + e.partido}>{e.nome} <span className="muted">({e.partido}, {numero(e.votos)} votos)</span></li>)}</ul>
      </details>
    </div>
  );
}

function CadeirasPorPartido({ c }: { c: Cidade }) {
  const lista = c.resumo.cadeiras_por_partido;
  if (!lista.length) return null;
  const max = Math.max(1, ...lista.map((x) => x.cadeiras));
  return (
    <>
      <h3 style={{ marginTop: 20 }}>Vereadores eleitos por partido, somando todas as eleições</h3>
      <div className="bars" style={{ marginTop: 8 }}>
        {lista.map((x) => (
          <div className="bar-row" key={x.partido}>
            <span><i className="partido-cor" style={{ background: corPartido(x.partido) }} /><strong>{x.partido}</strong></span>
            <span className="num">{x.cadeiras}</span>
            <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(x.cadeiras / max) * 100}%`, background: corPartido(x.partido) }} /></div>
          </div>
        ))}
      </div>
    </>
  );
}

function BarrasPct({ itens, eleitoTxt = "eleito" }: { itens: Candidato[]; eleitoTxt?: string }) {
  return (
    <div className="bars" style={{ marginTop: 6 }}>
      {itens.map((x, i) => (
        <div className="bar-row" key={i}>
          <span>{x.nome} <span className="muted">({x.partido})</span>{x.eleito && <> <span className="chip ok">{eleitoTxt}</span></>}</span>
          <span className="num">{pctTxt(x.pct)} <span className="muted small">· {numero(x.votos)}</span></span>
          <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${x.pct || 0}%`, background: corPartido(x.partido) }} /></div>
        </div>
      ))}
    </div>
  );
}

const ELEITO_EM: Record<string, string> = { Presidente: "eleito presidente", Governador: "eleito governador", Senador: "eleito senador" };

function ComoVotou({ nome, gerais }: { nome: string; gerais: EleicaoGeral[] }) {
  const [ano, setAno] = useState(gerais[0].eleicao);
  const g = gerais.find((x) => x.eleicao === ano) || gerais[0];
  return (
    <section>
      <h2>Como {nome} votou nas eleições gerais</h2>
      <Explain>Os mais votados na cidade para presidente, governador, senador e deputados. "Eleito" quer dizer que o candidato ganhou no país ou no estado, não só na cidade. Para deputado, mostramos os 10 mais votados na cidade.</Explain>
      <div className="row" role="group" aria-label="Eleição" style={{ margin: "10px 0" }}>
        {gerais.map((x) => (
          <button key={x.eleicao} className={`chip ${x.eleicao === g.eleicao ? "ok" : ""}`} aria-pressed={x.eleicao === g.eleicao} onClick={() => setAno(x.eleicao)}>{x.eleicao}</button>
        ))}
      </div>
      <div className="two">
        {g.cargos.map((cg) => (
          <div key={`${cg.cargo}-${cg.turno}`} className="card">
            <h3>{cg.cargo}{g.cargos.some((o) => o.cargo === cg.cargo && o.turno !== cg.turno) ? `, ${cg.turno}º turno` : ""}</h3>
            <span className="small muted">{numero(cg.total_votos)} votos válidos em {nome}{cg.n_candidatos > cg.candidatos.length ? `; os ${cg.candidatos.length} mais votados de ${cg.n_candidatos}` : ""}</span>
            <BarrasPct itens={cg.candidatos} eleitoTxt={ELEITO_EM[cg.cargo] || "eleito"} />
          </div>
        ))}
      </div>
    </section>
  );
}
