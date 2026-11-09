import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { cnpjFmt, corPartido, dataBR, linkSeguro, reais, reaisCurto, type HistoriaEmenda, type HistoriasCidade } from "../data";
import { Plano } from "./DestinoPix";
import { Explain, Loading, useData } from "./ui";
import "../pages/emendas.css";

/* A história inteira de cada emenda federal que chegou a uma cidade (gerada por mg/etl/mg_etl/emendas_federais.py,
   historias): quem indicou e para quê, quanto foi reservado e pago, quando o dinheiro chegou e, nas emendas Pix, o
   plano de ação e cada pagamento que a prefeitura informou no Transferegov. O arquivo da cidade só é baixado quando
   a pessoa abre a lista (ou chega por um link de uma emenda). */

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const mesBR = (m: string) => `${MESES[Number(m.slice(5, 7)) - 1] || m.slice(5, 7)}/${m.slice(0, 4)}`;
const semAcento = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const pct = (a: number, b: number) => (b > 0 ? `${Math.round((a / b) * 100)}%` : "");

const TIPO: Record<string, string> = {
  pix: "Emenda Pix", individual: "Individual", bancada: "De bancada", comissao: "De comissão", relator: "Do relator", outro: "Emenda",
};
const TIPO_EXPLICA: Record<string, string> = {
  pix: "Na emenda Pix (transferência especial) o dinheiro cai direto no caixa da prefeitura, sem dizer no Orçamento em que vai ser usado. A prefeitura é obrigada a registrar no Transferegov o plano de ação e cada pagamento que faz com o dinheiro.",
  individual: "Emenda individual com finalidade definida: o Orçamento já diz em que o dinheiro vai ser usado (a área e a ação abaixo).",
  bancada: "Decidida em conjunto pelos deputados e senadores de um estado.",
  comissao: "Decidida por uma comissão da Câmara ou do Senado.",
  relator: "Indicada pelo relator do Orçamento.",
  outro: "",
};

type Situacao = "todas" | "esperando" | "chegou" | "gasto";

/** Em que ponto está a emenda: as quatro etapas da história. */
function etapas(e: HistoriaEmenda) {
  const chegou = e.recebido_aqui > 0;
  const plano = !!e.plano;
  const gasto = (e.plano?.gastos.length || 0) > 0;
  return { indicada: true, chegou, plano, gasto };
}

function situacao(e: HistoriaEmenda): Exclude<Situacao, "todas"> {
  const s = etapas(e);
  return s.gasto ? "gasto" : s.chegou ? "chegou" : "esperando";
}

/** O texto onde a busca procura: quem indicou, para quê, o plano, as metas e cada gasto da prefeitura. */
function textoBusca(e: HistoriaEmenda): string {
  const p = e.plano;
  return semAcento([
    e.codigo, e.autor, e.partido, e.funcao, e.subfuncao, ...e.acoes, e.local, ...e.recebido.map((r) => r.nome),
    p?.objeto, p?.area, ...(p?.executores || []).flatMap((x) => [x.nome, x.objeto, ...x.metas.flatMap((m) => [m.nome, m.descricao])]),
    ...(p?.gastos || []).flatMap((g) => [g.descricao, g.recebedor]),
  ].filter(Boolean).join(" "));
}

/** Para quê, numa linha: o plano da prefeitura (Pix) ou a ação do Orçamento. */
function paraQue(e: HistoriaEmenda): string {
  if (e.plano?.objeto) return e.plano.objeto;
  if (e.acoes[0]) return e.acoes[0];
  if (e.tipo === "pix") return "Emenda Pix: o plano de ação ainda não aparece no Transferegov";
  return [e.funcao, e.subfuncao].filter(Boolean).join(" › ") || "Finalidade não informada";
}

export function EmendasUmaAUma({ id, nome, n }: { id: string; nome: string; n: number }) {
  const [params] = useSearchParams();
  const alvo = params.get("emenda") || "";
  const [aberto, setAberto] = useState(!!alvo);
  if (!n) return <p className="small muted">Nenhuma emenda federal dos anos mostrados no site chegou a {nome}.</p>;
  if (!aberto) {
    return (
      <button className="btn-abrir-historias" onClick={() => setAberto(true)}>
        Abrir as {n.toLocaleString("pt-BR")} emendas, uma a uma: se o dinheiro chegou, qual o plano e em que foi gasto
      </button>
    );
  }
  return <Lista id={id} nome={nome} alvo={alvo} />;
}

function Lista({ id, nome, alvo }: { id: string; nome: string; alvo: string }) {
  const { data, error } = useData<HistoriasCidade>(`cidades/emendas/${id}.json`);
  const anos = useMemo(() => Array.from(new Set((data?.emendas || []).map((e) => e.ano))).sort((a, b) => b - a), [data]);
  const anoAlvo = data?.emendas.find((e) => e.codigo === alvo)?.ano;
  // começa no ano mais recente (o ano atual, quando já há emendas dele); quem chega por link vê o ano da emenda
  const [ano, setAno] = useState<number | "">("");
  const anoUsado = ano === "" ? (anoAlvo ?? anos[0] ?? "") : ano;
  const [sit, setSit] = useState<Situacao>("todas");
  const [q, setQ] = useState("");
  const [n, setN] = useState(15);
  const lista = useMemo(() => {
    const busca = semAcento(q.trim());
    return (data?.emendas || []).filter((e) => (anoUsado === 0 || e.ano === anoUsado)
      && (sit === "todas" || situacao(e) === sit) && (!busca || textoBusca(e).includes(busca)));
  }, [data, anoUsado, sit, q]);
  useEffect(() => { // quem chega pelo link de uma emenda vê a emenda, sem filtros de antes
    if (alvo) { setAno(""); setSit("todas"); setQ(""); }
  }, [alvo]);
  useEffect(() => {
    if (!alvo || !data) return;
    document.getElementById(`emenda-${alvo}`)?.scrollIntoView({ block: "start" });
  }, [alvo, data]);
  if (!data) return <Loading error={error} />;
  const doAno = data.emendas.filter((e) => anoUsado === 0 || e.ano === anoUsado);
  const conta = (s: Situacao) => doAno.filter((e) => situacao(e) === s).length;
  const visiveis = lista.slice(0, Math.max(n, lista.findIndex((e) => e.codigo === alvo) + 1));
  const tg = data.transferegov;
  return (
    <div className="hist">
      <Explain>
        Toque numa emenda para ver a história dela do começo ao fim: quem indicou e para quê, quanto o governo federal reservou e pagou,
        quando o dinheiro chegou a {nome} e, nas emendas Pix, o plano que a prefeitura registrou e cada pagamento que ela diz ter feito
        com o dinheiro (para quem, para quê e quanto). Use a busca para achar um gasto, como “festa”, “show” ou “asfalto”.
      </Explain>
      <div className="row" style={{ gap: 8 }}>
        <select aria-label="Ano da emenda" value={anoUsado} onChange={(e) => { setAno(Number(e.target.value)); setN(15); }}>
          {anos.map((a) => <option key={a} value={a}>Emendas de {a}</option>)}
          <option value={0}>Todos os anos</option>
        </select>
        <div className="search" style={{ flex: "1 1 220px" }}>
          <input aria-label="Procurar nas emendas" value={q} onChange={(e) => { setQ(e.target.value); setN(15); }}
            placeholder="Procure: festa, carnaval, asfalto, deputado…" />
        </div>
      </div>
      <div className="toggle hist-filtro" role="group" aria-label="Situação da emenda">
        <button aria-pressed={sit === "todas"} onClick={() => setSit("todas")}>Todas ({doAno.length})</button>
        <button aria-pressed={sit === "esperando"} onClick={() => setSit("esperando")}>Dinheiro ainda não chegou ({conta("esperando")})</button>
        <button aria-pressed={sit === "chegou"} onClick={() => setSit("chegou")}>Chegou ({conta("chegou")})</button>
        <button aria-pressed={sit === "gasto"} onClick={() => setSit("gasto")}>Com gastos informados ({conta("gasto")})</button>
      </div>
      <div className="emd-autores">
        {visiveis.map((e) => <Ficha key={e.codigo} e={e} id={id} nome={nome} consulta={tg?.consulta || ""} transferegov={!!tg} aberta={e.codigo === alvo} />)}
        {!lista.length && <div className="empty">Nenhuma emenda encontrada com estes filtros.</div>}
      </div>
      {lista.length > visiveis.length && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais ({lista.length - visiveis.length} restantes)</button>}
      <p className="muted small fonte-linha">
        Fontes: <a href={linkSeguro(data.fonte)} target="_blank" rel="noreferrer">Portal da Transparência (CGU), arquivo de emendas parlamentares ↗</a> (quem
        indicou, valores e quem recebeu, mês a mês)
        {tg ? <>; <a href={linkSeguro(tg.fonte)} target="_blank" rel="noreferrer">API do Transferegov, transferências especiais ↗</a> (plano
          de ação e pagamentos da prefeitura), lida em {dataBR(tg.atualizado)}.{!tg.completo && " A leitura dos relatórios de gestão ainda não terminou; alguns pagamentos podem faltar."}</>
          : <>. O Transferegov ainda não foi lido nesta atualização: o plano de ação e os gastos das emendas Pix não aparecem até a próxima.</>}
        {" "}De pessoas físicas mostramos só o nome, como as fontes oficiais, sem CPF.
      </p>
    </div>
  );
}

function Etapas({ e }: { e: HistoriaEmenda }) {
  const s = etapas(e);
  const itens: [boolean, string][] = [
    [s.indicada, `Indicada em ${e.ano}`],
    [s.chegou, s.chegou ? "Dinheiro chegou" : "Dinheiro não chegou"],
    ...(e.tipo === "pix" ? [[s.plano, s.plano ? "Plano de ação" : "Sem plano de ação"], [s.gasto, s.gasto ? "Gastos informados" : "Sem gastos informados"]] as [boolean, string][] : []),
  ];
  return (
    <ol className="hist-etapas" aria-label="Etapas da emenda">
      {itens.map(([feito, t]) => <li key={t} className={feito ? "feito" : ""}><span aria-hidden="true">{feito ? "✓" : "○"}</span> {t}</li>)}
    </ol>
  );
}

function Ficha({ e, id, nome, consulta, transferegov, aberta }: { e: HistoriaEmenda; id: string; nome: string; consulta: string; transferegov: boolean; aberta: boolean }) {
  const valor = Math.max(e.pago, e.recebido_aqui) || e.empenhado;
  return (
    <details className="emd-autor hist-ficha" id={`emenda-${e.codigo}`} open={aberta || undefined}>
      <summary>
        <span className="emd-pos small muted num">{e.ano}</span>
        <span className="emd-quem">
          <strong>{paraQue(e)}</strong>
          <span className="small muted"><span className="chip">{TIPO[e.tipo] || "Emenda"}</span> {e.autor}
            {e.partido && <> · <i className="partido-cor" style={{ background: corPartido(e.partido) }} />{e.partido}</>} · nº {e.codigo}</span>
          <Etapas e={e} />
        </span>
        <span className="num emd-valor">{reaisCurto(valor)}</span>
      </summary>
      <div className="hist-corpo">
        <section className="hist-passo">
          <h4>1. Quem indicou e para quê</h4>
          <p className="small">Em {e.ano}, {e.politico ? <Link to={`/p/${e.politico}`}>{e.autor}</Link> : e.autor}{e.partido && ` (${e.partido})`} indicou esta
            emenda{e.local && <> para <b>{e.local}</b></>}. {TIPO_EXPLICA[e.tipo]}</p>
          {e.tipo !== "pix" && (e.funcao || e.acoes.length > 0) && <ul className="small hist-lista">
            {(e.funcao || e.subfuncao) && <li>Área: {[e.funcao, e.subfuncao].filter(Boolean).join(" › ")}</li>}
            {e.acoes.map((a) => <li key={a}>Ação do Orçamento: {a}</li>)}
          </ul>}
        </section>
        <section className="hist-passo">
          <h4>2. Quanto foi reservado e pago</h4>
          <div className="pix-exec">
            <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${e.empenhado ? Math.min(100, (e.pago / e.empenhado) * 100) : 0}%` }} /></span>
            <span className="small">Reservado (empenhado): <b className="num">{reais(e.empenhado)}</b> · pago: <b className="num">{reais(e.pago)}</b>
              {e.empenhado > 0 && ` (${pct(e.pago, e.empenhado)})`}</span>
          </div>
          {!e.na_cidade && <p className="small muted">A emenda é para {e.local || "outro lugar"}; os valores acima são da emenda inteira. Abaixo, só o que chegou a quem tem endereço em {nome}.</p>}
        </section>
        <section className="hist-passo">
          <h4>3. Quando o dinheiro chegou a {nome}</h4>
          {e.recebido.length ? <ul className="emd-docs">{e.recebido.map((r, i) => (
            <li key={i}><div className="emd-doc-topo"><span className="small muted">{mesBR(r.mes)}</span><strong className="num">{reais(r.valor, true)}</strong></div>
              <div>{r.cnpj ? <a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${r.cnpj}`} target="_blank" rel="noreferrer">{r.nome} ↗</a> : r.nome}
                {r.cnpj && <span className="small muted mono"> {cnpjFmt(r.cnpj)}</span>} recebeu</div></li>))}</ul>
            : <p className="small">Nenhum pagamento desta emenda chegou ainda a quem tem endereço em {nome}{e.pago > 0 && !e.na_cidade ? "" : ". Pode estar só reservado (empenhado) ou ainda na fila de pagamento do governo federal"}.</p>}
        </section>
        <section className="hist-passo">
          <h4>4. {e.tipo === "pix" ? "O plano da prefeitura e em que o dinheiro foi gasto" : "Em que o dinheiro foi gasto"}</h4>
          {e.plano ? <Plano p={e.plano} consulta={consulta} />
            : e.tipo === "pix" ? <p className="small">{transferegov
              ? "A prefeitura ainda não registrou um plano de ação para esta emenda no Transferegov, ou ele ainda não aparece na consulta pública."
              : "O Transferegov ainda não foi lido nesta atualização; o plano de ação e os gastos desta emenda aparecem na próxima."}</p>
              : <p className="small">Nesta emenda o Orçamento já diz a finalidade (passo 1). O que foi comprado ou contratado com o dinheiro fica no convênio ou
                no repasse fundo a fundo, que este site ainda não lê. Veja os documentos de cada pagamento na página oficial da emenda, abaixo.</p>}
        </section>
        <p className="small emd-doc-links">
          <a href={linkSeguro(e.url)} target="_blank" rel="noreferrer">Emenda nº {e.codigo} no Portal da Transparência ↗</a>
          <Link to={`/cidade/${id}?aba=dinheiro&emenda=${e.codigo}`}>Link desta emenda</Link>
        </p>
      </div>
    </details>
  );
}
