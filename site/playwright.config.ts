import { defineConfig, devices } from "@playwright/test";

// Testes de navegador (topo da pirâmide). Antes: dados de teste em public/data (etl/tests/gerar_dados_teste.py) e npm run build.
export default defineConfig({
  testDir: "./e2e",
  testIgnore: "mg.spec.ts",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: "http://localhost:4173/", trace: "retain-on-failure", serviceWorkers: "block" },
  webServer: { command: "npx vite preview --port 4173 --strictPort", url: "http://localhost:4173/", reuseExistingServer: !process.env.CI },
  projects: [
    { name: "computador", use: { ...devices["Desktop Chrome"] } },
    { name: "celular", use: { ...devices["Pixel 7"] } },
  ],
});
