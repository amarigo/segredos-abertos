// Testes do tradutor PT/EN/ES (public/i18n/tradutor.js) e dos dicionários. Rodam com: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

// tradutor.js é um script comum do navegador; em Node, roda isolado e devolve as funções em module.exports
const modulo = { exports: {} as Record<string, any> };
runInNewContext(readFileSync(new URL("../public/i18n/tradutor.js", import.meta.url), "utf-8"), { module: modulo });
const { chave, numeroIngles, traduzirTexto } = modulo.exports;
const dic = (arq: string) => JSON.parse(readFileSync(new URL(arq, import.meta.url), "utf-8")) as Record<string, string>;

test("chave troca números por {n} e junta espaços", () => {
  assert.equal(chave("  Gastou   R$ 1.234,56 em 2024 ").k, "Gastou R$ {0} em {1}");
  assert.equal(chave("Sem número").k, "Sem número");
});

test("CNPJ e datas ficam iguais em inglês (sem trocar ponto por vírgula)", () => {
  const d = { "CNPJ {0}/{1}-{2}": "Tax ID {0}/{1}-{2}" };
  assert.equal(traduzirTexto("CNPJ 12.345.678/0001-90", d, "en"), "Tax ID 12.345.678/0001-90");
});

test("números em inglês usam ponto decimal e vírgula de milhar", () => {
  assert.equal(numeroIngles("1.234,5"), "1,234.5");
  assert.equal(numeroIngles("12,5"), "12.5");
  assert.equal(numeroIngles("2024"), "2024");
  const d = { "Gastou R$ {0}": "Spent R$ {0}" };
  assert.equal(traduzirTexto("Gastou R$ 1.234,56", d, "en"), "Spent R$ 1,234.56");
  assert.equal(traduzirTexto("Gastou R$ 1.234,56", { "Gastou R$ {0}": "Gastó R$ {0}" }, "es"), "Gastó R$ 1.234,56");
});

test("texto sem tradução devolve null (fica em português)", () => {
  assert.equal(traduzirTexto("Maria da Silva", {}, "en"), null);
});

test("{*} deixa passar nomes no meio da frase", () => {
  const d = { "Foto de {*}": "Photo of {*}" };
  assert.equal(traduzirTexto("Foto de João Pereira", d, "en"), "Photo of João Pereira");
});

test("dicionários: mesmas chaves em EN e ES, e cada tradução mantém os {n} do original", () => {
  for (const [en, es] of [["../public/i18n/en.json", "../public/i18n/es.json"],
    ["../../eleicao2026/site/i18n/en.json", "../../eleicao2026/site/i18n/es.json"]]) {
    const a = dic(en), b = dic(es);
    assert.deepEqual(Object.keys(a).sort(), Object.keys(b).sort(), en);
    const ph = (t: string) => [...new Set(t.match(/\{\d+\}/g) || [])].sort().join();
    for (const k of Object.keys(a)) {
      assert.equal(ph(a[k]), ph(k), `EN: ${k}`);
      assert.equal(ph(b[k]), ph(k), `ES: ${k}`);
    }
    // O nome do projeto não se traduz
    assert.ok(!("Segredos Abertos" in a) && !("Segredos Abertos Brasil" in a));
  }
});
