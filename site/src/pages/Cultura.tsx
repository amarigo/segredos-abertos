import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Barras, Colunas, Explain, Loading, OndeVer, useData } from "../components/ui";
import { cnpjFmt, dataBR, linkSeguro, numero, reais, reaisCurto } from "../data";
import { norm } from "./Home";

/* Shows e cultura em Minas, com quatro fontes oficiais:
   - PNCP: cada contratação de artista feita por prefeitura ou pelo estado (art. 74, II da Lei 14.133);
   - Transferegov: emendas Pix com show, festa ou evento, com o parlamentar que indicou o dinheiro;
   - SALIC (Ministério da Cultura): Lei Rouanet por região de Minas;
   - IBGE: população de cada cidade, para comparar o gasto por habitante. */

interface CidadeValor { cod: number | null; nome: string; regiao: string; populacao: number | null; valor: number; n: number; por_habitante: number | null }
interface Regiao { regiao: string; valor: number; n: number; cidades: number; populacao: number | null; por_habitante: number | null }
interface Contrato { ano: number; data: string; cidade: string; cod: number | null; orgao: string; objeto: string; valor: number; estimado: boolean;
  fornecedores: { nome: string; cnpj: string; valor: number }[]; url: string }
interface Artista { nome: string; cnpj: string; pessoa?: boolean; valor: number; n: number; cidades: string[] }
interface PlanoPix { ano: number; cidade: string; cod: number | null; regiao: string; populacao: number | null; parlamentar: string; politico: string | null;
  partido: string; emenda: string; plano: string; objeto: string; area: string; valor: number; gasto: number; palavras: string[];
  pagamentos_artistas: { data: string; nome: string; cnpj: string; descricao: string; valor: number }[] }
interface Parlamentar { nome: string; politico: string | null; partido: string; valor: number; gasto: number; n: number; cidades: string[] }
interface Cultura {
  atualizado: string;
  populacao: { fonte: string; api: string; ano: string; cidades: number } | null;
  contratos: { fonte: string; api: string; completo: boolean; total: number; n: number; sem_fornecedor: number; anos: number[];
    por_ano: { ano: number; valor: number; n: number }[]; cidades: CidadeValor[]; artistas: Artista[]; maiores: Contrato[] } | null;
  pix: { fonte: string; consulta: string; anos: number[]; completo: boolean; total: number; gasto: number; n: number;
    parlamentares: Parlamentar[]; artistas: Artista[]; planos: PlanoPix[] } | null;
  rouanet: { fonte: string; api: string; completo: boolean;
    incentivadores: { total: number; n: number; n_pessoas: number; pessoas: number; regioes: Regiao[]; cidades: CidadeValor[];
      empresas: { nome: string; cnpj: string; cidade: string; valor: number }[] };
    projetos: { total: number; n: number; regioes: Regiao[]; cidades: CidadeValor[]; por_ano: { ano: number; valor: number; n: number }[];
      maiores: { pronac: string; nome: string; proponente: string; cidade: string; ano: number | null; area: string; segmento: string; valor: number; url: string }[] };
  } | null;
}

const porHab = (v: number | null) => (v == null ? "" : `${reais(v, true)} por habitante`);
const pop = (p: number | null) => (p ? `${numero(p)} habitantes` : "população não informada");

export default function CulturaPage() {
  const { data, error } = useData<Cultura>("estado/cultura.json");
  if (!data) return <Loading error={error} />;
  const c = data.contratos, p = data.pix, r = data.rouanet;
  return (
    <>
      <section>
        <span className="eyebrow">Minas Gerais</span>
        <h1>Shows e cultura</h1>
        <Explain>Quanto as prefeituras de Minas gastam contratando artistas para shows e festas, quem recebeu, que deputado ou senador mandou o dinheiro e quanto imposto deixou de ser pago em cada região por causa da Lei Rouanet. Ao lado de cada cidade mostramos quantas pessoas moram nela, para comparar o gasto por habitante.</Explain>
        <div className="grid">
          <div className="card stat"><span className="label">Contratação de artistas</span><span className="value">{c ? reaisCurto(c.total) : "—"}</span>
            <span className="hint">{c ? `${numero(c.n)} contratações publicadas por prefeituras e pelo estado desde ${c.anos[0] || 2024}` : "fonte fora do ar nesta atualização"}</span></div>
          <div className="card stat"><span className="label">Emendas Pix com show ou evento</span><span className="value">{p ? reaisCurto(p.total) : "—"}</span>
            <span className="hint">{p ? `${numero(p.n)} planos de ${numero(p.parlamentares.length)} parlamentares` : "sem dados nesta atualização"}</span></div>
          <div className="card stat"><span className="label">Lei Rouanet: imposto destinado por quem é de Minas</span><span className="value">{r ? reaisCurto(r.incentivadores.total) : "—"}</span>
            <span className="hint">{r ? "valor acumulado desde o início do programa" : "fonte fora do ar nesta atualização"}</span></div>
        </div>
        <p className="muted small">Atualizado em {dataBR(data.atualizado)}.{data.populacao ? ` População: estimativa do IBGE de ${data.populacao.ano}.` : " A população do IBGE não pôde ser baixada nesta atualização."}</p>
      </section>
      <Contratos c={c} />
      <Pix p={p} />
      <Rouanet r={r} />
      <section>
        <h2>De onde vêm os números</h2>
        <ul className="small">
          <li><strong>Contratação de artistas:</strong> Portal Nacional de Contratações Públicas (PNCP), onde todo órgão público é obrigado a publicar as compras. Entram só as contratações que a própria prefeitura ou o estado publicou com base no art. 74, inciso II, da Lei 14.133/2021 ("contratação de profissional do setor artístico"). O valor é o homologado; quando ainda não há, o estimado (marcado com *). Prefeitura que não publica no PNCP não aparece aqui.</li>
          <li><strong>Emendas Pix:</strong> planos de ação do Transferegov. Nós separamos os planos de prefeituras de Minas cujo texto oficial fala de show, cachê, carnaval, festa, rodeio, festival ou evento cultural; as palavras encontradas aparecem em cada plano. O valor é o do plano inteiro, que pode incluir outras coisas além do evento.</li>
          <li><strong>Lei Rouanet:</strong> API do SALIC (Ministério da Cultura). Quem patrocina um projeto cultural desconta o valor do imposto de renda: 100% nos projetos do art. 18 e de 30% a 80% nos do art. 26. Por isso o imposto que deixou de ser recolhido é de até o valor mostrado. Pessoas físicas entram só na soma, sem nome.</li>
          <li><strong>População:</strong> estimativa da população do IBGE (tabela 6579), e as regiões são as regiões geográficas intermediárias do IBGE.</li>
        </ul>
        <OndeVer links={[
          ...(c ? [{ nome: "Contratações no PNCP", url: c.fonte, explica: "busca de inexigibilidades de Minas" }] : []),
          ...(p ? [{ nome: "Emendas Pix no Transferegov", url: p.consulta, explica: "plano de ação de cada emenda" }] : []),
          ...(r ? [{ nome: "Lei Rouanet (dados abertos do Ministério da Cultura)", url: r.fonte }] : []),
          ...(data.populacao ? [{ nome: "Estimativas de população (IBGE)", url: data.populacao.fonte }] : []),
        ]} />
      </section>
    </>
  );
}

function Contratos({ c }: { c: Cultura["contratos"] }) {
  const anos = c?.anos || [];
  const [ano, setAno] = useState(0);
  const [busca, setBusca] = useState("");
  const a = anos.includes(ano) ? ano : anos[anos.length - 1] || 0;
  const { data: lista } = useData<{ lista: Contrato[] }>(a ? `estado/cultura/contratos-${a}.json` : null);
  const filtrados = useMemo(() => (lista?.lista || []).filter((x) => !busca
    || norm(`${x.cidade} ${x.objeto} ${x.orgao} ${x.fornecedores.map((f) => f.nome).join(" ")}`).includes(norm(busca))), [lista, busca]);
  if (!c) return <section><h2>Contratação de artistas</h2><div className="empty">O Portal Nacional de Contratações Públicas (PNCP) não respondeu e ainda não temos uma leitura guardada. Veja direto no <a href="https://pncp.gov.br/app/editais?q=&status=todos&ufs=MG&modalidades=9" target="_blank" rel="noreferrer">PNCP ↗</a>.</div></section>;
  return (
    <section>
      <h2>Contratação de artistas pelas prefeituras</h2>
      <Explain>Para contratar um artista, a prefeitura não precisa fazer licitação: a lei permite contratar direto, desde que o artista seja conhecido pelo público. Cada contratação assim tem de ser publicada. Aqui estão todas as de Minas, com o evento, a cidade, o valor e quem recebeu.</Explain>
      {!c.completo && <p className="alert small">A leitura do PNCP ainda está em andamento; a lista pode crescer na próxima atualização.</p>}
      {c.por_ano.length > 0 && <Colunas rotulo="Contratação de artistas por ano" partes={[{ nome: "Gasto com artistas", cor: "var(--s1)" }]}
        itens={c.por_ano.map((x) => ({ label: `${x.ano}`, valores: [x.valor] }))} />}
      <div className="grid grid-2">
        <div>
          <h3>Cidades que mais gastaram</h3>
          <Barras itens={c.cidades.slice(0, 12).map((x) => ({ label: x.nome, valor: x.valor, cor: "var(--s1)",
            nota: [`${x.n} contratações`, pop(x.populacao), porHab(x.por_habitante)].filter(Boolean).join(" · ") }))} />
        </div>
        <div>
          <h3>Artistas que mais receberam</h3>
          {c.artistas.length ? <Barras itens={c.artistas.slice(0, 12).map((x) => ({ label: x.nome, valor: x.valor, cor: "var(--s3)",
            nota: `${x.n} contratações em ${x.cidades.length} cidades${x.cnpj ? ` · CNPJ ${cnpjFmt(x.cnpj)}` : ""}` }))} />
            : <p className="muted small">As prefeituras ainda não publicaram o resultado (quem recebeu) dessas contratações.</p>}
          {c.sem_fornecedor > 0 && <p className="muted small">{numero(c.sem_fornecedor)} contratações ainda sem o resultado publicado: o valor conta no total, mas o artista não aparece.</p>}
        </div>
      </div>
      <Abrir titulo={<>Cidades com o gasto por habitante ({numero(c.cidades.length)} cidades)</>}>
        <div className="table-wrap"><table>
          <thead><tr><th>Cidade</th><th>Região</th><th className="r">Habitantes</th><th className="r">Gasto com artistas</th><th className="r">Por habitante</th></tr></thead>
          <tbody>{c.cidades.map((x) => (
            <tr key={`${x.cod}-${x.nome}`}><td>{x.nome}</td><td>{x.regiao}</td><td className="r num">{x.populacao ? numero(x.populacao) : "—"}</td>
              <td className="r num">{reais(x.valor)}</td><td className="r num">{x.por_habitante == null ? "—" : reais(x.por_habitante, true)}</td></tr>
          ))}</tbody>
        </table></div>
      </Abrir>
      <h3>Cada contratação</h3>
      <div className="search">
        <label className="ano-sel"><span className="muted small">Ano</span>
          <select id="ano-cultura" value={a} onChange={(e) => setAno(Number(e.target.value))}>{anos.map((x) => <option key={x} value={x}>{x}</option>)}</select></label>
        <input id="busca-cultura" aria-label="Cidade, evento ou artista" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Cidade, evento ou artista" />
      </div>
      {!lista ? <Loading /> : (
        <div className="table-wrap"><table>
          <thead><tr><th>Data</th><th>Cidade</th><th>Evento e artista</th><th className="r">Valor</th></tr></thead>
          <tbody>{filtrados.slice(0, 200).map((x, k) => (
            <tr key={k}>
              <td className="num">{dataBR(x.data)}</td>
              <td>{x.cidade}</td>
              <td>{x.objeto}
                {x.fornecedores.length > 0 && <div className="muted small">Recebeu: {x.fornecedores.map((f) => f.cnpj ? `${f.nome} (CNPJ ${cnpjFmt(f.cnpj)})` : f.nome).join("; ")}</div>}
                {linkSeguro(x.url) && <div className="small"><a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">Ver no PNCP ↗</a></div>}</td>
              <td className="r num">{reais(x.valor)}{x.estimado ? "*" : ""}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      {lista && filtrados.length > 200 && <p className="muted small">Mostrando as 200 primeiras de {numero(filtrados.length)}. Use a busca para achar uma cidade ou um artista.</p>}
      {lista && !filtrados.length && <div className="empty">Nenhuma contratação encontrada.</div>}
    </section>
  );
}

function Pix({ p }: { p: Cultura["pix"] }) {
  const [quem, setQuem] = useState("");
  if (!p) return <section><h2>Quem indicou o dinheiro</h2><div className="empty">Os planos das emendas Pix ainda não foram lidos do Transferegov nesta atualização.</div></section>;
  const planos = p.planos.filter((x) => !quem || x.parlamentar === quem);
  if (!p.planos.length) return <section><h2>Quem indicou o dinheiro: emendas Pix para shows e festas</h2><div className="empty">Nenhum plano de emenda Pix para cidades de Minas fala de show, festa ou evento nos anos lidos ({p.anos.join(", ")}). Veja todos no <a href={linkSeguro(p.consulta)} target="_blank" rel="noreferrer">Transferegov ↗</a>.</div></section>;
  return (
    <section>
      <h2>Quem indicou o dinheiro: emendas Pix para shows e festas</h2>
      <Explain>Na emenda Pix, o deputado ou senador manda dinheiro direto para o caixa da prefeitura, que depois diz no Transferegov o que vai fazer com ele. Separamos os planos de cidades de Minas que falam de show, festa, carnaval, rodeio ou festival.</Explain>
      {!p.completo && <p className="alert small">A leitura do Transferegov ainda não terminou; alguns pagamentos podem faltar.</p>}
      <div className="grid grid-2">
        <div>
          <h3>Parlamentares que mais mandaram dinheiro para eventos</h3>
          <Barras itens={p.parlamentares.slice(0, 12).map((x) => ({ label: <button className="link" onClick={() => setQuem(quem === x.nome ? "" : x.nome)}>{x.nome}</button>,
            nome: x.nome, valor: x.valor, cor: "var(--s2)", nota: `${x.n} planos em ${x.cidades.length} cidades` }))} />
        </div>
        <div>
          <h3>Quem mais recebeu como artista</h3>
          {p.artistas.length ? <Barras itens={p.artistas.slice(0, 12).map((x) => ({ label: x.nome, valor: x.valor, cor: "var(--s3)", nota: `${x.n} pagamentos` }))} />
            : <p className="muted small">As prefeituras ainda não informaram pagamentos a artistas nesses planos.</p>}
          <p className="muted small">Conta só o pagamento cuja descrição fala de cachê, show ou apresentação artística; aluguel de palco, som e estrutura fica de fora.</p>
        </div>
      </div>
      <h3>{quem ? `Planos de ${quem}` : "Todos os planos"} ({numero(planos.length)})</h3>
      {quem && <p><button className="link" onClick={() => setQuem("")}>Ver de todos os parlamentares</button></p>}
      {planos.slice(0, 100).map((x, k) => (
        <Abrir key={`${x.emenda}-${k}`} titulo={<>{x.ano} · {x.cidade} · {x.parlamentar} · <span className="num">{reaisCurto(x.valor)}</span></>}>
          <p>{x.objeto || "Plano sem descrição"}</p>
          <div className="kv small" style={{ maxWidth: 520 }}>
            <span>Quem indicou</span><span>{x.politico ? <Link to={`/p/${x.politico}`}>{x.parlamentar}</Link> : x.parlamentar}{x.partido ? ` (${x.partido})` : ""}</span>
            <span>Cidade</span><span>{x.cidade}{x.populacao ? ` · ${numero(x.populacao)} habitantes` : ""}</span>
            <span>Valor do plano</span><span className="num">{reais(x.valor)}</span>
            <span>Já pago pela prefeitura</span><span className="num">{reais(x.gasto)}</span>
            {x.emenda && <><span>Emenda</span><span className="num">{x.emenda}</span></>}
            <span>Palavras que puseram na lista</span><span>{x.palavras.join(", ")}</span>
          </div>
          {x.pagamentos_artistas.length > 0 && <>
            <p className="small"><strong>Pagamentos a artistas:</strong></p>
            <ul className="small">{x.pagamentos_artistas.map((g, i) => (
              <li key={i}>{dataBR(g.data)} · {g.nome}{g.cnpj ? ` (CNPJ ${cnpjFmt(g.cnpj)})` : ""} · <span className="num">{reais(g.valor, true)}</span>{g.descricao ? ` · ${g.descricao}` : ""}</li>
            ))}</ul>
          </>}
          <p className="small"><a href={linkSeguro(p.consulta)} target="_blank" rel="noreferrer">Conferir no Transferegov ↗</a>{x.plano ? ` (plano ${x.plano})` : ""}</p>
        </Abrir>
      ))}
      {planos.length > 100 && <p className="muted small">Mostrando os 100 primeiros de {numero(planos.length)}. Clique num parlamentar para ver só os dele.</p>}
    </section>
  );
}

function Rouanet({ r }: { r: Cultura["rouanet"] }) {
  if (!r) return <section><h2>Lei Rouanet em Minas</h2><div className="empty">A API da Lei Rouanet (SALIC, do Ministério da Cultura) não respondeu e ainda não temos uma leitura guardada. Veja nos <a href="https://dados.cultura.gov.br/dataset/incentivos-da-lei-rouanet" target="_blank" rel="noreferrer">dados abertos do Ministério da Cultura ↗</a>.</div></section>;
  const inc = r.incentivadores, pr = r.projetos;
  return (
    <section>
      <h2>Lei Rouanet em Minas, por região</h2>
      <Explain>Pela Lei Rouanet, pessoas e empresas podem mandar parte do imposto de renda para um projeto cultural, em vez de pagar ao governo. É dinheiro que deixa de entrar nos cofres públicos. Aqui está quanto quem mora ou tem sede em cada região de Minas destinou assim, e quanto os projetos feitos em Minas captaram.</Explain>
      {!r.completo && <p className="alert small">A leitura do SALIC não terminou nesta atualização; os números são da última leitura completa.</p>}
      <div className="grid">
        <div className="card stat"><span className="label">Imposto destinado por pessoas e empresas de Minas</span><span className="value">{reaisCurto(inc.total)}</span>
          <span className="hint">{numero(inc.n)} incentivadores, dos quais {numero(inc.n_pessoas)} pessoas físicas ({reaisCurto(inc.pessoas)}). Deixou de ser recolhido até esse valor.</span></div>
        <div className="card stat"><span className="label">Captado por projetos feitos em Minas</span><span className="value">{reaisCurto(pr.total)}</span>
          <span className="hint">{numero(pr.n)} projetos</span></div>
      </div>
      <div className="grid grid-2">
        <div>
          <h3>Imposto que deixou de ser recolhido, por região</h3>
          <Barras itens={inc.regioes.map((x) => ({ label: x.regiao, valor: x.valor, cor: "var(--s2)",
            nota: [`${x.cidades} cidades`, x.populacao ? `${numero(x.populacao)} habitantes` : "", porHab(x.por_habitante)].filter(Boolean).join(" · ") }))} />
        </div>
        <div>
          <h3>Dinheiro captado pelos projetos, por região</h3>
          <Barras itens={pr.regioes.map((x) => ({ label: x.regiao, valor: x.valor, cor: "var(--s1)",
            nota: [`${x.n} projetos`, porHab(x.por_habitante)].filter(Boolean).join(" · ") }))} />
        </div>
      </div>
      {pr.por_ano.length > 1 && <Colunas rotulo="Captação dos projetos feitos em Minas, pelo ano do projeto" partes={[{ nome: "Captado", cor: "var(--s1)" }]}
        itens={pr.por_ano.map((x) => ({ label: `${x.ano}`, valores: [x.valor] }))} />}
      <Abrir titulo="Por cidade: imposto destinado e população">
        <div className="table-wrap"><table>
          <thead><tr><th>Cidade</th><th>Região</th><th className="r">Habitantes</th><th className="r">Imposto destinado</th><th className="r">Por habitante</th></tr></thead>
          <tbody>{inc.cidades.slice(0, 300).map((x) => (
            <tr key={`${x.cod}-${x.nome}`}><td>{x.nome}</td><td>{x.regiao}</td><td className="r num">{x.populacao ? numero(x.populacao) : "—"}</td>
              <td className="r num">{reais(x.valor)}</td><td className="r num">{x.por_habitante == null ? "—" : reais(x.por_habitante, true)}</td></tr>
          ))}</tbody>
        </table></div>
      </Abrir>
      <Abrir titulo="Empresas de Minas que mais destinaram">
        <div className="table-wrap"><table>
          <thead><tr><th>Empresa</th><th>Cidade</th><th className="r">Destinado</th></tr></thead>
          <tbody>{inc.empresas.map((x) => (
            <tr key={x.cnpj}><td>{x.nome}<div className="muted small">CNPJ {cnpjFmt(x.cnpj)}</div></td><td>{x.cidade}</td><td className="r num">{reais(x.valor)}</td></tr>
          ))}</tbody>
        </table></div>
      </Abrir>
      <Abrir titulo="Projetos feitos em Minas que mais captaram">
        <div className="table-wrap"><table>
          <thead><tr><th>Projeto</th><th>Cidade</th><th className="r">Captado</th></tr></thead>
          <tbody>{pr.maiores.map((x) => (
            <tr key={x.pronac}><td>{linkSeguro(x.url) ? <a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">{x.nome} ↗</a> : x.nome}
              <div className="muted small">{[x.proponente, x.area, x.ano ? `projeto de ${x.ano}` : ""].filter(Boolean).join(" · ")}</div></td>
              <td>{x.cidade}</td><td className="r num">{reais(x.valor)}</td></tr>
          ))}</tbody>
        </table></div>
      </Abrir>
    </section>
  );
}
