/* Seção Corrupção: tipos dos casos. O conteúdo é escrito à mão (não há API oficial que junte processos, delações e
   cassações), sempre com o link para a fonte original: STF, PF, MPF, CGU, Câmara, Senado ou imprensa reconhecida. */

export interface Fonte { nome: string; url: string }

/** Em que pé está cada pessoa, do mais grave para o mais leve. "anulado" é quem foi condenado, mas teve a condenação
 *  anulada depois (por exemplo, por erro de foro ou parcialidade do juiz): não é o mesmo que ser absolvido. */
export type Status =
  | "condenado"          // condenação mantida pela Justiça (pode já ter cumprido a pena ou recebido indulto)
  | "condenado_recorre"  // condenado, mas ainda cabe recurso
  | "anulado"            // foi condenado, mas a condenação foi anulada depois
  | "reu"                // denúncia aceita: responde a ação penal
  | "indiciado"          // a Polícia Federal concluiu que há indícios de crime; falta o Ministério Público denunciar
  | "investigado"        // alvo de inquérito, operação ou CPI, sem acusação formal
  | "citado"             // citado por delator, investigado ou reportagem, sem investigação aberta contra ele até onde as fontes mostram
  | "absolvido"          // absolvido ou acusação arquivada
  | "sem_acusacao";      // aparece no caso (por exemplo, saiu do cargo), mas não é acusado de nada

export type Situacao = "encerrado" | "parcial" | "investigacao";

/** Nível do cargo mais alto que a pessoa ocupava, para medir influência: 1 é o mais alto. */
export type Nivel = 1 | 2 | 3 | 4 | 5;

export interface Pessoa {
  nome: string;
  /** Cargo ou função na época dos fatos */
  papel: string;
  /** Sigla do partido na época dos fatos (vazio para quem não era filiado) */
  partido?: string;
  nivel: Nivel;
  status: Status;
  /** O que a Justiça, a polícia ou o Ministério Público dizem, em linguagem simples */
  detalhe: string;
  pena?: string;
  /** Delação premiada, acordo de não persecução, indulto... */
  acordo?: string;
  /** Perda de mandato ligada ao caso */
  cassado?: string;
  /** Onde a pessoa está hoje */
  onde: string;
  /** Id do deputado na Câmara (foto oficial e link para o perfil) */
  camara?: number;
  /** Código do senador no Senado */
  senado?: number;
  /** Já aparece em outro caso pelo mesmo fato: mostrado aqui, mas não conta de novo no placar */
  repete?: string;
  fontes: Fonte[];
}

/** Grupo de pessoas sem nome publicado por partido (ex.: a lista da CPI dos Sanguessugas) */
export interface Grupo { partido: string; n: number; status: Status; nota: string; fonte: Fonte }

export interface Evento { data: string; texto: string; fonte?: Fonte }

export interface Empresa {
  nome: string;
  papel: string;
  /** Situação hoje: se ainda existe, com que nome */
  hoje: string;
  /** Relação com o governo hoje, quando as fontes mostram */
  governo: string;
  /** Termo para procurar no Portal da Transparência (contratos e sanções atuais) */
  busca?: string;
  fontes: Fonte[];
}

export interface Acordo { tipo: "Delação premiada" | "Acordo de leniência" | "Proposta de delação"; quem: string; quando: string; resumo: string; fonte: Fonte }

export interface Visao { texto: string[]; fontes: Fonte[] }

export interface Caso {
  id: string;
  nome: string;
  subtitulo: string;
  periodo: string;
  situacao: Situacao;
  situacaoTexto: string;
  resumo: string[];
  valor: { texto: string; nota: string; fonte: Fonte };
  /** Valor em reais para comparar os casos no gráfico (0 quando não há estimativa) */
  valorNum: number;
  timeline: Evento[];
  pessoas: Pessoa[];
  grupos?: Grupo[];
  empresas: Empresa[];
  acordos: Acordo[];
  visoes: { esquerda: Visao; direita: Visao; justica: Visao };
  fontes: Fonte[];
}
