import type { ReactNode } from "react";
import { Explain, Loading, useAno, useData } from "../components/ui";
import { METRICAS_ATUACAO, atuacaoAtiva, taxaPresenca, type Atuacao, type Casa, type Politico, type Resumo } from "../data";

const num = (x: number) => x.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const pct = (x: number) => `${Math.round(x * 100)}%`;

function mediana(v: number[]): number {
  const s = [...v].sort((a, b) => a - b);
  const m = s.length >> 1;
  return !s.length ? 0 : s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
function quantil(v: number[], q: number): number {
  const s = [...v].sort((a, b) => a - b);
  return s.length ? s[Math.min(s.length - 1, Math.floor(q * s.length))] : 0;
}
/** Posição entre os colegas (1 = maior valor). Empates ficam com a melhor posição. */
const posicao = (v: number, todos: number[]) => 1 + todos.filter((x) => x > v).length;

const COR = { presente: "var(--sim)", justificada: "var(--gold)", injustificada: "var(--nao)" };

/* Aba "Atuação" do político: propostas, relatorias, votações, discursos e presença, comparados com os colegas da mesma Casa. */
export function AtuacaoPolitico({ p }: { p: Politico }) {
  const { ano } = useAno();
  const { data: todos, error } = useData<Resumo[]>("politicos.json");
  if (!todos) return <Loading error={error} />;
  const eu = p.por_ano[ano]?.atuacao;
  const quem = p.casa === "camara" ? "deputados" : "senadores";
  const colegas = todos.filter((r) => r.casa === p.casa).map((r) => r.por_ano[ano]?.atuacao).filter(atuacaoAtiva);
  if (!atuacaoAtiva(eu)) {
    return <div className="empty">Não há dados de atuação de {p.nome} em {ano}. Isso acontece quando {p.casa === "camara" ? "o deputado" : "o senador"} não estava no cargo no ano. Escolha outro ano no topo da página.</div>;
  }
  const primeiro = p.nome.split(" ")[0];
  return (
    <>
      <section>
        <h2>Atuação em {ano}</h2>
        <Explain>Números oficiais {p.casa === "camara" ? "da Câmara" : "do Senado"}, comparados com os {colegas.length} {quem} que estavam no cargo em {ano}. Quantidade não mede qualidade: um projeto importante pode valer mais que dezenas de requerimentos. Mas mostra quem aparece para trabalhar e quem participa.</Explain>
      </section>

      <section>
        <h2>Presença</h2>
        <div className="atu-legenda small" aria-hidden="true">
          <span><i style={{ background: COR.presente }} />Presente</span>
          <span><i style={{ background: COR.justificada }} />Ausência justificada</span>
          <span><i style={{ background: COR.injustificada }} />Ausência sem justificativa</span>
        </div>
        <div className="atu-grade">
          {eu.plenario && <Presenca titulo="No Plenário" nome={primeiro} quem={quem} eu={eu.plenario} colegas={colegas.map((c) => c.plenario)}
            unidade={p.casa === "camara" ? ["dia", "dias"] : ["votação", "votações"]}
            explica={p.casa === "camara" ? "Dias de sessão deliberativa no Plenário, em que se vota." : "Contado pelas votações nominais do Plenário: em cada uma, o Senado registra se o senador votou, se estava em missão ou licença, ou se faltou."} />}
          {eu.comissoes && sum(eu.comissoes) > 0 && <Presenca titulo="Nas comissões" nome={primeiro} quem={quem} eu={eu.comissoes} colegas={colegas.map((c) => c.comissoes)}
            unidade={["reunião", "reuniões"]} explica="Reuniões das comissões de que é membro, onde os projetos são discutidos antes de ir ao Plenário." />}
        </div>
        {p.casa === "senado" && <p className="muted small">O Senado não publica a presença nas comissões por senador nos dados abertos.</p>}
      </section>

      <section>
        <h2>Trabalho legislativo</h2>
        <p className="muted small" style={{ marginTop: -4 }}>A barra mostra {primeiro}. A linha marca a mediana: metade dos {quem} fez mais que isso, metade fez menos.</p>
        <div className="atu-grade atu-grade-4">
          {METRICAS_ATUACAO.filter((m) => eu[m.chave] != null).map((m) => (
            <Metrica key={m.chave} nome={m.nome} explica={m.explica[p.casa]} quem={quem} v={eu[m.chave]!}
              todos={colegas.map((c) => c[m.chave]).filter((x): x is number => x != null)} />
          ))}
        </div>
        <Fonte casa={p.casa} id={p.id} ano={ano} />
      </section>
    </>
  );
}

const sum = (x: number[]) => x[0] + x[1] + x[2];

function Presenca({ titulo, nome, quem, eu, colegas, unidade, explica }: {
  titulo: string; nome: string; quem: string; eu: [number, number, number]; colegas: (Atuacao["plenario"])[];
  unidade: [string, string]; explica: string;
}) {
  const taxas = colegas.map(taxaPresenca).filter((x): x is number => x != null);
  const minha = taxaPresenca(eu) ?? 0;
  const com = colegas.filter((c): c is [number, number, number] => !!c && sum(c) > 0);
  // Média das proporções de cada colega, para comparar a barra inteira
  const media = [0, 1, 2].map((i) => com.reduce((a, c) => a + c[i] / sum(c), 0) / (com.length || 1)) as [number, number, number];
  const u = (n: number) => `${num(n)} ${n === 1 ? unidade[0] : unidade[1]}`;
  return (
    <div className="card atu-card">
      <div className="atu-topo"><h3>{titulo}</h3><span className="atu-valor">{pct(minha)}</span></div>
      <p className="small muted atu-pos">{posicao(minha, taxas)}º de {taxas.length} {quem} · mediana {pct(mediana(taxas))}</p>
      <BarraPresenca rotulo={nome} partes={eu} texto={(i) => [`${u(eu[0])} presente`, `${u(eu[1])} com ausência justificada`, `${u(eu[2])} sem justificativa`][i]} />
      <BarraPresenca rotulo={`Média dos ${quem}`} partes={media} texto={(i) => `${pct(media[i])} ${["presente", "com ausência justificada", "sem justificativa"][i]}`} />
      <p className="small">{u(eu[0])} presente · {num(eu[1])} {eu[1] === 1 ? "ausência justificada" : "ausências justificadas"} · <strong>{num(eu[2])} sem justificativa</strong></p>
      <p className="muted small">{explica}</p>
    </div>
  );
}

function BarraPresenca({ rotulo, partes, texto }: { rotulo: string; partes: number[]; texto: (i: number) => string }) {
  const t = partes.reduce((a, b) => a + b, 0) || 1;
  const cores = [COR.presente, COR.justificada, COR.injustificada];
  return (
    <div className="atu-pres">
      <span className="small">{rotulo}</span>
      <div className="atu-pres-barra" role="img" aria-label={`${rotulo}: ${partes.map((_, i) => texto(i)).join(", ")}`}>
        {partes.map((x, i) => x > 0 && <span key={i} style={{ flexGrow: x / t, background: cores[i] }} title={texto(i)} />)}
      </div>
    </div>
  );
}

function Metrica({ nome, explica, quem, v, todos }: { nome: string; explica: string; quem: string; v: number; todos: number[] }) {
  const med = mediana(todos);
  const escala = Math.max(v, quantil(todos, 0.9), med, 1) * 1.1;
  const pos = posicao(v, todos);
  const menos = todos.filter((x) => x < v).length;
  const frase = !todos.length ? "" : v === 0 && menos === 0 ? `Nenhum registro, como ${todos.filter((x) => x === 0).length - 1} outros ${quem}`
    : `Mais que ${pct(menos / todos.length)} dos ${quem}`;
  return (
    <div className="card atu-card">
      <div className="atu-topo"><h3>{nome}</h3><span className="atu-valor num">{num(v)}</span></div>
      <p className="small muted atu-pos">{pos}º de {todos.length} · mediana {num(med)}</p>
      <div className="atu-trilha" role="img" aria-label={`${nome}: ${num(v)}. Mediana dos ${quem}: ${num(med)}.`}>
        <span className="atu-barra" style={{ width: `${Math.min(1, v / escala) * 100}%` }} title={`${num(v)}`} />
        <span className="atu-mediana" style={{ left: `${(med / escala) * 100}%` }} title={`Mediana dos ${quem}: ${num(med)}`} />
      </div>
      {frase && <p className="small">{frase}.</p>}
      <p className="muted small">{explica}</p>
    </div>
  );
}

function Fonte({ casa, id, ano }: { casa: Casa; id: string; ano: string }): ReactNode {
  const n = id.split("-")[1];
  return casa === "camara"
    ? <p className="muted small">Fonte: <a href={`https://www.camara.leg.br/deputados/${n}?ano=${ano}`} target="_blank" rel="noreferrer">página oficial do deputado na Câmara, ano {ano} ↗</a>, bloco "Atuação no Plenário e Comissões".</p>
    : <p className="muted small">Fonte: <a href="https://legis.senado.leg.br/dadosabertos/" target="_blank" rel="noreferrer">dados abertos do Senado ↗</a> (propostas, relatorias, pronunciamentos e votações nominais do ano).</p>;
}
