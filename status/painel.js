// Painel de status (/status/): mostra se cada coleta rodou, quando os dados foram atualizados, se as atualizações
// estão funcionando e, quando não estão, por quê.
//
// De onde vêm os dados (tudo público, sem senha):
// - API oficial do GitHub Actions (api.github.com): execuções do "Dados e site" e do "Tentar de novo", etapas de
//   cada execução e as anotações com o motivo de cada problema (escritas por etl/anotar.py e pelos validadores).
// - Arquivos publicados no próprio site: data/meta.json (data da coleta e avisos), data/verificacao.json
//   (verificação com a segunda fonte oficial) e mg/data/meta.json (Minas Nossa).
// A página é estática e lê tudo na hora, no navegador: assim ela mostra a situação real mesmo quando uma coleta
// falha e o site não é publicado de novo. Sem a API, nenhuma outra fonte diz por que uma execução parou.
//
// As funções de cálculo (sem tela) são exportadas e testadas em status/painel.test.mjs.

export const REPO = "amarigo/segredos-abertos";
export const API = `https://api.github.com/repos/${REPO}`;
export const ACTIONS = `https://github.com/${REPO}/actions`;
export const FLUXO = "dados-e-site.yml";
export const FLUXO_REPETIR = "tentar-de-novo.yml";
export const HORA_AGENDADA_UTC = 9; // cron "0 9 * * *": 6h de Brasília
export const DETALHAR = 6; // quantas execuções recentes são abertas etapa por etapa (cada uma custa 2 consultas)
const FUSO = "America/Sao_Paulo";

// Partes da coleta, na ordem em que rodam. "passos" casa com o nome da etapa na API; "titulos" com o título das
// anotações (::error title=...) que explicam o problema daquela parte.
export const PARTES = [
  { id: "testes", nome: "Testes do código", jobs: /^testes-/ },
  { id: "coleta", nome: "Coleta dos dados oficiais", job: "coletar", passos: /^Coletar dados oficiais/, titulos: ["Coleta dos dados", "Aviso da coleta"] },
  { id: "conferencia", nome: "Conferência dos dados", job: "coletar", passos: /^Conferir os dados/, titulos: ["Conferência dos dados"] },
  { id: "verificacao", nome: "Verificação com a 2ª fonte oficial", job: "coletar", passos: /^Verificação independente/, titulos: ["Verificação com a segunda fonte"] },
  { id: "site", nome: "Site Segredos Abertos", job: "coletar", passos: /npm run build && npm run paginas$/ },
  { id: "mg", nome: "Minas Nossa", job: "coletar", passos: /^Minas Nossa: (montar os dados|conferir os dados|montar o site)/, titulos: ["Minas Nossa", "Minas Nossa: conferência", "Minas Nossa: aviso da coleta"] },
  { id: "eleicao", nome: "Eleição 2026", job: "coletar", passos: /^Eleição 2026/, titulos: ["Eleição 2026"] },
  { id: "terras", nome: "Terras Raras", job: "coletar", passos: /^Terras Raras/, titulos: ["Terras Raras"] },
  { id: "publicar", nome: "Publicação no ar (GitHub Pages)", jobs: /^publicar$/ },
  { id: "seguranca", nome: "Segurança das dependências", jobs: /^seguranca$/ },
];

// Avisos automáticos do GitHub que não dizem nada sobre os dados
const RUIDO = /Node\.js \d+ (is|are) deprecated|ubuntu-latest label|Process completed with exit code|runner-images/i;

// ------------------------------------------------------------------ datas

export function diaBrasilia(iso) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FUSO, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
}

export function dataHora(iso) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

export function haQuanto(iso, agora = Date.now()) {
  if (!iso) return "—";
  const min = Math.round((agora - new Date(iso).getTime()) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `há ${h} ${h === 1 ? "hora" : "horas"}`;
  return `há ${Math.round(h / 24)} dias`;
}

export function minutos(inicio, fim) {
  if (!inicio || !fim) return null;
  return Math.max(0, (new Date(fim) - new Date(inicio)) / 60000);
}

export function duracaoTexto(min) {
  if (min == null) return "—";
  if (min < 1) return `${Math.round(min * 60)} s`;
  if (min < 60) return `${Math.round(min)} min`;
  return `${Math.floor(min / 60)} h ${String(Math.round(min % 60)).padStart(2, "0")} min`;
}

export function proximaAgendada(agora = new Date()) {
  const p = new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth(), agora.getUTCDate(), HORA_AGENDADA_UTC));
  if (p <= agora) p.setUTCDate(p.getUTCDate() + 1);
  return p.toISOString();
}

// ------------------------------------------------------------------ execuções

export function comoComecou(run) {
  if (run.event === "schedule") return "Agendada (todo dia às 6h)";
  if (run.event === "push") return "Mudança no código";
  if (run.event === "workflow_dispatch") {
    const quem = run.triggering_actor?.login || run.actor?.login || "";
    return quem === "github-actions[bot]" ? "Tentar de novo (automático)" : "Manual";
  }
  return run.event || "—";
}

// Situação de uma execução: rodando, publicada, falhou (não publicou) ou cancelada (uma mais nova tomou o lugar).
export function situacaoExecucao(run) {
  if (run.status !== "completed") return "rodando";
  if (run.conclusion === "success") return "publicada";
  if (run.conclusion === "cancelled" || run.conclusion === "skipped") return "cancelada";
  return "falhou";
}

export function resumirExecucao(run) {
  return {
    id: run.id, url: run.html_url, numero: run.run_number, inicio: run.run_started_at || run.created_at,
    fim: run.status === "completed" ? run.updated_at : null, dia: diaBrasilia(run.run_started_at || run.created_at),
    situacao: situacaoExecucao(run), comoComecou: comoComecou(run),
    duracao: run.status === "completed" ? minutos(run.run_started_at || run.created_at, run.updated_at) : null,
  };
}

// Um quadrado por dia nos últimos `dias` dias: publicado se alguma execução publicou, senão falhou se alguma
// falhou, senão rodando, senão sem coleta (nenhuma ou só canceladas).
export function calendario(execs, dias = 30, agora = new Date(), completo = false) {
  const porDia = new Map();
  // Dias antes da execução mais antiga lida: a API não trouxe esses dias, então não dá para dizer que não houve coleta
  const primeiro = completo || !execs.length ? "" : execs.reduce((m, e) => (e.dia < m ? e.dia : m), execs[0].dia);
  for (const e of execs) (porDia.get(e.dia) || porDia.set(e.dia, []).get(e.dia)).push(e);
  const out = [];
  for (let i = dias - 1; i >= 0; i--) {
    const d = diaBrasilia(new Date(agora.getTime() - i * 86400000).toISOString());
    const es = porDia.get(d) || [];
    const tem = (s) => es.some((e) => e.situacao === s);
    const situacao = tem("publicada") ? "publicada" : tem("falhou") ? "falhou" : tem("rodando") ? "rodando" : d < primeiro ? "fora" : "sem";
    out.push({ dia: d, situacao, execucoes: es });
  }
  return out;
}

// ------------------------------------------------------------------ etapas e motivos

export function anotacoesUteis(anots) {
  return (anots || []).filter((a) => (a.annotation_level === "failure" || a.annotation_level === "warning") && !RUIDO.test(a.message || ""));
}

function estadoDe(conclusoes) {
  if (!conclusoes.length) return "nao_rodou";
  if (conclusoes.includes("failure") || conclusoes.includes("timed_out")) return "erro";
  if (conclusoes.includes(null) || conclusoes.includes(undefined)) return "rodando";
  if (conclusoes.includes("cancelled")) return "cancelada";
  if (conclusoes.every((c) => c === "skipped")) return "nao_rodou";
  return "ok";
}

// Situação de cada parte numa execução, a partir das etapas (jobs) e das anotações do GitHub.
export function partesDaExecucao(jobs, anotsPorJob = {}) {
  const lista = jobs || [];
  return PARTES.map((p) => {
    let itens = [];
    if (p.jobs) {
      itens = lista.filter((j) => p.jobs.test(j.name)).map((j) => ({ job: j, passo: null }));
    } else {
      const j = lista.find((x) => x.name === p.job);
      itens = (j?.steps || []).filter((s) => p.passos.test(s.name)).map((s) => ({ job: j, passo: s }));
    }
    const conclusoes = itens.map(({ job, passo }) => (passo || job).status === "completed" ? (passo || job).conclusion : null);
    let estado = estadoDe(conclusoes);
    const anots = [];
    for (const { job } of itens) {
      for (const a of anotacoesUteis(anotsPorJob[job.id])) {
        // Etapas do job "coletar" só levam as anotações com o seu título; um job inteiro (testes, publicação) leva todas
        if (p.titulos ? p.titulos.includes(a.title) : Boolean(p.jobs)) anots.push(a);
      }
    }
    const unicas = [...new Map(anots.map((a) => [a.annotation_level + a.message, a])).values()];
    if (estado === "ok" && unicas.some((a) => a.annotation_level === "failure")) estado = "erro";
    else if (estado === "ok" && unicas.length) estado = "aviso";
    const falhou = itens.find(({ job, passo }) => (passo || job).conclusion === "failure");
    const motivos = unicas.map((a) => ({ nivel: a.annotation_level === "failure" ? "erro" : "aviso", titulo: a.title, texto: a.message }));
    if (estado === "erro" && !motivos.some((m) => m.nivel === "erro") && falhou) {
      motivos.unshift({ nivel: "erro", titulo: "", texto: `A etapa “${(falhou.passo || falhou.job).name}” falhou. Abra o registro para ver o erro.` });
    }
    const alvo = falhou || itens[0];
    const url = alvo ? alvo.job.html_url + (alvo.passo ? `#step:${alvo.passo.number}:1` : "") : null;
    const dur = itens.reduce((s, { job, passo }) => s + (minutos((passo || job).started_at, (passo || job).completed_at) || 0), 0);
    return { id: p.id, nome: p.nome, estado, motivos, url, duracao: itens.length && estado !== "nao_rodou" ? dur : null };
  });
}

// Por que uma execução não publicou: o primeiro motivo de erro das partes, ou a primeira parte com erro.
export function motivoDaFalha(partes) {
  for (const p of partes) {
    const m = p.motivos.find((x) => x.nivel === "erro");
    if (m) return { parte: p.nome, texto: m.texto, url: p.url };
  }
  const p = partes.find((x) => x.estado === "erro");
  return p ? { parte: p.nome, texto: `A parte “${p.nome}” falhou.`, url: p.url } : null;
}

// ------------------------------------------------------------------ saúde geral

// verde: publicou nas últimas 30 horas e a última coleta deu certo, sem avisos;
// amarelo: publicou há até 54 horas, mas a última coleta falhou ou saiu com avisos;
// vermelho: mais de 54 horas (duas coletas diárias perdidas) sem publicar.
export function saude({ execs, ultimaDetalhe, avisosPublicados = [], agora = Date.now() }) {
  const pub = execs.find((e) => e.situacao === "publicada");
  const fim = execs.find((e) => e.situacao === "publicada" || e.situacao === "falhou");
  const rodando = execs.find((e) => e.situacao === "rodando");
  const horas = pub ? (agora - new Date(pub.fim).getTime()) / 3600000 : Infinity;
  const motivo = fim?.situacao === "falhou" ? ultimaDetalhe?.motivo || null : null;
  const avisos = (ultimaDetalhe?.partes || []).filter((p) => p.estado === "aviso" || (p.estado === "erro" && fim?.situacao === "publicada"));
  let nivel, titulo, frase;
  if (horas > 54) {
    nivel = "critico"; titulo = "Atualizações paradas";
    frase = pub ? `Nenhuma publicação desde ${dataHora(pub.fim)} (${haQuanto(pub.fim, agora)}).` : "Nenhuma publicação encontrada nas últimas execuções.";
  } else if (fim?.situacao === "falhou" || horas > 30) {
    nivel = "atencao"; titulo = "Atenção: a última coleta não publicou";
    frase = `O site continua com os dados de ${dataHora(pub?.fim)} (${haQuanto(pub?.fim, agora)}).`;
    if (horas > 30 && fim?.situacao !== "falhou") titulo = "Atenção: atualização atrasada";
  } else if (avisos.length || avisosPublicados.length) {
    nivel = "atencao"; titulo = "Funcionando, com avisos";
    const n = avisos.length + avisosPublicados.length;
    frase = `Publicado ${haQuanto(pub.fim, agora)}, mas ${n === 1 ? "há 1 aviso" : `há ${n} avisos`} para olhar (veja abaixo).`;
  } else {
    nivel = "ok"; titulo = "Tudo funcionando";
    frase = `A última coleta publicou os dados ${haQuanto(pub.fim, agora)}.`;
  }
  return { nivel, titulo, frase, motivo, rodando: rodando || null, ultimaPublicacao: pub || null, horas };
}

// "Última vez que deu certo" de cada parte, olhando as execuções abertas etapa por etapa (da mais nova para a mais velha)
export function ultimaVezOk(detalhes, parteId) {
  for (const d of detalhes) {
    const p = d.partes.find((x) => x.id === parteId);
    if (p && (p.estado === "ok" || p.estado === "aviso")) return d.exec.fim || d.exec.inicio;
  }
  return null;
}

// ------------------------------------------------------------------ busca dos dados (navegador)

async function json(url, opcoes) {
  const r = await fetch(url, opcoes);
  if (!r.ok) {
    const limite = r.headers.get("x-ratelimit-remaining") === "0";
    const e = new Error(limite ? "limite" : `HTTP ${r.status}`);
    e.limite = limite;
    e.volta = Number(r.headers.get("x-ratelimit-reset")) * 1000 || null;
    throw e;
  }
  return r.json();
}

async function opcional(url) {
  try { return await json(url, { cache: "no-store" }); } catch { return null; }
}

// Execuções dos últimos 30 dias (até 3 páginas de 100; num dia comum são 2 a 8)
async function execucoesDe30Dias(gh) {
  const corte = Date.now() - 30 * 86400000;
  const todas = [];
  for (let pag = 1; pag <= 3; pag++) {
    const r = await json(`${API}/actions/workflows/${FLUXO}/runs?branch=main&per_page=100&page=${pag}`, gh);
    const lista = r.workflow_runs || [];
    todas.push(...lista);
    const ultima = lista[lista.length - 1];
    if (lista.length < 100 || !ultima || new Date(ultima.created_at).getTime() < corte) break;
  }
  return { workflow_runs: todas };
}

export async function carregar(base) {
  const gh = { headers: { Accept: "application/vnd.github+json" } };
  const [runs, repetir, meta, verif, metaMg] = await Promise.all([
    execucoesDe30Dias(gh),
    json(`${API}/actions/workflows/${FLUXO_REPETIR}/runs?per_page=10`, gh).catch(() => null),
    opcional(new URL("data/meta.json", base)),
    opcional(new URL("data/verificacao.json", base)),
    opcional(new URL("mg/data/meta.json", base)),
  ]);
  const execs = (runs.workflow_runs || []).map(resumirExecucao);
  const abrir = execs.filter((e) => e.situacao !== "cancelada").slice(0, DETALHAR);
  const detalhes = await Promise.all(abrir.map(async (exec) => {
    try {
      const { jobs } = await json(`${API}/actions/runs/${exec.id}/jobs?per_page=30`, gh);
      const anotsPorJob = {};
      // Anotações só dos jobs que podem explicar algo: a coleta, e qualquer um que falhou
      await Promise.all(jobs.filter((j) => j.name === "coletar" || j.conclusion === "failure").map(async (j) => {
        anotsPorJob[j.id] = await json(`${API}/check-runs/${j.id}/annotations?per_page=50`, gh).catch(() => []);
      }));
      const partes = partesDaExecucao(jobs, anotsPorJob);
      return { exec, partes, motivo: exec.situacao === "falhou" ? motivoDaFalha(partes) : null };
    } catch (e) {
      if (e.limite) throw e;
      return null;
    }
  }));
  return {
    lido_em: new Date().toISOString(), execs, detalhes: detalhes.filter(Boolean),
    repetir: (repetir?.workflow_runs || []).map((r) => ({ inicio: r.run_started_at || r.created_at, situacao: situacaoExecucao(r), url: r.html_url })),
    meta, verif, metaMg,
  };
}
