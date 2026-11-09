import { useMemo, useState } from "react";
import { Loading, useData } from "./ui";
import { dataBR, linkSeguro, reais, type MapaMG, type Viagem, type ViagensDetalhe, type ViagensPessoa } from "../data";

const MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const SEMANA = ["D", "S", "T", "Q", "Q", "S", "S"];
const dia = (a: number, m: number, d: number) => `${a}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

/** Os dias (aaaa-mm-dd) de uma viagem, do início ao fim. Sem fim, só o dia do início. */
function diasDaViagem(v: Viagem): string[] {
  const ini = new Date(`${v.inicio.slice(0, 10)}T12:00:00Z`);
  const fim = new Date(`${(v.fim && v.fim >= v.inicio ? v.fim : v.inicio).slice(0, 10)}T12:00:00Z`);
  if (isNaN(ini.getTime()) || isNaN(fim.getTime())) return [];
  const out: string[] = [];
  for (let d = ini; d <= fim && out.length < 366; d = new Date(d.getTime() + 864e5)) out.push(d.toISOString().slice(0, 10));
  return out;
}

/** Margem em volta do desenho, para a bolinha de uma cidade na divisa não ficar cortada */
function comMargem(vb: string): string {
  const [x, y, w, h] = vb.split(" ").map(Number);
  return [x - 16, y - 16, w + 32, h + 32].join(" ");
}

/** Calendário do ano com todos os dias de viagem e, ao lado, o mapa de Minas com as cidades visitadas.
 *  Lê a lista completa de viagens da pessoa (estado/viagens/<id>.json). */
export function ViagensAno({ v, mapa }: { v: ViagensPessoa; mapa?: MapaMG | null }) {
  const { data, error } = useData<ViagensDetalhe>(v.id && /^[a-z0-9-]+$/.test(v.id) ? `estado/viagens/${v.id}.json` : null);
  const anos = v.anos.map((a) => a.ano);
  const [ano, setAno] = useState(anos[0]);
  const [cidade, setCidade] = useState<string | null>(null);
  const [diaSel, setDiaSel] = useState<string | null>(null);
  const viagens = useMemo(() => (data?.viagens || []).filter((u) => u.inicio.startsWith(`${ano}`)), [data, ano]);
  // dia -> viagens daquele dia
  const porDia = useMemo(() => {
    const m = new Map<string, Viagem[]>();
    for (const u of viagens) for (const d of diasDaViagem(u)) m.set(d, [...(m.get(d) || []), u]);
    return m;
  }, [viagens]);
  // cidade -> quantas viagens foram até ela no ano
  const cidades = useMemo(() => {
    const c = new Map<string, number>();
    for (const u of viagens) for (const n of u.destinos) c.set(n, (c.get(n) || 0) + 1);
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [viagens]);
  if (!v.id) return null;
  if (!data) return error ? <p className="small muted">O calendário de viagens não pôde ser carregado.</p> : <Loading />;
  const lugares = data.lugares || {};
  const noMapa = cidades.filter(([n]) => lugares[n]);
  const fora = cidades.filter(([n]) => !lugares[n]);
  const diasNoAno = [...porDia.keys()].filter((d) => d.startsWith(`${ano}`)).length;
  const marca = (u: Viagem) => !cidade || u.destinos.includes(cidade);
  const doDia = diaSel ? (porDia.get(diaSel) || []) : [];
  const maxVezes = Math.max(1, ...noMapa.map(([, n]) => n));
  const hoje = new Date().toISOString().slice(0, 10);

  return (
    <div className="viagens-ano">
      <div className="viagens-anos" role="tablist" aria-label="Ano das viagens">
        {anos.map((a) => <button key={a} role="tab" aria-selected={a === ano} className={a === ano ? "ativo" : ""}
          onClick={() => { setAno(a); setCidade(null); setDiaSel(null); }}>{a}</button>)}
      </div>
      <p className="small" style={{ margin: "6px 0 10px" }}>
        Em {ano}: <strong className="num">{viagens.length}</strong> viage{viagens.length === 1 ? "m" : "ns"}, <strong className="num">{diasNoAno}</strong> dia{diasNoAno === 1 ? "" : "s"} fora a serviço e <strong className="num">{cidades.length}</strong> cidade{cidades.length === 1 ? "" : "s"} visitada{cidades.length === 1 ? "" : "s"}.
        {cidade && <> Mostrando só as viagens para <strong>{cidade}</strong>. <button className="link small" onClick={() => setCidade(null)}>Mostrar todas</button></>}
      </p>
      <div className="viagens-grade">
        <div className="calendario" aria-label={`Calendário das viagens de ${ano}`}>
          {MESES.map((nome, m) => {
            const primeiro = new Date(Date.UTC(ano, m, 1)).getUTCDay();
            const n = new Date(Date.UTC(ano, m + 1, 0)).getUTCDate();
            return (
              <div key={m} className="cal-mes">
                <div className="cal-nome">{nome}</div>
                <div className="cal-dias">
                  {SEMANA.map((s, i) => <span key={`s${i}`} className="cal-sem" aria-hidden="true">{s}</span>)}
                  {Array.from({ length: primeiro }, (_, i) => <span key={`v${i}`} />)}
                  {Array.from({ length: n }, (_, i) => {
                    const d = dia(ano, m, i + 1);
                    const us = (porDia.get(d) || []).filter(marca);
                    const titulo = us.length ? `${dataBR(d)}: ${us.map((u) => u.destinos.join(", ") || "destino não informado").join("; ")}` : dataBR(d);
                    return us.length
                      ? <button key={d} className={`cal-dia com-viagem${diaSel === d ? " sel" : ""}`} title={titulo} aria-label={titulo}
                          onClick={() => setDiaSel(diaSel === d ? null : d)}>{i + 1}</button>
                      : <span key={d} className={`cal-dia${d > hoje ? " futuro" : ""}`} title={titulo}>{i + 1}</span>;
                  })}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mapa-viagens">
          {mapa ? (
            <svg viewBox={comMargem(mapa.vb)} role="img" aria-label={`Mapa de Minas Gerais com as cidades visitadas em ${ano}`}>
              <path d={mapa.contorno} className="mapa-mg" />
              {noMapa.slice().reverse().map(([n, vezes]) => {
                const [x, y, oficial] = lugares[n]!;
                const r = 4 + 10 * Math.sqrt(vezes / maxVezes);
                return (
                  <circle key={n} cx={x} cy={y} r={r} className={`ponto${cidade === n ? " ativo" : ""}${cidade && cidade !== n ? " apagado" : ""}`}
                    tabIndex={0} role="button" aria-label={`${oficial}: ${vezes} viage${vezes === 1 ? "m" : "ns"}`}
                    onClick={() => setCidade(cidade === n ? null : n)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setCidade(cidade === n ? null : n); } }}>
                    <title>{`${oficial}: ${vezes} viage${vezes === 1 ? "m" : "ns"} em ${ano}`}</title>
                  </circle>
                );
              })}
            </svg>
          ) : <p className="small muted">O mapa de Minas (IBGE) não pôde ser baixado nesta atualização.</p>}
          {cidades.length > 0 && <ul className="lista-cidades small">
            {cidades.slice(0, 12).map(([n, vezes]) => (
              <li key={n}><button className={`link${cidade === n ? " ativo" : ""}`} onClick={() => setCidade(cidade === n ? null : n)}>{lugares[n]?.[2] || n}</button> <span className="num muted">{vezes}×</span>{!lugares[n] && <span className="muted"> (fora de Minas)</span>}</li>
            ))}
          </ul>}
          {cidades.length > 12 && <p className="small muted">E mais {cidades.length - 12} cidade{cidades.length - 12 === 1 ? "" : "s"}.</p>}
          {fora.length > 0 && mapa && cidades.length > 12 && <p className="small muted">Fora do mapa: {fora.map(([n, vezes]) => `${n} (${vezes}×)`).join(", ")}.</p>}
        </div>
      </div>
      {diaSel && <div className="card small" style={{ marginTop: 10 }}>
        <strong>{dataBR(diaSel)}</strong>
        {doDia.map((u, i) => (
          <p key={i} style={{ margin: "4px 0" }}>{u.destinos.join(", ") || "destino não informado"} · {dataBR(u.inicio)}{u.fim && u.fim !== u.inicio && <> até {dataBR(u.fim)}</>} · <span className="num">{reais(u.valor)}</span>
            {u.motivo && <span className="muted"><br />{u.motivo}</span>}</p>
        ))}
      </div>}
      <p className="small muted">Cada dia pintado é um dia em viagem a serviço, do dia da ida ao da volta. Clique num dia para ver a viagem, ou numa cidade para ver só as viagens até ela.
        Fonte: <a href={linkSeguro(data.fonte)} target="_blank" rel="noreferrer">sistema de viagens do estado (SCDP), no Dados MG ↗</a>
        {mapa && <>; mapa e pontos das cidades: <a href={linkSeguro(mapa.fonte)} target="_blank" rel="noreferrer">API de malhas do IBGE ↗</a></>}.</p>
    </div>
  );
}
