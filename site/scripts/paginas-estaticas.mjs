/* Páginas estáticas para buscadores e IAs, em português, inglês e espanhol.
 *
 * O site é um app (React) que monta as telas no navegador, com endereços do tipo #/p/123 que o Google não indexa.
 * Este script roda depois do build e escreve, a partir dos mesmos arquivos de dados (dist/data):
 *   politico/<nome>-<id>.html    uma página por deputado e senador (gastos, empresas, votos), e en/ e es/
 *   empresa/<cnpj>.html          as empresas que mais receberam, com os donos, e en/ e es/
 *   votacao/<id>.html            cada votação nominal, com o placar por partido, e en/ e es/
 *   indice.html                  lista de todas as páginas (en/indice.html, es/indice.html)
 *   sitemap-paginas.xml, llms.txt
 * Cada página tem o resumo em texto, dados estruturados (schema.org), o link para a tela completa do app e o link
 * para a fonte oficial. Nada é calculado aqui: os números são os dos arquivos de dados.
 *
 * Uso: node scripts/paginas-estaticas.mjs dist https://amarigo.github.io/segredos-abertos/ [--mg]
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [dist, base, ...resto] = process.argv.slice(2);
const MG = resto.includes("--mg");
if (!dist || !base) { console.error("uso: node scripts/paginas-estaticas.mjs <dist> <endereço público> [--mg]"); process.exit(2); }
const lerJson = (rel) => { const p = join(dist, "data", rel); return existsSync(p) ? JSON.parse(readFileSync(p, "utf-8")) : null; };
const meta = lerJson("meta.json");
const politicos = lerJson("politicos.json");
if (!meta || !politicos) { console.log("Páginas estáticas: sem dados em", join(dist, "data"), "(nada a fazer)"); process.exit(0); }
const empresas = lerJson("empresas.json") || [];
const votacoes = lerJson("votacoes.json") || [];
const ANO = String(meta.anos[meta.anos.length - 1]);
const N_EMPRESAS = 500;
const SITE = MG ? "Minas Nossa" : "Segredos Abertos Brasil";

/* ---------- Textos ---------- */
const LINGUAS = ["pt", "en", "es"];
const LOCALE = { pt: "pt-BR", en: "en-US", es: "es" };
const T = {
  pt: {
    dep: "Deputado(a) federal", sen: "Senador(a)", camara: "Câmara dos Deputados", senado: "Senado Federal",
    tituloPol: (p) => `${p.nome} (${p.partido}-${p.uf}): gastos da cota parlamentar, empresas e votos`,
    descPol: (p, v) => `Quanto ${p.nome}, ${p.cargo.toLowerCase()} do ${p.partido}-${p.uf}, gastou da cota parlamentar em ${ANO} (${v}), com quais empresas, e como vota. Dados oficiais.`,
    resumoPol: (p, v, c) => `Em ${ANO}, ${p.nome} pediu ${v} de reembolso da cota parlamentar (despesas do mandato pagas com dinheiro público, com nota fiscal).` + (c ? ` Somando salário, equipe e outros gastos informados pelos sites oficiais, o custo conhecido do mandato foi ${c}.` : ""),
    porAno: "Por ano", ano: "Ano", cota: "Cota parlamentar", custo: "Custo conhecido",
    categorias: "Em que gastou a cota", fornecedores: "Quem recebeu o dinheiro da cota", fornecedor: "Fornecedor", valor: "Valor", socios: "Sócios",
    votos: "Como vota", posicao: "Posição pelos votos", governo: "Vota com o governo", partido: "Vota com o próprio partido",
    nVotos: (n) => `Calculado a partir de ${n} votos nominais.`, completo: "Ver a página completa, com cada nota fiscal e cada voto",
    fonte: "Fonte oficial", esq: "Esquerda", centro: "Centro", dir: "Direita",
    tituloEmp: (e) => `${e.nome}: quanto recebeu de dinheiro público e quem são os donos`,
    descEmp: (e, v) => `${e.nome} (CNPJ ${e.cnpjF}) recebeu ${v} da cota de ${e.n_politicos} parlamentares. Veja os donos, outras empresas dos mesmos donos e quem pagou.`,
    resumoEmp: (e, v) => `${e.nome} recebeu ${v} da cota parlamentar de ${e.n_politicos} deputados e senadores, somando todos os anos.`,
    donos: "Quem são os donos", outras: "Outras empresas dos mesmos donos no site", pagadores: "Quem pagou com a cota", parlamentar: "Parlamentar",
    situacao: "Situação na Receita", atividade: "Atividade", abertura: "Aberta em", municipio: "Cidade",
    emendas: "Recebeu de emendas parlamentares", governoFed: "Recebeu do governo federal", renuncia: "Imposto que deixou de pagar (renúncia fiscal)",
    tituloVot: (v) => `${v.nome}: como votou cada deputado e senador`, descVot: (v) => `Votação de ${v.data} no ${v.casaNome}: ${v.resultado}. Sim ${v.sim}, Não ${v.nao}. Veja o voto de cada parlamentar e de cada partido.`,
    aprovada: "aprovada", rejeitada: "rejeitada", oQue: "O que foi votado", porPartido: "Por partido", sim: "Sim", nao: "Não", outros: "Outros",
    indice: "Todas as páginas", politicos: "Deputados e senadores", empresasT: "Empresas", votacoesT: "Votações",
    tituloIndice: `${SITE}: deputados, senadores, empresas e votações`,
    descIndice: "Lista de todas as páginas: gastos da cota parlamentar de cada deputado e senador, as empresas que receberam e quem são os donos, e como cada um votou.",
    rodape: "Projeto independente e sem fins lucrativos. Dados oficiais da Câmara dos Deputados, do Senado Federal, da Receita Federal e do Portal da Transparência.",
    atualizado: (d) => `Atualizado em ${d}.`, inicio: "Início", app: "Abrir o site",
  },
  en: {
    dep: "Federal deputy", sen: "Senator", camara: "Chamber of Deputies", senado: "Federal Senate",
    tituloPol: (p) => `${p.nome} (${p.partido}-${p.uf}): parliamentary allowance spending, companies and votes`,
    descPol: (p, v) => `How much ${p.nome}, ${p.cargoT.toLowerCase()} for ${p.partido}-${p.uf} (Brazil), spent from the parliamentary allowance in ${ANO} (${v}), with which companies, and how they vote. Official data.`,
    resumoPol: (p, v, c) => `In ${ANO}, ${p.nome} claimed ${v} in reimbursements from the parliamentary allowance ("cota parlamentar": mandate expenses paid with public money, backed by invoices).` + (c ? ` Adding salary, staff and other expenses reported by the official websites, the known cost of the mandate was ${c}.` : ""),
    porAno: "By year", ano: "Year", cota: "Parliamentary allowance", custo: "Known cost",
    categorias: "What the allowance was spent on", fornecedores: "Who received the allowance money", fornecedor: "Supplier", valor: "Amount", socios: "Partners",
    votos: "How they vote", posicao: "Position based on votes", governo: "Votes with the government", partido: "Votes with own party",
    nVotos: (n) => `Calculated from ${n} roll-call votes.`, completo: "See the full page, with every invoice and every vote",
    fonte: "Official source", esq: "Left", centro: "Center", dir: "Right",
    tituloEmp: (e) => `${e.nome}: public money received and who owns it`,
    descEmp: (e, v) => `${e.nome} (CNPJ ${e.cnpjF}) received ${v} from the allowances of ${e.n_politicos} members of Brazil's Congress. See the owners, other companies of the same owners and who paid.`,
    resumoEmp: (e, v) => `${e.nome} received ${v} from the parliamentary allowance of ${e.n_politicos} deputies and senators, adding up all years.`,
    donos: "Who the owners are", outras: "Other companies of the same owners on the site", pagadores: "Who paid with the allowance", parlamentar: "Member of Congress",
    situacao: "Status at the Federal Revenue Service", atividade: "Business activity", abertura: "Opened on", municipio: "City",
    emendas: "Received from parliamentary earmarks", governoFed: "Received from the federal government", renuncia: "Tax not paid (tax breaks)",
    tituloVot: (v) => `${v.nome}: how each deputy and senator voted`, descVot: (v) => `Vote of ${v.data} in the ${v.casaNome} (Brazil): ${v.resultado}. Yes ${v.sim}, No ${v.nao}. See each member's and each party's vote.`,
    aprovada: "approved", rejeitada: "rejected", oQue: "What was voted", porPartido: "By party", sim: "Yes", nao: "No", outros: "Other",
    indice: "All pages", politicos: "Deputies and senators", empresasT: "Companies", votacoesT: "Votes",
    tituloIndice: `${SITE}: Brazilian deputies, senators, companies and votes`,
    descIndice: "List of all pages: parliamentary allowance spending of each Brazilian deputy and senator, the companies that received the money and who owns them, and how each one voted.",
    rodape: "Independent, non-profit project. Official data from Brazil's Chamber of Deputies, Federal Senate, Federal Revenue Service and Transparency Portal.",
    atualizado: (d) => `Updated on ${d}.`, inicio: "Home", app: "Open the site",
  },
  es: {
    dep: "Diputado(a) federal", sen: "Senador(a)", camara: "Cámara de Diputados", senado: "Senado Federal",
    tituloPol: (p) => `${p.nome} (${p.partido}-${p.uf}): gastos de la cuota parlamentaria, empresas y votos`,
    descPol: (p, v) => `Cuánto gastó ${p.nome}, ${p.cargoT.toLowerCase()} del ${p.partido}-${p.uf} (Brasil), de la cuota parlamentaria en ${ANO} (${v}), con qué empresas, y cómo vota. Datos oficiales.`,
    resumoPol: (p, v, c) => `En ${ANO}, ${p.nome} pidió ${v} de reembolso de la cuota parlamentaria (gastos del mandato pagados con dinero público, con factura).` + (c ? ` Sumando salario, personal y otros gastos informados por los sitios oficiales, el costo conocido del mandato fue ${c}.` : ""),
    porAno: "Por año", ano: "Año", cota: "Cuota parlamentaria", custo: "Costo conocido",
    categorias: "En qué gastó la cuota", fornecedores: "Quién recibió el dinero de la cuota", fornecedor: "Proveedor", valor: "Valor", socios: "Socios",
    votos: "Cómo vota", posicao: "Posición según los votos", governo: "Vota con el gobierno", partido: "Vota con su propio partido",
    nVotos: (n) => `Calculado a partir de ${n} votos nominales.`, completo: "Ver la página completa, con cada factura y cada voto",
    fonte: "Fuente oficial", esq: "Izquierda", centro: "Centro", dir: "Derecha",
    tituloEmp: (e) => `${e.nome}: cuánto recibió de dinero público y quiénes son los dueños`,
    descEmp: (e, v) => `${e.nome} (CNPJ ${e.cnpjF}) recibió ${v} de la cuota de ${e.n_politicos} parlamentarios de Brasil. Vea los dueños, otras empresas de los mismos dueños y quién pagó.`,
    resumoEmp: (e, v) => `${e.nome} recibió ${v} de la cuota parlamentaria de ${e.n_politicos} diputados y senadores, sumando todos los años.`,
    donos: "Quiénes son los dueños", outras: "Otras empresas de los mismos dueños en el sitio", pagadores: "Quién pagó con la cuota", parlamentar: "Parlamentario",
    situacao: "Situación en la Receita Federal", atividade: "Actividad", abertura: "Abierta el", municipio: "Ciudad",
    emendas: "Recibió de enmiendas parlamentarias", governoFed: "Recibió del gobierno federal", renuncia: "Impuesto que dejó de pagar (renuncia fiscal)",
    tituloVot: (v) => `${v.nome}: cómo votó cada diputado y senador`, descVot: (v) => `Votación del ${v.data} en el ${v.casaNome} (Brasil): ${v.resultado}. Sí ${v.sim}, No ${v.nao}. Vea el voto de cada parlamentario y de cada partido.`,
    aprovada: "aprobada", rejeitada: "rechazada", oQue: "Qué se votó", porPartido: "Por partido", sim: "Sí", nao: "No", outros: "Otros",
    indice: "Todas las páginas", politicos: "Diputados y senadores", empresasT: "Empresas", votacoesT: "Votaciones",
    tituloIndice: `${SITE}: diputados, senadores, empresas y votaciones de Brasil`,
    descIndice: "Lista de todas las páginas: gastos de la cuota parlamentaria de cada diputado y senador de Brasil, las empresas que recibieron y quiénes son los dueños, y cómo votó cada uno.",
    rodape: "Proyecto independiente y sin fines de lucro. Datos oficiales de la Cámara de Diputados, del Senado Federal, de la Receita Federal y del Portal de la Transparencia de Brasil.",
    atualizado: (d) => `Actualizado el ${d}.`, inicio: "Inicio", app: "Abrir el sitio",
  },
};
if (MG) {
  T.pt.rodape = "Projeto independente e sem fins lucrativos. Minas Nossa é a parte de Minas Gerais do Segredos Abertos Brasil.";
  T.en.rodape = "Independent, non-profit project. Minas Nossa is the Minas Gerais section of Segredos Abertos Brasil.";
  T.es.rodape = "Proyecto independiente y sin fines de lucro. Minas Nossa es la parte de Minas Gerais de Segredos Abertos Brasil.";
}

/* ---------- Ajudantes ---------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reais = (v, l) => new Intl.NumberFormat(LOCALE[l], { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v || 0);
const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const data = (s, l) => { if (!s) return ""; const [a, m, d] = s.slice(0, 10).split("-"); return l === "en" ? `${a}-${m}-${d}` : `${d}/${m}/${a}`; };
const slug = (s) => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const cnpjF = (c) => { const d = String(c).replace(/\D/g, ""); return d.length === 14 ? `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}` : c; };
const linkSeguro = (u) => (/^https?:\/\/[^\s<>"']+$/i.test(u || "") ? u : null);
const rotulo = (r, l) => ({ Esquerda: T[l].esq, Direita: T[l].dir, Centro: T[l].centro, "Centro-esquerda": l === "pt" ? "Centro-esquerda" : l === "en" ? "Center-left" : "Centroizquierda", "Centro-direita": l === "pt" ? "Centro-direita" : l === "en" ? "Center-right" : "Centroderecha" }[r] || r || "—");
const prefixo = (l) => (l === "pt" ? "" : `${l}/`);
/** Endereço de uma página estática ("politico/x.html") em cada língua */
const url = (rel, l) => `${base}${prefixo(l)}${rel}`;
/** Link do app (tela completa) a partir de uma página em politico/, empresa/... */
const appLink = (hash, l) => `${l === "pt" ? "../" : "../../"}${l === "pt" ? "" : `?lang=${l}`}#${hash}`;
const ate = (l) => (l === "pt" ? "../" : "../../");
const gravar = (rel, html) => { const p = join(dist, rel); mkdirSync(join(p, ".."), { recursive: true }); writeFileSync(p, html); };

function pagina({ l, rel, titulo, descricao, corpo, jsonld, tipo = "article" }) {
  const alternativas = LINGUAS.map((x) => `<link rel="alternate" hreflang="${x === "pt" ? "pt-BR" : x}" href="${url(rel, x)}">`).join("\n");
  const raiz = rel.includes("/") ? ate(l) : l === "pt" ? "./" : "../";
  return `<!doctype html>
<html lang="${LOCALE[l] === "en-US" ? "en" : LOCALE[l]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'none'; style-src 'unsafe-inline'; img-src 'self' https: data:; base-uri 'none'; form-action 'none'">
<title>${esc(titulo)} | ${SITE}</title>
<meta name="description" content="${esc(descricao)}">
<link rel="canonical" href="${url(rel, l)}">
${alternativas}
<link rel="alternate" hreflang="x-default" href="${url(rel, "pt")}">
<meta property="og:type" content="${tipo}">
<meta property="og:site_name" content="${SITE}">
<meta property="og:title" content="${esc(titulo)}">
<meta property="og:description" content="${esc(descricao)}">
<meta property="og:url" content="${url(rel, l)}">
<meta property="og:locale" content="${LOCALE[l].replace("-", "_")}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="${raiz}icon.svg" type="image/svg+xml">
<script type="application/ld+json">${JSON.stringify(jsonld).replace(/</g, "\\u003c")}</script>
<style>
:root{--bg:#fbf8f4;--fg:#1c1433;--muted:#5c5470;--line:#e6e0ea;--faixa:#24104a;--link:#5a2bc2;--hot:#d81e5b}
@media (prefers-color-scheme:dark){:root{--bg:#120c1f;--fg:#f3eff8;--muted:#b5abc9;--line:#30274a;--faixa:#1d0c3d;--link:#b9a0ff;--hot:#ff6e98}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header,footer{background:var(--faixa);color:#fff}header .w,footer .w{padding-block:12px}header a,footer a{color:#fff}
.w{max-width:960px;margin:0 auto;padding-inline:16px}main.w{padding-block:24px 48px}
a{color:var(--link)}h1{font-size:clamp(1.6rem,4vw,2.3rem);line-height:1.15;margin:.2em 0}h2{font-size:1.25rem;margin:1.6em 0 .5em}
.muted{color:var(--muted)}.big{font-size:1.8rem;font-weight:800;color:var(--hot)}nav.l a{margin-right:10px}
table{border-collapse:collapse;width:100%;font-size:.95rem}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
td.r,th.r{text-align:right;white-space:nowrap}.tw{overflow-x:auto}.cta{display:inline-block;margin:14px 0;padding:10px 18px;border-radius:999px;background:var(--hot);color:#fff;text-decoration:none;font-weight:700}
ul.c{columns:2 260px;padding-left:18px}
</style>
</head>
<body>
<header><div class="w"><a href="${raiz}${l === "pt" ? "" : `?lang=${l}`}"><strong>${SITE}</strong></a> · <a href="${raiz}${prefixo(l)}indice.html">${T[l].indice}</a>
<nav class="l" aria-label="Idioma / Language" style="float:right">${LINGUAS.map((x) => `<a href="${url(rel, x)}" hreflang="${x}" lang="${x}"${x === l ? ' aria-current="true"' : ""}>${x.toUpperCase()}</a>`).join(" ")}</nav></div></header>
<main class="w">
${corpo}
</main>
<footer><div class="w"><p>${T[l].rodape} ${T[l].atualizado(data(meta.atualizado_em, l))}</p><p><a href="https://github.com/amarigo/segredos-abertos">GitHub</a></p></div></footer>
</body>
</html>
`;
}

const editor = { "@type": "Organization", name: SITE, url: base };
const paginas = []; // [rel, lastmod]

/* ---------- Políticos ---------- */
const idsPol = new Map(politicos.map((p) => [p.id, `politico/${slug(p.nome)}-${p.id}.html`]));
for (const p of politicos) {
  const d = lerJson(`p/${p.id}.json`) || p;
  const anos = Object.keys(p.por_ano || {}).sort();
  const atual = (d.anos && d.anos[ANO]) || null;
  const rel = idsPol.get(p.id);
  paginas.push(rel);
  for (const l of LINGUAS) {
    const t = T[l];
    const cargoT = p.casa === "senado" ? t.sen : t.dep;
    const ano = p.por_ano?.[ANO];
    const v = reais(ano?.total || 0, l);
    const custo = ano && ano.custo_total > ano.total ? reais(ano.custo_total, l) : "";
    const fonte = linkSeguro(p.fonte);
    const forn = (atual?.fornecedores || []).slice(0, 15);
    const cats = (atual?.categorias || []).slice(0, 10);
    const corpo = `<p class="muted">${esc(cargoT)} · ${esc(p.partido)}-${esc(p.uf)} · ${p.casa === "senado" ? t.senado : t.camara}</p>
<h1>${esc(p.nome)}</h1>
<p class="big">${v} <span class="muted" style="font-size:1rem;font-weight:400">${t.cota} · ${ANO}</span></p>
<p>${esc(t.resumoPol({ ...p, cargoT }, v, custo))}</p>
<a class="cta" href="${appLink(`/p/${p.id}`, l)}">${t.completo}</a>
<h2>${t.porAno}</h2>
<div class="tw"><table><thead><tr><th>${t.ano}</th><th class="r">${t.cota}</th><th class="r">${t.custo}</th></tr></thead><tbody>
${anos.map((a) => `<tr><td>${a}</td><td class="r">${reais(p.por_ano[a].total, l)}</td><td class="r">${reais(p.por_ano[a].custo_total, l)}</td></tr>`).join("\n")}
</tbody></table></div>
${cats.length ? `<h2>${t.categorias} (${ANO})</h2>
<div class="tw"><table><tbody>${cats.map((c) => `<tr><td>${esc(c.categoria)}</td><td class="r">${reais(c.valor, l)}</td></tr>`).join("")}</tbody></table></div>` : ""}
${forn.length ? `<h2>${t.fornecedores} (${ANO})</h2>
<div class="tw"><table><thead><tr><th>${t.fornecedor}</th><th>${t.socios}</th><th class="r">${t.valor}</th></tr></thead><tbody>
${forn.map((f) => `<tr><td>${f.tipo === "cnpj" ? `<a href="${appLink(`/e/${f.doc}`, l)}">${esc(f.nome)}</a><br><span class="muted">CNPJ ${cnpjF(f.doc)}</span>` : esc(f.nome)}</td><td>${esc((f.socios || []).join(", "))}</td><td class="r">${reais(f.valor, l)}</td></tr>`).join("\n")}
</tbody></table></div>` : ""}
<h2>${t.votos}</h2>
<ul>
<li>${t.posicao}: <strong>${esc(rotulo(p.rotulo, l))}</strong></li>
<li>${t.governo}: <strong>${pct(p.alinhamento_governo)}</strong></li>
<li>${t.partido}: <strong>${pct(p.fidelidade_partido)}</strong></li>
</ul>
<p class="muted">${t.nVotos(p.n_votos || 0)}</p>
${fonte ? `<p>${t.fonte}: <a href="${esc(fonte)}">${esc(fonte)}</a></p>` : ""}`;
    gravar(`${prefixo(l)}${rel}`, pagina({
      l, rel, tipo: "profile", titulo: t.tituloPol(p), descricao: t.descPol({ ...p, cargoT }, v), corpo,
      jsonld: {
        "@context": "https://schema.org", "@type": "ProfilePage", inLanguage: LOCALE[l], url: url(rel, l), publisher: editor, dateModified: meta.atualizado_em,
        mainEntity: {
          "@type": "Person", name: p.nome, jobTitle: cargoT, image: linkSeguro(p.foto) || undefined, sameAs: fonte ? [fonte] : undefined,
          affiliation: { "@type": "PoliticalParty", name: p.partido },
          memberOf: { "@type": "GovernmentOrganization", name: p.casa === "senado" ? "Senado Federal" : "Câmara dos Deputados" },
        },
      },
    }));
  }
}

/* ---------- Empresas (as que mais receberam) ---------- */
const listaEmp = empresas.slice().sort((a, b) => b.total - a.total).slice(0, N_EMPRESAS);
const relEmp = new Map(listaEmp.map((e) => [e.cnpj, `empresa/${e.cnpj}.html`]));
for (const r of listaEmp) {
  const e = lerJson(`e/${r.cnpj}.json`);
  if (!e) continue;
  const rel = relEmp.get(r.cnpj);
  paginas.push(rel);
  const emp = e.empresa;
  for (const l of LINGUAS) {
    const t = T[l];
    const info = { ...e, cnpjF: cnpjF(e.cnpj) };
    const v = reais(e.total, l);
    const donos = (e.donos_finais && e.donos_finais.length ? e.donos_finais : e.socios || []);
    const outras = new Map();
    for (const s of donos) for (const o of s.outras_empresas || []) outras.set(o.cnpj, o);
    const corpo = `<p class="muted">CNPJ ${cnpjF(e.cnpj)}${emp ? ` · ${esc(emp.municipio)}-${esc(emp.uf)}` : ""}</p>
<h1>${esc(e.nome)}</h1>
<p class="big">${v}</p>
<p>${esc(t.resumoEmp(info, v))}</p>
<a class="cta" href="${appLink(`/e/${e.cnpj}`, l)}">${t.completo}</a>
${emp ? `<ul><li>${t.situacao}: ${esc(emp.situacao)}</li><li>${t.atividade}: ${esc(emp.atividade)}</li><li>${t.abertura}: ${data(emp.abertura, l)}</li></ul>` : ""}
${e.emendas?.total ? `<p>${t.emendas}: <strong>${reais(e.emendas.total, l)}</strong></p>` : ""}
${e.governo?.total ? `<p>${t.governoFed}: <strong>${reais(e.governo.total, l)}</strong></p>` : ""}
${e.renuncia?.total ? `<p>${t.renuncia}: <strong>${reais(e.renuncia.total, l)}</strong></p>` : ""}
${donos.length ? `<h2>${t.donos}</h2><ul>${donos.map((s) => `<li>${esc(s.nome)}${s.qualificacao ? ` <span class="muted">(${esc(s.qualificacao)})</span>` : ""}</li>`).join("")}</ul>` : ""}
${outras.size ? `<h2>${t.outras}</h2><ul>${[...outras.values()].map((o) => `<li>${relEmp.has(o.cnpj) ? `<a href="${o.cnpj}.html">${esc(o.nome)}</a>` : esc(o.nome)} · ${reais(o.total, l)}</li>`).join("")}</ul>` : ""}
${(e.pagadores || []).length ? `<h2>${t.pagadores}</h2>
<div class="tw"><table><thead><tr><th>${t.parlamentar}</th><th class="r">${t.valor}</th></tr></thead><tbody>
${e.pagadores.slice(0, 50).map((x) => `<tr><td>${idsPol.has(x.politico) ? `<a href="../${idsPol.get(x.politico)}">${esc(x.nome)}</a>` : esc(x.nome)} <span class="muted">${esc(x.partido)}-${esc(x.uf)}</span></td><td class="r">${reais(x.valor, l)}</td></tr>`).join("\n")}
</tbody></table></div>` : ""}`;
    gravar(`${prefixo(l)}${rel}`, pagina({
      l, rel, titulo: t.tituloEmp(e), descricao: t.descEmp(info, v), corpo,
      jsonld: {
        "@context": "https://schema.org", "@type": "WebPage", inLanguage: LOCALE[l], url: url(rel, l), publisher: editor, dateModified: meta.atualizado_em,
        about: { "@type": "Organization", name: e.nome, legalName: emp?.razao_social || e.nome, taxID: cnpjF(e.cnpj),
          address: emp ? { "@type": "PostalAddress", addressLocality: emp.municipio, addressRegion: emp.uf, addressCountry: "BR" } : undefined,
          founder: undefined, member: donos.slice(0, 20).map((s) => ({ "@type": s.tipo === "empresa" ? "Organization" : "Person", name: s.nome })) },
      },
    }));
  }
}

/* ---------- Votações ---------- */
const relVot = new Map(votacoes.map((v) => [v.id, `votacao/${v.id}.html`]));
for (const r of votacoes) {
  const v = lerJson(`v/${r.id}.json`) || r;
  const rel = relVot.get(r.id);
  paginas.push(rel);
  const nome = v.proposicao?.titulo || (v.proposicao ? `${v.proposicao.sigla} ${v.proposicao.numero}/${v.proposicao.ano}` : "") || (v.descricao || "").slice(0, 80);
  for (const l of LINGUAS) {
    const t = T[l];
    const info = { nome, data: data(v.data, l), casaNome: v.casa === "senado" ? t.senado : t.camara, resultado: v.aprovada ? t.aprovada : t.rejeitada, sim: v.sim, nao: v.nao };
    const partidos = Object.entries(v.por_partido || {}).sort((a, b) => Object.values(b[1]).reduce((x, y) => x + y, 0) - Object.values(a[1]).reduce((x, y) => x + y, 0));
    const fonte = linkSeguro(v.proposicao?.url) || linkSeguro(v.fonte);
    const corpo = `<p class="muted">${info.data} · ${info.casaNome}</p>
<h1>${esc(nome)}</h1>
<p class="big">${t.sim} ${v.sim} · ${t.nao} ${v.nao}</p>
<p><strong>${esc(info.resultado)}</strong></p>
<h2>${t.oQue}</h2>
${v.proposicao?.ementa ? `<p>${esc(v.proposicao.ementa)}</p>` : ""}
<p class="muted">${esc(v.descricao || "")}</p>
<a class="cta" href="${appLink(`/v/${v.id}`, l)}">${t.completo}</a>
${partidos.length ? `<h2>${t.porPartido}</h2><div class="tw"><table><thead><tr><th></th><th class="r">${t.sim}</th><th class="r">${t.nao}</th><th class="r">${t.outros}</th></tr></thead><tbody>
${partidos.map(([sg, c]) => { const outros = Object.entries(c).filter(([k]) => k !== "Sim" && k !== "Não").reduce((a, [, n]) => a + n, 0); return `<tr><td>${esc(sg)}</td><td class="r">${c["Sim"] || 0}</td><td class="r">${c["Não"] || 0}</td><td class="r">${outros}</td></tr>`; }).join("\n")}
</tbody></table></div>` : ""}
${fonte ? `<p>${t.fonte}: <a href="${esc(fonte)}">${esc(fonte)}</a></p>` : ""}`;
    gravar(`${prefixo(l)}${rel}`, pagina({
      l, rel, titulo: t.tituloVot(info), descricao: t.descVot(info), corpo,
      jsonld: { "@context": "https://schema.org", "@type": "WebPage", inLanguage: LOCALE[l], url: url(rel, l), publisher: editor, dateModified: meta.atualizado_em,
        about: { "@type": "Legislation", name: nome, legislationIdentifier: nome, abstract: v.proposicao?.ementa || undefined, url: fonte || undefined } },
    }));
  }
}

/* ---------- Índice ---------- */
for (const l of LINGUAS) {
  const t = T[l];
  const rel = "indice.html";
  const pol = politicos.slice().sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  const corpo = `<h1>${esc(t.tituloIndice)}</h1>
<p>${esc(t.descIndice)}</p>
<a class="cta" href="${l === "pt" ? "./" : `../?lang=${l}`}">${t.app}</a>
<h2>${t.politicos} (${pol.length})</h2>
<ul class="c">${pol.map((p) => `<li><a href="${idsPol.get(p.id)}">${esc(p.nome)}</a> <span class="muted">${esc(p.partido)}-${esc(p.uf)}</span></li>`).join("\n")}</ul>
<h2>${t.empresasT} (${relEmp.size})</h2>
<ul class="c">${listaEmp.map((e) => `<li><a href="${relEmp.get(e.cnpj)}">${esc(e.nome)}</a></li>`).join("\n")}</ul>
<h2>${t.votacoesT} (${votacoes.length})</h2>
<ul>${votacoes.map((v) => `<li><a href="${relVot.get(v.id)}">${esc(v.proposicao?.titulo || (v.descricao || "").slice(0, 80))}</a> <span class="muted">${data(v.data, l)}</span></li>`).join("\n")}</ul>`;
  gravar(`${prefixo(l)}${rel}`, pagina({
    l, rel, tipo: "website", titulo: t.tituloIndice, descricao: t.descIndice, corpo,
    jsonld: { "@context": "https://schema.org", "@type": "CollectionPage", name: t.tituloIndice, inLanguage: LOCALE[l], url: url(rel, l), publisher: editor },
  }));
}
paginas.unshift("indice.html");

/* ---------- Sitemap das páginas (com as três línguas de cada uma) ---------- */
const lastmod = meta.atualizado_em.slice(0, 10);
const entrada = (rel) => LINGUAS.map((l) => `<url><loc>${url(rel, l)}</loc><lastmod>${lastmod}</lastmod>${LINGUAS.map((x) => `<xhtml:link rel="alternate" hreflang="${x === "pt" ? "pt-BR" : x}" href="${url(rel, x)}"/>`).join("")}</url>`).join("\n");
const outros = MG ? [] : ["mg/", "eleicao2026/"]; // os outros sites do projeto, publicados abaixo deste endereço
const app = ["", ...outros].flatMap((d) => LINGUAS.map((l) => `<url><loc>${base}${d}${l === "pt" ? "" : `?lang=${l}`}</loc><lastmod>${lastmod}</lastmod><changefreq>daily</changefreq>${LINGUAS.map((x) => `<xhtml:link rel="alternate" hreflang="${x === "pt" ? "pt-BR" : x}" href="${base}${d}${x === "pt" ? "" : `?lang=${x}`}"/>`).join("")}</url>`)).join("\n");
writeFileSync(join(dist, "sitemap-paginas.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${app}
${paginas.map(entrada).join("\n")}
</urlset>
`);
console.log(`Páginas estáticas (${MG ? "Minas Nossa" : "Brasil"}): ${politicos.length} políticos, ${relEmp.size} empresas, ${votacoes.length} votações, em ${LINGUAS.length} línguas.`);

/* ---------- Só no site nacional: índice dos sitemaps e llms.txt (resumo do site para IAs) ---------- */
if (!MG) {
  writeFileSync(join(dist, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>${base}sitemap-paginas.xml</loc><lastmod>${lastmod}</lastmod></sitemap>
<sitemap><loc>${base}mg/sitemap-paginas.xml</loc><lastmod>${lastmod}</lastmod></sitemap>
</sitemapindex>
`);
  const c = meta.contagens || {};
  writeFileSync(join(dist, "llms.txt"), `# Segredos Abertos Brasil

> Quanto cada deputado federal e senador do Brasil gasta da cota parlamentar (reembolso de despesas do mandato), com quais empresas, quem são os donos dessas empresas, para onde vai o dinheiro das emendas parlamentares, quais empresas mais recebem dinheiro público ou deixam de pagar impostos, e como cada parlamentar vota (por partido e de esquerda a direita). Só dados oficiais, com link para a fonte. Projeto independente, sem fins lucrativos e de código aberto. Disponível em português, inglês (?lang=en) e espanhol (?lang=es).

How much each Brazilian federal deputy and senator spends from the parliamentary allowance, with which companies, who owns those companies, where parliamentary earmarks go, and how each one votes. Official data only, each figure linked to its source.

Atualizado em ${lastmod}. ${c.politicos || politicos.length} parlamentares, ${c.despesas || "?"} despesas, ${c.votacoes || votacoes.length} votações, ${c.empresas_com_socios || "?"} empresas com sócios identificados. Anos: ${meta.anos.join(", ")}.

## Páginas para ler (texto simples, uma por assunto)

- [Índice de todas as páginas](${base}indice.html): cada deputado e senador, as empresas que mais receberam e cada votação nominal
- [Index in English](${base}en/indice.html)
- [Índice en español](${base}es/indice.html)
- [Site completo (app)](${base}): busca, gráficos, página de cada político, empresa, votação, partido, emendas, incentivos e contas do governo federal
- [Minas Nossa](${base}mg/): o recorte de Minas Gerais (governo do estado, deputados estaduais, cidades)
- [Eleição 2026 Aberta](${base}eleicao2026/): eleição para presidente de 2026, urna por urna, com dados do TSE

## Dados em JSON (os mesmos que o site usa)

- [meta.json](${base}data/meta.json): data da atualização, anos, totais e médias
- [politicos.json](${base}data/politicos.json): todos os deputados e senadores, com total gasto por ano, partido, estado e posição pelos votos
- ${base}data/p/<id>.json: um político (gastos por categoria, fornecedores, maiores notas fiscais, equipe, votos)
- [empresas.json](${base}data/empresas.json): empresas que receberam da cota parlamentar
- ${base}data/e/<cnpj>.json: uma empresa (sócios, donos finais, outras empresas dos mesmos donos, quem pagou, emendas, renúncia fiscal)
- [votacoes.json](${base}data/votacoes.json): votações nominais da Câmara e do Senado
- ${base}data/v/<id>.json: uma votação (voto de cada parlamentar, orientação e placar por partido)
- [partidos.json](${base}data/partidos.json): gasto e posição de cada partido

## Fontes oficiais

- Câmara dos Deputados, dados abertos: https://dadosabertos.camara.leg.br
- Senado Federal, dados abertos: https://www12.senado.leg.br/dados-abertos
- Receita Federal, base de CNPJ (via Minha Receita): https://minhareceita.org
- Portal da Transparência (CGU): https://portaldatransparencia.gov.br
- Tesouro Nacional, API do Siconfi: https://apidatalake.tesouro.gov.br/docs/siconfi/
- Tribunal Superior Eleitoral (TSE): https://dadosabertos.tse.jus.br

## Código

- https://github.com/amarigo/segredos-abertos
`);
}
