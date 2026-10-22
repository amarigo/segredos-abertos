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

// base "./" para funcionar no GitHub Pages (amarigo.github.io/segredos-abertos/)
export default defineConfig({ plugins: [react(), csp()], base: "./" });
