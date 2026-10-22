/** Como cada partido se define, nas próprias palavras, com a fonte. */

export const LADOS = ["Esquerda", "Centro-esquerda", "Centro", "Centro-direita", "Direita"] as const;
export type Lado = (typeof LADOS)[number];

export type Fonte = { nome: string; url: string; quando: string };
export type Autodefinicao = {
  /** Lado em que o próprio partido se coloca. null: o partido não se coloca entre esquerda e direita. */
  lado: Lado | null;
  /** O que o partido diz de si. */
  diz: string;
  /** true quando `diz` é uma citação literal. */
  literal?: boolean;
  fonte: Fonte;
  nota?: string;
};

/* A maioria das respostas vem de um levantamento em que o Estadão perguntou aos 33 partidos registrados no TSE como cada um se define. */
const ESTADAO_2019: Fonte = {
  nome: "resposta do partido ao Estadão",
  url: "https://www.em.com.br/app/noticia/politica/2019/12/25/interna_politica,1110467/maioria-dos-partidos-se-identifica-como-de-centro.shtml",
  quando: "dez. 2019",
};

const TABELA: Record<string, Autodefinicao> = {
  pt: { lado: "Esquerda", diz: "de esquerda democrática e libertária", literal: true, fonte: ESTADAO_2019 },
  pcdob: { lado: "Esquerda", diz: "orienta-se pela teoria marxista-leninista", literal: true, fonte: ESTADAO_2019 },
  psol: { lado: "Esquerda", diz: "Se define como socialista.", fonte: ESTADAO_2019 },
  psb: { lado: "Centro-esquerda", diz: "Se define como de centro-esquerda.", fonte: ESTADAO_2019 },
  pdt: { lado: "Centro-esquerda", diz: "raízes no trabalhismo histórico de Vargas", literal: true, fonte: ESTADAO_2019 },
  pv: { lado: "Centro-esquerda", diz: "Se define como de centro-esquerda.", fonte: ESTADAO_2019 },
  cidadania: { lado: "Centro-esquerda", diz: "Se define como de centro-esquerda.", fonte: ESTADAO_2019 },
  mdb: { lado: "Centro", diz: "Se define como de centro.", fonte: ESTADAO_2019 },
  psd: { lado: "Centro", diz: "Se define como de centro.", fonte: ESTADAO_2019 },
  avante: { lado: "Centro", diz: "Se define como de centro.", fonte: ESTADAO_2019 },
  podemos: { lado: "Centro", diz: "Mais transparência, mais participação e mais democracia direta", literal: true, fonte: ESTADAO_2019 },
  prd: {
    lado: "Centro", diz: "Nasce um partido de centro que tem como essência a defesa da democracia", literal: true,
    fonte: { nome: "nota de fundação do partido", url: "https://www.gazetadopovo.com.br/republica/tse-aprova-criacao-prd-partido-funde-ptb-patriota/", quando: "nov. 2023" },
  },
  progressistas: { lado: "Centro-direita", diz: "Se define como de centro-direita.", fonte: ESTADAO_2019 },
  republicanos: { lado: "Centro-direita", diz: "liberal na economia", literal: true, fonte: ESTADAO_2019 },
  pl: {
    lado: "Direita", diz: "seguiremos unidos nas pautas conservadoras que a direita sempre defende", literal: true,
    fonte: { nome: "carta do partido aos seus parlamentares", url: "https://static.poder360.com.br/2023/07/Carta_PL-Nacional.pdf", quando: "jul. 2023" },
    nota: "Em 2019, o PL se dizia “liberal de centro”.",
  },
  missao: {
    lado: "Direita", diz: "hoje pode ser enquadrado como um partido no campo da direita altamente pragmático", literal: true,
    fonte: { nome: "Renan Santos, presidente do partido", url: "https://jornaldebrasilia.com.br/noticias/politica-e-poder/presidente-de-partido-do-mbl-ve-implosao-do-bolsonarismo-e-pretende-disputar-planalto/", quando: "set. 2025" },
  },
  uniao: {
    lado: null, diz: "Liberal não só na política, mas nos costumes e na economia", literal: true,
    fonte: { nome: "Luciano Bivar, presidente na fundação", url: "https://congressoemfoco.com.br/area/congresso-nacional/tse-aprova-por-unanimidade-a-criacao-do-partido-uniao-brasil/", quando: "dez. 2021" },
  },
  psdb: { lado: null, diz: "liberalismo social", literal: true, fonte: ESTADAO_2019 },
  novo: { lado: null, diz: "Se define apenas como liberal.", fonte: ESTADAO_2019 },
  solidariedade: { lado: null, diz: "humanismo sistêmico", literal: true, fonte: ESTADAO_2019 },
  rede: { lado: null, diz: "sustentabilismo progressista", literal: true, fonte: ESTADAO_2019, nota: "Diz que a divisão entre esquerda e direita não serve para ela." },
};

const APELIDOS: Record<string, string> = { pode: "podemos", pp: "progressistas" };

const chave = (sigla: string) => (sigla || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z]/g, "");

export function autodefinicao(sigla: string): Autodefinicao | undefined {
  const k = chave(sigla);
  return TABELA[APELIDOS[k] || k];
}

/** Mesmos cortes de etl/sa_etl/ideologia.py (rotulo). */
export function ladoPelosVotos(pos: number): Lado {
  if (pos <= -0.5) return "Esquerda";
  if (pos <= -0.15) return "Centro-esquerda";
  if (pos < 0.15) return "Centro";
  if (pos < 0.5) return "Centro-direita";
  return "Direita";
}
