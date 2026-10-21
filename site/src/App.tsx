import { useEffect } from "react";
import { NavLink, Route, Routes, Link, useLocation } from "react-router-dom";
import Home from "./pages/Home";
import Politicos from "./pages/Politicos";
import PoliticoPage from "./pages/Politico";
import Empresas from "./pages/Empresas";
import EmpresaPage from "./pages/Empresa";
import Votacoes from "./pages/Votacoes";
import VotacaoPage from "./pages/Votacao";
import Sobre from "./pages/Sobre";
import { useData } from "./components/ui";
import { dataBR, type Meta } from "./data";

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  const { data: meta } = useData<Meta>("meta.json");
  return (
    <>
      <header className="top">
        <div className="wrap">
          <Link to="/" className="brand"><img src="./icon.svg" alt="" /><span>Segredos Abertos <span style={{ color: "var(--gold)" }}>Brasil</span></span></Link>
          <nav className="nav" aria-label="Principal">
            <NavLink to="/politicos">Políticos</NavLink>
            <NavLink to="/empresas">Empresas</NavLink>
            <NavLink to="/votacoes">Votações</NavLink>
            <NavLink to="/sobre">Como funciona</NavLink>
          </nav>
        </div>
      </header>
      <main className="wrap">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/politicos" element={<Politicos />} />
          <Route path="/p/:id" element={<PoliticoPage />} />
          <Route path="/empresas" element={<Empresas />} />
          <Route path="/e/:cnpj" element={<EmpresaPage />} />
          <Route path="/votacoes" element={<Votacoes />} />
          <Route path="/v/:id" element={<VotacaoPage />} />
          <Route path="/sobre" element={<Sobre />} />
          <Route path="*" element={<div className="empty">Página não encontrada. <Link to="/">Voltar ao início</Link></div>} />
        </Routes>
      </main>
      <footer>
        <div className="wrap">
          <span>Dados oficiais da Câmara dos Deputados, do Senado Federal e da Receita Federal{meta ? `, atualizados em ${dataBR(meta.atualizado_em)}` : ""}.</span>
          <span>Projeto independente e sem fins lucrativos. Código aberto em <a href="https://github.com/amarigo/segredos-abertos">GitHub</a>.</span>
        </div>
      </footer>
    </>
  );
}
