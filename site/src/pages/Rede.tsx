/* Minha rede: acompanhar políticos como uma rede de pessoas, empresas, votações e fontes.
 * A base é pessoal e fica só neste navegador (rede/guardar.ts). Os dados oficiais vêm dos mesmos arquivos do site. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Explain, Loading, useAno, useData } from "../components/ui";
import { FotoPolitico } from "../components/Foto";
import {
  atuacaoAtiva, dataBR, linkSeguro, load, numero, pct, reais, taxaPresenca,
  type EmpresaResumo, type Meta, type Politico, type Resumo, type VotacaoResumo,
} from "../data";
import {
  TIPOS, acharMencoes, baseVazia, apagarFonte, apagarLigacao, apagarObjeto, buscar, idObjeto, juntar, lerExportada,
  ligacoesDe, nomeTipo, normalizar, novidades, sugestoes, vizinhanca, corTipo,
  type Base, type Comparacao, type Fonte, type LinhaComparacao, type Mencao, type NomeConhecido, type Objeto, type TipoObjeto,
} from "../rede/modelo";
import { redeOficial, resolverPedido, type EmendasAno } from "../rede/oficial";
import { carregarBase, exportar, salvarBase } from "../rede/guardar";
import { Grafo } from "../rede/Grafo";

type Aba = "novidades" | "rede" | "fontes" | "buscar" | "comparar";
const ABAS: [Aba, string][] = [["novidades", "Seguidos e novidades"], ["rede", "Rede"], ["fontes", "Fontes"], ["buscar", "Perguntar"], ["comparar", "Comparar"]];
const agora = () => new Date().toISOString();

/** Lê os arquivos oficiais de um político e junta a rede dele na base */
async function trazerPolitico(base: Base, id: string, votacoes: VotacaoResumo[], anos: number[]): Promise<Base> {
  const p = await load<Politico>(`p/${id}.json`);
  const emendas: EmendasAno[] = [];
  for (const a of anos) {
    try { emendas.push(await load<EmendasAno>(`emendas/${a}.json`)); } catch { /* ano sem arquivo de emendas (ou Minas Nossa) */ }
  }
  const r = redeOficial(p, votacoes, emendas, agora());
  const b = juntar(base, r);
  const velho = b.seguidos[id];
  return { ...b, seguidos: { ...b.seguidos, [id]: velho ? { ...velho, atual: r.retrato } : { id, desde: r.retrato.em, atual: r.retrato, visto: r.retrato } } };
}

export default function Rede() {
  const [params, setParams] = useSearchParams();
  const { data: meta } = useData<Meta>("meta.json");
  const { data: politicos, error } = useData<Resumo[]>("politicos.json");
  const { data: votacoes } = useData<VotacaoResumo[]>("votacoes.json");
  const { data: empresas } = useData<EmpresaResumo[]>("empresas.json");
  const [base, setBase] = useState<Base | null>(null);
  const [guarda, setGuarda] = useState(true);
  const [aviso, setAviso] = useState("");
  const [aba, setAba] = useState<Aba>(() => (params.get("aba") as Aba) || "novidades");
  const [sel, setSel] = useState<string | undefined>(params.get("objeto") || undefined);

  useEffect(() => { carregarBase().then((r) => { setBase(r.base); setGuarda(r.guarda); }); }, []);
  // Salva cada mudança na hora (as anotações só mudam ao sair do campo, então não grava a cada tecla)
  const primeira = useRef(true);
  useEffect(() => {
    if (!base) return;
    if (primeira.current) { primeira.current = false; return; }
    salvarBase(base).then(setGuarda);
  }, [base]);
  const mudar = useCallback((f: (b: Base) => Base) => setBase((b) => (b ? f(b) : b)), []);

  // Lê um político e junta na base atual. Quem já era seguido guarda o "visto" (base das novidades).
  const trazer = useCallback(async (id: string) => {
    if (!votacoes || !meta) return false;
    try {
      const r = await trazerPolitico(baseVazia(), id, votacoes, meta.anos);
      const novo = r.seguidos[id];
      setBase((atual) => {
        if (!atual) return atual;
        const b = juntar(atual, { objetos: Object.values(r.objetos), fontes: Object.values(r.fontes), ligacoes: Object.values(r.ligacoes) });
        const velho = atual.seguidos[id];
        return { ...b, seguidos: { ...b.seguidos, [id]: velho ? { ...velho, atual: novo.atual } : novo } };
      });
      return true;
    } catch { return false; }
  }, [votacoes, meta]);
  const seguir = useCallback(async (id: string) => {
    if (await trazer(id)) setSel(idObjeto("politico", id));
    else setAviso(`Não foi possível ler os dados de ${id} agora.`);
  }, [trazer]);

  // Ao abrir: atualiza cada político seguido com os dados de hoje.
  // E segue quem veio no link ?seguir= (ids ou nomes com UF, separados por vírgula: veja resolverPedido)
  const atualizado = useRef(false);
  const pedido = params.get("seguir");
  useEffect(() => {
    if (!base || !votacoes || !meta || !politicos || atualizado.current) return;
    atualizado.current = true;
    (async () => {
      for (const id of Object.keys(base.seguidos)) {
        if (!(await trazer(id))) setAviso(`Não foi possível atualizar ${base.seguidos[id]?.atual.nome || id} agora. Os dados guardados continuam aqui.`);
      }
    })();
  }, [base, votacoes, meta, politicos, trazer]);
  useEffect(() => {
    if (!pedido || !base || !votacoes || !meta || !politicos) return;
    params.delete("seguir"); setParams(params, { replace: true });
    const { ids, faltou } = resolverPedido(pedido, politicos);
    if (faltou.length) setAviso(`Não encontrei: ${faltou.join(", ")}. Procure pelo nome abaixo.`);
    (async () => {
      for (const id of ids) if (!base.seguidos[id] && !(await trazer(id))) setAviso(`Não foi possível ler os dados de ${id} agora.`);
      if (ids.length) setSel(idObjeto("politico", ids[0]));
    })();
  }, [pedido, base, votacoes, meta, politicos, params, setParams, trazer]);

  if (!politicos || !base) return <Loading error={error} />;
  const nObj = Object.keys(base.objetos).length, nLig = Object.keys(base.ligacoes).length, nFon = Object.keys(base.fontes).length;
  const irPara = (id: string) => { setSel(id); setAba("rede"); window.scrollTo(0, 0); };

  return (
    <>
      <p className="eyebrow">Ferramenta pessoal</p>
      <h1>Minha rede<span className="h1-sub">Acompanhe políticos, quem está ligado a eles e de onde vem cada informação</span></h1>
      <Explain>
        Siga um político e a rede dele se monta sozinha com os dados oficiais deste site: empresas pagas com a cota e seus sócios,
        votações, projetos e emendas. Junte suas próprias fontes (notícias, documentos, anotações) e ligue o que encontrar.
        Toda ligação guarda a fonte e o trecho de origem. <strong>A sua rede fica só neste navegador</strong>: ninguém mais vê, nem o site.
      </Explain>
      <div className="rede-barra">
        <span className="muted small">{numero(nObj)} objetos, {numero(nLig)} ligações, {numero(nFon)} fontes</span>
        <button className="btn alt" onClick={() => exportar(base)}>Exportar cópia</button>
        <label className="btn alt">Importar cópia
          <input type="file" accept="application/json,.json" hidden onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try { const b = lerExportada(await f.text()); setBase(b); setAviso(`Cópia importada: ${Object.keys(b.objetos).length} objetos.`); }
            catch (err) { setAviso((err as Error).message); }
            e.target.value = "";
          }} />
        </label>
      </div>
      {!guarda && <p className="alerta" role="alert">Este navegador não deixou guardar a rede (janela anônima ou armazenamento bloqueado). Exporte uma cópia antes de fechar a página.</p>}
      {aviso && <p className="alerta" role="status">{aviso} <button className="link" onClick={() => setAviso("")}>Fechar</button></p>}

      <div className="tabs" role="tablist" aria-label="Partes da Minha rede">
        {ABAS.map(([k, nome]) => (
          <button key={k} role="tab" aria-selected={aba === k} onClick={() => setAba(k)}>{nome}</button>
        ))}
      </div>

      {aba === "novidades" && <Novidades base={base} mudar={mudar} politicos={politicos} votacoes={votacoes || []} meta={meta} seguir={seguir} irPara={irPara} />}
      {aba === "rede" && <AbaRede base={base} mudar={mudar} sel={sel} setSel={setSel} />}
      {aba === "fontes" && <Fontes base={base} mudar={mudar} politicos={politicos} empresas={empresas || []} irPara={irPara} />}
      {aba === "buscar" && <Perguntar base={base} irPara={irPara} />}
      {aba === "comparar" && <Comparar base={base} mudar={mudar} politicos={politicos} meta={meta} />}
    </>
  );
}

/* ---------- Seguidos e novidades ---------- */

function EscolherPolitico({ politicos, onEscolher, rotulo, excluir = [] }: { politicos: Resumo[]; onEscolher: (id: string) => void; rotulo: string; excluir?: string[] }) {
  const [q, setQ] = useState("");
  const achados = useMemo(() => {
    const n = normalizar(q);
    if (n.length < 2) return [];
    return politicos.filter((p) => !excluir.includes(p.id) && [p.nome, ...(p.outros_nomes || [])].some((x) => normalizar(x).includes(n))).slice(0, 8);
  }, [q, politicos, excluir]);
  return (
    <div className="rede-escolher">
      <label>{rotulo}
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Digite um nome" />
      </label>
      {achados.length > 0 && (
        <ul>
          {achados.map((p) => (
            <li key={p.id}>
              <button className="link" onClick={() => { onEscolher(p.id); setQ(""); }}>{p.nome}</button>
              <span className="muted small"> {p.partido}-{p.uf}, {p.cargo}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Novidades({ base, mudar, politicos, votacoes, meta, seguir, irPara }: {
  base: Base; mudar: (f: (b: Base) => Base) => void; politicos: Resumo[]; votacoes: VotacaoResumo[]; meta: Meta | null;
  seguir: (id: string) => void; irPara: (id: string) => void;
}) {
  const seguidos = Object.values(base.seguidos);
  const porId = useMemo(() => new Map(votacoes.map((v) => [v.id, v])), [votacoes]);
  const foto = (id: string) => politicos.find((p) => p.id === id)?.foto;
  return (
    <section>
      <EscolherPolitico politicos={politicos} rotulo="Seguir um político" excluir={Object.keys(base.seguidos)} onEscolher={seguir} />
      <p className="small muted">
        Os dados oficiais do site são atualizados todo dia às 3h17{meta?.atualizado_em ? ` (última vez: ${dataBR(meta.atualizado_em)})` : ""}.
        As novidades aparecem aqui quando você abre esta página, comparando com a última vez que você marcou como visto.
      </p>
      {!seguidos.length && <div className="empty">Você ainda não segue ninguém. Procure um nome acima ou use o botão "Acompanhar na Minha rede" na página de um político.</div>}
      <div className="grid-2">
        {seguidos.map((s) => {
          const nov = novidades(s.visto, s.atual);
          return (
            <article key={s.id} className="card">
              <div className="rede-seguido">
                <FotoPolitico url={foto(s.id)} nome={s.atual.nome} tamanho={52} />
                <div>
                  <h3><Link to={`/p/${s.id}`}>{s.atual.nome}</Link></h3>
                  <span className="muted small">{s.atual.partido} · segue desde {dataBR(s.desde)} · visto em {dataBR(s.visto.em)}</span>
                </div>
              </div>
              {nov.length ? (
                <ul className="rede-novidades">
                  {nov.map((n, i) => (
                    <li key={i}>
                      <strong>{n.texto}</strong>{n.valor != null && <> : {reais(n.valor)}</>}
                      {n.tipo === "voto" && (
                        <ul>{n.ids!.slice(0, 5).map((v) => { const vt = porId.get(v); return vt ? <li key={v}><Link to={`/v/${v}`}>{dataBR(vt.data)}: {vt.proposicao?.titulo || vt.descricao.slice(0, 90)}</Link></li> : null; })}
                          {n.ids!.length > 5 && <li className="muted">e mais {n.ids!.length - 5}</li>}</ul>
                      )}
                      {n.tipo === "empresa" && (
                        <ul>{n.ids!.slice(0, 5).map((d) => <li key={d}><button className="link" onClick={() => irPara(idObjeto("empresa", d))}>{s.atual.empresas[d]}</button></li>)}</ul>
                      )}
                    </li>
                  ))}
                </ul>
              ) : <p className="muted small">Nada novo desde a última visita.</p>}
              <div className="rede-acoes">
                {nov.length > 0 && <button className="btn" onClick={() => mudar((b) => ({ ...b, seguidos: { ...b.seguidos, [s.id]: { ...s, visto: s.atual } } }))}>Marcar como visto</button>}
                <button className="btn alt" onClick={() => irPara(idObjeto("politico", s.id))}>Ver a rede</button>
                <button className="link" onClick={() => mudar((b) => { const x = { ...b.seguidos }; delete x[s.id]; return { ...b, seguidos: x }; })}>Deixar de seguir</button>
              </div>
            </article>
          );
        })}
      </div>
      <Sugestoes base={base} mudar={mudar} irPara={irPara} />
    </section>
  );
}

/** Ligações que você ainda não fez: objetos com vizinhos em comum */
function Sugestoes({ base, mudar, irPara }: { base: Base; mudar: (f: (b: Base) => Base) => void; irPara: (id: string) => void }) {
  const lista = useMemo(() => sugestoes(base, 12), [base]);
  if (!lista.length) return null;
  const nome = (id: string) => base.objetos[id]?.nome || id;
  return (
    <section>
      <h2>Conexões que você ainda não fez</h2>
      <p className="small muted">Objetos que não estão ligados entre si, mas têm ligações em comum (por exemplo, dois políticos que pagaram a mesma empresa).</p>
      <ul className="rede-lista">
        {lista.map((s) => (
          <li key={s.a + s.b}>
            <button className="link" onClick={() => irPara(s.a)}>{nome(s.a)}</button> e <button className="link" onClick={() => irPara(s.b)}>{nome(s.b)}</button>
            <span className="muted small"> têm em comum: {s.comuns.slice(0, 3).map(nome).join(", ")}{s.comuns.length > 3 ? ` e mais ${s.comuns.length - 3}` : ""}</span>{" "}
            <button className="chip" onClick={() => mudar((b) => {
              const fid = `deducao:${s.a}|${s.b}`;
              return juntar(b, {
                fontes: [{ id: fid, tipo: "texto", titulo: `Dedução da Minha rede: ${nome(s.a)} e ${nome(s.b)}`, em: agora(),
                  texto: `${nome(s.a)} e ${nome(s.b)} têm ligações com: ${s.comuns.map(nome).join(", ")}.` }],
                ligacoes: [{ de: s.a, para: s.b, tipo: "tem ligação em comum com", fonte: fid, manual: true }],
              });
            })}>Ligar</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* ---------- Rede (grafo e painel do objeto) ---------- */

function AbaRede({ base, mudar, sel, setSel }: { base: Base; mudar: (f: (b: Base) => Base) => void; sel?: string; setSel: (id?: string) => void }) {
  const [centro, setCentro] = useState<string | undefined>(sel);
  const [passos, setPassos] = useState(1);
  // Votações ligam muita coisa e escondem o resto: começam escondidas (um clique mostra)
  const [tiposFora, setTiposFora] = useState<TipoObjeto[]>(["evento"]);
  useEffect(() => { if (sel && !centro) setCentro(sel); }, [sel, centro]);
  const objetos = useMemo(() => Object.values(base.objetos).sort((a, b) => (a.tipo === "politico" ? -1 : 0) - (b.tipo === "politico" ? -1 : 0) || a.nome.localeCompare(b.nome)), [base]);
  const c = centro && base.objetos[centro] ? centro : Object.keys(base.seguidos).map((id) => idObjeto("politico", id)).find((id) => base.objetos[id]) || objetos[0]?.id;
  const viz = useMemo(() => {
    if (!c) return { objetos: [], ligacoes: [] };
    // Tira os tipos escondidos antes de andar pela rede: o que só se ligava por eles também sai
    const fica = (id: string) => id === c || (!!base.objetos[id] && !tiposFora.includes(base.objetos[id].tipo));
    const filtrada: Base = { ...base, ligacoes: Object.fromEntries(Object.entries(base.ligacoes).filter(([, l]) => fica(l.de) && fica(l.para))) };
    return vizinhanca(filtrada, c, passos, passos > 1 ? 150 : 90);
  }, [base, c, passos, tiposFora]);
  if (!objetos.length) return <div className="empty">A rede está vazia. Siga um político ou adicione uma fonte para começar.</div>;
  return (
    <section>
      <div className="rede-filtros">
        <label>Centro da rede
          <select value={c} onChange={(e) => { setCentro(e.target.value); setSel(e.target.value); }}>
            {objetos.map((o) => <option key={o.id} value={o.id}>{o.nome} ({nomeTipo(o.tipo)})</option>)}
          </select>
        </label>
        <label>Distância
          <select value={passos} onChange={(e) => setPassos(Number(e.target.value))}>
            <option value={1}>Ligações diretas</option>
            <option value={2}>Até 2 passos</option>
          </select>
        </label>
        <fieldset>
          <legend className="small muted">Mostrar</legend>
          {TIPOS.filter((t) => objetos.some((o) => o.tipo === t.tipo)).map((t) => (
            <label key={t.tipo} className="small">
              <input type="checkbox" checked={!tiposFora.includes(t.tipo)} onChange={(e) => setTiposFora((f) => e.target.checked ? f.filter((x) => x !== t.tipo) : [...f, t.tipo])} />
              {" "}{t.nome}
            </label>
          ))}
        </fieldset>
      </div>
      <div className="rede-corpo">
        <Grafo objetos={viz.objetos} ligacoes={viz.ligacoes} centro={c} selecionado={sel} onSelecionar={(id) => setSel(id)} />
        {sel && base.objetos[sel] && <Painel base={base} mudar={mudar} id={sel} setSel={setSel} centralizar={() => setCentro(sel)} />}
      </div>
      <NovoObjeto mudar={mudar} onCriado={(id) => { setSel(id); setCentro(id); }} />
    </section>
  );
}

function LinkFonte({ f }: { f?: Fonte }) {
  if (!f) return null;
  const url = linkSeguro(f.url);
  return url ? <a href={url} target="_blank" rel="noopener noreferrer">{f.titulo}</a> : <span>{f.titulo}</span>;
}

function Painel({ base, mudar, id, setSel, centralizar }: { base: Base; mudar: (f: (b: Base) => Base) => void; id: string; setSel: (id?: string) => void; centralizar: () => void }) {
  const o = base.objetos[id];
  const ligs = useMemo(() => ligacoesDe(base, id).sort((a, b) => (b.data || "").localeCompare(a.data || "")), [base, id]);
  const [mostrar, setMostrar] = useState(25);
  return (
    <aside className="card rede-painel" aria-label={`Sobre ${o.nome}`}>
      <span className="chip" style={{ color: corTipo(o.tipo), borderColor: "currentColor" }}>{nomeTipo(o.tipo)}</span>
      <h2>{o.nome}</h2>
      <div className="rede-acoes">
        <button className="btn alt" onClick={centralizar}>Pôr no centro</button>
        {o.ref && <Link to={o.ref}>Abrir a página no site</Link>}
      </div>
      <label className="small">Suas anotações
        <textarea rows={3} defaultValue={o.notas || ""} key={o.id}
          onBlur={(e) => { const v = e.target.value; mudar((b) => ({ ...b, objetos: { ...b.objetos, [id]: { ...b.objetos[id], notas: v } } })); }} />
      </label>
      <h3>{ligs.length} {ligs.length === 1 ? "ligação" : "ligações"}</h3>
      <ul className="rede-ligacoes">
        {ligs.slice(0, mostrar).map((l) => {
          const outro = base.objetos[l.de === id ? l.para : l.de];
          const f = base.fontes[l.fonte];
          return (
            <li key={l.id}>
              {l.de === id && <>{l.tipo} </>}
              <button className="link" onClick={() => setSel(outro?.id)}>{outro?.nome}</button>
              {l.de !== id && <> {l.tipo} {o.nome}</>}
              {l.valor != null && <> · {reais(l.valor)}</>}{l.data && <> · {l.data.length === 10 ? dataBR(l.data) : l.data}</>}
              {l.trecho && <blockquote className="small">{l.trecho}</blockquote>}
              <span className="small muted">Fonte: <LinkFonte f={f} />{f?.tipo === "texto" ? " (sua)" : ""}</span>
              {l.manual && <> <button className="link small" onClick={() => mudar((b) => apagarLigacao(b, l.id))}>apagar ligação</button></>}
            </li>
          );
        })}
      </ul>
      {ligs.length > mostrar && <button className="link" onClick={() => setMostrar((m) => m + 50)}>Mostrar mais</button>}
      <NovaLigacao base={base} mudar={mudar} de={id} />
      <button className="link small" onClick={() => { if (confirm(`Apagar ${o.nome} e as ligações dele da sua rede?`)) { mudar((b) => apagarObjeto(b, id)); setSel(undefined); } }}>Apagar este objeto da minha rede</button>
    </aside>
  );
}

function NovoObjeto({ mudar, onCriado }: { mudar: (f: (b: Base) => Base) => void; onCriado: (id: string) => void }) {
  const [tipo, setTipo] = useState<TipoObjeto>("pessoa");
  const [nome, setNome] = useState("");
  return (
    <form className="rede-form" onSubmit={(e) => {
      e.preventDefault();
      if (!nome.trim()) return;
      const id = idObjeto(tipo, nome.trim());
      mudar((b) => juntar(b, { objetos: [{ id, tipo, nome: nome.trim() }] }));
      setNome("");
      onCriado(id);
    }}>
      <h3>Novo objeto</h3>
      <label>Tipo <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoObjeto)}>{TIPOS.map((t) => <option key={t.tipo} value={t.tipo}>{t.nome}</option>)}</select></label>
      <label>Nome <input value={nome} onChange={(e) => setNome(e.target.value)} required /></label>
      <button className="btn" type="submit">Criar</button>
    </form>
  );
}

/** Liga o objeto aberto a outro, sempre com fonte: uma já guardada ou uma anotação nova (título, link e trecho) */
function NovaLigacao({ base, mudar, de }: { base: Base; mudar: (f: (b: Base) => Base) => void; de: string }) {
  const [para, setPara] = useState("");
  const [tipo, setTipo] = useState("");
  const [fonte, setFonte] = useState("");
  const [titulo, setTitulo] = useState("");
  const [url, setUrl] = useState("");
  const [trecho, setTrecho] = useState("");
  const opcoes = useMemo(() => Object.values(base.objetos).filter((o) => o.id !== de).sort((a, b) => a.nome.localeCompare(b.nome)), [base, de]);
  const fontes = useMemo(() => Object.values(base.fontes).sort((a, b) => b.em.localeCompare(a.em)).slice(0, 200), [base]);
  return (
    <form className="rede-form" onSubmit={(e) => {
      e.preventDefault();
      if (!para || !tipo.trim() || (!fonte && !titulo.trim())) return;
      const fid = fonte || `texto:${Date.now().toString(36)}`;
      mudar((b) => juntar(b, {
        fontes: fonte ? [] : [{ id: fid, tipo: "texto", titulo: titulo.trim(), url: linkSeguro(url), em: agora(), texto: trecho || undefined }],
        ligacoes: [{ de, para, tipo: tipo.trim(), fonte: fid, trecho: trecho || undefined, manual: true }],
      }));
      setPara(""); setTipo(""); setTrecho(""); setTitulo(""); setUrl("");
    }}>
      <h3>Nova ligação</h3>
      <label>Com <select value={para} onChange={(e) => setPara(e.target.value)} required>
        <option value="">Escolha</option>
        {opcoes.map((o) => <option key={o.id} value={o.id}>{o.nome} ({nomeTipo(o.tipo)})</option>)}
      </select></label>
      <label>Que ligação (ex.: "é assessor de", "doou para") <input value={tipo} onChange={(e) => setTipo(e.target.value)} required /></label>
      <label>Fonte <select value={fonte} onChange={(e) => setFonte(e.target.value)}>
        <option value="">Nova fonte (escreva abaixo)</option>
        {fontes.map((f) => <option key={f.id} value={f.id}>{f.titulo.slice(0, 90)}</option>)}
      </select></label>
      {!fonte && <>
        <label>Título da fonte <input value={titulo} onChange={(e) => setTitulo(e.target.value)} required /></label>
        <label>Link (opcional) <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></label>
      </>}
      <label>Trecho que mostra a ligação <textarea rows={2} value={trecho} onChange={(e) => setTrecho(e.target.value)} /></label>
      <button className="btn" type="submit">Ligar</button>
    </form>
  );
}

/* ---------- Fontes próprias ---------- */

/** Texto de um arquivo HTML sem as marcações (o navegador faz isso sem rodar nada do arquivo) */
function textoDeHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("script,style,noscript").forEach((n) => n.remove());
  return (doc.body?.textContent || "").replace(/\s+/g, " ").trim();
}

function Fontes({ base, mudar, politicos, empresas, irPara }: {
  base: Base; mudar: (f: (b: Base) => Base) => void; politicos: Resumo[]; empresas: EmpresaResumo[]; irPara: (id: string) => void;
}) {
  const [titulo, setTitulo] = useState("");
  const [url, setUrl] = useState("");
  const [data, setData] = useState("");
  const [texto, setTexto] = useState("");
  const [lida, setLida] = useState<{ fonte: Fonte; mencoes: Mencao[] } | null>(null);
  const conhecidos: NomeConhecido[] = useMemo(() => [
    ...politicos.map((p) => ({ id: idObjeto("politico", p.id), tipo: "politico" as const, nome: p.nome, ref: `/p/${p.id}`, variantes: p.outros_nomes })),
    ...empresas.map((e) => ({ id: idObjeto("empresa", e.cnpj), tipo: "empresa" as const, nome: e.nome, ref: `/e/${e.cnpj}` })),
    ...Object.values(base.objetos).filter((o) => o.tipo !== "afirmacao" && o.tipo !== "evento").map((o) => ({ id: o.id, tipo: o.tipo, nome: o.nome, ref: o.ref })),
  ], [politicos, empresas, base.objetos]);
  const proprias = Object.values(base.fontes).filter((f) => f.tipo === "texto" && !f.id.startsWith("deducao:")).sort((a, b) => b.em.localeCompare(a.em));
  const usos = (fid: string) => Object.values(base.ligacoes).filter((l) => l.fonte === fid).length;

  return (
    <section>
      <form className="rede-form largo" onSubmit={(e) => {
        e.preventDefault();
        if (!titulo.trim() || !texto.trim()) return;
        const f: Fonte = { id: `texto:${Date.now().toString(36)}`, tipo: "texto", titulo: titulo.trim(), url: linkSeguro(url), data: data || undefined, em: agora(), texto: texto.trim() };
        mudar((b) => juntar(b, { fontes: [f] }));
        setLida({ fonte: f, mencoes: acharMencoes(f.texto!, conhecidos) });
        setTitulo(""); setUrl(""); setData(""); setTexto("");
      }}>
        <h2>Adicionar uma fonte</h2>
        <p className="small muted">Cole o texto de uma notícia, documento, transcrição ou anotação, ou escolha um arquivo de texto (.txt, .md, .html).
          O texto fica guardado só aqui. Em seguida, mostramos os políticos e empresas citados para você ligar.</p>
        <label>Título <input value={titulo} onChange={(e) => setTitulo(e.target.value)} required /></label>
        <label>Link do original (opcional) <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></label>
        <label>Data do documento (opcional) <input type="date" value={data} onChange={(e) => setData(e.target.value)} /></label>
        <label>Texto <textarea rows={8} value={texto} onChange={(e) => setTexto(e.target.value)} required /></label>
        <label className="small">Ou ler de um arquivo
          <input type="file" accept=".txt,.md,.html,.htm,text/plain,text/html,text/markdown" onChange={async (e) => {
            const arq = e.target.files?.[0];
            if (!arq) return;
            const bruto = await arq.text();
            setTexto(/\.html?$/i.test(arq.name) || arq.type === "text/html" ? textoDeHtml(bruto) : bruto);
            if (!titulo) setTitulo(arq.name.replace(/\.[^.]+$/, ""));
          }} />
        </label>
        <button className="btn" type="submit">Guardar e procurar nomes</button>
      </form>

      {lida && <Mencoes base={base} mudar={mudar} lida={lida} fechar={() => setLida(null)} irPara={irPara} />}

      <h2>Suas fontes</h2>
      {!proprias.length && <div className="empty">Nenhuma fonte sua ainda.</div>}
      <ul className="rede-lista">
        {proprias.map((f) => (
          <li key={f.id}>
            <LinkFonte f={f} /> <span className="muted small">{f.data ? `de ${dataBR(f.data)}, ` : ""}guardada em {dataBR(f.em)} · {usos(f.id)} {usos(f.id) === 1 ? "ligação" : "ligações"}</span>{" "}
            <button className="link small" onClick={() => setLida({ fonte: f, mencoes: acharMencoes(f.texto || "", conhecidos) })}>procurar nomes de novo</button>{" "}
            <button className="link small" onClick={() => { if (confirm(`Apagar a fonte "${f.titulo}" e as ligações que dependem dela?`)) mudar((b) => apagarFonte(b, f.id)); }}>apagar</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Nomes encontrados numa fonte. Cada frase marcada vira uma afirmação, ligada a quem ela cita, com o trecho como prova. */
function Mencoes({ base, mudar, lida, fechar, irPara }: { base: Base; mudar: (f: (b: Base) => Base) => void; lida: { fonte: Fonte; mencoes: Mencao[] }; fechar: () => void; irPara: (id: string) => void }) {
  const { fonte, mencoes } = lida;
  // Frases que citam alguém, com quem cada uma cita
  const porFrase = useMemo(() => {
    const m = new Map<string, Mencao["conhecido"][]>();
    for (const x of mencoes) for (const t of x.trechos) m.set(t, [...(m.get(t) || []), x.conhecido]);
    return [...m.entries()];
  }, [mencoes]);
  const [marcadas, setMarcadas] = useState<Set<string>>(() => new Set(porFrase.map(([f]) => f)));
  if (!mencoes.length) return <p className="alerta" role="status">Nenhum político ou empresa conhecida aparece em "{fonte.titulo}". Você ainda pode ligar a fonte à mão na aba Rede. <button className="link" onClick={fechar}>Fechar</button></p>;
  const guardar = () => {
    mudar((b) => {
      const objetos: Objeto[] = [];
      const ligacoes: Parameters<typeof juntar>[1]["ligacoes"] = [];
      for (const [frase, quem] of porFrase) {
        if (!marcadas.has(frase)) continue;
        const af = idObjeto("afirmacao", `${fonte.id} ${frase}`);
        objetos.push({ id: af, tipo: "afirmacao", nome: frase.length > 140 ? frase.slice(0, 138) + "…" : frase, notas: frase });
        for (const c of quem) {
          if (!b.objetos[c.id]) objetos.push({ id: c.id, tipo: c.tipo, nome: c.nome, ref: c.ref });
          ligacoes.push({ de: c.id, para: af, tipo: "é citado em", fonte: fonte.id, trecho: frase, data: fonte.data, manual: true });
        }
        // Dois nomes na mesma frase: ligação direta entre eles, com a frase como prova
        for (let i = 0; i < quem.length; i++) for (let j = i + 1; j < quem.length; j++)
          ligacoes.push({ de: quem[i].id, para: quem[j].id, tipo: "aparece junto com", fonte: fonte.id, trecho: frase, data: fonte.data, manual: true });
      }
      return juntar(b, { objetos, ligacoes });
    });
    fechar();
  };
  return (
    <section className="card">
      <h3>Encontrado em "{fonte.titulo}"</h3>
      <p className="small">
        {mencoes.map((m, i) => <span key={m.conhecido.id}>{i > 0 && ", "}
          {base.objetos[m.conhecido.id] ? <button className="link" onClick={() => irPara(m.conhecido.id)}>{m.conhecido.nome}</button> : m.conhecido.nome}
          <span className="muted"> ({m.trechos.length})</span></span>)}
      </p>
      <p className="small muted">Marque as frases que são afirmações que valem guardar. Cada uma vira um objeto ligado a quem ela cita, com a frase como prova.</p>
      <ul className="rede-frases">
        {porFrase.map(([frase, quem]) => (
          <li key={frase}>
            <label>
              <input type="checkbox" checked={marcadas.has(frase)} onChange={(e) => setMarcadas((s) => { const n = new Set(s); if (e.target.checked) n.add(frase); else n.delete(frase); return n; })} />
              {" "}{frase} <span className="muted small">({quem.map((q) => q.nome).join(", ")})</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="rede-acoes">
        <button className="btn" onClick={guardar} disabled={!marcadas.size}>Guardar {marcadas.size} {marcadas.size === 1 ? "afirmação" : "afirmações"}</button>
        <button className="link" onClick={fechar}>Agora não</button>
      </div>
    </section>
  );
}

/* ---------- Perguntar ---------- */

function Perguntar({ base, irPara }: { base: Base; irPara: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [feita, setFeita] = useState("");
  const res = useMemo(() => (feita ? buscar(base, feita, 15) : []), [base, feita]);
  return (
    <section>
      <form className="rede-form largo" onSubmit={(e) => { e.preventDefault(); setFeita(q); }}>
        <label>Pergunte à sua rede <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex.: quem são os sócios das empresas pagas? como votou sobre saúde?" /></label>
        <button className="btn" type="submit">Procurar</button>
      </form>
      <p className="small muted">A resposta são os trechos das suas fontes e das ligações oficiais que mais combinam com a pergunta, cada um com o link para o original.</p>
      {feita && !res.length && <div className="empty">Nada encontrado para "{feita}".</div>}
      <ol className="rede-trechos">
        {res.map((t, i) => (
          <li key={i}>
            <p>{t.texto}</p>
            <span className="small muted">Fonte: <LinkFonte f={base.fontes[t.fonte]} />{t.objetos && <> · {t.objetos.map((o) => base.objetos[o] && <button key={o} className="link" onClick={() => irPara(o)}>{base.objetos[o].nome}</button>).reduce<React.ReactNode[]>((a, x, k) => k ? [...a, ", ", x] : [x], [])}</>}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ---------- Comparar ---------- */

const METRICAS: { chave: string; nome: string; fmt: (v: number) => string; explica: string }[] = [
  { chave: "cota", nome: "Cota parlamentar no ano", fmt: (v) => reais(v), explica: "Reembolsos com nota fiscal" },
  { chave: "custo", nome: "Custo total no ano", fmt: (v) => reais(v), explica: "Cota, salário, verba de gabinete e outros, quando a página oficial publica" },
  { chave: "presenca", nome: "Presença no Plenário", fmt: (v) => pct(v), explica: "Parte das sessões em que esteve presente" },
  { chave: "projetos", nome: "Projetos como primeiro autor", fmt: (v) => numero(v), explica: "No ano" },
  { chave: "requerimentos", nome: "Requerimentos e indicações", fmt: (v) => numero(v), explica: "No ano" },
  { chave: "discursos", nome: "Discursos", fmt: (v) => numero(v), explica: "No ano" },
  { chave: "governo", nome: "Votou com o governo", fmt: (v) => pct(v), explica: "Nas votações nominais com orientação do governo" },
  { chave: "fidelidade", nome: "Votou com o partido", fmt: (v) => pct(v), explica: "Nas votações com orientação do partido" },
  { chave: "posicao", nome: "Posição (0 esquerda, 100 direita)", fmt: (v) => String(Math.round(v * 100)), explica: "Pelos votos, o mesmo critério para todos" },
  { chave: "n_votos", nome: "Votos nominais registrados", fmt: (v) => numero(v), explica: "Na legislatura" },
];

function linha(p: Resumo, ano: string): LinhaComparacao {
  const a = p.por_ano[ano];
  const at = atuacaoAtiva(a?.atuacao) ? a!.atuacao! : undefined;
  return {
    id: p.id, nome: p.nome, partido: p.partido, uf: p.uf,
    valores: {
      cota: a?.total ?? null, custo: a?.custo_total ?? null, presenca: taxaPresenca(at?.plenario),
      projetos: at?.projetos ?? null, requerimentos: at?.requerimentos ?? null, discursos: at?.discursos ?? null,
      governo: p.alinhamento_governo, fidelidade: p.fidelidade_partido, posicao: p.posicao, n_votos: p.n_votos,
    },
  };
}

function Comparar({ base, mudar, politicos, meta }: { base: Base; mudar: (f: (b: Base) => Base) => void; politicos: Resumo[]; meta: Meta | null }) {
  const { ano } = useAno();
  const [ids, setIds] = useState<string[]>(() => Object.keys(base.seguidos).slice(0, 4));
  const [nome, setNome] = useState("");
  const [aberta, setAberta] = useState<Comparacao | null>(null);
  const porId = useMemo(() => new Map(politicos.map((p) => [p.id, p])), [politicos]);
  const linhas = ids.map((id) => porId.get(id)).filter(Boolean).map((p) => linha(p!, ano));
  return (
    <section>
      <EscolherPolitico politicos={politicos} rotulo="Adicionar à comparação" excluir={ids} onEscolher={(id) => setIds((x) => [...x, id].slice(0, 6))} />
      {linhas.length > 0 ? (
        <>
          <TabelaComparacao linhas={linhas} remover={(id) => setIds((x) => x.filter((y) => y !== id))} />
          <p className="small muted">Ano {ano}. Fonte: dados abertos da Câmara e do Senado, coletados por este site{meta?.atualizado_em ? ` (atualizado em ${dataBR(meta.atualizado_em)})` : ""}. Abra cada político para ver o link oficial de cada número.</p>
          <form className="rede-form" onSubmit={(e) => {
            e.preventDefault();
            const c: Comparacao = { id: Date.now().toString(36), nome: nome.trim() || linhas.map((l) => l.nome).join(" × "), em: agora(), ano, linhas };
            mudar((b) => ({ ...b, comparacoes: [c, ...b.comparacoes] }));
            setNome("");
          }}>
            <label>Nome da comparação (opcional) <input value={nome} onChange={(e) => setNome(e.target.value)} /></label>
            <button className="btn" type="submit">Guardar comparação</button>
          </form>
        </>
      ) : <div className="empty">Escolha dois ou mais políticos para comparar.</div>}

      <h2>Comparações guardadas</h2>
      {!base.comparacoes.length && <p className="muted">Nenhuma ainda. Ao guardar, os números do dia ficam salvos, e depois você vê o que mudou.</p>}
      <ul className="rede-lista">
        {base.comparacoes.map((c) => (
          <li key={c.id}>
            <button className="link" onClick={() => setAberta(aberta?.id === c.id ? null : c)}>{c.nome}</button>
            <span className="muted small"> guardada em {dataBR(c.em)}, ano {c.ano}</span>{" "}
            <button className="link small" onClick={() => mudar((b) => ({ ...b, comparacoes: b.comparacoes.filter((x) => x.id !== c.id) }))}>apagar</button>
            {aberta?.id === c.id && (
              <>
                <TabelaComparacao linhas={c.linhas} hoje={c.linhas.map((l) => porId.get(l.id)).filter(Boolean).map((p) => linha(p!, c.ano))} />
                <p className="small muted">Entre parênteses, quanto mudou desde que a comparação foi guardada.</p>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function TabelaComparacao({ linhas, hoje, remover }: { linhas: LinhaComparacao[]; hoje?: LinhaComparacao[]; remover?: (id: string) => void }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th scope="col">Indicador</th>{linhas.map((l) => (
            <th key={l.id} scope="col"><Link to={`/p/${l.id}`}>{l.nome}</Link> <span className="muted small">{l.partido}-{l.uf}</span>
              {remover && <> <button className="link small" onClick={() => remover(l.id)} aria-label={`Tirar ${l.nome}`}>tirar</button></>}</th>
          ))}</tr>
        </thead>
        <tbody>
          {METRICAS.map((m) => {
            const vals = linhas.map((l) => l.valores[m.chave]);
            const maior = Math.max(...vals.map((v) => v ?? -Infinity));
            return (
              <tr key={m.chave}>
                <th scope="row">{m.nome}<br /><span className="muted small">{m.explica}</span></th>
                {linhas.map((l, i) => {
                  const v = vals[i];
                  const h = hoje?.find((x) => x.id === l.id)?.valores[m.chave];
                  const dif = h != null && v != null && Math.abs(h - v) > 1e-9 ? h - v : null;
                  return (
                    <td key={l.id} className="num" style={v === maior && linhas.length > 1 ? { fontWeight: 800 } : undefined}>
                      {v == null ? "—" : m.fmt(v)}
                      {dif != null && <span className="small muted"> ({dif > 0 ? "+" : "−"}{m.fmt(Math.abs(dif))})</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

