import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useData } from "../components/ui";
import { useState } from "react";
import { corPartido, dataBR, linkSeguro, numero, partidoComHoje, reais, type EquipeGoverno, type Governo, type PessoaEquipe } from "../data";

/** Governo de Minas: quem foi eleito governador e vice, e onde achar salários, viagens e pagamentos do governo */
export default function GovernoPage() {
  const { data: g, error } = useData<Governo>("estado/governo.json");
  if (!g) return <Loading error={error} />;
  const atual = g.eleicoes[0];
  const folha = g.equipe?.pessoas.find((p) => /^governador/i.test(p.cargo));
  return (
    <>
      <section>
        <span className="eyebrow">Minas Gerais</span>
        <h1>Governo do estado</h1>
        <p style={{ fontSize: "1.05rem", maxWidth: 760 }}>O governador administra o estado: polícia, escolas estaduais, hospitais da rede estadual, estradas e o orçamento de Minas. A Assembleia Legislativa faz as leis estaduais, aprova o orçamento e fiscaliza o governador.</p>
      </section>
      {atual ? (
        <section>
          <h2>Eleitos em {atual.eleicao}, para {atual.inicio} a {atual.fim}</h2>
          <div className="grid">
            <div className="card stat">
              <span className="label">Governador</span>
              <span className="value cidade-quem">{atual.governador.nome}</span>
              <span className="partido-tag"><i className="partido-cor" style={{ background: corPartido(atual.governador.partido_hoje) }} />{partidoComHoje(atual.governador.partido, atual.governador.partido_hoje)}</span>
              <span className="hint">{numero(atual.governador.votos)} votos ({atual.governador.pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% dos válidos){atual.turnos > 1 ? " no 2º turno" : ""}.</span>
            </div>
            <div className="card stat">
              <span className="label">Vice-governador</span>
              {atual.vice ? <>
                <span className="value cidade-quem">{atual.vice.nome}</span>
                <span className="partido-tag"><i className="partido-cor" style={{ background: corPartido(atual.vice.partido_hoje) }} />{partidoComHoje(atual.vice.partido, atual.vice.partido_hoje)}</span>
              </> : <span className="muted">Não encontrado na lista de candidatos do TSE</span>}
              <span className="hint">Assume se o governador deixar o cargo, por exemplo para disputar outra eleição.</span>
            </div>
          </div>
          <p className="muted small">Quem foi eleito, segundo o TSE. Se o governador renuncia (por exemplo, para disputar outra eleição), o vice assume.
            {folha && <> Na folha de pagamento de {mesAno(g.equipe!.mes_salarios)}, quem recebe como governador é <strong>{folha.nome}</strong>.</>}</p>
          <h3>Resultado da eleição de {atual.eleicao}</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Candidato</th><th className="r">Votos</th><th className="r">%</th></tr></thead>
              <tbody>{atual.candidatos.map((c) => (
                <tr key={c.nome}><td>{c.eleito ? <strong>{c.nome}</strong> : c.nome} <span className="muted small">{c.partido}</span>{c.eleito && <> <span className="chip txt-sim">Eleito</span></>}</td>
                  <td className="r num">{numero(c.votos)}</td><td className="r num">{c.pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</td></tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      ) : <div className="empty">O resultado da eleição para governador não pôde ser baixado do TSE nesta atualização.</div>}
      {g.eleicoes.slice(1).map((e) => (
        <section key={e.eleicao}>
          <h2>Eleitos em {e.eleicao}</h2>
          <p>Governador: <strong>{e.governador.nome}</strong> ({partidoComHoje(e.governador.partido, e.governador.partido_hoje)}){e.vice && <>; vice: <strong>{e.vice.nome}</strong> ({partidoComHoje(e.vice.partido, e.vice.partido_hoje)})</>}.</p>
        </section>
      ))}
      <Equipe e={g.equipe} />
      <section>
        <h2>O dinheiro do estado</h2>
        <Explain>Aqui no Minas Nossa já estão as <Link to="/emendas-estaduais">emendas dos deputados estaduais</Link> (para onde cada um mandou dinheiro do orçamento), os <Link to="/assembleia">gastos e a atuação de cada deputado estadual</Link> e, em cada <Link to="/cidades">cidade</Link>, o dinheiro que chegou e onde a prefeitura gasta. Os pagamentos do governo a cada empresa e os contratos ficam, por enquanto, nos sites oficiais abaixo.</Explain>
        <div className="grid">
          {g.links.filter((l) => linkSeguro(l.url)).map((l) => (
            <a key={l.url} className="card cidade-card" href={linkSeguro(l.url)} target="_blank" rel="noreferrer">
              <strong>{l.nome} ↗</strong><span className="small muted">{l.explica}</span>
            </a>
          ))}
        </div>
      </section>
      <p className="muted small">Fonte da eleição: <a href={linkSeguro(g.fonte_tse)} target="_blank" rel="noreferrer">dados abertos do TSE ↗</a>.</p>
    </>
  );
}

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const mesAno = (s: string | null) => { if (!s) return ""; const [a, m] = s.split("-"); return `${MESES[Number(m) - 1]} de ${a}`; };

/** Quem está no governo hoje (pela folha de pagamento), quanto ganha e quanto gastou em viagens */
function Equipe({ e }: { e?: EquipeGoverno | null }) {
  const [aberta, setAberta] = useState<string | null>(null);
  if (!e || (!e.tem_salarios && !e.tem_viagens)) {
    return <section><h2>Quem está no governo hoje</h2><div className="empty">Os salários e as viagens do governo não puderam ser baixados do Dados MG nesta atualização. Veja no <a href="https://www.transparencia.mg.gov.br/" target="_blank" rel="noreferrer">Portal da Transparência de MG ↗</a>.</div></section>;
  }
  const gov = e.pessoas.filter((p) => /^governador|^vice/i.test(p.cargo));
  const sec = e.pessoas.filter((p) => !/^governador|^vice/i.test(p.cargo));
  return (
    <section>
      <h2>Quem está no governo hoje</h2>
      <Explain>Pela folha de pagamento de {mesAno(e.mes_salarios)}: o governador e os secretários de estado, quanto cada um recebeu no mês e quanto o estado gastou com as viagens de cada um (diárias e passagens). "Bruto" é o salário antes dos descontos; "líquido" é o que cai na conta. "Jetons" é o que recebem por participar do conselho de empresas do estado, como Cemig e Copasa.</Explain>
      <div className="grid">{gov.map((p) => <CartaoPessoa key={p.nome} p={p} />)}</div>
      {sec.length > 0 && <>
        <h3>Secretários de estado e cargos do primeiro escalão</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Quem e onde</th><th className="r">Bruto</th><th className="r so-largo">Líquido</th><th className="r">Viagens no ano</th></tr></thead>
            <tbody>{sec.map((p) => {
              const v = p.viagens?.anos[0];
              return (
                <tr key={p.nome}>
                  <td><strong>{p.nome}</strong><div className="small muted">{p.cargo} · {p.orgao}</div>
                    {p.jetons > 0 && <div className="small">+ {reais(p.jetons)} de jetons</div>}
                    <div className="small so-celular">Líquido: <span className="num">{reais(p.liquido)}</span></div>
                    {p.viagens && p.viagens.ultimas.length > 0 && <button className="link small" onClick={() => setAberta(aberta === p.nome ? null : p.nome)}>{aberta === p.nome ? "Esconder viagens" : "Ver viagens"}</button>}
                    {aberta === p.nome && p.viagens && <Viagens v={p.viagens} />}</td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(p.bruto)}</td>
                  <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(p.liquido)}</td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{v ? <>{reais(v.diarias + v.passagens)}<div className="small muted">{v.viagens} viage{v.viagens === 1 ? "m" : "ns"} em {v.ano}</div></> : <span className="muted">—</span>}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      </>}
      <p className="muted small fonte-linha">Fontes: <a href={linkSeguro(e.fontes.salarios)} target="_blank" rel="noreferrer">remuneração dos servidores (Dados MG) ↗</a>, <a href={linkSeguro(e.fontes.viagens)} target="_blank" rel="noreferrer">viagens e diárias do SCDP (Dados MG) ↗</a>. Para procurar outro servidor: <a href={linkSeguro(e.fontes.portal_salarios)} target="_blank" rel="noreferrer">Portal da Transparência de MG ↗</a>.</p>
    </section>
  );
}

function CartaoPessoa({ p }: { p: PessoaEquipe }) {
  return (
    <div className="card">
      <span className="label small muted">{p.cargo}</span>
      <div className="value cidade-quem">{p.nome}</div>
      <p className="small" style={{ margin: "6px 0" }}>Salário em folha: <strong className="num">{reais(p.bruto)}</strong> bruto, <span className="num">{reais(p.liquido)}</span> líquido{p.jetons > 0 && <>, mais <span className="num">{reais(p.jetons)}</span> de jetons</>}.</p>
      {p.viagens ? <Viagens v={p.viagens} /> : <p className="small muted">Nenhuma viagem registrada no sistema de viagens do estado.</p>}
    </div>
  );
}

function Viagens({ v }: { v: NonNullable<PessoaEquipe["viagens"]> }) {
  return (
    <div className="small">
      {v.anos.length > 0 && <Barras itens={v.anos.map((a) => ({ label: `${a.ano}`, valor: a.diarias + a.passagens, cor: "var(--s2)",
        nota: `${a.viagens} viage${a.viagens === 1 ? "m" : "ns"}: ${reais(a.diarias)} em diárias e ${reais(a.passagens)} em passagens` }))} />}
      {v.destinos.length > 0 && <p className="muted">Destinos mais comuns: {v.destinos.map((d) => d.nome).join(", ")}.</p>}
      {v.ultimas.length > 0 && <ul className="lista-viagens">{v.ultimas.slice(0, 6).map((u, i) => (
        <li key={i}><span className="num">{dataBR(u.inicio)}</span>: {u.destinos.join(", ") || "destino não informado"}{u.valor > 0 && <> · <span className="num">{reais(u.valor)}</span></>}{u.motivo && <div className="muted">{u.motivo}</div>}</li>
      ))}</ul>}
    </div>
  );
}
