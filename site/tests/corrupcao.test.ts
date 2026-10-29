// Seção Corrupção: confere os dados escritos à mão e as contas do placar.
import { test } from "node:test";
import assert from "node:assert/strict";
import { CASOS } from "../src/corrupcao/dados.ts";
import { campoDaNota, campoPartido, infoPartido, PARTIDOS } from "../src/corrupcao/partidos.ts";
import { ORDEM, PADRAO, placar, porCampo, resumoGeral, STATUS } from "../src/corrupcao/placar.ts";

const https = (u: string) => /^https:\/\/[^\s"<>]+$/.test(u);

test("todo caso, pessoa, evento e empresa tem fonte https", () => {
  const ids = new Set<string>();
  for (const c of CASOS) {
    assert.ok(!ids.has(c.id), `id repetido: ${c.id}`);
    ids.add(c.id);
    assert.ok(c.fontes.length && c.fontes.every((f) => https(f.url)), `${c.id}: fontes`);
    assert.ok(https(c.valor.fonte.url), `${c.id}: fonte do valor`);
    for (const e of c.timeline) assert.ok(e.fonte && https(e.fonte.url), `${c.id}: evento ${e.data} sem fonte`);
    for (const p of c.pessoas) {
      assert.ok(p.fontes.length > 0 && p.fontes.every((f) => https(f.url)), `${c.id}: ${p.nome} sem fonte`);
      assert.ok(ORDEM.includes(p.status), `${p.nome}: status ${p.status}`);
      assert.ok(p.onde.trim(), `${p.nome}: falta onde está`);
      if (p.partido) assert.ok(PARTIDOS[p.partido], `${p.nome}: partido ${p.partido} sem classificação`);
      if (p.repete) assert.ok(CASOS.some((x) => x.id === p.repete), `${p.nome}: repete aponta para caso que não existe`);
    }
    for (const e of c.empresas) assert.ok(e.fontes.every((f) => https(f.url)), `${c.id}: ${e.nome}`);
    for (const a of c.acordos) assert.ok(https(a.fonte.url), `${c.id}: acordo ${a.quem}`);
    for (const v of [c.visoes.esquerda, c.visoes.direita, c.visoes.justica]) assert.ok(v.texto.length && v.fontes.every((f) => https(f.url)), `${c.id}: visões`);
  }
});

test("os sete casos pedidos estão na seção", () => {
  assert.deepEqual(CASOS.map((c) => c.id), ["mensalao", "sanguessugas", "petrolao", "lava-jato", "banco-master", "careca-do-inss", "cassados"]);
});

test("lista da CPI dos Sanguessugas soma 72 com as pessoas com nome", () => {
  const c = CASOS.find((x) => x.id === "sanguessugas")!;
  const grupos = c.grupos!.reduce((a, g) => a + g.n, 0);
  const comNome = c.pessoas.filter((p) => p.partido).length;
  assert.equal(grupos + comNome, 72);
});

test("cortes de esquerda e direita do artigo", () => {
  assert.equal(campoDaNota(1.28), "Extrema-esquerda");
  assert.equal(campoDaNota(2.97), "Esquerda");
  assert.equal(campoDaNota(3.92), "Centro-esquerda");
  assert.equal(campoDaNota(4.92), "Centro");
  assert.equal(campoDaNota(6.1), "Centro-direita");
  assert.equal(campoDaNota(7.01), "Direita");
  assert.equal(campoDaNota(8.57), "Extrema-direita");
  assert.equal(campoPartido("PT"), "Esquerda");
  assert.equal(campoPartido("PMDB"), "Direita");
  assert.equal(infoPartido("PR").hoje, "PL");
  assert.equal(infoPartido("PMDB").hoje, "MDB");
});

test("placar: soma por partido de hoje, sem contar repetidos nem quem não tem partido", () => {
  const linhas = placar(CASOS, PADRAO);
  const total = linhas.reduce((a, l) => a + l.total, 0);
  let esperado = 0;
  for (const c of CASOS) {
    esperado += c.pessoas.filter((p) => p.partido && !p.repete && PADRAO.includes(p.status)).length;
    esperado += (c.grupos || []).filter((g) => PADRAO.includes(g.status)).reduce((a, g) => a + g.n, 0);
  }
  assert.equal(total, esperado);
  // PMDB e MDB juntos; PR e PL juntos
  assert.ok(!linhas.some((l) => l.partido === "PMDB" || l.partido === "PR"));
  // Ordem: do maior para o menor
  for (let i = 1; i < linhas.length; i++) assert.ok(linhas[i - 1].total >= linhas[i].total);
  // Só condenados
  const so = placar(CASOS, ["condenado"]);
  assert.ok(so.every((l) => l.total === l.por.condenado));
  assert.deepEqual(placar(CASOS, []), []);
  assert.equal(porCampo(linhas).reduce((a, c) => a + c.total, 0), total);
});

test("resumo geral e textos dos status", () => {
  const r = resumoGeral(CASOS);
  assert.equal(r.casos, 7);
  assert.ok(r.pessoas > 100 && r.condenados > 20);
  for (const s of ORDEM) assert.ok(STATUS[s].nome && STATUS[s].um && STATUS[s].explica);
});
