import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Abrir, Barras, Explain, Loading, OndeVer, useAno, useData } from "../components/ui";
import { MapaUF, NOME_UF, numero } from "../components/graficos";
import { MESES_LONGOS, reais, reaisCurto, type GabineteUf, type Gabinetes } from "../data";

/* Comparação justa da verba de gabinete entre os estados.
   Os dados (somas por estado, população, rendimento) vêm de gabinetes.json; as divisões são feitas aqui. */

type Id = "cadeira" | "teto" | "salarios" | "habitante" | "hab_assessor" | "hab_cadeira";
interface Medida { id: Id; botao: string; titulo: string; valor: (u: GabineteUf, meses: number) => number | null; fmt: (v: number) => string; explica: string; maiorEhMais: string }

const div = (a: number | null | undefined, b: number | null | undefined) => (a != null && b ? a / b : null);
const pct = (v: number) => `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%`;
const vezes = (v: number) => v.toLocaleString("pt-BR", { maximumFractionDigits: v < 10 ? 1 : 0 });

const MEDIDAS: Medida[] = [
  { id: "cadeira", botao: "Por cadeira", titulo: "Verba gasta por cadeira, por mês",
    valor: (u, m) => div(div(u.verba, u.cadeiras), m), fmt: (v) => reais(v),
    explica: "Tudo o que os deputados do estado gastaram com a equipe, dividido pelo número de cadeiras e pelos meses. Quem ocupou a vaga só parte do ano (suplente) entra na mesma cadeira.",
    maiorEhMais: "gasta mais por cadeira" },
  { id: "teto", botao: "Quanto do teto usou", titulo: "Parte do teto da verba que foi usada",
    valor: (u) => div(u.verba, u.teto), fmt: pct,
    explica: "O teto é o mesmo para todo deputado, de qualquer estado. Esta é a comparação mais direta entre deputados: quanto do limite cada bancada escolheu usar.",
    maiorEhMais: "usa mais do teto" },
  { id: "salarios", botao: "Em salários do estado", titulo: "Quantos salários típicos do estado a verba de uma cadeira paga por mês",
    valor: (u, m) => div(div(div(u.verba, u.cadeiras), m), u.rendimento), fmt: (v) => `${vezes(v)} salários`,
    explica: "A verba de um mês por cadeira dividida pelo rendimento médio de quem trabalha no estado (IBGE). Ajusta pela diferença de salários entre os estados: o mesmo valor contrata mais gente onde os salários são menores.",
    maiorEhMais: "paga mais salários do estado" },
  { id: "habitante", botao: "Por habitante", titulo: "Verba da bancada inteira por habitante",
    valor: (u) => div(u.verba, u.populacao), fmt: (v) => reais(v, true),
    explica: "A soma de todos os deputados do estado dividida pela população. Estados pequenos têm mais deputados por habitante (mínimo de 8), por isso costumam ficar no topo.",
    maiorEhMais: "custa mais por habitante" },
  { id: "hab_assessor", botao: "Habitantes por assessor", titulo: "Habitantes para cada secretário parlamentar da bancada (hoje)",
    valor: (u) => div(u.populacao, u.secretarios_hoje), fmt: (v) => numero(Math.round(v)),
    explica: "A população do estado dividida pelo número de secretários parlamentares que os deputados do estado têm hoje. Quanto maior o número, mais gente cada assessor precisa atender.",
    maiorEhMais: "tem mais habitantes por assessor" },
  { id: "hab_cadeira", botao: "Habitantes por deputado", titulo: "Habitantes para cada deputado federal",
    valor: (u) => div(u.populacao, u.cadeiras), fmt: (v) => numero(Math.round(v)),
    explica: "A Constituição dá a cada estado de 8 a 70 deputados. Por isso um deputado de um estado grande representa muito mais gente.",
    maiorEhMais: "tem mais habitantes por deputado" },
];

function trimestre(t: string): string {
  return /^\d{6}$/.test(t) ? `${Number(t.slice(4))}º trimestre de ${t.slice(0, 4)}` : t;
}

export default function GabinetesPage() {
  const { data, error } = useData<Gabinetes>("gabinetes.json");
  const { ano } = useAno();
  const [id, setId] = useState<Id>("teto");
  const [ufAtiva, setUf] = useState("");
  const anosDados = data ? Object.keys(data.anos).sort() : [];
  const a = data ? (data.anos[ano] ? ano : anosDados[anosDados.length - 1]) : "";
  const bloco = data?.anos[a];
  const meses = bloco?.meses || 12;
  const medida = MEDIDAS.find((m) => m.id === id)!;
  const linhas = useMemo(() => (bloco?.ufs || [])
    .map((u) => ({ u, v: medida.valor(u, meses) }))
    .filter((x): x is { u: GabineteUf; v: number } => x.v != null && Number.isFinite(x.v) && x.v > 0)
    .sort((x, y) => y.v - x.v), [bloco, medida, meses]);
  if (!data) return <Loading error={error} />;
  if (!bloco) return <div className="empty">Ainda não há dados da verba de gabinete.</div>;

  const ufs = bloco.ufs;
  const total = (k: keyof GabineteUf) => ufs.reduce((s, u) => s + ((u[k] as number) || 0), 0);
  const br: GabineteUf = { uf: "BR", populacao: total("populacao"), rendimento: null, cadeiras: total("cadeiras"), verba: total("verba"), teto: total("teto"),
    deputados_no_ano: total("deputados_no_ano"), secretarios_hoje: ufs.some((u) => u.secretarios_hoje != null) ? total("secretarios_hoje") : null,
    senadores: total("senadores"), equipe_senado: total("equipe_senado") || null, senadores_com_equipe: total("senadores_com_equipe") };
  const periodo = meses >= 12 ? `em ${a}` : `de janeiro a ${MESES_LONGOS[meses - 1]} de ${a}`;
  const r = data.regras;
  const cotas = r ? Object.entries(r.cota_por_uf).sort((x, y) => x[1] - y[1]) : [];
  const porCad = ufs.filter((u) => u.populacao && u.cadeiras).map((u) => ({ uf: u.uf, v: u.populacao! / u.cadeiras })).sort((x, y) => y.v - x.v);
  const topo = linhas[0], fim = linhas[linhas.length - 1];
  const senado = ufs.map((u) => ({ uf: u.uf, v: div(u.populacao, u.equipe_senado), pessoas: div(u.equipe_senado, u.senadores_com_equipe) }))
    .filter((x): x is { uf: string; v: number; pessoas: number } => x.v != null && x.pessoas != null).sort((x, y) => y.v - x.v);

  return (
    <section className="gabinetes">
      <p className="small"><Link to="/politicos">‹ Políticos</Link></p>
      <h1>Gasto com assessores: comparar de forma justa</h1>
      <Explain>Comparar só quanto cada deputado gastou com a equipe engana. Esta página explica o que entra nessa conta, o que muda de um estado para outro e mostra os estados lado a lado de seis jeitos diferentes, com a população e os salários de cada estado.</Explain>

      <div className="grid gab-perguntas">
        <div className="card">
          <h3>O que entra na verba de gabinete?</h3>
          {r ? <p>Só o salário dos <strong>secretários parlamentares</strong>, os assessores escolhidos pelo deputado. Cada deputado pode ter até {r.max_secretarios}, em Brasília ou no estado, e gastar até <strong>{reais(r.teto_mensal, true)} por mês</strong>{r.salario_min && r.salario_max ? <> com salários de {reais(r.salario_min, true)} a {reais(r.salario_max, true)}</> : null}. 13º, férias e auxílio-alimentação dos assessores são pagos à parte pela Câmara e não aparecem aqui.</p>
            : <p>Só o salário dos secretários parlamentares, os assessores escolhidos pelo deputado, em Brasília ou no estado. 13º, férias e auxílio-alimentação são pagos à parte pela Câmara.</p>}
          <p className="small muted">Fonte: <a href={data.fontes.regras} target="_blank" rel="noreferrer">Câmara, Gastos parlamentares ↗</a></p>
        </div>
        <div className="card">
          <h3>O estado muda o valor?</h3>
          <p>Na Câmara, <strong>não</strong>: o teto e a tabela de salários são os mesmos em São Paulo e em Cuiabá. O que muda é quanto o dinheiro rende. Um salário igual compra mais onde a vida é mais barata, por isso a medida <em>Em salários do estado</em> divide a verba pelo rendimento médio de cada estado.</p>
          {cotas.length > 1 && <p>Quem muda por estado é a <strong>cota parlamentar</strong>, porque inclui as passagens até Brasília: de {reais(cotas[0][1], true)} ({NOME_UF[cotas[0][0]] || cotas[0][0]}) a {reais(cotas[cotas.length - 1][1], true)} ({NOME_UF[cotas[cotas.length - 1][0]] || cotas[cotas.length - 1][0]}) por mês.</p>}
        </div>
        <div className="card">
          <h3>Estado grande precisa de mais assessores?</h3>
          <p>Cada estado tem de 8 a 70 deputados (<a href={data.fontes.constituicao} target="_blank" rel="noreferrer">Constituição, art. 45 ↗</a>) e sempre 3 senadores.
            {porCad.length > 1 && <> Um deputado de {NOME_UF[porCad[0].uf] || porCad[0].uf} representa {numero(Math.round(porCad[0].v))} pessoas; um de {NOME_UF[porCad[porCad.length - 1].uf] || porCad[porCad.length - 1].uf}, {numero(Math.round(porCad[porCad.length - 1].v))}: {vezes(porCad[0].v / porCad[porCad.length - 1].v)} vezes menos.</>}
            {" "}Os estados maiores compensam com mais cadeiras, mas não por inteiro. Por isso somamos a <strong>bancada inteira</strong> e dividimos pela população.</p>
        </div>
      </div>

      <h2>Os estados lado a lado {periodo}</h2>
      <div className="toggle" role="group" aria-label="Comparar por">
        {MEDIDAS.map((m) => <button key={m.id} aria-pressed={id === m.id} onClick={() => setId(m.id)}>{m.botao}</button>)}
      </div>
      <Explain>{medida.explica}</Explain>
      {topo && fim && topo !== fim && <p><strong>{NOME_UF[topo.u.uf] || topo.u.uf}</strong> é o estado que {medida.maiorEhMais}: {medida.fmt(topo.v)}. <strong>{NOME_UF[fim.u.uf] || fim.u.uf}</strong> fica no fim da lista, com {medida.fmt(fim.v)}{id !== "teto" && fim.v > 0 ? <> ({vezes(topo.v / fim.v)} vezes menos)</> : null}.</p>}
      <div className="secao-graficos">
        <div>
          <h3 className="graf-titulo">{medida.titulo}</h3>
          <p className="small muted">Toque num estado para ver o detalhe na tabela.</p>
          <MapaUF valores={Object.fromEntries(linhas.map((x) => [x.u.uf, x.v]))} titulo={medida.titulo} formato={medida.fmt} onUf={(u) => setUf(u === ufAtiva ? "" : u)} ufAtiva={ufAtiva} />
        </div>
        <div>
          <h3 className="graf-titulo">Do maior para o menor</h3>
          <Barras itens={linhas.map((x) => ({ nome: x.u.uf, label: <span className={x.u.uf === ufAtiva ? "gab-ativo" : undefined}>{NOME_UF[x.u.uf] || x.u.uf}</span>, valor: x.v, cor: x.u.uf === ufAtiva ? "var(--gold)" : "var(--s1)" }))} formato={medida.fmt} />
        </div>
      </div>

      <h3>Todos os números {periodo}</h3>
      <div className="table-wrap">
        <table className="gab-tabela">
          <thead><tr>
            <th>Estado</th><th className="num">Deputados</th><th className="num">Habitantes por deputado</th><th className="num">Verba gasta</th>
            <th className="num">Do teto</th><th className="num">Por cadeira, por mês</th><th className="num">Rendimento médio no estado</th>
            <th className="num">Em salários do estado</th><th className="num">Por habitante</th><th className="num">Assessores hoje</th><th className="num">Habitantes por assessor</th>
          </tr></thead>
          <tbody>
            {[...ufs].sort((x, y) => (NOME_UF[x.uf] || x.uf).localeCompare(NOME_UF[y.uf] || y.uf)).concat([br]).map((u) => {
              const pc = div(div(u.verba, u.cadeiras), meses);
              const sal = div(pc, u.rendimento);
              return (
                <tr key={u.uf} className={u.uf === ufAtiva ? "ativa" : u.uf === "BR" ? "total" : undefined}>
                  <td>{u.uf === "BR" ? <strong>Brasil</strong> : <Link to={`/politicos?uf=${u.uf}`}>{NOME_UF[u.uf] || u.uf}</Link>}</td>
                  <td className="num">{u.cadeiras}</td>
                  <td className="num">{u.populacao && u.cadeiras ? numero(Math.round(u.populacao / u.cadeiras)) : "—"}</td>
                  <td className="num">{reaisCurto(u.verba)}</td>
                  <td className="num">{u.teto ? pct(u.verba / u.teto) : "—"}</td>
                  <td className="num">{pc ? reais(pc) : "—"}</td>
                  <td className="num">{u.rendimento ? reais(u.rendimento) : "—"}</td>
                  <td className="num">{sal ? vezes(sal) : "—"}</td>
                  <td className="num">{u.populacao ? reais(u.verba / u.populacao, true) : "—"}</td>
                  <td className="num">{u.secretarios_hoje ?? "—"}</td>
                  <td className="num">{u.populacao && u.secretarios_hoje ? numero(Math.round(u.populacao / u.secretarios_hoje)) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="small muted">Fontes: verba e teto de cada deputado na <a href={data.fontes.regras} target="_blank" rel="noreferrer">Câmara ↗</a>; população {data.ano_populacao && <>(estimativa de {data.ano_populacao}) </>}e rendimento médio{data.trimestre_rendimento && <> ({trimestre(data.trimestre_rendimento)})</>} do <a href={data.fontes.populacao} target="_blank" rel="noreferrer">IBGE ↗</a>; assessores de hoje no <a href={data.fontes.secretarios} target="_blank" rel="noreferrer">arquivo de funcionários da Câmara ↗</a>. Atualizado em {new Date(data.atualizado).toLocaleDateString("pt-BR")}.</p>

      {senado.length > 0 && <>
        <h2>E no Senado?</h2>
        <Explain>No Senado não há um valor em reais por gabinete: o limite é de cargos, pagos pela folha do próprio Senado. Por isso comparamos pessoas. Cada estado tem 3 senadores, seja qual for a população.</Explain>
        <h3 className="graf-titulo">Habitantes para cada pessoa da equipe dos senadores do estado</h3>
        <Barras itens={senado.map((x) => ({ nome: x.uf, label: NOME_UF[x.uf] || x.uf, nota: `${numero(Math.round(x.pessoas))} pessoas por senador, em média`, valor: x.v }))} formato={(v) => numero(Math.round(v))} />
        <p className="small muted">Equipe de cada senador {periodo} pela <a href="https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html" target="_blank" rel="noreferrer">API administrativa do Senado ↗</a>, gabinete e escritório no estado.</p>
      </>}

      <Abrir titulo="Como fizemos as contas">
        <ul>
          <li><strong>Verba gasta</strong>: a soma do que cada deputado do estado gastou da verba de gabinete {periodo}, como a página oficial de cada um mostra. Quem ocupou a vaga só parte do ano (suplente, licenciado) também conta, então a soma é a do estado, não só de quem está no cargo hoje.</li>
          <li><strong>Do teto</strong>: a verba gasta dividida pela soma do que cada deputado podia gastar no tempo em que ficou no cargo.</li>
          <li><strong>Por cadeira, por mês</strong>: a verba gasta dividida pelo número de cadeiras do estado e pelos {meses} meses do período.</li>
          <li><strong>Em salários do estado</strong>: o valor por cadeira e por mês dividido pelo rendimento médio mensal de quem trabalha no estado (PNAD Contínua do IBGE, todos os trabalhos). O IBGE não publica um índice de custo de vida por estado: o IPCA mede só quanto os preços subiram, e só em 16 regiões. O rendimento médio é o número oficial mais próximo do custo de contratar alguém em cada estado.</li>
          <li><strong>Por habitante</strong>: a verba gasta da bancada inteira dividida pela população estimada pelo IBGE.</li>
          <li><strong>Assessores hoje</strong>: secretários parlamentares lotados nos gabinetes dos deputados do estado, pelo arquivo de funcionários da Câmara. É a foto de hoje, não a média do ano.</li>
        </ul>
        <p className="small">O que estas contas não mostram: se o assessor trabalha em Brasília ou no estado (a Câmara não publica), e o 13º, as férias e o auxílio-alimentação, pagos fora da verba.</p>
      </Abrir>

      <OndeVer links={[
        { nome: "Câmara: gastos parlamentares (cota e verba de gabinete)", url: data.fontes.regras, explica: "teto da verba, faixa de salário e cota de cada estado" },
        { nome: "IBGE: população estimada por estado", url: data.fontes.populacao, explica: "tabela 6579" },
        { nome: "IBGE: rendimento médio do trabalho por estado", url: data.fontes.rendimento, explica: "PNAD Contínua, tabela 5436" },
        { nome: "API de dados do IBGE", url: data.fontes.api_ibge, explica: "de onde lemos os dois números acima" },
        { nome: "Câmara: arquivo de funcionários", url: data.fontes.secretarios, explica: "secretários parlamentares de cada deputado" },
        { nome: "Constituição, art. 45", url: data.fontes.constituicao, explica: "de 8 a 70 deputados por estado" },
      ]} />
    </section>
  );
}
