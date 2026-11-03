import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { Abrir, Barras, Loading, OndeVer, useAno, useData } from "../components/ui";
import { atuacaoAtiva, corPartido, reaisCurto, taxaPresenca, type Resumo } from "../data";
import { PessoaLinha, norm } from "./Home";
import { AvisosFim } from "../components/Selo";
import { MapaUF, Rosca, prepararFatias } from "../components/graficos";
import { COR_LADO, LADOS, ladoPelosVotos } from "../partidos";

type Ordem = "total" | "nome" | "posicao" | "presenca" | "autoria" | "relatadas" | "discursos";
const ROTULO: Record<string, [string, string]> = { autoria: ["proposta", "propostas"], relatadas: ["relatoria", "relatorias"], discursos: ["discurso", "discursos"] };

export default function Politicos() {
  const { data, error } = useData<Resumo[]>("politicos.json");
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [params] = useSearchParams();
  const [uf, setUf] = useState(params.get("uf") || "");
  const [partido, setPartido] = useState(params.get("partido") || "");
  const [situacao, setSituacao] = useState("");
  const [ordem, setOrdem] = useState<Ordem>("total");
  const { ano } = useAno();
  const t = (p: Resumo) => p.por_ano[ano]?.total || 0;
  /** Valor da atuação no ano para ordenar (-1 quando não há dado: vai para o fim da lista). */
  const atu = (p: Resumo): number => {
    const a = p.por_ano[ano]?.atuacao;
    if (!atuacaoAtiva(a)) return -1;
    if (ordem === "presenca") return taxaPresenca(a.plenario) ?? -1;
    return (a as Record<string, unknown>)[ordem] as number ?? -1;
  };
  const extra = (p: Resumo) => {
    if (ordem === "posicao") return p.rotulo;
    if (ordem === "total" || ordem === "nome") return reaisCurto(t(p));
    const v = atu(p);
    if (v < 0) return "sem dado";
    if (ordem === "presenca") return `${Math.round(v * 100)}%`;
    return `${v.toLocaleString("pt-BR")} ${v === 1 ? ROTULO[ordem][0] : ROTULO[ordem][1]}`;
  };

  const ufs = useMemo(() => [...new Set((data || []).map((p) => p.uf))].sort(), [data]);
  const partidos = useMemo(() => [...new Set((data || []).map((p) => p.partido))].sort(), [data]);
  const lista = useMemo(() => {
    let l = (data || []).filter((p) => (!casa || p.casa === casa) && (!uf || p.uf === uf) && (!partido || p.partido === partido)
      && (!situacao || (situacao === "exercicio") === (p.em_exercicio !== false))
      && (!q || [p.nome, ...(p.outros_nomes || [])].some((n) => norm(n).includes(norm(q)))));
    l = l.slice().sort((a, b) => ordem === "nome" ? a.nome.localeCompare(b.nome)
      : ordem === "posicao" ? (a.posicao ?? 9) - (b.posicao ?? 9) : ordem === "total" ? t(b) - t(a) : atu(b) - atu(a) || a.nome.localeCompare(b.nome));
    return l;
  }, [data, q, casa, uf, partido, situacao, ordem, ano]);

  // Para os gráficos: os mesmos filtros, menos o de estado (o mapa mostra todos os estados)
  const semUf = useMemo(() => (data || []).filter((p) => (!casa || p.casa === casa) && (!partido || p.partido === partido)
    && (!situacao || (situacao === "exercicio") === (p.em_exercicio !== false))), [data, casa, partido, situacao]);
  const mediaUf = useMemo(() => {
    const s: Record<string, [number, number]> = {};
    semUf.forEach((p) => { const v = t(p); if (v > 0) { const x = (s[p.uf] ||= [0, 0]); x[0] += v; x[1] += 1; } });
    return Object.fromEntries(Object.entries(s).map(([u, [a, n]]) => [u, a / n]));
  }, [semUf, ano]);
  const lados = useMemo(() => {
    const c: Record<string, number> = {};
    lista.forEach((p) => { const l = p.posicao == null ? "Sem posição" : ladoPelosVotos(p.posicao); c[l] = (c[l] || 0) + 1; });
    return prepararFatias([...LADOS, "Sem posição"].map((l) => ({ nome: l, valor: c[l] || 0, cor: COR_LADO[l] })), 9);
  }, [lista]);
  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Políticos</h1>
      <div className="secao-graficos">
        {ufs.length > 1 && (
          <div>
            <h3 className="graf-titulo">Média de cota por parlamentar em {ano}, por estado</h3>
            <p className="small muted">Toque num estado para ver só os parlamentares dele.{uf && <> <button className="link" onClick={() => setUf("")}>Mostrar todos os estados</button></>}</p>
            <MapaUF valores={mediaUf} titulo={`Média de cota por parlamentar em ${ano}, por estado`} onUf={(u) => setUf(u === uf ? "" : u)} ufAtiva={uf} />
          </div>
        )}
        <div>
          <h3 className="graf-titulo">Da esquerda à direita, pelos votos</h3>
          <p className="small muted">Os {lista.length} parlamentares da lista abaixo, pelo lado em que ficam nas votações nominais. <a href="#/sobre">Entenda o cálculo</a>.</p>
          <Rosca fatias={lados} titulo="Parlamentares por lado" formato={(v) => `${v} parlamentar${v === 1 ? "" : "es"}`} centroRotulo="Parlamentares" centro={String(lista.length)} />
        </div>
      </div>
      <div className="search">
        <input id="filtro-nome" aria-label="Nome" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome" />
        <select id="filtro-casa" aria-label="Casa" value={casa} onChange={(e) => setCasa(e.target.value)}>
          <option value="">Câmara e Senado</option><option value="camara">Deputados federais</option><option value="senado">Senadores</option>
        </select>
        {ufs.length > 1 && (
          <select id="filtro-uf" aria-label="Estado" value={uf} onChange={(e) => setUf(e.target.value)}>
            <option value="">Todos os estados</option>{ufs.map((u) => <option key={u}>{u}</option>)}
          </select>
        )}
        <select id="filtro-partido" aria-label="Partido" value={partido} onChange={(e) => setPartido(e.target.value)}>
          <option value="">Todos os partidos</option>{partidos.map((u) => <option key={u}>{u}</option>)}
        </select>
        <select id="filtro-situacao" aria-label="Situação" value={situacao} onChange={(e) => setSituacao(e.target.value)}>
          <option value="">No cargo hoje e quem já saiu</option><option value="exercicio">Só quem está no cargo hoje</option>
          <option value="fora">Só quem saiu do cargo</option>
        </select>
        <select id="filtro-ordem" aria-label="Ordenar" value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
          <option value="total">Maior gasto de cota em {ano}</option><option value="nome">Nome</option><option value="posicao">Da esquerda para a direita</option>
          <option value="presenca">Maior presença no Plenário em {ano}</option><option value="autoria">Mais propostas apresentadas em {ano}</option>
          <option value="relatadas">Mais relatorias em {ano}</option><option value="discursos">Mais discursos em {ano}</option>
        </select>
      </div>
      {lista.some((p) => t(p) > 0) && <Abrir aberto titulo={`Gráfico: quem mais gastou da cota em ${ano}`}>
        <Barras itens={lista.slice().sort((a, b) => t(b) - t(a)).slice(0, 15).filter((p) => t(p) > 0).map((p) => ({
          label: <Link to={`/p/${p.id}`}>{p.nome}</Link>, nota: `${p.partido}-${p.uf} · ${p.casa === "senado" ? "senador" : "deputado federal"}`, valor: t(p), cor: corPartido(p.partido) }))} />
        <p className="muted small">Os 15 maiores gastos com os filtros escolhidos acima. Clique no nome para abrir cada gasto, nota por nota.</p>
      </Abrir>}
      <p className="muted small">{lista.length} resultado{lista.length === 1 ? "" : "s"}. A lista traz todos que tiveram mandato nesta legislatura, inclusive suplentes que já devolveram a vaga e quem se licenciou: os gastos e votos do período no cargo continuam contando.</p>
      <div className="list">
        {lista.map((p) => <PessoaLinha key={p.id} p={p} extra={extra(p)} />)}
      </div>
      <OndeVer links={[
        { nome: "Gastos da cota parlamentar na Câmara", url: "https://www.camara.leg.br/transparencia/gastos-parlamentares", explica: "cada nota de cada deputado federal" },
        { nome: "Dados abertos da Câmara", url: "https://dadosabertos.camara.leg.br/swagger/api.html", explica: "a API oficial de deputados, despesas e votações" },
        { nome: "Dados abertos do Senado", url: "https://www12.senado.leg.br/dados-abertos", explica: "senadores, gastos (CEAPS) e votações" },
      ]} />
      <AvisosFim secao="cota" />
    </section>
  );
}
