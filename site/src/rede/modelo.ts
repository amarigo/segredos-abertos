/* Minha rede: base de conhecimento pessoal em forma de grafo.
 *
 * A informação fica em objetos (pessoas, empresas, órgãos, eventos, projetos, lugares, afirmações) e em ligações
 * entre eles. Toda ligação aponta para a fonte de onde saiu (link oficial ou texto colado pela pessoa) e, quando dá,
 * guarda o trecho exato. Tudo aqui é função pura: sem rede e sem armazenamento, para dar para testar com o Node.
 * A base fica só no navegador de quem usa (guardar.ts); o site não recebe nada.
 */

export type TipoObjeto = "pessoa" | "politico" | "empresa" | "orgao" | "partido" | "evento" | "projeto" | "lugar" | "afirmacao";
export const TIPOS: { tipo: TipoObjeto; nome: string; cor: string }[] = [
  { tipo: "politico", nome: "Político", cor: "var(--s1)" },
  { tipo: "pessoa", nome: "Pessoa", cor: "var(--s3)" },
  { tipo: "empresa", nome: "Empresa", cor: "var(--s2)" },
  { tipo: "orgao", nome: "Órgão", cor: "var(--c7)" },
  { tipo: "partido", nome: "Partido", cor: "var(--c5)" },
  { tipo: "evento", nome: "Evento ou votação", cor: "var(--c4)" },
  { tipo: "projeto", nome: "Projeto de lei", cor: "var(--c6)" },
  { tipo: "lugar", nome: "Lugar", cor: "var(--c8)" },
  { tipo: "afirmacao", nome: "Afirmação", cor: "var(--c-outros)" },
];
export const nomeTipo = (t: TipoObjeto) => TIPOS.find((x) => x.tipo === t)?.nome || t;
export const corTipo = (t: TipoObjeto) => TIPOS.find((x) => x.tipo === t)?.cor || "var(--muted)";

/** De onde veio a informação. "oficial": dado público coletado pelo site; "texto": algo que a pessoa colou ou escreveu. */
export interface Fonte {
  id: string; titulo: string; url?: string; tipo: "oficial" | "texto";
  /** Quando a fonte entrou na base (ISO) */
  em: string;
  /** Data do próprio documento, quando se sabe (ISO, aaaa-mm-dd) */
  data?: string;
  texto?: string;
}
export interface Objeto {
  id: string; tipo: TipoObjeto; nome: string;
  /** Página do próprio site sobre o objeto (ex.: "/p/dep-1000"), quando existe */
  ref?: string;
  notas?: string;
}
export interface Ligacao {
  id: string; de: string; para: string;
  /** O que liga os dois, escrito do ponto de vista de "de" (ex.: "pagou com a cota", "é sócio de") */
  tipo: string;
  fonte: string;
  trecho?: string; valor?: number; data?: string;
  /** Criada pela pessoa (e não pela coleta automática) */
  manual?: boolean;
}
/** Retrato de um político num momento: o que muda de um dia para o outro e merece aviso */
export interface Retrato {
  em: string; nome: string; partido: string; cota: number; ano: string;
  votos: string[]; empresas: Record<string, string>; emendas: number; situacao: string;
}
export interface Seguido { id: string; desde: string; atual: Retrato; visto: Retrato }
export interface LinhaComparacao { id: string; nome: string; partido: string; uf: string; valores: Record<string, number | null> }
export interface Comparacao { id: string; nome: string; em: string; ano: string; linhas: LinhaComparacao[] }
export interface Base {
  versao: 1;
  objetos: Record<string, Objeto>;
  ligacoes: Record<string, Ligacao>;
  fontes: Record<string, Fonte>;
  seguidos: Record<string, Seguido>;
  comparacoes: Comparacao[];
}

export const baseVazia = (): Base => ({ versao: 1, objetos: {}, ligacoes: {}, fontes: {}, seguidos: {}, comparacoes: [] });

/** Texto sem acento, minúsculo e com espaços simples: para comparar nomes e buscar */
export function normalizar(s: string): string {
  return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Ids previsíveis: o mesmo político, empresa ou sócio vindo de fontes diferentes cai no mesmo objeto */
export const idObjeto = (tipo: TipoObjeto, chave: string) => `${tipo}:${tipo === "empresa" ? chave.replace(/\D/g, "") : normalizar(chave)}`;
const idLigacao = (l: Omit<Ligacao, "id">) => [l.de, normalizar(l.tipo), l.para, l.fonte].join("|");

/** Junta objetos, fontes e ligações na base. Não apaga nada e não duplica; o nome mais recente vence, as notas ficam. */
export function juntar(base: Base, novo: { objetos?: Objeto[]; fontes?: Fonte[]; ligacoes?: Omit<Ligacao, "id">[] }): Base {
  const b: Base = { ...base, objetos: { ...base.objetos }, fontes: { ...base.fontes }, ligacoes: { ...base.ligacoes } };
  for (const o of novo.objetos || []) {
    const velho = b.objetos[o.id];
    b.objetos[o.id] = velho ? { ...velho, ...o, notas: velho.notas || o.notas, ref: o.ref || velho.ref } : o;
  }
  for (const f of novo.fontes || []) b.fontes[f.id] = b.fontes[f.id] ? { ...b.fontes[f.id], ...f, em: b.fontes[f.id].em } : f;
  for (const l of novo.ligacoes || []) {
    if (!b.objetos[l.de] || !b.objetos[l.para] || !b.fontes[l.fonte] || l.de === l.para) continue;
    const id = idLigacao(l);
    b.ligacoes[id] = { ...l, id };
  }
  return b;
}

/** Apaga um objeto e as ligações dele. Fontes ficam (podem servir a outras ligações). */
export function apagarObjeto(base: Base, id: string): Base {
  const objetos = { ...base.objetos };
  delete objetos[id];
  const ligacoes = Object.fromEntries(Object.entries(base.ligacoes).filter(([, l]) => l.de !== id && l.para !== id));
  return { ...base, objetos, ligacoes };
}
export function apagarLigacao(base: Base, id: string): Base {
  const ligacoes = { ...base.ligacoes };
  delete ligacoes[id];
  return { ...base, ligacoes };
}
/** Apaga uma fonte e tudo o que só ela sustentava */
export function apagarFonte(base: Base, id: string): Base {
  const fontes = { ...base.fontes };
  delete fontes[id];
  const ligacoes = Object.fromEntries(Object.entries(base.ligacoes).filter(([, l]) => l.fonte !== id));
  return { ...base, fontes, ligacoes };
}

/** Ligações de um objeto, para os dois lados */
export function ligacoesDe(base: Base, id: string): Ligacao[] {
  return Object.values(base.ligacoes).filter((l) => l.de === id || l.para === id);
}

/** Vizinhança de um objeto até "passos" de distância, limitada a "max" objetos (os mais ligados primeiro) */
export function vizinhanca(base: Base, centro: string, passos = 1, max = 120): { objetos: Objeto[]; ligacoes: Ligacao[] } {
  const grau = new Map<string, number>();
  for (const l of Object.values(base.ligacoes)) { grau.set(l.de, (grau.get(l.de) || 0) + 1); grau.set(l.para, (grau.get(l.para) || 0) + 1); }
  const dentro = new Set([centro]);
  let borda = [centro];
  for (let i = 0; i < passos && dentro.size < max; i++) {
    const prox = new Set<string>();
    for (const l of Object.values(base.ligacoes)) {
      if (borda.includes(l.de) && !dentro.has(l.para)) prox.add(l.para);
      if (borda.includes(l.para) && !dentro.has(l.de)) prox.add(l.de);
    }
    const ordem = [...prox].sort((a, b) => (grau.get(b) || 0) - (grau.get(a) || 0)).slice(0, max - dentro.size);
    ordem.forEach((x) => dentro.add(x));
    borda = ordem;
  }
  const objetos = [...dentro].map((id) => base.objetos[id]).filter(Boolean);
  const ligacoes = Object.values(base.ligacoes).filter((l) => dentro.has(l.de) && dentro.has(l.para));
  return { objetos, ligacoes };
}

/** Ligações que ainda não existem mas a rede sugere: dois objetos com vizinhos em comum e sem ligação direta.
 *  Ex.: dois políticos que pagaram a mesma empresa, ou um sócio que aparece em duas empresas pagas. */
export function sugestoes(base: Base, max = 20): { a: string; b: string; comuns: string[] }[] {
  const viz = new Map<string, Set<string>>();
  const add = (x: string, y: string) => { if (!viz.has(x)) viz.set(x, new Set()); viz.get(x)!.add(y); };
  for (const l of Object.values(base.ligacoes)) { add(l.de, l.para); add(l.para, l.de); }
  const pares = new Map<string, string[]>();
  for (const [meio, vs] of viz) {
    // Votações e partidos ligam centenas de objetos de uma vez: não dizem nada sobre uma relação próxima
    const tipo = base.objetos[meio]?.tipo;
    if (tipo === "evento" || tipo === "partido" || vs.size > 40) continue;
    const lista = [...vs].sort();
    for (let i = 0; i < lista.length; i++) for (let j = i + 1; j < lista.length; j++) {
      const [a, b] = [lista[i], lista[j]];
      if (viz.get(a)?.has(b)) continue;
      const k = `${a}\u0000${b}`;
      pares.set(k, [...(pares.get(k) || []), meio]);
    }
  }
  return [...pares.entries()]
    .map(([k, comuns]) => { const [a, b] = k.split("\u0000"); return { a, b, comuns }; })
    .filter((s) => base.objetos[s.a] && base.objetos[s.b])
    // Mais interessante: políticos e pessoas primeiro, depois quem tem mais em comum
    .sort((x, y) => peso(base, y) - peso(base, x) || y.comuns.length - x.comuns.length)
    .slice(0, max);
}
function peso(base: Base, s: { a: string; b: string; comuns: string[] }): number {
  const p = (id: string) => ({ politico: 3, pessoa: 2, empresa: 1 } as Record<string, number>)[base.objetos[id]?.tipo] || 0;
  return p(s.a) + p(s.b) + s.comuns.length;
}

/* ---------- Textos: encontrar nomes e buscar trechos ---------- */

/** Divide um texto em frases (para mostrar o trecho exato onde algo aparece) */
export function frases(texto: string): string[] {
  return (texto || "").replace(/\s+/g, " ").split(/(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9"“(])/).map((f) => f.trim()).filter(Boolean);
}

export interface NomeConhecido { id: string; tipo: TipoObjeto; nome: string; ref?: string; variantes?: string[] }
export interface Mencao { conhecido: NomeConhecido; trechos: string[] }

/** Procura no texto nomes já conhecidos (políticos e empresas do site, objetos da base) e CNPJs.
 *  Nomes curtos demais (uma palavra com menos de 6 letras) ficam de fora, porque confundem com palavras comuns. */
export function acharMencoes(texto: string, conhecidos: NomeConhecido[]): Mencao[] {
  const fs = frases(texto);
  const fsN = fs.map((f) => ` ${normalizar(f)} `);
  const fsDig = fs.map((f) => f.replace(/\D/g, ""));
  const achados = new Map<string, Mencao>();
  for (const c of conhecidos) {
    const nomes = [c.nome, ...(c.variantes || [])].map(normalizar).filter((n) => n.includes(" ") ? n.length >= 5 : n.length >= 6);
    const cnpj = c.tipo === "empresa" ? c.id.split(":")[1] : "";
    const trechos: string[] = [];
    fs.forEach((f, i) => {
      if (nomes.some((n) => fsN[i].includes(` ${n} `)) || (cnpj.length === 14 && fsDig[i].includes(cnpj))) trechos.push(f);
    });
    if (trechos.length) {
      const velho = achados.get(c.id);
      achados.set(c.id, { conhecido: velho?.conhecido || c, trechos: [...new Set([...(velho?.trechos || []), ...trechos])] });
    }
  }
  return [...achados.values()].sort((a, b) => b.trechos.length - a.trechos.length);
}

const PARADAS = new Set(("a o e as os de da do das dos em no na nos nas um uma uns umas por para com sem que se sua seu suas seus " +
  "ao aos à às pelo pela pelos pelas é foi ser são como mais mas ou quem qual quais quando onde porque isso esse essa este esta ele ela eles elas " +
  "lhe já não sim tem têm ter há").split(" ").map(normalizar));
const termos = (s: string) => normalizar(s).split(" ").filter((t) => t.length > 1 && !PARADAS.has(t));

export interface Trecho { fonte: string; texto: string; objetos?: string[]; nota: number }

/** Busca uma pergunta nas fontes e nas ligações da base. Devolve os trechos mais parecidos, cada um com a fonte.
 *  Conta palavras (com peso maior para as raras, como no BM25) e dá um bônus quando o trecho cita um objeto da pergunta. */
export function buscar(base: Base, pergunta: string, max = 12): Trecho[] {
  const q = termos(pergunta);
  if (!q.length) return [];
  const docs: Omit<Trecho, "nota">[] = [];
  for (const f of Object.values(base.fontes)) for (const t of frases(f.texto || "")) docs.push({ fonte: f.id, texto: t });
  for (const l of Object.values(base.ligacoes)) {
    const de = base.objetos[l.de]?.nome, para = base.objetos[l.para]?.nome;
    docs.push({ fonte: l.fonte, texto: l.trecho || `${de} ${l.tipo} ${para}${l.data ? ` (${l.data})` : ""}`, objetos: [l.de, l.para] });
  }
  const toks = docs.map((d) => termos(d.texto));
  const df = new Map<string, number>();
  for (const ts of toks) for (const t of new Set(ts)) df.set(t, (df.get(t) || 0) + 1);
  const n = docs.length, media = toks.reduce((s, t) => s + t.length, 0) / (n || 1);
  const qn = ` ${normalizar(pergunta)} `;
  const citados = Object.values(base.objetos).filter((o) => normalizar(o.nome).length >= 5 && qn.includes(` ${normalizar(o.nome)} `)).map((o) => o.id);
  const notas = docs.map((d, i) => {
    let s = 0;
    for (const t of new Set(q)) {
      const tf = toks[i].filter((x) => x === t || (t.length >= 5 && x.startsWith(t.slice(0, -1)))).length;
      if (!tf) continue;
      const idf = Math.log(1 + (n - (df.get(t) || 0) + 0.5) / ((df.get(t) || 0) + 0.5));
      s += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * toks[i].length / media));
    }
    if (s && d.objetos?.some((o) => citados.includes(o))) s *= 1.5;
    return { ...d, nota: s };
  });
  const vistos = new Set<string>();
  const topo = Math.max(0, ...notas.map((d) => d.nota));
  // Só o que chega perto do melhor trecho: o resto casou com uma palavra comum
  return notas.filter((d) => d.nota > 0 && d.nota >= topo * 0.4).sort((a, b) => b.nota - a.nota)
    .filter((d) => { const k = d.fonte + d.texto; if (vistos.has(k)) return false; vistos.add(k); return true; })
    .slice(0, max);
}

/* ---------- Alertas: o que mudou desde a última visita ---------- */

export interface Novidade { tipo: "cota" | "voto" | "empresa" | "partido" | "emenda" | "situacao"; texto: string; ids?: string[]; valor?: number }

export function novidades(antes: Retrato, agora: Retrato): Novidade[] {
  const out: Novidade[] = [];
  if (antes.partido !== agora.partido) out.push({ tipo: "partido", texto: `Mudou de partido: ${antes.partido} → ${agora.partido}` });
  if ((antes.situacao || "") !== (agora.situacao || "")) out.push({ tipo: "situacao", texto: `Situação no mandato: ${agora.situacao || "em exercício"}` });
  if (agora.ano === antes.ano && agora.cota > antes.cota + 0.005) out.push({ tipo: "cota", texto: `Novas despesas da cota em ${agora.ano}`, valor: agora.cota - antes.cota });
  else if (agora.ano !== antes.ano && agora.cota > 0) out.push({ tipo: "cota", texto: `Primeiras despesas da cota em ${agora.ano}`, valor: agora.cota });
  const vistos = new Set(antes.votos);
  const novos = agora.votos.filter((v) => !vistos.has(v));
  if (novos.length) out.push({ tipo: "voto", texto: `${novos.length} ${novos.length === 1 ? "voto novo" : "votos novos"}`, ids: novos });
  const empresas = Object.keys(agora.empresas).filter((d) => !(d in antes.empresas));
  if (empresas.length) out.push({ tipo: "empresa", texto: `${empresas.length} ${empresas.length === 1 ? "empresa nova paga" : "empresas novas pagas"} com a cota`, ids: empresas });
  if (agora.emendas > antes.emendas + 0.005) out.push({ tipo: "emenda", texto: "Novos pagamentos de emendas", valor: agora.emendas - antes.emendas });
  return out;
}

/** Lê uma base exportada (arquivo JSON) e recusa o que não tem a forma esperada */
export function lerExportada(texto: string): Base {
  const d = JSON.parse(texto);
  const obj = (x: unknown) => x && typeof x === "object" && !Array.isArray(x);
  if (!obj(d) || d.versao !== 1 || !obj(d.objetos) || !obj(d.ligacoes) || !obj(d.fontes)) throw new Error("Arquivo não é uma base exportada da Minha rede.");
  const ok = (o: unknown, campos: string[]) => obj(o) && campos.every((c) => typeof (o as Record<string, unknown>)[c] === "string");
  for (const o of Object.values(d.objetos)) if (!ok(o, ["id", "tipo", "nome"])) throw new Error("Objeto com defeito no arquivo.");
  for (const l of Object.values(d.ligacoes)) if (!ok(l, ["id", "de", "para", "tipo", "fonte"])) throw new Error("Ligação com defeito no arquivo.");
  for (const f of Object.values(d.fontes)) if (!ok(f, ["id", "titulo", "tipo", "em"])) throw new Error("Fonte com defeito no arquivo.");
  return { versao: 1, objetos: d.objetos, ligacoes: d.ligacoes, fontes: d.fontes, seguidos: obj(d.seguidos) ? d.seguidos : {}, comparacoes: Array.isArray(d.comparacoes) ? d.comparacoes : [] };
}
