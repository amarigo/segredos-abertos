/* Levanta os textos em português que aparecem nos sites e diz quais ainda não têm tradução.
 *
 * Abre o site montado no navegador, passa por todas as páginas (até 3 de cada tipo: 3 políticos, 3 empresas...),
 * clica em cada aba, em cada botão de alternar e em cada ano, e guarda os textos do mesmo jeito que o tradutor
 * (i18n/tradutor.js) procura no dicionário. Só entram textos escritos no código do site ou do coletor: nomes de
 * pessoas, empresas e outros dados oficiais ficam de fora (não são traduzidos).
 *
 * Uso (com o site servido em algum endereço, por exemplo npx vite preview --port 4173):
 *   node scripts/textos.mjs http://localhost:4173/ public/i18n            -> textos sem tradução em en.json e es.json
 *   node scripts/textos.mjs http://localhost:4173/mg/ public/i18n
 *   node scripts/textos.mjs http://localhost:4173/eleicao2026/ ../eleicao2026/site/i18n
 * Saída: <pasta>/faltando.json com cada texto e um trecho em volta, para ajudar a traduzir. Código de saída 1 se faltar algum.
 */
import { chromium } from "@playwright/test";
import { readFileSync, readdirSync, statSync, writeFileSync, existsSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(AQUI, "..", "..");
// tradutor.js é um script comum do navegador; em Node, roda isolado e devolve as funções em module.exports
const modulo = { exports: {} };
runInNewContext(readFileSync(join(AQUI, "..", "public", "i18n", "tradutor.js"), "utf-8"), { module: modulo });
const { chave, traduzirTexto } = modulo.exports;

const [base, pasta] = process.argv.slice(2);
if (!base || !pasta) { console.error("uso: node scripts/textos.mjs <endereço do site> <pasta do dicionário>"); process.exit(2); }

/* Tudo que foi escrito à mão: o site, o coletor (avisos e alertas que vão nos dados) e a página da eleição */
function arquivos(dir, ext, out = []) {
  if (!existsSync(dir)) return out;
  for (const f of readdirSync(dir)) {
    if (f === "node_modules" || f === "tests" || f === "dist" || f.startsWith(".")) continue;
    const p = join(dir, f);
    if (statSync(p).isDirectory()) arquivos(p, ext, out);
    else if (ext.some((e) => f.endsWith(e))) out.push(p);
  }
  return out;
}
const fontes = [
  ...arquivos(join(RAIZ, "site", "src"), [".ts", ".tsx"]), join(RAIZ, "site", "index.html"),
  ...arquivos(join(RAIZ, "etl", "sa_etl"), [".py"]), ...arquivos(join(RAIZ, "mg", "etl", "mg_etl"), [".py"]),
  ...arquivos(join(RAIZ, "eleicao2026", "site"), [".html"]), ...arquivos(join(RAIZ, "eleicao2026", "etl", "el_etl"), [".py"]),
];
const corpus = fontes.map((f) => readFileSync(f, "utf-8")).join("\n").replace(/\s+/g, " ");
/** O texto foi escrito no código? Cada pedaço entre os números tem que aparecer em algum arquivo. */
/* Nomes próprios do projeto e siglas (partidos, estados) não se traduzem */
const NAO_TRADUZ = new Set(["Brasil", "Minas", "Nossa", "Minas Nossa", "Segredos Abertos", "Segredos Abertos Brasil", "Minas Gerais", "GitHub"]);
/* Palavras do código: um pedaço também conta como "do código" quando cada palavra dele aparece no código. Assim entram
   frases montadas em pedaços ("a abstenção " + (caiu ? "caiu" : "subiu") + ", de "...), que não aparecem inteiras. */
const palavras = new Set(corpus.toLowerCase().match(/\p{L}+/gu));
const temPalavras = (p) => (p.toLowerCase().match(/\p{L}+/gu) || []).every((w) => palavras.has(w));
function doCodigo(k) {
  if (NAO_TRADUZ.has(k) || !/\p{Ll}/u.test(k)) return false;
  const pedacos = k.split(/\{\d+\}/).map((p) => p.trim()).filter((p) => /\p{L}/u.test(p));
  return pedacos.length > 0 && pedacos.every((p) => corpus.includes(p) || temPalavras(p));
}

/* No navegador: os textos do jeito que o tradutor procura (frase inteira quando o elemento só tem texto) */
function coletar() {
  const out = [];
  const pular = (el) => el.closest("script,style,noscript,textarea,code,pre,[translate=no],.notranslate");
  const ctx = (el) => (el.closest("p,li,td,th,h1,h2,h3,label,button,summary,a,div") || el).textContent.replace(/\s+/g, " ").trim().slice(0, 200);
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  for (let el = document.body; el; el = w.nextNode()) {
    if (pular(el)) continue;
    // Igual ao tradutor: quando o elemento só tem texto, junta todos os pedaços (inclusive os só de espaço)
    const todos = [...el.childNodes].filter((c) => c.nodeType === 3);
    const textos = todos.filter((c) => /\S/.test(c.nodeValue));
    const soTexto = ![...el.childNodes].some((c) => c.nodeType === 1);
    if (soTexto && todos.length > 1) out.push([todos.map((t) => t.nodeValue).join(""), ctx(el), textos.map((t) => t.nodeValue)]);
    else for (const t of textos) out.push([t.nodeValue, ctx(el)]);
    for (const a of ["title", "aria-label", "placeholder", "alt"]) { const v = el.getAttribute(a); if (v) out.push([v, `[${a}] ${ctx(el)}`]); }
  }
  out.push([document.title, "[title]"]);
  const d = document.querySelector('meta[name="description"]');
  if (d) out.push([d.getAttribute("content"), "[description]"]);
  return out;
}

const achados = new Map(); // chave -> contexto
function guardar(lista) {
  for (const [texto, ctx, pedacos] of lista) {
    const { k } = chave(texto);
    if (doCodigo(k)) { if (!achados.has(k)) achados.set(k, [ctx, texto]); continue; }
    // Frase com dado no meio (nome de pessoa...): o tradutor cai para pedaço por pedaço
    if (pedacos) for (const p of pedacos) { const kp = chave(p).k; if (doCodigo(kp) && !achados.has(kp)) achados.set(kp, [ctx, p]); }
  }
}

const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
const page = await browser.newPage({ serviceWorkers: "block" });
page.on("pageerror", (e) => console.error("erro na página:", e.message));
await page.addInitScript(() => { try { localStorage.setItem("lingua", "pt"); } catch { /* */ } });

/* Listas de escolha, controles deslizantes, mapas e linhas de tabela que mudam o texto da página: tenta alguns valores de cada */
async function explorar() {
  const selects = await page.locator("select:not(#ano)").count();
  for (let i = 0; i < selects; i++) {
    const sel = page.locator("select:not(#ano)").nth(i);
    if (!(await sel.isVisible().catch(() => false))) continue;
    const vals = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value));
    for (const v of [...new Set([vals[0], vals[1], vals[vals.length - 1]])].filter((v) => v != null)) {
      await sel.selectOption(v).catch(() => {});
      await espera();
      guardar(await page.evaluate(coletar));
    }
  }
  const ranges = await page.locator("input[type=range]").count();
  for (let i = 0; i < ranges; i++) {
    const r = page.locator("input[type=range]").nth(i);
    if (!(await r.isVisible().catch(() => false))) continue;
    for (const pos of ["min", "max", "meio"]) {
      await r.evaluate((el, pos) => {
        const min = +el.min || 0, max = +el.max || 100;
        el.value = String(pos === "min" ? min : pos === "max" ? max : Math.round((min + max) / 2));
        el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true }));
      }, pos);
      await espera();
      guardar(await page.evaluate(coletar));
    }
  }
  for (const css of ["svg path[tabindex]", "svg [role=button]", ".tile", "tr.rowbtn"]) {
    const n = Math.min(await page.locator(css).count(), 3);
    for (let i = 0; i < n; i++) {
      const el = page.locator(css).nth(i);
      if (!(await el.isVisible().catch(() => false))) continue;
      await el.click({ timeout: 2000 }).catch(() => {});
      await espera();
      guardar(await page.evaluate(coletar));
    }
  }
}

const visto = new Map(); // tipo de página -> quantas
const fila = ["#/"];
const feitos = new Set();
const tipo = (h) => h.replace(/\/[^/]*\d[^/]*$/, "/:id");
const espera = () => page.waitForTimeout(250);

while (fila.length) {
  const h = fila.shift();
  if (feitos.has(h)) continue;
  feitos.add(h);
  const t = tipo(h);
  if ((visto.get(t) || 0) >= 3) continue;
  visto.set(t, (visto.get(t) || 0) + 1);
  await page.goto(new URL(h, base).toString());
  await page.waitForLoadState("networkidle");
  await espera();
  const anos = await page.locator("#ano option").evaluateAll((os) => os.map((o) => o.value)).catch(() => []);
  for (const ano of anos.length ? anos : [null]) {
    if (ano) { await page.selectOption("#ano", ano); await espera(); }
    guardar(await page.evaluate(coletar));
    // Seções do menu (página da eleição) e, em cada uma, abas, botões de alternar, detalhes e o resto (explorar)
    const secoes = await page.locator(".menu button").count();
    for (let m = 0; m < Math.max(secoes, 1); m++) {
      if (secoes) { await page.locator(".menu button").nth(m).click({ timeout: 2000 }).catch(() => {}); await espera(); }
      const n = await page.locator('[role=tab], button[aria-pressed]').count();
      for (let i = 0; i < n; i++) {
        const b = page.locator('[role=tab], button[aria-pressed]').nth(i);
        if (!(await b.isVisible().catch(() => false))) continue;
        await b.click({ timeout: 2000 }).catch(() => {});
        await espera();
        await page.locator("details:not([open]) > summary").evaluateAll((ss) => ss.forEach((s) => s.click())).catch(() => {});
        guardar(await page.evaluate(coletar));
        await explorar();
      }
      await page.locator("details:not([open]) > summary").evaluateAll((ss) => ss.forEach((s) => s.click())).catch(() => {});
      guardar(await page.evaluate(coletar));
      await explorar();
    }
  }
  const links = await page.locator('a[href^="#/"]').evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  for (const l of links) if (!feitos.has(l)) fila.push(l);
}
await browser.close();

let falta = 0;
const relatorio = {};
for (const l of ["en", "es"]) {
  const arq = join(pasta, `${l}.json`);
  const dic = existsSync(arq) ? JSON.parse(readFileSync(arq, "utf-8")) : {};
  // Traduzido = o tradutor acha no dicionário (direto ou por uma chave com {*})
  const faltando = [...achados].filter(([, [, texto]]) => traduzirTexto(texto, dic, l) == null).map(([k, [ctx]]) => [k, ctx]);
  falta += faltando.length;
  relatorio[l] = Object.fromEntries(faltando);
  console.log(`${l}: ${achados.size} textos no site, ${faltando.length} sem tradução`);
}
console.log(`páginas visitadas: ${[...visto].map(([t, n]) => `${t} (${n})`).join(", ")}`);
writeFileSync(join(pasta, "faltando.json"), JSON.stringify(relatorio, null, 1));
process.exit(falta ? 1 : 0);
