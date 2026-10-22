// Tipos e funções para ler os arquivos JSON gerados pelo coletor (etl/).
export type Casa = "camara" | "senado";
export type Grupo = "pessoal" | "escritorio" | "servicos";

/* Valores de um ano. "total" é a cota (reembolsos com nota fiscal). O resto vem das páginas oficiais. */
export interface AnoResumo {
  total: number; grupos: Record<Grupo, number>;
  salario: number | null; verba_gabinete: number | null; outros_gastos: number | null;
  cota_oficial: number | null; n_pessoal: number | null; custo_total: number;
  fora_do_periodo?: number; meses_fora?: number[];
  atuacao?: Atuacao;
}
/** Atuação no ano. Presença: [presente, ausência justificada, ausência não justificada].
 *  Câmara: tudo da página oficial do deputado (Plenário em dias, comissões em reuniões).
 *  Senado: propostas, relatorias e discursos dos dados abertos; Plenário contado pelas votações nominais. */
export interface Atuacao {
  autoria?: number; relatadas?: number; votacoes?: number; discursos?: number;
  plenario?: [number, number, number]; comissoes?: [number, number, number];
}
export type MetricaAtuacao = "autoria" | "relatadas" | "votacoes" | "discursos";
export const METRICAS_ATUACAO: { chave: MetricaAtuacao; nome: string; explica: Record<Casa, string> }[] = [
  { chave: "autoria", nome: "Propostas apresentadas", explica: {
    camara: "Projetos, requerimentos e outras propostas de que foi autor ou coautor no ano.",
    senado: "Projetos, requerimentos e outras propostas de que foi autor ou coautor no ano." } },
  { chave: "relatadas", nome: "Relatorias", explica: {
    camara: "Propostas em que foi relator: quem estuda o texto e dá o parecer para os colegas votarem.",
    senado: "Propostas em que foi relator no ano: quem estuda o texto e dá o parecer para os colegas votarem." } },
  { chave: "votacoes", nome: "Votações no Plenário", explica: {
    camara: "Votações nominais (em que cada voto fica registrado com o nome) de que participou.",
    senado: "Votações nominais (em que cada voto fica registrado com o nome) de que participou." } },
  { chave: "discursos", nome: "Discursos", explica: {
    camara: "Discursos no Plenário da Câmara.",
    senado: "Falas registradas no Senado: discursos, falas como relator, pela ordem e pela liderança." } },
];
/** Teve mandato no ano: há presença registrada ou alguma atividade. */
export function atuacaoAtiva(a?: Atuacao): a is Atuacao {
  if (!a) return false;
  const soma = (x?: number[]) => (x ? x[0] + x[1] + x[2] : 0);
  return soma(a.plenario) + soma(a.comissoes) + (a.votacoes || 0) + (a.autoria || 0) + (a.discursos || 0) > 0;
}
/** Parte das sessões em que esteve presente (0 a 1), ou null se não houve sessões. */
export function taxaPresenca(x?: [number, number, number]): number | null {
  const t = x ? x[0] + x[1] + x[2] : 0;
  return t ? x![0] / t : null;
}
export interface Resumo {
  id: string; casa: Casa; cargo: string; nome: string; partido: string; uf: string; foto: string;
  bloco?: string; fonte: string; total: number; por_ano: Record<string, AnoResumo>;
  posicao: number | null; rotulo: string; alinhamento_governo: number | null; campo: string | null;
  fidelidade_partido: number | null; n_votos: number;
}
export interface Pessoa { nome: string; grupo: string; cargo: string; periodo: string }
export interface Recursos {
  cota_oficial?: number; verba_gasto?: number; verba_disponivel?: number; verba_meses?: { mes: number; valor: number }[];
  n_pessoal?: number; salario_bruto?: number; salario_estimado?: boolean; salario_ano?: number | null; salario_meses?: { mes: number; valor: number }[];
  imovel_funcional?: string; auxilio_moradia?: string; viagens_missao?: number; passaporte_diplomatico?: string;
  outros_gastos?: { recurso: string; valor: number }[]; outros_total?: number;
  beneficios?: { beneficio: string; utilizacao: string }[]; vinculos?: { vinculo: string; quantidade: number }[];
  equipe?: Pessoa[];
}
export interface AnoDetalhe extends AnoResumo {
  categorias: { categoria: string; grupo: Grupo; valor: number }[];
  meses: { mes: number; valor: number }[];
  fornecedores: Fornecedor[];
  maiores_notas: Nota[];
  sem_nota_meses?: { mes: number; valor: number; url: string }[];
  passagens_da_lista?: { n: number; valor: number };
  recursos: Recursos | null;
}
export interface Fornecedor { doc: string; tipo: string; nome: string; valor: number; n: number; ficha: boolean; socios: string[] }
export interface Nota { data: string; categoria: string; fornecedor: string; doc: string; valor: number; url: string; link?: string; detalhe?: string }
export interface Politico extends Resumo {
  anos: Record<string, AnoDetalhe>;
  temas?: Record<string, { Sim?: number; "Não"?: number; Outros?: number; contra_partido?: number }>;
  votos: { votacao: string; voto: string; partido: string }[];
}
export interface Proposicao { sigla: string; numero: string; ano: string; ementa: string; titulo: string; url: string }
export interface VotacaoResumo { id: string; casa: Casa; data: string; descricao: string; aprovada: boolean; proposicao: Proposicao | null; sim: number; nao: number; temas?: string[] }
export const TEMAS = ["Mulheres", "Micro e pequenas empresas", "Saúde", "Educação", "Segurança pública", "Armas", "Meio ambiente",
  "Impostos e contas públicas", "Trabalho e aposentadoria", "Agropecuária", "Crianças e adolescentes", "Indígenas e minorias",
  "Energia e combustíveis", "Eleições e política"];
export interface Votacao extends VotacaoResumo {
  orientacoes: Record<string, string>; fonte: string; contagem: Record<string, number>;
  por_partido: Record<string, Record<string, number>>; por_lado: Record<string, Record<string, number>>;
  votos: { politico: string; nome: string; partido: string; uf: string; voto: string; posicao: number | null }[];
}
export interface Socio { nome: string; doc: string; qualificacao: string; entrada: string; faixa_etaria: string; tipo?: "empresa" | "pessoa" | "estrangeiro" | ""; outras_empresas: { cnpj: string; nome: string; total: number }[] }
/** Dono final: a pessoa (ou o ponto onde a busca parou) por trás de uma ou mais empresas sócias */
export interface DonoFinal {
  nome: string; doc: string; tipo: string; qualificacao: string; pais: string;
  cadeia: { cnpj: string; nome: string; qualificacao: string }[];
  fim: "pessoa" | "estrangeiro" | "sem_socios" | "sem_dados" | "limite" | "ciclo";
  outras_empresas: { cnpj: string; nome: string; total: number }[];
}
export interface EmpresaResumo { cnpj: string; nome: string; total: number; n_politicos: number; tem_socios: boolean; n_mesmo_endereco?: number; tem_holding?: boolean }
export interface Empresa extends EmpresaResumo {
  empresa: null | { razao_social: string; nome_fantasia: string; situacao: string; abertura: string; atividade: string; municipio: string; uf: string; capital_social: number; porte: string; natureza: string;
    endereco?: { logradouro: string; numero: string; complemento: string; bairro: string; cep: string } };
  socios: Socio[];
  donos_finais?: DonoFinal[];
  n_notas?: number; notas_por_ano?: Record<string, number>;
  por_mes?: { politico: string; nome: string; ano: number; mes: number; valor: number }[];
  mesmo_endereco?: { cnpj: string; nome: string; total: number; mesmos_socios: boolean }[]; pagadores: { politico: string; nome: string; partido: string; uf: string; valor: number }[]; alertas: string[];
}
/* Nota fiscal na página da empresa: [data, id do político, tipo de gasto, valor, link] */
/** [data, parlamentar, tipo de gasto, valor, link, tipo de link, detalhe]. Tipo de link: "nota" (imagem da nota),
 *  "detalhe" (página oficial da despesa na Câmara), "lista" (lista oficial do Senado ou resumo do mês na Câmara). */
export type NotaEmpresa = [string, string, string, number, string, string?, string?];
export interface PartidoAno { n: number; cota: number; cota_por_membro: number; custo_total: number; custo_por_membro: number }
export interface Partido { casa: Casa; sigla: string; n: number; posicao: number | null; alinhamento_governo: number | null; fidelidade: number | null; total: number; por_ano: Record<string, PartidoAno> }
export interface Meta {
  atualizado_em: string; anos: number[]; grupos: Record<Grupo, string>; medias: Record<string, Record<Casa, number>>;
  contagens: { politicos: number; despesas: number; votacoes: number; empresas_com_socios: number }; total_gasto: number;
  total_por_ano: Record<string, number>; custo_por_ano: Record<string, number>;
}

const cache = new Map<string, Promise<unknown>>();
export function load<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(path, fetch(`./data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Não encontrado: ${path}`);
      return r.json();
    }).catch((e) => { cache.delete(path); throw e; }));
  }
  return cache.get(path) as Promise<T>;
}

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const brl2 = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const reais = (v: number, centavos = false) => (centavos ? brl2 : brl).format(v || 0);
export function reaisCurto(v: number): string {
  if (v >= 1e9) return `R$ ${(v / 1e9).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} bi`;
  if (v >= 1e6) return `R$ ${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (v >= 1e3) return `R$ ${(v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mil`;
  return reais(v);
}
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
export const dataBR = (s: string) => (s ? s.slice(0, 10).split("-").reverse().join("/") : "");
export const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
export const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
export function cnpjFmt(c: string): string {
  const d = c.replace(/\D/g, "");
  if (d.length !== 14) return c;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}
export const casaNome = (c: Casa) => (c === "camara" ? "Câmara" : "Senado");
export const GRUPO_CURTO: Record<Grupo, string> = { pessoal: "Com o próprio parlamentar", escritorio: "Com o gabinete", servicos: "Com serviços contratados" };
export const GRUPO_EXPLICA: Record<Grupo, string> = {
  pessoal: "Passagens, hospedagem, comida, combustível, aluguel de carro e táxi.",
  escritorio: "Aluguel e contas do escritório no estado, telefone, correio, material e assinaturas.",
  servicos: "Divulgação do mandato, consultorias, pesquisas e segurança.",
};
const semAcento = (t: string) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

/** Que parte da proposta estava em votação. Num mesmo dia a mesma proposta pode ter várias votações:
 *  o texto principal, cada destaque, emendas e requerimentos. */
export function tipoVotacao(descricao: string): string {
  // "ressalvado o destaque" quer dizer que o texto principal foi votado e os destaques ficaram para depois
  const d = semAcento(descricao || "").replace(/ressalvad[oa]s? (os? )?(destaques?|emendas?)( destacadas?)?/g, "");
  if (/requerimento/.test(d)) return /urgencia/.test(d) ? "Pedido de urgência" : "Requerimento";
  if (/destaque|destacad|\bdtq\b|mantid[oa] o texto|supressiva/.test(d)) return "Destaque (trecho votado à parte)";
  if (/redacao final/.test(d)) return "Redação final";
  if (/segundo turno|2o turno/.test(d)) return "Texto principal, 2º turno";
  if (/primeiro turno|1o turno/.test(d)) return "Texto principal, 1º turno";
  if (/emenda aglutinativa/.test(d)) return "Emenda aglutinativa";
  if (/preferencia/.test(d)) return "Preferência (ordem de votação)";
  if (/subemenda substitutiva|substitutivo|parecer|projeto|proposta|texto|materia/.test(d)) return "Texto principal";
  if (/emenda/.test(d)) return "Emenda";
  return "";
}

/** Descrição oficial da votação sem a contagem de votos no final (já mostramos Sim e Não ao lado). */
export function descricaoCurta(descricao: string): string {
  return (descricao || "").replace(/\s*(Sim|SIM)\s*:\s*\d+.*$/s, "").replace(/\s*Total\s*:.*$/is, "").trim();
}

export function proposicaoNome(p: Proposicao | null): string {
  if (!p) return "";
  if (p.sigla && p.numero) return `${p.sigla} ${p.numero}/${p.ano}`;
  return p.titulo || "";
}

/** Cor conhecida de cada partido (PT vermelho, PL azul...). Partidos sem cor definida ficam cinza. */
const PARTIDOS_COM_COR = new Set(["pt", "pcdob", "pdt", "psb", "psol", "pv", "rede", "avante", "psd", "mdb", "pode", "pp", "uniao", "republicanos", "psdb", "pl", "novo", "solidariedade", "cidadania", "prd", "missao", "agir", "dc", "pcb"]);
export function corPartido(sigla: string): string {
  const k = (sigla || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z]/g, "");
  return PARTIDOS_COM_COR.has(k) ? `var(--p-${k})` : "var(--c-outros)";
}
