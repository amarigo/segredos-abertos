import { useEffect, useMemo, useState } from "react";
import { NavLink, Route, Routes, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home";
import Politicos from "./pages/Politicos";
import PoliticoPage from "./pages/Politico";
import Empresas from "./pages/Empresas";
import EmpresaPage from "./pages/Empresa";
import Votacoes from "./pages/Votacoes";
import VotacaoPage from "./pages/Votacao";
import Sobre from "./pages/Sobre";
import Partidos from "./pages/Partidos";
import Emendas from "./pages/Emendas";
import { AnoCtx, AnoSeletor, ErroNaPagina, useData } from "./components/ui";
import { dataBR, type Meta } from "./data";

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
      <header className="top">
        <div className="wrap">
          <Link to="/" className="brand"><img src="./icon.svg" alt="" /><span>Segredos Abertos <span style={{ color: "var(--gold)" }}>Brasil</span></span></Link>
          <nav className="nav" aria-label="Principal">
            <NavLink to="/politicos">Políticos</NavLink>
            <NavLink to="/empresas">Empresas</NavLink>
            <NavLink to="/votacoes">Votações</NavLink>
            <NavLink to="/partidos">Partidos</NavLink>
            <NavLink to="/emendas">Emendas</NavLink>
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
          <Route path="/v/:id" element={<VotacaoPage />} />
          <Route path="/partidos" element={<Partidos />} />
          <Route path="/emendas" element={<Emendas />} />
          <Route path="/sobre" element={<Sobre />} />
          <Route path="*" element={<div className="empty">Página não encontrada. <Link to="/">Voltar ao início</Link></div>} />
        </Routes>
        </ErroNaPagina>
      </main>
      <footer>
        <div className="wrap">
          <span>Dados oficiais da Câmara dos Deputados, do Senado Federal, da Receita Federal e do Portal da Transparência{meta ? `, atualizados em ${dataBR(meta.atualizado_em)}` : ""}.</span>
          <span>Projeto independente e sem fins lucrativos. Código aberto em <a href="https://github.com/amarigo/segredos-abertos">GitHub</a>.</span>
        </div>
      </footer>
    </AnoCtx.Provider>
  );
}
