import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" para funcionar no GitHub Pages (amarigo.github.io/segredos-abertos/)
export default defineConfig({ plugins: [react()], base: "./" });
