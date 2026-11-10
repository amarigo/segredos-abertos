/* Cartão para compartilhar: uma imagem com os números de um político, pronta para o Instagram (feed e stories),
 * WhatsApp e redes que mostram a prévia do link.
 *
 * O mesmo código desenha o cartão em dois lugares:
 *   - no app (botão "Compartilhar" do perfil), no navegador de quem lê;
 *   - na publicação (scripts/cartoes.mjs), uma imagem por político, usada como prévia (og:image) da página estática.
 * Por isso este arquivo não importa nada: os tipos abaixo são só o pedaço de politicos.json e meta.json que ele usa.
 * Nada é calculado além do que a página do político já mostra: os números são os dos arquivos de dados, e a imagem
 * leva a fonte oficial e a data da atualização no rodapé (regra 3 do projeto).
 */

export type Formato = "link" | "feed" | "stories";
/** Tamanhos em pixels: prévia de link (1,91:1), feed do Instagram (4:5) e stories (9:16) */
export const TAMANHO: Record<Formato, [number, number]> = { link: [1200, 630], feed: [1080, 1350], stories: [1080, 1920] };

interface AnoCartao { total: number; custo_total?: number | null }
export interface PoliticoCartao {
  id: string; casa: "camara" | "senado"; cargo: string; nome: string; partido: string; uf: string;
  por_ano: Record<string, AnoCartao>; posicao: number | null; rotulo: string;
  alinhamento_governo: number | null; fidelidade_partido: number | null; n_votos: number; em_exercicio?: boolean;
}
export interface MetaCartao { atualizado_em: string; anos: number[]; medias: Record<string, Partial<Record<"camara" | "senado", number>>> }

export interface DadosCartao {
  site: string; endereco: string; cargo: string; nome: string; partidoUf: string; ano: string;
  cota: number; comparacao: string; linhas: [string, string][]; nota: string; fonte: string; atualizado: string;
}

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const reais = (v: number) => brl.format(v || 0).replace(/ /g, " ");
const pct = (v: number) => `${Math.round(v * 100)}%`;
const dataBR = (s: string) => s.slice(0, 10).split("-").reverse().join("/");

/** Endereço da página estática de um político (o mesmo que scripts/paginas-estaticas.mjs grava) */
export const slug = (s: string) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
export const paginaPolitico = (p: { nome: string; id: string }) => `politico/${slug(p.nome)}-${p.id}.html`;
/** Onde a publicação grava a imagem de prévia de cada político */
export const imagemPolitico = (id: string) => `cartao/${id}.jpg`;

/** Junta os números do cartão. Sem gasto no ano, devolve null (não há cartão para mostrar). */
export function dadosCartao(p: PoliticoCartao, meta: MetaCartao, opcoes: { ano?: string; site: string; endereco: string }): DadosCartao | null {
  const ano = opcoes.ano || String(meta.anos[meta.anos.length - 1]);
  const a = p.por_ano?.[ano];
  if (!a || !(a.total > 0)) return null;
  const camara = p.casa === "camara";
  // Mesma regra do perfil no app (Politico.tsx): média da Casa no mesmo ano, de quem teve gasto
  const media = meta.medias?.[ano]?.[p.casa] || 0;
  const vezes = media ? a.total / media : 0;
  const quem = camara ? "dos deputados" : "dos senadores";
  const comparacao = !media ? "" : vezes >= 1.05
    ? `${vezes.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}× a média ${quem} (${reais(media)})`
    : vezes <= 0.95 ? `${Math.round((1 - vezes) * 100)}% abaixo da média ${quem} (${reais(media)})` : `Na média ${quem} (${reais(media)})`;
  const linhas: [string, string][] = [];
  if (a.custo_total && a.custo_total > a.total) linhas.push([`Custo conhecido do mandato em ${ano}`, reais(a.custo_total)]);
  if (p.posicao != null && p.rotulo) linhas.push(["Posição pelos votos", p.rotulo]);
  if (p.alinhamento_governo != null) linhas.push(["Vota com o governo", pct(p.alinhamento_governo)]);
  if (p.fidelidade_partido != null) linhas.push(["Vota com o próprio partido", pct(p.fidelidade_partido)]);
  const atual = ano === String(new Date(meta.atualizado_em).getFullYear());
  const notas = [
    atual ? `${ano} até ${dataBR(meta.atualizado_em)}.` : "",
    a.custo_total && a.custo_total > a.total ? "Custo: salário, equipe, cota e outros gastos informados pela Casa." : "",
    p.n_votos ? `Votos: ${p.n_votos.toLocaleString("pt-BR")} votações nominais de ${meta.anos[0]} a ${meta.anos[meta.anos.length - 1]}.` : "",
  ];
  return {
    site: opcoes.site, endereco: opcoes.endereco.replace(/^https?:\/\//, "").replace(/\/$/, ""),
    cargo: p.cargo, nome: p.nome, partidoUf: `${p.partido}-${p.uf}`, ano, cota: a.total, comparacao, linhas,
    nota: notas.filter(Boolean).join(" "),
    fonte: camara ? "Câmara dos Deputados (dados abertos e página do deputado)" : "Senado Federal (dados abertos)",
    atualizado: dataBR(meta.atualizado_em),
  };
}

/* ---------- Desenho ---------- */
const COR = { navy: "#071d41", verde: "#168821", amarelo: "#ffcd07", azul: "#1351b4", tinta: "#1b2533", cinza: "#5f6a7a", linha: "#dcdfe5", fundo: "#ffffff", eyebrow: "#137a1d" };

type Ctx = CanvasRenderingContext2D;
const fonteDe = (peso: number, px: number, familia: string) => `${peso} ${px}px ${familia}, "Segoe UI", Arial, sans-serif`;

/** Quebra o texto em linhas que cabem na largura */
function quebrar(ctx: Ctx, texto: string, largura: number): string[] {
  const linhas: string[] = [];
  let atual = "";
  for (const palavra of texto.split(/\s+/).filter(Boolean)) {
    const tentativa = atual ? `${atual} ${palavra}` : palavra;
    if (ctx.measureText(tentativa).width <= largura || !atual) atual = tentativa;
    else { linhas.push(atual); atual = palavra; }
  }
  if (atual) linhas.push(atual);
  return linhas;
}

/** Escreve o texto quebrado em até maxLinhas, diminuindo a letra até caber. Devolve o y depois do bloco. */
function bloco(ctx: Ctx, texto: string, x: number, y: number, largura: number, o: { peso: number; px: number; min: number; maxLinhas: number; cor: string; familia: string; entre?: number }): number {
  let px = o.px;
  let linhas: string[] = [];
  for (; px >= o.min; px -= 2) {
    ctx.font = fonteDe(o.peso, px, o.familia);
    linhas = quebrar(ctx, texto, largura);
    if (linhas.length <= o.maxLinhas && linhas.every((l) => ctx.measureText(l).width <= largura)) break;
  }
  px = Math.max(px, o.min);
  ctx.font = fonteDe(o.peso, px, o.familia);
  ctx.fillStyle = o.cor;
  ctx.textBaseline = "alphabetic";
  const altura = px * (o.entre ?? 1.15);
  if (linhas.length > o.maxLinhas) {
    linhas = linhas.slice(0, o.maxLinhas);
    linhas[o.maxLinhas - 1] = linhas[o.maxLinhas - 1].replace(/\s*\S*$/, "") + "…";
  }
  linhas.forEach((l, i) => ctx.fillText(l, x, y + px + i * altura));
  return y + px + (linhas.length - 1) * altura + px * 0.35;
}

/** Desenha o cartão inteiro. O canvas precisa ter o tamanho de TAMANHO[formato].
 *  Devolve quantas linhas de números ficaram de fora por falta de espaço (0 quando cabe tudo). */
export function desenharCartao(ctx: Ctx, d: DadosCartao, formato: Formato, familia = "Raleway"): number {
  const [W, H] = TAMANHO[formato];
  const link = formato === "link";
  const s = link ? 1 : 1.25; // escala das letras: feed e stories são vistos no celular, em tela cheia
  const m = link ? 56 : 80; // margem lateral
  ctx.fillStyle = COR.fundo;
  ctx.fillRect(0, 0, W, H);

  // Faixa azul-escura do topo com fio verde e amarelo (padrão gov.br do site)
  const faixa = link ? 84 : formato === "stories" ? 260 : 130;
  ctx.fillStyle = COR.navy;
  ctx.fillRect(0, 0, W, faixa);
  ctx.fillStyle = COR.verde; ctx.fillRect(0, faixa, W / 2, 8);
  ctx.fillStyle = COR.amarelo; ctx.fillRect(W / 2, faixa, W / 2, 8);
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#ffffff";
  ctx.font = fonteDe(800, 34 * s, familia);
  const meioFaixa = formato === "stories" ? faixa - 60 : faixa / 2;
  ctx.fillText(d.site, m, meioFaixa);
  ctx.font = fonteDe(600, 22 * s, familia);
  ctx.textAlign = "right";
  ctx.fillStyle = COR.amarelo;
  ctx.fillText("Dados oficiais", W - m, meioFaixa);
  ctx.textAlign = "left";

  // Rodapé: fonte, data e endereço (vale para todos os formatos)
  const rodape = link ? 92 : formato === "stories" ? 330 : 170;
  ctx.fillStyle = COR.navy;
  ctx.fillRect(0, H - rodape, W, rodape);
  const rx = m, rw = W - 2 * m;
  let ry = H - rodape + (link ? 14 : 28);
  ry = bloco(ctx, `Fonte: ${d.fonte}. Atualizado em ${d.atualizado}.`, rx, ry, rw, { peso: 500, px: 19 * s, min: 15, maxLinhas: 2, cor: "#ffffff", familia, entre: 1.3 });
  bloco(ctx, d.endereco, rx, ry, rw, { peso: 700, px: 20 * s, min: 14, maxLinhas: 1, cor: COR.amarelo, familia });

  // Corpo
  const topo = faixa + 8 + (link ? 34 : formato === "stories" ? 90 : 60);
  const fim = H - rodape - (link ? 26 : 50);
  const colW = link ? 600 : W - 2 * m;
  let y = topo;
  ctx.font = fonteDe(800, 22 * s, familia);
  y = bloco(ctx, `${d.cargo} · ${d.partidoUf}`.toUpperCase(), m, y, colW, { peso: 800, px: 22 * s, min: 16, maxLinhas: 1, cor: COR.eyebrow, familia });
  y = bloco(ctx, d.nome, m, y + 4, colW, { peso: 800, px: link ? 58 : formato === "stories" ? 88 : 70, min: link ? 34 : 46, maxLinhas: 2, cor: COR.navy, familia, entre: 1.08 });
  y += link ? 18 : formato === "stories" ? 50 : 40;
  y = bloco(ctx, `Cota parlamentar em ${d.ano}`, m, y, colW, { peso: 600, px: 24 * s, min: 16, maxLinhas: 1, cor: COR.cinza, familia });
  y = bloco(ctx, reais(d.cota), m, y, colW, { peso: 800, px: (link ? 76 : 104) * (formato === "stories" ? 1.1 : 1), min: 40, maxLinhas: 1, cor: COR.azul, familia });
  if (d.comparacao) y = bloco(ctx, d.comparacao, m, y + 2, colW, { peso: 600, px: 22 * s, min: 15, maxLinhas: 2, cor: COR.tinta, familia, entre: 1.25 });

  // Linhas de números: à direita na prévia de link, embaixo no feed e no stories
  const lx = link ? 700 : m;
  const lw = link ? W - 700 - m : W - 2 * m;
  let ly = link ? topo + 6 : y + (formato === "stories" ? 50 : 30);
  // Aperta o espaço entre as linhas quando o nome ocupou duas linhas, para não cortar nenhuma
  const passo = Math.max(link ? 72 : 90, Math.min(link ? 78 : formato === "stories" ? 118 : 98, Math.floor((fim - (link ? 0 : 50) - ly) / Math.max(1, d.linhas.length))));
  if (link) { ctx.fillStyle = COR.linha; ctx.fillRect(lx - 40, topo, 2, fim - topo); }
  let desenhadas = 0;
  for (const [rotulo, valor] of d.linhas) {
    if (ly + passo > fim - (link ? 0 : 50)) break;
    desenhadas++;
    ctx.fillStyle = COR.linha; ctx.fillRect(lx, ly, lw, 2);
    const yr = bloco(ctx, rotulo, lx, ly + 12, lw, { peso: 600, px: 19 * s, min: 14, maxLinhas: 1, cor: COR.cinza, familia });
    bloco(ctx, valor, lx, yr - 2, lw, { peso: 800, px: 32 * s, min: 18, maxLinhas: 1, cor: COR.navy, familia });
    ly += passo;
  }
  // Nota com o que cada número quer dizer (o período e de onde vem o custo)
  if (d.nota) {
    // Na prévia de link vai embaixo da coluna da esquerda, que tem espaço; no feed e no stories, embaixo das linhas
    // (ou embaixo das linhas da direita, quando o nome ocupou duas linhas e não sobrou lugar)
    const esquerda = !link || y + 16 + 64 <= fim;
    const ny = !link ? Math.max(ly + 10, fim - (formato === "stories" ? 110 : 90)) : esquerda ? Math.max(y + 16, fim - 64) : ly + 6;
    bloco(ctx, d.nota, esquerda ? m : lx, ny, !link ? W - 2 * m : esquerda ? colW - 40 : lw, { peso: 500, px: 16 * s, min: 12, maxLinhas: 3, cor: COR.cinza, familia, entre: 1.3 });
  }
  return d.linhas.length - desenhadas;
}
