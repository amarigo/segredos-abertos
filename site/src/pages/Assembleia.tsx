import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Barras, Explain, Loading, OndeVer, useData } from "../components/ui";
import { corPartido, reais, reaisCurto, type AlmgAno, type AlmgIndice } from "../data";
import { norm } from "./Home";
import { FotoPolitico, RotuloRanking } from "../components/Foto";
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
  const [situacao, setSituacao] = useState("");
  const [ordem, setOrdem] = useState<Ordem>("verba");
  const [anoSel, setAno] = useState("");
  const anos = data?.anos || [];
  const ano = anos.includes(anoSel) ? anoSel : anos[anos.length - 1] || "";
  const partidos = useMemo(() => [...new Set((data?.deputados || []).map((d) => d.partido))].sort(), [data]);
  const lista = useMemo(() => {
    const v = (x: AlmgAno | undefined, k: Ordem) => (k === "nome" || !x ? 0 : x[k]);
    return (data?.deputados || [])
      .filter((d) => (!partido || d.partido === partido)
        && (!situacao || (situacao === "exercicio") === (d.em_exercicio !== false))
        && (!q || [d.nome, ...(d.outros_nomes || [])].some((n) => norm(n).includes(norm(q)))))
      .sort((a, b) => ordem === "nome" ? a.nome.localeCompare(b.nome) : v(b.por_ano[ano], ordem) - v(a.por_ano[ano], ordem) || a.nome.localeCompare(b.nome));
  }, [data, q, partido, situacao, ordem, ano]);
  if (!data) return <Loading error={error} />;
  const noCargo = data.n_em_exercicio ?? data.deputados.filter((d) => d.em_exercicio !== false).length;
  const sairam = data.deputados.length - noCargo;
  const med = data.medianas[ano];
  const dinheiro = ordem === "verba" || ordem === "emendas_indicado";
  const porPartido = ordem === "nome" ? [] : Object.values(lista.reduce((acc, d) => {
    const p = (acc[d.partido] ||= { partido: d.partido, n: 0, valor: 0 });
    p.n += 1; p.valor += d.por_ano[ano]?.[ordem] || 0;
    return acc;
  }, {} as Record<string, { partido: string; n: number; valor: number }>)).sort((a, b) => b.valor - a.valor);
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
      <Explain>Os {noCargo} deputados em exercício na Assembleia Legislativa de Minas Gerais (ALMG). Eles fazem as leis do estado, aprovam o orçamento e fiscalizam o governador. Para cada um, mostramos quanto gastou da verba indenizatória (o reembolso de despesas do mandato), quantos projetos apresentou e quanto dinheiro do orçamento indicou em emendas, e para onde. "Acima" ou "abaixo da maioria" compara com o deputado do meio da lista.</Explain>
      {sairam > 0 && <p className="muted small">{sairam === 1
        ? "Também está na lista 1 deputado que teve mandato nesta legislatura e já saiu do cargo (suplente que devolveu a vaga, quem renunciou ou se afastou). Use o filtro de situação para ver só um grupo."
        : `Também estão na lista os ${sairam} deputados que tiveram mandato nesta legislatura e já saíram do cargo (suplentes que devolveram a vaga, quem renunciou ou se afastou). Use o filtro de situação para ver só um grupo.`}</p>}
      <div className="search">
        <input id="filtro-nome" aria-label="Nome" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome do deputado" />
        <select id="filtro-partido" aria-label="Partido" value={partido} onChange={(e) => setPartido(e.target.value)}>
          <option value="">Todos os partidos</option>{partidos.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select id="filtro-situacao" aria-label="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
          <option value="">No cargo hoje e quem já saiu</option><option value="exercicio">Só quem está no cargo hoje</option>
          <option value="fora">Só quem saiu do cargo</option>
        </select>
        <select id="filtro-ordem" aria-label="Ordenar" value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
          {ORDENS.map((o) => <option key={o.k} value={o.k}>{o.nome}</option>)}
        </select>
        <select id="filtro-ano" aria-label="Ano" value={ano} onChange={(e) => setAno(e.target.value)}>
          {anos.slice().reverse().map((a) => <option key={a}>{a}</option>)}
        </select>
      </div>
      {ordem !== "nome" && lista.length > 1 && <Abrir aberto titulo={`Gráfico: ${ORDENS.find((o) => o.k === ordem)!.nome.toLowerCase()} em ${ano}`}>
        <div className="rank-lista"><Barras fmt={dinheiro ? (v) => reais(v) : (v) => v.toLocaleString("pt-BR")}
          itens={lista.slice(0, 15).map((d, i) => ({ nome: d.nome, label: <RotuloRanking posicao={i + 1} to={`/deputado-estadual/${d.id}`} foto={d.foto} nome={d.nome} sub={d.partido} cor={corPartido(d.partido)} />,
            valor: d.por_ano[ano]?.[ordem as Exclude<Ordem, "nome">] || 0, cor: corPartido(d.partido) }))} /></div>
        {porPartido.length > 1 && <Abrir titulo="Somado por partido">
          <Barras fmt={dinheiro ? (v) => reais(v) : (v) => v.toLocaleString("pt-BR")}
            itens={porPartido.map((p) => ({ label: p.partido, nota: `${p.n} deputado${p.n === 1 ? "" : "s"}`, valor: p.valor, cor: corPartido(p.partido) }))} />
        </Abrir>}
      </Abrir>}
      {med && ordem !== "nome" && <p className="muted small">Deputado do meio da lista em {ano} (entre os que estão no cargo hoje): {valor(med)}.</p>}
      <p className="muted small">{lista.length} deputado{lista.length === 1 ? "" : "s"}. A lista traz todos que tiveram mandato nesta legislatura, inclusive quem já saiu do cargo: os gastos, projetos e emendas do período no cargo continuam contando.</p>
      <div className="list">
        {lista.map((d) => (
          <Link key={d.id} to={`/deputado-estadual/${d.id}`} className="person">
            <FotoPolitico url={d.foto} nome={d.nome} decorativa />
            <div style={{ minWidth: 0 }}>
              <div className="pname">{d.nome}</div>
              <div className="meta">Deputado estadual · {d.partido}{d.em_exercicio === false && <> · <span className="fora-cargo">fora do cargo hoje</span></>}</div>
            </div>
            <div className="num r-col">{valor(d.por_ano[ano])}<div>{d.em_exercicio !== false && lado(d.por_ano[ano])}</div></div>
          </Link>
        ))}
      </div>
      <OndeVer links={[
        { nome: "Dados abertos da ALMG", url: data.fontes.dados, explica: "a API oficial de onde vêm deputados, projetos e gastos" },
        { nome: "Verba indenizatória na ALMG", url: data.fontes.verba, explica: "a prestação de contas de cada deputado, mês a mês" },
        { nome: "Emendas parlamentares na ALMG", url: "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/", explica: "cada indicação de dinheiro do orçamento" },
        { nome: "Site da Assembleia (ALMG)", url: "https://www.almg.gov.br/", explica: "página de cada deputado, projetos e leis; o link de cada um está na página dele aqui" },
      ]} />
      <AvisosFim>
        {ordem === "verba" && data.verba_completa && data.verba_completa[ano] === false && (
          <p className="alert small" role="note">Os gastos de {ano} ainda estão incompletos: a Assembleia só deixa consultar um deputado e um mês por vez, e estamos baixando aos poucos para não sobrecarregar o site dela. Os meses mais recentes vêm primeiro.</p>
        )}
      </AvisosFim>
    </section>
  );
}
