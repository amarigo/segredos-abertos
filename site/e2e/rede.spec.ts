import { expect, test } from "@playwright/test";

// Minha rede: seguir, ver a rede, guardar uma fonte com afirmação, perguntar, comparar e manter tudo ao recarregar.
test("Minha rede: seguir um político, ligar uma fonte e perguntar", async ({ page }) => {
  await page.goto("./#/p/dep-1000");
  await page.getByRole("link", { name: "Acompanhar na Minha rede" }).click();
  await expect(page.locator(".rede-seguido")).toHaveCount(1);
  await expect(page.getByText("Nada novo desde a última visita.")).toBeVisible();

  // Mapa do político: foto no centro, blocos em volta; clicar numa empresa abre a ficha com a fonte
  await page.getByRole("tab", { name: "Rede" }).click();
  await expect(page.locator(".mapa-centro h2")).toHaveText("Deputado Ficticio 00");
  await page.locator(".cartao-obj").first().click();
  await expect(page.locator(".rede-gaveta .rede-painel")).toContainText("Fonte:");
  await page.getByRole("button", { name: "Fechar a ficha" }).click();
  for (const v of ["Lado a lado", "Ranking", "Círculo"]) {
    await page.getByRole("tab", { name: v }).click();
    await expect(page.locator(".palco")).toBeVisible();
  }
  await page.getByRole("tab", { name: "Grafo livre" }).click();
  await expect(page.locator(".rede-grafo .no").first()).toBeVisible();

  await page.getByRole("tab", { name: "Fontes" }).click();
  await page.getByLabel("Título", { exact: true }).fill("Notícia de teste");
  await page.getByLabel("Texto", { exact: true }).fill("O Deputado Ficticio 00 contratou a gráfica para a campanha. O dia estava bonito.");
  await page.getByRole("button", { name: "Guardar e procurar nomes" }).click();
  await page.getByRole("button", { name: "Guardar 1 afirmação" }).click();

  await page.getByRole("tab", { name: "Perguntar" }).click();
  await page.getByRole("searchbox", { name: "Pergunte à sua rede" }).fill("quem contratou a gráfica");
  await page.getByRole("button", { name: "Procurar" }).click();
  await expect(page.locator(".rede-trechos li").first()).toContainText("contratou a gráfica");

  await page.getByRole("tab", { name: "Comparar" }).click();
  await page.getByRole("button", { name: "Guardar comparação" }).click();
  await expect(page.getByText(/guardada em/)).toBeVisible();

  await page.reload();
  await expect(page.locator(".rede-seguido")).toHaveCount(1);
});

test("Minha rede: um link segue vários de uma vez (nome com UF e todos os senadores de um estado)", async ({ page }) => {
  await page.goto("./#/rede?seguir=" + encodeURIComponent("Deputado Ficticio 01/MG,senado/RJ,Ninguém/AC"));
  await expect(page.locator(".rede-seguido")).toHaveCount(4);
  await expect(page.getByText("Não encontrei: Ninguém/AC")).toBeVisible();
  await page.reload();
  await expect(page.locator(".rede-seguido")).toHaveCount(4);
});

test("Minha rede: em comum mostra o que dois políticos dividem", async ({ page }) => {
  await page.goto("./#/rede?seguir=dep-1000,dep-1001");
  await expect(page.locator(".rede-seguido")).toHaveCount(2);
  await page.getByRole("tab", { name: "Rede" }).click();
  await page.getByRole("tab", { name: "Em comum" }).click();
  await expect(page.locator(".estacao")).toHaveCount(2);
  await expect(page.locator(".parada").first()).toBeVisible();
  await page.locator(".parada").first().click();
  await expect(page.locator(".rede-gaveta")).toBeVisible();
});
