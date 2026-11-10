/* Confiança em cada número do perfil: média da Casa ao lado, o que a fonte publica e o que falta, e o link para
   avisar um erro. Funções puras (testadas em tests/unidade.test.ts); os componentes ficam em components/Confianca.tsx. */
import { MESES_LONGOS, reais, type AnoDetalhe, type Casa, type Politico } from "./data.ts";

/** Uma média da Casa e quantos políticos entraram na conta (etl/sa_etl/medias.py) */
export interface MediaCasa { media: number; n: number }
export interface MediasCasaAno {
  /** Meses do período: 12 nos anos fechados; no ano em andamento, até o último mês fechado com nota */
  meses: number;
  total?: MediaCasa; custo_total?: MediaCasa; verba_gabinete?: MediaCasa; n_pessoal?: MediaCasa; presenca_plenario?: MediaCasa;
}
export interface MediasCasa {
  /** Quantos meses sem nota ainda contam como "período inteiro" */
  folga_meses: number;
  anos: Record<string, Partial<Record<Casa, MediasCasaAno>>>;
  votos: Partial<Record<Casa, { min_votos: number; fidelidade_partido?: MediaCasa; alinhamento_governo?: MediaCasa }>>;
}

export const REPOSITORIO = "https://github.com/amarigo/segredos-abertos";

export const nomeCasa = (c: Casa) => (c === "camara" ? "da Câmara" : "do Senado");
export const quemCasa = (c: Casa, n = 2) => (c === "camara" ? (n === 1 ? "deputado" : "deputados") : (n === 1 ? "senador" : "senadores"));

/** "de 2025" ou "de janeiro a outubro de 2026" */
export function periodoNome(ano: string, meses: number): string {
  return meses >= 12 ? `de ${ano}` : meses === 1 ? `de janeiro de ${ano}` : `de janeiro a ${MESES_LONGOS[meses - 1]} de ${ano}`;
}

/** Ficou o período inteiro? Mesma regra da coleta (medias.periodo_inteiro). */
export function periodoInteiro(meses: number | undefined, periodo: number, folga: number): boolean {
  return (meses || 0) >= Math.max(periodo - folga, 1);
}

export interface Referencia {
  /** O valor com que comparar: a média, ou a média proporcional aos meses do político */
  valor: number;
  /** Rótulo curto: "Média da Câmara" ou "Média da Câmara para 5 meses" */
  rotulo: string;
  /** De quem é a média, com o critério exato */
  criterio: string;
  proporcional: boolean;
}

/** Média de dinheiro (cota, custo, verba): de quem ficou o período inteiro. Quem ficou menos é comparado com a
 *  média proporcional aos meses em que teve nota da cota. */
export function referenciaDinheiro(m: MediaCasa, casa: Casa, ano: string, periodo: number, folga: number, mesesPolitico?: number): Referencia {
  const minimo = Math.max(periodo - folga, 1);
  const quantos = minimo === periodo ? `em todos os ${periodo} meses` : `em ${minimo} ou mais dos ${periodo} meses`;
  const base = `${m.n.toLocaleString("pt-BR")} ${quemCasa(casa, m.n)} com nota da cota ${quantos} ${periodoNome(ano, periodo)}`;
  if (mesesPolitico != null && mesesPolitico > 0 && !periodoInteiro(mesesPolitico, periodo, folga)) {
    return {
      valor: (m.media / periodo) * mesesPolitico, proporcional: true,
      rotulo: `Média ${nomeCasa(casa)} para ${mesesPolitico} ${mesesPolitico === 1 ? "mês" : "meses"}`,
      criterio: `Teve nota da cota em ${mesesPolitico} dos ${periodo} meses; a média é a de ${base}, dividida por ${periodo} e multiplicada por ${mesesPolitico}.`,
    };
  }
  return { valor: m.media, proporcional: false, rotulo: `Média ${nomeCasa(casa)}`, criterio: `Média de ${base}.` };
}

/** Taxa (presença, voto com o partido): média de todos que têm a taxa */
export function referenciaTaxa(m: MediaCasa, casa: Casa, quemTem: string): Referencia {
  return { valor: m.media, proporcional: false, rotulo: `Média ${nomeCasa(casa)}`,
    criterio: `Média de ${m.n.toLocaleString("pt-BR")} ${quemCasa(casa, m.n)} ${quemTem}.` };
}

/** "1,5× a média", "20% abaixo da média" ou "Na média" */
export function comparacao(valor: number, ref: number): string {
  if (!ref) return "";
  const vezes = valor / ref;
  return vezes >= 1.05 ? `${vezes.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}× a média`
    : vezes <= 0.95 ? `${Math.round((1 - vezes) * 100)}% abaixo da média` : "Na média";
}

/** Diferença em pontos percentuais entre duas taxas: "3 pontos acima da média" */
export function comparacaoPontos(taxa: number, ref: number): string {
  const d = Math.round((taxa - ref) * 100);
  return d === 0 ? "Na média" : `${Math.abs(d)} ${Math.abs(d) === 1 ? "ponto" : "pontos"} ${d > 0 ? "acima" : "abaixo"} da média`;
}

/* ------------------------------------------------------------------ o que está aqui e o que falta */

/** tem: está no site como a fonte publica; completado: a fonte aberta não traz, completamos com outra fonte oficial;
 *  fonte_nao_publica: nenhuma fonte oficial publica em formato aberto; ainda_nao: a fonte publica, ainda não trazemos. */
export type EstadoCobertura = "tem" | "completado" | "fonte_nao_publica" | "ainda_nao";
export interface ItemCobertura { estado: EstadoCobertura; titulo: string; texto: string; link?: string; linkTexto?: string }

export const ESTADO_COBERTURA: Record<EstadoCobertura, { icone: string; nome: string }> = {
  tem: { icone: "✓", nome: "Está aqui" },
  completado: { icone: "◐", nome: "Completado com outra fonte oficial" },
  fonte_nao_publica: { icone: "○", nome: "A fonte oficial não publica" },
  ainda_nao: { icone: "○", nome: "Ainda não trazemos" },
};

const DADOS_ABERTOS_SENADO = "https://legis.senado.leg.br/dadosabertos/";
const TSE_CANDIDATURAS = "https://divulgacandcontas.tse.jus.br/";

/** O que este perfil mostra no ano escolhido, o que completamos e o que falta, a partir dos próprios dados do político */
export function oQueFalta(p: Politico, ano: string, d: AnoDetalhe | undefined): ItemCobertura[] {
  const itens: ItemCobertura[] = [];
  const camara = p.casa === "camara";
  const r = d?.recursos || {};
  const fonte = p.fonte || undefined;
  // Senado: a lista oficial de despesas do senador é o link que cada nota já traz
  const despesasSenado = d?.maiores_notas?.find((n) => n.url)?.url || fonte;
  if (d) {
    if (d.n_notas) {
      itens.push({ estado: "tem", titulo: "Notas fiscais da cota", link: fonte, linkTexto: "página oficial",
        texto: camara ? `As ${d.n_notas.toLocaleString("pt-BR")} notas de ${ano}, cada uma com o link para a imagem da nota no site da Câmara.`
          : `As ${d.n_notas.toLocaleString("pt-BR")} notas de ${ano}, com o tipo de despesa e o fornecedor.` });
    } else if (d.n_notas === undefined) {
      itens.push({ estado: "ainda_nao", titulo: "Lista completa de notas", texto: `Para ${ano} mostramos só as maiores notas; a lista completa existe na fonte oficial.`, link: fonte, linkTexto: "página oficial" });
    }
    if (!camara) {
      itens.push({ estado: "fonte_nao_publica", titulo: "Imagem das notas fiscais", link: despesasSenado, linkTexto: "despesas do senador no Senado",
        texto: "O Senado não publica a imagem das notas; o link de cada nota abre a lista oficial de despesas do senador." });
    }
    const pl = d.passagens_da_lista;
    if (pl && pl.n > 0) {
      itens.push({ estado: "completado", titulo: "Passagens aéreas compradas pela Câmara", link: fonte, linkTexto: "página oficial",
        texto: `Desde agosto de 2025 o arquivo de dados abertos não traz essas passagens. Buscamos ${pl.n.toLocaleString("pt-BR")} bilhetes (${reais(pl.valor)}) na lista oficial de despesas do deputado.` });
    }
    const sem = (d.sem_nota_meses || []).reduce((s, x) => s + x.valor, 0);
    if (sem) {
      itens.push({ estado: "fonte_nao_publica", titulo: "Despesas sem nota publicada", link: fonte, linkTexto: "página oficial",
        texto: `${reais(sem)} que a página oficial soma em ${ano} e que não aparecem em nenhuma nota nem na lista de despesas. Entram no total para ele ficar igual ao oficial.` });
    }
    if (camara) {
      itens.push(r.salario_meses?.length
        ? { estado: "tem", titulo: "Salário", texto: `O que a Câmara diz que pagou em cada mês de ${ano}, antes dos descontos.`, link: fonte, linkTexto: "página oficial" }
        : { estado: "ainda_nao", titulo: "Salário", texto: `Ainda sem o salário mês a mês de ${ano}.`, link: fonte, linkTexto: "página oficial" });
      itens.push(r.verba_gasto != null
        ? { estado: "tem", titulo: "Verba de gabinete", texto: "O total gasto com a equipe em cada mês." }
        : { estado: "ainda_nao", titulo: "Verba de gabinete", texto: `Ainda sem o gasto com a equipe em ${ano}.`, link: fonte, linkTexto: "página oficial" });
      itens.push({ estado: "ainda_nao", titulo: "Salário de cada pessoa da equipe",
        texto: "Mostramos quem trabalhou no gabinete e o cargo, mas ainda não quanto cada pessoa recebeu; a página do deputado mostra só o total da verba." });
    } else {
      if (r.salario_estimado) {
        itens.push({ estado: "completado", titulo: "Salário", link: DADOS_ABERTOS_SENADO, linkTexto: "dados abertos do Senado",
          texto: "O Senado não publica o salário junto dos gastos do senador. Usamos o subsídio pago aos deputados, que é o mesmo valor." });
      }
      if (r.beneficios?.length) {
        itens.push({ estado: "fonte_nao_publica", titulo: "Valor dos benefícios", link: fonte, linkTexto: "página oficial",
          texto: `O Senado informa se o senador usou cada benefício (${r.beneficios.map((b) => b.beneficio.toLowerCase()).join(", ")}), mas não quanto custou.` });
      }
    }
  }
  const at = p.por_ano[ano]?.atuacao;
  if (camara) {
    if (at?.plenario) itens.push({ estado: "tem", titulo: "Presença no Plenário e nas comissões", texto: "Os números da página oficial do deputado, com ausências justificadas e sem justificativa.", link: fonte, linkTexto: "página oficial" });
  } else {
    if (at?.plenario) itens.push({ estado: "tem", titulo: "Presença no Plenário", texto: "Contada pelas votações nominais: em cada uma o Senado registra se o senador votou, se estava em missão ou licença, ou se faltou.", link: DADOS_ABERTOS_SENADO, linkTexto: "dados abertos do Senado" });
    itens.push({ estado: "fonte_nao_publica", titulo: "Presença nas comissões", texto: "O Senado não publica a presença de cada senador nas comissões nos dados abertos.", link: DADOS_ABERTOS_SENADO, linkTexto: "dados abertos do Senado" });
  }
  if (p.n_votos) {
    itens.push({ estado: "tem", titulo: "Votos no Plenário", texto: `${p.n_votos.toLocaleString("pt-BR")} votações nominais no Plenário desde o início do mandato (todos os anos), em que cada voto fica registrado com o nome.` });
  }
  itens.push({ estado: "fonte_nao_publica", titulo: "Votações simbólicas", texto: "Quando a votação é simbólica, a Casa registra só o resultado, não o voto de cada um." });
  if (camara) {
    itens.push({ estado: "ainda_nao", titulo: "Votos nas comissões", texto: "Ficam fora de propósito, para não somar votos de comissão (como a CCJ) com os do Plenário. Ainda não mostramos à parte." });
  }
  itens.push({ estado: "ainda_nao", titulo: "Patrimônio declarado e contas de campanha", link: TSE_CANDIDATURAS, linkTexto: "divulgação de candidaturas do TSE",
    texto: "O TSE publica; ainda não trazemos para o perfil." });
  return itens;
}

/* ------------------------------------------------------------------ avisar um erro, sem servidor */

/** Link para abrir um aviso público no GitHub, com o formulário já preenchido (.github/ISSUE_TEMPLATE/).
 *  tipo "resposta": direito de resposta do político ou da equipe dele. */
export function linkAvisarErro(pagina: string, assunto: string, tipo: "erro" | "resposta" = "erro"): string {
  const q = new URLSearchParams({
    template: tipo === "erro" ? "erro-nos-dados.yml" : "direito-de-resposta.yml",
    title: `${tipo === "erro" ? "Erro nos dados" : "Direito de resposta"}: ${assunto}`.slice(0, 200),
    pagina: pagina.slice(0, 500),
  });
  return `${REPOSITORIO}/issues/new?${q.toString()}`;
}
