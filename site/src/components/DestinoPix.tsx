import { useMemo, useState } from "react";
import { cnpjFmt, dataBR, reais, reaisCurto } from "../data";
import { Explain, Loading, useData } from "./ui";
import "../pages/emendas.css";

/* Emendas Pix no Transferegov (gerados por etl/sa_etl/transferegov.py): em que a prefeitura ou o estado gastou o
   dinheiro e a quem pagou. data/emendas/destino/{ano}.json é a lista; data/emendas/destino/{ano}/{cnpj}.json o detalhe. */
export interface GastoPix { data: string; recebedor: string; cnpj: string; pessoa: boolean; descricao: string; natureza: string; valor: number }
interface MetaPix { nome: string; descricao: string; quantidade: number; unidade: string; valor: number }
interface ExecutorPix { cnpj: string; nome: string; objeto: string; valor: number; executado: number; relatorio: string; metas: MetaPix[] }
export interface PlanoPix {
  id: number; plano: string; emenda: string; parlamentar: string; situacao: string; impedimento: string;
  valor: number; custeio: number; investimento: number; area: string; objeto: string;
  executores: ExecutorPix[]; executado: number; gasto: number; gastos: GastoPix[];
}
interface RecebedorPix { nome: string; cnpj: string; pessoa: boolean; valor: number; n: number }
export interface DestinoBenef {
  cnpj: string; nome: string; uf: string; ano: number; fonte: string; consulta: string;
  valor: number; executado: number; gasto: number; n_gastos: number; planos: PlanoPix[]; recebedores: RecebedorPix[];
}
interface ItemLista { cnpj: string; nome: string; uf: string; valor: number; executado: number; gasto: number; n_gastos: number; n: number }
export interface DestinoIndice {
  ano: number; fonte: string; consulta: string; atualizado: string; completo: boolean;
  n: number; valor: number; gasto: number; n_gastos: number; beneficiarios: ItemLista[]; emendas: Record<string, string>;
}

const PORTAL = "https://portaldatransparencia.gov.br";
const digitos = (s: string) => s.replace(/\D/g, "");
const pct = (a: number, b: number) => (b > 0 ? `${Math.round((a / b) * 100).toLocaleString("pt-BR")}%` : "");
const semAcento = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const nomeBonito = (s: string) => s.toLowerCase().replace(/(^|[\s/(-])(\p{L})/gu, (_, a, b) => a + b.toUpperCase())
  .replace(/\b(De|Do|Da|Dos|Das|E)\b/g, (m) => m.toLowerCase());

export function useDestinoIndice(ano: number | string | null) {
  return useData<DestinoIndice>(ano ? `emendas/destino/${ano}.json` : null);
}

/** Em que foi gasto o dinheiro de uma emenda Pix: o detalhe só é baixado quando a pessoa abre. */
export function GastoDaEmenda({ ano, cnpj, emenda }: { ano: number | string; cnpj: string; emenda: string }) {
  const { data, error } = useData<DestinoBenef>(`emendas/destino/${ano}/${cnpj}.json`);
  if (!data) return <Loading error={error} />;
  const planos = data.planos.filter((p) => digitos(p.emenda) === digitos(emenda));
  if (!planos.length) return <p className="small muted">O plano de ação desta emenda não foi encontrado no Transferegov.</p>;
  return <>{planos.map((p) => <Plano key={p.id} p={p} consulta={data.consulta} />)}</>;
}

/** Um plano de ação: o que a prefeitura disse que ia fazer, quem executa, as metas e os pagamentos já informados. */
export function Plano({ p, consulta, comParlamentar = false }: { p: PlanoPix; consulta: string; comParlamentar?: boolean }) {
  const metas = p.executores.flatMap((e) => e.metas);
  const objetos = Array.from(new Set(p.executores.map((e) => e.objeto).filter((o) => o && o !== p.objeto)));
  return (
    <div className="pix-plano">
      <div className="pix-plano-topo">
        <span><strong>Emenda nº {p.emenda}</strong>{comParlamentar && p.parlamentar && <span className="muted"> · {nomeBonito(p.parlamentar)}</span>}
          <span className="small muted"> · plano de ação {p.plano}{p.situacao && ` · ${p.situacao}`}</span></span>
        <strong className="num">{reais(p.valor)}</strong>
      </div>
      {p.objeto && <div className="small"><b>O que a prefeitura disse que ia fazer:</b> {p.objeto}</div>}
      {objetos.map((o) => <div key={o} className="small"><b>Objeto do executor:</b> {o}</div>)}
      {p.area && <div className="small muted">Área: {p.area}</div>}
      {p.impedimento && <div className="small aviso-texto">Impedimento: {p.impedimento}</div>}
      <Execucao valor={p.valor} executado={p.executado} gasto={p.gasto} />
      {metas.length > 0 && <>
        <h5>Metas</h5>
        <ul className="pix-metas">{metas.map((m, i) => (
          <li key={i}><span>{m.nome}{m.descricao && m.descricao !== m.nome && <span className="muted"> · {m.descricao}</span>}
            {m.quantidade > 0 && <span className="small muted num"> · {m.quantidade.toLocaleString("pt-BR")} {m.unidade}</span>}</span>
            <span className="num">{reaisCurto(m.valor)}</span></li>))}</ul>
      </>}
      <h5>Pagamentos que a prefeitura informou ({p.gastos.length.toLocaleString("pt-BR")})</h5>
      <ListaGastos gastos={p.gastos} />
      <div className="small emd-doc-links">
        <a href={consulta} target="_blank" rel="noreferrer">Plano de ação no Transferegov ↗</a>
        <a href={`${PORTAL}/emendas/detalhe?codigoEmenda=${encodeURIComponent(p.emenda)}&ano=${p.emenda.slice(0, 4)}`} target="_blank" rel="noreferrer">Emenda no Portal da Transparência ↗</a>
      </div>
    </div>
  );
}

function Execucao({ valor, executado, gasto }: { valor: number; executado: number; gasto: number }) {
  const feito = Math.max(executado, gasto);
  return (
    <div className="pix-exec">
      <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${Math.min(100, valor ? (feito / valor) * 100 : 0)}%` }} /></span>
      <span className="small">
        {gasto > 0 ? <>Pagamentos informados: <b className="num">{reais(gasto)}</b> ({pct(gasto, valor)} do valor)</> : "Nenhum pagamento informado ainda"}
        {executado > 0 && Math.abs(executado - gasto) > 0.01 && <span className="muted"> · o relatório de gestão diz {reais(executado)} executados</span>}
      </span>
    </div>
  );
}

/** Os pagamentos feitos com o dinheiro: quem recebeu, para quê, quanto e quando. */
export function ListaGastos({ gastos, inicial = 8 }: { gastos: GastoPix[]; inicial?: number }) {
  const [n, setN] = useState(inicial);
  if (!gastos.length) return <p className="small muted">A prefeitura ainda não informou no relatório de gestão nenhum pagamento feito com este dinheiro.</p>;
  return (
    <>
      <ul className="emd-docs">
        {gastos.slice(0, n).map((g, i) => (
          <li key={i}>
            <div className="emd-doc-topo"><span className="small muted num">{dataBR(g.data)}</span><strong className="num">{reais(g.valor, true)}</strong></div>
            <div>Para {g.cnpj ? <a href={`${PORTAL}/pessoa-juridica/${g.cnpj}`} target="_blank" rel="noreferrer">{g.recebedor} ↗</a> : <strong>{g.recebedor}</strong>}
              {g.cnpj ? <span className="small muted mono"> {cnpjFmt(g.cnpj)}</span> : g.pessoa && <span className="small muted"> (pessoa física)</span>}</div>
            {g.descricao && <div className="small emd-doc-desc"><b>Para quê:</b> {g.descricao}</div>}
            {g.natureza && <div className="small muted">{g.natureza}</div>}
          </li>
        ))}
      </ul>
      {gastos.length > n && <button className="link" onClick={() => setN(n + 25)}>Mostrar mais pagamentos ({gastos.length - n} restantes)</button>}
    </>
  );
}

/** A prefeitura ou o estado aberto: todas as emendas Pix do ano e a quem pagou. */
function DetalheBenef({ ano, cnpj }: { ano: number | string; cnpj: string }) {
  const { data, error } = useData<DestinoBenef>(`emendas/destino/${ano}/${cnpj}.json`);
  const [nRec, setNRec] = useState(10);
  if (!data) return <Loading error={error} />;
  return (
    <div className="pix-det">
      {data.recebedores.length > 0 && <>
        <h4>A quem {nomeBonito(data.nome)} pagou com o dinheiro das emendas Pix</h4>
        <ul className="pix-metas">{data.recebedores.slice(0, nRec).map((r, i) => (
          <li key={i}><span>{r.cnpj ? <a href={`${PORTAL}/pessoa-juridica/${r.cnpj}`} target="_blank" rel="noreferrer">{r.nome} ↗</a> : r.nome}
            <span className="small muted">{r.cnpj ? ` ${cnpjFmt(r.cnpj)}` : r.pessoa ? " (pessoa física)" : ""} · {r.n} pagamento{r.n > 1 ? "s" : ""}</span></span>
            <span className="num">{reais(r.valor)}</span></li>))}</ul>
        {data.recebedores.length > nRec && <button className="link" onClick={() => setNRec(nRec + 30)}>Mostrar mais ({data.recebedores.length - nRec} restantes)</button>}
      </>}
      <h4>As emendas, uma a uma ({data.planos.length})</h4>
      {data.planos.map((p) => <Plano key={p.id} p={p} consulta={data.consulta} comParlamentar />)}
    </div>
  );
}

/** Uma prefeitura ou estado na lista; o detalhe só é baixado quando a pessoa abre. */
function ItemBenef({ b, ano, max }: { b: ItemLista; ano: string; max: number }) {
  const [aberto, setAberto] = useState(false);
  return (
    <details className="emd-autor pix-benef" onToggle={(e) => setAberto((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>
        <span className="emd-quem">
          <strong>{nomeBonito(b.nome)}</strong>
          <span className="small muted">{b.uf} · {b.n} emenda{b.n > 1 ? "s" : ""} · {b.n_gastos.toLocaleString("pt-BR")} pagamento{b.n_gastos === 1 ? "" : "s"} informado{b.n_gastos === 1 ? "" : "s"} ({pct(b.gasto, b.valor) || "0%"})</span>
        </span>
        <span className="num emd-valor">{reaisCurto(b.valor)}</span>
        <span className="track pix-track" aria-hidden="true" style={{ width: `${Math.max(4, (b.valor / max) * 100)}%` }}>
          <span className="fill" style={{ width: `${b.valor ? Math.min(100, (b.gasto / b.valor) * 100) : 0}%` }} />
        </span>
      </summary>
      {aberto && <DetalheBenef ano={ano} cnpj={b.cnpj} />}
    </details>
  );
}

/** Botão que abre, embaixo de uma emenda Pix, em que o dinheiro foi gasto. */
export function AbrirGastoDaEmenda({ ano, cnpj, emenda }: { ano: number | string; cnpj: string; emenda: string }) {
  const [aberto, setAberto] = useState(false);
  if (!aberto) return <button className="link" onClick={() => setAberto(true)}>Em que foi gasto e a quem a prefeitura pagou</button>;
  return <GastoDaEmenda ano={ano} cnpj={cnpj} emenda={emenda} />;
}

/** Seção da página de emendas: cada prefeitura e estado que recebeu emenda Pix, quanto já informou ter gasto e com quem. */
export function DestinoPix({ ano }: { ano: string }) {
  const { data } = useDestinoIndice(ano);
  const [q, setQ] = useState("");
  const [uf, setUf] = useState("");
  const [ordem, setOrdem] = useState<"valor" | "gasto" | "falta">("valor");
  const [n, setN] = useState(15);
  const ufs = useMemo(() => Array.from(new Set((data?.beneficiarios || []).map((b) => b.uf).filter(Boolean))).sort(), [data]);
  const lista = useMemo(() => {
    if (!data) return [];
    const busca = semAcento(q.trim());
    const l = data.beneficiarios.filter((b) => (!uf || b.uf === uf)
      && (!busca || semAcento(`${b.nome} ${b.uf}`).includes(busca) || (digitos(q) && b.cnpj.includes(digitos(q)))));
    const falta = (b: ItemLista) => b.valor - b.gasto;
    return l.sort((a, b) => (ordem === "gasto" ? b.gasto - a.gasto : ordem === "falta" ? falta(b) - falta(a) : b.valor - a.valor));
  }, [data, q, uf, ordem]);
  if (!data || !data.beneficiarios.length) return null;
  const max = Math.max(1, ...lista.slice(0, 1).map((b) => b.valor), ...lista.slice(0, n).map((b) => b.valor));
  return (
    <section id="destino-pix">
      <h2>Emendas Pix: em que cada prefeitura e estado gastou, e a quem pagou</h2>
      <Explain>
        Na emenda Pix o dinheiro cai direto no caixa da prefeitura ou do estado. Quem recebe é obrigado a registrar no Transferegov o
        plano de ação (o que vai fazer), as metas e, no relatório de gestão, <strong>cada pagamento feito com o dinheiro</strong>: para
        quem, para quê, quanto e quando. É o que o governo federal publica mais perto das notas fiscais. Das {data.n.toLocaleString("pt-BR")} emendas
        Pix de {ano} ({reaisCurto(data.valor)}), as prefeituras e estados já informaram {data.n_gastos.toLocaleString("pt-BR")} pagamentos,
        somando {reaisCurto(data.gasto)} ({pct(data.gasto, data.valor)}).
      </Explain>
      <div className="row" style={{ gap: 8 }}>
        <div className="search" style={{ flex: "1 1 220px" }}>
          <input aria-label="Procurar prefeitura ou estado" value={q} onChange={(e) => { setQ(e.target.value); setN(15); }} placeholder="Cidade, estado ou CNPJ" />
        </div>
        <select aria-label="Estado" value={uf} onChange={(e) => { setUf(e.target.value); setN(15); }}>
          <option value="">Todos os estados</option>
          {ufs.map((u) => <option key={u} value={u}>{u}</option>)}
        </select>
        <div className="toggle" role="group" aria-label="Ordenar">
          <button aria-pressed={ordem === "valor"} onClick={() => setOrdem("valor")}>Mais recebeu</button>
          <button aria-pressed={ordem === "gasto"} onClick={() => setOrdem("gasto")}>Mais gastou</button>
          <button aria-pressed={ordem === "falta"} onClick={() => setOrdem("falta")}>Mais falta informar</button>
        </div>
      </div>
      <div className="emd-autores">
        {lista.slice(0, n).map((b) => <ItemBenef key={b.cnpj} b={b} ano={ano} max={max} />)}
        {!lista.length && <div className="empty">Nada encontrado.</div>}
      </div>
      {lista.length > n && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais ({lista.length - n} restantes)</button>}
      <p className="small muted">
        Barra cinza: o valor das emendas Pix de {ano}; parte azul: o que a prefeitura ou o estado já informou ter pago com ele.
        Fonte: <a href={data.fonte} target="_blank" rel="noreferrer">API de dados abertos do Transferegov ↗</a>, lida em {dataBR(data.atualizado)}.
        {!data.completo && " A leitura dos relatórios de gestão ainda não terminou; alguns pagamentos podem faltar e entram nas próximas atualizações."}
        {" "}De pessoas físicas mostramos só o nome, como o Transferegov, sem o CPF.
      </p>
    </section>
  );
}
