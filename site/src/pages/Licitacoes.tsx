import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Barras, Explain, Loading, useData } from "../components/ui";
import { cnpjFmt, dataBR, linkSeguro, numero, reais, reaisCurto, type CidadeResumo, type CompraPncp, type FormaCompra, type LicitacoesIndice, type LicitacoesLocal } from "../data";

/* Licitações e contratações diretas, do governo de Minas e de cada cidade, pelo PNCP (Portal Nacional de Contratações
   Públicas): quem recebeu, quanto, para quê, em que pé está e se houve licitação ou se ela foi dispensada. */
export default function LicitacoesPage() {
  const [params, setParams] = useSearchParams();
  const { data: cidades } = useData<CidadeResumo[]>("cidades.json");
  const onde = params.get("onde") || "estado";
  const cidade = cidades?.find((c) => c.id === onde);
  const ir = (o: string) => setParams(o === "estado" ? {} : { onde: o }, { replace: true });
  return (
    <>
      <section>
        <span className="eyebrow">Minas Gerais</span>
        <h1>Licitações e contratações</h1>
        <Explain>Toda compra pública deveria passar por uma licitação: uma disputa aberta em que vence quem oferece o melhor preço. A lei permite contratar sem disputa em alguns casos (a dispensa e a inexigibilidade), mas o órgão tem de dizer qual artigo da lei usou. Aqui você vê, para o governo de Minas e para cada cidade, cada compra publicada, quem recebeu, quanto, para quê, em que pé está e se houve licitação.</Explain>
        <div className="tabs" role="tablist" aria-label="Onde">
          <button role="tab" aria-selected={onde === "estado"} onClick={() => ir("estado")}>Governo de Minas</button>
          {(cidades || []).map((c) => <button key={c.id} role="tab" aria-selected={onde === c.id} onClick={() => ir(c.id)}>{c.nome}</button>)}
        </div>
      </section>
      {onde === "estado" ? <LicitacoesLugar id="estado" nome="o governo de Minas" />
        : cidade ? <LicitacoesLugar id={cidade.id} nome={cidade.nome} /> : cidades ? <div className="empty">Cidade não encontrada.</div> : <Loading />}
    </>
  );
}

/** "de Itajubá", "do governo de Minas" */
const de = (n: string) => (n.startsWith("o ") ? `do ${n.slice(2)}` : `de ${n}`);
const por = (n: string) => (n.startsWith("o ") ? `pelo ${n.slice(2)}` : `por ${n}`);
const portal = (cnpj: string) => `https://portaldatransparencia.gov.br/pessoa-juridica/${cnpj}`;
const CHIP: Record<FormaCompra, string> = { licitacao: "ok", dispensa: "nao", inexigibilidade: "nao", outro: "" };
const NOME_FORMA: Record<FormaCompra, string> = { licitacao: "Licitação", dispensa: "Dispensa", inexigibilidade: "Inexigibilidade", outro: "Outro" };
const COR_FORMA: Record<FormaCompra, string> = { licitacao: "var(--s1)", dispensa: "var(--s2)", inexigibilidade: "var(--s3)", outro: "var(--s4)" };

/** O bloco de um lugar (o estado ou uma cidade). Também aparece na aba "Licitações" da página da cidade. */
export function LicitacoesLugar({ id, nome }: { id: string; nome: string }) {
  const { data: idx, error } = useData<LicitacoesIndice>("licitacoes/index.json");
  const local = idx?.locais.find((l) => l.id === id);
  const [anoSel, setAno] = useState<number | null>(null);
  if (!idx) return <Loading error={error && "As licitações ainda não foram baixadas do PNCP."} />;
  if (!local || !local.anos.length) return (
    <section><div className="empty">As licitações {de(nome)} ainda não foram lidas do Portal Nacional de Contratações Públicas (PNCP). A leitura é feita aos poucos, a cada atualização do site.</div></section>
  );
  const ano = local.anos.find((a) => a.ano === anoSel)?.ano ?? local.anos[0].ano;
  return (
    <>
      {local.anos.length > 1 && (
        <section className="row" style={{ gap: 8, alignItems: "baseline" }}>
          <label htmlFor="ano-licitacoes" className="small">Ano:</label>
          <select id="ano-licitacoes" value={ano} onChange={(e) => setAno(Number(e.target.value))}>
            {local.anos.map((a) => <option key={a.ano} value={a.ano}>{a.ano}{a.completo ? "" : " (leitura em andamento)"}</option>)}
          </select>
        </section>
      )}
      <Ano key={`${id}-${ano}`} id={id} ano={ano} nome={nome} />
    </>
  );
}

function Ano({ id, ano, nome }: { id: string; ano: number; nome: string }) {
  const { data: d, error } = useData<LicitacoesLocal>(`licitacoes/${id}-${ano}.json`);
  if (!d) return <Loading error={error} />;
  const t = d.total;
  const sem = d.por_forma.filter((f) => f.forma === "dispensa" || f.forma === "inexigibilidade");
  const nSem = sem.reduce((a, f) => a + f.n, 0);
  const valorDe = (f: { homologado: number; estimado: number }) => f.homologado || f.estimado;
  const vTotal = d.por_forma.reduce((a, f) => a + valorDe(f), 0);
  const vSem = sem.reduce((a, f) => a + valorDe(f), 0);
  const fonte = (
    <p className="muted small fonte-linha">Fonte: <a href={linkSeguro(d.fonte)} target="_blank" rel="noreferrer">Portal Nacional de Contratações Públicas (PNCP) ↗</a>, compras publicadas em {ano} e contratos dos mesmos órgãos.
      Atualizado em {dataBR(d.atualizado)}. <a href={linkSeguro(d.api)} target="_blank" rel="noreferrer">Consulta oficial (API) ↗</a></p>
  );
  return (
    <>
      {!d.completo && (
        <div className="alert" role="status">A leitura de {ano} no PNCP ainda está em andamento ({d.faltam.length} {d.faltam.length === 1 ? "parte falta" : "partes faltam"}: {d.faltam.slice(0, 4).join(", ")}{d.faltam.length > 4 ? "..." : ""}). Os números abaixo vão crescer nas próximas atualizações.</div>
      )}
      <section>
        <h2>Compras {de(nome)} em {ano}</h2>
        {!t.n ? <div className="empty">Nenhuma compra {de(nome)} publicada no PNCP em {ano}.</div> : <>
          <div className="grid">
            <div className="card stat"><span className="label">Compras publicadas</span><span className="value">{numero(t.n)}</span>
              <span className="hint">{numero(t.contratos)} contrato{t.contratos === 1 ? "" : "s"} assinado{t.contratos === 1 ? "" : "s"}</span></div>
            <div className="card stat"><span className="label">Valor (homologado ou estimado)</span><span className="value">{reaisCurto(vTotal)}</span>
              <span className="hint">Sem as compras revogadas ou anuladas</span></div>
            <div className="card stat"><span className="label">Sem licitação</span><span className="value">{t.n ? `${Math.round((nSem / t.n) * 100)}%` : "—"}</span>
              <span className="hint">{numero(nSem)} compra{nSem === 1 ? "" : "s"} por dispensa ou inexigibilidade, {reaisCurto(vSem)}</span></div>
          </div>
          <Explain>"Homologado" é o valor final, depois da disputa ou da escolha do fornecedor. Quando a compra ainda não terminou, usamos o valor estimado pelo órgão.</Explain>
          <h3>Com licitação ou sem</h3>
          <Barras rosca={{ titulo: `Compras ${de(nome)} em ${ano}, com e sem licitação` }}
            itens={d.por_forma.map((f) => ({ label: f.rotulo, valor: valorDe(f), cor: COR_FORMA[f.forma], nota: `${numero(f.n)} compra${f.n === 1 ? "" : "s"}` }))} />
          <h3>Em que pé estão</h3>
          <p className="dinheiro-total small">{d.por_andamento.map((a) => <span key={a.andamento}><strong>{a.andamento}:</strong> {numero(a.n)}</span>)}</p>
        </>}
        {fonte}
      </section>
      {d.amparos.length > 0 && (
        <section>
          <h2>Por que não houve licitação</h2>
          <Explain>Na dispensa e na inexigibilidade o órgão escolhe o fornecedor sem disputa. Ele tem de dizer o artigo da lei que permite isso. Estes são os motivos mais usados {por(nome)} em {ano}.</Explain>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Motivo legal</th><th className="r">Compras</th><th className="r">Valor</th></tr></thead>
              <tbody>
                {d.amparos.map((a) => (
                  <tr key={a.nome}>
                    <td><span className={`chip ${CHIP[a.forma]}`}>{NOME_FORMA[a.forma]}</span> <strong>{a.nome}</strong>{a.descricao && <div className="small muted">{a.descricao}</div>}</td>
                    <td className="r num">{numero(a.n)}</td>
                    <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(a.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {d.fornecedores.length > 0 && <Fornecedores d={d} nome={nome} />}
      {d.orgaos.length > 1 && (
        <section>
          <h2>Quem comprou</h2>
          <Explain>Os órgãos {de(nome)} que publicaram compras em {ano}.</Explain>
          <Barras itens={d.orgaos.slice(0, 12).map((o) => ({ label: o.nome, valor: o.valor, nota: `${numero(o.n)} compra${o.n === 1 ? "" : "s"}` }))} cor="var(--s1)" />
        </section>
      )}
      {d.compras.length > 0 && <Lista d={d} nome={nome} />}
      <section>
        <h2>Limites destes dados</h2>
        <ul className="small">
          <li>Tudo vem do <a href="https://pncp.gov.br" target="_blank" rel="noreferrer">PNCP</a>, onde os órgãos públicos são obrigados a publicar as compras e os contratos desde a Lei 14.133/2021. Compra que o órgão não publicou no PNCP não aparece aqui.</li>
          <li>"Se foi feito": o PNCP mostra a situação da compra (publicada, revogada, anulada, suspensa) e o contrato (assinado, em vigor ou encerrado). Ele não registra a entrega da obra ou do serviço nem os pagamentos; isso fica no portal da transparência de cada órgão.</li>
          <li>Quem recebeu vem dos contratos. Compras pequenas, por dispensa, muitas vezes não têm contrato publicado: nesses casos o fornecedor fica só na página da compra no PNCP (o link de cada linha).</li>
          <li>Fornecedor pessoa física aparece só como "Pessoa física", sem nome e sem CPF.</li>
          {id === "estado" ? <li>Governo de Minas: só órgãos estaduais (secretarias, autarquias, fundações, empresas do estado). Prefeituras e órgãos federais ficam de fora.</li>
            : <li>{nome}: só órgãos municipais (prefeitura, câmara, autarquias e fundos). A universidade federal, o exército ou as escolas estaduais que ficam na cidade ficam de fora.</li>}
        </ul>
      </section>
    </>
  );
}

function Fornecedores({ d, nome }: { d: LicitacoesLocal; nome: string }) {
  const [todos, setTodos] = useState(false);
  return (
    <section>
      <h2>Quem recebeu</h2>
      <Explain>As empresas e entidades com contratos assinados com {nome} em {d.ano}, pela soma do valor dos contratos. O nome leva à página da empresa no Portal da Transparência.</Explain>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Fornecedor</th><th className="r">Contratos</th><th className="r">Valor</th></tr></thead>
          <tbody>
            {d.fornecedores.slice(0, todos ? 100 : 15).map((f, i) => (
              <tr key={i}>
                <td>{f.cnpj ? <a href={portal(f.cnpj)} target="_blank" rel="noreferrer">{f.nome} ↗</a> : f.nome}
                  {f.cnpj && <div className="muted small mono">CNPJ {cnpjFmt(f.cnpj)}</div>}</td>
                <td className="r num">{numero(f.n)}</td>
                <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(f.valor)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.fornecedores.length > 15 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${d.fornecedores.length} maiores`}</button>}
    </section>
  );
}

function Lista({ d, nome }: { d: LicitacoesLocal; nome: string }) {
  const [forma, setForma] = useState<FormaCompra | "">("");
  const [busca, setBusca] = useState("");
  const [n, setN] = useState(30);
  const sem = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const lista = useMemo(() => {
    const q = sem(busca.trim());
    return d.compras.filter((c) => (!forma || c.forma === forma)
      && (!q || sem(`${c.objeto} ${c.orgao} ${c.unidade} ${c.contratos.map((x) => x.fornecedor).join(" ")}`).includes(q)));
  }, [d, forma, busca]);
  return (
    <section>
      <h2>Cada compra</h2>
      <Explain>Da maior para a menor. Procure pelo que foi comprado ("asfalto", "show", "merenda") ou pelo nome do fornecedor. Cada linha leva à página oficial da compra no PNCP, com o edital, os itens e os documentos.</Explain>
      {d.n_lista < d.total.n && <p className="small muted">Mostrando as {numero(d.n_lista)} maiores compras, de {numero(d.total.n)}. Os totais acima contam todas.</p>}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <input type="search" placeholder="Procurar compra ou fornecedor" aria-label="Procurar compra ou fornecedor" value={busca} onChange={(e) => { setBusca(e.target.value); setN(30); }} />
        <select aria-label="Com ou sem licitação" value={forma} onChange={(e) => { setForma(e.target.value as FormaCompra | ""); setN(30); }}>
          <option value="">Com e sem licitação</option>
          <option value="licitacao">Só com licitação</option>
          <option value="dispensa">Só dispensa</option>
          <option value="inexigibilidade">Só inexigibilidade</option>
          <option value="outro">Outros procedimentos</option>
        </select>
      </div>
      {!lista.length ? <div className="empty">Nenhuma compra {de(nome)} com esse filtro.</div> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Para quê</th><th className="so-largo">Quem recebeu</th><th className="r">Valor</th></tr></thead>
            <tbody>{lista.slice(0, n).map((c) => <Linha key={c.id} c={c} />)}</tbody>
          </table>
        </div>
      )}
      {lista.length > n && <button className="link" onClick={() => setN(n + 50)}>Mostrar mais ({numero(lista.length - n)} restantes)</button>}
    </section>
  );
}

function Linha({ c }: { c: CompraPncp }) {
  return (
    <tr>
      <td>
        <div className="small muted">{dataBR(c.data)} · {c.orgao}{c.unidade ? ` · ${c.unidade}` : ""}</div>
        <a href={linkSeguro(c.url)} target="_blank" rel="noreferrer">{c.objeto || "Compra sem descrição"} ↗</a>
        <div className="small" style={{ marginTop: 4 }}>
          <span className={`chip ${CHIP[c.forma]}`}>{c.forma === "outro" ? c.modalidade : NOME_FORMA[c.forma]}</span>{" "}
          {c.forma === "licitacao" ? c.modalidade : c.amparo}{" · "}<strong>{c.andamento}</strong>
        </div>
        {c.forma !== "licitacao" && c.amparo_descricao && <div className="small muted">{c.amparo_descricao}</div>}
        <div className="small so-celular" style={{ marginTop: 4 }}><strong>Quem recebeu:</strong> <Recebeu c={c} /></div>
      </td>
      <td className="small so-largo"><Recebeu c={c} /></td>
      <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(c.valor)}
        {c.homologado > 0 && c.estimado > 0 && c.homologado !== c.estimado && <div className="small muted">estimado {reais(c.estimado)}</div>}</td>
    </tr>
  );
}

function Recebeu({ c }: { c: CompraPncp }) {
  return (
    <>
        {c.contratos.length ? c.contratos.slice(0, 3).map((x, i) => (
          <div key={i}>{x.cnpj ? <a href={portal(x.cnpj)} target="_blank" rel="noreferrer">{x.fornecedor}</a> : x.fornecedor}{" "}
            <a href={linkSeguro(x.url)} target="_blank" rel="noreferrer" className="muted">contrato ↗</a>
            <div className="muted">{reais(x.valor)}{x.fim ? ` · até ${dataBR(x.fim)}` : ""}</div></div>
        )) : <span className="muted">Sem contrato no PNCP</span>}
        {c.contratos.length > 3 && <div className="muted">e mais {c.contratos.length - 3}</div>}
    </>
  );
}
