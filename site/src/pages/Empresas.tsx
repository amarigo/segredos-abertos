import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Barras, Explain, Loading, OndeVer, useAno, useData } from "../components/ui";
import { cnpjFmt, cotaNoAno, reais, type EmpresaResumo } from "../data";
import { norm } from "./Home";
import { AvisosFim } from "../components/Selo";

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
  if (!data) return <Loading error={error} />;
  return (
    <section>
      <span className="eyebrow">Cota parlamentar · {porAno ? ano : "todos os anos"}</span>
      <h1>Empresas</h1>
      <Explain>As empresas que mais receberam dinheiro da cota parlamentar{porAno ? <> em <strong>{ano}</strong> (troque o ano no topo da página)</> : null}. Em cada uma você vê quem são os donos (pela Receita Federal) e quais parlamentares pagaram.</Explain>
      <div className="search"><input id="busca-empresa" aria-label="Buscar empresa" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou CNPJ" /></div>
      {lista.length > 1 && <Abrir aberto titulo={`Gráfico: as 15 empresas que mais receberam${porAno ? ` em ${ano}` : ""}`}>
        <Barras itens={lista.slice(0, 15).map((e) => ({ label: <Link to={`/e/${e.cnpj}`}>{e.nome}</Link>, nota: `${cotaNoAno(e, ano)?.n_politicos ?? e.n_politicos} parlamentares`, valor: valor(e), cor: "var(--s1)" }))} />
      </Abrir>}
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
      <OndeVer links={[
        { nome: "Gastos da cota parlamentar na Câmara", url: "https://www.camara.leg.br/transparencia/gastos-parlamentares", explica: "as notas pagas a cada empresa" },
        { nome: "Dados abertos do Senado", url: "https://www12.senado.leg.br/dados-abertos", explica: "os gastos dos senadores" },
        { nome: "Donos e endereço de cada empresa (Minha Receita)", url: "https://minhareceita.org", explica: "a base de CNPJ da Receita Federal" },
      ]} />
      <AvisosFim secao="empresas" />
    </section>
  );
}
