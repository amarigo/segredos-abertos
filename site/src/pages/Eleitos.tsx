import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Explain, Loading, OndeVer, useData } from "../components/ui";
import { NOME_UF } from "../components/graficos";
import { dataBR, reais, type Eleito, type EleitosCidades, type EleitosEstados, type EleitosIndice, type LugarEleitos } from "../data";

/* Quem foi eleito para os mandatos de agora: governador e assembleia de cada estado, prefeito e câmara de cada cidade,
   com o patrimônio declarado ao TSE (eleitos/estados.json, eleitos/indice.json e eleitos/cidades/{UF}.json, montados
   por etl/sa_etl/eleitos.py). */

const semAcento = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const NOME_CARGO: Record<string, string> = {
  governador: "governador", vice: "vice", deputados: "deputados estaduais", prefeito: "prefeito", vereadores: "vereadores",
};

function porPartido(xs: Eleito[]) {
  const c: Record<string, number> = {};
  xs.forEach((x) => { c[x.partido] = (c[x.partido] || 0) + 1; });
  return Object.entries(c).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([label, valor]) => ({ label, valor }));
}

/* Cadeiras por partido em uma linha de etiquetas (uma barra por partido ficava alta demais com 20 partidos) */
function Partidos({ xs }: { xs: Eleito[] }) {
  return (
    <div className="tags partidos-cadeiras" aria-label="Cadeiras por partido">
      {porPartido(xs).map((p) => <span key={p.label} className="chip">{p.label} <strong>{p.valor}</strong></span>)}
    </div>
  );
}

function Pessoa({ x, cargo }: { x: Eleito; cargo: string }) {
  return (
    <div className="card eleito-card">
      <span className="eyebrow">{cargo}</span>
      <strong>{x.nome}</strong>
      <span className="small muted">{x.civil} · {x.partido} · {x.numero}</span>
      <span className="small">{x.resultado}{x.suplementar ? ` na eleição suplementar de ${dataBR(x.suplementar)}` : ""}</span>
      <span className="small">Patrimônio declarado: <strong className="num">{x.sem_bens ? "não declarou bens" : reais(x.patrimonio)}</strong></span>
      {x.tipos && x.tipos.length > 0 && <span className="small muted">{x.tipos.slice(0, 3).map((t) => `${t.tipo}: ${reais(t.valor)}`).join(" · ")}</span>}
    </div>
  );
}

function Tabela({ xs, titulo }: { xs: Eleito[]; titulo: string }) {
  const [ordem, setOrdem] = useState<"partido" | "patrimonio">("partido");
  const [todos, setTodos] = useState(false);
  const ordenada = ordem === "partido" ? xs : [...xs].sort((a, b) => b.patrimonio - a.patrimonio);
  const lista = todos ? ordenada : ordenada.slice(0, 15);
  return (
    <>
      <div className="row graf-controles">
        <div className="toggle" role="group" aria-label={`Ordem: ${titulo}`}>
          <button aria-pressed={ordem === "partido"} onClick={() => setOrdem("partido")}>Por partido</button>
          <button aria-pressed={ordem === "patrimonio"} onClick={() => setOrdem("patrimonio")}>Maior patrimônio</button>
        </div>
      </div>
      <div className="table-wrap"><table aria-label={titulo}>
        <thead><tr><th>Nome na urna</th><th>Partido</th><th>Resultado</th><th className="num">Patrimônio declarado</th></tr></thead>
        <tbody>{lista.map((x) => (
          <tr key={x.sq}>
            <td>{x.nome}<div className="small muted">{x.civil}</div></td>
            <td>{x.partido}</td>
            <td>{x.resultado}{x.suplementar ? <div className="small">suplementar de {dataBR(x.suplementar)}</div> : null}</td>
            <td className="num">{x.sem_bens ? "não declarou" : reais(x.patrimonio)}</td>
          </tr>
        ))}</tbody>
      </table></div>
      {xs.length > lista.length && <button className="btn alt" onClick={() => setTodos(true)}>Ver todos os {xs.length}</button>}
    </>
  );
}

function SemEleito({ lug }: { lug: LugarEleitos }) {
  if (!lug.sem_eleito?.length) return null;
  return (
    <p className="small aviso-salto" role="note">
      O arquivo do TSE não traz ninguém eleito para {lug.sem_eleito.map((c) => NOME_CARGO[c] || c).join(", ")}. Isso
      acontece quando a eleição do cargo foi anulada, está em julgamento na Justiça Eleitoral ou o mais votado teve o
      registro negado. Não escolhemos ninguém no lugar do TSE.
    </p>
  );
}

function Suplementares({ lug }: { lug: LugarEleitos }) {
  const s = Object.entries(lug.suplementar || {});
  const p = Object.entries(lug.suplementar_parcial || {});
  if (!s.length && !p.length) return null;
  return (
    <ul className="small muted">
      {s.map(([c, d]) => <li key={c}>{NOME_CARGO[c] || c}: eleito na eleição suplementar de {dataBR(d)}, que substituiu a eleição normal.</li>)}
      {p.map(([c, d]) => <li key={c}>{NOME_CARGO[c] || c}: a eleição suplementar de {dataBR(d)} preencheu só parte das cadeiras. O TSE não diz quem foi substituído; mostramos os eleitos das duas.</li>)}
    </ul>
  );
}

export default function EleitosPage() {
  const { data: est, error } = useData<EleitosEstados>("eleitos/estados.json");
  const { data: indice } = useData<EleitosIndice>("eleitos/indice.json");
  const [params, setParams] = useSearchParams();
  const ufs = Object.keys(est?.ufs || {}).sort();
  const uf = params.get("uf") && ufs.includes(params.get("uf")!) ? params.get("uf")! : (ufs.includes("MG") ? "MG" : ufs[0]);
  const cidade = params.get("cidade") || "";
  const mudar = (k: string, v: string) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); setParams(p, { replace: true }); };
  if (!est) return <Loading error={error} />;
  const lug = est.ufs[uf];

  return (
    <section className="eleitos">
      <p className="small"><Link to="/politicos">‹ Políticos</Link></p>
      <span className="eyebrow">Eleições</span>
      <h1>Quem foi eleito nos estados e nas cidades</h1>
      <Explain>
        Governadores e deputados estaduais eleitos em {est.ano} (mandato {est.mandato}) e prefeitos e vereadores eleitos
        em {indice?.ano ?? "—"} (mandato {indice?.mandato ?? "—"}), com o patrimônio que cada um declarou ao TSE.
        Eleito não é o mesmo que quem está no cargo hoje: há cassação, renúncia, morte e suplente que assume. O TSE publica
        quem foi eleito, e é isso que mostramos.
      </Explain>
      {est.proxima && <p className="small"><a href={est.proxima}>A eleição de 2026 já aconteceu: veja os resultados e quem foi eleito para o mandato de 2027 ›</a></p>}

      <h2>Governador e assembleia</h2>
      <div className="row graf-controles">
        <label className="small" htmlFor="eleitos-uf">Estado</label>
        <select id="eleitos-uf" value={uf} onChange={(e) => mudar("uf", e.target.value)}>
          {ufs.map((u) => <option key={u} value={u}>{NOME_UF[u] || u}</option>)}
        </select>
      </div>
      {lug && <>
        <SemEleito lug={lug} />
        <div className="grid">
          {(lug.governador || []).map((x) => <Pessoa key={x.sq} x={x} cargo={`Governador${uf === "DF" ? " do DF" : ""}`} />)}
          {(lug.vice || []).map((x) => <Pessoa key={x.sq} x={x} cargo="Vice-governador" />)}
        </div>
        <Suplementares lug={lug} />
        <h3>{lug.casa}{uf !== "DF" ? ` de ${NOME_UF[uf] || uf}` : ""}: {(lug.deputados || []).length} deputados{lug.vagas ? ` (${lug.vagas} vagas)` : ""}</h3>
        <Partidos xs={lug.deputados || []} />
        <Tabela xs={lug.deputados || []} titulo={`Deputados estaduais de ${uf}`} />
        <p className="small muted">Fonte: <a href={est.fonte} target="_blank" rel="noreferrer">dados abertos do TSE, candidatos de {est.ano} ↗</a> (o número de eleitos é conferido com o arquivo de vagas do TSE). Atualizado em {dataBR(est.atualizado)}.</p>
      </>}

      <h2>Prefeito e vereadores</h2>
      {indice ? <BuscaCidade indice={indice} cidade={cidade} setCidade={(c) => mudar("cidade", c)} /> : <Loading />}

      <OndeVer links={[
        { nome: "TSE: DivulgaCandContas", url: "https://divulgacandcontas.tse.jus.br/", explica: "cada candidato, com bens, contas e situação" },
        { nome: "TSE: dados abertos", url: est.fonte, explica: "arquivos de candidatos, bens e vagas" },
      ]} />
      <p className="small"><Link to="/patrimonio">Patrimônio declarado dos deputados federais e senadores ›</Link></p>
    </section>
  );
}

function BuscaCidade({ indice, cidade, setCidade }: { indice: EleitosIndice; cidade: string; setCidade: (c: string) => void }) {
  const [q, setQ] = useState("");
  const achadas = useMemo(() => {
    const b = semAcento(q.trim());
    if (b.length < 2) return [];
    return indice.cidades.filter(([, , nome]) => semAcento(nome).includes(b))
      .sort((a, b2) => Number(!semAcento(a[2]).startsWith(b)) - Number(!semAcento(b2[2]).startsWith(b)) || a[2].localeCompare(b2[2]))
      .slice(0, 12);
  }, [q, indice]);
  const [ufSel, ueSel] = cidade.split("-");
  return (
    <>
      <p className="small muted">
        {indice.cidades.length.toLocaleString("pt-BR")} cidades, {indice.prefeitos.toLocaleString("pt-BR")} prefeitos e{" "}
        {indice.vereadores.toLocaleString("pt-BR")} vereadores eleitos em {indice.ano}
        {indice.sem_eleito ? `; em ${indice.sem_eleito} cidades o TSE não traz eleito para algum cargo` : ""}.
      </p>
      <div className="search">
        <input id="busca-cidade" aria-label="Cidade" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Digite o nome da cidade" />
      </div>
      {achadas.length > 0 && <ul className="lista-cidades">
        {achadas.map(([u, ue, nome]) => (
          <li key={`${u}${ue}`}><button className="link" onClick={() => { setCidade(`${u}-${ue}`); setQ(""); }}>{nome} <span className="muted">({u})</span></button></li>
        ))}
      </ul>}
      {q.trim().length >= 2 && !achadas.length && <p className="small muted">Nenhuma cidade com esse nome.</p>}
      {ufSel && ueSel && <Cidade uf={ufSel} ue={ueSel} />}
    </>
  );
}

function Cidade({ uf, ue }: { uf: string; ue: string }) {
  const { data, error } = useData<EleitosCidades>(/^[A-Z]{2}$/.test(uf) ? `eleitos/cidades/${uf}.json` : null);
  if (!data) return <Loading error={error} />;
  const lug = data.cidades.find((c) => c.ue === ue);
  if (!lug) return <p className="small muted">Cidade não encontrada.</p>;
  const ver = lug.vereadores || [];
  return (
    <div className="eleitos-cidade" data-testid="eleitos-cidade">
      <h3>{lug.nome} ({uf})</h3>
      <SemEleito lug={lug} />
      <div className="grid">
        {(lug.prefeito || []).map((x) => <Pessoa key={x.sq} x={x} cargo="Prefeito" />)}
        {(lug.vice || []).map((x) => <Pessoa key={x.sq} x={x} cargo="Vice-prefeito" />)}
      </div>
      <Suplementares lug={lug} />
      {ver.length > 0 && <>
        <h4>Câmara Municipal: {ver.length} vereadores{lug.vagas ? ` (${lug.vagas} vagas)` : ""}</h4>
        <Partidos xs={ver} />
        <Tabela xs={ver} titulo={`Vereadores de ${lug.nome}`} />
      </>}
      <p className="small muted">Mandato {data.mandato}. Fonte: <a href={data.fonte} target="_blank" rel="noreferrer">dados abertos do TSE, candidatos de {data.ano} ↗</a>. Atualizado em {dataBR(data.atualizado)}.</p>
    </div>
  );
}
