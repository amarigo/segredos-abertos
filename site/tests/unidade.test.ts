// Testes unitários das funções puras do site (base da pirâmide no front-end).
// Rodam com o executor de testes do próprio Node: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  atuacaoAtiva, cnpjFmt, corPartido, dataBR, descricaoCurta, linkSeguro, pct, proposicaoNome, reais, reaisCurto,
  taxaPresenca, tipoVotacao,
} from "../src/data.ts";

test("linkSeguro só aceita http(s)", () => {
  for (const ruim of ["javascript:alert(1)", " JAVASCRIPT:alert(1)", "data:text/html,<script>", "vbscript:x", "//evil.com",
    "https://ok.gov.br/\"><img onerror=x>", "", undefined, null]) {
    assert.equal(linkSeguro(ruim as string), undefined, String(ruim));
  }
  assert.equal(linkSeguro(" https://www.camara.leg.br/x.pdf "), "https://www.camara.leg.br/x.pdf");
  assert.equal(linkSeguro("http://www.senado.leg.br/f.jpg"), "http://www.senado.leg.br/f.jpg");
});

test("dinheiro em reais", () => {
  assert.equal(reais(1234.5).replace(/\s/g, " "), "R$ 1.235");
  assert.equal(reais(1234.5, true).replace(/\s/g, " "), "R$ 1.234,50");
  assert.equal(reais(NaN).replace(/\s/g, " "), "R$ 0");
  assert.equal(reaisCurto(2_500_000_000), "R$ 2,5 bi");
  assert.equal(reaisCurto(1_200_000), "R$ 1,2 mi");
  assert.equal(reaisCurto(45_000), "R$ 45 mil");
});

test("datas, CNPJ e percentuais", () => {
  assert.equal(dataBR("2025-03-09T00:00:00"), "09/03/2025");
  assert.equal(dataBR(""), "");
  assert.equal(cnpjFmt("11222333000181"), "11.222.333/0001-81");
  assert.equal(cnpjFmt("123"), "123");
  assert.equal(pct(0.456), "46%");
  assert.equal(pct(null), "—");
});

test("tipo de votação a partir da descrição oficial", () => {
  assert.equal(tipoVotacao("Aprovado o requerimento de urgência"), "Pedido de urgência");
  assert.equal(tipoVotacao("Rejeitado o destaque do PL"), "Destaque (trecho votado à parte)");
  assert.equal(tipoVotacao("Aprovada a PEC em segundo turno"), "Texto principal, 2º turno");
  assert.equal(tipoVotacao("Aprovado o projeto, ressalvados os destaques"), "Texto principal");
  assert.equal(tipoVotacao(""), "");
});

test("descrição sem o placar e nome da proposta", () => {
  assert.equal(descricaoCurta("Aprovado o texto. Sim: 300; Não: 100; Total: 400"), "Aprovado o texto.");
  assert.equal(proposicaoNome({ sigla: "PL", numero: "12", ano: "2025", ementa: "", titulo: "", url: "" }), "PL 12/2025");
  assert.equal(proposicaoNome(null), "");
});

test("atuação e presença", () => {
  assert.equal(atuacaoAtiva(undefined), false);
  assert.equal(atuacaoAtiva({ plenario: [0, 0, 0] }), false);
  assert.equal(atuacaoAtiva({ autoria: 1 }), true);
  assert.equal(taxaPresenca([3, 1, 0]), 0.75);
  assert.equal(taxaPresenca([0, 0, 0]), null);
});

test("cor de partido desconhecido é cinza", () => {
  assert.equal(corPartido("PT"), "var(--p-pt)");
  assert.equal(corPartido("União"), "var(--p-uniao)");
  assert.equal(corPartido("XYZ"), "var(--c-outros)");
});
