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
/** Posição entre os colegas (1 = maior valor). Empates ficam com a melhor posição. */
const posicao = (v: number, todos: number[]) => 1 + todos.filter((x) => x > v).length;
/** Porcentagem arredondada para baixo: "mais que 99%" só quando é mesmo mais que 99%. */
const pctBaixo = (x: number) => `${Math.floor(x * 100)}%`;

type Lado = "acima" | "abaixo" | "meio";
/** Compara o valor do político com o dos colegas. `todos` inclui o próprio político: ele é tirado uma vez. */
function comparar(v: number, todos: number[], quem: string, verbos = { mais: "Fez mais", menos: "Fez menos" }, fmt = num) {
  const outros = [...todos];
  const i = outros.indexOf(v);
  if (i >= 0) outros.splice(i, 1);
  const n = outros.length;
  const menos = n ? outros.filter((x) => x < v).length / n : 0;
  const mais = n ? outros.filter((x) => x > v).length / n : 0;
  const iguais = 1 - menos - mais;
  const lugar = `${posicao(v, todos)}º de ${todos.length}`;
  let lado: Lado, titulo: string, frase: string;
  if (menos > 0.5) {
    lado = "acima"; titulo = "Acima da maioria";
    frase = menos === 1 ? `${verbos.mais} que todos os outros ${quem}` : `${verbos.mais} que ${pctBaixo(menos)} dos outros ${quem}`;
  } else if (mais > 0.5) {
    lado = "abaixo"; titulo = "Abaixo da maioria";
    frase = mais === 1 ? `${verbos.menos} que todos os outros ${quem}` : `${verbos.menos} que ${pctBaixo(mais)} dos outros ${quem}`;
  } else if (iguais >= 0.5) {
    lado = "meio"; titulo = "Igual à maioria";
    frase = `${pctBaixo(iguais)} dos outros ${quem} também ficaram com ${fmt(v)}`;
  } else {
    lado = "meio"; titulo = "No meio";
    frase = `${pctBaixo(mais)} dos outros ${quem} ficaram acima e ${pctBaixo(menos)} abaixo`;
  }
  return { lado, titulo, frase: `${frase} (${lugar}).`, n };
}

const SETA: Record<Lado, string> = { acima: "▲", abaixo: "▼", meio: "●" };
function Veredito({ c }: { c: ReturnType<typeof comparar> }) {
  return (
    <div className="atu-veredito">
      <p className={`atu-lado atu-${c.lado}`}><span aria-hidden="true">{SETA[c.lado]}</span> {c.titulo}</p>
      <p className="small">{c.frase}</p>
    </div>
  );
}

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
        <Explain>Números oficiais {p.casa === "camara" ? "da Câmara" : "do Senado"}, comparados com os outros {Math.max(colegas.length - 1, 0)} {quem} em exercício hoje que também tinham mandato em {ano}. Quantidade não mede qualidade: um projeto importante pode valer mais que dezenas de requerimentos. Mas mostra quem aparece para trabalhar e quem participa.</Explain>
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
        <p className="muted small" style={{ marginTop: -4 }}>Cada cartão compara {primeiro} com o {quem === "deputados" ? "deputado" : "senador"} típico: o do meio da lista, em que metade dos {quem} fez mais e metade fez menos.</p>
        <div className="atu-grade atu-grade-4">
          {METRICAS_ATUACAO.filter((m) => eu[m.chave] != null && !(m.chave === "autoria" && eu.projetos != null)).map((m) => (
            <Metrica key={m.chave} nome={m.nome} explica={m.explica[p.casa]} quem={quem} eu={primeiro} v={eu[m.chave]!}
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
      <Veredito c={comparar(minha, taxas, quem, { mais: "Presença maior", menos: "Presença menor" }, pct)} />
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

function Metrica({ nome, explica, quem, eu, v, todos }: { nome: string; explica: string; quem: string; eu: string; v: number; todos: number[] }) {
  const med = Math.round(mediana(todos)); // contagens: o típico é um número inteiro
  const escala = Math.max(v, med, 1);
  const c = comparar(v, todos, quem);
  const tipico = quem === "deputados" ? "Deputado típico" : "Senador típico";
  return (
    <div className="card atu-card">
      <div className="atu-topo"><h3>{nome}</h3><span className="atu-valor num">{num(v)}</span></div>
      {todos.length > 1 && <>
        <Veredito c={c} />
        <div className="atu-comp" role="img" aria-label={`${nome}: ${eu} ${num(v)}; ${tipico.toLowerCase()} ${num(med)}.`}>
          <span className="small">{eu}</span>
          <span className="atu-comp-trilha"><span className="atu-comp-eu" style={{ width: `${(v / escala) * 100}%` }} /></span>
          <span className="small num">{num(v)}</span>
          <span className="small muted">{tipico}</span>
          <span className="atu-comp-trilha"><span className="atu-comp-tipico" style={{ width: `${(med / escala) * 100}%` }} /></span>
          <span className="small num muted">{num(med)}</span>
        </div>
      </>}
      <p className="muted small">{explica}</p>
    </div>
  );
}

function Fonte({ casa, id, ano }: { casa: Casa; id: string; ano: string }): ReactNode {
  const n = id.split("-")[1];
  return casa === "camara"
    ? <p className="muted small">Fontes: <a href={`https://www.camara.leg.br/deputados/${n}?ano=${ano}`} target="_blank" rel="noreferrer">página oficial do deputado na Câmara, ano {ano} ↗</a>, bloco "Atuação no Plenário e Comissões" (presença, relatorias, votações e discursos), e <a href="https://dadosabertos.camara.leg.br/swagger/api.html?tab=staticfile" target="_blank" rel="noreferrer">arquivos de proposições dos dados abertos da Câmara ↗</a> (projetos e requerimentos, com a ordem de assinatura de cada autor).</p>
    : <p className="muted small">Fonte: <a href="https://legis.senado.leg.br/dadosabertos/" target="_blank" rel="noreferrer">dados abertos do Senado ↗</a> (propostas, relatorias, pronunciamentos e votações nominais do ano).</p>;
}
