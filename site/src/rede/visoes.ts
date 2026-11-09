/* Contas das visões da Minha rede (mapa do político, quadro, ranking, em comum, círculo).
 * Só funções puras sobre a base: a tela (rede/Visoes.tsx) só desenha o que sai daqui. */
import { idObjeto, type Base, type Objeto, type TipoObjeto } from "./modelo.ts";

export interface Item { id: string; nome: string; tipo: TipoObjeto; ref?: string; valor?: number; data?: string; detalhe?: string }
export interface Empresa extends Item { socios: Item[] }
export interface Dossie {
  id: string; siteId: string; nome: string; ref?: string;
  partido?: Item; mandato?: string;
  empresas: Empresa[]; lugares: Item[]; votos: Item[]; projetos: Item[]; citacoes: Item[]; outros: Item[];
  totalEmpresas: number; totalLugares: number;
}

const item = (o: Objeto, extra: Partial<Item> = {}): Item => ({ id: o.id, nome: o.nome, tipo: o.tipo, ref: o.ref, ...extra });

/** Tudo o que liga um político seguido, separado em grupos que a pessoa entende */
export function dossie(base: Base, siteId: string): Dossie | null {
  const id = idObjeto("politico", siteId);
  const eu = base.objetos[id];
  if (!eu) return null;
  const d: Dossie = { id, siteId, nome: eu.nome, ref: eu.ref, empresas: [], lugares: [], votos: [], projetos: [], citacoes: [], outros: [], totalEmpresas: 0, totalLugares: 0 };
  const empresas = new Map<string, Empresa>(), lugares = new Map<string, Item>(), projetos = new Map<string, Item>();
  const ligs = Object.values(base.ligacoes);
  for (const l of ligs) {
    if (l.de !== id && l.para !== id) continue;
    const outroId = l.de === id ? l.para : l.de;
    const o = base.objetos[outroId];
    if (!o) continue;
    if (l.tipo === "é filiado a") d.partido = item(o);
    else if (l.tipo.startsWith("exerce mandato")) d.mandato = l.tipo.replace(/^exerce mandato\s*\(?/, "").replace(/\)$/, "");
    else if (l.tipo === "pagou com a cota") {
      const e = empresas.get(o.id) || { ...item(o), valor: 0, socios: [] };
      e.valor = (e.valor || 0) + (l.valor || 0);
      empresas.set(o.id, e);
    } else if (l.tipo === "mandou emenda Pix para") {
      const x = lugares.get(o.id) || item(o, { valor: 0 });
      x.valor = (x.valor || 0) + (l.valor || 0);
      lugares.set(o.id, x);
    } else if (l.tipo.startsWith("votou ")) {
      d.votos.push(item(o, { detalhe: l.tipo.slice(6), data: l.data }));
    } else if (o.tipo === "afirmacao") d.citacoes.push(item(o, { detalhe: l.trecho, data: l.data }));
    else d.outros.push(item(o, { detalhe: l.de === id ? l.tipo : `${l.tipo} (de ${o.nome})` }));
  }
  // Donos de cada empresa e projeto de cada votação
  for (const l of ligs) {
    if (l.tipo === "é sócio de" && empresas.has(l.para) && base.objetos[l.de]) empresas.get(l.para)!.socios.push(item(base.objetos[l.de]));
    if (l.tipo === "votou o projeto" && base.objetos[l.para] && d.votos.some((v) => v.id === l.de)) {
      const p = base.objetos[l.para];
      if (!projetos.has(p.id)) projetos.set(p.id, item(p, { detalhe: p.notas }));
    }
  }
  d.empresas = [...empresas.values()].sort((a, b) => (b.valor || 0) - (a.valor || 0));
  d.lugares = [...lugares.values()].sort((a, b) => (b.valor || 0) - (a.valor || 0));
  d.votos.sort((a, b) => (b.data || "").localeCompare(a.data || ""));
  d.projetos = [...projetos.values()];
  d.totalEmpresas = d.empresas.reduce((s, e) => s + (e.valor || 0), 0);
  d.totalLugares = d.lugares.reduce((s, e) => s + (e.valor || 0), 0);
  return d;
}

/** Tipos que não contam como "em comum": todo mundo da mesma Casa, partido ou votação já se liga por eles.
 *  Projetos também ficam de fora: todos os parlamentares votam os mesmos projetos. */
const NAO_CONTA: TipoObjeto[] = ["orgao", "partido", "evento", "afirmacao", "projeto"];

/** Para cada objeto, quais políticos seguidos se ligam a ele (direto, ou pelo dono de uma empresa paga) */
export function quemSeLiga(base: Base, siteIds: string[]): Map<string, string[]> {
  const m = new Map<string, Set<string>>();
  const add = (obj: string, pol: string) => { if (!m.has(obj)) m.set(obj, new Set()); m.get(obj)!.add(pol); };
  for (const s of siteIds) {
    const d = dossie(base, s);
    if (!d) continue;
    for (const e of d.empresas) { add(e.id, s); for (const p of e.socios) add(p.id, s); }
    for (const x of [...d.lugares, ...d.outros]) if (!NAO_CONTA.includes(x.tipo)) add(x.id, s);
  }
  return new Map([...m].map(([k, v]) => [k, [...v]]));
}

/** Pares de políticos seguidos e o que eles têm em comum (empresas, donos, lugares, pessoas) */
export function emComum(base: Base, siteIds: string[]): { a: string; b: string; itens: Item[] }[] {
  const liga = quemSeLiga(base, siteIds);
  const pares = new Map<string, Item[]>();
  for (const [obj, pols] of liga) {
    if (pols.length < 2 || !base.objetos[obj]) continue;
    const ps = [...pols].sort();
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) {
      const k = `${ps[i]}|${ps[j]}`;
      pares.set(k, [...(pares.get(k) || []), item(base.objetos[obj])]);
    }
  }
  return [...pares].map(([k, itens]) => { const [a, b] = k.split("|"); return { a, b, itens: itens.sort((x, y) => x.nome.localeCompare(y.nome)) }; })
    .sort((x, y) => y.itens.length - x.itens.length);
}

export type Medida = "cota" | "empresas" | "emendas" | "votos" | "ligacoes";
export const MEDIDAS: { chave: Medida; nome: string; dinheiro: boolean }[] = [
  { chave: "cota", nome: "Cota parlamentar no ano", dinheiro: true },
  { chave: "empresas", nome: "Pago a empresas (todos os anos)", dinheiro: true },
  { chave: "emendas", nome: "Emendas pagas", dinheiro: true },
  { chave: "votos", nome: "Votos registrados", dinheiro: false },
  { chave: "ligacoes", nome: "Ligações na sua rede", dinheiro: false },
];

/** Ranking dos políticos seguidos por uma medida, do maior para o menor */
export function ranking(base: Base, medida: Medida): { siteId: string; nome: string; partido: string; valor: number }[] {
  return Object.values(base.seguidos).map((s) => {
    const d = dossie(base, s.id);
    const id = idObjeto("politico", s.id);
    const valor = medida === "cota" ? s.atual.cota
      : medida === "empresas" ? d?.totalEmpresas || 0
      : medida === "emendas" ? s.atual.emendas
      : medida === "votos" ? s.atual.votos.length
      : Object.values(base.ligacoes).filter((l) => l.de === id || l.para === id).length;
    return { siteId: s.id, nome: s.atual.nome, partido: s.atual.partido, valor };
  }).sort((a, b) => b.valor - a.valor || a.nome.localeCompare(b.nome));
}
