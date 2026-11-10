import { Suspense, lazy, useEffect, useMemo, useState, type ComponentType } from "react";
import { NavLink, Navigate, Route, Routes, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home";
import { MG, SITE } from "./recorte";
import { AnoCtx, AnoSeletor, ErroNaPagina, Loading, useData } from "./components/ui";
import { dataBR, type Meta } from "./data";

/* Cada página vira um arquivo separado, baixado só quando a pessoa abre a página: o início carrega bem menos código
   (no celular, com internet fraca, faz diferença). A página inicial continua no arquivo principal.
   Depois de uma publicação nova, os arquivos antigos deixam de existir; quem estava com o site aberto recarrega uma
   vez para pegar os novos, em vez de ver a mensagem de erro. */
function pagina<T extends ComponentType>(carregar: () => Promise<{ default: T }>) {
  return lazy(() => carregar().then((m) => {
    try { sessionStorage.removeItem("recarregou"); } catch { /* sem armazenamento */ }
    return m;
  }, (erro) => {
    let ja = true;
    try { ja = sessionStorage.getItem("recarregou") === "1"; if (!ja) sessionStorage.setItem("recarregou", "1"); } catch { /* sem armazenamento */ }
    if (!ja) { location.reload(); return new Promise<{ default: T }>(() => {}); }
    throw erro;
  }));
}

const Politicos = pagina(() => import("./pages/Politicos"));
const Rede = pagina(() => import("./pages/Rede"));
const PoliticoPage = pagina(() => import("./pages/Politico"));
const Empresas = pagina(() => import("./pages/Empresas"));
const EmpresaPage = pagina(() => import("./pages/Empresa"));
const Votacoes = pagina(() => import("./pages/Votacoes"));
const VotacaoPage = pagina(() => import("./pages/Votacao"));
const TramitacaoPage = pagina(() => import("./pages/Tramitacao"));
const TribunaisPage = pagina(() => import("./pages/Tribunais"));
const Sobre = pagina(() => import("./pages/Sobre"));
const VerificacaoPage = pagina(() => import("./pages/Verificacao"));
const Partidos = pagina(() => import("./pages/Partidos"));
const GabinetesPage = pagina(() => import("./pages/Gabinetes"));
const Emendas = pagina(() => import("./pages/Emendas"));
const Incentivos = pagina(() => import("./pages/Incentivos"));
const Financas = pagina(() => import("./pages/Financas"));
const Cidades = pagina(() => import("./pages/Cidades"));
const CidadePage = pagina(() => import("./pages/Cidade"));
const Assembleia = pagina(() => import("./pages/Assembleia"));
const DeputadoEstadualPage = pagina(() => import("./pages/DeputadoEstadual"));
const GovernoPage = pagina(() => import("./pages/Governo"));
const DinheiroMinas = pagina(() => import("./pages/DinheiroMinas"));
const Licitacoes = pagina(() => import("./pages/Licitacoes"));
const EmendasEstaduais = pagina(() => import("./pages/EmendasEstaduais"));
const Cultura = pagina(() => import("./pages/Cultura"));
const PainelAreas = pagina(() => import("./pages/PainelAreas"));
const Corrupcao = pagina(() => import("./pages/Corrupcao"));
const CasoCorrupcao = pagina(() => import("./pages/CasoCorrupcao"));

/* Os projetos do Segredos Abertos, publicados lado a lado no mesmo site (/, /mg/, /eleicao2026/ e /terras-raras/).
   Links relativos: funcionam no GitHub Pages e numa cópia local de site/dist. */
const PROJETOS = [
  { id: "brasil", nome: "Brasil", href: MG ? "../" : "./" },
  { id: "mg", nome: "Minas Nossa", href: MG ? "./" : "mg/" },
  { id: "eleicao", nome: "Eleição 2026", href: MG ? "../eleicao2026/" : "eleicao2026/" },
  { id: "terras", nome: "Terras Raras MG", href: MG ? "../terras-raras/" : "terras-raras/" },
];

/* Seletor de língua. A tradução é feita por public/i18n/tradutor.js (carregado no index.html), que troca os textos
   da página pelos do dicionário. Os links levam ao mesmo endereço com ?lang=en ou ?lang=es (o português fica sem). */
const LINGUAS = [
  { id: "pt", sigla: "PT", nome: "Português", lang: "pt-BR" },
  { id: "en", sigla: "EN", nome: "English", lang: "en" },
  { id: "es", sigla: "ES", nome: "Español", lang: "es" },
];
function Linguas() {
  const i18n = window.SA_I18N;
  const atual = i18n?.lingua || "pt";
  return (
    <span className="linguas" translate="no" role="group" aria-label={atual === "en" ? "Language" : "Idioma"}>
      {LINGUAS.map((l) => (
        <a key={l.id} href={i18n ? i18n.endereco(l.id) : "#"} lang={l.lang} hrefLang={l.lang} title={l.nome}
          aria-current={l.id === atual ? "true" : undefined}
          onClick={(e) => { if (i18n) { e.preventDefault(); i18n.trocar(l.id); } }}>{l.sigla}</a>
      ))}
    </span>
  );
}

function Projetos() {
  const atual = MG ? "mg" : "brasil";
  return (
    <nav className="projetos" aria-label="Projetos do Segredos Abertos">
      <div className="wrap">
        <span>Projetos:</span>
        {PROJETOS.map((p) => (
          <a key={p.id} href={p.href} aria-current={p.id === atual ? "page" : undefined}>{p.nome}</a>
        ))}
        <Linguas />
      </div>
    </nav>
  );
}

export default function App() {
  const { pathname } = useLocation();
  // Chaves: scrollTo pode devolver uma Promise em navegadores novos, e o React trataria isso como limpeza
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  const { data: meta } = useData<Meta>("meta.json");
  const [escolhido, setEscolhido] = useState<string>(() => { try { return localStorage.getItem("ano") || ""; } catch { return ""; } });
  const anos = useMemo(() => (meta?.anos || []).map(String), [meta]);
  const ano = anos.includes(escolhido) ? escolhido : anos[anos.length - 1] || "";
  const setAno = (a: string) => { setEscolhido(a); try { localStorage.setItem("ano", a); } catch { /* sem armazenamento */ } };
  return (
    <AnoCtx.Provider value={{ ano, anos, setAno }}>
      <Projetos />
      <header className="top">
        <div className="wrap">
          <Link to="/" className="brand"><img src="./icon.svg" alt="" /><span>{SITE.nome} <span style={{ color: "var(--gold)" }}>{SITE.destaque}</span></span></Link>
          <nav className="nav" aria-label="Principal">
            {!MG && <NavLink to="/dinheiro">Arrecadação e gastos</NavLink>}
            {MG && <NavLink to="/dinheiro">Dinheiro</NavLink>}
            {MG && <NavLink to="/governo">Governo</NavLink>}
            {MG && <NavLink to="/assembleia">Deputados estaduais</NavLink>}
            <NavLink to="/politicos">{MG ? "Federais" : "Políticos"}</NavLink>
            {MG && <NavLink to="/cidades">Cidades</NavLink>}
            {MG && <NavLink to="/emendas-estaduais">Emendas</NavLink>}
            {MG && <NavLink to="/licitacoes">Licitações</NavLink>}
            {MG && <NavLink to="/cultura">Shows e cultura</NavLink>}
            {MG && <NavLink to="/painel">Painel por área</NavLink>}
            <NavLink to="/empresas">Empresas</NavLink>
            <NavLink to="/votacoes">Votações</NavLink>
            <NavLink to="/partidos">Partidos</NavLink>
            {!MG && <NavLink to="/emendas">Emendas</NavLink>}
            {!MG && <NavLink to="/incentivos">Incentivos</NavLink>}
            {!MG && <NavLink to="/corrupcao">Corrupção</NavLink>}
            <NavLink to="/rede">Minha rede</NavLink>
            <NavLink to="/sobre">Como funciona</NavLink>
          </nav>
          {/* A página de arrecadação e o painel por área têm os próprios anos; corrupção, julgamentos do STF e shows e cultura não dependem do ano escolhido: o seletor só confundiria */}
          {pathname !== "/dinheiro" && pathname !== "/licitacoes" && !pathname.startsWith("/corrupcao") && pathname !== "/votacoes/tribunais" && pathname !== "/painel" && pathname !== "/cultura" && <AnoSeletor />}
        </div>
      </header>
      <main className="wrap">
        <ErroNaPagina key={pathname}>
        <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/politicos" element={<Politicos />} />
          <Route path="/p/:id" element={<PoliticoPage />} />
          <Route path="/empresas" element={<Empresas />} />
          <Route path="/e/:cnpj" element={<EmpresaPage />} />
          <Route path="/votacoes" element={<VotacoesInicio />} />
          <Route path="/votacoes/ja-votadas" element={<Votacoes />} />
          {!MG && <Route path="/votacoes/tribunais" element={<TribunaisPage />} />}
          <Route path="/votacoes/em-andamento" element={<EmAndamentoAntigo />} />
          <Route path="/v/:id" element={<VotacaoPage />} />
          <Route path="/partidos" element={<Partidos />} />
          {!MG && <Route path="/gabinetes" element={<GabinetesPage />} />}
          {!MG && <Route path="/dinheiro" element={<Financas />} />}
          {!MG && <Route path="/emendas" element={<Emendas />} />}
          {!MG && <Route path="/incentivos" element={<Incentivos />} />}
          {!MG && <Route path="/corrupcao" element={<Corrupcao />} />}
          {!MG && <Route path="/corrupcao/:id" element={<CasoCorrupcao />} />}
          {MG && <Route path="/cidades" element={<Cidades />} />}
          {MG && <Route path="/cidade/:id" element={<CidadePage />} />}
          {MG && <Route path="/dinheiro" element={<DinheiroMinas />} />}
          {MG && <Route path="/licitacoes" element={<Licitacoes />} />}
          {MG && <Route path="/governo" element={<GovernoPage />} />}
          {MG && <Route path="/assembleia" element={<Assembleia />} />}
          {MG && <Route path="/deputado-estadual/:id" element={<DeputadoEstadualPage />} />}
          {MG && <Route path="/emendas-estaduais" element={<EmendasEstaduais />} />}
          <Route path="/rede" element={<Rede />} />
          {MG && <Route path="/cultura" element={<Cultura />} />}
          {MG && <Route path="/painel" element={<PainelAreas />} />}
          <Route path="/sobre" element={<Sobre />} />
          {!MG && <Route path="/verificacao" element={<VerificacaoPage />} />}
          <Route path="*" element={<div className="empty">Página não encontrada. <Link to="/">Voltar ao início</Link></div>} />
        </Routes>
        </Suspense>
        </ErroNaPagina>
      </main>
      <footer>
        <div className="wrap">
          <span>{SITE.fontes}{meta ? `, atualizados em ${dataBR(meta.atualizado_em)}` : ""}.</span>
          {MG && <span>O Minas Nossa é a parte de Minas Gerais do <a href={SITE.nacional}>Segredos Abertos Brasil</a>.</span>}
          {!MG && <span><Link to="/verificacao">Como conferimos os números</Link>.</span>}
          <span>Projeto independente e sem fins lucrativos. Código aberto em <a href="https://github.com/amarigo/segredos-abertos">GitHub</a>.</span>
        </div>
      </footer>
    </AnoCtx.Provider>
  );
}

/** A aba Votações abre nos projetos em andamento; as já votadas ficam a um clique. Links antigos continuam valendo:
 * "?tema=" era filtro da lista das já votadas, e "/votacoes/em-andamento" era o endereço dos projetos em andamento. */
function VotacoesInicio() {
  const { search } = useLocation();
  if (new URLSearchParams(search).has("tema")) return <Navigate to={`/votacoes/ja-votadas${search}`} replace />;
  return <TramitacaoPage />;
}

function EmAndamentoAntigo() {
  const { search } = useLocation();
  return <Navigate to={`/votacoes${search}`} replace />;
}
