import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

// Os números esperados vêm do arquivo oficial do TSE gerado no mesmo build, não de valores escritos à mão.
const dados = (rel: string) => JSON.parse(readFileSync(new URL(`../dist/eleicao2026/${rel}`, import.meta.url), "utf-8"));
const oficial = dados("dados/resultados_oficiais.json");
const fmt = (n: number) => n.toLocaleString("pt-BR");

const semErros = (page: Page) => {
  const erros: string[] = [];
  page.on("pageerror", (e) => erros.push(e.message));
  return erros;
};

test("resultado oficial do 2º turno aparece igual ao do TSE", async ({ page }) => {
  const erros = semErros(page);
  await page.goto("./");
  const br = oficial["6258"].BR.cand;
  await expect(page.locator("body")).toContainText(fmt(br["13"].v));
  await expect(page.locator("body")).toContainText(fmt(br["22"].v));
  await expect(page.locator("#brmap path")).toHaveCount(27);
  expect(erros).toEqual([]);
});

test("todas as seções abrem pelo menu", async ({ page }) => {
  const erros = semErros(page);
  await page.goto("./");
  for (const nome of ["Apuração hora a hora", "Onde mudou", "Simulador", "Urnas e horário", "Dados abertos", "Mapa e resultado"]) {
    await page.locator("nav.menu button", { hasText: nome }).click();
    await expect(page.locator("section.view:not([hidden])")).toHaveCount(1);
  }
  expect(erros).toEqual([]);
});

test("lista de urnas de um estado carrega e tem link para o TSE", async ({ page }) => {
  await page.goto("./");
  await page.locator("nav.menu button", { hasText: "Urnas e horário" }).click();
  await page.selectOption("#l-uf", "SP");
  await expect(page.locator("#l-sum")).toContainText("urnas");
  const link = page.locator("#t-l tbody a").first();
  await expect(link).toHaveAttribute("href", /^https:\/\/resultados\.tse\.jus\.br\/oficial\/ele2026\/arquivo-urna\/3221\/dados\/sp\//);
});

test("planilha de um estado pode ser baixada e tem o cabeçalho certo", async ({ page, request }) => {
  await page.goto("./");
  await page.locator("nav.menu button", { hasText: "Dados abertos" }).click();
  await page.selectOption("#dl-uf", "MG");
  const href = await page.locator("#dl-links a").first().getAttribute("href");
  expect(href).toBe("dados/urnas/2turno_MG.csv");
  const r = await request.get(href!);
  expect(r.ok()).toBe(true);
  expect((await r.text()).split("\n")[0]).toBe(
    "UF;Municipio;Cod_municipio_TSE;Zona;Secao;Abertura_hora_local;Encerramento_hora_local;Encerramento_horario_Brasilia;Eleitores_aptos;Comparecimento;Votos_13_Lula;Votos_22_Flavio;Brancos;Nulos",
  );
});

test("caos: se a lista de urnas não carregar, avisa e o resto continua", async ({ page }) => {
  const erros = semErros(page);
  await page.route("**/urnas/2_RJ.json", (r) => r.abort("failed"));
  await page.goto("./");
  await page.locator("nav.menu button", { hasText: "Urnas e horário" }).click();
  await page.selectOption("#l-uf", "RJ");
  await expect(page.locator("#l-sum")).toContainText("ainda não está disponível");
  await page.locator("nav.menu button", { hasText: "Simulador" }).click();
  await expect(page.locator("#smap path")).toHaveCount(27);
  expect(erros).toEqual([]);
});

test("cabe na tela do celular sem rolar para o lado", async ({ page }) => {
  await page.goto("./");
  const largura = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(largura).toBeLessThanOrEqual(1);
});

test("fotos oficiais dos candidatos carregam", async ({ page }) => {
  await page.goto("./");
  for (const img of await page.locator(".avatar.ph img").all()) {
    await expect(img).toBeVisible();
    expect(await img.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(100);
  }
});

test("apuração hora a hora termina no resultado oficial e mostra as viradas", async ({ page }) => {
  const erros = semErros(page);
  const D = dados("dados/numeros_do_site.json");
  const n = D.noite["2"];
  const ult = n.n.length - 1;
  expect(n["13"][ult]).toBe(oficial["6258"].BR.cand["13"].v);
  expect(n["22"][ult]).toBe(oficial["6258"].BR.cand["22"].v);
  await page.goto("./#noite");
  await expect(page.locator("#nchart path.ln")).toHaveCount(2);
  await expect(page.locator("#nmap path")).toHaveCount(27);
  await expect(page.locator("#n-check")).toContainText("igual ao total oficial");
  await page.locator("#n-play").click();
  await page.waitForTimeout(400);
  await page.locator("#n-play").click();
  await page.locator("[data-nround='1']").click();
  await expect(page.locator("#n-h")).toContainText("na frente");
  expect(erros).toEqual([]);
});

test("tabela 1º × 2º turno mostra os números oficiais do estado escolhido", async ({ page }) => {
  await page.goto("./#diferencas");
  await page.selectOption("#cmp-uf", "BA");
  const ba = oficial["6258"].BA.cand;
  await expect(page.locator("#t-cmp")).toContainText(fmt(ba["13"].v));
  await expect(page.locator("#d-txt")).toContainText("voto é secreto");
});

test.describe("celular pequeno (320 px)", () => {
  test.use({ viewport: { width: 320, height: 568 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });

  test("nenhuma seção passa da largura da tela e as tabelas viram cartões", async ({ page }) => {
    const erros = semErros(page);
    await page.goto("./");
    for (const nome of ["Mapa e resultado", "Apuração hora a hora", "Onde mudou", "Simulador", "Urnas e horário", "Dados abertos"]) {
      await page.locator("nav.menu button", { hasText: nome }).click();
      await page.waitForTimeout(300);
      expect(await page.evaluate(() => window.innerWidth), nome).toBe(320);
      expect(await page.evaluate(() => document.documentElement.scrollWidth), nome).toBeLessThanOrEqual(321);
    }
    await page.locator("nav.menu button", { hasText: "Urnas e horário" }).click();
    await expect(page.locator("#t-l thead")).toBeHidden();
    await expect(page.locator("#t-l tbody td").nth(2)).toHaveAttribute("data-l", "Fechou às");
    expect(erros).toEqual([]);
  });

  test("botão Menu aparece ao rolar e volta ao menu", async ({ page }) => {
    await page.goto("./");
    await expect(page.locator("#tomenu")).toBeHidden();
    await page.evaluate(() => window.scrollTo(0, 3000));
    await expect(page.locator("#tomenu")).toBeVisible();
    await page.locator("#tomenu").click();
    await expect(page.locator("nav.menu")).toBeInViewport();
  });
});
