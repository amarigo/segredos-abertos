/* Busca de cidade pelo nome, para "Quem me representa" (funções puras, testadas em tests/unidade.test.ts). */

export const normal = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const UFS = new Set("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split(" "));

/** Cidades que combinam com o que a pessoa digitou: primeiro as que começam com o texto. "campinas sp" e
 *  "Campinas - SP" também valem (a sigla do estado no fim filtra o estado). */
export function buscarCidades(lista: [string, string, string][], q: string, max = 8): [string, string, string][] {
  let t = normal(q);
  if (t.length < 2) return [];
  let uf = "";
  const m = t.match(/^(.*\S)\s+([a-z]{2})$/);
  if (m && UFS.has(m[2].toUpperCase())) { t = m[1]; uf = m[2].toUpperCase(); }
  const comeca: [string, string, string][] = [];
  const tem: [string, string, string][] = [];
  for (const c of lista) {
    if (uf && c[2] !== uf) continue;
    const n = normal(c[1]);
    if (n.startsWith(t)) comeca.push(c);
    else if (n.includes(" " + t) || (t.length >= 4 && n.includes(t))) tem.push(c);
    if (comeca.length >= max) break;
  }
  return [...comeca, ...tem].slice(0, max);
}
