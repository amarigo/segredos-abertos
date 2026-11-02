import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Abrir, Barras, Colunas, Explain, Loading, OndeVer, useData } from "../components/ui";
import { cnpjFmt, reais, reaisCurto, type CidadeResumo, type ContasEnte, type DinheiroCidade, type IncentivosMG } from "../data";
import { norm } from "./Home";

/* O dinheiro de Minas em 3 cliques:
   1. escolher onde (o estado ou uma cidade);
   2. escolher o ano (e com qual ano comparar);
   3. abrir uma área (saúde, educação...) para ver o detalhe e o caminho até as notas.
   Tudo com as contas que o próprio governo e as prefeituras entregam ao Tesouro Nacional (SICONFI). */
export default function DinheiroMinas() {
  const [params, setParams] = useSearchParams();
  const { data: cidades } = useData<CidadeResumo[]>("cidades.json");
  const onde = params.get("onde") || "estado";
  const cidade = cidades?.find((c) => c.id === onde);
  const ir = (o: string) => setParams(o === "estado" ? {} : { onde: o }, { replace: true });
  return (
    <>
      <section>
        <span className="eyebrow">Minas Gerais</span>
        <h1>O dinheiro de Minas</h1>
        <Explain>O dinheiro público é o dinheiro dos impostos que todos nós pagamos. Aqui você vê, em três passos, quanto o governo de Minas e as prefeituras gastaram, em quê, e como isso mudou de um ano para outro. Também mostramos quanto as empresas de Minas deixaram de pagar de impostos por causa de benefícios do governo.</Explain>
        <ol className="passos" aria-label="Como usar esta página">
          <li><strong>Escolha onde:</strong> o estado ou uma cidade.</li>
          <li><strong>Escolha o ano</strong> e com qual ano comparar.</li>
          <li><strong>Abra uma área</strong> (saúde, educação...) para ver o detalhe e onde estão as notas.</li>
        </ol>
        <div className="tabs" role="tablist" aria-label="Onde">
          <button role="tab" aria-selected={onde === "estado"} onClick={() => ir("estado")}>Estado de Minas</button>
          {(cidades || []).map((c) => <button key={c.id} role="tab" aria-selected={onde === c.id} onClick={() => ir(c.id)}>{c.nome}</button>)}
        </div>
      </section>
      {onde === "estado" ? <ContasEstado /> : cidade ? <ContasCidade id={cidade.id} nome={cidade.nome} /> : cidades ? <div className="empty">Cidade não encontrada.</div> : <Loading />}
      {onde === "estado" && <Incentivos />}
      <Glossario />
    </>
  );
}

function ContasEstado() {
  const { data, error } = useData<{ contas: ContasEnte | null }>("estado/contas.json");
  if (!data) return <Loading error={error} />;
  return <Contas c={data.contas} quem="o governo de Minas" caminho={<CaminhoEstado />} />;
}

function ContasCidade({ id, nome }: { id: string; nome: string }) {
  const { data, error } = useData<DinheiroCidade>(`cidades/dinheiro/${id}.json`);
  if (!data) return <Loading error={error} />;
  return <Contas c={data.contas} quem={`a prefeitura de ${nome}`} caminho={<CaminhoCidade id={id} nome={nome} />} />;
}

const pct = (a: number, b: number) => (b ? ((a - b) / b) * 100 : null);
const pctTxt = (p: number | null) => (p == null ? "" : `${p > 0 ? "+" : ""}${p.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`);

/** Passos 2 e 3: o ano, a comparação e cada área aberta */
function Contas({ c, quem, caminho }: { c: ContasEnte | null; quem: string; caminho: React.ReactNode }) {
  const anos = c?.anos || [];
  const [anoSel, setAno] = useState(0);
  const [compSel, setComp] = useState(0);
  if (!c || !anos.length) return <div className="empty">As contas de {quem} não puderam ser baixadas do Tesouro Nacional nesta atualização. Veja no <a href="https://siconfi.tesouro.gov.br/" target="_blank" rel="noreferrer">SICONFI ↗</a>.</div>;
  const a = anos.find((x) => x.ano === anoSel) || anos[0];
  const b = anos.find((x) => x.ano === compSel) || anos.find((x) => x.ano === a.ano - 1) || null;
  const variacao = b ? pct(a.total_liquidado, b.total_liquidado) : null;
  const daArea = (codigo: string, ano: number) => anos.find((x) => x.ano === ano)?.funcoes.find((f) => f.codigo === codigo)?.liquidado || 0;
  return (
    <>
      <section>
        <h2>1. Quanto {quem} gastou por ano</h2>
        <Colunas rotulo={`Gasto de ${quem} por ano`} partes={[{ nome: "Gasto", cor: "var(--s1)" }]}
          itens={anos.slice().reverse().map((x) => ({ label: `${x.ano}`, valores: [x.total_liquidado] }))} />
        <p className="muted small">"Gasto" aqui é o valor liquidado: o serviço foi feito ou a compra foi entregue. Os valores não descontam a inflação.</p>
      </section>
      <section>
        <h2>2. Em que gastou em {a.ano}</h2>
        <div className="search">
          <label className="ano-sel"><span className="muted small">Ano</span>
            <select id="ano-dinheiro" value={a.ano} onChange={(e) => setAno(Number(e.target.value))}>{anos.map((x) => <option key={x.ano} value={x.ano}>{x.ano}</option>)}</select></label>
          <label className="ano-sel"><span className="muted small">Comparar com</span>
            <select id="comparar-dinheiro" value={b?.ano || 0} onChange={(e) => setComp(Number(e.target.value))}>
              <option value={0}>Não comparar</option>{anos.filter((x) => x.ano !== a.ano).map((x) => <option key={x.ano} value={x.ano}>{x.ano}</option>)}</select></label>
        </div>
        <div className="grid">
          <div className="card stat"><span className="label">Gasto em {a.ano}</span><span className="value">{reaisCurto(a.total_liquidado)}</span>
            <span className="hint">{b && variacao != null ? `${pctTxt(variacao)} em relação a ${b.ano} (${reaisCurto(b.total_liquidado)})` : `Pago até o fim do ano: ${reaisCurto(a.total_pago)}`}</span></div>
          {a.funcoes.slice(0, 3).map((f) => (
            <div className="card stat" key={f.codigo}><span className="label">{f.funcao}</span><span className="value">{a.total_liquidado ? Math.round((f.liquidado / a.total_liquidado) * 100) : 0}%</span>
              <span className="hint">de cada R$ 100 gastos, R$ {a.total_liquidado ? Math.round((f.liquidado / a.total_liquidado) * 100) : 0} foram para {f.funcao.toLowerCase()}</span></div>
          ))}
        </div>
        <Barras itens={a.funcoes.map((f) => {
          const p = b ? pct(f.liquidado, daArea(f.codigo, b.ano)) : null;
          return { label: f.funcao, valor: f.liquidado, cor: "var(--s1)", nota: b ? (p == null ? `não aparecia em ${b.ano}` : `${pctTxt(p)} em relação a ${b.ano}`) : undefined };
        })} />
      </section>
      <section>
        <h2>3. Abra uma área para ver o detalhe</h2>
        {a.funcoes.map((f) => (
          <Abrir key={f.codigo} titulo={<>{f.funcao} · <span className="num">{reaisCurto(f.liquidado)}</span></>}>
            {f.principais.length > 0 && <>
              <p className="small"><strong>Principalmente em:</strong></p>
              <Barras itens={f.principais.map((s) => ({ label: s.nome, valor: s.valor, cor: "var(--s3)" }))} />
            </>}
            <p className="small"><strong>{f.funcao}, ano a ano:</strong></p>
            <Colunas rotulo={`${f.funcao} por ano`} partes={[{ nome: f.funcao, cor: "var(--s1)" }]}
              itens={anos.slice().reverse().map((x) => ({ label: `${x.ano}`, valores: [daArea(f.codigo, x.ano)] }))} />
            <div className="kv small" style={{ maxWidth: 460 }}>
              <span>Reservado no orçamento (empenhado)</span><span className="num">{reais(f.empenhado)}</span>
              <span>Entregue (liquidado)</span><span className="num">{reais(f.liquidado)}</span>
              <span>Pago até o fim do ano</span><span className="num">{reais(f.pago)}</span>
            </div>
          </Abrir>
        ))}
        {caminho}
        <OndeVer links={[
          { nome: "Contas no SICONFI (Tesouro Nacional)", url: c.fonte, explica: `as contas que ${quem} entregou` },
          { nome: "Dados brutos (API do Tesouro)", url: c.api, explica: "o arquivo de onde tiramos estes números" },
        ]} />
      </section>
    </>
  );
}

/** Do total até as notas: onde ver quem recebeu cada pagamento */
function CaminhoEstado() {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <strong>Quer chegar às notas?</strong>
      <ul className="small" style={{ margin: "6px 0 0", paddingLeft: 18, display: "grid", gap: 4 }}>
        <li><Link to="/assembleia">Deputados estaduais</Link>: cada nota da verba indenizatória, com número, CNPJ e data.</li>
        <li><Link to="/governo">Governo</Link>: salário e cada viagem do governador e dos secretários.</li>
        <li><Link to="/emendas-estaduais">Emendas estaduais</Link>: para quem cada deputado mandou dinheiro.</li>
        <li><a href="https://www.transparencia.mg.gov.br/" target="_blank" rel="noreferrer">Portal da Transparência de MG ↗</a>: cada pagamento do governo a empresas, por órgão e por favorecido.</li>
      </ul>
    </div>
  );
}

function CaminhoCidade({ id, nome }: { id: string; nome: string }) {
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <strong>Quer ver quem recebeu?</strong>
      <ul className="small" style={{ margin: "6px 0 0", paddingLeft: 18, display: "grid", gap: 4 }}>
        <li><Link to={`/cidade/${id}?aba=dinheiro`}>Dinheiro de {nome}</Link>: as emendas federais e estaduais, uma por uma, e quem recebeu.</li>
        <li><Link to={`/cidade/${id}`}>Quem governa {nome}</Link>: prefeitos e vereadores, para saber de quem cobrar.</li>
        <li>Os pagamentos da prefeitura a cada empresa ficam no portal da transparência da prefeitura e no <a href="https://www.tce.mg.gov.br/" target="_blank" rel="noreferrer">Tribunal de Contas (TCE-MG) ↗</a>.</li>
      </ul>
    </div>
  );
}

/** Quanto as empresas de Minas deixaram de pagar de impostos federais por benefícios fiscais (renúncia da Receita) */
function Incentivos() {
  const { data, error } = useData<IncentivosMG>("estado/incentivos.json");
  const [anoSel, setAno] = useState(0);
  const [busca, setBusca] = useState("");
  const [cidade, setCidade] = useState("");
  const [setor, setSetor] = useState("");
  const anos = useMemo(() => (data?.anos || []).filter((x) => x.n > 0).sort((a, b) => b.ano - a.ano), [data]);
  if (!data) return <Loading error={error} />;
  const a = anos.find((x) => x.ano === anoSel) || anos[0];
  const top = (a?.top || []).filter((e) => (!cidade || e.municipio === cidade) && (!setor || e.setor === setor)
    && (!busca || norm(`${e.nome} ${e.cnpj}`).includes(norm(busca))));
  return (
    <section>
      <h2>Quem deixa de pagar imposto</h2>
      <Explain>Para atrair empresas ou ajudar um setor, o governo federal dá descontos de impostos: é a "renúncia fiscal". O dinheiro que a empresa deixa de pagar não entra nos cofres públicos, então é como se fosse um gasto. Aqui estão as empresas com sede em Minas e quanto cada uma deixou de pagar, segundo a Receita Federal.</Explain>
      {!a ? <div className="empty">A Receita Federal não publicou a renúncia fiscal das empresas de Minas nesta atualização. Veja no <a href="https://portaldatransparencia.gov.br/download-de-dados/renuncias" target="_blank" rel="noreferrer">Portal da Transparência ↗</a>.</div> : <>
        {anos.length > 1 && <Colunas rotulo="Renúncia fiscal das empresas de Minas por ano" partes={[{ nome: "Deixou de pagar", cor: "var(--s2)" }]}
          itens={anos.slice().reverse().map((x) => ({ label: `${x.ano}${x.parcial ? "*" : ""}`, valores: [x.total] }))} />}
        <div className="search">
          <label className="ano-sel"><span className="muted small">Ano</span>
            <select id="ano-incentivos" value={a.ano} onChange={(e) => setAno(Number(e.target.value))}>{anos.map((x) => <option key={x.ano} value={x.ano}>{x.ano}</option>)}</select></label>
          <input id="busca-incentivo" aria-label="Empresa ou CNPJ" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Empresa ou CNPJ" />
          <select id="filtro-cidade-inc" aria-label="Cidade" value={cidade} onChange={(e) => setCidade(e.target.value)}>
            <option value="">Todas as cidades</option>{a.por_municipio.map(([m]) => <option key={m}>{m}</option>)}
          </select>
          <select id="filtro-setor-inc" aria-label="Setor" value={setor} onChange={(e) => setSetor(e.target.value)}>
            <option value="">Todos os setores</option>{a.por_setor.map((s) => <option key={s.setor}>{s.setor}</option>)}
          </select>
        </div>
        <div className="grid">
          <div className="card stat"><span className="label">Empresas de Minas, {a.ano}</span><span className="value">{reaisCurto(a.total)}</span>
            <span className="hint">{a.n.toLocaleString("pt-BR")} empresas{a.total_brasil ? `, ${((a.total / a.total_brasil) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% do Brasil` : ""}{a.parcial ? ". Ano ainda incompleto" : ""}</span></div>
        </div>
        <div className="grid grid-2">
          <div><h3>Por setor</h3><Barras itens={a.por_setor.slice(0, 10).map((s) => ({ label: <button className="link" onClick={() => setSetor(setor === s.setor ? "" : s.setor)}>{s.setor}</button>, valor: s.valor, nota: `${s.n} empresas`, cor: "var(--s2)" }))} /></div>
          <div><h3>Por cidade</h3><Barras itens={a.por_municipio.slice(0, 10).map(([m, v, n]) => ({ label: <button className="link" onClick={() => setCidade(cidade === m ? "" : m)}>{m}</button>, valor: v, nota: `${n} empresas`, cor: "var(--s2)" }))} /></div>
        </div>
        <h3>As empresas que mais deixaram de pagar{cidade ? ` em ${cidade}` : ""}{setor ? ` (${setor.toLowerCase()})` : ""}</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Empresa</th><th className="r">Deixou de pagar</th></tr></thead>
            <tbody>{top.slice(0, 50).map((e) => (
              <tr key={e.cnpj}>
                <td><a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${e.cnpj}`} target="_blank" rel="noreferrer">{e.nome} ↗</a>
                  <div className="small muted">{[e.municipio, e.atividade || e.setor].filter(Boolean).join(" · ")} · <span className="mono">{cnpjFmt(e.cnpj)}</span></div>
                  {e.beneficios.length > 0 && <div className="small">Por quê: {e.beneficios.map(([n, v]) => `${n} (${reaisCurto(v)})`).join(", ")}</div>}
                  {!!e.donos?.length && <div className="small muted">Donos: {e.donos.slice(0, 3).join(", ")}</div>}</td>
                <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(e.valor)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        {!top.length && <div className="empty">Nenhuma empresa com esses filtros entre as maiores.</div>}
        <p className="muted small">Mostramos as {a.top.length} empresas de Minas com maior renúncia no ano. Os descontos de ICMS dados pelo próprio governo de Minas não são publicados empresa por empresa.</p>
      </>}
      <OndeVer links={[
        { nome: "Renúncia fiscal por empresa no Portal da Transparência", url: data.fonte, explica: "o arquivo completo, com dados da Receita Federal" },
        { nome: "Benefícios fiscais do estado na Secretaria de Fazenda de MG", url: "https://www.fazenda.mg.gov.br/", explica: "o total de ICMS que Minas deixa de cobrar está na lei de diretrizes orçamentárias" },
      ]} />
    </section>
  );
}

/** As palavras difíceis, explicadas */
function Glossario() {
  return (
    <section>
      <h2>Palavras que aparecem aqui</h2>
      <Abrir titulo="O que quer dizer empenhado, liquidado e pago?">
        <p className="small">Pense numa compra: <strong>empenhado</strong> é quando o governo separa o dinheiro (como guardar o dinheiro no envelope); <strong>liquidado</strong> é quando o serviço foi feito ou a compra chegou; <strong>pago</strong> é quando o dinheiro saiu da conta. Nesta página usamos o liquidado, porque mostra o que foi entregue de verdade.</p>
      </Abrir>
      <Abrir titulo="O que é uma área (função)?">
        <p className="small">É o grande assunto do gasto: saúde, educação, segurança, transporte. Dentro de cada área há partes menores (subfunções), como "atenção básica" dentro de saúde.</p>
      </Abrir>
      <Abrir titulo="O que é renúncia fiscal?">
        <p className="small">É o imposto que o governo decide não cobrar de uma empresa ou de um setor, para incentivar alguma atividade. Não é ilegal, mas é dinheiro que deixa de ir para escolas, hospitais e estradas, por isso precisa ser acompanhado.</p>
      </Abrir>
    </section>
  );
}
