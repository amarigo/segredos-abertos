// Testes das contas do painel de status: node --test status/
import test from "node:test";
import assert from "node:assert/strict";
import {
  situacaoExecucao, resumirExecucao, calendario, partesDaExecucao, motivoDaFalha, saude, anotacoesUteis,
  proximaAgendada, comoComecou, ultimaVezOk, duracaoTexto,
} from "./painel.js";

const run = (o) => ({ id: 1, html_url: "https://github.com/x/actions/runs/1", run_number: 7, event: "schedule", status: "completed",
  conclusion: "success", run_started_at: "2026-11-02T09:44:07Z", updated_at: "2026-11-02T10:34:22Z", ...o });

const passo = (number, name, conclusion = "success", ini = "2026-11-02T10:00:00Z", fim = "2026-11-02T10:10:00Z") =>
  ({ number, name, status: "completed", conclusion, started_at: ini, completed_at: fim });

const jobs = (coletarPassos, extra = []) => [
  { id: 11, name: "testes-coletor", status: "completed", conclusion: "success", html_url: "https://github.com/j/11", started_at: "2026-11-02T09:44:00Z", completed_at: "2026-11-02T09:46:00Z", steps: [] },
  { id: 12, name: "coletar", status: "completed", conclusion: coletarPassos.some((s) => s.conclusion === "failure") ? "failure" : "success", html_url: "https://github.com/j/12", steps: coletarPassos },
  ...extra,
];

test("situação de cada execução", () => {
  assert.equal(situacaoExecucao(run()), "publicada");
  assert.equal(situacaoExecucao(run({ conclusion: "failure" })), "falhou");
  assert.equal(situacaoExecucao(run({ conclusion: "cancelled" })), "cancelada");
  assert.equal(situacaoExecucao(run({ status: "in_progress", conclusion: null })), "rodando");
  const r = resumirExecucao(run());
  assert.equal(r.dia, "2026-11-02");
  assert.equal(Math.round(r.duracao), 50);
});

test("como a execução começou", () => {
  assert.equal(comoComecou(run()), "Agendada (todo dia às 6h)");
  assert.equal(comoComecou(run({ event: "workflow_dispatch", triggering_actor: { login: "github-actions[bot]" } })), "Tentar de novo (automático)");
  assert.equal(comoComecou(run({ event: "workflow_dispatch", triggering_actor: { login: "amarigo" } })), "Manual");
  assert.equal(comoComecou(run({ event: "push" })), "Mudança no código");
});

test("o dia vira no horário de Brasília", () => {
  // 01h UTC do dia 2 ainda é dia 1 em Brasília
  assert.equal(resumirExecucao(run({ run_started_at: "2026-11-02T01:40:00Z" })).dia, "2026-11-01");
});

test("calendário: publicado vence falha no mesmo dia; dia sem coleta fica cinza", () => {
  const execs = [
    resumirExecucao(run({ id: 1, conclusion: "failure", run_started_at: "2026-11-02T09:00:00Z" })),
    resumirExecucao(run({ id: 2, run_started_at: "2026-11-02T15:00:00Z" })),
    resumirExecucao(run({ id: 3, conclusion: "failure", run_started_at: "2026-11-01T12:00:00Z" })),
    resumirExecucao(run({ id: 4, conclusion: "cancelled", run_started_at: "2026-10-31T12:00:00Z" })),
  ];
  const c = calendario(execs, 4, new Date("2026-11-02T18:00:00Z"), true);
  assert.deepEqual(c.map((x) => [x.dia, x.situacao]), [
    ["2026-10-30", "sem"], ["2026-10-31", "sem"], ["2026-11-01", "falhou"], ["2026-11-02", "publicada"]]);
  // Sem o histórico completo, dias antes da execução mais antiga lida não viram "sem coleta"
  assert.equal(calendario(execs, 4, new Date("2026-11-02T18:00:00Z"))[0].situacao, "fora");
});

test("ruído do GitHub não vira motivo", () => {
  const a = anotacoesUteis([
    { annotation_level: "warning", message: "Node.js 20 is deprecated. The following actions..." },
    { annotation_level: "failure", message: "Process completed with exit code 1." },
    { annotation_level: "notice", message: "The ubuntu-latest label will migrate" },
    { annotation_level: "failure", title: "Conferência dos dados", message: "votacoes.json: 3 votos repetidos" },
  ]);
  assert.deepEqual(a.map((x) => x.message), ["votacoes.json: 3 votos repetidos"]);
});

test("conferência barrou: a parte falha, as seguintes não rodam e o motivo vem da anotação", () => {
  const js = jobs([
    passo(6, "Coletar dados oficiais"),
    passo(8, "Conferir os dados (se algo não bater, não publica e o site continua com a versão anterior)", "failure"),
    passo(9, "Verificação independente (segunda fonte oficial)", "skipped"),
    passo(15, "Run npm ci && npm run build && npm run paginas", "skipped"),
    passo(12, "Minas Nossa: montar os dados de MG", "skipped"),
  ], [{ id: 13, name: "publicar", status: "completed", conclusion: "skipped", html_url: "https://github.com/j/13", steps: [] }]);
  const anots = { 12: [
    { annotation_level: "failure", title: "Conferência dos dados", message: "politicos.json: 513 deputados esperados, 480 encontrados" },
    { annotation_level: "failure", title: "", message: "Process completed with exit code 1." },
    { annotation_level: "warning", title: "Aviso da coleta", message: "Emendas: o Portal da Transparência não respondeu" },
  ] };
  const ps = partesDaExecucao(js, anots);
  const p = Object.fromEntries(ps.map((x) => [x.id, x]));
  assert.equal(p.testes.estado, "ok");
  assert.equal(p.coleta.estado, "aviso");
  assert.equal(p.coleta.motivos[0].texto, "Emendas: o Portal da Transparência não respondeu");
  assert.equal(p.conferencia.estado, "erro");
  assert.equal(p.conferencia.url, "https://github.com/j/12#step:8:1");
  assert.equal(p.verificacao.estado, "nao_rodou");
  assert.equal(p.verificacao.duracao, null);
  assert.deepEqual(p.site.motivos, []); // anotação de outra parte não aparece aqui
  assert.equal(p.mg.estado, "nao_rodou");
  assert.equal(p.publicar.estado, "nao_rodou");
  assert.equal(p.seguranca.estado, "nao_rodou"); // job ausente
  assert.deepEqual(motivoDaFalha(ps), { parte: "Conferência dos dados", texto: "politicos.json: 513 deputados esperados, 480 encontrados", url: "https://github.com/j/12#step:8:1" });
});

test("falha sem anotação: o motivo aponta a etapa", () => {
  const ps = partesDaExecucao(jobs([passo(6, "Coletar dados oficiais", "failure")]), {});
  assert.match(motivoDaFalha(ps).texto, /“Coletar dados oficiais” falhou/);
});

test("Minas Nossa com continue-on-error: etapa ok na API, mas o aviso marca a parte", () => {
  const ps = partesDaExecucao(jobs([passo(12, "Minas Nossa: montar os dados de MG"), passo(16, "Minas Nossa: montar o site em /mg/")]),
    { 12: [{ annotation_level: "warning", title: "Minas Nossa", message: "A coleta ou a conferência de MG falhou; o Minas Nossa ficou com a última versão publicada" }] });
  const mg = ps.find((x) => x.id === "mg");
  assert.equal(mg.estado, "aviso");
  assert.equal(Math.round(mg.duracao), 20);
});

test("saúde geral", () => {
  const agora = new Date("2026-11-02T18:00:00Z").getTime();
  const ok = resumirExecucao(run());
  assert.equal(saude({ execs: [ok], agora }).nivel, "ok");
  const falhou = resumirExecucao(run({ id: 2, conclusion: "failure", run_started_at: "2026-11-02T15:00:00Z", updated_at: "2026-11-02T15:40:00Z" }));
  const s = saude({ execs: [falhou, ok], ultimaDetalhe: { motivo: { parte: "Conferência dos dados", texto: "x" }, partes: [] }, agora });
  assert.equal(s.nivel, "atencao");
  assert.equal(s.motivo.texto, "x");
  assert.equal(saude({ execs: [ok], avisosPublicados: ["Emendas: cópia de 01/11"], agora }).titulo, "Funcionando, com avisos");
  const velho = resumirExecucao(run({ run_started_at: "2026-10-30T09:00:00Z", updated_at: "2026-10-30T10:00:00Z" }));
  assert.equal(saude({ execs: [velho], agora }).nivel, "critico");
  assert.equal(saude({ execs: [], agora }).nivel, "critico");
  const rodando = resumirExecucao(run({ id: 3, status: "in_progress", conclusion: null }));
  assert.equal(saude({ execs: [rodando, ok], agora }).rodando.id, 3);
});

test("última vez que cada parte funcionou", () => {
  const d = [
    { exec: { fim: "2026-11-02T10:00:00Z" }, partes: [{ id: "conferencia", estado: "erro" }] },
    { exec: { fim: "2026-11-01T10:00:00Z" }, partes: [{ id: "conferencia", estado: "aviso" }] },
  ];
  assert.equal(ultimaVezOk(d, "conferencia"), "2026-11-01T10:00:00Z");
  assert.equal(ultimaVezOk(d, "mg"), null);
});

test("próxima coleta agendada e durações", () => {
  assert.equal(proximaAgendada(new Date("2026-11-02T08:00:00Z")), "2026-11-02T09:00:00.000Z");
  assert.equal(proximaAgendada(new Date("2026-11-02T09:30:00Z")), "2026-11-03T09:00:00.000Z");
  assert.equal(duracaoTexto(0.5), "30 s");
  assert.equal(duracaoTexto(46.2), "46 min");
  assert.equal(duracaoTexto(75), "1 h 15 min");
});
