import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Explain, Loading, useData } from "../components/ui";
import { corPartido, linkSeguro, reaisCurto, type AlmgAno, type AlmgIndice } from "../data";
import { norm } from "./Home";
import { AvisosFim } from "../components/Selo";

type Ordem = "verba" | "projetos" | "aprovadas" | "emendas_indicado" | "nome";
const ORDENS: { k: Ordem; nome: string }[] = [
  { k: "verba", nome: "Mais gasto da verba indenizatória" },
  { k: "projetos", nome: "Mais projetos apresentados" },
  { k: "aprovadas", nome: "Mais projetos aprovados" },
  { k: "emendas_indicado", nome: "Mais dinheiro de emendas indicado" },
  { k: "nome", nome: "Nome" },
];

/** Deputados estaduais (Assembleia Legislativa de Minas Gerais) */
export default function Assembleia() {
  const { data, error } = useData<AlmgIndice>("almg/deputados.json");
  const [q, setQ] = useState("");
  const [partido, setPartido] = useState("");
  const [ordem, setOrdem] = useState<Ordem>("verba");
  const [anoSel, setAno] = useState("");
  const anos = data?.anos || [];
  const ano = anos.includes(anoSel) ? anoSel : anos[anos.length - 1] || "";
  const partidos = useMemo(() => [...new Set((data?.deputados || []).map((d) => d.partido))].sort(), [data]);
  const lista = useMemo(() => {
    const v = (x: AlmgAno | undefined, k: Ordem) => (k === "nome" || !x ? 0 : x[k]);
    return (data?.deputados || [])
      .filter((d) => (!partido || d.partido === partido) && (!q || norm(d.nome).includes(norm(q))))
      .sort((a, b) => ordem === "nome" ? a.nome.localeCompare(b.nome) : v(b.por_ano[ano], ordem) - v(a.por_ano[ano], ordem) || a.nome.localeCompare(b.nome));
  }, [data, q, partido, ordem, ano]);
  if (!data) return <Loading error={error} />;
  const med = data.medianas[ano];
  const valor = (x?: AlmgAno) => {
    if (!x) return "sem dado";
    if (ordem === "projetos") return `${x.projetos} projeto${x.projetos === 1 ? "" : "s"}`;
    if (ordem === "aprovadas") return `${x.aprovadas} aprovado${x.aprovadas === 1 ? "" : "s"}`;
    if (ordem === "emendas_indicado") return `${reaisCurto(x.emendas_indicado)} em emendas`;
    return `${reaisCurto(x.verba)} de verba`;
  };
  const lado = (x?: AlmgAno) => {
    if (!x || !med || ordem === "nome") return null;
    const v = x[ordem], m = med[ordem];
    if (v > m) return <span className="atu-acima small"><span aria-hidden="true">▲</span> Acima da maioria</span>;
    if (v < m) return <span className="atu-abaixo small"><span aria-hidden="true">▼</span> Abaixo da maioria</span>;
    return <span className="atu-meio small"><span aria-hidden="true">●</span> Na média</span>;
  };
  return (
    <section>
      <h1>Deputados estaduais</h1>
      <Explain>Os {data.deputados.length} deputados em exercício na Assembleia Legislativa de Minas Gerais (ALMG). Eles fazem as leis do estado, aprovam o orçamento e fiscalizam o governador. Para cada um, mostramos quanto gastou da verba indenizatória (o reembolso de despesas do mandato), quantos projetos apresentou e quanto dinheiro do orçamento indicou em emendas, e para onde. "Acima" ou "abaixo da maioria" compara com o deputado do meio da lista.</Explain>
      <div className="search">
        <input id="filtro-nome" aria-label="Nome" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome do deputado" />
        <select id="filtro-partido" aria-label="Partido" value={partido} onChange={(e) => setPartido(e.target.value)}>
          <option value="">Todos os partidos</option>{partidos.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select id="filtro-ordem" aria-label="Ordenar" value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
          {ORDENS.map((o) => <option key={o.k} value={o.k}>{o.nome}</option>)}
        </select>
        <select id="filtro-ano" aria-label="Ano" value={ano} onChange={(e) => setAno(e.target.value)}>
          {anos.slice().reverse().map((a) => <option key={a}>{a}</option>)}
        </select>
      </div>
      {med && ordem !== "nome" && <p className="muted small">Deputado do meio da lista em {ano}: {valor(med)}.</p>}
      <p className="muted small">{lista.length} deputado{lista.length === 1 ? "" : "s"}</p>
      <div className="list">
        {lista.map((d) => (
          <Link key={d.id} to={`/deputado-estadual/${d.id}`} className="person">
            <span className="avatar sigla-avatar" aria-hidden="true" style={{ background: corPartido(d.partido) }}>{d.partido.slice(0, 4)}</span>
            <div style={{ minWidth: 0 }}>
              <div className="pname">{d.nome}</div>
              <div className="meta">Deputado estadual · {d.partido}</div>
            </div>
            <div className="num r-col">{valor(d.por_ano[ano])}<div>{lado(d.por_ano[ano])}</div></div>
          </Link>
        ))}
      </div>
      <p className="muted small">Fonte: <a href={linkSeguro(data.fontes.dados)} target="_blank" rel="noreferrer">dados abertos da ALMG ↗</a> e <a href={linkSeguro(data.fontes.verba)} target="_blank" rel="noreferrer">prestação de contas da verba indenizatória ↗</a>.</p>
      <AvisosFim>
        {ordem === "verba" && data.verba_completa && data.verba_completa[ano] === false && (
          <p className="alert small" role="note">Os gastos de {ano} ainda estão incompletos: a Assembleia só deixa consultar um deputado e um mês por vez, e estamos baixando aos poucos para não sobrecarregar o site dela. Os meses mais recentes vêm primeiro.</p>
        )}
      </AvisosFim>
    </section>
  );
}
