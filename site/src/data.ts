// Tipos e funções para ler os arquivos JSON gerados pelo coletor (etl/).
export type Casa = "camara" | "senado";
export type Grupo = "pessoal" | "escritorio" | "servicos";

/* Valores de um ano. "total" é a cota (reembolsos com nota fiscal). O resto vem das páginas oficiais. */
export interface AnoResumo {
  total: number; grupos: Record<Grupo, number>;
  salario: number | null; verba_gabinete: number | null; outros_gastos: number | null;
  cota_oficial: number | null; n_pessoal: number | null; custo_total: number;
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
  n_pessoal?: number; salario_bruto?: number; salario_ano?: number | null; salario_meses?: { mes: number; valor: number }[];
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
  recursos: Recursos | null;
}
export interface Fornecedor { doc: string; tipo: string; nome: string; valor: number; n: number; ficha: boolean; socios: string[] }
export interface Nota { data: string; categoria: string; fornecedor: string; doc: string; valor: number; url: string }
export interface Politico extends Resumo {
  anos: Record<string, AnoDetalhe>;
  votos: { votacao: string; voto: string; partido: string }[];
}
export interface Proposicao { sigla: string; numero: string; ano: string; ementa: string; titulo: string; url: string }
export interface VotacaoResumo { id: string; casa: Casa; data: string; descricao: string; aprovada: boolean; proposicao: Proposicao | null; sim: number; nao: number }
export interface Votacao extends VotacaoResumo {
  orientacoes: Record<string, string>; fonte: string; contagem: Record<string, number>;
  por_partido: Record<string, Record<string, number>>; por_lado: Record<string, Record<string, number>>;
  votos: { politico: string; nome: string; partido: string; uf: string; voto: string; posicao: number | null }[];
}
export interface Socio { nome: string; doc: string; qualificacao: string; entrada: string; faixa_etaria: string; outras_empresas: { cnpj: string; nome: string; total: number }[] }
export interface EmpresaResumo { cnpj: string; nome: string; total: number; n_politicos: number; tem_socios: boolean; n_mesmo_endereco?: number }
export interface Empresa extends EmpresaResumo {
  empresa: null | { razao_social: string; nome_fantasia: string; situacao: string; abertura: string; atividade: string; municipio: string; uf: string; capital_social: number; porte: string; natureza: string;
    endereco?: { logradouro: string; numero: string; complemento: string; bairro: string; cep: string } };
  socios: Socio[]; mesmo_endereco?: { cnpj: string; nome: string; total: number; mesmos_socios: boolean }[]; pagadores: { politico: string; nome: string; partido: string; uf: string; valor: number }[]; alertas: string[];
}
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
export function proposicaoNome(p: Proposicao | null): string {
  if (!p) return "";
  if (p.sigla && p.numero) return `${p.sigla} ${p.numero}/${p.ano}`;
  return p.titulo || "";
}
