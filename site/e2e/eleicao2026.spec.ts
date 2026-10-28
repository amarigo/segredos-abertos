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

test("barra dos projetos liga a Eleição 2026 aos outros sites do Segredos Abertos", async ({ page }) => {
  await page.goto("./");
  const nav = page.getByRole("navigation", { name: "Projetos do Segredos Abertos" });
  await expect(nav.getByRole("link", { name: "Brasil" })).toHaveAttribute("href", "../");
  await expect(nav.getByRole("link", { name: "Minas Nossa" })).toHaveAttribute("href", "../mg/");
  await expect(nav.getByRole("link", { name: "Eleição 2026" })).toHaveAttribute("href", "./");
  await expect(nav.locator('a[aria-current="page"]')).toHaveText("Eleição 2026");
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
    "UF;Municipio;Cod_municipio_TSE;Zona;Secao;Abertura_hora_local;Encerramento_hora_local;Encerramento_horario_Brasilia;Eleitores_aptos;Comparecimento;Votos_13_Lula;Votos_22_Flavio;Brancos;Nulos;Votos_depois_17h",
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

test("comparecimento e abstenção usam a mesma base do TSE (exterior)", async ({ page }) => {
  // O TSE divide pelos aptos das seções instaladas; no exterior há seções não instaladas.
  const tse = JSON.parse(readFileSync(new URL("../../eleicao2026/dados/tse/zz-6258.json", import.meta.url), "utf-8"));
  await page.goto("./#diferencas");
  await page.selectOption("#cmp-uf", "ZZ");
  await expect(page.locator("#t-cmp")).toContainText(tse.e.pc + "%");
  await expect(page.locator("#t-cmp")).toContainText(tse.e.pa + "%");
  await expect(page.locator("#cmp-ni")).toContainText("não foram instaladas");
});

test("apuração hora a hora: mapa ao lado do gráfico no computador, empilhado no celular", async ({ page }) => {
  await page.goto("./#noite");
  await expect(page.locator("#nchart path.ln")).toHaveCount(2);
  const box = async (sel: string) => (await page.locator(sel).boundingBox())!;
  const mapa = await box("#nmap"), graf = await box("#nchart"), hora = await box("#n-t");
  if (page.viewportSize()!.width > 860) {
    // lado a lado: o gráfico fica à direita do mapa, na mesma altura da tela
    expect(graf.x).toBeGreaterThanOrEqual(mapa.x + mapa.width);
    expect(Math.abs(graf.y - mapa.y)).toBeLessThan(200);
    // o controle de horário fica logo abaixo do gráfico
    expect(hora.y).toBeGreaterThan(graf.y + graf.height);
  } else {
    // celular: primeiro o mapa, depois o horário, depois o gráfico
    expect(mapa.y).toBeLessThan(hora.y);
    expect(hora.y).toBeLessThan(graf.y);
  }
});

test("apuração hora a hora: a velocidade da animação pode ser ajustada", async ({ page }) => {
  await page.goto("./#noite");
  await expect(page.locator("#nchart path.ln")).toHaveCount(2);
  await expect(page.locator("[data-nvel='200']")).toHaveAttribute("aria-pressed", "true");
  const passos = async (vel: string) => {
    await page.locator(`[data-nvel='${vel}']`).click();
    await expect(page.locator(`[data-nvel='${vel}']`)).toHaveAttribute("aria-pressed", "true");
    await page.locator("#n-t").evaluate((e: HTMLInputElement) => { e.value = e.min; e.dispatchEvent(new Event("input")); });
    const v0 = Number(await page.locator("#n-t").inputValue());
    await page.locator("#n-play").click();
    await page.waitForTimeout(1500);
    await page.locator("#n-play").click();
    return Number(await page.locator("#n-t").inputValue()) - v0;
  };
  const devagar = await passos("500"), rapido = await passos("70");
  expect(devagar).toBeGreaterThan(0);
  expect(rapido).toBeGreaterThan(devagar * 2);
});

test("votos depois das 17h: números do registro das urnas, conferidos com o boletim", async ({ page }) => {
  const erros = semErros(page);
  const D = dados("dados/numeros_do_site.json");
  for (const t of ["2", "1"]) {
    const x = D.d17[t];
    expect(x, `registros do ${t}º turno`).toBeTruthy();
    // toda urna com boletim foi lida; só ficam de fora as que não têm registro publicado ou não batem
    const sem = Object.entries(x.conf).filter(([k]) => k.startsWith("sem_registro_")).reduce((a, [, v]) => a + (v as number), 0);
    expect(x.conf.bate + (x.conf.diferente || 0) + sem).toBe(x.conf.urnas);
    expect(x.conf.bate / x.conf.urnas).toBeGreaterThan(0.999);
    // por minuto soma o total; estados somam o Brasil
    const br = x.uf.BR;
    expect(x.pm.BR.reduce((a: number, [, q]: number[]) => a + q, 0)).toBe(br[2]);
    const ufs = Object.keys(x.uf).filter((u) => u !== "BR");
    expect(ufs.reduce((a, u) => a + x.uf[u][2], 0)).toBe(br[2]);
    await page.goto("./#tarde");
    await page.locator(`[data-tround='${t}']`).click();
    await expect(page.locator("#t-short")).toContainText(br[2].toLocaleString("pt-BR"));
    await expect(page.locator("#tmap path")).toHaveCount(27);
    await expect(page.locator("#t-check")).toContainText("batem exatamente");
    await expect(page.locator("#t-who")).toContainText("Não dá para saber");
  }
  await expect(page.locator("#t-tl tbody tr").first()).toBeVisible();
  expect(erros).toEqual([]);
});

test("simulador: dá para escolher o exterior, e o número real devolve o resultado oficial", async ({ page }) => {
  const erros = semErros(page);
  const br = oficial["6258"].BR.cand, zz = oficial["6258"].ZZ.cand;
  await page.goto("./#simulador");
  await page.locator("#sa-zz").click();
  await expect(page.locator("#sa-uf")).toHaveValue("ZZ");
  await expect(page.locator("#sa-zz")).toHaveAttribute("aria-pressed", "true");
  // com o número real do exterior, a diferença é a oficial
  await expect(page.locator("#sa-out")).toContainText("no exterior");
  await expect(page.locator("#sa-out")).toContainText((br["13"].v - br["22"].v).toLocaleString("pt-BR") + " votos");
  // sem os votos do exterior: tira exatamente os votos do exterior
  await page.locator("#sa-zero").click();
  await expect(page.locator("#sa-out")).toContainText("Sem nenhum voto do exterior");
  const semZZ = br["13"].v - zz["13"].v - (br["22"].v - zz["22"].v);
  await expect(page.locator("#sa-out")).toContainText(Math.abs(semZZ).toLocaleString("pt-BR") + " votos");
  expect(erros).toEqual([]);
});

for (const largura of [1366, 1024, 800]) {
  test(`menu: todas as abas aparecem inteiras (${largura} px)`, async ({ page }) => {
    await page.setViewportSize({ width: largura, height: 800 });
    await page.goto("./");
    const abas = page.locator("nav.menu button");
    expect(await abas.count()).toBe(7);
    for (const b of await abas.all()) {
      const r = (await b.boundingBox())!;
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.x + r.width).toBeLessThanOrEqual(largura);
      // o texto cabe no botão (não está cortado)
      expect(await b.evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBe(true);
    }
  });
}

test.describe("tema escuro", () => {
  test.use({ colorScheme: "dark" });
  test("botões vazados têm texto legível", async ({ page }) => {
    await page.goto("./");
    const cores = await page.locator("#zzbtn").evaluate((b) => {
      const c = getComputedStyle(b).color;
      let e: Element | null = b, bg = "rgba(0, 0, 0, 0)";
      while (e && /rgba\(.*, 0\)|transparent/.test(bg)) { bg = getComputedStyle(e).backgroundColor; e = e.parentElement; }
      return [c, bg];
    });
    expect(cores[0]).not.toBe(cores[1]);
    const lum = (s: string) => { const [r, g, b] = (s.match(/[\d.]+/g) || []).map(Number).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const [a, b] = cores.map(lum);
    expect((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)).toBeGreaterThan(4.5);
  });
});

test("troca para inglês e espanhol; os números continuam os oficiais", async ({ page }) => {
  const erros = semErros(page);
  await page.goto("./?lang=en");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const nav = page.getByRole("navigation", { name: "Segredos Abertos projects" });
  await expect(nav).toContainText("Election 2026");
  // Em inglês o número usa vírgula de milhar
  const br = oficial["6258"].BR.cand;
  await expect(page.locator("body")).toContainText(br["13"].v.toLocaleString("en-US"));
  await page.locator(".linguas").getByRole("link", { name: "ES", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "es");
  await expect(page.getByRole("navigation", { name: "Proyectos de Segredos Abertos" })).toContainText("Elección 2026");
  await expect(page.locator("body")).toContainText(fmt(br["13"].v));
  await page.locator(".linguas").getByRole("link", { name: "PT", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
  expect(erros).toEqual([]);
});

test("em inglês, as frases montadas com números também são traduzidas (1º × 2º turno)", async ({ page }) => {
  await page.goto("./?lang=en");
  await page.locator(".menu button").nth(2).click();
  const txt = page.locator("#d-txt");
  await expect(txt).toContainText("abstention");
  await expect(txt).not.toContainText("abstenção");
  await expect(page.locator("body")).toContainText("million");
  await expect(page.locator("body")).not.toContainText("milhões");
});
