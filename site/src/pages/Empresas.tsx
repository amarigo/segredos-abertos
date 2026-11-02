import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Barras, Explain, Loading, OndeVer, useAno, useData } from "../components/ui";
import { cnpjFmt, corPartido, cotaNoAno, reais, type CotaAnoEmpresa, type EmpresaResumo } from "../data";
import { norm } from "./Home";
import { AvisosFim } from "../components/Selo";
import { CompararAnos, Kpi, Rosca, curto, numero, prepararFatias, type Fatia } from "../components/graficos";

const LADOS = [
  { k: "esquerda", nome: "Esquerda", cor: "var(--esq)" },
  { k: "centro", nome: "Centro", cor: "var(--centro)" },
  { k: "direita", nome: "Direita", cor: "var(--dir)" },
  { k: "sem", nome: "Sem posição", cor: "var(--outro)" },
];
type OrdemEmp = "valor" | "media" | "n";

/** Barrinha empilhada com a parte de parlamentares de cada lado que pagaram à empresa */
function BarraLados({ lados }: { lados?: Record<string, [number, number]> }) {
  if (!lados) return <span className="muted">—</span>;
  const n = LADOS.reduce((a, l) => a + (lados[l.k]?.[0] || 0), 0) || 1;
  const txt = LADOS.filter((l) => lados[l.k]?.[0]).map((l) => `${l.nome} ${Math.round(((lados[l.k]?.[0] || 0) / n) * 100)}%`).join(" · ");
  return (
    <div title={txt}>
      <div className="stack" aria-hidden="true">{LADOS.map((l) => lados[l.k]?.[0] ? <span key={l.k} style={{ width: `${((lados[l.k][0]) / n) * 100}%`, background: l.cor }} /> : null)}</div>
      <div className="small muted">{txt}</div>
    </div>
  );
}

export default function Empresas() {
  const { data, error } = useData<EmpresaResumo[]>("empresas.json");
  const [q, setQ] = useState("");
  const [ordem, setOrdem] = useState<OrdemEmp>("valor");
  const [partido, setPartido] = useState("");
  const [lado, setLado] = useState("");
  const { ano } = useAno();
  // O ano escolhido no topo é o principal: só entram as empresas pagas naquele ano, da maior para a menor.
  // Sem o detalhe por ano (dados antigos), a lista usa o total de todos os anos e avisa.
  const porAno = !!data?.some((e) => e.por_ano);
  const valor = (e: EmpresaResumo) => cotaNoAno(e, ano)?.valor ?? e.total;
  const nPol = (e: EmpresaResumo) => cotaNoAno(e, ano)?.n_politicos ?? e.n_politicos;
  const media = (e: EmpresaResumo) => valor(e) / (nPol(e) || 1);
  const lados = (e: EmpresaResumo) => (cotaNoAno(e, ano) as CotaAnoEmpresa | null)?.lados;
  const partidosE = (e: EmpresaResumo) => (cotaNoAno(e, ano) as CotaAnoEmpresa | null)?.partidos || [];
  // "mais de metade dos parlamentares que pagaram são do lado escolhido"
  const doLado = (e: EmpresaResumo) => { const l = lados(e); if (!l) return false; const n = Object.values(l).reduce((a, x) => a + x[0], 0); return (l[lado]?.[0] || 0) * 2 > n; };
  const lista = useMemo(() => (data || [])
    .filter((e) => !porAno || valor(e) > 0)
    .filter((e) => !q || norm(e.nome).includes(norm(q)) || e.cnpj.includes(q.replace(/\D/g, "") || "x"))
    .filter((e) => !partido || partidosE(e).some(([p]) => p === partido))
    .filter((e) => !lado || doLado(e))
    .sort((a, b) => ordem === "media" ? media(b) - media(a) : ordem === "n" ? nPol(b) - nPol(a) || valor(b) - valor(a) : valor(b) - valor(a)), [data, q, ano, porAno, ordem, partido, lado]);
  const todosPartidos = useMemo(() => [...new Set((data || []).flatMap((e) => partidosE(e).map(([p]) => p)))].sort(), [data, ano]);
  // Somas da lista filtrada, para os gráficos
  const somaPartidos = useMemo(() => {
    const m: Record<string, number> = {};
    lista.forEach((e) => partidosE(e).forEach(([p, v]) => { m[p] = (m[p] || 0) + v; }));
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [lista]);
  const somaLados = useMemo(() => {
    const m: Record<string, number> = {};
    lista.forEach((e) => Object.entries(lados(e) || {}).forEach(([k, [, v]]) => { m[k] = (m[k] || 0) + v; }));
    return m;
  }, [lista]);
  const graf = useMemo(() => {
    const anos = new Set<string>();
    (data || []).forEach((e) => Object.keys(e.por_ano || {}).forEach((a) => anos.add(a)));
    const total: [string, number][] = [...anos].sort().map((a) => [a, (data || []).reduce((s, e) => s + (e.por_ano?.[a]?.valor || 0), 0)]);
    const qtd: [string, number][] = [...anos].sort().map((a) => [a, (data || []).filter((e) => (e.por_ano?.[a]?.valor || 0) > 0).length]);
    // As empresas que mais receberam em algum ano, comparadas ano a ano
    const top = new Set((data || []).slice().sort((a, b) => b.total - a.total).slice(0, 15).map((e) => e.cnpj));
    const porAno: Record<string, Fatia[]> = {};
    [...anos].forEach((a) => { porAno[a] = (data || []).filter((e) => top.has(e.cnpj)).map((e) => ({ nome: e.nome, valor: e.por_ano?.[a]?.valor || 0 })); });
    return { total, qtd, porAno };
  }, [data]);
  if (!data) return <Loading error={error} />;
  const totalAno = lista.reduce((s, e) => s + valor(e), 0);
  const temLados = Object.keys(somaLados).length > 0;
  return (
    <section>
      <span className="eyebrow">Cota parlamentar · {porAno ? ano : "todos os anos"}</span>
      <h1>Empresas</h1>
      <Explain>As empresas que mais receberam dinheiro da cota parlamentar{porAno ? <> em <strong>{ano}</strong> (troque o ano no topo da página)</> : null}. Em cada uma você vê quem são os donos (pela Receita Federal) e quais parlamentares pagaram. A <strong>média por parlamentar</strong> é o valor recebido dividido pelo número de parlamentares que pagaram. As cores mostram quantos desses parlamentares são de esquerda, de centro ou de direita, pelo jeito como votam.</Explain>
      {porAno && !q && !partido && !lado && lista.length > 0 && (
        <>
          <div className="grid">
            <Kpi rotulo={`Pago pela cota às empresas da lista em ${ano}`} valor={graf.total.find(([a]) => a === ano)?.[1]} serie={graf.total} ano={ano} dica={`as ${numero(data.length)} empresas que mais receberam, somando todos os anos`} />
            <Kpi rotulo={`Empresas da lista pagas em ${ano}`} valor={graf.qtd.find(([a]) => a === ano)?.[1]} formato={numero} serie={graf.qtd} ano={ano} />
            <Kpi rotulo="Parte das 10 maiores" valor={totalAno ? lista.map(valor).sort((a, b) => b - a).slice(0, 10).reduce((s, v) => s + v, 0) / totalAno : null} formato={(v) => `${Math.round(v * 100)}%`} dica={`do que foi pago às empresas da lista em ${ano}`} />
          </div>
          <div className="secao-graficos">
            <div>
              <h3 className="graf-titulo">Quem ficou com o dinheiro em {ano}</h3>
              <Rosca fatias={prepararFatias(lista.map((e) => ({ nome: e.nome, valor: valor(e) })), 7)} titulo={`Parte de cada empresa no que foi pago às empresas da lista em ${ano}`} centro={curto(totalAno)} />
            </div>
            <CompararAnos porAno={graf.porAno} titulo="As maiores empresas, ano a ano" anoInicial={ano} limite={8} nota="As 15 empresas que mais receberam somando todos os anos. O ano em andamento vai só até a última nota publicada." />
          </div>
        </>
      )}
      <div className="search">
        <input id="busca-empresa" aria-label="Buscar empresa" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou CNPJ" />
        <select id="ordem-empresa" aria-label="Ordenar" value={ordem} onChange={(e) => setOrdem(e.target.value as OrdemEmp)}>
          <option value="valor">Quem mais recebeu</option><option value="media">Maior média por parlamentar</option><option value="n">Mais parlamentares</option>
        </select>
        {todosPartidos.length > 0 && <select id="filtro-partido-emp" aria-label="Partido" value={partido} onChange={(e) => setPartido(e.target.value)}>
          <option value="">Pagas por qualquer partido</option>{todosPartidos.map((p) => <option key={p} value={p}>Pagas pelo {p}</option>)}
        </select>}
        {temLados && <select id="filtro-lado-emp" aria-label="Lado" value={lado} onChange={(e) => setLado(e.target.value)}>
          <option value="">Qualquer lado</option>{LADOS.slice(0, 3).map((l) => <option key={l.k} value={l.k}>Pagas mais pela {l.nome.toLowerCase()}</option>)}
        </select>}
      </div>
      {lista.length > 1 && (
        <div className="grid grid-2">
          <Abrir aberto titulo={`Gráfico: ${ordem === "media" ? "maior média por parlamentar" : "quem mais recebeu"}`}>
            <Barras itens={lista.slice(0, 10).map((e) => ({ label: <Link to={`/e/${e.cnpj}`}>{e.nome}</Link>,
              nota: ordem === "media" ? `${reais(valor(e))} de ${nPol(e)} parlamentares` : `média de ${reais(media(e))} por parlamentar`,
              valor: ordem === "media" ? media(e) : valor(e), cor: "var(--s1)" }))} />
          </Abrir>
          {somaPartidos.length > 0 && <Abrir aberto titulo="Gráfico: quanto cada partido pagou a estas empresas">
            <Barras itens={somaPartidos.slice(0, 12).map(([p, v]) => ({ label: <button className="link" onClick={() => setPartido(partido === p ? "" : p)}>{p}</button>, valor: v, cor: corPartido(p) }))} />
            {temLados && <>
              <p className="small" style={{ marginTop: 12 }}><strong>Por lado</strong></p>
              <Barras itens={LADOS.filter((l) => somaLados[l.k]).map((l) => ({ label: l.nome, valor: somaLados[l.k], cor: l.cor }))} />
            </>}
          </Abrir>}
        </div>
      )}
      <p className="muted small">{lista.length} empresa{lista.length === 1 ? "" : "s"}{partido ? ` pagas por parlamentares do ${partido}` : ""}</p>
      {porAno && !lista.length && !q && !partido && !lado ? <div className="empty">Nenhuma empresa recebeu da cota em {ano} até agora. Escolha outro ano no topo da página.</div> :
      <div className="table-wrap">
        <table>
          <thead><tr><th>Empresa</th><th className="r">Parlamentares</th><th className="r so-largo">Média por parlamentar</th>{temLados && <th className="so-largo">Esquerda, centro e direita</th>}<th className="r">{porAno ? `Recebeu em ${ano}` : "Recebeu (todos os anos)"}</th></tr></thead>
          <tbody>
            {lista.slice(0, 300).map((e) => (
              <tr key={e.cnpj}>
                <td><Link to={`/e/${e.cnpj}`}>{e.nome}</Link><div className="muted small mono">{cnpjFmt(e.cnpj)}</div>
                  {e.n_mesmo_endereco ? <div className="small" style={{ color: "var(--alert-ink)" }}>Mesmo endereço de outra{e.n_mesmo_endereco > 1 ? `s ${e.n_mesmo_endereco}` : ""} fornecedora{e.n_mesmo_endereco > 1 ? "s" : ""}</div> : null}
                  {e.emendas ? <div className="small">Também recebeu {reais(e.emendas)} de emendas parlamentares</div> : null}
                  <div className="so-celular small">Média: <span className="num">{reais(media(e))}</span> por parlamentar</div>
                  {temLados && <div className="so-celular" style={{ maxWidth: 220 }}><BarraLados lados={lados(e)} /></div>}</td>
                <td className="r num">{nPol(e)}</td>
                <td className="r num so-largo">{reais(media(e))}</td>
                {temLados && <td className="so-largo" style={{ minWidth: 160 }}><BarraLados lados={lados(e)} /></td>}
                <td className="r num">{reais(valor(e))}{porAno && e.total !== valor(e) && <div className="small muted">{reais(e.total)} em todos os anos</div>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
      <OndeVer links={[
        { nome: "Gastos da cota parlamentar na Câmara", url: "https://www.camara.leg.br/transparencia/gastos-parlamentares", explica: "as notas pagas a cada empresa" },
        { nome: "Dados abertos do Senado", url: "https://www12.senado.leg.br/dados-abertos", explica: "os gastos dos senadores" },
        { nome: "Donos e endereço de cada empresa (Minha Receita)", url: "https://minhareceita.org", explica: "a base de CNPJ da Receita Federal" },
      ]} />
      <AvisosFim secao="empresas" />
    </section>
  );
}
