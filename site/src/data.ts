import type { DocPagamento } from "./components/DocsEmendas";
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
 *  Câmara: página oficial do deputado (Plenário em dias, comissões em reuniões); projetos e requerimentos dos arquivos
 *  de proposições dos dados abertos. Senado: dados abertos; Plenário contado pelas votações nominais.
 *  projetos: como primeiro autor; projetos_apoio: assinou o projeto de outro autor; requerimentos: como primeiro autor.
 *  autoria: o total da página da Câmara (tudo junto), usado só quando não há a contagem separada. */
export interface Atuacao {
  autoria?: number; projetos?: number; projetos_apoio?: number; requerimentos?: number;
  relatadas?: number; votacoes?: number; discursos?: number;
  plenario?: [number, number, number]; comissoes?: [number, number, number];
}
export type MetricaAtuacao = "projetos" | "projetos_apoio" | "requerimentos" | "autoria" | "relatadas" | "votacoes" | "discursos";
export const METRICAS_ATUACAO: { chave: MetricaAtuacao; nome: string; explica: Record<Casa, string> }[] = [
  { chave: "projetos", nome: "Projetos de autoria própria", explica: {
    camara: "Projetos de lei, de emenda à Constituição e outros projetos que apresentou no ano como primeiro autor.",
    senado: "Projetos de lei, de emenda à Constituição e outros projetos que apresentou no ano como primeiro autor." } },
  { chave: "projetos_apoio", nome: "Projetos de colegas que assinou", explica: {
    camara: "Projetos de outro autor que assinou junto, como coautor ou apoiador. Uma emenda à Constituição, por exemplo, só pode ser apresentada com a assinatura de 171 deputados.",
    senado: "Projetos de outro autor que assinou junto, como coautor ou apoiador. Uma emenda à Constituição, por exemplo, só pode ser apresentada com a assinatura de 27 senadores." } },
  { chave: "requerimentos", nome: "Requerimentos e indicações", explica: {
    camara: "Pedidos de informação a ministérios, de audiência pública, de urgência, homenagens e sugestões ao governo, como primeiro autor. Não contamos os pedidos de procedimento, como adiar uma votação, que alguns deputados apresentam aos milhares.",
    senado: "Pedidos de informação a ministérios, de audiência pública, de urgência, homenagens e sugestões ao governo, como primeiro autor." } },
  { chave: "autoria", nome: "Propostas apresentadas", explica: {
    camara: "Projetos, requerimentos e outras propostas de que foi autor ou coautor no ano. Alguns deputados apresentam centenas de requerimentos por ano.",
    senado: "Projetos, requerimentos e outras propostas de que foi autor ou coautor no ano." } },
  { chave: "relatadas", nome: "Relatorias", explica: {
    camara: "Propostas em que foi relator: quem estuda o texto e dá o parecer para os colegas votarem. Membros da Mesa Diretora, como o 1º vice-presidente, aparecem com milhares de propostas e relatorias, porque a página oficial conta os pareceres que eles dão em nome da Mesa.",
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
  return soma(a.plenario) + soma(a.comissoes) + (a.votacoes || 0) + (a.autoria || 0) + (a.discursos || 0)
    + (a.projetos || 0) + (a.projetos_apoio || 0) + (a.requerimentos || 0) > 0;
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
/** sim e não: votos listados (no site nacional, de quem está no mandato hoje; no Minas Nossa, da bancada de MG).
    placar_casa: placar oficial da Casa inteira, inclusive quem já saiu do cargo. */
export interface VotacaoResumo { id: string; casa: Casa; data: string; descricao: string; aprovada: boolean; proposicao: Proposicao | null; sim: number; nao: number; temas?: string[]; placar_casa?: { sim: number; nao: number } }
export const TEMAS = ["Mulheres", "Micro e pequenas empresas", "Saúde", "Educação", "Segurança pública", "Armas", "Meio ambiente",
  "Impostos e contas públicas", "Trabalho e aposentadoria", "Agropecuária", "Crianças e adolescentes", "Indígenas e minorias",
  "Energia e combustíveis", "Eleições e política"];
export interface Votacao extends VotacaoResumo {
  orientacoes: Record<string, string>; fonte: string; contagem: Record<string, number>;
  por_partido: Record<string, Record<string, number>>; por_lado: Record<string, Record<string, number>>;
  /** Minas Nossa: votos da bancada de MG por partido (por_partido e por_lado continuam sendo da Casa inteira) */
  por_partido_mg?: Record<string, Record<string, number>>;
  votos: { politico: string; nome: string; partido: string; uf: string; voto: string; posicao: number | null }[];
}
export interface Socio { nome: string; doc: string; qualificacao: string; entrada: string; faixa_etaria: string; tipo?: "empresa" | "pessoa" | "estrangeiro" | ""; outras_empresas: OutraEmpresa[] }
/** Dono final: a pessoa (ou o ponto onde a busca parou) por trás de uma ou mais empresas sócias */
export interface DonoFinal {
  nome: string; doc: string; tipo: string; qualificacao: string; pais: string;
  cadeia: { cnpj: string; nome: string; qualificacao: string }[];
  fim: "pessoa" | "estrangeiro" | "sem_socios" | "sem_dados" | "limite" | "ciclo";
  outras_empresas: OutraEmpresa[];
}
/** Outra empresa do mesmo dono: total recebido da cota e, se houver, de emendas, do governo federal e renúncia fiscal */
export interface OutraEmpresa { cnpj: string; nome: string; total: number; emendas?: number; governo?: number; renuncia?: number }
export interface EmpresaResumo { cnpj: string; nome: string; total: number; n_politicos: number; por_ano?: Record<string, { valor: number; n_politicos: number }>; tem_socios: boolean; n_mesmo_endereco?: number; tem_holding?: boolean; emendas?: number; governo?: number; renuncia?: number }
export interface Empresa extends Omit<EmpresaResumo, "emendas" | "governo" | "renuncia"> {
  empresa: null | { razao_social: string; nome_fantasia: string; situacao: string; abertura: string; atividade: string; municipio: string; uf: string; capital_social: number; porte: string; natureza: string;
    endereco?: { logradouro: string; numero: string; complemento: string; bairro: string; cep: string } };
  socios: Socio[];
  donos_finais?: DonoFinal[];
  /** O que recebeu de emendas parlamentares (pagamentos do governo federal) */
  emendas?: null | { total: number; por_ano: Record<string, number>; orgaos: [string, number][];
    autores: { nome: string; politico: string | null; partido: string; valor: number }[]; docs: DocPagamento[];
    /** Detalhe de cada ano: de quem eram as emendas e quem pagou */
    anos?: Record<string, { valor: number; autores: { nome: string; politico: string | null; partido: string; valor: number }[]; orgaos: [string, number][] }> };
  /** Pagamentos do governo federal (compras, obras, serviços, convênios, subsídios), pelo ano do pagamento */
  governo?: null | { total: number; por_ano: Record<string, number>; cats: [string, number][]; orgaos: [string, number][];
    anos?: Record<string, { valor: number; n: number; cats: [string, number][]; orgaos: [string, number][] }> };
  /** Renúncia fiscal: imposto federal que deixou de pagar, pelo ano-calendário */
  renuncia?: null | { total: number; por_ano: Record<string, number>; beneficios: [string, number][]; fonte: string;
    anos?: Record<string, { valor: number; beneficios: [string, number][] }> };
  n_notas?: number; notas_por_ano?: Record<string, number>;
  por_mes?: { politico: string; nome: string; ano: number; mes: number; valor: number }[];
  mesmo_endereco?: (OutraEmpresa & { mesmos_socios: boolean })[]; pagadores: { politico: string; nome: string; partido: string; uf: string; valor: number }[]; alertas: string[];
}
/* Nota fiscal na página da empresa: [data, id do político, tipo de gasto, valor, link] */
/** [data, parlamentar, tipo de gasto, valor, link, tipo de link, detalhe]. Tipo de link: "nota" (imagem da nota),
 *  "detalhe" (página oficial da despesa na Câmara), "sem_pdf" (nota cujo PDF dá erro 404 na Câmara: link para o detalhe),
 *  "lista" (lista oficial do Senado ou resumo do mês na Câmara). */
export type NotaEmpresa = [string, string, string, number, string, string?, string?];
export interface PartidoAno { n: number; cota: number; cota_por_membro: number; custo_total: number; custo_por_membro: number }
export interface Partido { casa: Casa; sigla: string; n: number; posicao: number | null; alinhamento_governo: number | null; fidelidade: number | null; total: number; por_ano: Record<string, PartidoAno> }
/* Página da cidade (Minas Nossa): dados do TSE desde 1996 */
export interface PessoaEleita { nome: string; partido: string; partido_hoje: string; mudou: string | null; votos?: number; pct?: number | null }
export interface Candidato { turno?: number; nome: string; partido: string; votos: number; pct: number | null; eleito: boolean }
export interface MandatoPrefeito {
  eleicao: number; inicio: number; fim: number; turnos: number; prefeito: PessoaEleita; vice: PessoaEleita | null;
  coligacao: { nome: string; partidos: string[] }; candidatos: Candidato[];
}
export interface Legislatura {
  eleicao: number; inicio: number; fim: number; vagas: number;
  por_partido: { partido: string; partido_hoje: string; cadeiras: number; do_prefeito: boolean; da_coligacao: boolean }[];
  eleitos: { nome: string; partido: string; votos: number }[]; do_partido_do_prefeito: number; da_coligacao_do_prefeito: number;
}
export interface EleicaoGeral { eleicao: number; cargos: { cargo: string; turno: number; total_votos: number; n_candidatos: number; candidatos: Candidato[] }[] }
export interface Cidade {
  id: string; nome: string; uf: string; links: { nome: string; url: string }[];
  executivo: MandatoPrefeito[]; camara: Legislatura[]; gerais: EleicaoGeral[]; avisos: string[];
  resumo: { anos_por_partido: { partido: string; anos: number; siglas: string[] }[]; cadeiras_por_partido: { partido: string; cadeiras: number }[];
    mandatos: number; camaras: number; coligacao_do_prefeito_com_maioria: number };
}
export interface CidadeResumo { id: string; nome: string; uf: string; prefeito: PessoaEleita | null; desde: number | null; vereadores: number | null }

/* Verificação independente (etl/sa_etl/verificar.py, arquivo verificacao.json) */
export type StatusVerificacao = "conferido" | "parcial" | "divergente" | "nao_conferido" | "sem_segunda_fonte";
export interface ItemVerificado { o_que: string; site: number | string; oficial: number | string; fonte: string }
export interface Checagem {
  id: string; secao: string; titulo: string; como: string; fonte: string; status: "conferido" | "divergente" | "nao_conferido";
  conferidos: number; divergentes: number; nao_conferidos: number; completados?: number; motivo: string;
  divergencias: ItemVerificado[]; exemplos: ItemVerificado[];
}
export interface SecaoVerificada {
  titulo: string; status: StatusVerificacao; checagens: string[]; motivo?: string;
  hoje: { conferidos: number; divergentes: number };
  acumulado: { conferidos: number; divergentes: number; desde: string | null; dias: number; certos_min: number | null };
}
export interface Verificacao {
  gerado_em: string; data: string; confianca: number; dias_mes_fechado: number; dias_historico: number; para_99_99: number;
  secoes: Record<string, SecaoVerificada>; checagens: Checagem[];
}

export interface Meta {
  /** Problemas da última coleta (fonte oficial fora do ar, cópia antiga em uso...), para avisar quem lê */
  avisos?: string[];
  atualizado_em: string; anos: number[]; grupos: Record<Grupo, string>; medias: Record<string, Record<Casa, number>>;
  contagens: { politicos: number; despesas: number; votacoes: number; empresas_com_socios: number }; total_gasto: number;
  total_por_ano: Record<string, number>; custo_por_ano: Record<string, number>;
  /** Minas Nossa: "MG" e as cidades acompanhadas */
  recorte?: string; cidades?: string[];
  estado?: { deputados_estaduais: number; emendas_estaduais: number; governo: number; equipe_governo: number };
}

/** Só links http(s). Um link "javascript:" ou "data:" vindo de dados adulterados vira undefined, e o React não põe o href. */
export function linkSeguro(url?: string | null): string | undefined {
  const u = (url || "").trim();
  return /^https?:\/\/[^\s<>"']+$/i.test(u) ? u : undefined;
}

const cache = new Map<string, Promise<unknown>>();
export function load<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(path, fetch(`./data/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Não encontrado: ${path}`);
      return r.json().catch(() => { throw new Error(`Arquivo com defeito: ${path}`); });
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

/** "PMDB (hoje MDB)". Partidos que mudaram de nome ou se juntaram a outro aparecem com o nome de hoje ao lado. */
export function partidoComHoje(partido: string, hoje?: string | null): string {
  const k = (x: string) => x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/[^A-Z]/g, "");
  return hoje && k(hoje) !== k(partido) ? `${partido} (hoje ${hoje})` : partido;
}
export const numero = (n: number) => (n || 0).toLocaleString("pt-BR");

/* Minas Nossa: deputados estaduais (ALMG) */
export interface AlmgAno { verba: number; projetos: number; requerimentos: number; aprovadas: number; emendas_indicado: number; emendas_pago: number }
export interface DeputadoEstadualResumo { id: string; nome: string; partido: string; url: string; url_verba?: string; por_ano: Record<string, AlmgAno> }
export interface AlmgIndice { anos: string[]; medianas: Record<string, AlmgAno>; deputados: DeputadoEstadualResumo[]; fontes: { verba: string; dados: string };
  verba_completa?: Record<string, boolean> }
export interface VerbaAno {
  total: number; tipos: { tipo: string; valor: number }[]; meses: { mes: number; valor: number }[]; meses_faltando?: number[];
  fornecedores: { nome: string; cnpj: string; pf: boolean; valor: number; n: number }[]; n_fornecedores: number; n_notas: number;
  notas: { data: string; mes: number; fornecedor: string; cnpj: string; pf: boolean; tipo: string; valor: number }[];
}
export interface ProposicaoAlmg { sigla: string; numero: string; ano: number; ementa: string; situacao: string; aprovada: boolean; data: string; url: string }
export interface EmendasDeputado {
  indicado: number; pago: number; n: number; n_municipios: number;
  municipios: { nome: string; indicado: number; pago: number; n: number }[];
  beneficiarios: { nome: string; municipio: string; indicado: number; pago: number; n: number; descricao: string; area: string }[];
}
export interface DeputadoEstadual extends DeputadoEstadualResumo {
  anos: Record<string, { verba: VerbaAno | null; proposicoes: { projetos: number; requerimentos: number; outras: number; coautor: number; aprovadas: number; lista: ProposicaoAlmg[] } | null; emendas: EmendasDeputado | null }>;
}
export interface EmendasEstado {
  fonte: string;
  anos: Record<string, { indicado: number; pago: number; n: number; n_municipios: number; municipios: { nome: string; indicado: number; pago: number; n: number }[];
    autores: { nome: string; deputado: string | null; indicado: number; pago: number; n: number }[] }>;
}
/* Minas Nossa: governo do estado */
export interface PessoaGoverno { nome: string; partido: string; partido_hoje: string; mudou: string | null }
export interface Governo {
  eleicoes: { eleicao: number; inicio: number; fim: number; turnos: number; governador: PessoaGoverno & { votos: number; pct: number }; vice: PessoaGoverno | null;
    candidatos: { nome: string; partido: string; votos: number; pct: number; eleito: boolean }[] }[];
  links: { nome: string; url: string; explica: string }[]; fonte_tse: string;
  equipe?: EquipeGoverno | null;
}
export interface ViagensPessoa {
  nome: string; cargo: string; anos: { ano: number; viagens: number; diarias: number; passagens: number }[];
  destinos: { nome: string; vezes: number }[];
  ultimas: { inicio: string; fim: string; destinos: string[]; valor: number; motivo: string }[];
}
export interface PessoaEquipe {
  nome: string; cargo: string; orgao: string; bruto: number; abate_teto: number; ferias_13: number; eventual: number; jetons: number;
  descontos: number; liquido: number; viagens: ViagensPessoa | null;
}
export interface EquipeGoverno {
  mes_salarios: string | null; pessoas: PessoaEquipe[]; tem_salarios: boolean; tem_viagens: boolean;
  fontes: { salarios: string; viagens: string; portal_salarios: string; portal_viagens: string };
}
/* Minas Nossa: dinheiro que chega à cidade e onde a prefeitura gasta */
export interface EmendaEstadualCidade { ano: number; autor: string; deputado: string | null; beneficiario: string; tipo_beneficiario: string; descricao: string; area: string; orgao: string; indicado: number; pago: number; situacao: string }
export interface DinheiroCidade {
  id: string; nome: string;
  estaduais: { fonte: string; lista: EmendaEstadualCidade[] | null } | null;
  federais: { fonte: string; por_ano: { ano: number; valor: number; n: number }[];
    favorecidos: { nome: string; cnpj: string; valor: number; anos: number[]; url: string; autores: { nome: string; valor: number }[] }[];
    autores: { nome: string; politico: string | null; partido: string; valor: number; n: number }[] } | null;
  contas: { cod_ibge: number; fonte: string; api: string; anos: { ano: number; instituicao: string; total_empenhado: number; total_liquidado: number; total_pago: number;
    funcoes: { codigo: string; funcao: string; empenhado: number; liquidado: number; pago: number; principais: { nome: string; valor: number }[] }[] }[] } | null;
}

/** Cota que a empresa recebeu no ano escolhido. Sem o detalhe por ano (dados antigos), devolve null e a tela usa o total. */
export function cotaNoAno(e: { por_ano?: Record<string, { valor: number; n_politicos: number }> }, ano: string): { valor: number; n_politicos: number } | null {
  if (!e.por_ano) return null;
  return e.por_ano[ano] || { valor: 0, n_politicos: 0 };
}

/* Projetos em andamento (tramitacao.json, gerado por etl/sa_etl/tramitacao.py; almg/tramitacao.json no Minas Nossa) */
export interface AutorProjeto { nome: string; partido: string; uf: string; id: string }
export interface PautaProjeto { data: string; onde: string; url: string; urgencia: boolean; regime: string; relator: string; parecer?: string; terminativo?: boolean }
export type GrupoProjeto = "pauta" | "mpv" | "nova" | "andamento";
export interface Projeto {
  id: string; casa: Casa | "almg"; sigla: string; numero: string; ano: string; nome: string;
  ementa: string; resumo?: string; resumo_oficial?: string; o_que_e?: string;
  apresentada: string; atualizada: string; autores: AutorProjeto[]; n_autores: number;
  situacao: string; fase?: string; onde: string; regime?: string; etapa: number; etapa_nome?: string;
  url: string; texto?: string; passos?: { data: string; onde: string; texto: string }[];
  pauta?: PautaProjeto[]; grupos: GrupoProjeto[]; temas?: string[]; proximo?: string;
  prazo?: string; tranca_pauta?: string; suspenso?: boolean; veio_da_camara?: boolean; do_estado?: boolean;
}
export interface Tramitacao {
  atualizado_em: string; dias_pauta: number; dias_novas: number; etapas: string[]; o_que_e: Record<string, string>;
  situacao_fontes: Record<string, string>; itens: Projeto[];
  agenda: { id: string; casa: Casa; data: string; onde: string; tipo: string; situacao: string; url: string; itens: string[] }[];
}
export interface TramitacaoAlmg { atualizado_em: string; dias_andamento: number; dias_novas: number; itens: Projeto[]; fonte: string }

const DIAS_SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
/** "2026-10-28T14:00" -> "quarta, 28/10, às 14h00" */
export function dataHoraBR(s: string): string {
  const [d, h] = (s || "").split("T");
  const p = (d || "").split("-").map(Number);
  if (p.length !== 3 || p.some(isNaN)) return s || "";
  const dia = new Date(p[0], p[1] - 1, p[2]);
  const txt = `${DIAS_SEMANA[dia.getDay()]}, ${String(p[2]).padStart(2, "0")}/${String(p[1]).padStart(2, "0")}`;
  const hora = (h || "").slice(0, 5);
  return hora && hora !== "00:00" ? `${txt}, às ${hora.replace(":", "h")}` : txt;
}
/** Partido e estado do autor, como "(PT-SP)". */
export function autorSigla(a: AutorProjeto): string {
  const x = [a.partido, a.uf].filter(Boolean).join("-");
  return x ? ` (${x})` : "";
}
