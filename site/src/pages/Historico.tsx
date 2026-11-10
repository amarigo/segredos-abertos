import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, OndeVer, useData } from "../components/ui";
import { ColunasAnos } from "../components/graficos";
import { MESES_LONGOS, reais, reaisCurto, type Historico, type HistoricoAno, type HistoricoPessoa, type Resumo } from "../data";

/* Histórico da cota parlamentar desde 2008: somas por ano de cada Casa (historico.json) e, no perfil, de cada
   parlamentar (h/{id}.json). Os valores vêm prontos do coletor; aqui só escolhemos o que mostrar. */

type Casa = "camara" | "senado" | "as_duas";
const NOME_CASA: Record<Casa, string> = { camara: "Câmara", senado: "Senado", as_duas: "Câmara e Senado" };

export const PERFIL_OFICIAL = (id: string) => id.startsWith("dep-")
  ? `https://www.camara.leg.br/deputados/${id.slice(4)}`
  : `https://www25.senado.leg.br/web/senadores/senador/-/perfil/${id.slice(4)}`;

function mesAno(base: string): string {
  return /^\d{6}$/.test(base) ? `${MESES_LONGOS[Number(base.slice(4)) - 1]} de ${base.slice(0, 4)}` : "";
}

/* Valor curto para colunas estreitas, sem o "R$" (o título já diz que é dinheiro) */
const compacto = (v: number) => v >= 1e6 ? `${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: v >= 1e8 ? 0 : 1 })} mi`
  : v >= 1e3 ? `${Math.round(v / 1e3).toLocaleString("pt-BR")} mil` : Math.round(v).toLocaleString("pt-BR");

function listaMeses(ms: number[]): string {
  const n = ms.map((m) => MESES_LONGOS[m - 1]);
  return n.length > 1 ? `${n.slice(0, -1).join(", ")} e ${n[n.length - 1]}` : n.join("");
}

export default function HistoricoPage() {
  const { data, error } = useData<Historico>("historico.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const [casa, setCasa] = useState<Casa>("as_duas");
  const [hoje, setHoje] = useState(true);
  const [ano, setAno] = useState("");
  const comPerfil = useMemo(() => new Set((pols || []).map((p) => p.id)), [pols]);
  if (!data) return <Loading error={error} />;

  const temIpca = data.anos.some((x) => x.total_hoje != null);
  const usarHoje = hoje && temIpca;
  const valor = (x: HistoricoAno) => (usarHoje ? x.total_hoje : x.total);
  const linhas = data.anos.filter((x) => casa === "as_duas" || x.casa === casa);
  const anos = [...new Set(linhas.map((x) => String(x.ano)))].sort();
  const somaAno = (a: string, f: (x: HistoricoAno) => number | null) => {
    const xs = linhas.filter((x) => String(x.ano) === a);
    const vs = xs.map(f);
    return vs.some((v) => v == null) ? null : vs.reduce((s: number, v) => s + (v as number), 0);
  };
  const serie: [string, number | null][] = anos.map((a) => [a, somaAno(a, valor)]);
  const anoAtual = String(new Date().getFullYear());
  const parcial = new Set(anos.filter((a) => a === anoAtual));
  const anoSel = anos.includes(ano) ? ano : anos[anos.length - 1];
  const doAno = linhas.filter((x) => String(x.ano) === anoSel);
  const cats: Record<string, number> = {};
  doAno.forEach((x) => Object.entries(x.categorias).forEach(([c, v]) => { cats[c] = (cats[c] || 0) + v; }));
  const fator = (x: HistoricoAno) => (usarHoje && x.total_hoje && x.total ? x.total_hoje / x.total : 1);
  const porParl = (["camara", "senado"] as const).filter((c) => casa === "as_duas" || casa === c).map((c) => ({
    // ano com poucas notas no arquivo oficial fica sem coluna: a média dele não é comparável
    c, serie: data.anos.filter((x) => x.casa === c).map((x) => [String(x.ano), x.poucas_notas ? null : x.por_parlamentar * fator(x)] as [string, number | null]),
  }));
  const poucas = data.anos.filter((x) => (casa === "as_duas" || x.casa === casa) && x.poucas_notas);
  const fracos = data.anos.filter((x) => (casa === "as_duas" || x.casa === casa) && x.meses_fracos.length && !parcial.has(String(x.ano)));
  const fmt = compacto;
  const base = mesAno(data.ipca_base);
  const totalTudo = serie.reduce((s, [, v]) => s + (v || 0), 0);
  const maiores = (["camara", "senado"] as const).filter((c) => casa === "as_duas" || casa === c);

  return (
    <section className="historico">
      <p className="small"><Link to="/politicos">‹ Políticos</Link></p>
      <span className="eyebrow">Cota parlamentar</span>
      <h1>A cota parlamentar desde {data.inicio}</h1>
      <Explain>
        A cota paga, com nota fiscal, gastos do mandato: viagens, escritório, divulgação, combustível. Aqui está quanto a
        Câmara e o Senado gastaram com ela em cada ano desde {data.inicio}, segundo os arquivos oficiais.
        {temIpca && base && <> Em "reais de hoje", cada mês foi corrigido pela inflação (IPCA) até {base}.</>}
      </Explain>
      <div className="row graf-controles">
        <div className="toggle" role="group" aria-label="Casa">
          {(["as_duas", "camara", "senado"] as Casa[]).map((c) => (
            <button key={c} aria-pressed={casa === c} onClick={() => setCasa(c)}>{NOME_CASA[c]}</button>
          ))}
        </div>
        {temIpca && <div className="toggle" role="group" aria-label="Valores">
          <button aria-pressed={usarHoje} onClick={() => setHoje(true)}>Em reais de hoje</button>
          <button aria-pressed={!usarHoje} onClick={() => setHoje(false)}>Valores da época</button>
        </div>}
      </div>
      <h2>Gasto total por ano: {NOME_CASA[casa]}</h2>
      <p className="small muted">Soma de {anos[0]} a {anos[anos.length - 1]}: <strong className="num">{reais(totalTudo)}</strong>{usarHoje ? " em reais de hoje" : " em valores da época"}. Toque num ano para ver os tipos de despesa.</p>
      <ColunasAnos serie={serie} titulo={`Cota parlamentar por ano, ${NOME_CASA[casa]}`} formato={fmt} parcial={parcial} ano={anoSel} setAno={setAno} cor="var(--s1)" compacta={anos.length > 10} />
      <p className="small muted">Valores em reais{usarHoje ? " de hoje" : " da época"}; "mi" é milhão.</p>
      {parcial.size > 0 && <p className="small muted">* {anoAtual} ainda está em andamento.</p>}
      {(poucas.length > 0 || fracos.length > 0) && <ul className="small muted">
        {poucas.map((x) => <li key={`p${x.casa}${x.ano}`}>{x.ano}, {NOME_CASA[x.casa]}: o arquivo oficial tem poucas notas neste ano ({x.notas.toLocaleString("pt-BR")} notas, {reais(x.por_parlamentar)} por parlamentar). Não compare com os outros anos.</li>)}
        {fracos.map((x) => <li key={`f${x.casa}${x.ano}`}>{x.ano}, {NOME_CASA[x.casa]}: poucas notas em {listaMeses(x.meses_fracos)}.</li>)}
      </ul>}

      <h2>Média por parlamentar</h2>
      <Explain>O número de parlamentares muda de ano para ano (suplentes entram quando o titular sai). A média por parlamentar é a soma das notas de cada um dividida por quantos tiveram alguma nota no ano. As notas das lideranças dos partidos ficam fora da média.</Explain>
      {porParl.map(({ c, serie: s }) => (
        <div key={c}>
          <h3>{c === "camara" ? "Média por deputado" : "Média por senador"}</h3>
          <ColunasAnos serie={s} titulo={`Média por parlamentar, ${NOME_CASA[c]}`} formato={fmt} parcial={parcial} cor={c === "camara" ? "var(--s2)" : "var(--s3)"} compacta={s.length > 10} />
        </div>
      ))}

      <h2>Tipos de despesa em {anoSel}</h2>
      <p className="small muted">{NOME_CASA[casa]}, em valores da época{usarHoje ? " (a correção pela inflação vale para o ano inteiro, não para cada tipo)" : ""}.</p>
      <Barras itens={Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([c, v]) => ({ label: c, valor: v }))} formato={(v) => reais(v)} />

      {maiores.map((c) => (
        <div key={c}>
          <h2>Quem mais gastou somando todos os anos: {NOME_CASA[c]}</h2>
          <p className="small muted">Soma de todos os anos com nota desde {data.inicio}{data.maiores[c].some((m) => m.total_hoje != null) ? ", em reais de hoje" : ""}. Quem ficou mais tempo no cargo tende a somar mais: veja os anos ao lado.</p>
          <div className="table-wrap"><table>
            <thead><tr><th>Parlamentar</th><th>Anos com nota</th><th className="num">Total</th></tr></thead>
            <tbody>{data.maiores[c].slice(0, 20).map((m) => (
              <tr key={m.id}>
                <td>{comPerfil.has(m.id) ? <Link to={`/p/${m.id}`}>{m.nome}</Link> : <a href={PERFIL_OFICIAL(m.id)} target="_blank" rel="noreferrer">{m.nome} ↗</a>}
                  {(m.partido || m.uf) && <span className="muted small"> {[m.partido, m.uf].filter(Boolean).join("-")}</span>}</td>
                <td>{m.anos} ({m.de}{m.ate !== m.de ? `–${m.ate}` : ""})</td>
                <td className="num">{reais(m.total_hoje ?? m.total)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      ))}

      <p className="small muted">Fontes: <a href={data.fontes.camara_arquivo.replace("{ano}", anoSel)} target="_blank" rel="noreferrer">arquivo anual da cota da Câmara ↗</a>, <a href={data.fontes.senado_api.replace("{ano}", anoSel)} target="_blank" rel="noreferrer">API da cota do Senado ↗</a>{temIpca && <> e <a href={data.fontes.ipca} target="_blank" rel="noreferrer">IPCA do IBGE ↗</a></>}. Atualizado em {new Date(data.atualizado + "T12:00:00").toLocaleDateString("pt-BR")}.</p>
      <OndeVer links={[
        { nome: "Câmara: gastos parlamentares", url: data.fontes.camara, explica: "consulta da cota de cada deputado, por ano" },
        { nome: "Senado: transparência dos senadores", url: data.fontes.senado, explica: "cota (CEAPS) de cada senador" },
        { nome: "IBGE: IPCA", url: data.fontes.ipca, explica: "tabela 1737, inflação mês a mês" },
      ]} />
    </section>
  );
}

/* "PT (2009–2018), PSB (2019–2026)": o partido de cada período, sem repetir ano a ano */
function partidos(lista: [string, string][]): string {
  const g: { p: string; de: string; ate: string }[] = [];
  for (const [a, p] of lista) {
    const u = g[g.length - 1];
    if (u && u.p === (p || "?")) u.ate = a; else g.push({ p: p || "?", de: a, ate: a });
  }
  return g.map((x) => `${x.p} (${x.de}${x.ate !== x.de ? `–${x.ate}` : ""})`).join(", ");
}

/* No perfil: a cota da pessoa em todos os anos de mandato desde 2008 (quando houver h/{id}.json). */
export function HistoricoPolitico({ id }: { id: string }) {
  const { data } = useData<HistoricoPessoa>(`h/${id}.json`);
  if (!data || Object.keys(data.anos).length < 2) return null;
  const anos = Object.keys(data.anos).sort();
  const temHoje = anos.every((a) => data.anos[a].total_hoje != null);
  const serie: [string, number][] = anos.map((a) => [a, temHoje ? data.anos[a].total_hoje! : data.anos[a].total]);
  const anoAtual = String(new Date().getFullYear());
  return (
    <div className="historico-politico">
      <h3>Cota em todos os anos com nota, desde {anos[0]}</h3>
      <ColunasAnos serie={serie} titulo={`Cota parlamentar por ano de ${data.nome}`} formato={anos.length > 10 ? compacto : reaisCurto} parcial={new Set(anos.filter((a) => a === anoAtual))} cor="var(--s2)" compacta={anos.length > 10} />
      <p className="small muted">{temHoje ? "Em reais de hoje (corrigido pelo IPCA). " : "Em valores da época. "}Soma das notas dos arquivos oficiais de cada ano; nos anos mais recentes, é o mesmo total mostrado acima. {anos.some((a) => data.anos[a].partido) && <>Partido: {partidos(anos.map((a) => [a, data.anos[a].partido]))}. </>}<Link to="/historico">Veja a Câmara e o Senado desde 2008 ›</Link></p>
    </div>
  );
}
