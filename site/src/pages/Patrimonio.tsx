import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, OndeVer, useData } from "../components/ui";
import { ColunasAnos } from "../components/graficos";
import { dataBR, reais, reaisCurto, type Patrimonio, type PatrimonioPessoa, type PatrimonioResumo } from "../data";

/* Patrimônio declarado ao TSE por cada deputado federal e senador do site (patrimonio.json e pat/{id}.json).
   Os números vêm prontos do coletor (etl/sa_etl/patrimonio.py); aqui só escolhemos o que mostrar. */

type Casa = "camara" | "senado" | "as_duas";
const NOME_CASA: Record<Casa, string> = { camara: "Câmara", senado: "Senado", as_duas: "Câmara e Senado" };
const POR_PAGINA = 30;

function Aviso() {
  return (
    <Explain>
      Todo candidato entrega ao TSE a lista dos seus bens quando registra a candidatura. O valor é o que a pessoa declarou,
      em geral o do imposto de renda (quase sempre o preço de compra), e não o valor de mercado. A lista de cada bem, com a
      descrição, fica no site do TSE; aqui mostramos o total e a soma por tipo.
    </Explain>
  );
}

export default function PatrimonioPage() {
  const { data, error } = useData<Patrimonio>("patrimonio.json");
  const [casa, setCasa] = useState<Casa>("as_duas");
  const [n, setN] = useState(POR_PAGINA);
  const lista = useMemo(() => (data?.politicos || []).filter((p) => casa === "as_duas" || p.casa === casa), [data, casa]);
  const aumentos = useMemo(() => lista.filter((p) => p.anterior)
    .map((p) => ({ p, dif: p.ultimo.total - p.anterior!.total }))
    .sort((a, b) => b.dif - a.dif).slice(0, 20), [lista]);
  if (!data) return <Loading error={error} />;
  const ligados = data.politicos.length;

  return (
    <section className="patrimonio">
      <p className="small"><Link to="/politicos">‹ Políticos</Link></p>
      <span className="eyebrow">Eleições</span>
      <h1>Patrimônio declarado ao TSE</h1>
      <Aviso />
      <p className="small muted">
        Eleições lidas: {data.anos.join(", ")}. Achamos o registro de candidatura de {ligados.toLocaleString("pt-BR")} dos{" "}
        {data.total_politicos.toLocaleString("pt-BR")} parlamentares do site{data.sem_registro ? ` (${data.sem_registro} sem registro achado)` : ""}, pelo nome civil e pela data de nascimento.
      </p>
      <div className="row graf-controles">
        <div className="toggle" role="group" aria-label="Casa">
          {(["as_duas", "camara", "senado"] as Casa[]).map((c) => (
            <button key={c} aria-pressed={casa === c} onClick={() => { setCasa(c); setN(POR_PAGINA); }}>{NOME_CASA[c]}</button>
          ))}
        </div>
      </div>

      <h2>Maiores patrimônios declarados: {NOME_CASA[casa]}</h2>
      <p className="small muted">Na eleição mais recente em que a pessoa se candidatou (o cargo disputado está ao lado).</p>
      <div className="table-wrap"><table>
        <thead><tr><th>Parlamentar</th><th>Eleição</th><th className="num">Patrimônio declarado</th></tr></thead>
        <tbody>{lista.slice(0, n).map((p) => <Linha key={p.id} p={p} />)}</tbody>
      </table></div>
      {lista.length > n && <button className="btn" onClick={() => setN(n + POR_PAGINA * 3)}>Ver mais ({lista.length - n} restantes)</button>}

      <h2>Quem mais aumentou o patrimônio declarado</h2>
      <p className="small muted">Diferença entre as duas últimas eleições em que a pessoa se candidatou, em valores da época (sem correção pela inflação).</p>
      <div className="table-wrap"><table>
        <thead><tr><th>Parlamentar</th><th>Antes</th><th>Depois</th><th className="num">Diferença</th></tr></thead>
        <tbody>{aumentos.map(({ p, dif }) => (
          <tr key={p.id}>
            <td><Link to={`/p/${p.id}`}>{p.nome}</Link> <span className="muted small">{[p.partido, p.uf].filter(Boolean).join("-")}</span>
              {p.salto && <div className="small aviso-salto">Subiu mais de 20 vezes: confira no TSE</div>}</td>
            <td>{reaisCurto(p.anterior!.total)} <span className="muted small">({p.anterior!.ano})</span></td>
            <td>{reaisCurto(p.ultimo.total)} <span className="muted small">({p.ultimo.ano})</span></td>
            <td className="num">{dif >= 0 ? "+" : ""}{reais(dif)}</td>
          </tr>
        ))}</tbody>
      </table></div>

      <p className="small muted">Fonte: <a href={data.fontes.tse} target="_blank" rel="noreferrer">dados abertos do TSE, candidatos e bens de cada eleição ↗</a>; nome civil e nascimento pelo <a href={data.fontes.camara} target="_blank" rel="noreferrer">arquivo de deputados da Câmara ↗</a> e pela <a href={data.fontes.senado} target="_blank" rel="noreferrer">API do Senado ↗</a>. Atualizado em {dataBR(data.atualizado)}.</p>
      <OndeVer links={[
        { nome: "TSE: DivulgaCandContas", url: "https://divulgacandcontas.tse.jus.br/", explica: "cada candidato, com a lista de bens e a descrição de cada um" },
        { nome: "TSE: dados abertos", url: data.fontes.tse, explica: "arquivos de candidatos e bens de cada eleição" },
      ]} />
      <p className="small"><Link to="/eleitos">Governadores, assembleias, prefeitos e vereadores eleitos, com o patrimônio declarado ›</Link></p>
    </section>
  );
}

function Linha({ p }: { p: PatrimonioResumo }) {
  return (
    <tr>
      <td><Link to={`/p/${p.id}`}>{p.nome}</Link> <span className="muted small">{[p.partido, p.uf].filter(Boolean).join("-")}</span>
        {p.salto && <div className="small aviso-salto">Subiu mais de 20 vezes desde a eleição anterior: confira no TSE</div>}</td>
      <td>{p.ultimo.ano} <span className="muted small">{p.ultimo.cargo}</span></td>
      <td className="num">{reais(p.ultimo.total)}</td>
    </tr>
  );
}

/* No perfil: o patrimônio declarado em cada eleição desde 2014 (quando houver pat/{id}.json). */
export function PatrimonioPolitico({ id }: { id: string }) {
  const { data } = useData<PatrimonioPessoa>(`pat/${id}.json`);
  if (!data || !data.declaracoes.length) return null;
  const prin = data.declaracoes.filter((d) => d.principal);
  const ult = prin[prin.length - 1];
  const serie: [string, number][] = prin.map((d) => [String(d.ano), d.total]);
  const outras = data.declaracoes.filter((d) => !d.principal);
  return (
    <section className="patrimonio-politico">
      <h2>Patrimônio declarado ao TSE</h2>
      <p className="small muted">Na eleição de {ult.ano} ({ult.cargo}{ult.local ? `, ${ult.local}` : ""}): <strong className="num">{reais(ult.total)}</strong>{ult.sem_bens ? " (não declarou bens)" : ""}.</p>
      {ult.salto && <p className="small aviso-salto" role="note">O total de {ult.ano} é mais de 20 vezes o da eleição anterior. É o número publicado pelo TSE; pode ser erro de digitação na declaração. <a href={ult.fonte} target="_blank" rel="noreferrer">Confira no TSE ↗</a></p>}
      {serie.length > 1 && <ColunasAnos serie={serie} titulo={`Patrimônio declarado por eleição de ${data.nome}`} formato={reaisCurto} cor="var(--c7)" />}
      {ult.tipos.length > 0 && <>
        <h3>Por tipo de bem, em {ult.ano}</h3>
        <Barras itens={ult.tipos.slice(0, 8).map((t) => ({ label: t.tipo, valor: t.valor }))} formato={(v) => reais(v)} />
      </>}
      <div className="table-wrap"><table>
        <thead><tr><th>Eleição</th><th>Cargo disputado</th><th>Resultado</th><th className="num">Total declarado</th></tr></thead>
        <tbody>{[...prin, ...outras].sort((a, b) => b.ano - a.ano).map((d, i) => (
          <tr key={`${d.ano}${i}`} className={d.principal ? "" : "muted"}>
            <td><a href={d.fonte} target="_blank" rel="noreferrer">{d.ano}{d.suplementar ? " (suplementar)" : ""} ↗</a></td>
            <td>{d.cargo}{d.local ? `, ${d.local}` : ""} <span className="muted small">{d.partido}</span>{!d.principal && <div className="small">outro registro no mesmo ano ({d.situacao.toLowerCase() || "sem votação"})</div>}</td>
            <td>{d.resultado || d.situacao}</td>
            <td className="num">{d.sem_bens ? "não declarou" : reais(d.total)}</td>
          </tr>
        ))}</tbody>
      </table></div>
      <p className="small muted">Valor declarado pela própria pessoa (em geral o do imposto de renda), não o valor de mercado. Valores da época. Ligamos o registro do TSE ao parlamentar pelo nome civil e pela data de nascimento. Fonte: dados abertos do TSE (link em cada ano). Atualizado em {dataBR(data.atualizado)}. <Link to="/patrimonio">Veja todos os parlamentares ›</Link></p>
    </section>
  );
}
