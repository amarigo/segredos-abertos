import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useAno, useData } from "../components/ui";
import { casaNome, cnpjFmt, corPartido, dataBR, linkSeguro, reais, reaisCurto, type Casa } from "../data";
import { DocsDoAutor, type AutorEmenda } from "../components/DocsEmendas";
import { Pizza } from "./Partidos";
import "./emendas.css";

/* Formato de data/emendas/{ano}.json (gerado por etl/sa_etl/emendas.py) */
interface Valores { empenhado: number; pago: number }
type Par = [string, number];
interface Autor extends Valores {
  nome: string; n: number; areas: Par[]; recebedores: Par[]; pix: number;
  politico: string | null; partido: string; uf: string; casa: Casa | "";
  pagamentos?: { valor: number; arquivo: string };
}
interface Coletivo extends Valores { nome: string; n: number; tipo: string; areas: Par[]; recebedores: Par[]; pagamentos?: { valor: number; arquivo: string } }
/* Pagamentos ligados às emendas, pelo ano em que foram feitos (etl/sa_etl/pagamentos.py) */
interface Pagamentos {
  ate: string; total: number; n: number;
  orgaos: { nome: string; valor: number; n: number; ugs: Par[] }[];
  autores: (AutorEmenda & { valor: number; n: number; orgaos: Par[]; arquivo: string })[];
  empresas: { cnpj: string; nome: string; tipo: string; pagina: boolean; valor: number; n: number; autores: (AutorEmenda & { valor: number })[]; orgaos: Par[] }[];
  n_empresas: number;
}
interface PartidoEmendas extends Valores { sigla: string; n: number; camara: number; senado: number; pix: number; areas: Par[] }
interface Favorecido { doc: string; nome: string; cat: string; natureza: string; uf: string; municipio: string; valor: number; autores: Par[] }
interface Recebedores {
  n: number; total: number; por_categoria: { cat: string; rotulo: string; valor: number; n: number }[];
  lista: Favorecido[]; empresas: Favorecido[]; entidades: Favorecido[];
  por_uf: Par[]; municipios: { nome: string; uf: string; valor: number; n: number }[]; n_municipios: number;
}
interface EmendasAno {
  ano: number; fonte: string; total: Valores & { n: number };
  por_tipo: (Valores & { tipo: string; rotulo: string; n: number })[];
  por_area: (Valores & { area: string })[];
  autores: Autor[]; coletivos: Coletivo[]; partidos: PartidoEmendas[];
  sem_partido: Valores & { n: number };
  favorecidos: Recebedores | null;
  pagamentos?: Pagamentos | null;
}
interface Indice { anos: number[]; totais: Record<string, Valores & { n: number }> }

type Medida = "pago" | "empenhado";

const COR_TIPO: Record<string, string> = { individual: "var(--s1)", pix: "var(--c4)", bancada: "var(--s3)", comissao: "var(--c7)", relator: "var(--c8)", outro: "var(--c-outros)" };
const EXPLICA_TIPO: Record<string, string> = {
  individual: "Cada deputado e senador escolhe para onde vai uma parte do Orçamento. Aqui o destino e a finalidade ficam definidos (por exemplo, um posto de saúde).",
  pix: "Também individual, mas o dinheiro cai direto no caixa da prefeitura ou do estado, sem dizer em que será usado. Por isso é chamada de emenda Pix.",
  bancada: "Decidida em conjunto pelos deputados e senadores de um mesmo estado.",
  comissao: "Decidida por uma comissão da Câmara ou do Senado (de Saúde, de Agricultura...).",
  relator: "Indicada pelo relator do Orçamento. Foi a base do chamado orçamento secreto, proibido pelo STF em 2022.",
  outro: "",
};
const NOME_COLETIVO: Record<string, string> = { bancada: "Bancada", comissao: "Comissão", relator: "Relator" };
const semAcento = (t: string) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const pctDe = (v: number, t: number) => (t ? `${((v / t) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%` : "—");

export default function Emendas() {
  const { ano } = useAno();
  const { data: indice, error: erroIndice } = useData<Indice>("emendas/anos.json");
  const tem = indice?.anos.map(String).includes(ano);
  const { data, error } = useData<EmendasAno>(tem ? `emendas/${ano}.json` : null);
  const [medida, setMedida] = useState<Medida>("pago");

  if (!indice && !erroIndice) return <Loading />;
  if (!tem) {
    return (
      <>
        <h1>Emendas parlamentares</h1>
        <div className="empty">
          {indice ? <>Ainda não há dados de emendas de {ano}. Anos disponíveis: {indice.anos.join(", ")}.</>
            : "Os dados de emendas ainda não foram coletados. Eles aparecem aqui depois da próxima atualização diária."}
        </div>
      </>
    );
  }
  if (!data) return <Loading error={error} />;
  const v = (x: Valores) => x[medida];
  const tot = v(data.total);

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Emendas parlamentares · {ano}</span>
        <h1>Para onde foi o dinheiro das emendas</h1>
        <Explain>
          Todo ano, deputados federais e senadores decidem para onde vai uma parte do Orçamento do governo federal. Essa parte se chama <strong>emenda parlamentar</strong>.
          O dinheiro costuma ir para prefeituras, estados, hospitais e entidades da base eleitoral de quem fez a emenda. Aqui você vê para onde foi, para quê, quem mandou mais e que partido usa mais.
        </Explain>
        <div className="grid">
          <div className="card stat"><span className="label">Reservado (empenhado)</span><span className="value">{reaisCurto(data.total.empenhado)}</span><span className="hint">O governo separou esse valor para as emendas de {ano}</span></div>
          <div className="card stat"><span className="label">Pago até agora</span><span className="value">{reaisCurto(data.total.pago)}</span><span className="hint">{pctDe(data.total.pago, data.total.empenhado)} do reservado já saiu do caixa</span></div>
          <div className="card stat"><span className="label">Emendas</span><span className="value">{data.total.n.toLocaleString("pt-BR")}</span><span className="hint">{data.autores.length.toLocaleString("pt-BR")} parlamentares fizeram emendas</span></div>
          {data.favorecidos && <div className="card stat"><span className="label">Cidades</span><span className="value">{data.favorecidos.n_municipios.toLocaleString("pt-BR")}</span><span className="hint">receberam pagamentos de emendas em {ano}</span></div>}
        </div>
        <div className="row emd-medida">
          <span className="small muted">Mostrar valores</span>
          <div className="toggle" role="group" aria-label="Valor mostrado">
            <button aria-pressed={medida === "pago"} onClick={() => setMedida("pago")}>Pagos</button>
            <button aria-pressed={medida === "empenhado"} onClick={() => setMedida("empenhado")}>Reservados</button>
          </div>
          <span className="small muted">{medida === "pago" ? "O que já foi pago de fato (inclui pagamentos feitos nos anos seguintes)." : "O que o governo se comprometeu a pagar (empenho). Parte pode nunca ser paga."}</span>
        </div>
      </section>

      <section>
        <h2>Tipos de emenda</h2>
        <Barras itens={data.por_tipo.filter((t) => v(t) > 0).map((t) => ({
          label: <strong>{t.rotulo}</strong>, nota: `${EXPLICA_TIPO[t.tipo] || ""} ${t.n.toLocaleString("pt-BR")} emendas · ${pctDe(v(t), tot)} do total.`.trim(),
          valor: v(t), cor: COR_TIPO[t.tipo],
        }))} />
      </section>

      <section>
        <h2>Para quê: áreas que receberam mais</h2>
        <Explain>Cada emenda diz em que área do governo o dinheiro será usado, como saúde, educação ou obras na cidade (urbanismo). Na emenda Pix essa informação não existe.</Explain>
        <Barras itens={data.por_area.filter((a) => v(a) > 0).sort((a, b) => v(b) - v(a)).slice(0, 14).map((a) => ({
          label: <strong>{a.area}</strong>, nota: pctDe(v(a), tot), valor: v(a),
          cor: a.area.includes("Pix") ? "var(--c4)" : "var(--s1)",
        }))} />
      </section>

      {data.favorecidos && <Destinos f={data.favorecidos} ano={ano} />}
      {data.pagamentos && <QuemPagou p={data.pagamentos} ano={ano} />}
      {data.pagamentos && <EmpresasPagas p={data.pagamentos} ano={ano} />}
      <Autores data={data} medida={medida} />
      <PartidosEmendas data={data} medida={medida} />
      <Coletivas data={data} medida={medida} />
      {data.favorecidos && <Favorecidos f={data.favorecidos} ano={ano} />}

      <section>
        <h2>De onde vêm estes dados</h2>
        <p className="small">
          Portal da Transparência do governo federal (Controladoria-Geral da União), arquivo completo de emendas parlamentares, atualizado todo dia. <a href={linkSeguro(data.fonte)} target="_blank" rel="noreferrer">Consultar uma emenda no Portal ↗</a>
        </p>
        <ul className="small muted emd-notas">
          <li>O ano é o ano do Orçamento em que a emenda foi feita. "Pago" soma o que foi pago no próprio ano e o que ficou para depois (restos a pagar) e já foi pago.</li>
          <li>O partido é o partido atual do parlamentar. Quem não está mais no cargo aparece com o último partido que teve na Câmara ou no Senado, quando encontramos. {data.sem_partido.n > 0 && <>Não achamos o partido de {data.sem_partido.n} autores ({reaisCurto(v(data.sem_partido))}).</>}</li>
          <li>Emendas de bancada, de comissão e do relator não são de uma pessoa só. Elas aparecem separadas e não entram na conta dos partidos.</li>
          <li>Quem pagou, as empresas e os documentos vêm dos arquivos diários de despesas do Portal da Transparência. Cada pagamento é ligado à nota de empenho (a reserva do dinheiro), que diz de qual emenda ele é. Só entram pagamentos de empenhos feitos a partir do ano anterior ao primeiro ano do site, por isso a soma pode ser menor que o total pago acima.{data.pagamentos?.ate && <> Dados de pagamento até {dataBR(data.pagamentos.ate)}.</>}</li>
        </ul>
      </section>
    </>
  );
}

function Destinos({ f, ano }: { f: Recebedores; ano: string }) {
  const [q, setQ] = useState("");
  const [n, setN] = useState(12);
  const [todosUf, setTodosUf] = useState(false);
  const muns = useMemo(() => f.municipios.filter((m) => !q.trim() || semAcento(`${m.nome} ${m.uf}`).includes(semAcento(q.trim()))), [f, q]);
  return (
    <section>
      <h2>Para onde foi o dinheiro</h2>
      <Explain>Aqui contamos os <strong>pagamentos feitos em {ano}</strong>, pelo local de quem recebeu: a prefeitura, o governo do estado, o hospital ou a entidade. Inclui pagamentos de emendas de anos anteriores. O dinheiro repassado por bancos e órgãos federais (como a Caixa, que paga obras) fica de fora do mapa, porque o arquivo não diz em que cidade ele foi usado.</Explain>
      <div className="two">
        <div>
          <h3>Por estado</h3>
          <p className="small muted" style={{ margin: "4px 0 12px" }}>Soma o que foi para as prefeituras, para o governo do estado e para as entidades de cada estado.</p>
          <Barras itens={f.por_uf.slice(0, todosUf ? 27 : 10).map(([uf, x]) => ({ label: <strong>{uf}</strong>, nota: pctDe(x, f.por_uf.reduce((a, [, y]) => a + y, 0)), valor: x, cor: "var(--s3)" }))} />
          {!todosUf && f.por_uf.length > 10 && <button className="link" style={{ marginTop: 8 }} onClick={() => setTodosUf(true)}>Ver todos os estados</button>}
        </div>
        <div>
          <h3>Cidades que mais receberam</h3>
          <p className="small muted" style={{ margin: "4px 0 0" }}>Prefeituras, fundos municipais e entidades da cidade. Não inclui o que foi para o governo do estado.</p>
          <div className="search" style={{ margin: "8px 0 12px" }}>
            <input aria-label="Procurar cidade" value={q} onChange={(e) => { setQ(e.target.value); setN(12); }} placeholder="Procure sua cidade" />
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Cidade</th><th className="r">Valor pago</th></tr></thead>
              <tbody>
                {muns.slice(0, n).map((m) => (
                  <tr key={`${m.nome}-${m.uf}`}><td>{m.nome} <span className="muted">({m.uf})</span><div className="small muted">{m.n} recebedor{m.n > 1 ? "es" : ""}</div></td><td className="r num">{reais(m.valor)}</td></tr>
                ))}
                {!muns.length && <tr><td colSpan={2} className="muted">Nenhuma cidade encontrada entre as {f.municipios.length} que mais receberam.</td></tr>}
              </tbody>
            </table>
          </div>
          {muns.length > n && <button className="link" onClick={() => setN(n + 40)}>Mostrar mais cidades</button>}
        </div>
      </div>
    </section>
  );
}

function Autores({ data, medida }: { data: EmendasAno; medida: Medida }) {
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState<Casa | "">("");
  const [n, setN] = useState(15);
  const v = (x: Valores) => x[medida];
  const lista = useMemo(() => data.autores.filter((a) => (!casa || a.casa === casa)
    && (!q.trim() || semAcento(`${a.nome} ${a.partido} ${a.uf}`).includes(semAcento(q.trim()))))
    .sort((a, b) => v(b) - v(a)), [data, casa, q, medida]); // eslint-disable-line react-hooks/exhaustive-deps
  const max = Math.max(1, ...lista.slice(0, 1).map(v));
  return (
    <section>
      <h2>Quem mandou mais dinheiro em emendas</h2>
      <Explain>Todo parlamentar tem direito ao mesmo valor de emendas individuais por ano. As diferenças vêm de quanto o governo de fato reserva e paga para cada um, e das emendas Pix. Toque num nome para ver para onde foi o dinheiro e para quê.</Explain>
      <div className="row" style={{ gap: 8 }}>
        <div className="toggle" role="group" aria-label="Casa">
          <button aria-pressed={casa === ""} onClick={() => setCasa("")}>Todos</button>
          {(["camara", "senado"] as Casa[]).map((c) => <button key={c} aria-pressed={casa === c} onClick={() => setCasa(c)}>{casaNome(c)}</button>)}
        </div>
        <div className="search" style={{ flex: "1 1 240px" }}>
          <input aria-label="Procurar parlamentar" value={q} onChange={(e) => { setQ(e.target.value); setN(15); }} placeholder="Nome, partido ou estado" />
        </div>
      </div>
      <div className="emd-autores">
        {lista.slice(0, n).map((a, i) => (
          <details key={`${a.nome}-${i}`} className="emd-autor">
            <summary>
              <span className="emd-pos num muted">{i + 1}</span>
              <span className="emd-quem">
                <strong>{a.nome}</strong>
                <span className="small muted">{a.partido ? <><i className="partido-cor" style={{ background: corPartido(a.partido) }} />{a.partido}</> : "Partido não identificado"}{a.uf && `-${a.uf}`}{a.casa && ` · ${casaNome(a.casa)}`} · {a.n} emendas</span>
              </span>
              <span className="num emd-valor">{reaisCurto(v(a))}</span>
              <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${(v(a) / max) * 100}%`, background: a.partido ? corPartido(a.partido) : "var(--c-outros)" }} /></span>
            </summary>
            <div className="emd-det">
              <div>
                <h4>Para quê</h4>
                <ul>{a.areas.map(([k, x], j) => <li key={j}><span>{k}</span><span className="num">{reaisCurto(x)}</span></li>)}</ul>
              </div>
              <div>
                <h4>Quem recebeu (pagamentos de {data.ano})</h4>
                {a.recebedores.length ? <ul>{a.recebedores.map(([k, x], j) => <li key={j}><span>{k}</span><span className="num">{reaisCurto(x)}</span></li>)}</ul>
                  : <p className="small muted">Nenhum pagamento em {data.ano}.</p>}
              </div>
              {a.pagamentos && <div style={{ gridColumn: "1 / -1" }}>
                <h4>Notas e documentos de pagamento de {data.ano}</h4>
                <AbrirDocs ano={data.ano} arquivo={a.pagamentos.arquivo} />
              </div>}
              <p className="small muted" style={{ gridColumn: "1 / -1" }}>
                Reservado {reais(a.empenhado)} · pago {reais(a.pago)}{a.pix > 0 && <> · {reaisCurto(a.pix)} em emendas Pix</>}.
                {a.politico && <> <Link to={`/p/${a.politico}`}>Ver gastos e votos de {a.nome}</Link></>}
              </p>
            </div>
          </details>
        ))}
        {!lista.length && <div className="empty">Ninguém encontrado.</div>}
      </div>
      {lista.length > n && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais ({lista.length - n} restantes)</button>}
    </section>
  );
}

function PartidosEmendas({ data, medida }: { data: EmendasAno; medida: Medida }) {
  const [modo, setModo] = useState<"membro" | "total">("membro");
  const v = (x: Valores) => x[medida];
  const linhas = data.partidos.filter((p) => v(p) > 0).map((p) => ({ ...p, valor: v(p), membro: v(p) / p.n }))
    .sort((a, b) => (modo === "total" ? b.valor - a.valor : b.membro - a.membro));
  const principais = new Set(data.partidos.slice().sort((a, b) => v(b) - v(a)).slice(0, 7).map((p) => p.sigla));
  return (
    <section>
      <h2>Que partido usa mais emendas, e para quê</h2>
      <Explain>O <strong>total</strong> mostra quanto todos os parlamentares do partido mandaram em emendas individuais. O valor <strong>por parlamentar</strong> divide pelo número de membros que fizeram emendas, para comparar partidos grandes e pequenos.</Explain>
      <div className="toggle" role="group" aria-label="Medida" style={{ justifySelf: "start" }}>
        <button aria-pressed={modo === "membro"} onClick={() => setModo("membro")}>Por parlamentar</button>
        <button aria-pressed={modo === "total"} onClick={() => setModo("total")}>Total</button>
      </div>
      <Pizza fatias={linhas.map((p) => ({ sigla: p.sigla, valor: p.valor, cor: corPartido(p.sigla), outros: !principais.has(p.sigla) }))}
        titulo={`Emendas individuais ${medida === "pago" ? "pagas" : "reservadas"} por partido em ${data.ano}`} />
      <div className="table-wrap">
        <table>
          <thead><tr><th>Partido</th><th className="r">{modo === "total" ? "Total" : "Por parlamentar"}</th><th className="so-largo-emd">Principais áreas</th></tr></thead>
          <tbody>
            {linhas.map((p) => (
              <tr key={p.sigla}>
                <td><Link to={`/politicos?partido=${encodeURIComponent(p.sigla)}`}><i className="partido-cor" style={{ background: corPartido(p.sigla) }} /><strong>{p.sigla}</strong></Link>
                  <div className="small muted">{p.n} parlamentar{p.n > 1 ? "es" : ""}{p.senado ? ` (${p.senado} no Senado)` : ""}</div>
                  <div className="small emd-areas-cel">{areasTexto(p)}</div></td>
                <td className="r num">{reais(modo === "total" ? p.valor : p.membro)}<div className="small muted">{modo === "total" ? `${reaisCurto(p.membro)} por parlamentar` : `${reaisCurto(p.valor)} no total`}</div></td>
                <td className="small so-largo-emd">{areasTexto(p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted">Conta cada parlamentar no partido atual. Só emendas individuais (incluindo as Pix).</p>
    </section>
  );
}

function areasTexto(p: PartidoEmendas) {
  const t = p.areas.reduce((a, [, x]) => a + x, 0) || 1;
  return p.areas.slice(0, 3).map(([k, x], i) => <Fragment key={k}>{i > 0 && " · "}{k} <span className="muted">{Math.round((x / t) * 100)}%</span></Fragment>);
}

function Coletivas({ data, medida }: { data: EmendasAno; medida: Medida }) {
  const v = (x: Valores) => x[medida];
  const lista = data.coletivos.filter((c) => v(c) > 0).sort((a, b) => v(b) - v(a)).slice(0, 12);
  if (!lista.length) return null;
  return (
    <section>
      <h2>Emendas de bancada, comissão e relator</h2>
      <Explain>Estas emendas são decididas por um grupo, e não por uma pessoa. Por isso não aparecem no ranking de parlamentares nem de partidos.</Explain>
      <Barras itens={lista.map((c) => ({
        label: <><span className="chip">{NOME_COLETIVO[c.tipo] || c.tipo}</span> <strong>{c.nome}</strong></>,
        nota: c.areas.slice(0, 3).map(([k]) => k).join(" · "), valor: v(c), cor: COR_TIPO[c.tipo],
      }))} />
    </section>
  );
}

const COR_CAT: Record<string, string> = { prefeitura: "var(--s1)", estado: "var(--s3)", entidade: "var(--c7)", empresa: "var(--c4)", federal: "var(--c5)", pessoa: "var(--c8)", outro: "var(--c-outros)" };

function Favorecidos({ f, ano }: { f: Recebedores; ano: string }) {
  const [aba, setAba] = useState<"lista" | "empresas" | "entidades">("lista");
  const [n, setN] = useState(15);
  const lista = f[aba];
  return (
    <section>
      <h2>Quem recebeu o dinheiro em {ano}</h2>
      <Explain>Prefeituras, governos estaduais, hospitais, entidades e empresas que receberam pagamentos de emendas neste ano. Ao todo, {f.n.toLocaleString("pt-BR")} recebedores e {reaisCurto(f.total)}. As empresas recebem quando são contratadas diretamente com dinheiro de emenda, por exemplo para obras ou compras.</Explain>
      <Barras itens={f.por_categoria.filter((c) => c.valor > 0).map((c) => ({
        label: <strong>{c.rotulo}</strong>, nota: `${c.n.toLocaleString("pt-BR")} recebedores · ${pctDe(c.valor, f.total)}`, valor: c.valor, cor: COR_CAT[c.cat],
      }))} />
      <div className="toggle" role="group" aria-label="Quem mostrar" style={{ justifySelf: "start" }}>
        <button aria-pressed={aba === "lista"} onClick={() => { setAba("lista"); setN(15); }}>Todos</button>
        <button aria-pressed={aba === "empresas"} onClick={() => { setAba("empresas"); setN(15); }}>Empresas</button>
        <button aria-pressed={aba === "entidades"} onClick={() => { setAba("entidades"); setN(15); }}>Entidades</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Quem recebeu</th><th className="r">Valor</th></tr></thead>
          <tbody>
            {lista.slice(0, n).map((x, i) => (
              <tr key={`${x.doc || x.nome}-${i}`}>
                <td><strong>{x.nome}</strong>
                  <div className="small muted">{[x.natureza, x.municipio && `${x.municipio}${x.uf ? ` (${x.uf})` : ""}`, x.doc && cnpjFmt(x.doc)].filter(Boolean).join(" · ")}</div>
                  {x.autores.length > 0 && <div className="small">Emendas de {x.autores.slice(0, 3).map(([k]) => k).join(", ")}{x.autores.length > 3 ? " e outros" : ""}</div>}
                  {x.doc && <div className="small"><a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${x.doc}`} target="_blank" rel="noreferrer">Ver no Portal da Transparência ↗</a></div>}
                </td>
                <td className="r num">{reais(x.valor)}</td>
              </tr>
            ))}
            {!lista.length && <tr><td colSpan={2} className="muted">Nenhum recebedor deste tipo em {ano}.</td></tr>}
          </tbody>
        </table>
      </div>
      {lista.length > n && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais</button>}
    </section>
  );
}

/** Botão que carrega os documentos só quando a pessoa pede (são centenas de arquivos pequenos). */
function AbrirDocs({ ano, arquivo }: { ano: number | string; arquivo: string }) {
  const [aberto, setAberto] = useState(false);
  if (!aberto) return <button className="link" onClick={() => setAberto(true)}>Ver os pagamentos, quem recebeu e os links oficiais</button>;
  return <DocsDoAutor ano={ano} arquivo={arquivo} />;
}

function QuemPagou({ p, ano }: { p: Pagamentos; ano: string }) {
  return (
    <section>
      <h2>Quem pagou: os ministérios e órgãos</h2>
      <Explain>
        O parlamentar indica a emenda, mas quem paga é um ministério ou órgão do governo federal. Em {ano}, encontramos {p.n.toLocaleString("pt-BR")} pagamentos ligados a emendas, somando {reaisCurto(p.total)}.
        Embaixo de cada órgão aparecem as unidades que fizeram os pagamentos.
      </Explain>
      <Barras itens={p.orgaos.slice(0, 12).map((o) => ({
        label: <strong>{o.nome}</strong>,
        nota: `${o.n.toLocaleString("pt-BR")} pagamentos · ${pctDe(o.valor, p.total)}${o.ugs.length ? ` · ${o.ugs.slice(0, 3).map(([u]) => u).join("; ")}` : ""}`,
        valor: o.valor, cor: "var(--s1)",
      }))} />
    </section>
  );
}

function EmpresasPagas({ p, ano }: { p: Pagamentos; ano: string }) {
  const [q, setQ] = useState("");
  const [n, setN] = useState(15);
  const lista = useMemo(() => p.empresas.filter((e) => !q.trim()
    || semAcento(`${e.nome} ${e.autores.map((a) => `${a.nome} ${a.partido}`).join(" ")}`).includes(semAcento(q.trim()))
    || e.cnpj.includes(q.replace(/\D/g, "") || "x")), [p, q]);
  return (
    <section>
      <h2>Empresas e entidades pagas com emendas, e por indicação de quem</h2>
      <Explain>
        Quando o próprio governo federal compra ou contrata com dinheiro de emenda (uma obra, equipamentos, um serviço), o pagamento vai direto para a empresa ou entidade.
        Aqui estão as que mais receberam em {ano} ({p.n_empresas.toLocaleString("pt-BR")} ao todo), de quais parlamentares eram as emendas e qual órgão pagou.
        Toque no nome para ver os donos, se o mesmo dono tem outras empresas e todos os documentos.
      </Explain>
      <div className="search"><input aria-label="Procurar empresa ou parlamentar" value={q} onChange={(e) => { setQ(e.target.value); setN(15); }} placeholder="Empresa, CNPJ, parlamentar ou partido" /></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Quem recebeu</th><th className="r">Valor</th></tr></thead>
          <tbody>
            {lista.slice(0, n).map((e) => (
              <tr key={e.cnpj}>
                <td>
                  {e.pagina ? <Link to={`/e/${e.cnpj}`}><strong>{e.nome}</strong></Link> : <strong>{e.nome}</strong>}
                  <div className="small muted">{[e.tipo === "entidade" ? "Entidade sem fins lucrativos" : e.tipo === "empresa" ? "Empresa" : "", cnpjFmt(e.cnpj),
                    `${e.n.toLocaleString("pt-BR")} pagamento${e.n > 1 ? "s" : ""}`].filter(Boolean).join(" · ")}</div>
                  <div className="small">Emendas de {e.autores.map((a, i) => (
                    <Fragment key={i}>{i > 0 && ", "}{a.politico ? <Link to={`/p/${a.politico}`}>{a.nome}</Link> : a.nome}{a.partido && <span className="muted"> ({a.partido})</span>}</Fragment>
                  ))}</div>
                  {e.orgaos.length > 0 && <div className="small muted">Pago por {e.orgaos.map(([o]) => o).join(" e ")}</div>}
                  {!e.pagina && <div className="small"><a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${e.cnpj}`} target="_blank" rel="noreferrer">Ver no Portal da Transparência ↗</a></div>}
                </td>
                <td className="r num">{reais(e.valor)}</td>
              </tr>
            ))}
            {!lista.length && <tr><td colSpan={2} className="muted">Nada encontrado.</td></tr>}
          </tbody>
        </table>
      </div>
      {lista.length > n && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais ({lista.length - n} restantes)</button>}
    </section>
  );
}
