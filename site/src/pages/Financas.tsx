import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useData, useTip } from "../components/ui";
import { linkSeguro, reais } from "../data";
import "./financas.css";
import { AvisosFim } from "../components/Selo";

/* Formato de data/financas/ (gerado por etl/sa_etl/financas.py) */
type Nivel = "verde" | "amarelo" | "vermelho" | "sem_dados";
interface Kpi {
  id: string; titulo: string; valor: number | null; formato: "pct" | "pct_limite" | "pct_var"; nivel: Nivel;
  regra: string; explica: string; fonte: string; link: string; detalhe: [string, number][]; grupo: string;
}
interface Receita { id: string; nome: string; explica: string; tipo: "propria" | "divida" | "refinanciamento"; valor: number; previsto: number }
interface DespesaGrupo { id: string; nome: string; explica: string; liquidado: number; pago: number; empenhado: number; dotacao: number }
interface Funcao { nome: string; explica: string; liquidado: number; dotacao: number; sub: [string, number][] }
interface OrgaoRGF { nome: string; bruta: number; ativos: number; inativos: number; dtp: number; pct_rcl: number | null; limite_max: number; limite_pct: number | null; rcl: number }
interface Poder { poder: string; nome: string; ano: number; quadrimestre: number; orgaos: OrgaoRGF[]; url: string }
interface Grupo { id: string; nome: string; explica: string; valor: number; tributos: [string, number][] }
interface Arrecadacao { total: number; meses: [number, number][]; ate_mes: number; grupos: Grupo[]; por_uf: [string, number][] }
interface Setores { ate_mes: number; total: number; setores: { secao: string; nome: string; valor: number; impostos: [string, number][] }[] }
interface Categoria { id: string; nome: string; explica: string; realizado: number; atualizado: number }
interface Acao { cod: string; nome: string; orgao: string; realizado: number; atualizado: number; tipo: string; url: string }
interface Programa { cod: string; nome: string; funcao: string; realizado: number; atualizado: number; url: string; acoes: Acao[] }
interface Executivo {
  total: number; total_atualizado: number; categorias: Categoria[];
  orgaos: { cod: string; nome: string; realizado: number; atualizado: number; cat: Record<string, number>; url: string }[];
  programas: Programa[]; maquina_por_tipo: [string, number][];
}
interface GrupoPessoas { id: string; nome: string; explica: string; pessoas: number; folha_mes?: number | null; indenizacoes_mes?: number }
interface PessoalExec {
  ano: number; mes: number; pessoas: number; grupos: GrupoPessoas[]; funcoes: [string, number, number][];
  orgaos: { nome: string; comissionado: number; confianca: number; total: number; folha_confianca: number }[]; url: string;
}
interface PessoalCasa { grupos: GrupoPessoas[]; efetivos_com_funcao: number; url: string; mes?: number | null; ano?: number; url_remuneracao?: string | null; verba_gabinete?: number | null }
interface Ano {
  ano: number; parcial: boolean; periodo: { bimestre: number; mes: number; mes_nome: string; rgf_mes?: string };
  rreo: { receitas: Receita[]; receita_total_sem_intra: number; despesas: DespesaGrupo[]; despesa_total_sem_intra: number };
  funcoes: { total: number; funcoes: Funcao[]; confere: boolean } | null;
  fontes_ano: { rreo1: string; rreo2: string };
  pessoal_poderes: Poder[]; arrecadacao: Arrecadacao | null; setores: Setores | null; executivo: Executivo | null;
  pessoal_executivo: PessoalExec | null; pessoal_camara?: PessoalCasa | null; pessoal_senado?: PessoalCasa | null;
  emendas_empenhado: number | null; kpis: Kpi[];
  anterior_mesmo_periodo?: { despesas: Record<string, number>; receitas: Record<string, number>; adm_geral: number | null; ipca_fator: number | null };
}
interface Serie {
  ano: number; parcial: boolean; ate: string; impostos: number; receita_propria: number; divida_nova: number; rolagem: number;
  despesa: number; pessoal: number | null; juros: number | null; inss: number | null; investimentos: number | null;
  adm_geral: number | null; maquina_exec: number | null; arrecadacao_rfb: number | null; arrecadacao_ate_mes: number | null;
}
interface Indice { anos: number[]; atualizado: string; serie: Serie[]; fontes: Record<string, string>; avisos: string[] }

const MES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const NIVEL_NOME: Record<Nivel, string> = { vermelho: "Vermelho", amarelo: "Amarelo", verde: "Verde", sem_dados: "Sem dados" };
const ORDEM_NIVEL: Record<Nivel, number> = { vermelho: 0, amarelo: 1, verde: 2, sem_dados: 3 };
const COR_CAT: Record<string, string> = {
  pessoal_ativo: "var(--s1)", aposentados: "var(--c7)", inss: "var(--c5)", beneficios: "var(--s3)", transferencias: "var(--c4)",
  maquina: "var(--s2)", servicos: "var(--c6)", investimentos: "var(--c8)", inversoes: "var(--c-outros)", juros: "var(--esq)",
  amortizacao: "var(--c-outros)", reserva: "var(--c-outros)",
};
const FUNCOES_SOCIAIS = ["Assistência social", "Previdência social", "Saúde", "Educação", "Trabalho", "Habitação", "Saneamento", "Direitos da cidadania"];

/** R$ com a escala certa: tri, bi, mi, mil. */
export function rs(v: number | null | undefined): string {
  if (v == null) return "—";
  const a = Math.abs(v), s = v < 0 ? "−" : "";
  const f = (x: number) => x.toLocaleString("pt-BR", { maximumFractionDigits: x >= 100 ? 0 : 1 });
  if (a >= 1e12) return `${s}R$ ${f(a / 1e12)} tri`;
  if (a >= 1e9) return `${s}R$ ${f(a / 1e9)} bi`;
  if (a >= 1e6) return `${s}R$ ${f(a / 1e6)} mi`;
  if (a >= 1e3) return `${s}R$ ${f(a / 1e3)} mil`;
  return reais(v);
}
const pc = (v: number | null | undefined, casas = 1) => (v == null || !isFinite(v) ? "—" : `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`);
const num = (n: number) => n.toLocaleString("pt-BR");
const semAcento = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const Fonte = ({ href, children }: { href?: string | null; children: ReactNode }) => {
  const u = linkSeguro(href);
  return u ? <a href={u} target="_blank" rel="noreferrer">{children} ↗</a> : <>{children}</>;
};

function Sinal({ nivel }: { nivel: Nivel }) {
  return <span className={`fin-sinal ${nivel}`}>{NIVEL_NOME[nivel]}</span>;
}

export default function Financas() {
  const { data: idx, error: erroIdx } = useData<Indice>("financas/indice.json");
  const anos = (idx?.anos || []).map(String);
  const [escolhido, setEscolhido] = useState<string>("");
  // Abre no ano mais recente (2026), mesmo que o resto do site esteja em outro ano.
  const ano = anos.includes(escolhido) ? escolhido : [...anos].sort().pop() || "";
  const { data: d, error } = useData<Ano>(ano ? `financas/${ano}.json` : null);

  if (!idx) {
    return erroIdx ? <><h1>Arrecadação e gastos do Brasil</h1><div className="empty">Os dados desta página ainda não foram coletados. Eles aparecem aqui depois da próxima atualização diária.</div></>
      : <Loading />;
  }
  if (!d) return <Loading error={error} />;

  const rec = d.rreo.receitas;
  const impostos = rec.filter((r) => ["Impostos", "Taxas", "ContribuicoesSociais", "ContribuicaoDeIntervencaoNoDominioEconomico"].includes(r.id)).reduce((a, r) => a + r.valor, 0);
  const propria = rec.filter((r) => r.tipo === "propria").reduce((a, r) => a + r.valor, 0);
  const divida = rec.find((r) => r.id === "ReceitasDeOperacoesDeCredito")?.valor || 0;
  const gasto = d.rreo.despesas.filter((x) => x.id !== "AmortizacaoRefinanciamentoDaDivida").reduce((a, x) => a + x.liquidado, 0);
  const juros = d.rreo.despesas.find((x) => x.id === "JurosEEncargosDaDivida")?.liquidado || 0;
  const periodo = d.parcial ? `de janeiro a ${d.periodo.mes_nome} de ${d.ano}` : `em ${d.ano}`;

  return (
    <div className="fin">
      <section className="hero">
        <span className="eyebrow">Brasil · arrecadação e gastos do governo federal · {d.ano}</span>
        <h1>De onde vem e para onde vai o dinheiro</h1>
        <div className="row fin-anos" role="group" aria-label="Ano">
          {anos.slice().reverse().map((a) => (
            <button key={a} className="fin-ano" aria-pressed={a === ano} onClick={() => setEscolhido(a)}>{a}</button>
          ))}
        </div>
        <Explain>
          Quanto o governo federal arrecadou, quem pagou, como gastou e com quem. Cada ano aparece separado; cada número tem o link do dado oficial.
          {d.parcial && <> <strong>{d.ano} ainda não terminou:</strong> os valores vão de janeiro a {d.periodo.mes_nome}, o último relatório publicado pelo Tesouro Nacional.</>}
          {" "}Estados e municípios têm orçamentos próprios e não entram aqui.
        </Explain>
        <div className="grid">
          <div className="card stat"><span className="label">Arrecadado em impostos e contribuições</span><span className="value">{rs(impostos)}</span><span className="hint">{periodo}</span></div>
          <div className="card stat"><span className="label">Gasto (sem a rolagem da dívida)</span><span className="value">{rs(gasto)}</span><span className="hint">despesa liquidada {periodo}</span></div>
          <div className="card stat"><span className="label">Pego emprestado (dívida nova)</span><span className="value">{rs(divida)}</span><span className="hint">{pc(gasto ? divida / gasto : null, 0)} do que foi gasto</span></div>
          <div className="card stat"><span className="label">Pago de juros da dívida</span><span className="value">{rs(juros)}</span><span className="hint">{pc(impostos ? juros / impostos : null, 0)} do arrecadado em impostos</span></div>
        </div>
        <nav className="fin-indice" aria-label="Nesta página">
          <a href="#sinais" onClick={irPara("sinais")}>Sinais</a><a href="#arrecadacao" onClick={irPara("arrecadacao")}>Arrecadação</a>
          <a href="#quem-pagou" onClick={irPara("quem-pagou")}>Quem pagou</a><a href="#destino" onClick={irPara("destino")}>Para onde vai</a>
          <a href="#poderes" onClick={irPara("poderes")}>Poderes</a><a href="#cargos" onClick={irPara("cargos")}>Cargos</a>
          <a href="#programas" onClick={irPara("programas")}>Programas</a><a href="#anos" onClick={irPara("anos")}>Ano a ano</a>
        </nav>
      </section>

      <Sinais d={d} />
      <Arrecadou d={d} propria={propria} />
      <QuemPagou d={d} />
      <Destino d={d} />
      <Poderes d={d} />
      <Cargos d={d} />
      <Programas d={d} />
      <AnoAAno idx={idx} />
      <Ligacoes d={d} />
      <Fontes d={d} idx={idx} />
      <AvisosFim secao="financas">
        {idx.avisos?.length > 0 && <div className="alert" role="note"><div>{idx.avisos.map((a) => <div key={a}>{a}</div>)}</div></div>}
      </AvisosFim>
    </div>
  );
}

/* Rolagem até a seção sem mexer no endereço (o site usa # para as páginas) */
const irPara = (id: string) => (e: React.MouseEvent) => {
  e.preventDefault();
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
};

/* ------------------------------------------------------------------ sinais (KPIs) */

function valorKpi(k: Kpi): string {
  if (k.valor == null) return "—";
  if (k.formato === "pct_var") return `${k.valor > 0 ? "+" : ""}${pc(k.valor)}`;
  return pc(k.valor);
}

function Sinais({ d }: { d: Ano }) {
  const [filtro, setFiltro] = useState<Nivel | "">("");
  const ks = d.kpis.slice().sort((a, b) => ORDEM_NIVEL[a.nivel] - ORDEM_NIVEL[b.nivel]);
  const conta = (n: Nivel) => ks.filter((k) => k.nivel === n).length;
  const vis = ks.filter((k) => !filtro || k.nivel === filtro);
  return (
    <section id="sinais">
      <h2>Sinais: onde olhar primeiro</h2>
      <Explain>
        Indicadores calculados com os dados oficiais desta página para achar onde o gasto pode estar alto demais.
        <strong> Vermelho</strong> pede atenção já, <strong>amarelo</strong> merece acompanhamento, <strong>verde</strong> está dentro do esperado.
        Os limites de gasto com pessoal são da Lei de Responsabilidade Fiscal; os outros critérios são do Segredos Abertos e estão escritos em cada sinal.
      </Explain>
      <div className="toggle" role="group" aria-label="Filtrar sinais">
        <button aria-pressed={filtro === ""} onClick={() => setFiltro("")}>Todos ({ks.length})</button>
        {(["vermelho", "amarelo", "verde"] as Nivel[]).map((n) => (
          <button key={n} aria-pressed={filtro === n} onClick={() => setFiltro(n)}>{NIVEL_NOME[n]} ({conta(n)})</button>
        ))}
      </div>
      <div className="fin-kpis">
        {vis.map((k) => (
          <article key={k.id} className={`card fin-kpi ${k.nivel}`} data-testid="kpi">
            <div className="fin-kpi-topo"><Sinal nivel={k.nivel} /><span className="fin-kpi-valor num">{valorKpi(k)}</span></div>
            <h3>{k.titulo}</h3>
            {k.formato === "pct_limite" && k.valor != null && (
              <div className="fin-barra" aria-hidden="true"><span style={{ width: `${Math.min(100, k.valor * 100)}%` }} /><i style={{ left: "90%" }} /><i style={{ left: "95%" }} /></div>
            )}
            <p className="small">{k.explica}</p>
            {k.detalhe.length > 0 && (
              <ul className="small fin-kpi-det">{k.detalhe.slice(0, 8).map(([n, v]) => <li key={n}>{n}: <strong>{pc(v)}</strong></li>)}</ul>
            )}
            <p className="small muted">{k.regra}</p>
            <p className="small"><Fonte href={k.fonte}>Dado oficial</Fonte>{k.link && <> · <Link to={k.link}>{k.link === "/emendas" ? "Ver as emendas" : "Ver os parlamentares"}</Link></>}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ arrecadação */

function Arrecadou({ d, propria }: { d: Ano; propria: number }) {
  const rec = d.rreo.receitas.filter((r) => r.valor);
  const ant = d.anterior_mesmo_periodo?.receitas;
  const prop = rec.filter((r) => r.tipo === "propria").sort((a, b) => b.valor - a.valor);
  const div = rec.filter((r) => r.tipo !== "propria");
  return (
    <section id="arrecadacao">
      <h2>Quanto entrou e de onde</h2>
      <Explain>
        Tudo o que entrou no caixa do governo federal {d.parcial ? `de janeiro a ${d.periodo.mes_nome}` : `em ${d.ano}`}, pelo Relatório Resumido da Execução Orçamentária do Tesouro.
        Separamos o dinheiro que o governo arrecadou ({rs(propria)}) do dinheiro que ele pegou emprestado, que vira dívida e é pago com juros.
      </Explain>
      <h3 className="fin-sub">Dinheiro arrecadado</h3>
      <Barras itens={prop.map((r) => ({
        label: <span title={r.explica}>{r.nome}</span>, valor: r.valor, cor: "var(--s3)",
        nota: `${r.explica}${ant?.[r.id] ? ` Mesmo período de ${d.ano - 1}: ${rs(ant[r.id])}.` : ""}`,
      }))} />
      <h3 className="fin-sub">Dinheiro emprestado</h3>
      <Barras itens={div.map((r) => ({ label: r.nome, valor: r.valor, nota: r.explica, cor: r.tipo === "divida" ? "var(--esq)" : "var(--c-outros)" }))} />
      <p className="small muted">Valores realizados {d.parcial ? `até ${d.periodo.mes_nome}` : "no ano"}, sem as receitas intraorçamentárias (quando um órgão federal paga outro). <Fonte href={d.fontes_ano.rreo1}>RREO, Anexo 1, na API do Tesouro</Fonte></p>
    </section>
  );
}

function QuemPagou({ d }: { d: Ano }) {
  const a = d.arrecadacao;
  const s = d.setores;
  const [aberto, setAberto] = useState<string | null>(null);
  if (!a && !s) {
    return <section id="quem-pagou"><h2>Quem pagou</h2><div className="empty">A Receita Federal não tem dados de arrecadação por imposto para {d.ano}.</div></section>;
  }
  return (
    <section id="quem-pagou">
      <h2>Quem pagou os impostos</h2>
      <Explain>
        A Receita Federal publica quanto arrecadou de cada imposto, por estado e por setor da economia{a ? `; em ${d.ano}, até ${MES[a.ate_mes]}` : ""}.
        Quem paga de fato é discutido por economistas: o imposto sobre consumo é recolhido pelas empresas, mas entra no preço que todos pagam.
        Por isso mostramos sobre o que cada imposto é cobrado.
      </Explain>
      {a && (
        <>
          <h3 className="fin-sub">Sobre o que o imposto foi cobrado · {rs(a.total)}</h3>
          <div className="bars">
            {a.grupos.slice().sort((x, y) => y.valor - x.valor).map((g) => (
              <Fragment key={g.id}>
                <div className="bar-row">
                  <div style={{ minWidth: 0 }}>
                    <button className="link fin-abrir" aria-expanded={aberto === g.id} onClick={() => setAberto(aberto === g.id ? null : g.id)}>{g.nome}</button>
                    <div className="muted small">{g.explica} {pc(g.valor / a.total)} do total.</div>
                  </div>
                  <div className="num">{rs(g.valor)}</div>
                  <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(g.valor / Math.max(...a.grupos.map((x) => x.valor))) * 100}%`, background: "var(--s1)" }} /></div>
                </div>
                {aberto === g.id && (
                  <div className="fin-detalhe small">
                    {g.tributos.map(([n, v]) => <div key={n} className="fin-linha"><span>{n}</span><span className="num">{rs(v)}</span></div>)}
                  </div>
                )}
              </Fragment>
            ))}
          </div>
        </>
      )}
      {s && s.setores.length > 0 && (
        <>
          <h3 className="fin-sub">Por setor da economia{s.ate_mes ? ` (até ${MES[s.ate_mes]})` : ""}</h3>
          <Barras itens={s.setores.slice(0, 14).map((x) => ({ label: x.nome, valor: x.valor, cor: x.secao === "PF" ? "var(--c7)" : "var(--c4)",
            nota: `${pc(x.valor / s.total)} do total · mais pagos: ${x.impostos.slice(0, 3).map(([n]) => n).join(", ")}` }))} />
        </>
      )}
      {a && (
        <>
          <h3 className="fin-sub">Por estado</h3>
          <p className="small muted">O imposto entra no estado onde a empresa recolhe, em geral a sede. Por isso São Paulo, Rio e o Distrito Federal (sede de bancos e estatais) aparecem bem acima da sua população.</p>
          <Barras itens={a.por_uf.slice(0, 27).map(([uf, v]) => ({ label: uf, valor: v, cor: "var(--s2)", nota: pc(v / a.total) }))} />
        </>
      )}
      <p className="small muted"><Fonte href={linkSeguro("https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao")}>Dados abertos de arrecadação da Receita Federal</Fonte>. O Simples Nacional inclui a parte de estados e municípios, que a Receita repassa.</p>
    </section>
  );
}

/* ------------------------------------------------------------------ destino */

function Destino({ d }: { d: Ano }) {
  const [abertas, setAbertas] = useState<string | null>(null);
  const ant = d.anterior_mesmo_periodo;
  const fator = ant?.ipca_fator || null;
  const desp = d.rreo.despesas.filter((x) => x.liquidado || x.dotacao);
  const f = d.funcoes;
  return (
    <section id="destino">
      <h2>Para onde foi o dinheiro</h2>
      <Explain>
        Despesa liquidada (o serviço foi entregue e a conta foi reconhecida) {d.parcial ? `de janeiro a ${d.periodo.mes_nome}` : `em ${d.ano}`}. A barra mostra quanto do orçamento autorizado para o ano já foi usado.
        {fator && <> Entre parênteses, a variação contra o mesmo período de {d.ano - 1}, já descontada a inflação (IPCA).</>}
      </Explain>
      <h3 className="fin-sub">Por tipo de gasto</h3>
      <div className="table-wrap">
        <table className="fin-tabela">
          <thead><tr><th>Gasto</th><th className="r">{d.parcial ? `Até ${d.periodo.mes_nome}` : "No ano"}</th><th className="r">Autorizado no ano</th></tr></thead>
          <tbody>
            {desp.map((x) => {
              const a = ant?.despesas[x.id];
              const v = a && fator ? x.liquidado / (a * fator) - 1 : null;
              return (
                <tr key={x.id}>
                  <td><strong>{x.nome}</strong><div className="small muted">{x.explica}</div>
                    {x.dotacao > 0 && <div className="fin-barra fin-barra-fina" aria-hidden="true"><span style={{ width: `${Math.min(100, (x.liquidado / x.dotacao) * 100)}%` }} /></div>}
                  </td>
                  <td className="r num">{rs(x.liquidado)}{v != null && <div className={`small ${v > 0 ? "fin-sobe" : "fin-desce"}`}>({v > 0 ? "+" : ""}{pc(v)})</div>}</td>
                  <td className="r num muted">{rs(x.dotacao)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {f && f.funcoes.length > 0 && (
        <>
          <h3 className="fin-sub">Por área (função de governo)</h3>
          <p className="small muted">Toque numa área para ver em que ela gastou. "Administração geral" é o custo de manter os órgãos daquela área funcionando.</p>
          <div className="bars">
            {f.funcoes.filter((x) => x.liquidado > 0).map((x) => (
              <Fragment key={x.nome}>
                <div className="bar-row">
                  <div style={{ minWidth: 0 }}>
                    <button className="link fin-abrir" aria-expanded={abertas === x.nome} onClick={() => setAbertas(abertas === x.nome ? null : x.nome)}>{x.nome}</button>
                    {x.explica && <div className="muted small">{x.explica}</div>}
                  </div>
                  <div className="num">{rs(x.liquidado)}</div>
                  <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(x.liquidado / f.funcoes[0].liquidado) * 100}%`, background: x.nome === "Encargos Especiais" ? "var(--esq)" : "var(--s1)" }} /></div>
                </div>
                {abertas === x.nome && (
                  <div className="fin-detalhe small">
                    {x.sub.map(([n, v]) => <div key={n} className="fin-linha"><span>{n}</span><span className="num">{rs(v)}</span></div>)}
                    {!x.sub.length && <span className="muted">Sem detalhe por subfunção.</span>}
                  </div>
                )}
              </Fragment>
            ))}
          </div>
          <p className="small muted"><Fonte href={d.fontes_ano.rreo2}>RREO, Anexo 2, na API do Tesouro</Fonte>. Encargos especiais incluem os juros e a rolagem da dívida e os repasses obrigatórios a estados e municípios.</p>
        </>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ Poderes */

function Poderes({ d }: { d: Ano }) {
  const ex = d.executivo;
  const [aberto, setAberto] = useState<string | null>(null);
  const tot = (p: Poder, k: keyof OrgaoRGF) => p.orgaos.reduce((a, o) => a + ((o[k] as number) || 0), 0);
  return (
    <section id="poderes">
      <h2>Quanto custa cada Poder</h2>
      <Explain>
        Gasto com pessoal (salários, aposentadorias e pensões) de cada Poder e órgão nos últimos 12 meses, pelo Relatório de Gestão Fiscal, que cada Poder entrega ao Tesouro.
        A barra mostra quanto do limite da Lei de Responsabilidade Fiscal já foi usado (traços em 90%, alerta, e 95%, limite prudencial).
      </Explain>
      <div className="fin-poderes">
        {d.pessoal_poderes.map((p) => {
          const lim = tot(p, "limite_max"), dtp = tot(p, "dtp");
          const uso = lim ? dtp / lim : null;
          const nivel: Nivel = uso == null ? "sem_dados" : uso >= 0.95 ? "vermelho" : uso >= 0.9 ? "amarelo" : "verde";
          return (
            <article key={p.poder} className="card">
              <div className="fin-kpi-topo"><h3>{p.nome}</h3><Sinal nivel={nivel} /></div>
              <div className="fin-grande num">{rs(tot(p, "bruta"))}</div>
              <div className="small muted">gasto com pessoal em 12 meses até {["", "abril", "agosto", "dezembro"][p.quadrimestre]} de {p.ano}</div>
              <div className="fin-barra" aria-hidden="true"><span style={{ width: `${Math.min(100, (uso || 0) * 100)}%` }} /><i style={{ left: "90%" }} /><i style={{ left: "95%" }} /></div>
              <div className="small">{pc(uso)} do limite da LRF · ativos {rs(tot(p, "ativos"))} · aposentados e pensionistas {rs(tot(p, "inativos"))}</div>
              {p.orgaos.length > 1 && (
                <>
                  <button className="link small" aria-expanded={aberto === p.poder} onClick={() => setAberto(aberto === p.poder ? null : p.poder)}>
                    {aberto === p.poder ? "Esconder" : "Ver"} os {p.orgaos.length} órgãos
                  </button>
                  {aberto === p.poder && (
                    <div className="fin-detalhe small">
                      {p.orgaos.map((o) => (
                        <div key={o.nome} className="fin-linha"><span>{o.nome}{o.limite_max > 0 && <span className="muted"> · {pc(o.dtp / o.limite_max, 0)} do limite</span>}</span><span className="num">{rs(o.bruta)}</span></div>
                      ))}
                    </div>
                  )}
                </>
              )}
              <p className="small"><Fonte href={p.url}>RGF do {p.nome}</Fonte></p>
            </article>
          );
        })}
      </div>
      {!d.pessoal_poderes.length && <div className="empty">O Tesouro ainda não publicou o Relatório de Gestão Fiscal de {d.ano}.</div>}

      {ex && (
        <>
          <h3 className="fin-sub">Executivo: tudo o que os ministérios gastaram, por tipo</h3>
          <p className="small muted">
            O Executivo é o único Poder com o gasto aberto por órgão, ação e tipo de despesa nos dados abertos. Separamos o custo de funcionar a máquina
            (custeio das áreas de gestão: aluguéis, terceirizados, diárias, passagens, TI, consultorias) do custeio de serviços que chegam à população.
            Para o Legislativo e o Judiciário, os dados abertos trazem o gasto com pessoal (acima) e o gasto por área, na seção anterior.
          </p>
          <Barras itens={ex.categorias.filter((c) => c.realizado > 0).sort((a, b) => b.realizado - a.realizado).map((c) => ({
            label: c.nome, valor: c.realizado, cor: COR_CAT[c.id] || "var(--s1)", nota: `${c.explica} ${pc(c.realizado / ex.total)} do total.`,
          }))} />
          {ex.maquina_por_tipo.length > 0 && (
            <details className="small fin-mais">
              <summary>Em que se gasta para funcionar a máquina</summary>
              <div className="fin-detalhe">{ex.maquina_por_tipo.map(([n, v]) => <div key={n} className="fin-linha"><span>{n}</span><span className="num">{rs(v)}</span></div>)}</div>
            </details>
          )}
          <details className="small fin-mais">
            <summary>Gasto de cada ministério e órgão ({ex.orgaos.length})</summary>
            <div className="table-wrap">
              <table className="fin-tabela">
                <thead><tr><th>Órgão</th><th className="r">Realizado</th><th className="r">Máquina</th><th className="r">Pessoal ativo</th></tr></thead>
                <tbody>
                  {ex.orgaos.map((o) => (
                    <tr key={o.cod}>
                      <td><Fonte href={o.url}>{o.nome}</Fonte></td>
                      <td className="r num">{rs(o.realizado)}</td>
                      <td className="r num">{rs(o.cat.maquina || 0)}</td>
                      <td className="r num">{rs(o.cat.pessoal_ativo || 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ cargos de confiança */

function Cargos({ d }: { d: Ano }) {
  const ex = d.pessoal_executivo;
  const cam = d.pessoal_camara;
  const sen = d.pessoal_senado;
  return (
    <section id="cargos">
      <h2>Concursados, cargos de confiança e comissionados</h2>
      <Explain>
        Cargos e funções de confiança são de livre nomeação: quem ocupa pode ser trocado a cada governo ou a cada mandato.
        Os <strong>comissionados sem concurso</strong> saem do serviço público quando são exonerados; os <strong>concursados com função de confiança</strong> voltam ao cargo de origem.
        Os concursados ficam, seja qual for o governo.
      </Explain>
      {ex ? (
        <>
          <h3 className="fin-sub">Executivo federal · servidores civis em {MES[ex.mes]} de {ex.ano}</h3>
          <div className="table-wrap">
            <table className="fin-tabela">
              <thead><tr><th>Grupo</th><th className="r">Pessoas</th><th className="r">Folha do mês</th></tr></thead>
              <tbody>
                {ex.grupos.map((g) => (
                  <tr key={g.id} className={g.id === "comissionado" || g.id === "confianca" ? "fin-destaque" : ""}>
                    <td><strong>{g.nome}</strong><div className="small muted">{g.explica}</div></td>
                    <td className="r num">{num(g.pessoas)}<div className="small muted">{pc(g.pessoas / Math.max(1, ex.pessoas), 1)}</div></td>
                    <td className="r num">{g.id === "sigiloso" ? "—" : rs(g.folha_mes || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="small muted">Folha bruta do mês (salário, gratificações, férias e 13º, já com o abate-teto), sem auxílios e indenizações. Não inclui militares nem empregados de estatais que não dependem do Tesouro. Quem tem dois vínculos conta uma vez, no grupo de confiança.</p>
          {ex.funcoes.length > 0 && (
            <details className="small fin-mais" open>
              <summary>Tipos de cargo e função de confiança</summary>
              <div className="fin-detalhe">{ex.funcoes.map(([n, p, v]) => <div key={n} className="fin-linha"><span>{n}</span><span className="num">{num(p)} pessoas · {rs(v)}/mês</span></div>)}</div>
            </details>
          )}
          {ex.orgaos.length > 0 && (
            <details className="small fin-mais">
              <summary>Ministérios com mais cargos de confiança</summary>
              <div className="fin-detalhe">{ex.orgaos.slice(0, 25).map((o) => (
                <div key={o.nome} className="fin-linha"><span>{o.nome}</span><span className="num">{num(o.comissionado)} sem concurso · {num(o.confianca)} concursados · {pc((o.comissionado + o.confianca) / Math.max(1, o.total), 0)} do órgão</span></div>
              ))}</div>
            </details>
          )}
          <p className="small"><Fonte href={ex.url}>Cadastro e remuneração dos servidores, Portal da Transparência</Fonte></p>
        </>
      ) : <div className="empty">Ainda sem os dados de servidores do Executivo para {d.ano}.</div>}

      {(cam || sen) && (
        <div className="fin-casas">
          {cam && (
            <article className="card">
              <h3>Câmara dos Deputados · hoje</h3>
              <Barras itens={cam.grupos.filter((g) => g.pessoas).map((g) => ({ label: g.nome, valor: g.pessoas, nota: g.explica,
                cor: g.id === "secretario" || g.id === "cne" ? "var(--esq)" : g.id === "parlamentar" ? "var(--c-outros)" : "var(--s3)" }))} max={undefined} />
              <p className="small muted">Valores em pessoas, não em reais. Dos concursados, {num(cam.efetivos_com_funcao)} têm função comissionada.
                {cam.verba_gabinete ? <> Os secretários parlamentares são pagos pela verba de gabinete, que somou {rs(cam.verba_gabinete)} em {d.ano}: veja quanto cada deputado usou em <Link to="/politicos">Políticos</Link>.</> : null}
              </p>
              <p className="small"><Fonte href={cam.url}>Funcionários, dados abertos da Câmara</Fonte></p>
            </article>
          )}
          {sen && (
            <article className="card">
              <h3>Senado Federal · hoje</h3>
              <div className="fin-detalhe small">
                {sen.grupos.filter((g) => g.pessoas).map((g) => (
                  <div key={g.id} className="fin-linha"><span><strong>{g.nome}</strong><span className="muted"> · {g.explica}</span></span>
                    <span className="num">{num(g.pessoas)} pessoas{g.folha_mes ? ` · ${rs(g.folha_mes)}/mês` : ""}</span></div>
                ))}
              </div>
              <p className="small muted">Folha bruta de {sen.mes ? `${MES[sen.mes]} de ${sen.ano}` : "—"}, só de quem está na ativa. Dos concursados, {num(sen.efetivos_com_funcao)} têm função comissionada.</p>
              <p className="small"><Fonte href={sen.url}>Servidores, API do Senado</Fonte>{sen.url_remuneracao && <> · <Fonte href={sen.url_remuneracao}>remuneração do mês</Fonte></>}</p>
            </article>
          )}
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ programas */

function Programas({ d }: { d: Ano }) {
  const ex = d.executivo;
  const [q, setQ] = useState("");
  const [area, setArea] = useState("sociais");
  const [aberto, setAberto] = useState<string | null>(null);
  const [n, setN] = useState(15);
  const progs = useMemo(() => {
    if (!ex) return [];
    const t = semAcento(q.trim());
    return ex.programas.filter((p) => (area === "todos" || (area === "sociais" ? FUNCOES_SOCIAIS.some((f) => semAcento(f) === semAcento(p.funcao)) : p.funcao === area))
      && (!t || semAcento(`${p.nome} ${p.acoes.map((a) => a.nome).join(" ")}`).includes(t)));
  }, [ex, q, area]);
  if (!ex) return null;
  const funcoes = Array.from(new Set(ex.programas.map((p) => p.funcao))).sort();
  return (
    <section id="programas">
      <h2>Cada programa, um por um</h2>
      <Explain>
        Todos os programas do Executivo federal em {d.ano}, com cada ação separada: Bolsa Família, BPC, seguro-desemprego, Farmácia Popular, universidades, obras e todo o resto.
        "Realizado" é o que já foi gasto (liquidado); "autorizado" é o que o orçamento permite gastar no ano. Cada ação tem o link da página dela no Portal da Transparência.
      </Explain>
      <div className="row" style={{ gap: 8 }}>
        <label className="fin-escolha"><span className="muted small">Área</span>
          <select value={area} onChange={(e) => { setArea(e.target.value); setN(15); }}>
            <option value="sociais">Programas sociais, saúde e educação</option>
            <option value="todos">Todas as áreas</option>
            {funcoes.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <div className="search" style={{ flex: 1 }}>
          <input aria-label="Procurar programa ou ação" value={q} onChange={(e) => { setQ(e.target.value); setN(15); }} placeholder="Procurar: Bolsa Família, Pé-de-Meia, merenda, rodovia…" />
        </div>
      </div>
      <div className="table-wrap">
        <table className="fin-tabela">
          <thead><tr><th>Programa</th><th className="r">Realizado</th><th className="r">Autorizado</th></tr></thead>
          <tbody>
            {progs.slice(0, n).map((p) => (
              <Fragment key={p.cod}>
                <tr>
                  <td>
                    <button className="link fin-abrir" aria-expanded={aberto === p.cod} onClick={() => setAberto(aberto === p.cod ? null : p.cod)}>{p.nome}</button>
                    <div className="small muted">{p.funcao} · {p.acoes.length} {p.acoes.length === 1 ? "ação" : "ações"} · <Fonte href={p.url}>no Portal</Fonte></div>
                  </td>
                  <td className="r num">{rs(p.realizado)}</td>
                  <td className="r num muted">{rs(p.atualizado)}</td>
                </tr>
                {aberto === p.cod && p.acoes.map((a) => (
                  <tr key={a.cod} className="fin-acao">
                    <td><Fonte href={a.url}>{a.nome}</Fonte><div className="small muted">Ação {a.cod} · {a.orgao}</div></td>
                    <td className="r num">{rs(a.realizado)}</td>
                    <td className="r num muted">{rs(a.atualizado)}</td>
                  </tr>
                ))}
              </Fragment>
            ))}
            {!progs.length && <tr><td colSpan={3} className="muted">Nada encontrado.</td></tr>}
          </tbody>
        </table>
      </div>
      {progs.length > n && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais ({progs.length - n} restantes)</button>}
      <p className="small muted"><Fonte href={linkSeguro("https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa")}>Orçamento da despesa pública, Portal da Transparência</Fonte>. Não inclui juros e dívida.</p>
    </section>
  );
}

/* ------------------------------------------------------------------ ano a ano */

const METRICAS: { k: keyof Serie; nome: string; cor: string }[] = [
  { k: "impostos", nome: "Impostos e contribuições arrecadados", cor: "var(--s3)" },
  { k: "despesa", nome: "Gasto total (sem a rolagem da dívida)", cor: "var(--s1)" },
  { k: "divida_nova", nome: "Dívida nova (empréstimos)", cor: "var(--esq)" },
  { k: "juros", nome: "Juros da dívida", cor: "var(--esq)" },
  { k: "pessoal", nome: "Pessoal (salários, aposentadorias e pensões de servidores)", cor: "var(--c7)" },
  { k: "inss", nome: "Aposentadorias e pensões do INSS", cor: "var(--c5)" },
  { k: "adm_geral", nome: "Custo de manter a máquina (administração geral)", cor: "var(--s2)" },
  { k: "investimentos", nome: "Investimentos", cor: "var(--c4)" },
];

function AnoAAno({ idx }: { idx: Indice }) {
  const [m, setM] = useState<keyof Serie>("impostos");
  const met = METRICAS.find((x) => x.k === m)!;
  const serie = idx.serie;
  const tip = useTip();
  const vals = serie.map((s) => (s[m] as number | null) || 0);
  const max = Math.max(1, ...vals);
  const soma = vals.reduce((a, b) => a + b, 0);
  return (
    <section id="anos">
      <h2>Ano a ano</h2>
      <Explain>Cada ano separado, sem correção pela inflação. O ano em andamento vai só até o último relatório publicado e por isso aparece com a barra clara.</Explain>
      <label className="fin-escolha"><span className="muted small">Mostrar</span>
        <select value={m as string} onChange={(e) => setM(e.target.value as keyof Serie)}>{METRICAS.map((x) => <option key={x.k as string} value={x.k as string}>{x.nome}</option>)}</select>
      </label>
      <div className="fin-colunas" role="img" aria-label={`${met.nome} por ano`}>
        {serie.map((s, i) => (
          <div key={s.ano} className="fin-coluna" onMouseMove={(e) => tip.show(e, `${s.ano}${s.parcial ? ` (até ${s.ate})` : ""}: ${rs(vals[i])}`)} onMouseLeave={tip.hide}>
            <span className="fin-coluna-valor num">{rs(vals[i])}</span>
            <div className="fin-coluna-barra" style={{ height: `${(vals[i] / max) * 100}%`, background: met.cor, opacity: s.parcial ? 0.5 : 1 }} />
            <span className="fin-coluna-ano">{s.ano}{s.parcial && <small>até {s.ate.slice(0, 3)}</small>}</span>
          </div>
        ))}
      </div>
      {tip.el}
      <div className="table-wrap">
        <table className="fin-tabela fin-tabela-anos">
          <thead><tr><th></th>{serie.map((s) => <th key={s.ano} className="r">{s.ano}{s.parcial ? "*" : ""}</th>)}</tr></thead>
          <tbody>
            {METRICAS.map((x) => (
              <tr key={x.k as string}><td>{x.nome}</td>{serie.map((s) => <td key={s.ano} className="r num">{rs(s[x.k] as number | null)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted">* {serie.filter((s) => s.parcial).map((s) => `${s.ano}: até ${s.ate}`).join("; ")}.</p>
      <details className="small fin-mais"><summary>Soma de todos os anos (informação secundária)</summary>
        <p>{met.nome}, somando {serie[0]?.ano} a {serie[serie.length - 1]?.ano} sem corrigir a inflação: <strong>{rs(soma)}</strong>.</p>
      </details>
    </section>
  );
}

/* ------------------------------------------------------------------ ligações com o resto do site */

function Ligacoes({ d }: { d: Ano }) {
  return (
    <section>
      <h2>Siga o dinheiro no resto do site</h2>
      <div className="grid">
        <Link className="card fin-link" to="/emendas"><strong>Emendas parlamentares</strong><span className="small muted">Quanto cada deputado e senador mandou para onde{d.emendas_empenhado ? ` · ${rs(d.emendas_empenhado)} empenhados em ${d.ano}` : ""}.</span></Link>
        <Link className="card fin-link" to="/politicos"><strong>Deputados e senadores</strong><span className="small muted">Cota parlamentar, salário, verba de gabinete e equipe de cada um.</span></Link>
        <Link className="card fin-link" to="/incentivos"><strong>Incentivos a empresas</strong><span className="small muted">Quem recebe do governo e quem deixa de pagar imposto.</span></Link>
        <Link className="card fin-link" to="/empresas"><strong>Empresas</strong><span className="small muted">Fornecedores, donos e outras empresas dos mesmos donos.</span></Link>
      </div>
    </section>
  );
}

function Fontes({ d, idx }: { d: Ano; idx: Indice }) {
  const f = idx.fontes;
  return (
    <section>
      <h2>De onde vêm estes dados</h2>
      <ul className="small muted fin-fontes">
        <li><strong>Receitas, despesas por tipo e por área:</strong> Relatório Resumido da Execução Orçamentária (RREO) da União, pela <Fonte href={f.siconfi}>API do SICONFI, do Tesouro Nacional</Fonte>. <Fonte href={d.fontes_ano.rreo1}>Anexo 1 de {d.ano}</Fonte> · <Fonte href={d.fontes_ano.rreo2}>Anexo 2 de {d.ano}</Fonte>.</li>
        <li><strong>Pessoal por Poder e limites da LRF:</strong> Relatório de Gestão Fiscal (RGF) de cada Poder, pela mesma API. <Fonte href={f.rgf}>Sobre o RGF</Fonte>.</li>
        <li><strong>Impostos, estados e setores:</strong> <Fonte href={f.receita}>dados abertos da Receita Federal</Fonte> (<Fonte href={f.receita_uf}>por estado</Fonte>, <Fonte href={f.receita_cnae}>por setor</Fonte>). A Receita não tem API para isso; usamos os arquivos oficiais.</li>
        <li><strong>Gasto do Executivo por órgão, programa e ação:</strong> <Fonte href={f.orcamento}>Orçamento da despesa pública, Portal da Transparência</Fonte>. A API do Portal não cruza órgão com o tipo de despesa; o arquivo cruza.</li>
        <li><strong>Servidores do Executivo:</strong> <Fonte href={f.siape}>cadastro e remuneração do SIAPE, Portal da Transparência</Fonte>. <strong>Câmara:</strong> <Fonte href={f.camara}>arquivo de funcionários</Fonte>. <strong>Senado:</strong> <Fonte href={f.senado}>API de servidores</Fonte>.</li>
        <li><strong>Inflação:</strong> <Fonte href={f.ipca}>IPCA do IBGE, pela API SIDRA</Fonte>.</li>
        <li>Atualizado em {idx.atualizado.slice(0, 10).split("-").reverse().join("/")}. Dado faltando aparece como "—" ou com aviso; nunca estimamos um valor que não está nas fontes.</li>
      </ul>
    </section>
  );
}
