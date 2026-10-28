import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Explain, Loading, useData } from "../components/ui";
import { TEMAS, autorSigla, casaNome, dataBR, dataHoraBR, linkSeguro, type GrupoProjeto, type Projeto, type Tramitacao, type TramitacaoAlmg } from "../data";
import { norm } from "./Home";
import { MG } from "../recorte";
import { VotacoesAbas } from "./Votacoes";
import { AvisosFim } from "../components/Selo";

const ETAPAS_CONGRESSO = ["Apresentada", "Comissões", "Plenário", "Outra Casa", "Sanção ou promulgação"];
const ETAPAS_ALMG = ["Apresentado", "Comissões", "Plenário", "Sanção do governador"];
const EXPLICA_ETAPA = [
  "Um parlamentar, o presidente ou outro autor apresenta a proposta.",
  "Comissões temáticas estudam o texto. Um relator recomenda aprovar, mudar ou rejeitar.",
  "Todos os parlamentares da Casa votam.",
  "Aprovada numa Casa, segue para a outra (Câmara ou Senado), que pode mudar o texto.",
  "O presidente sanciona (vira lei) ou veta. Emendas à Constituição são promulgadas pelo Congresso.",
];
const ABAS: { id: GrupoProjeto | "almg"; nome: string; explica: string }[] = [
  { id: "pauta", nome: "Na pauta", explica: "Marcadas para votação nas próximas sessões do Plenário e reuniões das comissões. A pauta pode mudar até a hora da reunião." },
  { id: "mpv", nome: "Medidas provisórias", explica: "Já valem como lei, mas o Congresso precisa aprovar dentro do prazo, senão perdem a validade." },
  { id: "nova", nome: "Recém-apresentadas", explica: "Propostas que acabaram de chegar. A maioria ainda espera o presidente da Casa dizer por quais comissões vai passar." },
];
const CASA_NOME: Record<string, string> = { camara: "Câmara", senado: "Senado", almg: "Assembleia de Minas" };

function etapaAlmg(i: number) { return i >= 4 ? 3 : Math.min(i, 2); }

export function Etapas({ p }: { p: Projeto }) {
  const almg = p.casa === "almg";
  const nomes = almg ? ETAPAS_ALMG : ETAPAS_CONGRESSO;
  const atual = almg ? etapaAlmg(p.etapa) : p.etapa;
  return (
    <div>
    <ol className="proj-etapas" aria-label={`Etapa atual: ${nomes[atual]}`}>
      {nomes.map((n, i) => (
        <li key={n} className={i < atual ? "feita" : i === atual ? "atual" : ""} aria-current={i === atual ? "step" : undefined}>
          <span>{n}</span>
        </li>
      ))}
    </ol>
    <p className="small so-celular proj-etapa-txt">Etapa {atual + 1} de {nomes.length}: <b>{nomes[atual]}</b></p>
    </div>
  );
}

function Autores({ p }: { p: Projeto }) {
  if (!p.autores.length) return null;
  const mais = p.n_autores - p.autores.length;
  return (
    <p className="small"><b>Quem propôs: </b>
      {p.autores.map((a, k) => (
        <span key={k}>{k > 0 && ", "}{a.id ? <Link to={`/p/${a.id}`}>{a.nome}</Link> : a.nome}{autorSigla(a)}</span>
      ))}
      {mais > 0 && ` e mais ${mais}`}
      {p.veio_da_camara && " · já aprovada pela Câmara"}
    </p>
  );
}

function proximoAlmg(p: Projeto): string {
  const onde = [p.fase, p.onde].filter(Boolean).join(", ");
  return `Situação oficial: ${p.situacao || "sem informação"}${onde ? ` (${onde})` : ""}. A ALMG não publica nos dados abertos a data da próxima votação; veja a agenda na página do projeto.`;
}

export function CartaoProjeto({ p }: { p: Projeto }) {
  const titulo = p.resumo || p.ementa;
  const oficial = linkSeguro(p.url);
  const texto = linkSeguro(p.texto);
  const casa = CASA_NOME[p.casa] || p.casa;
  return (
    <article className="card proj" id={p.id}>
      <div className="row" style={{ gap: 8 }}>
        <span className="chip">{p.nome}</span>
        {p.grupos.includes("pauta") && <span className="status verde">Na pauta</span>}
        {p.sigla === "MPV" && p.prazo && !p.suspenso && <span className="status amarelo">Prazo: {dataBR(p.prazo)}</span>}
        {p.suspenso && <span className="status">Prazo suspenso</span>}
        {p.do_estado && <span className="status">Autor de MG</span>}
        <span className="small muted">{casa}{p.apresentada && ` · apresentada em ${dataBR(p.apresentada)}`}</span>
      </div>
      <h3 className="proj-titulo">{titulo}</h3>
      <Autores p={p} />
      <Etapas p={p} />
      <p className="proj-prox"><b>Próximo passo: </b>{p.casa === "almg" ? proximoAlmg(p) : p.proximo}</p>
      {p.pauta && p.pauta.length > 0 && (
        <ul className="small proj-pauta">
          {p.pauta.map((x, k) => {
            const u = linkSeguro(x.url);
            return (
              <li key={k}><b>{dataHoraBR(x.data)}</b> · {u ? <a href={u} target="_blank" rel="noreferrer">{x.onde}</a> : x.onde}
                {x.urgencia && " · pedido de urgência"}{x.relator && ` · relator: ${x.relator}`}
                {x.parecer && <div className="muted">Parecer: {x.parecer}</div>}</li>
            );
          })}
        </ul>
      )}
      <details className="small">
        <summary>Texto oficial e mais detalhes</summary>
        <div className="proj-col" style={{ marginTop: 8 }}>
          {p.resumo && <p><b>Ementa oficial: </b>{p.ementa}</p>}
          {p.resumo_oficial && p.resumo_oficial !== p.ementa && <p><b>Resumo da ALMG: </b>{p.resumo_oficial}</p>}
          {p.o_que_e && <p><b>O que significa {p.sigla}: </b>{p.o_que_e}</p>}
          {p.situacao && <p><b>Situação oficial: </b>{p.situacao}{p.onde && ` · ${p.onde}`}{p.atualizada && ` (desde ${dataBR(p.atualizada)})`}</p>}
          {p.regime && <p><b>Regime: </b>{p.regime}</p>}
          {p.tranca_pauta && !p.suspenso && <p>A partir de {dataBR(p.tranca_pauta)}, se ainda não tiver sido votada, ela <b>tranca a pauta</b>: a Casa onde está não pode votar outros projetos de lei antes dela.</p>}
          {p.temas && p.temas.length > 0 && <p><b>Temas: </b>{p.temas.join(" · ")}</p>}
          {p.passos && p.passos.length > 0 && (
            <div><b>Últimos passos</b>
              <ul>{p.passos.map((x, k) => <li key={k}>{dataBR(x.data)} · {x.onde}: {x.texto}</li>)}</ul>
            </div>
          )}
          {texto && <p><a href={texto} target="_blank" rel="noreferrer">Ler o texto completo da proposta ↗</a></p>}
        </div>
      </details>
      {oficial && <a className="small" href={oficial} target="_blank" rel="noreferrer">Ver na página oficial {p.casa === "camara" ? "da Câmara" : p.casa === "senado" ? "do Senado" : "da ALMG"} ↗</a>}
    </article>
  );
}

export default function TramitacaoPage() {
  const { data, error } = useData<Tramitacao>("tramitacao.json");
  const { data: almg } = useData<TramitacaoAlmg>(MG ? "almg/tramitacao.json" : null);
  const [params, setParams] = useSearchParams();
  const aba = (params.get("aba") || "pauta") as GrupoProjeto | "almg";
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [tipo, setTipo] = useState("");
  const [tema, setTema] = useState("");
  const [soMG, setSoMG] = useState(false);
  const [limite, setLimite] = useState(40);
  const mudarAba = (a: string) => { setParams(a === "pauta" ? {} : { aba: a }, { replace: true }); setLimite(40); };

  const abas = useMemo(() => [...ABAS, ...(MG ? [{ id: "almg" as const, nome: "Assembleia de Minas", explica: `Projetos de deputados estaduais e do governo de Minas que ainda não viraram lei e tiveram algum passo nos últimos ${almg?.dias_andamento || 30} dias.` }] : [])], [almg]);
  const base = useMemo(() => {
    if (aba === "almg") return almg?.itens || [];
    return (data?.itens || []).filter((p) => p.grupos.includes(aba as GrupoProjeto));
  }, [data, almg, aba]);
  const tipos = useMemo(() => [...new Set(base.map((p) => p.sigla))].sort(), [base]);
  const lista = useMemo(() => base.filter((p) => (!casa || p.casa === casa) && (!tipo || p.sigla === tipo)
    && (!tema || !!p.temas?.includes(tema)) && (!soMG || p.do_estado || p.casa === "almg")
    && (!q || norm(`${p.nome} ${p.sigla} ${p.numero} ${p.ementa} ${p.resumo || ""} ${p.autores.map((a) => `${a.nome} ${a.partido}`).join(" ")}`).includes(norm(q)))),
  [base, casa, tipo, tema, soMG, q]);
  const conta = (id: string) => id === "almg" ? (almg?.itens.length || 0) : (data?.itens || []).filter((p) => p.grupos.includes(id as GrupoProjeto)).length;

  if (!data) return <section><VotacoesAbas /><Loading error={error} /></section>;
  const atual = abas.find((a) => a.id === aba) || abas[0];
  const titulo = aba === "nova" ? `Apresentadas nos últimos ${data.dias_novas} dias` : atual.nome;
  // Na pauta: agrupado por dia da primeira reunião em que aparece
  const porDia: [string, Projeto[]][] = [];
  if (aba === "pauta") {
    for (const p of lista.slice(0, limite)) {
      const d = (p.pauta?.[0]?.data || "").slice(0, 10);
      const g = porDia.find(([k]) => k === d);
      if (g) g[1].push(p); else porDia.push([d, [p]]);
    }
  }
  const faltando = Object.entries(data.situacao_fontes || {}).filter(([, s]) => s !== "ok");

  return (
    <section>
      <VotacoesAbas />
      <h1>Projetos em andamento</h1>
      <Explain>
        O que está sendo proposto agora no Congresso{MG && " e na Assembleia de Minas"}, quem propôs e qual é o próximo passo.
        Tudo vem das APIs oficiais da Câmara e do Senado{MG && " e dos dados abertos da ALMG"}, atualizado em {dataBR(data.atualizado_em)}.
        Esta página mostra o momento atual e não depende do ano escolhido no topo.
      </Explain>

      <details className="card">
        <summary><b>Como uma proposta vira lei</b> (5 etapas)</summary>
        <ol className="proj-como">
          {ETAPAS_CONGRESSO.map((n, i) => <li key={n}><b>{n}.</b> {EXPLICA_ETAPA[i]}</li>)}
        </ol>
        <p className="small muted">PL é projeto de lei, PLP é projeto de lei complementar, PEC muda a Constituição, MPV é medida provisória e PDL é projeto de decreto legislativo. Cada cartão explica o tipo em "Texto oficial e mais detalhes".</p>
      </details>

      <div className="tabs" role="tablist" aria-label="O que acompanhar">
        {abas.map((a) => (
          <button key={a.id} role="tab" aria-selected={aba === a.id} onClick={() => mudarAba(a.id)}>{a.nome} ({conta(a.id)})</button>
        ))}
      </div>
      <p className="small muted">{atual.explica}</p>

      <div className="search">
        <input id="busca-projeto" aria-label="Buscar projeto" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Assunto, número ou autor (ex.: PEC 7)" />
        {aba !== "almg" && (
          <select aria-label="Casa" value={casa} onChange={(e) => setCasa(e.target.value)}>
            <option value="">Câmara e Senado</option><option value="camara">Câmara</option><option value="senado">Senado</option>
          </select>
        )}
        <select aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos os tipos</option>{tipos.map((t) => <option key={t}>{t}</option>)}
        </select>
        {aba !== "almg" && (
          <select aria-label="Tema" value={tema} onChange={(e) => setTema(e.target.value)}>
            <option value="">Todos os temas</option>{TEMAS.map((t) => <option key={t}>{t}</option>)}
          </select>
        )}
        {MG && aba !== "almg" && <label className="small row" style={{ gap: 6 }}><input type="checkbox" checked={soMG} onChange={(e) => setSoMG(e.target.checked)} /> Só de autores de Minas</label>}
      </div>

      <h2>{titulo} <span className="muted small">({lista.length})</span></h2>
      {lista.length === 0 && <div className="empty">{aba === "pauta" ? `Nenhuma proposta marcada para votação nos próximos ${data.dias_pauta} dias com esses filtros.` : "Nenhuma proposta com esses filtros."}</div>}
      {aba === "pauta"
        ? porDia.map(([d, ps]) => (
          <div key={d} className="proj-col">
            <h3 className="eyebrow">{d ? dataHoraBR(d) : "Sem data"}</h3>
            {ps.map((p) => <CartaoProjeto key={p.id} p={p} />)}
          </div>
        ))
        : lista.slice(0, limite).map((p) => <CartaoProjeto key={p.id} p={p} />)}
      {lista.length > limite && <button className="btn" onClick={() => setLimite(limite + 40)}>Mostrar mais ({lista.length - limite} restantes)</button>}
      <p className="small muted">
        Fontes: <a href="https://dadosabertos.camara.leg.br/swagger/api.html" target="_blank" rel="noreferrer">API da Câmara</a> (eventos, pautas e proposições) e{" "}
        <a href="https://legis.senado.leg.br/dadosabertos/docs/" target="_blank" rel="noreferrer">API do Senado</a> (agenda do Plenário, das comissões e processos)
        {MG && <>, e o <a href="https://dadosabertos.almg.gov.br/" target="_blank" rel="noreferrer">arquivo de proposições da ALMG</a></>}.
        O resumo em linguagem simples troca o número da lei pelo nome conhecido e o juridiquês por palavras do dia a dia; a ementa oficial fica sempre nos detalhes. <Link to="/sobre">Como funciona</Link>.
      </p>
      <AvisosFim>
        {faltando.length > 0 && (
          <p className="alert">{faltando.map(([c, s]) => `${casaNome(c as "camara" | "senado")}: ${s === "reserva" ? "a API não respondeu hoje; mostramos a última lista que conseguimos" : "a API não respondeu; essa Casa está faltando"}`).join(". ")}.</p>
        )}
      </AvisosFim>
    </section>
  );
}
