import { useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useData } from "../components/ui";
import { linkSeguro, reais, reaisCurto, type EmendasEstado } from "../data";

/** Emendas estaduais: quanto os deputados estaduais indicaram do orçamento de Minas, para quais cidades */
export default function EmendasEstaduais() {
  const { data, error } = useData<EmendasEstado>("estado/emendas.json");
  const anos = Object.keys(data?.anos || {}).sort();
  const [sel, setSel] = useState("");
  const [todos, setTodos] = useState(false);
  if (!data) return <Loading error={error} />;
  const ano = anos.includes(sel) ? sel : anos[anos.length - 1];
  const a = data.anos[ano];
  if (!a) return <div className="empty">Sem dados de emendas estaduais.</div>;
  return (
    <>
      <section>
        <h1>Emendas estaduais</h1>
        <Explain>Todo ano, os deputados estaduais indicam para onde vai uma parte do orçamento de Minas: obras, equipamentos, hospitais, escolas, associações. O governo é obrigado a pagar boa parte dessas indicações. Aqui está quanto cada deputado indicou, para quais cidades, e quanto já foi pago.</Explain>
        <div className="row" style={{ gap: 8 }}>
          <label className="ano-sel"><span className="muted small">Ano do orçamento</span>
            <select id="ano-emendas" value={ano} onChange={(e) => setSel(e.target.value)}>{anos.slice().reverse().map((x) => <option key={x}>{x}</option>)}</select>
          </label>
        </div>
        <div className="grid">
          <div className="card stat"><span className="label">Indicado em {ano}</span><span className="value">{reaisCurto(a.indicado)}</span><span className="hint">{a.n.toLocaleString("pt-BR")} indicações para {a.n_municipios} municípios</span></div>
          <div className="card stat"><span className="label">Já pago</span><span className="value">{reaisCurto(a.pago)}</span><span className="hint">{a.indicado ? Math.round((a.pago / a.indicado) * 100) : 0}% do indicado</span></div>
        </div>
      </section>
      <section>
        <h2>Quem indicou mais</h2>
        <Barras itens={a.autores.slice(0, todos ? 100 : 15).map((x) => ({
          label: x.deputado ? <Link to={`/deputado-estadual/${x.deputado}?aba=emendas&ano=${ano}`}>{x.nome}</Link> : <span>{x.nome}</span>,
          nota: `${x.n} indicações · ${reais(x.pago)} pago`, valor: x.indicado, cor: "var(--s3)" }))} />
        {a.autores.length > 15 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${a.autores.length}`}</button>}
        <p className="muted small">Nomes sem link são de quem não está mais em exercício na Assembleia, ou de blocos e comissões.</p>
      </section>
      <section>
        <h2>Cidades que mais receberam indicações</h2>
        <Barras itens={a.municipios.map((m) => ({ label: m.nome, nota: `${m.n} indicações · ${reais(m.pago)} pago`, valor: m.indicado, cor: "var(--s1)" }))} />
        <p className="small">Veja também a aba Dinheiro das <Link to="/cidades">cidades acompanhadas</Link>, com cada indicação.</p>
      </section>
      <p className="muted small">Fonte: <a href={linkSeguro(data.fonte)} target="_blank" rel="noreferrer">emendas parlamentares na Assembleia de Minas (ALMG) ↗</a>.</p>
    </>
  );
}
