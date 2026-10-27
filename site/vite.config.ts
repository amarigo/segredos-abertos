import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/* Política de segurança de conteúdo (CSP). O GitHub Pages não deixa mandar cabeçalhos, então vai numa <meta>.
   Só scripts do próprio site; imagens de qualquer https (fotos da Câmara e do Senado); fontes do Google;
   os dados (fetch) só do próprio site. Só no build: o servidor de desenvolvimento usa scripts embutidos. */
export const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: https:",
  "connect-src 'self'",
  "worker-src 'self'",
  "manifest-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "upgrade-insecure-requests", // fotos do Senado vêm com http://: o navegador pede por https
].join("; ");

const csp = (): Plugin => ({
  name: "csp",
  apply: "build",
  transformIndexHtml: (html) =>
    html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />\n    <meta name="referrer" content="strict-origin-when-cross-origin" />`),
});

/* Minas Nossa (vite build --mode mg): o mesmo site, com os dados de MG (public-mg/data) e publicado em /mg/.
   Ícone, service worker e tradução são os mesmos do nacional: copiados para public-mg a cada build. */
const minasNossa = (): Plugin => ({
  name: "minas-nossa",
  config() {
    mkdirSync("public-mg", { recursive: true });
    for (const f of ["icon.svg", "sw.js"]) copyFileSync(`public/${f}`, `public-mg/${f}`);
    // Tradutor e dicionários (inglês e espanhol) são os mesmos do nacional
    mkdirSync("public-mg/i18n", { recursive: true });
    for (const f of readdirSync("public/i18n").filter((x) => /\.(js|json)$/.test(x) && x !== "faltando.json")) copyFileSync(`public/i18n/${f}`, `public-mg/i18n/${f}`);
  },
  // Título, descrição e endereço do Minas Nossa vêm de .env.mg (VITE_TITULO, VITE_DESCRICAO, VITE_URL)
});

// base "./" para funcionar no GitHub Pages (amarigo.github.io/segredos-abertos/ e .../mg/)
export default defineConfig(({ mode }) => mode === "mg"
  ? { plugins: [react(), csp(), minasNossa()], base: "./", publicDir: "public-mg", build: { outDir: "dist/mg", emptyOutDir: true } }
  : { plugins: [react(), csp()], base: "./" });
