import type { Fonte } from "./tipos.ts";

/* Esquerda, centro ou direita: nota de 0 (extrema-esquerda) a 10 (extrema-direita) dada por 519 cientistas políticos
   na pesquisa de Bolognesi, Ribeiro e Codato, "Uma Nova Classificação Ideológica dos Partidos Políticos Brasileiros"
   (revista Dados, 2023). É uma fonte de fora, independente da régua por votos que o site calcula para cada parlamentar. */
export const FONTE_IDEOLOGIA: Fonte = {
  nome: "Bolognesi, Ribeiro e Codato (2023), revista Dados",
  url: "https://scielo.br/j/dados/a/zzyM3gzHD4P45WWdytXjZWg/?format=pdf",
};

export const CAMPOS = ["Extrema-esquerda", "Esquerda", "Centro-esquerda", "Centro", "Centro-direita", "Direita", "Extrema-direita"] as const;
export type Campo = (typeof CAMPOS)[number] | "Sem classificação";

/** Cortes do artigo: 0 a 1,5 extrema-esquerda; até 3 esquerda; até 4,49 centro-esquerda; até 5,5 centro;
 *  até 7 centro-direita; até 8,5 direita; acima disso extrema-direita. */
export function campoDaNota(n: number): Campo {
  if (n <= 1.5) return "Extrema-esquerda";
  if (n <= 3) return "Esquerda";
  if (n < 4.5) return "Centro-esquerda";
  if (n <= 5.5) return "Centro";
  if (n <= 7) return "Centro-direita";
  if (n <= 8.5) return "Direita";
  return "Extrema-direita";
}

export interface InfoPartido {
  /** Nome de hoje (o partido que herdou a sigla da época) */
  hoje: string;
  /** Nota do artigo para a sigla (ou para a herdeira, quando a da época não foi avaliada) */
  nota: number | null;
  nota_de?: string;
  obs?: string;
}

/** Siglas da época dos fatos. As que mudaram de nome apontam para o partido de hoje. */
export const PARTIDOS: Record<string, InfoPartido> = {
  PT: { hoje: "PT", nota: 2.97 },
  PCdoB: { hoje: "PCdoB", nota: 1.92 },
  PDT: { hoje: "PDT", nota: 3.92 },
  PSB: { hoje: "PSB", nota: 4.05 },
  PPS: { hoje: "Cidadania", nota: 4.92 },
  PTB: { hoje: "PRD", nota: 6.1, obs: "O PTB se juntou ao Patriota e virou PRD em 2023." },
  PMDB: { hoje: "MDB", nota: 7.01, obs: "Nota 7,01: no limite entre centro-direita e direita." },
  MDB: { hoje: "MDB", nota: 7.01, obs: "Nota 7,01: no limite entre centro-direita e direita." },
  PSDB: { hoje: "PSDB", nota: 7.11 },
  PSD: { hoje: "PSD", nota: 7.09 },
  // O PL de 2005 virou PR em 2006 e voltou a se chamar PL em 2019: é o mesmo partido
  PL: { hoje: "PL", nota: 7.78, nota_de: "PR", obs: "O PL virou PR em 2006 e voltou a ser PL em 2019. A pesquisa avaliou a sigla PR." },
  PR: { hoje: "PL", nota: 7.78, obs: "O PR voltou a se chamar PL em 2019." },
  PRB: { hoje: "Republicanos", nota: 7.78 },
  Republicanos: { hoje: "Republicanos", nota: 7.78, nota_de: "PRB" },
  PP: { hoje: "PP", nota: 8.2 },
  PPB: { hoje: "PP", nota: 8.2, nota_de: "Progressistas", obs: "O PPB virou PP (Progressistas) em 2003." },
  PSC: { hoje: "PSC", nota: 8.33, obs: "O PSC se juntou ao Podemos em 2023." },
  PFL: { hoje: "União", nota: 8.57, nota_de: "DEM", obs: "O PFL virou DEM em 2007, que se juntou ao PSL e virou União Brasil em 2022." },
  DEM: { hoje: "União", nota: 8.57, obs: "O DEM se juntou ao PSL e virou União Brasil em 2022." },
  "União": { hoje: "União", nota: null, obs: "O União Brasil nasceu depois da pesquisa, da fusão do DEM (nota 8,57) com o PSL (8,11)." },
  PRN: { hoje: "Agir", nota: 7.86, nota_de: "PTC", obs: "O PRN virou PTC em 2000 e Agir em 2022. A pesquisa avaliou a sigla PTC." },
};

export function infoPartido(sigla: string): InfoPartido {
  return PARTIDOS[sigla] || { hoje: sigla, nota: null };
}

export function campoPartido(sigla: string): Campo {
  const n = infoPartido(sigla).nota;
  return n == null ? (sigla === "União" ? "Direita" : "Sem classificação") : campoDaNota(n);
}

/** Cor do campo, na mesma régua vermelho-cinza-azul do resto do site */
export function corCampo(c: Campo): string {
  if (c === "Extrema-esquerda" || c === "Esquerda") return "var(--esq)";
  if (c === "Centro-esquerda") return "color-mix(in srgb, var(--esq) 55%, var(--centro))";
  if (c === "Centro") return "var(--centro)";
  if (c === "Centro-direita") return "color-mix(in srgb, var(--dir) 55%, var(--centro))";
  if (c === "Direita" || c === "Extrema-direita") return "var(--dir)";
  return "var(--c-outros)";
}
