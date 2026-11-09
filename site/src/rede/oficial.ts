/* Monta a rede de um político com os dados oficiais que o site já coletou (arquivos JSON de data/).
 * Cada ligação aponta para a fonte oficial de onde o número saiu: página do parlamentar, arquivo da cota,
 * votação na API da Câmara ou do Senado, Portal da Transparência (emendas) e base CNPJ da Receita (sócios). */
import type { Politico, Resumo, VotacaoResumo } from "../data.ts";
import { idObjeto, normalizar, type Fonte, type Ligacao, type Objeto, type Retrato } from "./modelo.ts";

/** Autor de emendas no arquivo emendas/{ano}.json */
export interface AutorEmenda { nome: string; politico?: string | null; pago: number; pix_emendas?: [string, string, number][]; areas?: [string, number][] }
export interface EmendasAno { ano: number; fonte: string; autores: AutorEmenda[] }

/** Quantas votações recentes entram no grafo (todas entram no retrato, para os alertas) */
export const VOTOS_NO_GRAFO = 30;

/** Endereço oficial de uma votação a partir do id do site (cd-<id da Câmara>, sf-<código da sessão no Senado>) */
export function urlVotacao(id: string): string | undefined {
  if (id.startsWith("cd-")) return `https://dadosabertos.camara.leg.br/api/v2/votacoes/${id.slice(3)}`;
  if (id.startsWith("sf-")) return `https://legis.senado.leg.br/dadosabertos/votacao?codigoSessaoVotacao=${id.slice(3)}`;
  return undefined;
}

function urlCota(p: Politico, ano: string): string {
  return p.casa === "camara"
    ? `https://www.camara.leg.br/cotas/Ano-${ano}.csv.zip`
    : `https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/${ano}`;
}

export function redeOficial(p: Politico, votacoes: VotacaoResumo[], emendas: EmendasAno[], agora: string): {
  objetos: Objeto[]; fontes: Fonte[]; ligacoes: Omit<Ligacao, "id">[]; retrato: Retrato;
} {
  const objetos: Objeto[] = [], fontes: Fonte[] = [], ligacoes: Omit<Ligacao, "id">[] = [];
  const eu = idObjeto("politico", p.id);
  objetos.push({ id: eu, tipo: "politico", nome: p.nome, ref: `/p/${p.id}` });

  const fPerfil = `oficial:perfil:${p.id}`;
  fontes.push({ id: fPerfil, tipo: "oficial", titulo: `Página oficial: ${p.nome}`, url: p.fonte, em: agora });
  const partido = idObjeto("partido", p.partido);
  objetos.push({ id: partido, tipo: "partido", nome: p.partido });
  ligacoes.push({ de: eu, para: partido, tipo: "é filiado a", fonte: fPerfil });
  const casa = idObjeto("orgao", p.casa === "camara" ? "Câmara dos Deputados" : "Senado Federal");
  objetos.push({ id: casa, tipo: "orgao", nome: p.casa === "camara" ? "Câmara dos Deputados" : "Senado Federal" });
  ligacoes.push({ de: eu, para: casa, tipo: `exerce mandato (${p.cargo}, ${p.uf})`, fonte: fPerfil });

  // Cota parlamentar: empresas pagas e os sócios delas
  const anos = Object.keys(p.anos || {}).sort();
  const empresas: Record<string, string> = {};
  for (const ano of anos) {
    const a = p.anos[ano];
    if (!a?.fornecedores?.length) continue;
    const fCota = `oficial:cota:${p.casa}:${ano}`;
    fontes.push({ id: fCota, tipo: "oficial", titulo: `Cota parlamentar ${ano} (${p.casa === "camara" ? "Câmara" : "Senado"}), dados abertos`, url: urlCota(p, ano), em: agora, data: `${ano}-12-31` });
    for (const f of a.fornecedores) {
      if (f.tipo !== "cnpj" || !/^\d{14}$/.test(f.doc)) continue; // pessoa física: fica de fora (dado pessoal)
      const emp = idObjeto("empresa", f.doc);
      empresas[f.doc] = f.nome;
      objetos.push({ id: emp, tipo: "empresa", nome: f.nome, ref: f.ficha ? `/e/${f.doc}` : undefined });
      ligacoes.push({ de: eu, para: emp, tipo: "pagou com a cota", fonte: fCota, valor: f.valor, data: ano,
        trecho: `${p.nome} pagou ${f.nome} com a cota parlamentar em ${ano}: ${f.n} ${f.n === 1 ? "nota" : "notas"}.` });
      if (f.socios?.length) {
        const fCnpj = `oficial:cnpj:${f.doc}`;
        fontes.push({ id: fCnpj, tipo: "oficial", titulo: `Base CNPJ da Receita Federal: ${f.nome}`, url: `https://minhareceita.org/${f.doc}`, em: agora });
        for (const s of f.socios) {
          const soc = idObjeto("pessoa", s);
          objetos.push({ id: soc, tipo: "pessoa", nome: s });
          ligacoes.push({ de: soc, para: emp, tipo: "é sócio de", fonte: fCnpj });
        }
      }
    }
  }

  // Votações: as mais recentes viram eventos ligados ao projeto votado
  const porId = new Map(votacoes.map((v) => [v.id, v]));
  const votos = (p.votos || []).filter((v) => porId.has(v.votacao))
    .sort((a, b) => (porId.get(b.votacao)!.data || "").localeCompare(porId.get(a.votacao)!.data || ""));
  for (const v of votos.slice(0, VOTOS_NO_GRAFO)) {
    const vt = porId.get(v.votacao)!;
    const fV = `oficial:votacao:${vt.id}`;
    fontes.push({ id: fV, tipo: "oficial", titulo: `Votação de ${vt.data.slice(0, 10).split("-").reverse().join("/")}: ${vt.descricao.slice(0, 120)}`, url: urlVotacao(vt.id) || vt.proposicao?.url, em: agora, data: vt.data.slice(0, 10) });
    const ev = idObjeto("evento", vt.id);
    objetos.push({ id: ev, tipo: "evento", nome: `Votação ${vt.data.slice(0, 10).split("-").reverse().join("/")}${vt.proposicao ? `: ${vt.proposicao.titulo}` : ""}`, ref: `/v/${vt.id}` });
    ligacoes.push({ de: eu, para: ev, tipo: `votou ${v.voto}`, fonte: fV, data: vt.data.slice(0, 10), trecho: `${p.nome} votou ${v.voto}. ${vt.descricao}` });
    if (vt.proposicao) {
      const pr = idObjeto("projeto", vt.proposicao.titulo);
      objetos.push({ id: pr, tipo: "projeto", nome: vt.proposicao.titulo, notas: vt.proposicao.ementa });
      ligacoes.push({ de: ev, para: pr, tipo: "votou o projeto", fonte: fV, trecho: vt.proposicao.ementa });
    }
  }

  // Emendas: para onde mandou dinheiro (emendas Pix com destino conhecido)
  let pagoEmendas = 0;
  for (const e of emendas) {
    const autor = e.autores.find((a) => a.politico === p.id);
    if (!autor) continue;
    pagoEmendas += autor.pago || 0;
    const fE = `oficial:emendas:${e.ano}`;
    fontes.push({ id: fE, tipo: "oficial", titulo: `Emendas parlamentares ${e.ano}, Portal da Transparência`, url: e.fonte, em: agora, data: `${e.ano}-12-31` });
    for (const [, destino, valor] of autor.pix_emendas || []) {
      if (!destino) continue;
      const lugar = idObjeto("lugar", destino);
      objetos.push({ id: lugar, tipo: "lugar", nome: destino });
      ligacoes.push({ de: eu, para: lugar, tipo: "mandou emenda Pix para", fonte: fE, valor, data: String(e.ano) });
    }
  }

  const ano = anos[anos.length - 1] || "";
  const retrato: Retrato = {
    em: agora, nome: p.nome, partido: p.partido, ano, cota: ano ? p.anos[ano]?.total || 0 : 0,
    votos: (p.votos || []).map((v) => v.votacao), empresas, emendas: Math.round(pagoEmendas * 100) / 100,
    situacao: p.em_exercicio === false ? p.situacao || "fora do exercício" : "",
  };
  return { objetos, fontes, ligacoes, retrato };
}

/** Lê o pedido do link "?seguir=" (vários itens separados por vírgula) e devolve os ids dos políticos.
 *  Cada item pode ser: o id do site ("dep-209787"); um nome com a UF ("Nikolas Ferreira/MG"); ou uma Casa com a UF
 *  ("senado/MG", "camara/SP"), que segue todos dessa Casa e estado que estão no mandato hoje.
 *  Um nome que bate com mais de uma pessoa fica de fora (vai em "faltou"): melhor não seguir a pessoa errada. */
export function resolverPedido(pedido: string, politicos: Resumo[]): { ids: string[]; faltou: string[] } {
  const ids: string[] = [], faltou: string[] = [];
  const porId = new Set(politicos.map((p) => p.id));
  for (const item of pedido.split(",").map((x) => x.trim()).filter(Boolean)) {
    if (porId.has(item)) { ids.push(item); continue; }
    const [texto, uf] = item.split("/").map((x) => x.trim());
    const n = normalizar(texto);
    const daUf = politicos.filter((p) => !uf || p.uf.toUpperCase() === uf.toUpperCase());
    if (n === "senado" || n === "camara") {
      const casa = daUf.filter((p) => p.casa === n && p.em_exercicio !== false);
      if (casa.length && uf) ids.push(...casa.map((p) => p.id)); else faltou.push(item);
      continue;
    }
    const nomes = (p: Resumo) => [p.nome, ...(p.outros_nomes || [])].map(normalizar);
    const exato = daUf.filter((p) => nomes(p).includes(n));
    const parecido = exato.length ? exato : daUf.filter((p) => nomes(p).some((x) => ` ${x} `.includes(` ${n} `)));
    const ativos = parecido.filter((p) => p.em_exercicio !== false);
    const achados = ativos.length ? ativos : parecido;
    if (achados.length === 1) ids.push(achados[0].id); else faltou.push(item);
  }
  return { ids: [...new Set(ids)], faltou };
}
