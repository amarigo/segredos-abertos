// Cartão para compartilhar: os números são os do arquivo de dados, com fonte e data, e o endereço bate com a página.
import { test } from "node:test";
import assert from "node:assert/strict";
import { dadosCartao, paginaPolitico, imagemPolitico, slug } from "../src/cartao.ts";

const meta = { atualizado_em: "2026-11-10T06:30:00", anos: [2025, 2026], medias: { "2026": { camara: 200000, senado: 300000 } } };
const base = {
  id: "dep-1", casa: "camara" as const, cargo: "Deputado(a) Federal", nome: "Fulana de Tal", partido: "XX", uf: "MG",
  por_ano: { "2026": { total: 300000, custo_total: 1500000 }, "2025": { total: 0, custo_total: 0 } },
  posicao: 0.5, rotulo: "Centro", alinhamento_governo: 0.42, fidelidade_partido: 0.9, n_votos: 1036,
};
const opc = { site: "Segredos Abertos Brasil", endereco: "https://amarigo.github.io/segredos-abertos/" };

test("cartão usa os números do arquivo e compara com a média da Casa", () => {
  const d = dadosCartao(base, meta, opc)!;
  assert.equal(d.ano, "2026");
  assert.equal(d.cota, 300000);
  assert.match(d.comparacao, /^1,5× a média dos deputados \(R\$ 200\.000\)$/);
  assert.deepEqual(d.linhas.map((l) => l[0]), ["Custo conhecido do mandato em 2026", "Posição pelos votos", "Vota com o governo", "Vota com o próprio partido"]);
  assert.equal(d.linhas[2][1], "42%");
  assert.equal(d.atualizado, "10/11/2026");
  assert.match(d.fonte, /Câmara dos Deputados/);
  assert.equal(d.endereco, "amarigo.github.io/segredos-abertos");
  assert.match(d.nota, /2026 até 10\/11\/2026/);
});

test("abaixo da média, sem posição e senador", () => {
  const d = dadosCartao({ ...base, casa: "senado", posicao: null, alinhamento_governo: null, por_ano: { "2026": { total: 90000, custo_total: 90000 } } }, meta, opc)!;
  assert.equal(d.comparacao, "70% abaixo da média dos senadores (R$ 300.000)");
  assert.deepEqual(d.linhas.map((l) => l[0]), ["Vota com o próprio partido"]);
  assert.match(d.fonte, /Senado Federal/);
});

test("sem gasto no ano não há cartão", () => {
  assert.equal(dadosCartao(base, meta, { ...opc, ano: "2025" }), null);
  assert.equal(dadosCartao(base, meta, { ...opc, ano: "2024" }), null);
});

test("endereços da página e da imagem", () => {
  assert.equal(slug("João D'Ávila Ç"), "joao-d-avila-c");
  assert.equal(paginaPolitico({ nome: "Flávio Bolsonaro", id: "sen-5894" }), "politico/flavio-bolsonaro-sen-5894.html");
  assert.equal(imagemPolitico("sen-5894"), "cartao/sen-5894.jpg");
});
