// Confiança em cada número: média da Casa, o que falta e o link para avisar um erro (src/confianca.ts)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  comparacao, comparacaoPontos, linkAvisarErro, oQueFalta, periodoInteiro, periodoNome, referenciaDinheiro, referenciaTaxa,
} from "../src/confianca.ts";
import type { AnoDetalhe, Politico } from "../src/data.ts";

test("nome do período: ano fechado e ano em andamento", () => {
  assert.equal(periodoNome("2025", 12), "de 2025");
  assert.equal(periodoNome("2026", 10), "de janeiro a outubro de 2026");
  assert.equal(periodoNome("2026", 1), "de janeiro de 2026");
});

test("período inteiro aceita um mês sem nota (mesma regra da coleta)", () => {
  assert.equal(periodoInteiro(12, 12, 1), true);
  assert.equal(periodoInteiro(11, 12, 1), true);
  assert.equal(periodoInteiro(10, 12, 1), false);
  assert.equal(periodoInteiro(undefined, 12, 1), false);
  assert.equal(periodoInteiro(1, 1, 1), true);
});

test("média de dinheiro: quem ficou o ano todo compara com a média; quem ficou menos, com a média proporcional", () => {
  const m = { media: 480_000, n: 486 };
  const cheio = referenciaDinheiro(m, "camara", "2025", 12, 1, 12);
  assert.equal(cheio.valor, 480_000);
  assert.equal(cheio.proporcional, false);
  assert.equal(cheio.rotulo, "Média da Câmara");
  assert.equal(cheio.criterio, "Média de 486 deputados com nota da cota em 11 ou mais dos 12 meses de 2025.");

  const parte = referenciaDinheiro(m, "camara", "2025", 12, 1, 3);
  assert.equal(parte.valor, 120_000);
  assert.equal(parte.proporcional, true);
  assert.equal(parte.rotulo, "Média da Câmara para 3 meses");
  assert.match(parte.criterio, /^Teve nota da cota em 3 dos 12 meses/);

  // Sem os meses do político (dado antigo), usa a média inteira
  assert.equal(referenciaDinheiro(m, "senado", "2026", 10, 1).rotulo, "Média do Senado");
  assert.match(referenciaDinheiro({ media: 1, n: 1 }, "senado", "2026", 10, 1).criterio, /1 senador com nota da cota em 9 ou mais dos 10 meses de janeiro a outubro de 2026/);
});

test("média de taxa diz quantos entraram e o critério", () => {
  const r = referenciaTaxa({ media: 0.9, n: 640 }, "camara", "com 15 ou mais votos Sim ou Não");
  assert.equal(r.criterio, "Média de 640 deputados com 15 ou mais votos Sim ou Não.");
});

test("comparação com a média", () => {
  assert.equal(comparacao(150, 100), "1,5× a média");
  assert.equal(comparacao(80, 100), "20% abaixo da média");
  assert.equal(comparacao(102, 100), "Na média");
  assert.equal(comparacao(5, 0), "");
  assert.equal(comparacaoPontos(0.93, 0.9), "3 pontos acima da média");
  assert.equal(comparacaoPontos(0.89, 0.9), "1 ponto abaixo da média");
  assert.equal(comparacaoPontos(0.901, 0.9), "Na média");
});

const ano = (extra: Partial<AnoDetalhe>): AnoDetalhe => ({
  total: 1, grupos: { pessoal: 1, escritorio: 0, servicos: 0 }, salario: null, verba_gabinete: null, outros_gastos: null,
  cota_oficial: null, n_pessoal: null, custo_total: 1, categorias: [], meses: [], fornecedores: [], maiores_notas: [], recursos: null, ...extra,
});
const pol = (casa: "camara" | "senado", d: AnoDetalhe, n_votos = 10): Politico => ({
  id: casa === "camara" ? "dep-1" : "sen-1", casa, cargo: "", nome: "Fulano", partido: "X", uf: "MG", foto: "", fonte: "https://www.camara.leg.br/deputados/1",
  total: 1, por_ano: { "2026": d }, posicao: null, rotulo: "", alinhamento_governo: null, campo: null, fidelidade_partido: null, n_votos,
  anos: { "2026": d }, votos: [],
});

test("o que falta: Câmara com passagens completadas e despesas sem nota", () => {
  const d = ano({ n_notas: 358, passagens_da_lista: { n: 172, valor: 124733.19 }, sem_nota_meses: [{ mes: 3, valor: 500, url: "" }],
    recursos: { salario_meses: [{ mes: 1, valor: 10 }], verba_gasto: 100 } });
  const itens = oQueFalta(pol("camara", d), "2026", d);
  const por = (t: string) => itens.find((x) => x.titulo === t);
  assert.equal(por("Notas fiscais da cota")?.estado, "tem");
  assert.equal(por("Passagens aéreas compradas pela Câmara")?.estado, "completado");
  assert.match(por("Passagens aéreas compradas pela Câmara")!.texto, /172 bilhetes/);
  assert.equal(por("Despesas sem nota publicada")?.estado, "fonte_nao_publica");
  assert.equal(por("Salário")?.estado, "tem");
  assert.equal(por("Votos nas comissões")?.estado, "ainda_nao");
  assert.equal(por("Presença nas comissões"), undefined); // só o Senado não publica
  assert.equal(por("Imagem das notas fiscais"), undefined);
  for (const x of itens) assert.ok(!x.link || /^https:\/\//.test(x.link), x.titulo);
});

test("o que falta: Senado sem imagem de nota, sem presença em comissões, salário completado", () => {
  const d = ano({ n_notas: 92, maiores_notas: [{ data: "", categoria: "", fornecedor: "", doc: "", valor: 1, url: "https://www6g.senado.leg.br/transparencia/sen/1/ceaps/" }],
    recursos: { salario_estimado: true, beneficios: [{ beneficio: "Auxílio-Moradia", utilizacao: "Não utilizou" }] } });
  const itens = oQueFalta(pol("senado", d), "2026", d);
  const por = (t: string) => itens.find((x) => x.titulo === t);
  assert.equal(por("Imagem das notas fiscais")?.estado, "fonte_nao_publica");
  assert.equal(por("Imagem das notas fiscais")?.link, "https://www6g.senado.leg.br/transparencia/sen/1/ceaps/");
  assert.equal(por("Presença nas comissões")?.estado, "fonte_nao_publica");
  assert.equal(por("Salário")?.estado, "completado");
  assert.match(por("Valor dos benefícios")!.texto, /auxílio-moradia/);
  assert.equal(por("Passagens aéreas compradas pela Câmara"), undefined);
});

test("link de avisar erro abre o formulário certo, já preenchido", () => {
  const u = new URL(linkAvisarErro("https://amarigo.github.io/segredos-abertos/#/p/dep-1", "Fulano (Deputado, X-MG), 2026"));
  assert.equal(u.origin + u.pathname, "https://github.com/amarigo/segredos-abertos/issues/new");
  assert.equal(u.searchParams.get("template"), "erro-nos-dados.yml");
  assert.equal(u.searchParams.get("title"), "Erro nos dados: Fulano (Deputado, X-MG), 2026");
  assert.equal(u.searchParams.get("pagina"), "https://amarigo.github.io/segredos-abertos/#/p/dep-1");
  const r = new URL(linkAvisarErro("x", "y", "resposta"));
  assert.equal(r.searchParams.get("template"), "direito-de-resposta.yml");
  assert.equal(linkAvisarErro("x", "a".repeat(400)).length < 600, true);
});
