/* Menu dos sites, organizado por tarefa. Antes eram 11 abas no Brasil e 13 no Minas Nossa, todas no mesmo nível:
   muita coisa para ler antes de achar o que se quer (sobrecarga cognitiva). Agora o menu tem poucas seções, cada
   uma com uma pergunta clara, e as páginas de cada seção aparecem como abas só quando a pessoa entra nela
   (divulgação progressiva). Nenhuma página saiu do site: só mudou de lugar.
   Seção com uma página só não mostra abas. */
import { MG } from "./recorte";

export interface Pagina { rota: string; nome: string; /** a rota vale também para os endereços que começam com estes */ prefixos?: string[]; exata?: boolean }
export interface Secao { id: string; nome: string; pergunta: string; paginas: Pagina[] }

const BRASIL: Secao[] = [
  {
    id: "politicos", nome: "Políticos", pergunta: "Quem são e quanto gastam",
    paginas: [
      { rota: "/quem", nome: "Quem me representa" },
      { rota: "/politicos", nome: "Deputados e senadores", prefixos: ["/p/", "/gabinetes", "/historico", "/patrimonio"] },
      { rota: "/partidos", nome: "Partidos" },
    ],
  },
  {
    id: "votacoes", nome: "Votações", pergunta: "Como cada um votou",
    paginas: [
      { rota: "/votacoes", nome: "Em andamento", exata: true },
      { rota: "/votacoes/ja-votadas", nome: "Já votadas", prefixos: ["/v/"] },
      { rota: "/votacoes/tribunais", nome: "Julgamentos do STF" },
    ],
  },
  {
    id: "dinheiro", nome: "Dinheiro", pergunta: "De onde vem e para onde vai",
    paginas: [
      { rota: "/dinheiro", nome: "Arrecadação e gastos" },
      { rota: "/emendas", nome: "Emendas" },
      { rota: "/incentivos", nome: "Incentivos" },
      { rota: "/empresas", nome: "Empresas", prefixos: ["/e/"] },
    ],
  },
  {
    id: "investigar", nome: "Investigar", pergunta: "Casos, punições e ligações",
    paginas: [
      { rota: "/corrupcao", nome: "Corrupção", prefixos: ["/corrupcao/"] },
      { rota: "/rede", nome: "Minha rede" },
    ],
  },
  {
    id: "sobre", nome: "Como funciona", pergunta: "De onde vêm os números",
    paginas: [
      { rota: "/sobre", nome: "Como funciona" },
      { rota: "/verificacao", nome: "Como conferimos" },
    ],
  },
];

const MINAS: Secao[] = [
  {
    id: "politicos", nome: "Políticos", pergunta: "Quem são e quanto gastam",
    paginas: [
      { rota: "/quem", nome: "Quem me representa" },
      { rota: "/governo", nome: "Governo" },
      { rota: "/assembleia", nome: "Deputados estaduais", prefixos: ["/deputado-estadual/"] },
      { rota: "/politicos", nome: "Federais", prefixos: ["/p/"] },
      { rota: "/partidos", nome: "Partidos" },
    ],
  },
  {
    id: "votacoes", nome: "Votações", pergunta: "Como cada um votou",
    paginas: [
      { rota: "/votacoes", nome: "Em andamento", exata: true },
      { rota: "/votacoes/ja-votadas", nome: "Já votadas", prefixos: ["/v/"] },
    ],
  },
  {
    id: "dinheiro", nome: "Dinheiro", pergunta: "De onde vem e para onde vai",
    paginas: [
      { rota: "/dinheiro", nome: "Estado" },
      { rota: "/cidades", nome: "Cidades", prefixos: ["/cidade/"] },
      { rota: "/emendas-estaduais", nome: "Emendas" },
      { rota: "/licitacoes", nome: "Licitações" },
      { rota: "/cultura", nome: "Shows e cultura" },
      { rota: "/painel", nome: "Por área" },
      { rota: "/empresas", nome: "Empresas", prefixos: ["/e/"] },
    ],
  },
  {
    id: "investigar", nome: "Investigar", pergunta: "Ligações entre políticos e empresas",
    paginas: [{ rota: "/rede", nome: "Minha rede" }],
  },
  {
    id: "sobre", nome: "Como funciona", pergunta: "De onde vêm os números",
    paginas: [{ rota: "/sobre", nome: "Como funciona" }],
  },
];

export const SECOES: Secao[] = MG ? MINAS : BRASIL;

/** A página do menu que corresponde ao endereço aberto (a mais específica ganha). */
export function paginaDe(pathname: string): { secao: Secao; pagina: Pagina } | null {
  let achou: { secao: Secao; pagina: Pagina; tam: number } | null = null;
  for (const secao of SECOES) {
    for (const pagina of secao.paginas) {
      const alvos = [pagina.rota, ...(pagina.prefixos || [])];
      for (const alvo of alvos) {
        const bate = pagina.exata && alvo === pagina.rota ? pathname === alvo
          : pathname === alvo || pathname.startsWith(alvo.endsWith("/") ? alvo : `${alvo}/`) || (alvo.endsWith("/") && pathname.startsWith(alvo));
        if (bate && (!achou || alvo.length > achou.tam)) achou = { secao, pagina, tam: alvo.length };
      }
    }
  }
  return achou && { secao: achou.secao, pagina: achou.pagina };
}
