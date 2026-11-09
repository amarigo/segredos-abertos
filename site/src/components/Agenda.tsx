import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarioAno, type MarcaDia } from "./CalendarioAno";
import { LinkNota, Loading, VotoChip, useData } from "./ui";
import { MESES_LONGOS, dataBR, linkSeguro, reais, type AgendaAno, type NotasPolitico, type Politico, type VotacaoResumo } from "../data";

const SEMANA_LONGA = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
const SEMANA_CURTA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const MES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const LINK_EVENTO = (id: number) => `https://www.camara.leg.br/evento-legislativo/${id}`;
const API_PRESENCA = (id: number) => `https://dadosabertos.camara.leg.br/api/v2/eventos/${id}/deputados`;
const AUSENTE = new Set(["Ausente", "Licença", "Em missão", "Em atividade parlamentar", "—", ""]);

type Filtro = "todos" | "presenca" | "gastos" | "conferir";
interface NotaDia { categoria: string; fornecedor: string; doc: string; valor: number; url: string; link: string; detalhe: string }
interface Dia {
  dia: string;
  eventos: NonNullable<AgendaAno["dias"][string]["e"]>;
  votos: NonNullable<AgendaAno["dias"][string]["v"]>;
  notas: NotaDia[]; conferir: AgendaAno["conferir"]; total: number; presente: boolean; texto: string;
}

const semana = (d: string) => new Date(`${d}T12:00:00Z`).getUTCDay();
const diaLongo = (d: string) => `${SEMANA_LONGA[semana(d)]}, ${Number(d.slice(8))} de ${MESES_LONGOS[Number(d.slice(5, 7)) - 1]} de ${d.slice(0, 4)}`;
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Dia a dia de um parlamentar: onde registrou presença e o que gastou em cada data, lado a lado.
 *  Visual de caixa de entrada: calendário do ano no alto, a lista de dias à esquerda e o dia aberto à direita. */
export function AgendaPolitico({ p, ano }: { p: Politico; ano: string }) {
  const d = p.anos[ano];
  const { data: ag, error } = useData<AgendaAno>(d?.agenda ? `p/agenda/${p.id}-${ano}.json` : null);
  const { data: ns } = useData<NotasPolitico>(d?.n_notas ? `p/notas/${p.id}-${ano}.json` : null);
  const { data: vots } = useData<VotacaoResumo[]>(d?.agenda ? "votacoes.json" : null);
  const [params, setParams] = useSearchParams();
  const sel = params.get("dia");
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [busca, setBusca] = useState("");
  const [mostrar, setMostrar] = useState(40);
  const painel = useRef<HTMLDivElement>(null);
  const casa = p.casa === "camara" ? "deputado" : "senador";

  const dias = useMemo(() => {
    if (!ag) return [] as Dia[];
    const m = new Map<string, Dia>();
    const novo = (k: string): Dia => ({ dia: k, eventos: [], votos: [], notas: [], conferir: [], total: 0, presente: false, texto: "" });
    for (const [k, x] of Object.entries(ag.dias)) m.set(k, { ...novo(k), eventos: x.e || [], votos: x.v || [] });
    if (ns) {
      const c = Object.fromEntries(ns.colunas.map((n, i) => [n, i]));
      for (const r of ns.notas) {
        const k = String(r[c.data] || "").slice(0, 10);
        if (!k.startsWith(ano)) continue;
        const dd = m.get(k) || novo(k);
        dd.notas.push({ categoria: String(r[c.categoria]), fornecedor: String(r[c.fornecedor]), doc: String(r[c.doc]),
          valor: Number(r[c.valor]), url: String(r[c.url] || ""), link: String(r[c.link] || ""), detalhe: String(r[c.detalhe] || "") });
        dd.total += Number(r[c.valor]);
        m.set(k, dd);
      }
    }
    for (const x of ag.conferir) m.get(x.data)?.conferir.push(x);
    for (const dd of m.values()) {
      dd.presente = dd.eventos.length > 0 || dd.votos.some((v) => !AUSENTE.has(v[1]));
      const lugar = (doc: string) => ag.lugares[doc] ? `${ag.lugares[doc][0]} ${ag.lugares[doc][1]}` : "";
      dd.texto = norm([...dd.eventos.map((e) => `${e[1]} ${e[2]} ${e[3]} ${e[4]}`), ...dd.votos.map((v) => v[1]),
        ...dd.notas.map((n) => `${n.categoria} ${n.fornecedor} ${lugar(n.doc)} ${n.detalhe}`)].join(" "));
    }
    return [...m.values()].sort((a, b) => b.dia.localeCompare(a.dia));
  }, [ag, ns, ano]);

  const conta = useMemo(() => ({
    todos: dias.length, presenca: dias.filter((x) => x.presente).length,
    gastos: dias.filter((x) => x.notas.length).length, conferir: dias.filter((x) => x.conferir.length).length,
  }), [dias]);
  const q = norm(busca.trim());
  const lista = dias.filter((x) => (filtro === "todos" || (filtro === "presenca" ? x.presente : filtro === "gastos" ? x.notas.length > 0 : x.conferir.length > 0))
    && (!q || x.texto.includes(q)));
  const marcas = useMemo(() => {
    const m = new Map<string, MarcaDia>();
    for (const x of lista) {
      const partes = [x.presente ? (x.eventos.length ? `presença em ${x.eventos.length} evento${x.eventos.length > 1 ? "s" : ""}` : "votou no Plenário") : "",
        x.notas.length ? `${x.notas.length} nota${x.notas.length > 1 ? "s" : ""}, ${reais(x.total)}` : "",
        !x.presente && x.votos.length ? x.votos[0][1].toLowerCase() : "", x.conferir.length ? "ponto para conferir" : ""].filter(Boolean);
      const classe = x.conferir.length ? "ag-conferir" : x.presente && x.notas.length ? "ag-ambos" : x.presente ? "ag-presenca" : x.notas.length ? "ag-gasto" : "ag-outro";
      m.set(x.dia, { classe, titulo: `${dataBR(x.dia)}: ${partes.join(" · ")}` });
    }
    return m;
  }, [lista]);
  const porVot = useMemo(() => new Map((vots || []).map((v) => [v.id, v])), [vots]);
  const aberto = sel ? dias.find((x) => x.dia === sel) || null : null;
  const abrir = (k: string | null) => {
    const n = new URLSearchParams(params);
    if (k) n.set("dia", k); else n.delete("dia");
    setParams(n, { replace: true });
  };
  useEffect(() => {
    if (sel && painel.current && window.matchMedia("(max-width: 820px)").matches) painel.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [sel]);
  useEffect(() => setMostrar(40), [filtro, busca, ano]);

  if (!d?.agenda) return <div className="empty">Ainda não há o calendário dia a dia de {p.nome} em {ano}. Escolha outro ano no topo da página.</div>;
  if (!ag) return <Loading error={error} />;
  const r = ag.resumo;

  return (
    <div className="agenda">
      <p className="explain">Cada dia do ano, lado a lado: onde {p.nome} registrou presença {p.casa === "camara" ? "(sessões do Plenário, comissões, audiências e outros eventos da Câmara)" : "(votações no Plenário do Senado)"} e as notas da cota com a data daquele dia, com a cidade de quem vendeu. Clique num dia do calendário ou da lista para abrir.</p>
      <section className="grid">
        <div className="card stat"><span className="label">Dias com presença em {ano}</span><span className="value">{r.dias_presenca}</span><span className="hint">{p.casa === "camara" ? "Dias com presença registrada em algum evento da Câmara." : "Dias em que votou em alguma votação nominal do Plenário."}</span></div>
        <div className="card stat"><span className="label">Dias com gastos em {ano}</span><span className="value">{r.dias_gastos}</span><span className="hint">Dias com ao menos uma nota da cota emitida naquela data.</span></div>
        {p.casa === "camara" && <div className="card stat"><span className="label">Pontos para conferir</span><span className={`value${r.conferir ? " ag-alerta" : ""}`}>{r.conferir}</span><span className="hint">Dias com presença em Brasília e refeição paga em outro estado.{r.conferir_cercado ? ` Em ${r.conferir_cercado}, também esteve em Brasília no dia anterior e no seguinte.` : ""}</span></div>}
      </section>

      <div className="ag-barra">
        <div className="ag-filtros" role="tablist" aria-label="Quais dias mostrar">
          {([["todos", "Todos os dias"], ["presenca", "Com presença"], ["gastos", "Com gastos"], ...(p.casa === "camara" ? [["conferir", "Para conferir"]] : [])] as [Filtro, string][]).map(([k, nome]) => (
            <button key={k} role="tab" aria-selected={filtro === k} className={`${filtro === k ? "ativo" : ""}${k === "conferir" && conta.conferir ? " ag-tem" : ""}`} onClick={() => setFiltro(k)}>
              {nome} <span className="num">{conta[k]}</span>
            </button>
          ))}
        </div>
        <input type="search" className="ag-busca" value={busca} onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar: restaurante, cidade, comissão..." aria-label="Buscar nos dias do ano" />
      </div>

      <div className="ag-legenda small" aria-hidden="true">
        <span><i className="ag-presenca" />Presença</span><span><i className="ag-gasto" />Gasto</span>
        <span><i className="ag-ambos" />Presença e gasto</span>{p.casa === "camara" && <span><i className="ag-conferir" />Para conferir</span>}
        {p.casa === "senado" && <span><i className="ag-outro" />Ausente, em missão ou de licença</span>}
      </div>
      <CalendarioAno ano={Number(ano)} marcas={marcas} sel={sel} onSel={abrir} rotulo={`Calendário dia a dia de ${p.nome} em ${ano}`} />

      <div className={`ag-caixa${aberto ? " com-dia" : ""}`}>
        <ul className="ag-lista" aria-label="Dias">
          {lista.length === 0 && <li className="muted small ag-vazio">Nenhum dia com esse filtro.</li>}
          {lista.slice(0, mostrar).map((x, i) => {
            const mes = x.dia.slice(0, 7);
            const novoMes = i === 0 || lista[i - 1].dia.slice(0, 7) !== mes;
            const onde = x.eventos.length
              ? [...new Set(x.eventos.map((e) => e[2] === "PLEN" ? "Plenário" : e[2] || e[1]))].slice(0, 3).join(", ")
              : x.votos.length ? (x.presente ? `Votou no Plenário (${x.votos.length})` : x.votos[0][1]) : "Sem presença registrada";
            const forn = x.notas.slice().sort((a, b) => b.valor - a.valor)[0];
            const lugar = forn && ag.lugares[forn.doc];
            return (
              <li key={x.dia}>
                {novoMes && <div className="ag-mes">{MESES_LONGOS[Number(mes.slice(5)) - 1]} de {mes.slice(0, 4)}</div>}
                <button className={`ag-linha${sel === x.dia ? " sel" : ""}${x.conferir.length ? " conferir" : ""}`} onClick={() => abrir(sel === x.dia ? null : x.dia)} aria-pressed={sel === x.dia}>
                  <span className="ag-data"><span className="num">{Number(x.dia.slice(8))}</span> {MES_CURTO[Number(x.dia.slice(5, 7)) - 1]}<small>{SEMANA_CURTA[semana(x.dia)]}</small></span>
                  <span className="ag-resumo">
                    <strong className={x.presente ? "" : "muted"}>{onde}</strong>
                    <span className="small muted">{x.notas.length ? <>{x.notas.length} nota{x.notas.length > 1 ? "s" : ""}{forn && <> · {forn.fornecedor}{lugar && ` (${lugar[0]}-${lugar[1]})`}</>}</> : "Nenhuma nota nesta data"}</span>
                  </span>
                  <span className="ag-valor">
                    {x.total !== 0 && <span className="num">{reais(x.total)}</span>}
                    {x.conferir.length > 0 && <span className="chip ag-chip">Conferir</span>}
                  </span>
                </button>
              </li>
            );
          })}
          {lista.length > mostrar && <li><button className="link small ag-mais" onClick={() => setMostrar(mostrar + 60)}>Mostrar mais dias ({lista.length - mostrar})</button></li>}
        </ul>

        <div className="ag-painel" ref={painel} aria-live="polite">
          {!aberto ? <p className="muted ag-vazio">Escolha um dia no calendário ou na lista para ver onde {p.nome} estava e o que gastou.</p> : (
            <article>
              <div className="ag-topo">
                <h3>{diaLongo(aberto.dia)}</h3>
                <button className="link small" onClick={() => abrir(null)}>Fechar</button>
              </div>
              {aberto.conferir.length > 0 && (() => {
                const c0 = aberto.conferir[0];
                const evs = aberto.eventos.filter((e) => aberto.conferir.some((c) => c.eventos.includes(e[6])));
                const e0 = evs[0];
                return (
                  <div className="alert ag-ponto" role="note">
                    <div>
                      <strong>Ponto para conferir.</strong> Neste dia, {p.nome} registrou presença em Brasília
                      ({evs.map((e, j) => <span key={e[6]}>{j > 0 && "; "}{e[1]}{e[2] && e[2] !== "PLEN" ? ` da ${e[2]}` : ""} às {e[0]}</span>)})
                      e pediu reembolso de {aberto.conferir.length === 1 ? "uma refeição" : `${aberto.conferir.length} refeições`} em outro estado:
                      <ul className="ag-refeicoes">
                        {aberto.conferir.map((c, i) => <li key={i}><strong>{reais(c.valor, true)}</strong> em <strong>{c.cidade} ({c.uf})</strong>, na empresa {c.fornecedor} · <LinkNota url={c.url} link={c.url ? "nota" : ""} /></li>)}
                      </ul>
                      {c0.cercado && <>Também registrou presença em Brasília no dia anterior e no dia seguinte.</>}
                      <p className="alert-nota">Não é acusação. Pode haver explicação: a data da nota pode ser diferente da data da refeição, o {casa} pode ter viajado no mesmo dia, e a Câmara aceita, em algumas reuniões, presença registrada pelo aplicativo. Cada evento abaixo tem o link da lista de presença oficial{e0 && <> (por exemplo, <a href={API_PRESENCA(e0[6])} target="_blank" rel="noreferrer">lista de presença ↗</a>)</>}.</p>
                    </div>
                  </div>
                );
              })()}

              <h4>{p.casa === "camara" ? "Onde registrou presença" : "No Plenário do Senado"}</h4>
              {aberto.eventos.length === 0 && aberto.votos.length === 0 && <p className="small muted">Nenhuma presença registrada nesta data.</p>}
              {aberto.eventos.length > 0 && <ul className="ag-eventos">
                {aberto.eventos.map((e) => (
                  <li key={e[6]}>
                    <span className="num ag-hora">{e[0]}</span>
                    <div>
                      <strong>{e[1]}{e[2] && <> · {e[2] === "PLEN" ? "Plenário" : e[2]}</>}</strong>
                      {e[3] && <div className="small">{e[3]}</div>}
                      <div className="small muted">{e[4] || "Local não informado"}{" · "}
                        {e[5] ? <span className="ag-tag">Brasília</span> : <span className="ag-tag fora">{/semipresencial|remot|virtual/i.test(e[3]) ? "aceita participação à distância" : "fora das salas da Câmara"}</span>}
                      </div>
                      <div className="small"><a href={LINK_EVENTO(e[6])} target="_blank" rel="noreferrer">Ver evento na Câmara ↗</a> · <a href={API_PRESENCA(e[6])} target="_blank" rel="noreferrer">Lista de presença (API) ↗</a></div>
                    </div>
                  </li>
                ))}
              </ul>}
              {aberto.votos.length > 0 && <>
                <p className="small">{aberto.presente ? `Votou em ${aberto.votos.filter((v) => !AUSENTE.has(v[1])).length} de ${aberto.votos.length} votações nominais neste dia.` : `Não votou nas ${aberto.votos.length} votações nominais deste dia.`}</p>
                <ul className="ag-votos small">
                  {aberto.votos.slice(0, 12).map(([vid, voto]) => {
                    const v = porVot.get(vid);
                    const nome = v?.proposicao ? `${v.proposicao.sigla} ${v.proposicao.numero}/${v.proposicao.ano}` : v?.descricao?.slice(0, 80) || "Votação";
                    return <li key={vid}><VotoChip voto={voto} /> <Link to={`/v/${vid}`}>{nome}</Link></li>;
                  })}
                  {aberto.votos.length > 12 && <li className="muted">E mais {aberto.votos.length - 12}.</li>}
                </ul>
              </>}

              <h4>Notas da cota com esta data</h4>
              {aberto.notas.length === 0 ? <p className="small muted">Nenhuma nota emitida nesta data.</p> : (
                <div className="table-wrap">
                  <table className="ag-notas">
                    <thead><tr><th>Gasto</th><th>Cidade de quem vendeu</th><th className="r">Valor</th><th>Fonte</th></tr></thead>
                    <tbody>
                      {aberto.notas.slice().sort((a, b) => b.valor - a.valor).map((n, i) => {
                        const l = ag.lugares[n.doc];
                        return (
                          <tr key={i}>
                            <td>{/^\d{14}$/.test(n.doc) ? <Link to={`/e/${n.doc}`}>{n.fornecedor}</Link> : n.fornecedor}<div className="small muted">{n.categoria}</div>{n.detalhe && <div className="small">{n.detalhe}</div>}</td>
                            <td className="small">{l ? <>{l[0]} ({l[1]})</> : <span className="muted">Sem dado</span>}</td>
                            <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(n.valor, true)}</td>
                            <td className="small"><LinkNota url={n.url} link={n.link} /></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </article>
          )}
        </div>
      </div>

      <p className="small muted">
        A data de cada gasto é a data de emissão da nota fiscal, como a {p.casa === "camara" ? "Câmara" : "o Senado"} publica. A cidade é a do cadastro da empresa (CNPJ) na Receita Federal; filiais têm CNPJ próprio. Pessoas físicas e empresas ainda não consultadas ficam "sem dado".
        {p.casa === "camara"
          ? <> Um ponto para conferir é um dia com presença registrada numa sala da Câmara, em Brasília, e uma nota de refeição (a cota só paga a alimentação do próprio deputado) de um restaurante de outro estado. Sessões semipresenciais, que aceitam voto à distância, não contam.</>
          : <> No Senado não apontamos pontos para conferir: o voto pode ser dado à distância e os dados abertos não dizem de onde.</>}
        {" "}Fontes: presença em <a href={linkSeguro(ag.fontes.presenca)} target="_blank" rel="noreferrer">{p.casa === "camara" ? "dados abertos da Câmara (eventos e lista de presença)" : "dados abertos do Senado (votações)"} ↗</a>; notas da cota na lista completa de gastos; cidade pela Receita Federal.
      </p>
    </div>
  );
}
