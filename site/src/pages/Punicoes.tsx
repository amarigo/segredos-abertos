import { useState } from "react";
import { Link } from "react-router-dom";
import { Explain, Loading } from "../components/ui";
import { cnpjFmt, dataBR, linkSeguro } from "../data";
import { ChipCadastro, ListaRegistros, situacaoFonte, usePunicoes, type Cadastro } from "../components/Punicoes";

/** Empresas, sócios e deputados que aparecem nas listas oficiais de punidos (CEIS, CNEP, CEAF e TCU) */
export default function PunicoesPage() {
  const { data: p, error } = usePunicoes();
  const [so, setSo] = useState<"todas" | "vigentes">("vigentes");
  if (!p) return <Loading error={error && "As punições oficiais ainda não foram coletadas."} />;
  const filtro = <T extends { vigente: boolean }>(xs: T[]) => (so === "vigentes" ? xs.filter((x) => x.vigente) : xs);
  const emps = filtro(p.empresas), pols = filtro(p.politicos);
  const c = p.cobertura;
  return (
    <>
      <section className="hero">
        <span className="eyebrow"><Link to="/corrupcao">Corrupção</Link> · Punições oficiais</span>
        <h1 style={{ margin: 0 }}>Quem do site aparece nas listas oficiais de punidos</h1>
        <p className="muted" style={{ margin: 0 }}>
          Empresas que recebem dinheiro público, seus sócios e deputados federais cruzados com as listas oficiais da CGU e do TCU.
          Só entram punições e condenações já decididas, publicadas por quem puniu. Conferido em {dataBR(p.atualizado_em)}.
        </p>
      </section>

      <div className="grid stats" style={{ marginTop: 16 }}>
        <div className="card stat"><span className="label">Empresas do site nas listas</span><span className="value">{p.empresas.filter((e) => e.registros.length).length}</span>
          <span className="hint">pelo próprio CNPJ, de {c.empresas.toLocaleString("pt-BR")} conferidas</span></div>
        <div className="card stat"><span className="label">Empresas com sócio nas listas</span><span className="value">{p.empresas.filter((e) => e.socios.length).length}</span>
          <span className="hint">{c.socios.toLocaleString("pt-BR")} sócios conferidos</span></div>
        <div className="card stat"><span className="label">Deputados federais nas listas</span><span className="value">{p.politicos.length}</span>
          <span className="hint">pelo CPF, {c.deputados_com_cpf} de {c.deputados} conferidos</span></div>
      </div>

      <Explain>
        <strong>Como ler:</strong> estar numa destas listas quer dizer que um órgão público ou a Justiça já decidiu punir. Não é denúncia nem investigação.
        Muitas punições têm prazo: mostramos se ainda está em vigor ou se já terminou. A punição de um sócio é da pessoa, não da empresa.
      </Explain>

      <div className="tabs" role="tablist" style={{ marginTop: 12 }}>
        <button role="tab" aria-selected={so === "vigentes"} onClick={() => setSo("vigentes")}>Em vigor</button>
        <button role="tab" aria-selected={so === "todas"} onClick={() => setSo("todas")}>Todas, inclusive as que já terminaram</button>
      </div>

      <section>
        <h2>Deputados federais</h2>
        {pols.length === 0 ? <div className="empty">Nenhum deputado federal {so === "vigentes" ? "com punição em vigor " : ""}nestas listas.</div>
          : pols.map((x) => (
            <div key={x.id} className="card punicao-bloco">
              <h3 style={{ marginTop: 0 }}><Link to={`/p/${x.id}`}>{x.nome}</Link> <span className="muted small">{x.partido}-{x.uf}</span></h3>
              <ListaRegistros rs={x.registros} fontes={p.fontes} />
            </div>
          ))}
      </section>

      <section>
        <h2>Empresas e sócios</h2>
        {emps.length === 0 ? <div className="empty">Nenhuma empresa do site {so === "vigentes" ? "com punição em vigor " : ""}nestas listas.</div>
          : emps.map((e) => (
            <div key={e.cnpj} className="card punicao-bloco">
              <h3 style={{ marginTop: 0 }}><Link to={`/e/${e.cnpj}`}>{e.nome}</Link> <span className="muted small mono">{cnpjFmt(e.cnpj)}</span></h3>
              {e.registros.length > 0 && <ListaRegistros rs={e.registros} fontes={p.fontes} />}
              {e.socios.map((s) => (
                <div key={s.nome + s.doc} className="punicao-socio">
                  <span className="small muted">Sócio:</span> <strong>{s.nome}</strong> <span className="mono small">{s.doc.length === 14 ? cnpjFmt(s.doc) : s.doc}</span>
                  <ListaRegistros rs={s.registros} fontes={p.fontes} />
                </div>
              ))}
            </div>
          ))}
      </section>

      <section>
        <h2>As listas</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Lista</th><th>O que é</th><th className="r">Linhas</th><th>Situação</th></tr></thead>
            <tbody>
              {(Object.keys(p.fontes) as Cadastro[]).map((k) => {
                const f = p.fontes[k];
                return (
                  <tr key={k}>
                    <td><ChipCadastro cad={k} fontes={p.fontes} /><div className="small"><a href={linkSeguro(f.pagina)} target="_blank" rel="noreferrer">{f.titulo} ↗</a></div><div className="small muted">{f.quem}</div></td>
                    <td className="small">{f.explica}</td>
                    <td className="r num">{f.n.toLocaleString("pt-BR")}</td>
                    <td className="small">{situacaoFonte(f)}{f.lida_em && <> · {dataBR(f.lida_em)}</>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Como cruzamos as listas</h2>
        <ul className="small">
          <li>As listas vêm da API oficial do Portal da Transparência (CEIS, CNEP e CEAF, da CGU) e dos serviços oficiais do Tribunal de Contas da União. Cada punição tem o link para a fonte.</li>
          <li><strong>Empresa:</strong> o CNPJ da lista tem de ser igual ao da empresa. Não usamos nome parecido.</li>
          <li><strong>Sócio:</strong> a Receita mostra o CPF do sócio com máscara (só os 6 dígitos do meio). Ligamos quando o nome completo e esses 6 dígitos são iguais aos da lista.</li>
          <li><strong>Deputado federal:</strong> a API da Câmara publica o CPF de cada deputado; ligamos pelo CPF.</li>
          <li><strong>Senadores:</strong> a API do Senado não publica o CPF. Sem ele não dá para ter certeza de que é a mesma pessoa, então não ligamos nenhum senador a estas listas ({c.senadores} senadores ficaram de fora).</li>
          <li>O CPF nunca aparece inteiro neste site: mostramos só ***.456.789-**, como a Receita e o Portal.</li>
          <li>Ficam de fora processos ainda sem decisão, denúncias e investigações. Para os grandes casos, com investigação e delação, veja a seção <Link to="/corrupcao">Corrupção</Link>.</li>
        </ul>
      </section>
    </>
  );
}
