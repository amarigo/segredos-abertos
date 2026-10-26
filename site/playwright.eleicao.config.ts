import { defineConfig, devices } from "@playwright/test";

// Testes de navegador da Eleição 2026 (/eleicao2026/), com os dados reais guardados em eleicao2026/dados.
// Antes: (cd ../eleicao2026/etl && python -m el_etl.build montar --saida ../../site/dist/eleicao2026)
export default defineConfig({
  testDir: "./e2e",
  testMatch: "eleicao2026.spec.ts",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never", outputFolder: "playwright-report-eleicao" }]] : "list",
  use: { baseURL: "http://localhost:4175/eleicao2026/", trace: "retain-on-failure", serviceWorkers: "block" },
  webServer: { command: "python3 -m http.server 4175 --directory dist", url: "http://localhost:4175/eleicao2026/", reuseExistingServer: !process.env.CI },
  projects: [
    { name: "computador", use: { ...devices["Desktop Chrome"] } },
    { name: "celular", use: { ...devices["Pixel 7"] } },
  ],
});
