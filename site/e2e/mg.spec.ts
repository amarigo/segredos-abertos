/* Testes de navegador do Minas Nossa, com os dados fictícios do FakeGov (recorte de MG) e do FakeTSE (cidades).
   - Jornada: o que a pessoa vê na página da cidade bate com os arquivos (prefeito, cadeiras, resumo).
   - Segurança: dados adulterados não viram link perigoso; nenhum CPF na tela.
   - Caos: arquivo da cidade que não carrega, cortado ou com formato errado nunca deixa a tela em branco. */
import { expect, test, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";

const dados = (rel: string) => JSON.parse(readFileSync(new URL(`../public-mg/data/${rel}`, import.meta.url), "utf-8"));
const meta = dados("meta.json");
const cidades: { id: string; nome: string }[] = dados("cidades.json");
const vots: { id: string; sim: number; nao: number; placar_casa: { sim: number; nao: number } }[] = dados("votacoes.json");
const ita = dados("cidades/itajuba.json");
const almgIdx = dados("almg/deputados.json");
const dep = dados("almg/d/20003.json");
const gov = dados("estado/governo.json");
const dinheiroIta = dados("cidades/dinheiro/itajuba.json");
const emEst = dados("estado/emendas.json");
const brl = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v).replace(/\s/g, " ");
const CPF = /(?<![\d.\/])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d.])/;

function vigiar(page: Page) {
  const erros: string[] = [];
  page.on("pageerror", (e) => erros.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|Erro ao mostrar/.test(m.text())) erros.push(m.text()); });
  page.on("dialog", (d) => { erros.push(`dialog: ${d.message()}`); d.dismiss(); });
  page.route(/^https:\/\/(?!localhost)/, (r) => r.fulfill({ status: 200, contentType: "image/png", body: Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", "base64") }));
  return erros;
}

test.describe("jornada", () => {
  test("início do Minas Nossa: só MG e atalho para as cidades", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./");
    await expect(page.locator(".brand")).toContainText("Minas Nossa");
    await expect(page).toHaveTitle(/^Minas Nossa/);
    await expect(page.locator(".hero")).toContainText(`${meta.contagens.politicos} deputados federais e senadores de Minas Gerais`);
    const nav = page.getByRole("navigation", { name: "Principal" });
    await expect(nav.getByRole("link", { name: "Cidades" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Emendas" })).toHaveAttribute("href", "#/emendas-estaduais");
    for (const c of cidades) await expect(page.locator("main")).toContainText(c.nome);
    for (const nome of ["Governo do estado", "Deputados estaduais", "Emendas estaduais"]) {
      await expect(page.locator("main").getByRole("link", { name: new RegExp(nome) })).toBeVisible();
    }
    expect(erros).toEqual([]);
  });

  test("todas as páginas do menu abrem sem erro", async ({ page }) => {
    const erros = vigiar(page);
    for (const rota of ["politicos", "cidades", "empresas", "votacoes", "votacoes/em-andamento", "votacoes/em-andamento?aba=almg", "partidos", "sobre", "governo", "assembleia", "emendas-estaduais",
      "deputado-estadual/20003", "deputado-estadual/20003?aba=atuacao", "deputado-estadual/20003?aba=emendas",
      ...cidades.map((c) => `cidade/${c.id}`), ...cidades.map((c) => `cidade/${c.id}?aba=dinheiro`)]) {
      await page.goto(`./#/${rota}`);
      await expect(page.locator("main")).not.toBeEmpty();
      await expect(page.locator("main")).not.toContainText("Não foi possível");
    }
    expect(erros).toEqual([]);
  });

  test("página da cidade mostra o prefeito, a Câmara e o resumo do arquivo", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/cidades");
    await page.getByRole("link", { name: /Itajubá/ }).first().click();
    await expect(page).toHaveURL(/#\/cidade\/itajuba/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Itajubá");
    const atual = ita.executivo[0];
    const hoje = page.locator("section", { has: page.getByRole("heading", { name: "De quem cobrar hoje" }) });
    await expect(hoje).toContainText(atual.prefeito.nome);
    await expect(hoje).toContainText(`${ita.camara[0].vagas} vereadores`);
    // uma faixa por mandato e um quadradinho por cadeira
    await expect(page.locator(".linha-faixas span")).toHaveCount(ita.executivo.length);
    await expect(page.locator(".mandato")).toHaveCount(ita.executivo.length);
    await expect(page.locator(".legislatura").first().locator(".cadeira")).toHaveCount(ita.camara[0].vagas);
    const lider = ita.resumo.anos_por_partido[0];
    await expect(page.locator(".resumo-cidade")).toContainText(String(lider.anos));
    expect(erros).toEqual([]);
  });

  test("história de um partido: mandatos e vereadores eleitos", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/cidade/itajuba");
    const p = ita.executivo[ita.executivo.length - 1].prefeito.partido_hoje;
    await page.getByLabel("Ver a história de um partido").selectOption(p);
    const card = page.locator(".historia");
    await expect(card).toContainText("Governou Itajubá");
    const cadeiras = ita.camara.reduce((a: number, l: { por_partido: { partido_hoje: string; cadeiras: number }[] }) =>
      a + l.por_partido.filter((x) => x.partido_hoje === p).reduce((b, x) => b + x.cadeiras, 0), 0);
    await expect(card).toContainText(`Elegeu ${cadeiras} `);
    await expect(page.locator(".mandato.apagado")).toHaveCount(ita.executivo.filter((m: { prefeito: { partido_hoje: string } }) => m.prefeito.partido_hoje !== p).length);
    expect(erros).toEqual([]);
  });

  test("partido antigo aparece com o nome de hoje", async ({ page }) => {
    vigiar(page);
    const m = ita.executivo.find((x: { prefeito: { partido: string; partido_hoje: string } }) => x.prefeito.partido !== x.prefeito.partido_hoje);
    test.skip(!m, "sem partido renomeado nos dados de teste");
    await page.goto("./#/cidade/itajuba");
    await expect(page.locator(".mandatos")).toContainText(`${m.prefeito.partido} (hoje ${m.prefeito.partido_hoje})`);
  });

  test("como a cidade votou: troca de eleição", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/cidade/itajuba");
    const antiga = ita.gerais[ita.gerais.length - 1];
    await page.getByRole("button", { name: String(antiga.eleicao), exact: true }).click();
    await expect(page.getByRole("button", { name: String(antiga.eleicao), exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("main")).toContainText(antiga.cargos[0].candidatos[0].nome);
    expect(erros).toEqual([]);
  });

  test("votação mostra o placar da Casa e o da bancada de MG", async ({ page }) => {
    const erros = vigiar(page);
    const v = vots[0];
    await page.goto(`./#/v/${v.id}`);
    await expect(page.locator("main")).toContainText(`Sim ${v.placar_casa.sim} · Não ${v.placar_casa.nao}`);
    await expect(page.locator("main")).toContainText(`Bancada de MG: Sim ${v.sim} · Não ${v.nao}`);
    await expect(page.getByRole("heading", { name: "Como votou a bancada de Minas Gerais" })).toBeVisible();
    expect(erros).toEqual([]);
  });

  test("sem rolagem lateral no celular", async ({ page }, info) => {
    test.skip(info.project.name !== "celular");
    vigiar(page);
    for (const rota of ["", "#/cidades", "#/cidade/itajuba", "#/cidade/paraisopolis", "#/votacoes", "#/votacoes/em-andamento", `#/v/${vots[0].id}`, "#/governo",
      "#/assembleia", "#/deputado-estadual/20003", "#/emendas-estaduais", "#/cidade/itajuba?aba=dinheiro"]) {
      await page.goto(`./${rota}`);
      await expect(page.locator("main")).not.toBeEmpty();
      await page.waitForTimeout(300);
      const largura = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(largura, rota).toBeLessThanOrEqual(1);
    }
  });

  test("a página das emendas federais do site nacional fica fora do Minas Nossa", async ({ page }) => {
    vigiar(page);
    await page.goto("./#/emendas");
    await expect(page.locator("main")).toContainText("Página não encontrada");
  });

  test("deputado estadual: a verba da página bate com o arquivo e leva à prestação de contas na ALMG", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/assembleia");
    await expect(page.locator(".person")).toHaveCount(almgIdx.deputados.length);
    await page.locator("#filtro-nome").fill(dep.nome);
    await page.locator(".person").first().click();
    await expect(page).toHaveURL(/#\/deputado-estadual\/20003/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(dep.nome);
    const ano = Object.keys(dep.anos).sort().pop()!;
    const v = dep.anos[ano].verba;
    await expect(page.locator("main")).toContainText(brl(v.total));
    await expect(page.locator("main")).toContainText("Pessoa física");
    await expect(page.getByRole("link", { name: /prestação de contas/ })).toHaveAttribute("href", /verba-indenizatoria\/detalhe\.html\?id=20003/);
    await page.getByRole("tab", { name: "Atuação" }).click();
    const pr = dep.anos[ano].proposicoes;
    if (pr?.lista.length) await expect(page.getByRole("link", { name: new RegExp(`${pr.lista[0].sigla} ${pr.lista[0].numero}/`) }).first()).toHaveAttribute("href", /almg\.gov\.br\/atividade-parlamentar\/projetos-de-lei\/texto/);
    await page.getByRole("tab", { name: "Emendas" }).click();
    await expect(page).toHaveURL(/aba=emendas/);
    expect(erros).toEqual([]);
  });

  test("governo: eleito pelo TSE, quem está na folha hoje, salário e viagens", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/governo");
    await expect(page.locator("main")).toContainText(gov.eleicoes[0].governador.nome);
    const g = gov.equipe.pessoas[0];
    await expect(page.locator("main")).toContainText(`quem recebe como governador é ${g.nome}`);
    await expect(page.locator("main")).toContainText(brl(g.bruto));
    const sec = gov.equipe.pessoas.find((p: { cargo: string; viagens: unknown }) => /^Secretario/i.test(p.cargo) && p.viagens);
    await page.getByRole("button", { name: "Ver viagens" }).first().click();
    await expect(page.locator(".lista-viagens").last()).toContainText(sec.viagens.ultimas[0].destinos[0]);
    expect(erros).toEqual([]);
  });

  test("dinheiro da cidade: contas da prefeitura, emendas federais e estaduais, com a fonte", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/cidade/itajuba");
    await page.getByRole("tab", { name: "Dinheiro" }).click();
    await expect(page).toHaveURL(/aba=dinheiro/);
    const main = page.locator("main");
    await expect(main).toContainText(`Gasto em ${dinheiroIta.contas.anos[0].ano}`);
    await expect(main).toContainText(brl(dinheiroIta.federais.por_ano[0].valor));
    await expect(main).toContainText("Pessoa física");
    await expect(main.getByRole("link", { name: /SICONFI/ })).toBeVisible();
    await expect(main.getByRole("link", { name: /Portal da Transparência \(CGU\)/ })).toBeVisible();
    await expect(main).toContainText(dinheiroIta.estaduais.lista[0].beneficiario);
    for (const a of await main.locator("a[href^='http']").evaluateAll((as) => as.map((x) => (x as HTMLAnchorElement).href))) {
      expect(a).toMatch(/^https:\/\/(siconfi\.tesouro|apidatalake\.tesouro|portaldatransparencia|www\.almg|dados\.mg|www\.transparencia\.mg|dadosabertos\.tse|[a-z.]+\.mg\.(gov|leg)\.br)/);
    }
    expect(erros).toEqual([]);
  });

  test("emendas estaduais: o ranking soma o total e leva ao deputado", async ({ page }) => {
    const erros = vigiar(page);
    await page.goto("./#/emendas-estaduais");
    const ano = Object.keys(emEst.anos).sort().pop()!;
    await expect(page.locator("main")).toContainText(`Indicado em ${ano}`);
    await page.locator("main .bar-label a, main a[href*='deputado-estadual']").first().click();
    await expect(page).toHaveURL(/deputado-estadual\/\d+\?aba=emendas/);
    expect(erros).toEqual([]);
  });
});

test.describe("segurança", () => {
  test("nenhum CPF nas páginas do estado (os arquivos de teste trazem CPF de propósito)", async ({ page }) => {
    vigiar(page);
    for (const rota of ["#/deputado-estadual/20003", "#/governo", "#/cidade/itajuba?aba=dinheiro", "#/emendas-estaduais"]) {
      await page.goto(`./${rota}`);
      await expect(page.locator("main")).not.toBeEmpty();
      await page.getByRole("button", { name: "Ver viagens" }).first().click({ timeout: 1000 }).catch(() => {});
      expect(await page.locator("main").innerText(), rota).not.toMatch(CPF);
      const links = await page.locator("main a").evaluateAll((as) => as.map((x) => (x as HTMLAnchorElement).href));
      expect(links.filter((h) => CPF.test(h.replace(/\d{14}/g, ""))), rota).toEqual([]);
    }
  });

  test("id de deputado estadual com caminho não busca arquivo fora da pasta", async ({ page }) => {
    vigiar(page);
    const pedidos: string[] = [];
    page.on("request", (r) => pedidos.push(r.url()));
    await page.goto("./#/deputado-estadual/..%2F..%2Fmeta");
    await expect(page.locator("main")).toContainText("Deputado não encontrado");
    expect(pedidos.filter((u) => u.includes("almg/d/.."))).toEqual([]);
  });

  test("nenhum CPF na página da cidade", async ({ page }) => {
    vigiar(page);
    await page.goto("./#/cidade/itajuba");
    await page.locator("details").evaluateAll((ds) => ds.forEach((d) => d.setAttribute("open", "")));
    const texto = await page.locator("main").innerText();
    expect(texto).not.toMatch(/(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)/);
  });

  test("dados da cidade adulterados não viram link javascript: nem HTML", async ({ page }) => {
    const erros = vigiar(page);
    await page.route("**/data/cidades/itajuba.json", (r) => r.fulfill({ json: {
      ...ita, links: [{ nome: "ruim", url: "javascript:alert(document.domain)" }],
      executivo: [{ ...ita.executivo[0], prefeito: { ...ita.executivo[0].prefeito, nome: '<img src=x onerror="alert(1)">' } }, ...ita.executivo.slice(1)],
    } }));
    await page.goto("./#/cidade/itajuba");
    await expect(page.locator("main")).toContainText('<img src=x onerror="alert(1)">');
    expect(await page.locator('a[href^="javascript:" i]').count()).toBe(0);
    expect(await page.locator("main img[src='x']").count()).toBe(0);
    expect(erros).toEqual([]);
  });

  test("id de cidade com caminho não busca arquivo fora da pasta", async ({ page }) => {
    vigiar(page);
    const pedidos: string[] = [];
    page.on("request", (r) => pedidos.push(r.url()));
    await page.goto("./#/cidade/..%2F..%2Fmeta");
    await expect(page.locator("main")).toContainText("Cidade não encontrada");
    expect(pedidos.filter((u) => u.includes("cidades/.."))).toEqual([]);
  });
});

test("barra dos projetos liga o Minas Nossa aos outros sites do Segredos Abertos", async ({ page }) => {
  await page.goto("./");
  const nav = page.getByRole("navigation", { name: "Projetos do Segredos Abertos" });
  await expect(nav.getByRole("link", { name: "Brasil" })).toHaveAttribute("href", "../");
  await expect(nav.getByRole("link", { name: "Minas Nossa" })).toHaveAttribute("href", "./");
  await expect(nav.getByRole("link", { name: "Eleição 2026" })).toHaveAttribute("href", "../eleicao2026/");
  await expect(nav.getByRole("link", { name: "Terras Raras MG" })).toHaveAttribute("href", "../terras-raras/");
  await expect(nav.locator('a[aria-current="page"]')).toHaveText("Minas Nossa");
});

test("Minas Nossa troca para inglês e tem páginas simples para buscadores", async ({ page, request }) => {
  await page.goto("./?lang=en");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("navigation", { name: "Segredos Abertos projects" })).toContainText("Projects:");
  await expect(page.locator('link[rel=alternate][hreflang="es"]')).toHaveAttribute("href", /\/mg\/\?lang=es/);
  expect((await request.get("./i18n/en.json")).ok()).toBeTruthy();
  expect(await (await request.get("./sitemap-paginas.xml")).text()).toContain("/mg/");
  expect((await request.get("./indice.html")).ok()).toBeTruthy();
  expect((await request.get("./en/indice.html")).ok()).toBeTruthy();
});

test.describe("caos no navegador", () => {
  test("arquivo da cidade que não carrega mostra aviso", async ({ page }) => {
    vigiar(page);
    await page.route("**/data/cidades/itajuba.json", (r) => r.abort("failed"));
    await page.goto("./#/cidade/itajuba");
    await expect(page.locator("main")).toContainText("Não foi possível carregar");
    await expect(page.getByRole("navigation", { name: "Principal" })).toBeVisible();
  });

  test("arquivo da cidade cortado ou com formato errado não derruba o site", async ({ page }) => {
    vigiar(page);
    await page.route("**/data/cidades/itajuba.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: '{"id":"ita' }));
    await page.goto("./#/cidade/itajuba");
    await expect(page.locator("main")).toContainText("Não foi possível carregar");
    await page.unroute("**/data/cidades/itajuba.json");
    await page.route("**/data/cidades/paraisopolis.json", (r) => r.fulfill({ json: { id: "paraisopolis", nome: "X", executivo: "?" } }));
    await page.goto("./#/cidade/paraisopolis");
    await expect(page.locator("main")).toContainText(/Não foi possível/);
    await page.getByRole("link", { name: "Cidades" }).click();
    await expect(page.locator("main")).toContainText("Itajubá");
  });

  test("fontes do estado fora do ar: cada parte avisa e o resto aparece", async ({ page }) => {
    const erros = vigiar(page);
    await page.route("**/data/estado/governo.json", (r) => r.fulfill({ json: { ...gov, equipe: null } }));
    await page.goto("./#/governo");
    await expect(page.locator("main")).toContainText(gov.eleicoes[0].governador.nome);
    await expect(page.locator("main")).toContainText("não puderam ser baixados do Dados MG");
    await page.route("**/data/cidades/dinheiro/itajuba.json", (r) => r.fulfill({ json: { ...dinheiroIta, contas: null, federais: null, estaduais: null } }));
    await page.goto("./#/cidade/itajuba?aba=dinheiro");
    await expect(page.locator("main")).toContainText("não puderam ser baixadas do Tesouro Nacional");
    await expect(page.locator("main")).toContainText("Portal da Transparência não estava disponível");
    await expect(page.locator("main")).toContainText("arquivo de emendas da Assembleia não estava disponível");
    await page.route("**/data/almg/d/20003.json", (r) => r.abort("failed"));
    await page.goto("./#/deputado-estadual/20003");
    await expect(page.locator("main")).toContainText("Não foi possível carregar");
    await expect(page.getByRole("navigation", { name: "Principal" })).toBeVisible();
    expect(erros).toEqual([]);
  });

  test("verba ainda incompleta avisa em vez de parecer que o deputado não gastou", async ({ page }) => {
    vigiar(page);
    const ano = Object.keys(dep.anos).sort().pop()!;
    await page.route("**/data/almg/d/20003.json", (r) => r.fulfill({ json: { ...dep, anos: { ...dep.anos, [ano]: { ...dep.anos[ano], verba: { ...dep.anos[ano].verba, meses_faltando: [1, 2] } } } } }));
    await page.goto(`./#/deputado-estadual/20003?ano=${ano}`);
    await expect(page.getByRole("note")).toContainText("janeiro, fevereiro");
  });

  test("ano sem dados do TSE aparece como aviso na página", async ({ page }) => {
    vigiar(page);
    await page.route("**/data/cidades/itajuba.json", (r) => r.fulfill({ json: { ...ita, avisos: ["Os dados do TSE da eleição de 2008 não puderam ser baixados nesta atualização."] } }));
    await page.goto("./#/cidade/itajuba");
    await expect(page.getByRole("note").first()).toContainText("2008");
  });

  test("macaco do caos nas páginas do Minas Nossa", async ({ page }) => {
    let semente = 7;
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
    for (const rota of ["", "#/cidades", "#/cidade/itajuba", "#/cidade/paraisopolis", "#/votacoes", `#/v/${vots[0].id}`, "#/politicos",
      "#/governo", "#/assembleia", "#/deputado-estadual/20003", "#/emendas-estaduais", "#/cidade/itajuba?aba=dinheiro"]) {
      await page.goto(`./${rota}`);
      await page.waitForTimeout(600);
      await expect(page.locator("header.top")).toBeVisible();
      expect((await page.locator("main").innerText()).trim().length, rota).toBeGreaterThan(0);
    }
    expect(erros).toEqual([]);
  });
});
