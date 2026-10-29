import type { Caso, Nivel, Status } from "./tipos.ts";
import { campoPartido, infoPartido, CAMPOS, type Campo } from "./partidos.ts";

/* Placar por partido: quantas pessoas de cada partido aparecem em cada situação, somando os casos.
   Regras:
   - Vale o partido da época dos fatos, agrupado pelo nome de hoje (PMDB e MDB contam juntos; PR e PL também).
   - Cada pessoa conta uma vez por caso. Quem aparece em dois casos pelo mesmo fato (ex.: cassado no Mensalão) conta só uma.
   - Grupos sem nome publicado (lista da CPI dos Sanguessugas) entram com o número de pessoas por partido.
   - Quem não tem partido (empresários, servidores) aparece nos casos, mas não no placar. */

export const STATUS: Record<Status, { nome: string; um: string; explica: string; cor: string }> = {
  condenado: { um: "Condenado", nome: "Condenados", explica: "Condenação mantida pela Justiça. Inclui quem já cumpriu a pena ou recebeu indulto.", cor: "var(--flag-r)" },
  condenado_recorre: { um: "Condenado (cabe recurso)", nome: "Condenados (cabe recurso)", explica: "Condenados, mas o processo ainda não terminou.", cor: "var(--c8)" },
  anulado: { um: "Condenação anulada", nome: "Condenação anulada", explica: "Foram condenados, mas a condenação foi anulada depois, em geral por erro no processo. Não é o mesmo que absolvição.", cor: "var(--c4)" },
  reu: { um: "Réu", nome: "Réus", explica: "A Justiça aceitou a denúncia e a pessoa responde a processo.", cor: "var(--c7)" },
  indiciado: { um: "Indiciado", nome: "Indiciados", explica: "A Polícia Federal concluiu que há indícios de crime. Ainda falta o Ministério Público denunciar.", cor: "var(--c5)" },
  investigado: { um: "Investigado", nome: "Investigados", explica: "Alvo de inquérito, operação ou CPI, sem acusação formal.", cor: "var(--s1)" },
  citado: { um: "Citado", nome: "Citados", explica: "Citados por delator, investigado ou reportagem, sem investigação aberta contra eles até onde as fontes mostram.", cor: "var(--c-outros)" },
  absolvido: { um: "Absolvido", nome: "Absolvidos", explica: "Absolvidos ou com a acusação arquivada.", cor: "var(--sim)" },
  sem_acusacao: { um: "Sem acusação", nome: "Sem acusação", explica: "Aparecem no caso (por exemplo, deixaram o cargo), mas não são acusados de nada.", cor: "var(--line)" },
};

/** Do mais grave para o mais leve: a ordem das barras e das colunas */
export const ORDEM: Status[] = ["condenado", "condenado_recorre", "anulado", "reu", "indiciado", "investigado", "citado", "absolvido", "sem_acusacao"];

/** O que entra no placar se a pessoa não mudar nada: de condenados a investigados */
export const PADRAO: Status[] = ["condenado", "condenado_recorre", "anulado", "reu", "indiciado", "investigado"];

export const NIVEL_NOME: Record<Nivel, string> = {
  1: "Presidente da República", 2: "Ministro, governador, presidente da Câmara ou de partido", 3: "Senador ou diretor de estatal",
  4: "Deputado federal", 5: "Outros cargos",
};

export interface LinhaPlacar {
  partido: string;            // nome de hoje
  siglas: string[];           // siglas da época que entraram na conta
  campo: Campo;
  nota: number | null;
  por: Record<Status, number>;
  total: number;              // só os status escolhidos
  casos: string[];            // ids dos casos em que o partido aparece (com os status escolhidos)
  maior: { nivel: Nivel; nome: string; papel: string } | null;
}

const zero = (): Record<Status, number> => Object.fromEntries(ORDEM.map((s) => [s, 0])) as Record<Status, number>;

export function placar(casos: Caso[], incluir: Status[]): LinhaPlacar[] {
  const conta = new Set(incluir);
  const linhas = new Map<string, LinhaPlacar>();
  const linha = (sigla: string) => {
    const hoje = infoPartido(sigla).hoje;
    let l = linhas.get(hoje);
    if (!l) {
      l = { partido: hoje, siglas: [], campo: campoPartido(sigla), nota: infoPartido(sigla).nota, por: zero(), total: 0, casos: [], maior: null };
      linhas.set(hoje, l);
    }
    if (!l.siglas.includes(sigla)) l.siglas.push(sigla);
    return l;
  };
  const somar = (l: LinhaPlacar, status: Status, n: number, caso: string) => {
    l.por[status] += n;
    if (conta.has(status)) {
      l.total += n;
      if (!l.casos.includes(caso)) l.casos.push(caso);
    }
  };
  for (const c of casos) {
    for (const p of c.pessoas) {
      if (!p.partido || p.repete) continue;
      const l = linha(p.partido);
      somar(l, p.status, 1, c.id);
      if (conta.has(p.status) && (!l.maior || p.nivel < l.maior.nivel)) l.maior = { nivel: p.nivel, nome: p.nome, papel: p.papel };
    }
    for (const g of c.grupos || []) {
      const l = linha(g.partido);
      somar(l, g.status, g.n, c.id);
      if (conta.has(g.status) && (!l.maior || 4 < l.maior.nivel)) l.maior = { nivel: 4, nome: `${g.n} parlamentar${g.n > 1 ? "es" : ""}`, papel: "Deputados e senadores citados pela CPI" };
    }
  }
  const pesoGrave = (l: LinhaPlacar) => ORDEM.map((s) => (conta.has(s) ? l.por[s] : 0));
  return [...linhas.values()]
    .filter((l) => l.total > 0)
    .sort((a, b) => {
      if (b.total !== a.total) return b.total - a.total;
      // Empate: quem tem mais casos graves fica na frente
      const ga = pesoGrave(a), gb = pesoGrave(b);
      for (let i = 0; i < ga.length; i++) if (gb[i] !== ga[i]) return gb[i] - ga[i];
      return a.partido.localeCompare(b.partido);
    });
}

/** Soma do placar por campo político (esquerda, centro, direita), na ordem da régua */
export function porCampo(linhas: LinhaPlacar[]): { campo: Campo; total: number; partidos: string[] }[] {
  const ordem: Campo[] = [...CAMPOS, "Sem classificação"];
  return ordem
    .map((campo) => {
      const ls = linhas.filter((l) => l.campo === campo);
      return { campo, total: ls.reduce((a, l) => a + l.total, 0), partidos: ls.map((l) => l.partido) };
    })
    .filter((x) => x.total > 0);
}

/** Contagens gerais para o topo da página */
export function resumoGeral(casos: Caso[]) {
  const pessoas = casos.flatMap((c) => c.pessoas.filter((p) => !p.repete));
  return {
    casos: casos.length,
    pessoas: pessoas.length + casos.reduce((a, c) => a + (c.grupos || []).reduce((s, g) => s + g.n, 0), 0),
    condenados: pessoas.filter((p) => p.status === "condenado").length,
    emInvestigacao: casos.filter((c) => c.situacao === "investigacao").length,
  };
}
