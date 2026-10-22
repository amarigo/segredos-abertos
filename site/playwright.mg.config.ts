import { defineConfig, devices } from "@playwright/test";

// Testes de navegador do Minas Nossa. Antes: dados de teste em public-mg/data (mg/etl/tests/gerar_dados_teste_mg.py)
// e npm run build:mg.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "mg.spec.ts",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never", outputFolder: "playwright-report-mg" }]] : "list",
  use: { baseURL: "http://localhost:4174/", trace: "retain-on-failure", serviceWorkers: "block" },
  webServer: { command: "npx vite preview --mode mg --port 4174 --strictPort", url: "http://localhost:4174/", reuseExistingServer: !process.env.CI },
  projects: [
    { name: "computador", use: { ...devices["Desktop Chrome"] } },
    { name: "celular", use: { ...devices["Pixel 7"] } },
  ],
});
