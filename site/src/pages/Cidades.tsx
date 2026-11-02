import { Link } from "react-router-dom";
import { Explain, Loading, OndeVer, useData } from "../components/ui";
import { corPartido, partidoComHoje, type CidadeResumo } from "../data";

export default function Cidades() {
  const { data, error } = useData<CidadeResumo[]>("cidades.json");
  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Cidades</h1>
      <Explain>Para cada cidade, mostramos quem foi prefeito e quais partidos tiveram vereadores desde 1997, e como a cidade votou para presidente, governador, senador e deputados. Assim dá para saber de qual partido cobrar o que foi feito, e o que deixou de ser feito, em cada época.</Explain>
      <div className="grid" style={{ marginTop: 16 }}>
        {data.map((c) => (
          <Link key={c.id} to={`/cidade/${c.id}`} className="card cidade-card">
            <span className="eyebrow">{c.uf}</span>
            <strong className="cidade-nome">{c.nome}</strong>
            {c.prefeito ? (
              <span className="small"><i className="partido-cor" style={{ background: corPartido(c.prefeito.partido_hoje) }} />
                Prefeito{c.desde ? ` desde ${c.desde}` : ""}: <strong>{c.prefeito.nome}</strong> ({partidoComHoje(c.prefeito.partido, c.prefeito.partido_hoje)})</span>
            ) : <span className="small muted">Sem dados do prefeito atual</span>}
            {c.vereadores != null && <span className="small muted">{c.vereadores} vereadores na Câmara Municipal</span>}
          </Link>
        ))}
      </div>
      <p className="muted small">Começamos por Itajubá e Paraisópolis. Outras cidades de Minas entram nas próximas etapas.</p>
      <OndeVer links={[
        { nome: "Resultados das eleições no TSE", url: "https://dadosabertos.tse.jus.br/dataset/?groups=resultados", explica: "prefeitos, vereadores e votos desde 1996" },
        { nome: "Contas das prefeituras no SICONFI (Tesouro Nacional)", url: "https://siconfi.tesouro.gov.br/siconfi/pages/public/declaracao/declaracao_list.jsf", explica: "o que cada prefeitura arrecada e gasta" },
        { nome: "Emendas estaduais na ALMG", url: "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/", explica: "dinheiro indicado pelos deputados estaduais para cada cidade" },
      ]} />
    </section>
  );
}
