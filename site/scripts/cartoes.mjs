/* Cartões de prévia: uma imagem JPEG por político (1200×630), mostrada quando alguém compartilha o link da página
 * estática dele no WhatsApp, Facebook, X, LinkedIn e outros. Roda depois do build e antes de paginas-estaticas.mjs,
 * que só põe a imagem (og:image) na página quando o arquivo existe.
 *
 * O desenho é o mesmo do botão "Compartilhar" do app (src/cartao.ts), feito num Chromium sem tela (Playwright, que
 * o projeto já usa nos testes). Os números são os de dist/data (politicos.json e meta.json); nada é calculado aqui.
 * Se o navegador não abrir, o script avisa e sai sem erro: as páginas ficam sem imagem, mas o site é publicado.
 *
 * Uso: node scripts/cartoes.mjs dist https://amarigo.github.io/segredos-abertos/ [--mg]
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { stripTypeScriptTypes } from "node:module";
import { dadosCartao, imagemPolitico } from "../src/cartao.ts";

const [dist, base, ...resto] = process.argv.slice(2);
const MG = resto.includes("--mg");
if (!dist || !base) { console.error("uso: node scripts/cartoes.mjs <dist> <endereço público> [--mg]"); process.exit(2); }
const lerJson = (rel) => { const p = join(dist, "data", rel); return existsSync(p) ? JSON.parse(readFileSync(p, "utf-8")) : null; };
const meta = lerJson("meta.json");
const politicos = lerJson("politicos.json");
if (!meta || !politicos) { console.log("Cartões: sem dados em", join(dist, "data"), "(nada a fazer)"); process.exit(0); }

const site = MG ? "Minas Nossa" : "Segredos Abertos Brasil";
const lista = politicos
  .map((p) => ({ id: p.id, dados: dadosCartao(p, meta, { site, endereco: base }) }))
  .filter((x) => x.dados);

const aviso = (msg) => { console.log(`::warning title=Cartões de prévia::${msg}`); process.exit(0); };
let chromium;
try { ({ chromium } = await import("playwright")); } catch { try { ({ chromium } = await import("@playwright/test")); } catch { aviso("Playwright não instalado; páginas sem imagem de prévia"); } }
let navegador;
// CHROMIUM_PATH: usar um Chromium já instalado fora do Playwright (máquina local)
try { navegador = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}); } catch (e) { aviso(`navegador não abriu (${String(e.message || e).split("\n")[0]}); páginas sem imagem de prévia`); }

const codigo = stripTypeScriptTypes(readFileSync(new URL("../src/cartao.ts", import.meta.url), "utf-8"));
const pagina = await navegador.newPage();
// A letra do site (Raleway, Google Fonts). Sem internet, o cartão sai com a letra padrão do sistema.
await pagina.setContent(`<!doctype html><html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Raleway:wght@500;600;700;800&display=block"></head><body></body></html>`, { waitUntil: "load" }).catch(() => {});
await pagina.addScriptTag({ type: "module", content: `${codigo}\nwindow.__cartao = { desenharCartao, TAMANHO };` });
await pagina.waitForFunction(() => window.__cartao);
const familia = await pagina.evaluate(async () => {
  try { await Promise.all([500, 600, 700, 800].map((w) => document.fonts.load(`${w} 40px Raleway`))); } catch { /* sem a letra */ }
  return document.fonts.check("800 40px Raleway") ? "Raleway" : "sans-serif";
});

mkdirSync(join(dist, "cartao"), { recursive: true });
const LOTE = 40;
let feitos = 0;
const cortados = []; // cartões em que alguma linha de números não coube
for (let i = 0; i < lista.length; i += LOTE) {
  const lote = lista.slice(i, i + LOTE);
  const imagens = await pagina.evaluate(({ lote, familia }) => lote.map(({ dados }) => {
    const [w, h] = window.__cartao.TAMANHO.link;
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const fora = window.__cartao.desenharCartao(c.getContext("2d"), dados, "link", familia);
    return [c.toDataURL("image/jpeg", 0.8).split(",")[1], fora];
  }), { lote, familia });
  imagens.forEach(([b64, fora], j) => {
    writeFileSync(join(dist, imagemPolitico(lote[j].id)), Buffer.from(b64, "base64"));
    feitos++;
    if (fora) cortados.push(lote[j].id);
  });
}
await navegador.close();
if (cortados.length) console.log(`::warning title=Cartões de prévia::${cortados.length} cartão(ões) sem todas as linhas de números por falta de espaço: ${cortados.slice(0, 10).join(", ")}`);
console.log(`Cartões de prévia (${MG ? "Minas Nossa" : "Brasil"}): ${feitos} imagens em ${join(dist, "cartao")}, letra ${familia}.`);
