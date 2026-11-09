/* Visões da Minha rede, pensadas para ler de relance: rostos grandes, grupos em blocos e ligações claras.
 * - Mapa do político: um político no centro e, em volta, em blocos, para quem foi o dinheiro e como votou.
 * - Lado a lado: uma coluna por político, as mesmas linhas para todos; o que se repete ganha destaque.
 * - Ranking: barras com foto, de quem tem mais para quem tem menos.
 * - Em comum: os políticos como estações e, nas linhas entre eles, cada empresa, dono ou lugar que dividem.
 * - Círculo: os políticos no anel de dentro e o que se liga a cada um no anel de fora.
 * Clicar em qualquer coisa abre a ficha dela (com a fonte de cada ligação). */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FotoPolitico } from "../components/Foto";
import { dataBR, numero, reais, reaisCurto } from "../data";
import { corTipo, nomeTipo, type Base } from "./modelo";
import { MEDIDAS, dossie, emComum, quemSeLiga, ranking, type Dossie, type Item, type Medida } from "./visoes";

export type Fotos = (siteId: string) => string | undefined;
const SERIES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--c4)", "var(--c5)", "var(--c7)", "var(--c8)", "var(--c6)"];
export const corSerie = (i: number) => SERIES[i % SERIES.length];

/** Duas letras para o selo de uma empresa, pessoa ou lugar (não há logotipo oficial nos dados) */
function sigla(nome: string): string {
  const ps = nome.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter((p) => p.length > 2 && !/^(ltda|eireli|me|epp|s\/a|sa|de|da|do|dos|das)$/i.test(p));
  const x = ps.length ? ps : [nome];
  return (x.length > 1 ? x[0][0] + x[1][0] : x[0].slice(0, 2)).toUpperCase();
}

function Selo({ item, tamanho = 34 }: { item: Item; tamanho?: number }) {
  return <span className="selo-obj" style={{ width: tamanho, height: tamanho, background: corTipo(item.tipo), fontSize: Math.round(tamanho * 0.36) }} aria-hidden="true">{sigla(item.nome)}</span>;
}

/** Marca de "também ligado a outro político que você segue" */
function Comum({ id, comum, nomes }: { id: string; comum: Map<string, string[]>; nomes: (s: string) => string }) {
  const quem = comum.get(id);
  if (!quem || quem.length < 2) return null;
  return <span className="marca-comum" title={`Ligado a ${quem.map(nomes).join(", ")}`}>em comum com {quem.length - 1}</span>;
}

/* ---------- Mapa do político (cadeia em blocos) ---------- */

export function MapaPolitico({ base, siteId, fotos, onAbrir }: { base: Base; siteId: string; fotos: Fotos; onAbrir: (id: string) => void }) {
  const d = useMemo(() => dossie(base, siteId), [base, siteId]);
  const comum = useMemo(() => quemSeLiga(base, Object.keys(base.seguidos)), [base]);
  const nomes = (s: string) => base.seguidos[s]?.atual.nome || s;
  const [todas, setTodas] = useState(false);
  if (!d) return <div className="empty">Este político ainda não tem dados na sua rede.</div>;
  const s = base.seguidos[siteId];
  const maior = d.empresas[0]?.valor || 1;
  const empresas = todas ? d.empresas : d.empresas.slice(0, 8);
  return (
    <div className="palco mapa">
      <div className="mapa-centro">
        <FotoPolitico url={fotos(siteId)} nome={d.nome} tamanho={132} />
        <h2>{d.nome}</h2>
        <p>{[d.partido?.nome, d.mandato].filter(Boolean).join(" · ")}</p>
        <div className="mapa-numeros">
          {s && <span><strong>{reaisCurto(s.atual.cota)}</strong> cota em {s.atual.ano}</span>}
          <span><strong>{numero(d.empresas.length)}</strong> empresas pagas</span>
          {s && s.atual.emendas > 0 && <span><strong>{reaisCurto(s.atual.emendas)}</strong> em emendas</span>}
          {s && <span><strong>{numero(s.atual.votos.length)}</strong> votos</span>}
        </div>
        {d.ref && <Link className="btn alt claro" to={d.ref}>Abrir o perfil completo</Link>}
      </div>

      <div className="mapa-blocos">
        <section className="bloco largo" aria-labelledby="b-cota">
          <h3 id="b-cota"><span className="ponto" style={{ background: "var(--s2)" }} />Dinheiro da cota: quem recebeu</h3>
          {!d.empresas.length && <p className="vazio">Nenhuma empresa na cota.</p>}
          <ul className="cadeia">
            {empresas.map((e) => (
              <li key={e.id}>
                <button className="cartao-obj" onClick={() => onAbrir(e.id)}>
                  <Selo item={e} />
                  <span className="nome">{e.nome}</span>
                  <span className="valor">{reais(e.valor || 0)}</span>
                  <span className="barra"><i style={{ width: `${Math.max(3, ((e.valor || 0) / maior) * 100)}%` }} /></span>
                  <Comum id={e.id} comum={comum} nomes={nomes} />
                </button>
                {e.socios.length > 0 && (
                  <div className="donos">
                    <span className="seta-dono" aria-hidden="true">↳</span>
                    <span className="small">{e.socios.length === 1 ? "Dono:" : "Donos:"}</span>
                    {e.socios.slice(0, 4).map((p) => (
                      <button key={p.id} className="chip-obj" onClick={() => onAbrir(p.id)}>{p.nome}<Comum id={p.id} comum={comum} nomes={nomes} /></button>
                    ))}
                    {e.socios.length > 4 && <span className="small">e mais {e.socios.length - 4}</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
          {d.empresas.length > 8 && <button className="link claro" onClick={() => setTodas(!todas)}>{todas ? "Mostrar só as 8 maiores" : `Ver todas as ${d.empresas.length}`}</button>}
        </section>

        <section className="bloco" aria-labelledby="b-emendas">
          <h3 id="b-emendas"><span className="ponto" style={{ background: "var(--c8)" }} />Emendas Pix: para onde foi</h3>
          {!d.lugares.length && <p className="vazio">Nenhuma emenda Pix com destino registrado.</p>}
          <ul className="lista-obj">
            {d.lugares.slice(0, 8).map((l) => (
              <li key={l.id}><button className="cartao-obj fino" onClick={() => onAbrir(l.id)}><Selo item={l} tamanho={28} /><span className="nome">{l.nome}</span><span className="valor">{reais(l.valor || 0)}</span><Comum id={l.id} comum={comum} nomes={nomes} /></button></li>
            ))}
          </ul>
        </section>

        <section className="bloco" aria-labelledby="b-votos">
          <h3 id="b-votos"><span className="ponto" style={{ background: "var(--c4)" }} />Como votou por último</h3>
          {!d.votos.length && <p className="vazio">Sem votações na rede.</p>}
          <ul className="lista-obj">
            {d.votos.slice(0, 6).map((v) => (
              <li key={v.id}><button className="cartao-obj fino" onClick={() => onAbrir(v.id)}>
                <span className={`voto-selo ${/^sim/i.test(v.detalhe || "") ? "sim" : /^n[aã]o/i.test(v.detalhe || "") ? "nao" : ""}`}>{v.detalhe}</span>
                <span className="nome">{v.nome.replace(/^Votação \d\d\/\d\d\/\d{4}:?\s*/, "") || v.nome}</span>
                {v.data && <span className="valor">{dataBR(v.data)}</span>}
              </button></li>
            ))}
          </ul>
        </section>

        {(d.citacoes.length > 0 || d.outros.length > 0) && (
          <section className="bloco" aria-labelledby="b-fontes">
            <h3 id="b-fontes"><span className="ponto" style={{ background: "var(--c-outros)" }} />Nas suas fontes</h3>
            <ul className="lista-obj">
              {[...d.citacoes, ...d.outros].slice(0, 6).map((c) => (
                <li key={c.id}><button className="cartao-obj fino" onClick={() => onAbrir(c.id)}><Selo item={c} tamanho={28} /><span className="nome">{c.nome}</span></button></li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

/* ---------- Lado a lado (quadro por político) ---------- */

export function LadoALado({ base, fotos, onAbrir, onFocar }: { base: Base; fotos: Fotos; onAbrir: (id: string) => void; onFocar: (siteId: string) => void }) {
  const ids = Object.keys(base.seguidos);
  const ds = useMemo(() => ids.map((s) => dossie(base, s)).filter(Boolean) as Dossie[], [base, ids.join()]);
  const comum = useMemo(() => quemSeLiga(base, ids), [base, ids.join()]);
  const nomes = (s: string) => base.seguidos[s]?.atual.nome || s;
  if (!ds.length) return <div className="empty">Siga políticos para ver um ao lado do outro.</div>;
  const donos = (d: Dossie) => [...new Map(d.empresas.flatMap((e) => e.socios).map((p) => [p.id, p])).values()];
  const Linha = ({ titulo, itens }: { titulo: string; itens: (d: Dossie) => Item[] }) => (
    <>
      <div className="quadro-rotulo">{titulo}</div>
      {ds.map((d) => {
        const xs = itens(d);
        return (
          <div key={d.id} className="quadro-celula">
            {!xs.length && <span className="vazio">—</span>}
            {xs.map((x) => (
              <button key={x.id} className={`chip-obj${(comum.get(x.id)?.length || 0) > 1 ? " repetido" : ""}`} onClick={() => onAbrir(x.id)}
                title={(comum.get(x.id)?.length || 0) > 1 ? `Também ligado a ${comum.get(x.id)!.filter((s) => s !== d.siteId).map(nomes).join(", ")}` : x.nome}>
                <Selo item={x} tamanho={22} />{x.nome}{x.valor ? <em>{reaisCurto(x.valor)}</em> : null}
              </button>
            ))}
          </div>
        );
      })}
    </>
  );
  return (
    <div className="palco quadro-rolagem">
      <div className="quadro" style={{ gridTemplateColumns: `minmax(110px, 150px) repeat(${ds.length}, minmax(190px, 1fr))` }}>
        <div className="quadro-rotulo topo" />
        {ds.map((d, i) => (
          <button key={d.id} className="quadro-cabeca" onClick={() => onFocar(d.siteId)} style={{ borderColor: corSerie(i) }}>
            <FotoPolitico url={fotos(d.siteId)} nome={d.nome} tamanho={64} />
            <strong>{d.nome}</strong>
            <span>{d.partido?.nome}{d.mandato ? ` · ${d.mandato}` : ""}</span>
          </button>
        ))}
        <Linha titulo="Empresas que mais receberam da cota" itens={(d) => d.empresas.slice(0, 6)} />
        <Linha titulo="Donos dessas empresas" itens={(d) => donos(d).slice(0, 8)} />
        <Linha titulo="Emendas Pix para" itens={(d) => d.lugares.slice(0, 5)} />
        <Linha titulo="Projetos que votou" itens={(d) => d.projetos.slice(0, 4)} />
      </div>
      <p className="nota-palco"><span className="chip-obj repetido amostra">destaque dourado</span> = também aparece na coluna de outro político que você segue.</p>
    </div>
  );
}

/* ---------- Ranking com fotos ---------- */

export function Ranking({ base, fotos, onFocar }: { base: Base; fotos: Fotos; onFocar: (siteId: string) => void }) {
  const [medida, setMedida] = useState<Medida>("cota");
  const m = MEDIDAS.find((x) => x.chave === medida)!;
  const lista = useMemo(() => ranking(base, medida), [base, medida]);
  if (!lista.length) return <div className="empty">Siga políticos para montar o ranking.</div>;
  const maior = lista[0].valor || 1;
  return (
    <div className="palco ranking">
      <div className="ranking-topo">
        <label>Ordenar por <select value={medida} onChange={(e) => setMedida(e.target.value as Medida)}>{MEDIDAS.map((x) => <option key={x.chave} value={x.chave}>{x.nome}</option>)}</select></label>
      </div>
      <ol className="ranking-barras" aria-label={`Ranking por ${m.nome}`}>
        {lista.map((r, i) => (
          <li key={r.siteId}>
            <button onClick={() => onFocar(r.siteId)} aria-label={`${i + 1}º ${r.nome}: ${m.dinheiro ? reais(r.valor) : numero(r.valor)}`}>
              <span className="posicao" style={{ background: corSerie(i) }}>{i + 1}</span>
              <FotoPolitico url={fotos(r.siteId)} nome={r.nome} tamanho={62} decorativa />
              <span className="quem">{r.nome}</span>
              <span className="quanto" style={{ color: corSerie(i) }}>{m.dinheiro ? reaisCurto(r.valor) : numero(r.valor)}</span>
              <span className="coluna" style={{ height: `${Math.max(4, (r.valor / maior) * 100)}%`, background: corSerie(i) }}>
                <span className="rotulo-base">{r.partido}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <p className="nota-palco">Fonte: dados abertos da Câmara, do Senado e do Portal da Transparência, coletados por este site. Clique num político para ver o mapa dele.</p>
    </div>
  );
}

/* ---------- Em comum (estações e linhas) ---------- */

const pos = (i: number, n: number, r = 38) => {
  if (n === 1) return { x: 50, y: 50 };
  const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
  return { x: 50 + r * Math.cos(a), y: 50 + r * Math.sin(a) };
};

export function EmComum({ base, fotos, onAbrir, onFocar }: { base: Base; fotos: Fotos; onAbrir: (id: string) => void; onFocar: (siteId: string) => void }) {
  const ids = Object.keys(base.seguidos);
  const pares = useMemo(() => emComum(base, ids), [base, ids.join()]);
  const [par, setPar] = useState<string | null>(null);
  const [aberto, setAberto] = useState<string | null>(null);
  if (ids.length < 2) return <div className="empty">Siga pelo menos dois políticos para ver o que eles têm em comum.</div>;
  const p = Object.fromEntries(ids.map((s, i) => [s, pos(i, ids.length)]));
  const MAX = 6;
  return (
    <div className="palco comum">
      <div className="comum-mapa">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {pares.map((x) => (
            <line key={x.a + x.b} x1={p[x.a].x} y1={p[x.a].y} x2={p[x.b].x} y2={p[x.b].y}
              className={par && par !== x.a + x.b ? "apagada" : ""} strokeWidth={Math.min(1.6, 0.5 + x.itens.length * 0.15)} />
          ))}
        </svg>
        {pares.map((x) => x.itens.slice(0, MAX).map((it, k) => {
          const n = Math.min(x.itens.length, MAX);
          const t = (k + 1) / (n + 1);
          const left = p[x.a].x + (p[x.b].x - p[x.a].x) * t, top = p[x.a].y + (p[x.b].y - p[x.a].y) * t;
          return (
            <button key={x.a + x.b + it.id} className={`parada${par && par !== x.a + x.b ? " apagada" : ""}`} style={{ left: `${left}%`, top: `${top}%`, background: corTipo(it.tipo) }}
              onClick={() => onAbrir(it.id)} onMouseEnter={() => setPar(x.a + x.b)} onMouseLeave={() => setPar(null)}
              title={`${it.nome} (${nomeTipo(it.tipo)})`} aria-label={`${it.nome}, ligado a ${base.seguidos[x.a]?.atual.nome} e ${base.seguidos[x.b]?.atual.nome}`} />
          );
        }))}
        {ids.map((s, i) => (
          <button key={s} className="estacao" style={{ left: `${p[s].x}%`, top: `${p[s].y}%`, borderColor: corSerie(i) }} onClick={() => onFocar(s)}>
            <FotoPolitico url={fotos(s)} nome={base.seguidos[s].atual.nome} tamanho={64} decorativa />
            <span>{base.seguidos[s].atual.nome}</span>
          </button>
        ))}
      </div>
      <div className="comum-lista">
        <h3>O que eles dividem</h3>
        {!pares.length && <p className="vazio">Nenhuma empresa, dono, lugar ou projeto em comum entre os políticos que você segue.</p>}
        <ul>
          {pares.map((x) => (
            <li key={x.a + x.b} onMouseEnter={() => setPar(x.a + x.b)} onMouseLeave={() => setPar(null)}>
              <strong>{base.seguidos[x.a]?.atual.nome} e {base.seguidos[x.b]?.atual.nome}</strong> <span className="small">({x.itens.length})</span>
              <div className="chips">{x.itens.slice(0, aberto === x.a + x.b ? undefined : 12).map((it) => <button key={it.id} className="chip-obj" onClick={() => onAbrir(it.id)}><Selo item={it} tamanho={20} />{it.nome}</button>)}
                {x.itens.length > 12 && <button className="link claro small" onClick={() => setAberto(aberto === x.a + x.b ? null : x.a + x.b)}>{aberto === x.a + x.b ? "Mostrar menos" : `e mais ${x.itens.length - 12}`}</button>}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ---------- Círculo (anel de políticos e anel do que se liga a eles) ---------- */

function arco(r1: number, r2: number, a1: number, a2: number): string {
  const p = (r: number, a: number) => `${(400 + r * Math.cos(a)).toFixed(2)} ${(400 + r * Math.sin(a)).toFixed(2)}`;
  const g = a2 - a1 > Math.PI ? 1 : 0;
  return `M ${p(r2, a1)} A ${r2} ${r2} 0 ${g} 1 ${p(r2, a2)} L ${p(r1, a2)} A ${r1} ${r1} 0 ${g} 0 ${p(r1, a1)} Z`;
}

export function Circulo({ base, fotos, onAbrir, onFocar }: { base: Base; fotos: Fotos; onAbrir: (id: string) => void; onFocar: (siteId: string) => void }) {
  const ids = Object.keys(base.seguidos);
  const ds = useMemo(() => ids.map((s) => dossie(base, s)).filter(Boolean) as Dossie[], [base, ids.join()]);
  if (!ds.length) return <div className="empty">Siga políticos para montar o círculo.</div>;
  const fatia = (2 * Math.PI) / ds.length, folga = ds.length > 1 ? 0.02 : 0;
  const pct = (v: number) => `${(v / 800) * 100}%`;
  return (
    <div className="palco circulo">
      <div className="circulo-area">
        <svg viewBox="0 0 800 800" aria-hidden="true">
          <circle cx="400" cy="400" r="345" className="anel-fora" />
          {ds.map((d, i) => {
            const a1 = -Math.PI / 2 + i * fatia + folga, a2 = -Math.PI / 2 + (i + 1) * fatia - folga;
            return <g key={d.id}>
              <path d={arco(110, 215, a1, a2)} fill={corSerie(i)} opacity={0.92} />
              <path d={arco(230, 380, a1, a2)} fill={corSerie(i)} opacity={0.14} />
            </g>;
          })}
          <circle cx="400" cy="400" r="104" className="miolo" />
        </svg>
        <div className="circulo-miolo" style={{ left: "50%", top: "50%" }}>
          <strong>{ds.length}</strong><span>{ds.length === 1 ? "político seguido" : "políticos seguidos"}</span>
        </div>
        {ds.map((d, i) => {
          const meio = -Math.PI / 2 + (i + 0.5) * fatia;
          const itens = [...d.empresas.slice(0, 8), ...d.lugares.slice(0, 4)];
          return (
            <div key={d.id}>
              <button className="circulo-foto" style={{ left: pct(400 + 162 * Math.cos(meio)), top: pct(400 + 162 * Math.sin(meio)) }} onClick={() => onFocar(d.siteId)} title={d.nome}>
                <FotoPolitico url={fotos(d.siteId)} nome={d.nome} tamanho={ds.length > 6 ? 46 : 64} decorativa />
                <span>{d.nome}</span>
              </button>
              {itens.map((it, k) => {
                const a = -Math.PI / 2 + i * fatia + fatia * ((k + 0.5) / itens.length);
                const r = k % 2 ? 340 : 275;
                return <button key={it.id} className="circulo-item" style={{ left: pct(400 + r * Math.cos(a)), top: pct(400 + r * Math.sin(a)), background: corTipo(it.tipo) }}
                  onClick={() => onAbrir(it.id)} title={`${it.nome}${it.valor ? `: ${reais(it.valor)}` : ""}`} aria-label={`${it.nome}, ligado a ${d.nome}`}>{sigla(it.nome)}</button>;
              })}
            </div>
          );
        })}
      </div>
      <p className="nota-palco">Anel de dentro: os políticos que você segue. Anel de fora: as 8 empresas que mais receberam da cota e os 4 principais destinos de emendas de cada um. Passe o mouse para ver o nome; clique para abrir.</p>
    </div>
  );
}
