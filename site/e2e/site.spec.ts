/* Testes de navegador com os dados fictícios do FakeGov.
   - Jornada: o que a pessoa vê bate com os arquivos de dados (totais, placar, donos).
   - Segurança: dados adulterados não viram link perigoso; nenhuma violação da CSP.
   - Caos: arquivos que não carregam, chegam cortados, com formato errado ou devagar nunca deixam a tela em branco. */
import { expect, test, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";

const dados = (rel: string) => JSON.parse(readFileSync(new URL(`../public/data/${rel}`, import.meta.url), "utf-8"));
const meta = dados("meta.json");
const pols: { id: string; nome: string; casa: string; total: number }[] = dados("politicos.json");
const vots: { id: string; sim: number; nao: number }[] = dados("votacoes.json");
const empresas: { cnpj: string }[] = dados("empresas.json");
const ANO = String(meta.anos[meta.anos.length - 1]);
const brl = (v: number, centavos = false) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: centavos ? 2 : 0 }).format(v);
const sp = (s: string) => s.replace(/\s/g, " ");

/** Guarda erros de JavaScript e violações de CSP; o teste falha se aparecer algum. */
function vigiar(page: Page) {
  const erros: string[] = [];
  page.on("pageerror", (e) => erros.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|Erro ao mostrar/.test(m.text())) erros.push(m.text()); });
  page.on("dialog", (d) => { erros.push(`dialog: ${d.message()}`); d.dismiss(); });
  // Fotos e fontes de fora: resposta local, o teste não depende da internet
  page.route(/^https:\/\/(?!localhost)/, (r) => r.fulfill({ status: 200, contentType: "image/png", body: Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", "base64") }));
  return erros;
}

test.describe("jornada", () => {
  test("início mostra o total do ano igual ao meta.json", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./");
    await expect(page.locator(".hero .big")).toBeVisible();
    const v = meta.total_por_ano[ANO];
    const curto = v >= 1e6 ? `R$ ${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`
      : `R$ ${(v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mil`;
    expect(sp(await page.locator(".hero .big").innerText())).toBe(curto);
    await expect(page.locator(".hero")).toContainText(`${meta.contagens.politicos} deputados federais e senadores`);
    expect(erros).toEqual([]);
  });

  test("busca e página do parlamentar com o total certo", async ({ page }) => {
    const erros = vigiar(page);
    const p = pols.filter((x) => x.casa === "camara").sort((a, b) => b.total - a.total)[0];
    await page.goto("./");
    await page.getByLabel("Procure seu deputado ou senador").fill(p.nome);
    await page.locator(".list a", { hasText: p.nome }).first().click();
    await expect(page).toHaveURL(new RegExp(`#/p/${p.id}`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(p.nome);
    const detalhe = dados(`p/${p.id}.json`);
    await expect(page.locator("main")).toContainText(sp(brl(detalhe.anos[ANO].total)));
    await page.getByRole("tab", { name: "Votos" }).click();
    await expect(page.locator("main")).toContainText(/Sim|Não/);
    expect(erros).toEqual([]);
  });

  test("votação mostra o placar do arquivo", async ({ page }) => {
    const erros = vigiar(page);
    const v = vots[0];
    await page.goto(`./#/v/${v.id}`);
    await expect(page.locator("main")).toContainText(`Sim ${v.sim} · Não ${v.nao}`);
    expect(erros).toEqual([]);
  });

  test("empresa com holding mostra a pessoa dona no fim da cadeia", async ({ page }) => {
    const erros = vigiar(page);
    const alvo = empresas.find((e) => (dados(`e/${e.cnpj}.json`).donos_finais || []).some((d: { fim: string }) => d.fim === "pessoa"));
    expect(alvo).toBeTruthy();
    await page.goto(`./#/e/${alvo!.cnpj}`);
    await expect(page.locator("main")).toContainText("DONA FINAL");
    expect(erros).toEqual([]);
  });

  test("incentivos: quem recebeu mais, donos e quem deu mais batem com os arquivos", async ({ page }) => {
    const erros = vigiar(page);
    const inc = dados(`incentivos/${ANO}.json`);
    const maior = inc.pagamentos.top[0];
    await page.goto("./#/incentivos");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Quem ganha com o dinheiro público");
    // para onde vai o dinheiro: setor privado e setor público, com o maior recebedor público
    const destino = inc.pagamentos.destino;
    const secDestino = page.locator("section", { has: page.getByRole("heading", { name: /setor privado ou setor público/ }) });
    await expect(secDestino).toContainText(destino.publico.top[0].nome);
    await expect(secDestino).toContainText(sp(brl(destino.publico.top[0].valor)));
    const tabela = page.locator(".inc-tabela");
    await expect(tabela.locator("tbody tr").first()).toContainText(maior.nome);
    await expect(tabela.locator("tbody tr").first()).toContainText(sp(brl(maior.valor)));
    await expect(tabela.locator("tbody tr").first()).toContainText(maior.donos[0]);
    // renúncia fiscal: o ano padrão é o último completo
    const idx = dados("incentivos/indice.json");
    const anoR = idx.anos_renuncia.filter((a: { parcial: boolean }) => !a.parcial).pop().ano;
    const ren = dados(`incentivos/renuncia-${anoR}.json`);
    await page.getByRole("group", { name: "De onde vem o dinheiro" }).first().getByRole("button", { name: "Deixou de pagar imposto" }).click();
    await expect(tabela.locator("tbody tr").first()).toContainText(ren.top[0].nome);
    await expect(tabela.locator("tbody tr").first()).toContainText(sp(brl(ren.top[0].valor)));
    // quem deu mais: partidos das emendas
    for (const p of inc.emendas.partidos) await expect(page.locator("main")).toContainText(p.sigla);
    await expect(page.locator(".emd-autor").first()).toContainText(inc.emendas.politicos[0].nome);
    // a empresa abre com os donos e o que recebeu do governo
    await page.getByRole("button", { name: "Recebeu do governo" }).first().click();
    await tabela.locator("tbody tr").first().getByRole("link", { name: maior.nome }).click();
    await expect(page).toHaveURL(new RegExp(`#/e/${maior.cnpj}`));
    await expect(page.locator("main")).toContainText("Pagamentos do governo federal");
    await expect(page.locator("main")).toContainText(maior.donos[0]);
    // e o dinheiro de cada ano, com o que explica o valor
    const emp = dados(`e/${maior.cnpj}.json`);
    const bloco = page.locator(".ano-bloco", { has: page.getByRole("heading", { name: ANO, exact: true }) });
    await expect(bloco).toContainText(sp(brl(emp.governo.anos[ANO].valor)));
    await expect(bloco).toContainText(emp.governo.anos[ANO].cats[0][0]);
    expect(erros).toEqual([]);
  });

  test("incentivos: sem dados do ano do menu, mostra o ano mais recente que existe e avisa", async ({ page }) => {
    const erros = vigiar(page);
    const ANTES = String(Number(ANO) - 1);
    const idx = dados("incentivos/indice.json");
    const inc = dados(`incentivos/${ANO}.json`);
    await page.route("**/data/incentivos/indice.json", (r) => r.fulfill({ json: { ...idx, anos: [Number(ANTES)], anos_renuncia: [] } }));
    await page.route(`**/data/incentivos/${ANTES}.json`, (r) => r.fulfill({ json: { ...inc, ano: Number(ANTES) } }));
    await page.goto("./#/incentivos");
    await expect(page.locator(".aviso-ano")).toContainText(`Ainda não temos os pagamentos de ${ANO}`);
    await expect(page.locator(".aviso-ano")).toContainText(`são de ${ANTES}`);
    await expect(page.locator(".inc-tabela tbody tr").first()).toContainText(inc.pagamentos.top[0].nome);
    await expect(page.locator("main")).toContainText("O arquivo ainda não foi baixado do Portal da Transparência");
    expect(erros).toEqual([]);
  });

  test("arrecadação e gastos: primeira aba, abre no ano mais recente e os sinais batem com o arquivo", async ({ page }) => {
    const erros = vigiar(page);
    const idx = dados("financas/indice.json");
    const ultimo = String(Math.max(...idx.anos));
    const fin = dados(`financas/${ultimo}.json`);
    await page.goto("./");
    await expect(page.locator("nav.nav a").first()).toHaveText("Arrecadação e gastos");
    await page.locator("nav.nav a").first().click();
    await expect(page.locator(".fin-ano[aria-pressed=true]")).toHaveText(ultimo);
    await expect(page.locator("[data-testid=kpi]")).toHaveCount(fin.kpis.length);
    const vermelhos = fin.kpis.filter((k: { nivel: string }) => k.nivel === "vermelho").length;
    await expect(page.locator("#sinais")).toContainText(`Vermelho (${vermelhos})`);
    await expect(page.locator("#destino")).toContainText(fin.funcoes.funcoes[0].nome);
    await expect(page.locator("#cargos")).toContainText("Comissionados sem concurso");
    await expect(page.locator("#poderes a[href^='https://apidatalake.tesouro.gov.br/']").first()).toBeVisible();
    // Outro ano: troca os números, sem somar os anos
    const antes = String(Number(ultimo) - 1);
    await page.locator(".fin-ano", { hasText: antes }).click();
    await expect(page.locator(".hero .eyebrow")).toContainText(antes);
    expect(erros).toEqual([]);
  });

  test("todas as páginas do menu abrem sem erro", async ({ page }) => {
    const erros = vigiar(page);
    for (const rota of ["dinheiro", "politicos", "empresas", "votacoes", "partidos", "emendas", "incentivos", "sobre"]) {
      await page.goto(`./#/${rota}`);
      await expect(page.locator("main")).not.toBeEmpty();
      await expect(page.locator("main")).not.toContainText("Não foi possível");
    }
    expect(erros).toEqual([]);
  });

  test("sem rolagem lateral no celular", async ({ page }, info) => {
    test.skip(info.project.name !== "celular");
    vigiar(page);
    for (const rota of ["", `#/p/${pols[0].id}`, "#/votacoes", "#/empresas", "#/incentivos", "#/dinheiro"]) {
      await page.goto(`./${rota}`);
      await expect(page.locator("main")).not.toBeEmpty();
      const largura = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(largura, rota).toBeLessThanOrEqual(1);
    }
  });
});

test("barra dos projetos liga o nacional aos outros sites do Segredos Abertos", async ({ page }) => {
  await page.goto("./");
  const nav = page.getByRole("navigation", { name: "Projetos do Segredos Abertos" });
  await expect(nav.getByRole("link", { name: "Brasil" })).toHaveAttribute("href", "./");
  await expect(nav.getByRole("link", { name: "Minas Nossa" })).toHaveAttribute("href", "mg/");
  await expect(nav.getByRole("link", { name: "Eleição 2026" })).toHaveAttribute("href", "eleicao2026/");
  await expect(nav.locator('a[aria-current="page"]')).toHaveText("Brasil");
});

test.describe("idiomas e buscadores", () => {
  test("troca para inglês e espanhol e volta para português", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./");
    await expect(page.getByRole("navigation", { name: "Projetos do Segredos Abertos" })).toBeVisible();
    await page.locator(".linguas").getByRole("link", { name: "EN", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByRole("navigation", { name: "Segredos Abertos projects" })).toContainText("Projects:");
    await expect(page.locator(".linguas").getByRole("link", { name: "ES", exact: true })).toHaveAttribute("href", /lang=es/);
    await page.locator(".linguas").getByRole("link", { name: "ES", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await expect(page.getByRole("navigation", { name: "Proyectos de Segredos Abertos" })).toContainText("Proyectos:");
    // A escolha fica guardada: abrir de novo sem ?lang= continua em espanhol
    await page.goto("./");
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await page.locator(".linguas").getByRole("link", { name: "PT", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "pt-BR");
    await expect(page.getByRole("navigation", { name: "Projetos do Segredos Abertos" })).toContainText("Projetos:");
    expect(erros).toEqual([]);
  });

  test("em inglês, a página de um político traduz os rótulos e mantém o nome", async ({ page }) => {
    const erros = vigiar(page);
    const p = pols[0];
    await page.goto(`./?lang=en#/p/${p.id}`);
    await expect(page.locator("h1")).toContainText(p.nome);
    await expect(page.locator("body")).not.toContainText("Projetos:");
    expect(erros).toEqual([]);
  });

  test("cabeçalho tem hreflang, canonical e dados estruturados", async ({ page }) => {
    await page.goto("./");
    for (const l of ["pt-BR", "en", "es", "x-default"]) await expect(page.locator(`link[rel=alternate][hreflang="${l}"]`)).toHaveCount(1);
    await expect(page.locator("link[rel=canonical]")).toHaveCount(1);
    const ld = JSON.parse((await page.locator('script[type="application/ld+json"]').first().textContent()) || "{}");
    expect(JSON.stringify(ld)).toContain("Dataset");
  });

  test("páginas simples para buscadores e IAs: político, robots.txt, sitemap e llms.txt", async ({ page, request }) => {
    const robots = await (await request.get("./robots.txt")).text();
    expect(robots).toMatch(/GPTBot/);
    expect(robots).toMatch(/ClaudeBot/);
    expect(robots).toMatch(/Sitemap: https:\/\/.+sitemap\.xml/);
    expect(await (await request.get("./sitemap.xml")).text()).toContain("sitemap-paginas.xml");
    const mapa = await (await request.get("./sitemap-paginas.xml")).text();
    expect(mapa).toContain("/politico/");
    expect(await (await request.get("./llms.txt")).text()).toContain("Segredos Abertos");
    const p = pols[0];
    const url = (mapa.match(new RegExp(`https://[^<]*/politico/[^<]*-${p.id}\\.html`)) || [])[0];
    expect(url).toBeTruthy();
    for (const pre of ["", "en/", "es/"]) {
      await page.goto("./" + pre + new URL(url!).pathname.replace(/^.*\/politico\//, "politico/"));
      await expect(page.locator("h1")).toContainText(p.nome);
      await expect(page.locator(`a[href*="#/p/${p.id}"]`).first()).toBeVisible();
    }
  });
});

test.describe("segurança", () => {
  test("CSP no HTML publicado", async ({ page }) => {
    await page.goto("./");
    const csp = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute("content");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("object-src 'none'");
  });

  test("dados adulterados não viram link javascript:", async ({ page }) => {
    const erros = vigiar(page);
    const p = pols[0];
    const ruim = "javascript:alert(document.domain)";
    await page.route(`**/data/p/${p.id}.json`, async (r) => {
      const x = dados(`p/${p.id}.json`);
      x.fonte = ruim; x.foto = ruim;
      for (const a of Object.values(x.anos) as { maiores_notas: { url: string }[] }[]) a.maiores_notas.forEach((n) => (n.url = ruim));
      await r.fulfill({ json: x });
    });
    await page.goto(`./#/p/${p.id}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(p.nome);
    expect(await page.locator('a[href^="javascript:" i], img[src^="javascript:" i]').count()).toBe(0);
    for (const a of await page.locator("a").all()) await a.click({ trial: true }).catch(() => {});
    expect(erros).toEqual([]);
  });

  test("texto com HTML nos dados aparece como texto", async ({ page }) => {
    const erros = vigiar(page);
    const v = vots[0];
    await page.route(`**/data/v/${v.id}.json`, async (r) => {
      const x = dados(`v/${v.id}.json`);
      x.descricao = '<img src=x onerror="alert(1)">Votação';
      await r.fulfill({ json: x });
    });
    await page.goto(`./#/v/${v.id}`);
    await expect(page.locator("main")).toContainText('<img src=x onerror="alert(1)">');
    expect(await page.locator("main img[src='x']").count()).toBe(0);
    expect(erros).toEqual([]);
  });
});

test.describe("caos no navegador", () => {
  const p = () => pols[1];

  test("arquivo que não carrega mostra aviso, não tela em branco", async ({ page }) => {
    vigiar(page);
    await page.route(`**/data/p/${p().id}.json`, (r) => r.abort("failed"));
    await page.goto(`./#/p/${p().id}`);
    await expect(page.locator("main")).toContainText("Não foi possível carregar");
    await expect(page.getByRole("navigation", { name: "Principal" })).toBeVisible();
  });

  test("JSON cortado no meio mostra aviso", async ({ page }) => {
    vigiar(page);
    await page.route(`**/data/p/${p().id}.json`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: '{"id":"dep' }));
    await page.goto(`./#/p/${p().id}`);
    await expect(page.locator("main")).toContainText("Não foi possível carregar");
  });

  test("formato inesperado não derruba o site", async ({ page }) => {
    vigiar(page);
    await page.route(`**/data/p/${p().id}.json`, (r) => r.fulfill({ json: { id: p().id, nome: "X", anos: null, votos: "?" } }));
    await page.goto(`./#/p/${p().id}`);
    await expect(page.locator("main")).toContainText(/Não foi possível|Não há gastos/);
    // o menu continua funcionando depois do erro
    await page.getByRole("link", { name: "Votações" }).click();
    await expect(page.locator("main")).not.toContainText("Não foi possível mostrar");
  });

  test("servidor lento: mostra Carregando e depois o conteúdo", async ({ page }) => {
    vigiar(page);
    await page.route(`**/data/v/${vots[1].id}.json`, async (r) => { await new Promise((ok) => setTimeout(ok, 2500)); await r.continue(); });
    await page.goto(`./#/v/${vots[1].id}`);
    await expect(page.locator("main")).toContainText("Carregando");
    await expect(page.locator("main")).toContainText(`Sim ${vots[1].sim}`, { timeout: 10_000 });
  });

  test("avisos da coleta aparecem na página inicial", async ({ page }) => {
    vigiar(page);
    await page.route("**/data/meta.json", (r) => r.fulfill({ json: { ...meta, avisos: ["Votações do Senado: a API oficial não respondeu para 03/2025"] } }));
    await page.goto("./");
    await expect(page.getByRole("note").first()).toContainText("Dados incompletos");
    await expect(page.getByRole("note").first()).toContainText("03/2025");
    await expect(page.getByRole("note").first()).toContainText("a cada 2 horas");
  });

  test("macaco do caos: falhas aleatórias em todos os dados", async ({ page }) => {
    let semente = 42;
    const aleatorio = () => ((semente = (semente * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
    const erros: string[] = [];
    page.on("pageerror", (e) => erros.push(e.message));
    await page.route("**/data/**", async (r: Route) => {
      const x = aleatorio();
      if (x < 0.15) return r.abort("failed");
      if (x < 0.25) return r.fulfill({ status: 500, body: "erro" });
      if (x < 0.32) return r.fulfill({ status: 200, contentType: "application/json", body: "{" });
      if (x < 0.4) await new Promise((ok) => setTimeout(ok, 400));
      return r.continue();
    });
    const rotas = ["", "#/politicos", `#/p/${pols[0].id}`, `#/p/${pols[2].id}?aba=votos`, "#/empresas", `#/e/${empresas[0].cnpj}`,
      "#/votacoes", `#/v/${vots[0].id}`, "#/partidos", "#/emendas"];
    for (const rota of rotas) {
      await page.goto(`./${rota}`);
      await page.waitForTimeout(600);
      await expect(page.locator("header.top")).toBeVisible();
      expect((await page.locator("main").innerText()).trim().length, rota).toBeGreaterThan(0);
    }
    expect(erros).toEqual([]);
  });
});
