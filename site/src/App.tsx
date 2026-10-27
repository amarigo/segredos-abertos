import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home";
import Politicos from "./pages/Politicos";
import PoliticoPage from "./pages/Politico";
import Empresas from "./pages/Empresas";
import EmpresaPage from "./pages/Empresa";
import Votacoes from "./pages/Votacoes";
import VotacaoPage from "./pages/Votacao";
import TramitacaoPage from "./pages/Tramitacao";
import Sobre from "./pages/Sobre";
import Partidos from "./pages/Partidos";
import Emendas from "./pages/Emendas";
import Incentivos from "./pages/Incentivos";
import Financas from "./pages/Financas";
import Cidades from "./pages/Cidades";
import CidadePage from "./pages/Cidade";
import Assembleia from "./pages/Assembleia";
import DeputadoEstadualPage from "./pages/DeputadoEstadual";
import GovernoPage from "./pages/Governo";
import EmendasEstaduais from "./pages/EmendasEstaduais";
import { MG, SITE } from "./recorte";
import { AnoCtx, AnoSeletor, ErroNaPagina, useData } from "./components/ui";
import { dataBR, type Meta } from "./data";

/* Os projetos do Segredos Abertos, publicados lado a lado no mesmo site (/, /mg/ e /eleicao2026/).
   Links relativos: funcionam no GitHub Pages e numa cópia local de site/dist. */
const PROJETOS = [
  { id: "brasil", nome: "Brasil", href: MG ? "../" : "./" },
  { id: "mg", nome: "Minas Nossa", href: MG ? "./" : "mg/" },
  { id: "eleicao", nome: "Eleição 2026", href: MG ? "../eleicao2026/" : "eleicao2026/" },
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
            {MG && <NavLink to="/governo">Governo</NavLink>}
            {MG && <NavLink to="/assembleia">Deputados estaduais</NavLink>}
            <NavLink to="/politicos">{MG ? "Federais" : "Políticos"}</NavLink>
            {MG && <NavLink to="/cidades">Cidades</NavLink>}
            {MG && <NavLink to="/emendas-estaduais">Emendas</NavLink>}
            <NavLink to="/empresas">Empresas</NavLink>
            <NavLink to="/votacoes">Votações</NavLink>
            <NavLink to="/partidos">Partidos</NavLink>
            {!MG && <NavLink to="/emendas">Emendas</NavLink>}
            {!MG && <NavLink to="/incentivos">Incentivos</NavLink>}
            <NavLink to="/sobre">Como funciona</NavLink>
          </nav>
          <AnoSeletor />
        </div>
      </header>
      <main className="wrap">
        <ErroNaPagina key={pathname}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/politicos" element={<Politicos />} />
          <Route path="/p/:id" element={<PoliticoPage />} />
          <Route path="/empresas" element={<Empresas />} />
          <Route path="/e/:cnpj" element={<EmpresaPage />} />
          <Route path="/votacoes" element={<Votacoes />} />
          <Route path="/votacoes/em-andamento" element={<TramitacaoPage />} />
          <Route path="/v/:id" element={<VotacaoPage />} />
          <Route path="/partidos" element={<Partidos />} />
          {!MG && <Route path="/dinheiro" element={<Financas />} />}
          {!MG && <Route path="/emendas" element={<Emendas />} />}
          {!MG && <Route path="/incentivos" element={<Incentivos />} />}
          {MG && <Route path="/cidades" element={<Cidades />} />}
          {MG && <Route path="/cidade/:id" element={<CidadePage />} />}
          {MG && <Route path="/governo" element={<GovernoPage />} />}
          {MG && <Route path="/assembleia" element={<Assembleia />} />}
          {MG && <Route path="/deputado-estadual/:id" element={<DeputadoEstadualPage />} />}
          {MG && <Route path="/emendas-estaduais" element={<EmendasEstaduais />} />}
          <Route path="/sobre" element={<Sobre />} />
          <Route path="*" element={<div className="empty">Página não encontrada. <Link to="/">Voltar ao início</Link></div>} />
        </Routes>
        </ErroNaPagina>
      </main>
      <footer>
        <div className="wrap">
          <span>{SITE.fontes}{meta ? `, atualizados em ${dataBR(meta.atualizado_em)}` : ""}.</span>
          {MG && <span>O Minas Nossa é a parte de Minas Gerais do <a href={SITE.nacional}>Segredos Abertos Brasil</a>.</span>}
          <span>Projeto independente e sem fins lucrativos. Código aberto em <a href="https://github.com/amarigo/segredos-abertos">GitHub</a>.</span>
        </div>
      </footer>
    </AnoCtx.Provider>
  );
}
