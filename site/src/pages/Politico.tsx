import { AtuacaoPolitico } from "./Atuacao";
import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CompararAnos, Kpi, Variacao, type Fatia } from "../components/graficos";
import { Abrir, Barras, COR_GRUPO, Espectro, Explain, GastoMensal, LinkNota, Loading, ResultadoChip, VotoChip, useAno, useData } from "../components/ui";
import {
  GRUPO_CURTO, GRUPO_EXPLICA, cnpjFmt, dataBR, linkSeguro, pct, proposicaoNome, reais,
  type Grupo, type Meta, type Politico, type Recursos, type Resumo, type VotacaoResumo,
  MESES_LONGOS, descricaoCurta, tipoVotacao, type AnoDetalhe, type NotasPolitico, type Pessoa,
} from "../data";
import { AvisosFim, EmRevisao } from "../components/Selo";
import { FotoPerfil } from "../components/Foto";
import { AgendaPolitico } from "../components/Agenda";
import { CampanhaPolitico } from "../components/Campanha";
import { Compartilhar } from "../components/Compartilhar";
import { norm } from "./Home";
import { MG } from "../recorte";
import { MediaCasaLinha, OQueFaltaQuadro } from "../components/Confianca";
import {
  comparacao, comparacaoPontos, nomeCasa, periodoInteiro, referenciaDinheiro, referenciaTaxa, type MediasCasaAno,
} from "../confianca";

export default function PoliticoPage() {
  const { id = "" } = useParams();
  const { data: p, error } = useData<Politico>(`p/${id}.json`);
  const { data: meta } = useData<Meta>("meta.json");
  const [params, setParams] = useSearchParams();
  const pedida = params.get("aba");
  const aba = pedida === "votos" || pedida === "atuacao" || pedida === "agenda" || pedida === "campanha" ? pedida : "gastos";
  const setAba = (a: "gastos" | "atuacao" | "votos" | "agenda" | "campanha") => setParams(a !== "gastos" ? { aba: a } : {}, { replace: true });
  const { ano } = useAno();
  if (!p) return <Loading error={error} />;
  return (
    <>
      <section className="profile">
        <FotoPerfil url={p.foto} nome={p.nome} />
        <div>
          <span className="eyebrow">{p.cargo} · {p.uf}</span>
          <h1>{p.nome}</h1>
          <div className="tags">
            <span className="chip">{p.partido}</span>
            {p.posicao != null && <span className="chip">{p.rotulo}</span>}
            {p.campo && <span className="chip">{p.campo}</span>}
            <a className="chip" href={linkSeguro(p.fonte)} target="_blank" rel="noreferrer">Página oficial ↗</a>
            <Link className="chip" to={`/rede?seguir=${encodeURIComponent(p.id)}`}>Acompanhar na Minha rede</Link>
            <Compartilhar p={p} meta={meta} ano={ano} />
          </div>
          {p.em_exercicio === false && <p className="small muted" role="note">
            <strong className="fora-cargo">Fora do cargo hoje</strong>
            {p.situacao && <> · <span>{p.situacao.replace(/^Fora do exercício:?\s*/i, "")}</span></>}
            {p.situacao_desde && <> <span>desde</span> {dataBR(p.situacao_desde)}</>}
            <br /><span>Os gastos e votos abaixo são do período em que esteve no cargo nesta legislatura.</span>
          </p>}
          {p.outros_nomes?.length ? <p className="small muted"><span>Também aparece nos dados oficiais como</span> {p.outros_nomes.join(", ")}</p> : null}
        </div>
      </section>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={aba === "gastos"} onClick={() => setAba("gastos")}>Gastos e equipe</button>
        <button role="tab" aria-selected={aba === "agenda"} onClick={() => setAba("agenda")}>Dia a dia</button>
        <button role="tab" aria-selected={aba === "atuacao"} onClick={() => setAba("atuacao")}>Atuação</button>
        <button role="tab" aria-selected={aba === "votos"} onClick={() => setAba("votos")}>Votos</button>
        <button role="tab" aria-selected={aba === "campanha"} onClick={() => setAba("campanha")}>Campanha</button>
      </div>
      {aba === "gastos" ? <Gastos p={p} meta={meta} /> : aba === "atuacao" ? <AtuacaoPolitico p={p} />
        : aba === "agenda" ? <AgendaPolitico p={p} ano={ano} /> : aba === "campanha" ? <CampanhaPolitico p={p} /> : <Votos p={p} meta={meta} />}
      <AvisosFim secao="cota" assunto={`${p.nome} (${p.cargo}, ${p.partido}-${p.uf}), ${ano}`} resposta>
        {aba === "gastos" && <NotasCota p={p} />}
        <EmRevisao campo="politico" valor={p.id} />
        <OQueFaltaQuadro p={p} ano={ano} atualizado={meta?.atualizado_em} />
      </AvisosFim>
    </>
  );
}

const MES_C = ["", "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function Gastos({ p, meta }: { p: Politico; meta: Meta | null }) {
  const { ano } = useAno();
  const [todas, setTodas] = useState(false);
  const d = p.anos[ano];
  if (!d) return <div className="empty">Não há gastos registrados para {p.nome} em {ano}. Escolha outro ano no topo da página.</div>;
  const r = d.recursos || {};
  // Média da Casa de quem ficou o período inteiro; quem ficou menos é comparado com a média proporcional aos meses
  const ma = meta?.medias_casa?.anos[ano]?.[p.casa];
  const folga = meta?.medias_casa?.folga_meses ?? 1;
  const inteiro = ma ? periodoInteiro(d.meses_com_nota, ma.meses, folga) : false;
  const refDe = (k: "total" | "custo_total") => (ma?.[k] ? referenciaDinheiro(ma[k]!, p.casa, ano, ma.meses, folga, d.meses_com_nota) : null);
  const refCota = refDe("total");
  const refCusto = refDe("custo_total");
  const refEquipe = ma?.n_pessoal ? referenciaDinheiro(ma.n_pessoal, p.casa, ano, ma.meses, folga) : null;
  const partes = [
    { label: "Salário", valor: d.salario || 0, nota: "Pago ao próprio parlamentar, antes dos descontos.", cor: "var(--s1)" },
    { label: "Equipe do gabinete (verba de gabinete)", valor: d.verba_gabinete || 0, nota: "Salários dos assessores.", cor: "var(--s3)" },
    { label: "Cota parlamentar", valor: d.total, nota: "Reembolsos com nota fiscal: viagens, escritório, divulgação.", cor: "var(--s2)" },
    { label: "Outros gastos do mandato", valor: d.outros_gastos || 0, nota: "Fora da cota: correios, diárias e passagens de viagens oficiais.", cor: "var(--gold)" },
  ].filter((x) => x.valor > 0);
  const anos = Object.keys(p.anos).sort();
  // Ano em andamento: a cota compara com o mesmo período do ano anterior (jan até o mesmo mês), pelo mês de cada nota.
  // O custo conhecido (salário e equipe) não tem o detalhe por mês: fica sem seta.
  const periodo = meta?.mesmo_periodo && String(meta.mesmo_periodo.ano) === ano ? meta.mesmo_periodo.ate_mes : 0;
  const somaAte = (ms?: { mes: number; valor: number }[]) => (ms || []).filter((m) => m.mes >= 1 && m.mes <= periodo).reduce((s, m) => s + m.valor, 0);
  const anoAntes = anos[anos.indexOf(ano) - 1];
  const serieDe = (k: "custo_total" | "total"): [string, number][] => anos.filter((a) => p.anos[a]?.[k]).map((a) => [a, p.anos[a][k]]);
  const categoriasAnos: Record<string, Fatia[]> = Object.fromEntries(anos.map((a) => [a, p.anos[a].categorias.map((c) => ({ nome: c.categoria, valor: c.valor }))]));
  return (
    <>
      <section className="grid">
        <Kpi rotulo={`Custo conhecido em ${ano}`} valor={d.custo_total} formato={(v) => reais(v)} serie={serieDe("custo_total")} ano={ano}
          anterior={periodo ? null : undefined}
          dica={<>Soma de salário, equipe, cota e outros gastos informados pelos sites oficiais.
            {refCusto && <MediaCasaLinha r={refCusto} fmt={(v) => reais(v)} comparacao={comparacao(d.custo_total, refCusto.valor)} />}</>} />
        <div className="card stat kpi">
          <span className="label">Cota parlamentar em {ano}</span>
          <span className="value">{reais(d.total)}</span>
          {anoAntes && (periodo
            ? <Variacao de={somaAte(p.anos[anoAntes]?.meses)} para={somaAte(d.meses)} rotulo={`jan–${MES_C[periodo]} ${anoAntes}`} />
            : <Variacao de={p.anos[anoAntes]?.total} para={d.total} rotulo={anoAntes} />)}
          <span className="hint">Reembolsos com nota fiscal{ma && ma.meses < 12 ? `, publicados até ${dataBR(meta!.atualizado_em)}` : ""}.
            {refCota && <MediaCasaLinha r={refCota} fmt={(v) => reais(v)} comparacao={comparacao(d.total, refCota.valor)} />}</span>
        </div>
        {d.n_pessoal != null && <div className="card stat"><span className="label">Pessoas que passaram pela equipe em {ano}</span><span className="value">{d.n_pessoal}</span>
          <span className="hint">Conta quem entrou ou saiu durante o ano; não é o tamanho da equipe num dia só.
            {refEquipe && <MediaCasaLinha r={refEquipe} fmt={(v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}
              comparacao={inteiro ? comparacao(d.n_pessoal, refEquipe.valor) : undefined} />}</span></div>}
      </section>
      <FonteGastos p={p} ano={ano} atualizado={meta?.atualizado_em} />

      {partes.length > 1 && (
        <section>
          <h2>Para onde foi o dinheiro em {ano}</h2>
          <Barras rosca={{ titulo: `Custo conhecido de ${p.nome} em ${ano}` }} itens={partes.map((x) => ({ nome: x.label, label: <strong>{x.label}</strong>, nota: x.nota, valor: x.valor, cor: x.cor }))} />
        </section>
      )}

      <SalarioBeneficios p={p} r={r} ano={ano} />
      <Equipe p={p} r={r} ano={ano} ma={ma} folga={folga} meses={d.meses_com_nota} />

      <section>
        <h2>Cota parlamentar</h2>
        <Explain>Além do salário, cada parlamentar tem uma cota mensal para despesas do mandato. Ele paga e pede reembolso apresentando a nota fiscal.</Explain>
        <SemNota d={d} ano={ano} />
        <div className="grid">
          {(Object.keys(d.grupos) as Grupo[]).map((g) => (
            <div className="card stat" key={g}>
              <span className="label"><i style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COR_GRUPO[g], marginRight: 6 }} />{GRUPO_CURTO[g]}</span>
              <span className="value">{reais(d.grupos[g])}</span>
              <span className="hint">{GRUPO_EXPLICA[g]}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>Em que gastou a cota</h2>
        <Barras rosca={{ titulo: `Cota de ${p.nome} em ${ano}, por tipo de gasto`, total: d.total, paleta: true }} itens={d.categorias.slice(0, todas ? 99 : 8).map((c) => ({ label: c.categoria, valor: c.valor }))} />
        {d.categorias.length > 8 && <button className="link" onClick={() => setTodas(!todas)}>{todas ? "Mostrar menos" : `Mostrar todas as ${d.categorias.length} categorias`}</button>}
        <CompararAnos porAno={categoriasAnos} titulo="Como a cota mudou de um ano para outro" anoInicial={ano} limite={8}
          nota="Cada tipo de gasto da cota, ano a ano. O ano em andamento vai só até a última nota publicada." />
      </section>

      <section>
        <div className="grid grid-2 lado-a-lado">
        <div>
        <h2>Quem recebeu o dinheiro da cota</h2>
        <p className="muted small">Empresas e pessoas que emitiram as notas fiscais. Clique numa empresa para ver quem são os donos e se eles têm outras empresas que também recebem de parlamentares.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Fornecedor e donos</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {d.fornecedores.map((f) => (
                <tr key={f.doc + f.nome}>
                  <td>{f.ficha ? <Link to={`/e/${f.doc}`}>{f.nome}</Link> : f.nome}
                    <div className="muted small mono">{f.tipo === "cnpj" ? cnpjFmt(f.doc) : f.tipo === "cpf" ? `Pessoa física ${f.doc}` : ""}</div>
                    {f.socios.length > 0 && <div className="small">Sócios: {f.socios.join(", ")}</div>}</td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(f.valor)}<div className="muted small">{f.n} nota{f.n > 1 ? "s" : ""}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </div>
        <div>
        <h2>Maiores notas fiscais de {ano}</h2>
        <p className="muted small">As notas de maior valor, cada uma com o link para a nota no site oficial.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Fornecedor e tipo de gasto</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {d.maiores_notas.map((n, i) => (
                <tr key={i}>
                  <td>{/^\d{14}$/.test(n.doc) ? <Link to={`/e/${n.doc}`}>{n.fornecedor}</Link> : n.fornecedor}<div className="small muted">{n.categoria}</div>{n.detalhe && <div className="small">{n.detalhe}</div>}
                    <div className="small"><span className="num muted">{dataBR(n.data)}</span> · <LinkNota url={n.url} link={n.link || (n.url ? "nota" : "")} /></div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(n.valor, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </div>
        </div>
        <h2>Cota por mês em {ano}</h2>
        <GastoMensal meses={d.meses} ano={ano} cor="var(--s2)" />
      </section>

      <TodasNotas p={p} d={d} ano={ano} />

      <ForaDoTotal d={d} ano={ano} />
    </>
  );
}

/* Fonte e data dos números do topo da aba (regra: todo número mostra a fonte e a data da última atualização) */
function FonteGastos({ p, ano, atualizado }: { p: Politico; ano: string; atualizado?: string }) {
  const oficial = linkSeguro(p.fonte);
  return (
    <p className="muted small fonte-numeros" data-testid="fonte-gastos">
      {p.casa === "camara"
        ? <>Fontes: <a href={oficial} target="_blank" rel="noreferrer">página oficial do deputado na Câmara ↗</a> (salário, verba de gabinete e total da cota) e <a href={`https://www.camara.leg.br/cotas/Ano-${ano}.csv.zip`} target="_blank" rel="noreferrer">arquivo da cota de {ano} nos dados abertos ↗</a> (cada nota).</>
        : <>Fontes: <a href="https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html" target="_blank" rel="noreferrer">API administrativa do Senado ↗</a> (cota, equipe e outros gastos) e <a href={oficial} target="_blank" rel="noreferrer">página oficial do senador ↗</a>. O salário é o subsídio pago aos deputados, que é o mesmo valor.</>}
      {atualizado && <> Dados coletados em {dataBR(atualizado)}.</>}
    </p>
  );
}

/* Ressalvas da cota do ano escolhido (fim da página): meses fora do mandato e diferença com a página oficial */
function NotasCota({ p }: { p: Politico }) {
  const { ano } = useAno();
  const d = p.anos[ano];
  if (!d) return null;
  const fora = d.fora_do_periodo || 0;
  const diferenca = d.cota_oficial ? d.cota_oficial - (d.total - fora) : 0;
  const nomesMeses = (d.meses_fora || []).map((m) => MESES_LONGOS[m - 1]).join(", ");
  const ft = d.fora_do_total_oficial;
  return (
    <>
      {fora !== 0 && d.cota_oficial != null && (
        <p className="muted small" role="note">A página oficial mostra {reais(d.cota_oficial)} em {ano} porque conta só os meses em que {p.casa === "camara" ? "o deputado" : "o senador"} estava no cargo neste mandato. Aqui somamos também {reais(fora)} de {nomesMeses}: {ano === "2023" && d.meses_fora?.includes(1)
          ? "janeiro de 2023 ainda era o mandato anterior, que a página de 2023 não inclui"
          : fora < 0 ? "são devoluções de passagens creditadas em meses em que estava fora do cargo (por exemplo, licenciado para ser ministro)" : "são notas de meses em que estava fora do cargo"}. Esses valores foram pagos ou devolvidos de fato, por isso ficam na soma.</p>
      )}
      {Math.abs(diferenca) > Math.max(50, Math.abs(d.total - fora) * 0.005) && d.cota_oficial != null && (
        <p className="alert" role="note">A página oficial mostra <strong>{reais(d.cota_oficial)}</strong> de cota em {ano}, e aqui somamos {reais(d.total - fora)}{fora !== 0 ? " nos mesmos meses" : ""}. {diferenca > 0 ? "A página oficial foi atualizada depois da nossa última coleta, ou há despesas ainda sem nota publicada." : "Há notas publicadas que a página oficial ainda não somou."} <Link to="/sobre">Entenda</Link>.</p>
      )}
      {ft && ft.valor !== 0 && (
        <p className="muted small" role="note">O total de {reais(d.total)} é o total oficial do Senado. Ele não soma {reais(ft.valor)} em {ft.n} nota{ft.n > 1 ? "s" : ""} que o Senado publica sem tipo de despesa; elas estão listadas acima, à parte. <Link to="/verificacao#motivo-senado_sem_tipo">Por quê</Link>.</p>
      )}
    </>
  );
}

/* Notas que a fonte publica, mas que o total oficial não soma: aparecem à parte, com o link, sem entrar no total */
function ForaDoTotal({ d, ano }: { d: AnoDetalhe; ano: string }) {
  const ft = d.fora_do_total_oficial;
  if (!ft || !ft.notas.length) return null;
  return (
    <section data-testid="fora-do-total">
      <h2>Notas fora do total oficial em {ano}</h2>
      <Explain>O Senado publica estas {ft.n} nota{ft.n > 1 ? "s" : ""} ({reais(ft.valor)}) sem o tipo de despesa, e o total oficial do senador não as soma. Por isso também não entram no total do site. Mostramos aqui para você conferir.</Explain>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Data</th><th>Fornecedor</th><th className="r">Valor</th><th>Fonte</th></tr></thead>
          <tbody>
            {ft.notas.map((n, i) => (
              <tr key={i}>
                <td className="num">{dataBR(n.data)}</td>
                <td>{/^\d{14}$/.test(n.doc) ? <Link to={`/e/${n.doc}`}>{n.fornecedor}</Link> : n.fornecedor}{n.detalhe && <div className="small">{n.detalhe}</div>}</td>
                <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(n.valor, true)}</td>
                <td className="small"><LinkNota url={n.url} link={n.url ? "nota" : ""} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SalarioBeneficios({ p, r, ano }: { p: Politico; r: Recursos; ano: string }) {
  const linhas: [string, ReactNode][] = [];
  if (r.salario_bruto) linhas.push([r.salario_estimado ? "Salário mensal bruto (subsídio, igual ao dos deputados)" : "Salário mensal bruto (atual)", reais(r.salario_bruto, true)]);
  if (r.salario_ano) linhas.push([`Salário recebido em ${ano}`, reais(r.salario_ano, true)]);
  if (r.imovel_funcional) linhas.push(["Apartamento funcional (imóvel da Câmara)", r.imovel_funcional]);
  if (r.auxilio_moradia) linhas.push(["Auxílio-moradia", r.auxilio_moradia]);
  r.beneficios?.forEach((b) => linhas.push([b.beneficio, b.utilizacao]));
  if (r.viagens_missao != null) linhas.push(["Viagens em missão oficial", String(r.viagens_missao)]);
  if (r.passaporte_diplomatico) linhas.push(["Passaporte diplomático", r.passaporte_diplomatico]);
  if (!linhas.length && !r.outros_gastos?.length) return null;
  return (
    <section>
      <h2>Salário e benefícios</h2>
      {p.casa === "senado" && <Explain>O salário dos senadores é o mesmo dos deputados federais (R$ 46.366,19 por mês desde fevereiro de 2025). O Senado não publica esse valor junto dos outros gastos, então usamos o subsídio pago aos deputados em cada mês, para o ano inteiro. O Senado informa quais benefícios cada senador usou, sem os valores.</Explain>}
      {linhas.length > 0 && <div className="card kv">{linhas.map(([k, v]) => <Fragment key={k}><span>{k}</span><strong>{v}</strong></Fragment>)}</div>}
      {r.salario_meses && r.salario_meses.length > 0 && <>
        <h3>Salário por mês em {ano}</h3>
        <GastoMensal meses={r.salario_meses} ano={ano} />
      </>}
      {r.outros_gastos && r.outros_gastos.length > 0 && <>
        <h3>Outros gastos do mandato em {ano} (fora da cota)</h3>
        <Barras itens={r.outros_gastos.map((o) => ({ label: o.recurso, valor: o.valor, cor: "var(--gold)" }))} />
      </>}
    </section>
  );
}

function Equipe({ p, r, ano, ma, folga, meses }: { p: Politico; r: Recursos; ano: string; ma?: MediasCasaAno; folga: number; meses?: number }) {
  const [todos, setTodos] = useState(false);
  const equipe = r.equipe || [];
  if (!equipe.length && !r.verba_gasto && !r.vinculos?.length) {
    return (
      <section>
        <h2>Equipe do gabinete</h2>
        <Explain>Ainda não há dados da equipe para {ano}. A lista oficial está na <a href={linkSeguro(p.fonte)} target="_blank" rel="noreferrer">página do parlamentar</a>.</Explain>
      </section>
    );
  }
  return (
    <section>
      <h2>Equipe do gabinete</h2>
      {p.casa === "camara"
        ? <Explain>Cada deputado tem uma verba de gabinete para pagar até 25 secretários parlamentares, em Brasília ou no estado. A Câmara mostra quanto foi gasto por mês, mas não o salário de cada assessor nesta lista.</Explain>
        : <Explain>O Senado mostra quem trabalha no gabinete e a função de cada pessoa. Servidores efetivos são concursados; comissionados são escolhidos pelo senador.</Explain>}
      {r.verba_gasto != null && (
        <div className="grid">
          <div className="card stat"><span className="label">Verba de gabinete gasta em {ano}</span><span className="value">{reais(r.verba_gasto)}</span>
            {r.verba_disponivel ? <span className="hint">{Math.round((r.verba_gasto / r.verba_disponivel) * 100)}% do disponível ({reais(r.verba_disponivel)})</span> : null}
            {ma?.verba_gabinete && (() => {
              const ref = referenciaDinheiro(ma.verba_gabinete, p.casa, ano, ma.meses, folga, meses);
              return <span className="hint"><MediaCasaLinha r={ref} fmt={(v) => reais(v)} comparacao={comparacao(r.verba_gasto!, ref.valor)} /></span>;
            })()}</div>
        </div>
      )}
      {p.casa === "camara" && r.verba_gasto != null && !MG && (
        <p className="small">O teto da verba é o mesmo para todo deputado, de qualquer estado. <Link to="/gabinetes">Compare os estados de forma justa, pela população e pelos salários de cada um ›</Link></p>
      )}
      {r.vinculos && r.vinculos.length > 0 && <p>{r.vinculos.map((v) => `${v.quantidade} ${v.vinculo.toLowerCase()}${v.quantidade === 1 ? "" : "s"}`).join(" e ")}.</p>}
      {r.verba_meses && r.verba_meses.length > 0 && <>
        <h3>Verba de gabinete por mês</h3>
        <GastoMensal meses={r.verba_meses} ano={ano} cor="var(--s3)" />
      </>}
      {equipe.length > 0 && <EquipePorCargo equipe={equipe} todos={todos} setTodos={setTodos} />}
    </section>
  );
}

function Votos({ p, meta }: { p: Politico; meta: Meta | null }) {
  const { data: vots } = useData<VotacaoResumo[]>("votacoes.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const [filtro, setFiltro] = useState<"todos" | "contra">("todos");
  const [tema, setTema] = useState("");
  const [voto, setVoto] = useState<"" | "Sim" | "Não" | "outros">("");
  const [mes, setMes] = useState("");
  const [resultado, setResultado] = useState<"" | "sim" | "nao">("");
  const [mostrar, setMostrar] = useState(200);
  const porId = useMemo(() => new Map((vots || []).map((v) => [v.id, v])), [vots]);
  if (!p.votos.length) return <div className="empty">Ainda não há votos nominais registrados para {p.nome} no período.</div>;
  const contra = p.votos.filter((v) => v.partido && (v.voto === "Sim" || v.voto === "Não") && v.voto !== v.partido);
  const meses = [...new Set(p.votos.map((v) => (porId.get(v.votacao)?.data || "").slice(0, 7)).filter((m) => m.length === 7))].sort().reverse();
  const lista = (filtro === "contra" ? contra : p.votos).filter((v) => {
    const info = porId.get(v.votacao);
    if (tema && !info?.temas?.includes(tema)) return false;
    if (voto && (voto === "outros" ? v.voto === "Sim" || v.voto === "Não" : v.voto !== voto)) return false;
    if (mes && !(mes.length === 4 ? info?.data?.startsWith(mes) : info?.data?.slice(0, 7) === mes)) return false;
    if (resultado && (!info || (resultado === "sim") !== !!info.aprovada)) return false;
    return true;
  });
  const conta = (k: "" | "Sim" | "Não" | "outros") => p.votos.filter((v) => !k || (k === "outros" ? v.voto !== "Sim" && v.voto !== "Não" : v.voto === k)).length;
  const temas = Object.entries(p.temas || {}).sort((a, b) => tot(b[1]) - tot(a[1]));
  const colegas = (pols || []).filter((x) => x.casa === p.casa && x.posicao != null);
  // Votos Sim ou Não em que o partido teve maioria: a base da taxa "votou como o partido" (mesma conta da coleta)
  const comPartido = p.votos.filter((v) => v.partido && (v.voto === "Sim" || v.voto === "Não"));
  const comoPartido = comPartido.filter((v) => v.voto === v.partido).length;
  const datas = p.votos.map((v) => porId.get(v.votacao)?.data || "").filter(Boolean).sort();
  const mv = meta?.medias_casa?.votos[p.casa];
  const quemTem = mv ? `com ${mv.min_votos} ou mais votos Sim ou Não` : "";
  return (
    <>
      <section className="grid">
        <div className="card stat"><span className="label">Posição pelos votos</span><span className="value">{p.rotulo}</span>
          <span className="hint">Calculada a partir de {p.n_votos.toLocaleString("pt-BR")} votos nominais no Plenário {nomeCasa(p.casa)}{datas.length ? `, de ${dataBR(datas[0])} a ${dataBR(datas[datas.length - 1])}` : ""}. Votos em comissões não entram.</span></div>
        <div className="card stat"><span className="label">Votou como a maioria do partido</span><span className="value">{pct(p.fidelidade_partido)}</span>
          <span className="hint">Em {comoPartido.toLocaleString("pt-BR")} de {comPartido.length.toLocaleString("pt-BR")} votos Sim ou Não no Plenário.
            {mv?.fidelidade_partido && p.fidelidade_partido != null && <MediaCasaLinha r={referenciaTaxa(mv.fidelidade_partido, p.casa, quemTem)} fmt={pct}
              comparacao={comparacaoPontos(p.fidelidade_partido, mv.fidelidade_partido.media)} />}</span></div>
        {p.alinhamento_governo != null && (
          <div className="card stat"><span className="label">Votou como o governo orientou</span><span className="value">{pct(p.alinhamento_governo)}</span>
            <span className="hint">Nas votações do Plenário em que o líder do governo orientou Sim ou Não.
              {mv?.alinhamento_governo && <MediaCasaLinha r={referenciaTaxa(mv.alinhamento_governo, p.casa, `${quemTem} com orientação do governo`)} fmt={pct}
                comparacao={comparacaoPontos(p.alinhamento_governo, mv.alinhamento_governo.media)} />}</span></div>
        )}
      </section>
      {p.posicao != null && colegas.length > 0 && (
        <section>
          <h2>Onde fica entre os colegas {p.casa === "camara" ? "da Câmara" : "do Senado"}</h2>
          <Espectro destaque={p.id} nomeDestaque={p.nome} pontos={colegas.map((c) => ({ id: c.id, pos: c.posicao!, label: `${c.nome} (${c.partido}-${c.uf})`, href: `/p/${c.id}` }))} />
          <p className="muted small">O ponto dourado, marcado com o nome, é {p.nome}. Passe o mouse sobre os outros pontos para ver quem são.</p>
        </section>
      )}
      {temas.length > 0 && (
        <section>
          <h2>Como votou por tema</h2>
          <Explain>Quantas vezes {p.nome} votou Sim ou Não em propostas de cada tema. Votar Sim nem sempre é ser a favor do tema: uma proposta pode, por exemplo, reduzir um direito. Clique no tema para ver cada votação.</Explain>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Tema</th><th className="r">Sim</th><th className="r">Não</th><th className="r">Outros</th><th className="r">Contra o partido</th></tr></thead>
              <tbody>
                {temas.map(([t, c]) => (
                  <tr key={t}>
                    <td><button className="link" onClick={() => setTema(tema === t ? "" : t)} aria-pressed={tema === t}>{tema === t ? <strong>{t}</strong> : t}</button></td>
                    <td className="r num">{c.Sim || 0}</td><td className="r num">{c["Não"] || 0}</td><td className="r num">{c.Outros || 0}</td><td className="r num">{c.contra_partido || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <section>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Como votou{tema ? ` sobre ${tema.toLowerCase()}` : ""}</h2>
          {tema && <button className="chip" onClick={() => setTema("")}>Tirar filtro de tema ✕</button>}
          <select id="filtro-votos" aria-label="Filtrar votos" value={filtro} onChange={(e) => setFiltro(e.target.value as "todos" | "contra")}>
            <option value="todos">Todas as votações nominais no Plenário ({p.votos.length})</option>
            <option value="contra">Só quando votou contra o partido ({contra.length})</option>
          </select>
        </div>
        <div className="filtros">
          <fieldset><legend>Votou</legend>
            {([["", "Todos"], ["Sim", "Sim"], ["Não", "Não"], ["outros", "Outros (abstenção, obstrução...)"]] as const).map(([k, n]) => (
              <button key={k} className="fchip" aria-pressed={voto === k} onClick={() => { setVoto(k); setMostrar(200); }}>{`${n} (${conta(k)})`}</button>
            ))}
          </fieldset>
          <fieldset><legend>Resultado</legend>
            {([["", "Todos"], ["sim", "Aprovadas"], ["nao", "Rejeitadas"]] as const).map(([k, n]) => (
              <button key={k} className="fchip" aria-pressed={resultado === k} onClick={() => { setResultado(k); setMostrar(200); }}>{n}</button>
            ))}
          </fieldset>
          {meses.length > 1 && (
            <label className="graf-ano"><span className="muted small">Quando</span>
              <select aria-label="Mês" value={mes} onChange={(e) => { setMes(e.target.value); setMostrar(200); }}>
                <option value="">Todos os meses</option>
                {[...new Set(meses.map((m) => m.slice(0, 4)))].map((a) => (
                  <optgroup key={a} label={a}>
                    <option value={a}>{`Todo o ano de ${a}`}</option>
                    {meses.filter((m) => m.startsWith(a)).map((m) => <option key={m} value={m}>{`${MESES_LONGOS[Number(m.slice(5)) - 1]} de ${a}`}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
          )}
          <span className="filtros-conta">{`${lista.length} votaç${lista.length === 1 ? "ão" : "ões"}`}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="so-largo">Data</th><th>O que foi votado</th><th className="so-largo">Voto</th><th className="so-largo">Maioria do partido</th><th className="so-largo">Resultado</th></tr></thead>
            <tbody>
              {lista.slice(0, mostrar).map((v) => {
                const info = porId.get(v.votacao);
                return (
                  <tr key={v.votacao}>
                    <td className="num so-largo">{info ? dataBR(info.data) : ""}</td>
                    <td><Link to={`/v/${v.votacao}`}>{info ? (proposicaoNome(info.proposicao) || "Votação") : v.votacao}</Link>{info && tipoVotacao(info.descricao) && <> <span className="chip">{tipoVotacao(info.descricao)}</span></>}
                      {info && descricaoCurta(info.descricao) && <div className="small">{descricaoCurta(info.descricao).slice(0, 200)}</div>}
                      {info?.proposicao?.ementa && <div className="small muted">{info.proposicao.ementa.slice(0, 140)}</div>}
                      <div className="small so-celular voto-linha">
                        {info && <span className="num muted">{dataBR(info.data)}</span>}
                        <span>Votou <VotoChip voto={v.voto} /></span>
                        {v.partido && <span>Partido <VotoChip voto={v.partido} /></span>}
                        {info && <span>Resultado <ResultadoChip aprovada={info.aprovada} /></span>}
                      </div></td>
                    <td className="so-largo"><VotoChip voto={v.voto} /></td>
                    <td className="so-largo">{v.partido ? <VotoChip voto={v.partido} /> : <span className="muted">—</span>}</td>
                    <td className="so-largo">{info ? <ResultadoChip aprovada={info.aprovada} /> : <span className="muted">—</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {lista.length > mostrar && <p className="row" style={{ gap: 12, alignItems: "center" }}><span className="filtros-conta">{`Mostrando ${mostrar} de ${lista.length}.`}</span>
          <button className="btn alt" onClick={() => setMostrar((m) => m + 200)}>Mostrar mais 200</button></p>}
      </section>
    </>
  );
}

const tot = (c: Record<string, number | undefined>) => (c.Sim || 0) + (c["Não"] || 0) + (c.Outros || 0);

/* Passagens que faltam nos dados abertos e a diferença que sobra, explicadas */
/* Todas as notas fiscais do ano, cada uma com o tipo de despesa oficial (carro alugado, aluguel de escritório...),
   com filtro por tipo e por fornecedor. O arquivo é carregado só quando a seção aparece. */
function TodasNotas({ p, d, ano }: { p: Politico; d: AnoDetalhe; ano: string }) {
  const n_ano = d.n_notas || 0;
  const { data, error } = useData<NotasPolitico>(n_ano ? `p/notas/${p.id}-${ano}.json` : null);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [n, setN] = useState(50);
  const notas = useMemo(() => {
    if (!data) return [];
    const i = (c: string) => data.colunas.indexOf(c);
    const [iData, iCat, iForn, iDoc, iValor, iUrl, iLink, iDet] = ["data", "categoria", "fornecedor", "doc", "valor", "url", "link", "detalhe"].map(i);
    return data.notas.map((x) => ({ data: String(x[iData] || ""), categoria: String(x[iCat]), fornecedor: String(x[iForn]), doc: String(x[iDoc] || ""),
      valor: Number(x[iValor]), url: String(x[iUrl] || ""), link: String(x[iLink] || ""), detalhe: String(x[iDet] || "") }));
  }, [data]);
  // Tipos de despesa agrupados pelo tema simples, com quantas notas e quanto somam (do maior para o menor)
  const grupos = useMemo(() => {
    const porCat = new Map<string, { n: number; valor: number }>();
    for (const x of notas) { const c = porCat.get(x.categoria) || { n: 0, valor: 0 }; c.n++; c.valor += x.valor; porCat.set(x.categoria, c); }
    const porTema = new Map<string, { valor: number; cats: [string, { n: number; valor: number }][] }>();
    for (const [c, v] of porCat) {
      const t = data?.temas[c] || c;
      const g = porTema.get(t) || { valor: 0, cats: [] };
      g.valor += v.valor; g.cats.push([c, v]); porTema.set(t, g);
    }
    return [...porTema].sort((a, b) => b[1].valor - a[1].valor).map(([t, g]) => [t, g.cats.sort((a, b) => b[1].valor - a[1].valor)] as const);
  }, [notas, data]);
  const lista = useMemo(() => notas.filter((x) => (!cat || x.categoria === cat) && (!q || norm(`${x.fornecedor} ${x.detalhe}`).includes(norm(q)))), [notas, cat, q]);
  const soma = lista.reduce((s, x) => s + x.valor, 0);
  const comListas = Object.keys(p.anos).filter((a) => p.anos[a].n_notas).sort();
  return (
    <section id="todas-notas">
      <h2>Todas as notas fiscais de {ano}{n_ano ? ` (${n_ano.toLocaleString("pt-BR")})` : ""}</h2>
      <p className="muted small">Cada nota com o tipo de despesa oficial (por exemplo, aluguel de carro, aluguel de escritório, combustível ou divulgação), como a fonte oficial informa, e o link para o documento original.</p>
      {d.n_notas === undefined ? <div className="empty">A lista completa de notas está disponível só para os anos mais recentes{comListas.length ? ` (${comListas.join(", ")})` : ""}. Escolha o ano no topo da página. Acima estão as maiores notas de {ano}.</div>
        : !n_ano ? <div className="empty">Nenhuma nota fiscal publicada para {p.nome} em {ano}.</div>
        : !data ? <Loading error={error} /> : <>
        <div className="search">
          <select aria-label="Tipo de despesa" value={cat} onChange={(ev) => { setCat(ev.target.value); setN(50); }}>
            <option value="">Todos os tipos de despesa ({notas.length.toLocaleString("pt-BR")})</option>
            {grupos.map(([tema, cats]) => (
              <optgroup key={tema} label={tema}>
                {cats.map(([c, v]) => <option key={c} value={c}>{`${c} · ${v.n.toLocaleString("pt-BR")} ${v.n > 1 ? "notas" : "nota"} · ${reais(v.valor)}`}</option>)}
              </optgroup>
            ))}
          </select>
          <input aria-label="Filtrar por fornecedor" value={q} onChange={(ev) => { setQ(ev.target.value); setN(50); }} placeholder="Filtrar por fornecedor" />
        </div>
        <p className="small" role="status"><strong>{lista.length.toLocaleString("pt-BR")}</strong> {lista.length !== 1 ? "notas" : "nota"} · <strong className="num">{reais(soma, true)}</strong>{cat && <> em <em>{cat}</em></>}</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th className="so-largo">Data</th><th>Tipo de despesa e fornecedor</th><th className="r">Valor</th><th className="so-largo">Nota</th></tr></thead>
            <tbody>
              {lista.slice(0, n).map((x, i) => (
                <tr key={i}>
                  <td className="num so-largo">{x.data ? dataBR(x.data) : "Sem data"}</td>
                  <td><button className="chip cat-nota" title="Ver só as notas deste tipo" onClick={() => { setCat(x.categoria); setN(50); }}>{x.categoria}</button>
                    <div>{/^\d{14}$/.test(x.doc) ? <Link to={`/e/${x.doc}`}>{x.fornecedor}</Link> : x.fornecedor}{x.doc && !/^\d{14}$/.test(x.doc) && <span className="small muted mono"> · {x.doc}</span>}</div>
                    {x.detalhe && <div className="small">{x.detalhe}</div>}
                    <div className="small so-celular"><span className="num muted">{x.data ? dataBR(x.data) : "Sem data"}</span> · <LinkNota url={x.url} link={x.link || (x.url ? "nota" : "")} /></div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{reais(x.valor, true)}</td>
                  <td className="small so-largo"><LinkNota url={x.url} link={x.link || (x.url ? "nota" : "")} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {lista.length > n && <button className="link" onClick={() => setN(n + 200)}>Mostrar mais notas ({(lista.length - n).toLocaleString("pt-BR")} restantes)</button>}
        <p className="muted small">{p.casa === "camara"
          ? "Fonte: arquivo anual da cota da Câmara dos Deputados (dados abertos), campo do tipo de despesa. \"Abrir nota\" mostra a imagem da nota fiscal no site oficial; passagens compradas pela Câmara e contas de telefone não têm imagem e abrem a página oficial da despesa."
          : "Fonte: API de despesas da cota (CEAPS) do Senado Federal, campo do tipo de despesa. O Senado não publica a imagem das notas: o link abre a lista oficial de despesas do senador, por tipo e ano."}</p>
        {(d.sem_nota_meses || []).length > 0 && <p className="muted small">Valores que a página oficial soma mas que ainda não têm nota publicada não aparecem nesta lista (veja o aviso no início da cota).</p>}
      </>}
    </section>
  );
}

function SemNota({ d, ano }: { d: AnoDetalhe; ano: string }) {
  const lista = d.passagens_da_lista;
  const resto = d.sem_nota_meses || [];
  if (!(lista && lista.n) && !resto.length) return null;
  const totalResto = resto.reduce((a, x) => a + x.valor, 0);
  return (
    <div className="card" style={{ padding: "12px 16px", margin: "8px 0 16px" }}>
      <strong>Passagens aéreas que não estão nos dados abertos</strong>
      <p className="small" style={{ margin: "6px 0" }}>
        Desde agosto de 2025, o arquivo de dados abertos da Câmara deixou de trazer as passagens compradas pelo sistema da própria Câmara (SIGEPA). Essas passagens não têm nota fiscal: a Câmara compra direto da companhia aérea e registra o bilhete. A página oficial do deputado continua somando esse valor, e a lista oficial de despesas mostra cada bilhete.
      </p>
      {lista && lista.n > 0 && (
        <p className="small" style={{ margin: "6px 0" }}>
          Em {ano}, buscamos na lista oficial <strong>{lista.n.toLocaleString("pt-BR")} bilhete{lista.n > 1 ? "s" : ""}</strong> ({reais(lista.valor)}). Eles aparecem como "Passagem aérea (comprada pela Câmara)", com a companhia, a data, o número do bilhete e o link "Ver detalhe na Câmara". Valores negativos são bilhetes devolvidos ou remarcados.
        </p>
      )}
      {resto.length > 0 && (
        <>
          <p className="small" style={{ margin: "6px 0" }}>
            Ainda sobra <strong>{reais(totalResto)}</strong> que a página oficial soma e que não aparece em nenhuma nota nem na lista de despesas. Mostramos esse valor como "Despesas sem nota nos dados abertos" para o total ficar igual ao oficial. Mês a mês:
          </p>
          <div className="small" style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px" }}>
            {resto.map((x) => <span key={x.mes}>{MESES_LONGOS[x.mes - 1]}: <span className="num">{reais(x.valor)}</span>{linkSeguro(x.url) && <> · <a href={linkSeguro(x.url)} target="_blank" rel="noreferrer">ver o mês na Câmara ↗</a></>}</span>)}
          </div>
        </>
      )}
    </div>
  );
}

/** A equipe do gabinete em gráfico por cargo; cada cargo abre a lista de nomes, e cada nome mostra o detalhe */
function EquipePorCargo({ equipe, todos, setTodos }: { equipe: Pessoa[]; todos: boolean; setTodos: (v: boolean) => void }) {
  const [busca, setBusca] = useState("");
  const porCargo = Object.entries(equipe.reduce((acc, x) => { (acc[x.grupo || "Sem cargo informado"] ||= []).push(x); return acc; }, {} as Record<string, Pessoa[]>))
    .sort((a, b) => b[1].length - a[1].length);
  const achados = busca ? equipe.filter((x) => norm(`${x.nome} ${x.cargo} ${x.grupo}`).includes(norm(busca))) : [];
  return (
    <>
      <h3>Quem trabalha no gabinete, por cargo</h3>
      <Barras fmt={(v) => `${v} pessoa${v === 1 ? "" : "s"}`} itens={porCargo.map(([g, l]) => ({ label: g, valor: l.length, cor: "var(--s3)" }))} />
      <div className="search"><input id="busca-equipe" aria-label="Procurar na equipe" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Procurar um nome ou cargo" /></div>
      {busca ? <ListaEquipe lista={achados} /> : porCargo.slice(0, todos ? 99 : 6).map(([g, l]) => (
        <Abrir key={g} titulo={<>{g} · {l.length} pessoa{l.length === 1 ? "" : "s"}</>}><ListaEquipe lista={l} /></Abrir>
      ))}
      {!busca && porCargo.length > 6 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar os ${porCargo.length} cargos`}</button>}
    </>
  );
}

function ListaEquipe({ lista }: { lista: Pessoa[] }) {
  if (!lista.length) return <p className="small muted">Ninguém com esse nome ou cargo.</p>;
  return (
    <div className="table-wrap">
      <table className="small">
        <thead><tr><th>Nome</th><th>Cargo e nível</th><th>Período</th></tr></thead>
        <tbody>{lista.map((x, i) => (
          <tr key={i}><td>{x.nome}</td><td>{x.grupo}<div className="muted">{x.cargo}</div></td><td className="num">{x.periodo}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
