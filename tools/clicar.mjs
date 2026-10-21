import { chromium } from "playwright-core";
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome" });
const p = await b.newPage({ viewport: { width: 390, height: 844 } });
p.on("console", m => m.type() !== "warning" && console.log("console", m.type(), m.text()));
p.on("pageerror", e => console.log("pageerror", e.message));
p.on("requestfailed", r => console.log("requestfailed", r.url(), r.failure()?.errorText));
p.on("response", r => r.status() >= 400 && console.log("http", r.status(), r.url()));
const base = process.env.BASE || "https://amarigo.github.io/segredos-abertos/";
await p.goto(base); await p.waitForTimeout(4000);
const txt = async () => (await p.locator("main").innerText({ timeout: 5000 }).catch(() => "SEM MAIN")).slice(0, 120).replace(/\n/g, " | ");
console.log("home:", await txt());
for (const n of ["Políticos", "Empresas", "Votações", "Políticos"]) {
  await p.click(`nav >> text=${n}`); await p.waitForTimeout(2500); console.log(n, "->", await txt());
}
await p.click("main a.person >> nth=0"); await p.waitForTimeout(2500); console.log("perfil ->", await txt());
await p.click("role=tab[name='Votos']"); await p.waitForTimeout(2500); console.log("votos ->", await txt());
await p.click("role=tab[name='Gastos']"); await p.waitForTimeout(2500); console.log("gastos ->", await txt());
await p.reload(); await p.waitForTimeout(3000); console.log("reload ->", await txt());
await p.click(`nav >> text=Empresas`); await p.waitForTimeout(2500); console.log("empresas2 ->", await txt());
await b.close();
