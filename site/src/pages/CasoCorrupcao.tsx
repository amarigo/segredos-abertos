import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Explain, useData } from "../components/ui";
import { dataBR, linkSeguro, type Resumo } from "../data";
import { ATUALIZADO_EM, CASOS } from "../corrupcao/dados";
import { campoPartido, corCampo } from "../corrupcao/partidos";
import { ORDEM, STATUS } from "../corrupcao/placar";
import type { Fonte, Pessoa, Status, Visao } from "../corrupcao/tipos";
import { PartidoChip, SituacaoChip } from "./Corrupcao";
import { norm } from "./Home";
import "./corrupcao.css";

function Fontes({ fontes, curto }: { fontes: Fonte[]; curto?: boolean }) {
  const ok = fontes.filter((f) => linkSeguro(f.url));
  if (!ok.length) return null;
  return (
    <span className="fontes small">
      {curto ? "Fontes: " : ""}
      {ok.map((f, i) => (
        <span key={f.url + i}>{i > 0 && " · "}<a href={linkSeguro(f.url)} target="_blank" rel="noreferrer">{curto ? `[${i + 1}]` : f.nome} ↗</a></span>
      ))}
    </span>
  );
}

const fotoOficial = (p: Pessoa) => (p.camara ? `https://www.camara.leg.br/internet/deputado/bandep/${p.camara}.jpg`
  : p.senado ? `https://www.senado.leg.br/senadores/img/fotos-oficiais/senador${p.senado}.jpg` : undefined);
const perfilOficial = (p: Pessoa) => (p.camara ? `https://www.camara.leg.br/deputados/${p.camara}`
  : p.senado ? `https://www25.senado.leg.br/web/senadores/senador/-/perfil/${p.senado}` : undefined);

/** Iniciais para quem não tem foto oficial (empresários, servidores) ou quando a foto não carrega */
function Iniciais({ nome }: { nome: string }) {
  const ini = nome.replace(/\(.*\)/, "").split(/\s+/).filter((x) => x.length > 2 || /^[A-Z]/.test(x)).slice(0, 2).map((x) => x[0]).join("");
  return <span className="avatar foto-iniciais" aria-hidden="true">{ini}</span>;
}

function Foto({ p, url }: { p: Pessoa; url?: string }) {
  const [erro, setErro] = useState(false);
  if (!url || erro) return <Iniciais nome={p.nome} />;
  return <img className="foto-pessoa" src={url} alt={`Foto de ${p.nome}`} loading="lazy" referrerPolicy="no-referrer" onError={() => setErro(true)} />;
}

function CartaoPessoa({ p, noMandato }: { p: Pessoa; noMandato?: Resumo }) {
  const foto = linkSeguro(noMandato?.foto) || fotoOficial(p);
  const oficial = perfilOficial(p);
  return (
    <article className="pessoa-card card" id={norm(p.nome).replace(/[^a-z]+/g, "-")}>
      <div className="pessoa-topo">
        <Foto p={p} url={foto} />
        <div style={{ minWidth: 0 }}>
          <h3 className="pessoa-nome">{p.nome}</h3>
          <div className="muted small">{p.papel}</div>
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            <span className="chip status" style={{ borderColor: STATUS[p.status].cor }} title={STATUS[p.status].explica}>
              <i style={{ background: STATUS[p.status].cor }} />{STATUS[p.status].um}
            </span>
            {p.partido && <PartidoChip sigla={p.partido} />}
            {p.partido && <span className="campo-chip small" style={{ borderColor: corCampo(campoPartido(p.partido)) }}>{campoPartido(p.partido)}</span>}
          </div>
        </div>
      </div>
      <p className="pessoa-detalhe">{p.detalhe}</p>
      <dl className="pessoa-kv small">
        {p.pena && <><dt>Pena</dt><dd>{p.pena}</dd></>}
        {p.acordo && <><dt>Acordo</dt><dd>{p.acordo}</dd></>}
        {p.cassado && <><dt>Mandato</dt><dd>{p.cassado}</dd></>}
        <dt>Onde está</dt>
        <dd>
          {p.onde}
          {noMandato && <> <Link to={`/p/${noMandato.id}`}>Ver o perfil no site ({noMandato.cargo}, {noMandato.partido}-{noMandato.uf})</Link></>}
          {!noMandato && oficial && <> <a href={oficial} target="_blank" rel="noreferrer">Página oficial ↗</a></>}
        </dd>
      </dl>
      {p.repete && <p className="small muted" style={{ margin: 0 }}>Também aparece no caso <Link to={`/corrupcao/${p.repete}`}>{CASOS.find((c) => c.id === p.repete)?.nome}</Link>; no placar conta só uma vez.</p>}
      <Fontes fontes={p.fontes} curto />
    </article>
  );
}

function ColunaVisao({ titulo, v, cls }: { titulo: string; v: Visao; cls: string }) {
  return (
    <div className={`card visao ${cls}`}>
      <h3 style={{ margin: 0 }}>{titulo}</h3>
      <ul>{v.texto.map((t, i) => <li key={i}>{t}</li>)}</ul>
      <Fontes fontes={v.fontes} curto />
    </div>
  );
}

export default function CasoCorrupcao() {
  const { id } = useParams();
  const caso = CASOS.find((c) => c.id === id);
  const [filtro, setFiltro] = useState<Status | "">("");
  // Quem está no mandato hoje: liga a pessoa ao perfil do site pelo id oficial da Câmara ou do Senado
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const mandato = useMemo(() => new Map((pols || []).map((p) => [p.id, p])), [pols]);
  if (!caso) return <div className="empty">Caso não encontrado. <Link to="/corrupcao">Ver todos os casos</Link></div>;
  const noMandato = (p: Pessoa) => (p.camara ? mandato.get(`dep-${p.camara}`) : undefined) || (p.senado ? mandato.get(`sen-${p.senado}`) : undefined);
  const presentes = ORDEM.filter((s) => caso.pessoas.some((p) => p.status === s));
  const pessoas = caso.pessoas.filter((p) => !filtro || p.status === filtro);
  return (
    <>
      <p className="small"><Link to="/corrupcao">← Todos os casos</Link></p>
      <section className="hero">
        <span className="eyebrow">Corrupção · {caso.periodo}</span>
        <h1 style={{ margin: 0 }}>{caso.nome}</h1>
        <p className="muted" style={{ margin: 0 }}>{caso.subtitulo}</p>
        <div className="row"><SituacaoChip s={caso.situacao} /><span className="small">{caso.situacaoTexto}</span></div>
      </section>

      <div className="two" style={{ marginTop: 16 }}>
        <div>{caso.resumo.map((t, i) => <p key={i}>{t}</p>)}</div>
        <div className="card stat">
          <span className="label">Dinheiro envolvido</span>
          <span className="value">{caso.valor.texto}</span>
          <span className="hint">{caso.valor.nota}</span>
          <Fontes fontes={[caso.valor.fonte]} />
        </div>
      </div>

      <section>
        <h2>Linha do tempo</h2>
        <ol className="timeline">
          {caso.timeline.map((e, i) => (
            <li key={i}>
              <span className="tl-data num">{e.data}</span>
              <span className="tl-texto">{e.texto} {e.fonte && <Fontes fontes={[e.fonte]} curto />}</span>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2>Quem está envolvido</h2>
        <Explain>Ser citado ou investigado não é ser culpado. A etiqueta colorida diz em que pé está cada pessoa na Justiça. Passe o mouse para ver o que cada uma quer dizer.</Explain>
        {presentes.length > 1 && (
          <div className="tabs" role="group" aria-label="Filtrar por situação" style={{ margin: "12px 0" }}>
            <button aria-pressed={!filtro} onClick={() => setFiltro("")}>Todos ({caso.pessoas.length})</button>
            {presentes.map((s) => (
              <button key={s} aria-pressed={filtro === s} onClick={() => setFiltro(s)}>{STATUS[s].nome} ({caso.pessoas.filter((p) => p.status === s).length})</button>
            ))}
          </div>
        )}
        <div className="pessoas-grid">{pessoas.map((p) => <CartaoPessoa key={p.nome} p={p} noMandato={noMandato(p)} />)}</div>
        {caso.grupos && (
          <>
            <h3>Outros citados, por partido</h3>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Partido</th><th>Campo</th><th className="num">Pessoas</th><th>Situação</th></tr></thead>
                <tbody>
                  {caso.grupos.map((g) => (
                    <tr key={g.partido}>
                      <td><PartidoChip sigla={g.partido} /></td>
                      <td>{campoPartido(g.partido)}</td>
                      <td className="num">{g.n}</td>
                      <td>{g.nota} <Fontes fontes={[g.fonte]} curto /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      {caso.acordos.length > 0 && (
        <section>
          <h2>Delações premiadas e acordos</h2>
          <p className="small muted">Na delação premiada, um acusado conta o que sabe em troca de pena menor. No acordo de leniência, uma empresa admite os crimes e devolve dinheiro para poder continuar trabalhando.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Tipo</th><th>Quem</th><th>Quando</th><th>O que foi</th></tr></thead>
              <tbody>
                {caso.acordos.map((a, i) => (
                  <tr key={i}><td>{a.tipo}</td><td>{a.quem}</td><td className="num">{a.quando}</td><td>{a.resumo} <Fontes fontes={[a.fonte]} curto /></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {caso.empresas.length > 0 && (
        <section>
          <h2>Empresas envolvidas</h2>
          <p className="small muted">Se a empresa (ou outra do mesmo grupo) tem contrato com o governo federal ou foi punida, o Portal da Transparência mostra na hora: use o link de cada uma.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Empresa</th><th>Papel no caso</th><th>Situação hoje</th><th>Relação com o governo</th></tr></thead>
              <tbody>
                {caso.empresas.map((e) => (
                  <tr key={e.nome}>
                    <td><strong>{e.nome}</strong></td>
                    <td>{e.papel}</td>
                    <td>{e.hoje}</td>
                    <td>
                      {e.governo}
                      {e.busca && <> <a href={`https://portaldatransparencia.gov.br/busca?termo=${encodeURIComponent(e.busca)}`} target="_blank" rel="noreferrer">Ver no Portal da Transparência ↗</a></>}
                      {" "}<Fontes fontes={e.fontes} curto />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <h2>O que dizem a esquerda, a direita e a Justiça</h2>
        <Explain>Os dois primeiros quadros resumem os argumentos que cada lado costuma usar sobre o caso. Não são conclusões do site. O terceiro diz o que a Justiça, a polícia ou o Ministério Público decidiram até agora.</Explain>
        <div className="visoes">
          <ColunaVisao titulo="O que diz a esquerda" v={caso.visoes.esquerda} cls="visao-esq" />
          <ColunaVisao titulo="O que diz a direita" v={caso.visoes.direita} cls="visao-dir" />
          <ColunaVisao titulo="O que diz a Justiça" v={caso.visoes.justica} cls="visao-just" />
        </div>
      </section>

      <section>
        <h2>Fontes principais</h2>
        <ul className="small">{caso.fontes.map((f) => <li key={f.url}><Fontes fontes={[f]} /></li>)}</ul>
        <p className="small muted">Situação conferida em {dataBR(ATUALIZADO_EM)}. Viu algo desatualizado? Abra um aviso no <a href="https://github.com/amarigo/segredos-abertos/issues" target="_blank" rel="noreferrer">GitHub</a>.</p>
      </section>
    </>
  );
}
