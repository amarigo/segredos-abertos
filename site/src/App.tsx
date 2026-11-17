import { Suspense, lazy, useEffect, useMemo, useState, type ComponentType } from "react";
import { Navigate, Route, Routes, Link, useLocation } from "react-router-dom";
import { Container } from "@mantine/core";
import { AbasDaSecao, Rodape, Topo, VoltarAoMenu } from "./components/Casca";
import Home from "./pages/Home";
import { MG } from "./recorte";
import { AnoCtx, ErroNaPagina, Loading, useData } from "./components/ui";
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
const HistoricoPage = pagina(() => import("./pages/Historico"));
const PatrimonioPage = pagina(() => import("./pages/Patrimonio"));
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
const PunicoesPage = pagina(() => import("./pages/Punicoes"));
const Representantes = pagina(() => import("./pages/Representantes"));

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
      <Topo />
      <Container size="lg" component="main" className="wrap">
        <AbasDaSecao />
        <ErroNaPagina key={pathname}>
        <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/quem" element={<Representantes />} />
          <Route path="/quem/:ue" element={<Representantes />} />
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
          {!MG && <Route path="/historico" element={<HistoricoPage />} />}
          {!MG && <Route path="/patrimonio" element={<PatrimonioPage />} />}
          {!MG && <Route path="/dinheiro" element={<Financas />} />}
          {!MG && <Route path="/emendas" element={<Emendas />} />}
          {!MG && <Route path="/incentivos" element={<Incentivos />} />}
          {!MG && <Route path="/corrupcao" element={<Corrupcao />} />}
          {!MG && <Route path="/corrupcao/punicoes" element={<PunicoesPage />} />}
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
      </Container>
      <Rodape atualizado={meta ? dataBR(meta.atualizado_em) : undefined} />
      <VoltarAoMenu />
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
