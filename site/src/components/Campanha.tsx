import { useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Barras, Explain, Loading, useData } from "./ui";
import {
  cnpjFmt, dataBR, linkSeguro, reais,
  type Campanha, type CampanhaPolitico as Dados, type DoadorCampanha, type Ligacao, type Politico, type TipoDoador,
} from "../data";

/* Aba "Campanha" do perfil: quem pagou a campanha, a quem a campanha pagou e onde esse dinheiro encontra o do mandato.
   Os dados vêm de p/campanha/{id}.json (etl/sa_etl/campanha.py), a partir da prestação de contas do TSE. */

const TIPO_DOADOR: Record<TipoDoador, string> = {
  pessoa: "Pessoa", empresa: "Empresa", partido: "Partido", candidato: "Outro candidato", proprio: "Recursos próprios",
  coletivo: "Vaquinha", nao_identificado: "Origem não identificada", rendimento: "Rendimento", outro: "Outro",
};
const CORRIGIR = "https://github.com/amarigo/segredos-abertos/issues/new";
const AVISO_CHAVE = "A ligação usa o nome completo e os 6 dígitos do meio do CPF, os únicos que a Receita mostra. Os dois precisam ser iguais. Ainda assim, é coincidência de cadastro: não indica irregularidade nem troca de favores.";

function docFmt(doc: string): string {
  return /^\d{14}$/.test(doc) ? cnpjFmt(doc) : doc;
}

function Empresa({ cnpj, nome }: { cnpj: string; nome: string }) {
  return <><Link to={`/e/${cnpj}`}>{nome || cnpjFmt(cnpj)}</Link> <span className="muted small mono">{cnpjFmt(cnpj)}</span></>;
}

function NoMandato({ l }: { l: Ligacao }) {
  const partes = [];
  if (l.cota) partes.push(<span key="c">recebeu <strong>{reais(l.cota)}</strong> da cota deste parlamentar{l.cota_de ? <> ({dataBR(l.cota_de)} a {dataBR(l.cota_ate || "")})</> : null}</span>);
  if (l.emendas) partes.push(<span key="e">recebeu <strong>{reais(l.emendas)}</strong> de emendas deste parlamentar</span>);
  return <>{partes.map((p, i) => <span key={i}>{i > 0 ? " e " : ""}{p}</span>)}</>;
}

/** Cada ligação em fatos curtos, um por linha, na ordem do tempo, sem adjetivos. */
function Fatos({ l, c }: { l: Ligacao; c?: Campanha }) {
  const tse = c ? <a href={linkSeguro(c.fonte)} target="_blank" rel="noreferrer">TSE ↗</a> : null;
  if (l.tipo === "fornecedor") return (
    <ol className="fatos">
      <li>Na campanha de {l.ano}, contratou <Empresa cnpj={l.empresa.cnpj} nome={l.empresa.nome} /> por <strong>{reais(l.campanha)}</strong>
        {l.servico ? <> ({l.servico.toLowerCase()})</> : null}. Fonte: {tse}</li>
      <li>No mandato, a mesma empresa <NoMandato l={l} />. Fonte: <Link to={`/e/${l.empresa.cnpj}`}>notas e pagamentos</Link></li>
    </ol>
  );
  if (l.tipo === "doador_socio") return (
    <ol className="fatos">
      <li>Na campanha de {l.ano}, <strong>{l.doador.nome}</strong> <span className="muted small mono">{l.doador.doc}</span> {l.via === "originario"
        ? <>deu <strong>{reais(l.doacao)}</strong> que chegou à campanha por partido, outro candidato ou vaquinha (doador originário)</>
        : <>doou <strong>{reais(l.doacao)}</strong></>}. Fonte: {tse}</li>
      <li>Na Receita, a pessoa com esse nome e esses dígitos do CPF é {l.papel === "dono_final" ? "dona, por meio de outra empresa," : (l.qualificacao || "sócia").toLowerCase()} de <Empresa cnpj={l.empresa.cnpj} nome={l.empresa.nome} />. Fonte: <Link to={`/e/${l.empresa.cnpj}`}>quadro de sócios</Link></li>
      <li>No mandato, essa empresa <NoMandato l={l} />.</li>
    </ol>
  );
  return (
    <ol className="fatos">
      <li>Na Receita, a pessoa com o nome civil e os dígitos do CPF deste parlamentar é {l.papel === "dono_final" ? "dona, por meio de outra empresa," : (l.qualificacao || "sócia").toLowerCase()} de <Empresa cnpj={l.empresa.cnpj} nome={l.empresa.nome} />. Fonte: <Link to={`/e/${l.empresa.cnpj}`}>quadro de sócios</Link></li>
      <li>No mandato, essa empresa <NoMandato l={l} />.</li>
    </ol>
  );
}

const TITULO: Record<Ligacao["tipo"], string> = {
  politico_socio: "O próprio parlamentar aparece como sócio",
  doador_socio: "Doador da campanha é sócio de empresa paga no mandato",
  fornecedor: "Fornecedora da campanha também foi paga no mandato",
};

function Ligacoes({ d }: { d: Dados }) {
  const campanhaDo = (ano?: number) => d.campanhas.find((c) => c.ano === ano);
  const raras = d.ligacoes.filter((l) => !l.comum);
  const comuns = d.ligacoes.filter((l) => l.comum);
  const card = (l: Ligacao, i: number) => (
    <div className="card ligacao" key={i} data-testid={`ligacao-${l.tipo}`}>
      <span className="label">{TITULO[l.tipo]}{l.ano ? ` · campanha de ${l.ano}` : ""}</span>
      <Fatos l={l} c={campanhaDo(l.ano)} />
      {l.tipo !== "fornecedor" && <p className="small muted">{AVISO_CHAVE}</p>}
    </div>
  );
  return (
    <section>
      <h2>Onde o dinheiro da campanha encontra o do mandato</h2>
      <Explain>Três cruzamentos, cada um com a fonte oficial: empresa contratada na campanha que depois recebeu da cota ou de emendas; doador da campanha que é sócio de uma empresa paga no mandato; e o próprio parlamentar como sócio de uma empresa paga no mandato. São fatos lado a lado. Nenhum deles, sozinho, mostra irregularidade.</Explain>
      {raras.length === 0 && comuns.length === 0 && <div className="empty">Nenhum cruzamento encontrado entre as contas de campanha e os gastos do mandato.</div>}
      {raras.map(card)}
      {comuns.length > 0 && (
        <Abrir titulo={<>Com empresas que atendem muitos parlamentares ({comuns.length})</>}>
          <p className="small muted">Correios, companhias aéreas, telefonia, redes sociais e postos de grandes redes recebem da cota de dezenas de parlamentares. Coincidir com elas diz pouco, por isso ficam aqui. Entre parênteses, quantos parlamentares pagaram a empresa pela cota.</p>
          <div className="table-wrap"><table>
            <thead><tr><th>Empresa</th><th>Como</th><th className="r">Campanha</th><th className="r">Mandato</th></tr></thead>
            <tbody>{comuns.map((l, i) => (
              <tr key={i}>
                <td><Empresa cnpj={l.empresa.cnpj} nome={l.empresa.nome} /> <span className="muted small">({l.n_parlamentares})</span></td>
                <td className="small">{l.tipo === "fornecedor" ? `Fornecedora em ${l.ano}` : l.tipo === "doador_socio" ? `${l.doador.nome} doou em ${l.ano}` : "Parlamentar sócio"}</td>
                <td className="r num">{l.tipo === "fornecedor" ? reais(l.campanha) : l.tipo === "doador_socio" ? reais(l.doacao) : "—"}</td>
                <td className="r num">{reais((l.cota || 0) + (l.emendas || 0))}</td>
              </tr>))}</tbody>
          </table></div>
        </Abrir>
      )}
      <p className="small muted">Viu um homônimo ou um erro? <a href={CORRIGIR} target="_blank" rel="noreferrer">Peça a correção no GitHub</a>, com o link desta página. A ligação é revista e, se for de outra pessoa, sai do site.</p>
    </section>
  );
}

function TabelaDoadores({ itens, total, mostrarTipo = true }: { itens: DoadorCampanha[]; total: number; mostrarTipo?: boolean }) {
  return (
    <div className="table-wrap"><table>
      <thead><tr><th>Quem</th>{mostrarTipo && <th>Tipo</th>}<th className="r">Valor</th></tr></thead>
      <tbody>{itens.map((x, i) => (
        <tr key={x.doc + x.nome + i}>
          <td>{/^\d{14}$/.test(x.doc) && x.tipo === "empresa" ? <Link to={`/e/${x.doc}`}>{x.nome}</Link> : x.nome}
            {x.doc && <div className="muted small mono">{docFmt(x.doc)}</div>}</td>
          {mostrarTipo && <td className="small">{TIPO_DOADOR[x.tipo] || x.tipo}</td>}
          <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.valor)}<div className="muted small">{total ? `${Math.round((x.valor / total) * 100)}%` : ""}</div></td>
        </tr>))}</tbody>
    </table></div>
  );
}

function UmaCampanha({ c }: { c: Campanha }) {
  const recente = c.ano >= new Date().getFullYear();
  return (
    <>
      <section className="grid">
        <div className="card stat"><span className="label">Recebeu na campanha de {c.ano}</span><span className="value">{reais(c.receitas.total)}</span>
          <span className="hint">{c.receitas.estimavel > 0 ? <>{reais(c.receitas.financeiro)} em dinheiro e {reais(c.receitas.estimavel)} em bens e serviços doados</> : "tudo em dinheiro"}</span></div>
        <div className="card stat"><span className="label">Contratou na campanha</span><span className="value">{reais(c.despesas.total)}</span>
          <span className="hint">{c.n_fornecedores.toLocaleString("pt-BR")} {c.n_fornecedores === 1 ? "fornecedor" : "fornecedores"} · valor contratado</span></div>
        <div className="card stat"><span className="label">Doadores</span><span className="value">{c.n_doadores.toLocaleString("pt-BR")}</span>
          <span className="hint">{c.cargo} · {c.uf} · {c.partido} · nº {c.numero}</span></div>
      </section>
      {recente && <div className="alert" role="note"><strong>Contas ainda abertas:</strong> as contas de {c.ano} ainda podem mudar com entregas atrasadas e retificações, e ainda não foram julgadas pela Justiça Eleitoral. Prestação {c.prestacao.toLowerCase()} de {dataBR(c.data_prestacao)}.</div>}
      <section>
        <h2>De onde veio o dinheiro</h2>
        <Barras rosca={{ titulo: `Origem do dinheiro da campanha de ${c.ano}`, total: c.receitas.total, paleta: true }}
          itens={c.receitas.por_origem.map(([k, v]) => ({ label: k, valor: v }))} />
        <p className="small muted">Fundo Especial (FEFC) e Fundo Partidário são dinheiro público repassado pelos partidos: {c.receitas.por_fonte.filter(([k]) => /FUNDO/i.test(k)).map(([k, v]) => `${k.toLowerCase()} ${reais(v)}`).join(", ") || "nenhum nesta campanha"}.</p>
      </section>
      <section>
        <div className="grid grid-2 lado-a-lado">
          <div>
            <h2>Maiores doadores</h2>
            <p className="muted small">{c.n_doadores > c.doadores.length ? `Os ${c.doadores.length} maiores de ${c.n_doadores.toLocaleString("pt-BR")}.` : "Todos os doadores."} O CPF aparece mascarado, como a Receita mostra.</p>
            <TabelaDoadores itens={c.doadores} total={c.receitas.total} />
          </div>
          <div>
            <h2>Quem a campanha contratou</h2>
            <p className="muted small">{c.n_fornecedores > c.fornecedores.length ? `Os ${c.fornecedores.length} maiores de ${c.n_fornecedores.toLocaleString("pt-BR")}.` : "Todos os fornecedores."} Empresas com página no site têm link.</p>
            <div className="table-wrap"><table>
              <thead><tr><th>Fornecedor</th><th className="r">Valor</th></tr></thead>
              <tbody>{c.fornecedores.map((f, i) => (
                <tr key={f.doc + f.nome + i}>
                  <td>{f.pagina ? <Link to={`/e/${f.doc}`}>{f.nome}</Link> : f.nome}
                    <div className="muted small">{f.doc && <span className="mono">{docFmt(f.doc)} · </span>}{f.tipo}</div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(f.valor)}</td>
                </tr>))}</tbody>
            </table></div>
          </div>
        </div>
      </section>
      {c.originarios.length > 0 && (
        <section>
          <Abrir titulo={<>Quem pagou o dinheiro que veio por partido, outro candidato ou vaquinha ({c.n_originarios.toLocaleString("pt-BR")})</>}>
            <p className="small muted">O TSE chama de doador originário: a pessoa ou empresa que deu o dinheiro antes de ele passar pelo partido, por outro candidato ou por uma vaquinha na internet.</p>
            <TabelaDoadores itens={c.originarios} total={c.receitas.total} mostrarTipo={false} />
          </Abrir>
        </section>
      )}
      <p className="small muted">Fonte: TSE, Prestação de contas de candidatos {c.ano} (<a href={linkSeguro(c.fonte)} target="_blank" rel="noreferrer">conjunto de dados</a> · <a href={linkSeguro(c.arquivo)} target="_blank" rel="noreferrer">arquivo</a>), gerado em {dataBR(c.gerado_em)}. Consulta da candidatura no <a href={linkSeguro(c.divulga)} target="_blank" rel="noreferrer">DivulgaCandContas</a>{c.cnpj_campanha ? <> (CNPJ da campanha <span className="mono">{cnpjFmt(c.cnpj_campanha)}</span>)</> : null}. Despesas pelo valor contratado.
        {c.achada_por === "nome" && " Candidatura achada pelo nome civil completo e pelo estado."}</p>
    </>
  );
}

export function CampanhaPolitico({ p }: { p: Politico }) {
  const { data: d, error } = useData<Dados>(`p/campanha/${p.id}.json`);
  const [sel, setSel] = useState<number | null>(null);
  if (error) return <div className="empty">Não achamos nas contas do TSE (2018, 2022 e 2026) uma candidatura de {p.nome}. Suplentes de senador, por exemplo, entram nas contas do titular da chapa.</div>;
  if (!d) return <Loading />;
  const c = d.campanhas.find((x) => x.ano === sel) || d.campanhas[0];
  return (
    <>
      <Ligacoes d={d} />
      {c && <>
        <h2>As contas de cada campanha</h2>
        {d.campanhas.length > 1 && <div className="tabs" role="tablist">
          {d.campanhas.map((x) => <button key={x.ano} role="tab" aria-selected={x.ano === c.ano} onClick={() => setSel(x.ano)}>{x.ano} · {x.cargo}</button>)}
        </div>}
        <UmaCampanha c={c} />
      </>}
    </>
  );
}
