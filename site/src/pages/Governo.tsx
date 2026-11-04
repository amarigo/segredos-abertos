import { Link } from "react-router-dom";
import { Abrir, Barras, Colunas, Explain, Loading, OndeVer, useData } from "../components/ui";
import { Fragment, useState } from "react";
import { FotoPerfil } from "../components/Foto";
import { corPartido, dataBR, linkSeguro, numero, partidoComHoje, reais, type EquipeGoverno, type Governo, type PessoaEquipe, type ViagensDetalhe } from "../data";

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
              <FotoPerfil url={atual.governador.foto} nome={atual.governador.nome} />
              <span className="value cidade-quem">{atual.governador.nome}</span>
              <span className="partido-tag"><i className="partido-cor" style={{ background: corPartido(atual.governador.partido_hoje) }} />{partidoComHoje(atual.governador.partido, atual.governador.partido_hoje)}</span>
              <span className="hint">{numero(atual.governador.votos)} votos ({atual.governador.pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% dos válidos){atual.turnos > 1 ? " no 2º turno" : ""}.</span>
            </div>
            <div className="card stat">
              <span className="label">Vice-governador</span>
              {atual.vice ? <>
                <FotoPerfil url={atual.vice.foto} nome={atual.vice.nome} />
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
  const [todosSal, setTodosSal] = useState(false);
  const [todosVia, setTodosVia] = useState(false);
  if (!e || (!e.tem_salarios && !e.tem_viagens)) {
    return <section><h2>Quem está no governo hoje</h2><div className="empty">Os salários e as viagens do governo não puderam ser baixados do Dados MG nesta atualização. Veja no <a href="https://www.transparencia.mg.gov.br/" target="_blank" rel="noreferrer">Portal da Transparência de MG ↗</a>.</div></section>;
  }
  const gov = e.pessoas.filter((p) => /^governador|^vice/i.test(p.cargo));
  const sec = e.pessoas.filter((p) => !/^governador|^vice/i.test(p.cargo));
  // Ano mais recente com viagem de alguém da equipe: é o que o gráfico de viagens compara
  const anoVia = Math.max(0, ...e.pessoas.flatMap((p) => p.viagens?.anos.map((a) => a.ano) || []));
  const porSalario = e.pessoas.filter((p) => p.bruto > 0).sort((a, b) => b.bruto + b.jetons - (a.bruto + a.jetons));
  const gastoVia = (p: PessoaEquipe) => { const a = p.viagens?.anos.find((x) => x.ano === anoVia); return a ? a.diarias + a.passagens : 0; };
  const porViagem = e.pessoas.filter((p) => gastoVia(p) > 0).sort((a, b) => gastoVia(b) - gastoVia(a));
  return (
    <section>
      <h2>Quem está no governo hoje</h2>
      <Explain>Pela folha de pagamento de {mesAno(e.mes_salarios)}: o governador e os secretários de estado, quanto cada um recebeu no mês e quanto o estado gastou com as viagens de cada um (diárias e passagens). "Bruto" é o salário antes dos descontos; "líquido" é o que cai na conta. "Jetons" é o que recebem por participar do conselho de empresas do estado, como Cemig e Copasa. Clique em cada ano para abrir a lista de viagens, uma por uma.</Explain>
      {gov.map((p) => <PessoaDetalhe key={p.nome} p={p} destaque />)}
      {(porSalario.length > 1 || porViagem.length > 1) && <div className="grid grid-2">
        {porSalario.length > 1 && <div>
          <h3>Quanto cada um recebeu em {mesAno(e.mes_salarios)}</h3>
          <Barras itens={porSalario.slice(0, todosSal ? undefined : 10).map((p) => ({ label: p.nome, valor: p.bruto + p.jetons, cor: "var(--s1)",
            nota: `${p.cargo}${p.jetons > 0 ? ` · inclui ${reais(p.jetons)} de jetons` : ""}` }))} />
          {porSalario.length > 10 && <button className="link small" onClick={() => setTodosSal(!todosSal)}>{todosSal ? "Mostrar menos" : `Mostrar os ${porSalario.length}`}</button>}
          <p className="muted small">Salário bruto mais jetons, no mês.</p>
        </div>}
        {porViagem.length > 1 && <div>
          <h3>Quem mais gastou com viagens em {anoVia}</h3>
          <Barras itens={porViagem.slice(0, todosVia ? undefined : 10).map((p) => {
            const a = p.viagens!.anos.find((x) => x.ano === anoVia)!;
            return { label: p.nome, valor: a.diarias + a.passagens, cor: "var(--s2)", nota: `${a.viagens} viage${a.viagens === 1 ? "m" : "ns"} · ${p.cargo}` };
          })} />
          {porViagem.length > 10 && <button className="link small" onClick={() => setTodosVia(!todosVia)}>{todosVia ? "Mostrar menos" : `Mostrar os ${porViagem.length}`}</button>}
          <p className="muted small">Diárias mais passagens pagas pelo estado.</p>
        </div>}
      </div>}
      {sec.length > 0 && <>
        <h3>Secretários de estado e cargos do primeiro escalão</h3>
        <p className="muted small">Clique em "Abrir detalhes" para ver o salário completo, o gasto com viagens ano a ano e cada viagem.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Quem e onde</th><th className="r">Bruto</th><th className="r so-largo">Líquido</th><th className="r">Viagens no ano</th></tr></thead>
            <tbody>{sec.map((p) => {
              const v = p.viagens?.anos[0];
              return (
                <Fragment key={p.nome}>
                  <tr>
                    <td><strong>{p.nome}</strong><div className="small muted">{p.cargo} · {p.orgao}</div>
                      {p.jetons > 0 && <div className="small">+ {reais(p.jetons)} de jetons</div>}
                      <div className="small so-celular">Líquido: <span className="num">{reais(p.liquido)}</span></div>
                      <button className="link small" aria-expanded={aberta === p.nome} onClick={() => setAberta(aberta === p.nome ? null : p.nome)}>{aberta === p.nome ? "Fechar detalhes" : "Abrir detalhes"}</button></td>
                    <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(p.bruto)}</td>
                    <td className="r num so-largo" style={{ whiteSpace: "nowrap" }}>{reais(p.liquido)}</td>
                    <td className="r num" style={{ whiteSpace: "nowrap" }}>{v ? <>{reais(v.diarias + v.passagens)}<div className="small muted">{v.viagens} viage{v.viagens === 1 ? "m" : "ns"} em {v.ano}</div></> : <span className="muted">—</span>}</td>
                  </tr>
                  {aberta === p.nome && <tr className="linha-aberta"><td colSpan={4}><PessoaDetalhe p={p} /></td></tr>}
                </Fragment>
              );
            })}</tbody>
          </table>
        </div>
      </>}
      <OndeVer links={[
        { nome: "Viagens e diárias do governo no Portal da Transparência de MG", url: e.fontes.portal_viagens, explica: "procure pelo nome de quem viajou" },
        { nome: "Salário de cada servidor no Portal da Transparência de MG", url: e.fontes.portal_salarios, explica: "procure pelo nome" },
        { nome: "Arquivo completo de viagens (SCDP) no Dados MG", url: e.fontes.viagens, explica: "todas as viagens do estado, para baixar" },
        { nome: "Arquivo completo de salários no Dados MG", url: e.fontes.salarios, explica: "um arquivo por mês, todos os servidores" },
      ]} />
    </section>
  );
}

/** Tudo de uma pessoa da equipe: salário aberto, viagens por ano (gráfico) e a lista de viagens de cada ano */
function PessoaDetalhe({ p, destaque = false }: { p: PessoaEquipe; destaque?: boolean }) {
  const v = p.viagens;
  const corpo = (
    <>
      <p className="small" style={{ margin: "6px 0" }}>Salário em folha: <strong className="num">{reais(p.bruto)}</strong> bruto, <span className="num">{reais(p.liquido)}</span> líquido{p.jetons > 0 && <>, mais <span className="num">{reais(p.jetons)}</span> de jetons</>}.</p>
      <Abrir titulo="Ver o salário parte por parte">
        <div className="kv small" style={{ maxWidth: 420 }}>
          <span>Remuneração bruta</span><span className="num">{reais(p.bruto, true)}</span>
          {p.ferias_13 > 0 && <><span>Férias e 13º no mês</span><span className="num">{reais(p.ferias_13, true)}</span></>}
          {p.eventual > 0 && <><span>Pagamentos eventuais</span><span className="num">{reais(p.eventual, true)}</span></>}
          {p.jetons > 0 && <><span>Jetons (conselhos de estatais)</span><span className="num">{reais(p.jetons, true)}</span></>}
          {p.abate_teto > 0 && <><span>Corte pelo teto salarial</span><span className="num">− {reais(p.abate_teto, true)}</span></>}
          <span>Imposto de renda e previdência</span><span className="num">− {reais(p.descontos, true)}</span>
          <strong>Líquido</strong><strong className="num">{reais(p.liquido, true)}</strong>
        </div>
      </Abrir>
      {v && v.anos.length > 0 ? <>
        <h4 style={{ margin: "14px 0 4px" }}>Viagens pagas pelo estado, por ano</h4>
        <Colunas rotulo={`Gasto com viagens de ${p.nome} por ano`} partes={[{ nome: "Diárias", cor: "var(--s2)" }, { nome: "Passagens", cor: "var(--s1)" }]}
          itens={v.anos.slice().reverse().map((a) => ({ label: `${a.ano}`, valores: [a.diarias, a.passagens] }))} />
        {v.destinos.length > 0 && <p className="small muted">Destinos mais comuns: {v.destinos.map((d) => `${d.nome} (${d.vezes}×)`).join(", ")}.</p>}
        {v.anos.map((a) => (
          <Abrir key={a.ano} titulo={<>As {a.viagens} viage{a.viagens === 1 ? "m" : "ns"} de {a.ano} · <span className="num">{reais(a.diarias + a.passagens)}</span></>}>
            <ListaViagens v={v} ano={a.ano} />
          </Abrir>
        ))}
      </> : <p className="small muted">Nenhuma viagem registrada no sistema de viagens do estado.</p>}
    </>
  );
  if (!destaque) return <div className="pessoa-detalhe">{corpo}</div>;
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <span className="label small muted">{p.cargo}</span>
      <div className="value cidade-quem">{p.nome}</div>
      {corpo}
    </div>
  );
}

/** Cada viagem de um ano. A lista completa fica num arquivo por pessoa, lido só quando alguém abre o ano. */
function ListaViagens({ v, ano }: { v: NonNullable<PessoaEquipe["viagens"]>; ano: number }) {
  const { data, error } = useData<ViagensDetalhe>(v.id && /^[a-z0-9-]+$/.test(v.id) ? `estado/viagens/${v.id}.json` : null);
  if (v.id && !data && !error) return <Loading />;
  const todas = data?.viagens || v.ultimas;
  const lista = todas.filter((u) => u.inicio.startsWith(`${ano}`));
  const incompleta = !data && v.ultimas.length < (v.n_todas || 0);
  if (!lista.length) return <p className="small muted">A lista de viagens de {ano} não está disponível nesta atualização. Veja no <a href="https://www.transparencia.mg.gov.br/despesa-estado/viagens" target="_blank" rel="noreferrer">Portal da Transparência de MG ↗</a>.</p>;
  return (
    <>
      {incompleta && <p className="small muted">Mostrando só as viagens mais recentes.</p>}
      <div className="table-wrap">
        <table className="small">
          <thead><tr><th>Quando</th><th>Para onde e por quê</th><th className="r so-largo">Diárias</th><th className="r so-largo">Passagens</th><th className="r">Total</th></tr></thead>
          <tbody>{lista.map((u, i) => (
            <tr key={i}>
              <td className="num" style={{ whiteSpace: "nowrap" }}>{dataBR(u.inicio)}{u.fim && u.fim !== u.inicio && <div className="muted">até {dataBR(u.fim)}</div>}</td>
              <td>{u.destinos.join(", ") || "destino não informado"}{u.motivo && <div className="muted">{u.motivo}</div>}</td>
              <td className="r num so-largo">{u.diarias != null ? reais(u.diarias) : "—"}</td>
              <td className="r num so-largo">{u.passagens != null ? reais(u.passagens) : "—"}</td>
              <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(u.valor)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
