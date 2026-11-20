// Visual igual nos três sites: as cores principais e a letra do Brasil e Minas Nossa (tema.ts) e do Terras Raras são
// as da Eleição 2026 (bloco "Visual do Segredos Abertos" de eleicao2026/site/corpo.html). Se alguém mudar uma página
// sem mudar as outras, este teste avisa.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ler = (p: string) => readFileSync(new URL(p, import.meta.url), "utf-8");
const eleicao = ler("../../eleicao2026/site/corpo.html");
const tema = ler("../src/tema.ts");
const terras = ler("../../terras-raras/pagina_modelo.html");
const visual = eleicao.slice(eleicao.indexOf("Visual do Segredos Abertos"));
const cor = (nome: string) => (visual.match(new RegExp(`${nome}:(#[0-9A-Fa-f]{6})`)) || [])[1]?.toUpperCase();

test("a Eleição 2026 ainda tem as cores de referência", () => {
  for (const n of ["--sa-faixa", "--br-blue", "--br-green", "--br-gold"]) assert.ok(cor(n), n);
});

for (const [nome, texto] of [["tema.ts (Brasil e Minas Nossa)", tema], ["Terras Raras", terras]] as const) {
  test(`${nome} usa a faixa, o azul, o verde e o amarelo da Eleição 2026 e a letra Raleway`, () => {
    const t = texto.toUpperCase();
    for (const n of ["--sa-faixa", "--br-blue", "--br-green", "--br-gold"]) assert.ok(t.includes(cor(n)!), `${n} ${cor(n)}`);
    assert.match(texto, /Raleway/);
  });
}
