import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Explain, Loading, useAno, useData } from "../components/ui";
import { cnpjFmt, cotaNoAno, reais, type EmpresaResumo } from "../data";
import { norm } from "./Home";
import { AvisosFim } from "../components/Selo";
import { CompararAnos, Kpi, Rosca, curto, numero, prepararFatias, type Fatia } from "../components/graficos";

export default function Empresas() {
  const { data, error } = useData<EmpresaResumo[]>("empresas.json");
  const [q, setQ] = useState("");
  const { ano } = useAno();
  // O ano escolhido no topo é o principal: só entram as empresas pagas naquele ano, da maior para a menor.
  // Sem o detalhe por ano (dados antigos), a lista usa o total de todos os anos e avisa.
  const porAno = !!data?.some((e) => e.por_ano);
  const valor = (e: EmpresaResumo) => cotaNoAno(e, ano)?.valor ?? e.total;
  const lista = useMemo(() => (data || [])
    .filter((e) => !porAno || valor(e) > 0)
    .filter((e) => !q || norm(e.nome).includes(norm(q)) || e.cnpj.includes(q.replace(/\D/g, "") || "x"))
    .sort((a, b) => valor(b) - valor(a)), [data, q, ano, porAno]);
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
  return (
    <section>
      <span className="eyebrow">Cota parlamentar · {porAno ? ano : "todos os anos"}</span>
      <h1>Empresas</h1>
      <Explain>As empresas que mais receberam dinheiro da cota parlamentar{porAno ? <> em <strong>{ano}</strong> (troque o ano no topo da página)</> : null}. Em cada uma você vê quem são os donos (pela Receita Federal) e quais parlamentares pagaram.</Explain>
      {porAno && !q && lista.length > 0 && (
        <>
          <div className="grid">
            <Kpi rotulo={`Pago pela cota às empresas da lista em ${ano}`} valor={graf.total.find(([a]) => a === ano)?.[1]} serie={graf.total} ano={ano} dica={`as ${numero(data.length)} empresas que mais receberam, somando todos os anos`} />
            <Kpi rotulo={`Empresas da lista pagas em ${ano}`} valor={graf.qtd.find(([a]) => a === ano)?.[1]} formato={numero} serie={graf.qtd} ano={ano} />
            <Kpi rotulo="Parte das 10 maiores" valor={totalAno ? lista.slice(0, 10).reduce((s, e) => s + valor(e), 0) / totalAno : null} formato={(v) => `${Math.round(v * 100)}%`} dica={`do que foi pago às empresas da lista em ${ano}`} />
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
      <div className="search"><input id="busca-empresa" aria-label="Buscar empresa" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou CNPJ" /></div>
      {porAno && !lista.length && !q ? <div className="empty">Nenhuma empresa recebeu da cota em {ano} até agora. Escolha outro ano no topo da página.</div> :
      <div className="table-wrap">
        <table>
          <thead><tr><th>Empresa</th><th className="r">Parlamentares</th><th className="r">{porAno ? `Recebeu em ${ano}` : "Recebeu (todos os anos)"}</th></tr></thead>
          <tbody>
            {lista.slice(0, 300).map((e) => (
              <tr key={e.cnpj}>
                <td><Link to={`/e/${e.cnpj}`}>{e.nome}</Link><div className="muted small mono">{cnpjFmt(e.cnpj)}</div>
                  {e.n_mesmo_endereco ? <div className="small" style={{ color: "var(--alert-ink)" }}>Mesmo endereço de outra{e.n_mesmo_endereco > 1 ? `s ${e.n_mesmo_endereco}` : ""} fornecedora{e.n_mesmo_endereco > 1 ? "s" : ""}</div> : null}
                  {e.emendas ? <div className="small">Também recebeu {reais(e.emendas)} de emendas parlamentares</div> : null}</td>
                <td className="r num">{cotaNoAno(e, ano)?.n_politicos ?? e.n_politicos}</td>
                <td className="r num">{reais(valor(e))}{porAno && e.total !== valor(e) && <div className="small muted">{reais(e.total)} em todos os anos</div>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
      <AvisosFim secao="empresas" />
    </section>
  );
}
