// Testes da Minha rede (src/rede): juntar sem duplicar, proveniência, menções, busca, sugestões e alertas.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  acharMencoes, apagarFonte, baseVazia, buscar, frases, idObjeto, juntar, lerExportada, novidades, sugestoes, vizinhanca,
  type Retrato,
} from "../src/rede/modelo.ts";
import { redeOficial, urlVotacao } from "../src/rede/oficial.ts";
import type { Politico, VotacaoResumo } from "../src/data.ts";

const EM = "2026-11-08T00:00:00Z";

function politico(): Politico {
  return {
    id: "dep-1", casa: "camara", cargo: "Deputado(a) Federal", nome: "Fulana de Tal", partido: "PX", uf: "MG", foto: "",
    fonte: "https://www.camara.leg.br/deputados/1", total: 100, por_ano: {}, posicao: 0.5, rotulo: "Centro",
    alinhamento_governo: 0.5, campo: null, fidelidade_partido: 0.9, n_votos: 2,
    anos: { "2026": { total: 100, fornecedores: [
      { doc: "11222333000181", tipo: "cnpj", nome: "Gráfica Boa", valor: 80, n: 2, ficha: true, socios: ["JOAO DA SILVA"] },
      { doc: "***123456**", tipo: "cpf", nome: "Pessoa Física", valor: 20, n: 1, ficha: false, socios: [] },
    ] } } as unknown as Politico["anos"],
    votos: [{ votacao: "cd-99-1", voto: "Sim", partido: "Sim" }, { votacao: "cd-98-1", voto: "Não", partido: "Sim" }],
  };
}
const votacoes: VotacaoResumo[] = [
  { id: "cd-99-1", casa: "camara", data: "2026-11-01", descricao: "Aprovado o PL 1/2026", aprovada: true, sim: 1, nao: 0,
    proposicao: { sigla: "PL", numero: "1", ano: "2026", ementa: "Dispõe sobre hospitais.", titulo: "PL 1/2026", url: "https://www.camara.leg.br/x" } },
  { id: "cd-98-1", casa: "camara", data: "2026-10-01", descricao: "Rejeitado o requerimento", aprovada: false, sim: 0, nao: 1, proposicao: null },
];

test("rede oficial: toda ligação tem fonte oficial com link, e pessoa física fica de fora", () => {
  const r = redeOficial(politico(), votacoes, [{ ano: 2026, fonte: "https://portaldatransparencia.gov.br/emendas", autores: [
    { nome: "Fulana de Tal", politico: "dep-1", pago: 500, pix_emendas: [["1", "Itajubá - MG", 500]] }] }], EM);
  const b = juntar(baseVazia(), r);
  assert.ok(Object.keys(b.ligacoes).length >= 8);
  for (const l of Object.values(b.ligacoes)) {
    const f = b.fontes[l.fonte];
    assert.ok(f, `ligação sem fonte: ${l.id}`);
    assert.match(f.url || "", /^https:\/\//);
  }
  assert.ok(b.objetos[idObjeto("empresa", "11222333000181")]);
  assert.ok(!Object.values(b.objetos).some((o) => o.nome === "Pessoa Física"));
  assert.ok(b.objetos[idObjeto("pessoa", "JOAO DA SILVA")]);
  assert.ok(b.objetos[idObjeto("lugar", "Itajubá - MG")]);
  assert.equal(r.retrato.cota, 100);
  assert.equal(r.retrato.emendas, 500);
  assert.deepEqual(r.retrato.empresas, { "11222333000181": "Gráfica Boa" });
});

test("juntar duas vezes não duplica, e as anotações da pessoa ficam", () => {
  const r = redeOficial(politico(), votacoes, [], EM);
  let b = juntar(baseVazia(), r);
  const id = idObjeto("politico", "dep-1");
  b = { ...b, objetos: { ...b.objetos, [id]: { ...b.objetos[id], notas: "minha nota" } } };
  const b2 = juntar(b, redeOficial(politico(), votacoes, [], EM));
  assert.equal(Object.keys(b2.ligacoes).length, Object.keys(b.ligacoes).length);
  assert.equal(b2.objetos[id].notas, "minha nota");
});

test("ligação sem fonte ou com objeto que não existe é recusada", () => {
  const b = juntar(baseVazia(), {
    objetos: [{ id: "pessoa:a", tipo: "pessoa", nome: "A" }, { id: "pessoa:b", tipo: "pessoa", nome: "B" }],
    ligacoes: [{ de: "pessoa:a", para: "pessoa:b", tipo: "conhece", fonte: "nao-existe" }, { de: "pessoa:a", para: "pessoa:c", tipo: "x", fonte: "f" }],
  });
  assert.equal(Object.keys(b.ligacoes).length, 0);
});

test("apagar uma fonte apaga as ligações que dependem dela", () => {
  let b = juntar(baseVazia(), {
    objetos: [{ id: "pessoa:a", tipo: "pessoa", nome: "A" }, { id: "pessoa:b", tipo: "pessoa", nome: "B" }],
    fontes: [{ id: "f", tipo: "texto", titulo: "Notícia", em: EM }],
    ligacoes: [{ de: "pessoa:a", para: "pessoa:b", tipo: "conhece", fonte: "f" }],
  });
  assert.equal(Object.keys(b.ligacoes).length, 1);
  b = apagarFonte(b, "f");
  assert.equal(Object.keys(b.ligacoes).length, 0);
});

test("frases e menções: acha nome sem acento, CNPJ com pontuação, e ignora nome curto", () => {
  assert.deepEqual(frases("Primeira frase. Segunda frase! Terceira"), ["Primeira frase.", "Segunda frase!", "Terceira"]);
  const texto = "A deputada FULANA DE TAL contratou a grafica. O CNPJ 11.222.333/0001-81 aparece na nota. O PT votou contra.";
  const m = acharMencoes(texto, [
    { id: "politico:dep 1", tipo: "politico", nome: "Fulana de Tal" },
    { id: "empresa:11222333000181", tipo: "empresa", nome: "Gráfica Boa" },
    { id: "partido:pt", tipo: "partido", nome: "PT" },
  ]);
  assert.deepEqual(m.map((x) => x.conhecido.id).sort(), ["empresa:11222333000181", "politico:dep 1"]);
  assert.equal(m.find((x) => x.conhecido.tipo === "empresa")!.trechos[0], "O CNPJ 11.222.333/0001-81 aparece na nota.");
});

test("busca devolve o trecho certo com a fonte", () => {
  const b = juntar(juntar(baseVazia(), redeOficial(politico(), votacoes, [], EM)), {
    fontes: [{ id: "t1", tipo: "texto", titulo: "Jornal", em: EM, texto: "O tempo estava bom. A obra do hospital de Itajubá atrasou dois anos." }],
  });
  const r = buscar(b, "atraso na obra do hospital");
  assert.equal(r[0].fonte, "t1");
  assert.match(r[0].texto, /hospital de Itajubá/);
  const s = buscar(b, "sócio da Gráfica Boa");
  assert.ok(s.some((t) => /oficial:cnpj/.test(t.fonte)));
  assert.deepEqual(buscar(b, "de da o"), []);
});

test("sugestões: dois políticos que pagaram a mesma empresa", () => {
  const p2 = { ...politico(), id: "dep-2", nome: "Beltrano", votos: [] };
  const b = juntar(juntar(baseVazia(), redeOficial(politico(), votacoes, [], EM)), redeOficial(p2, votacoes, [], EM));
  const s = sugestoes(b);
  const par = s.find((x) => [x.a, x.b].sort().join() === [idObjeto("politico", "dep-1"), idObjeto("politico", "dep-2")].sort().join());
  assert.ok(par);
  assert.ok(par!.comuns.includes(idObjeto("empresa", "11222333000181")));
  // partido não conta como "em comum"
  assert.ok(!par!.comuns.includes(idObjeto("partido", "PX")));
  const v = vizinhanca(b, idObjeto("politico", "dep-1"), 2);
  assert.ok(v.objetos.some((o) => o.id === idObjeto("politico", "dep-2")));
});

test("novidades entre dois retratos", () => {
  const antes: Retrato = { em: EM, nome: "F", partido: "PX", cota: 100, ano: "2026", votos: ["a"], empresas: { "1": "E1" }, emendas: 0, situacao: "" };
  assert.deepEqual(novidades(antes, antes), []);
  const agora = { ...antes, partido: "PY", cota: 150, votos: ["a", "b", "c"], empresas: { "1": "E1", "2": "E2" }, emendas: 10 };
  const n = novidades(antes, agora);
  assert.deepEqual(n.map((x) => x.tipo), ["partido", "cota", "voto", "empresa", "emenda"]);
  assert.equal(n.find((x) => x.tipo === "cota")!.valor, 50);
  assert.deepEqual(n.find((x) => x.tipo === "voto")!.ids, ["b", "c"]);
});

test("arquivo importado com defeito é recusado", () => {
  assert.throws(() => lerExportada("{}"));
  assert.throws(() => lerExportada(JSON.stringify({ versao: 1, objetos: { x: { id: 1 } }, ligacoes: {}, fontes: {} })));
  const b = lerExportada(JSON.stringify(baseVazia()));
  assert.deepEqual(b.comparacoes, []);
  assert.equal(urlVotacao("sf-123"), "https://legis.senado.leg.br/dadosabertos/votacao?codigoSessaoVotacao=123");
});
