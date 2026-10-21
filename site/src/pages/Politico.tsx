import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Barras, COR_GRUPO, Espectro, Explain, GastoMensal, Loading, VotoChip, useAno, useData } from "../components/ui";
import {
  GRUPO_CURTO, GRUPO_EXPLICA, casaNome, cnpjFmt, dataBR, pct, proposicaoNome, reais,
  type Grupo, type Meta, type Politico, type Recursos, type Resumo, type VotacaoResumo,
} from "../data";

export default function PoliticoPage() {
  const { id = "" } = useParams();
  const { data: p, error } = useData<Politico>(`p/${id}.json`);
  const { data: meta } = useData<Meta>("meta.json");
  const [params, setParams] = useSearchParams();
  const aba = params.get("aba") === "votos" ? "votos" : "gastos";
  const setAba = (a: "gastos" | "votos") => setParams(a === "votos" ? { aba: a } : {}, { replace: true });
  if (!p) return <Loading error={error} />;
  return (
    <>
      <section className="profile">
        {p.foto ? <img src={p.foto} alt={`Foto de ${p.nome}`} /> : <span className="avatar" style={{ width: 112, height: 112 }} />}
        <div>
          <span className="eyebrow">{p.cargo} · {p.uf}</span>
          <h1>{p.nome}</h1>
          <div className="tags">
            <span className="chip">{p.partido}</span>
            {p.posicao != null && <span className="chip">{p.rotulo}</span>}
            {p.campo && <span className="chip">{p.campo}</span>}
            <a className="chip" href={p.fonte} target="_blank" rel="noreferrer">Página oficial ↗</a>
          </div>
        </div>
      </section>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={aba === "gastos"} onClick={() => setAba("gastos")}>Gastos e equipe</button>
        <button role="tab" aria-selected={aba === "votos"} onClick={() => setAba("votos")}>Votos</button>
      </div>
      {aba === "gastos" ? <Gastos p={p} meta={meta} /> : <Votos p={p} />}
    </>
  );
}

function Gastos({ p, meta }: { p: Politico; meta: Meta | null }) {
  const { ano } = useAno();
  const [todas, setTodas] = useState(false);
  const d = p.anos[ano];
  if (!d) return <div className="empty">Não há gastos registrados para {p.nome} em {ano}. Escolha outro ano no topo da página.</div>;
  const r = d.recursos || {};
  const media = meta?.medias[ano]?.[p.casa] || 0;
  const vezes = media ? d.total / media : 0;
  const partes = [
    { label: "Salário", valor: d.salario || 0, nota: "Pago ao próprio parlamentar, antes dos descontos.", cor: "var(--s1)" },
    { label: "Equipe do gabinete (verba de gabinete)", valor: d.verba_gabinete || 0, nota: "Salários dos assessores.", cor: "var(--s3)" },
    { label: "Cota parlamentar", valor: d.total, nota: "Reembolsos com nota fiscal: viagens, escritório, divulgação.", cor: "var(--s2)" },
    { label: "Outros gastos do mandato", valor: d.outros_gastos || 0, nota: "Fora da cota: correios, diárias e passagens de viagens oficiais.", cor: "var(--gold)" },
  ].filter((x) => x.valor > 0);
  const diferenca = d.cota_oficial ? d.cota_oficial - d.total : 0;
  return (
    <>
      <section className="grid">
        <div className="card stat">
          <span className="label">Custo conhecido em {ano}</span>
          <span className="value">{reais(d.custo_total)}</span>
          <span className="hint">Soma de salário, equipe, cota e outros gastos informados pelos sites oficiais.</span>
        </div>
        <div className="card stat">
          <span className="label">Cota parlamentar em {ano}</span>
          <span className="value">{reais(d.total)}</span>
          {media > 0 && <span className="hint">{vezes >= 1.05 ? `${vezes.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}× a média` : vezes <= 0.95 ? `${Math.round((1 - vezes) * 100)}% abaixo da média` : "Na média"} {p.casa === "camara" ? "dos deputados" : "dos senadores"} ({reais(media)})</span>}
        </div>
        {d.n_pessoal != null && <div className="card stat"><span className="label">Pessoas na equipe em {ano}</span><span className="value">{d.n_pessoal}</span><span className="hint">Inclui quem entrou ou saiu durante o ano.</span></div>}
      </section>

      {partes.length > 1 && (
        <section>
          <h2>Para onde foi o dinheiro em {ano}</h2>
          <Barras itens={partes.map((x) => ({ label: <strong>{x.label}</strong>, nota: x.nota, valor: x.valor, cor: x.cor }))} />
        </section>
      )}

      <SalarioBeneficios p={p} r={r} ano={ano} />
      <Equipe p={p} r={r} ano={ano} />

      <section>
        <h2>Cota parlamentar</h2>
        <Explain>Além do salário, cada parlamentar tem uma cota mensal para despesas do mandato. Ele paga e pede reembolso apresentando a nota fiscal.</Explain>
        {d.categorias.some((c) => c.categoria === "Passagens aéreas sem nota publicada") && (
          <p className="muted small">"Passagens aéreas sem nota publicada": desde agosto de 2025 a Câmara soma as passagens compradas pelo próprio sistema na página do deputado, mas não publica essas notas nos dados abertos. Usamos o valor oficial de cada mês para o total ficar igual ao da Câmara.</p>
        )}
        {Math.abs(diferenca) > Math.max(50, d.total * 0.005) && d.cota_oficial != null && (
          <p className="alert" role="note">A página oficial mostra <strong>{reais(d.cota_oficial)}</strong> de cota em {ano}, e aqui somamos {reais(d.total)}. {diferenca > 0 ? "A página oficial foi atualizada depois da nossa última coleta, ou há despesas ainda sem nota publicada." : "Há notas publicadas que a página oficial ainda não somou."} <Link to="/sobre">Entenda</Link>.</p>
        )}
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
        <h2>Cota por mês em {ano}</h2>
        <GastoMensal meses={d.meses} ano={ano} cor="var(--s2)" />
      </section>

      <section>
        <h2>Em que gastou a cota</h2>
        <Barras itens={d.categorias.slice(0, todas ? 99 : 8).map((c) => ({ label: c.categoria, valor: c.valor, cor: COR_GRUPO[c.grupo] }))} />
        {d.categorias.length > 8 && <button className="link" onClick={() => setTodas(!todas)}>{todas ? "Mostrar menos" : `Mostrar todas as ${d.categorias.length} categorias`}</button>}
      </section>

      <section>
        <h2>Quem recebeu o dinheiro da cota</h2>
        <Explain>Empresas e pessoas que emitiram as notas fiscais. Clique numa empresa para ver quem são os donos e se eles têm outras empresas que também recebem de parlamentares.</Explain>
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
      </section>

      <section>
        <h2>Maiores notas fiscais de {ano}</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Data</th><th>Fornecedor e tipo de gasto</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {d.maiores_notas.map((n, i) => (
                <tr key={i}>
                  <td className="num">{dataBR(n.data)}</td>
                  <td>{n.doc.length === 14 ? <Link to={`/e/${n.doc}`}>{n.fornecedor}</Link> : n.fornecedor}<div className="small muted">{n.categoria}</div></td>
                  <td className="r num" style={{ whiteSpace: "nowrap" }}>{n.url ? <a href={n.url} target="_blank" rel="noreferrer">{reais(n.valor, true)}</a> : reais(n.valor, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">Quando o valor é um link, ele abre a nota fiscal original.</p>
      </section>
    </>
  );
}

function SalarioBeneficios({ p, r, ano }: { p: Politico; r: Recursos; ano: string }) {
  const linhas: [string, ReactNode][] = [];
  if (r.salario_bruto) linhas.push(["Salário mensal bruto (atual)", reais(r.salario_bruto, true)]);
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
      {p.casa === "senado" && <Explain>O salário dos senadores é o mesmo dos deputados federais (R$ 46.366,19 por mês desde fevereiro de 2025). O Senado informa quais benefícios cada senador usou, sem os valores.</Explain>}
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

function Equipe({ p, r, ano }: { p: Politico; r: Recursos; ano: string }) {
  const [todos, setTodos] = useState(false);
  const equipe = r.equipe || [];
  if (!equipe.length && !r.verba_gasto && !r.vinculos?.length) {
    return (
      <section>
        <h2>Equipe do gabinete</h2>
        <Explain>Ainda não há dados da equipe para {ano}. A lista oficial está na <a href={p.fonte} target="_blank" rel="noreferrer">página do parlamentar</a>.</Explain>
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
            {r.verba_disponivel ? <span className="hint">{Math.round((r.verba_gasto / r.verba_disponivel) * 100)}% do disponível ({reais(r.verba_disponivel)})</span> : null}</div>
        </div>
      )}
      {r.vinculos && r.vinculos.length > 0 && <p>{r.vinculos.map((v) => `${v.quantidade} ${v.vinculo.toLowerCase()}${v.quantidade === 1 ? "" : "s"}`).join(" e ")}.</p>}
      {r.verba_meses && r.verba_meses.length > 0 && <>
        <h3>Verba de gabinete por mês</h3>
        <GastoMensal meses={r.verba_meses} ano={ano} cor="var(--s3)" />
      </>}
      {equipe.length > 0 && <>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Nome</th><th>Cargo</th><th>Período</th></tr></thead>
            <tbody>
              {equipe.slice(0, todos ? 999 : 15).map((x, i) => (
                <tr key={i}><td>{x.nome}</td><td className="small">{x.grupo}<div className="muted">{x.cargo}</div></td><td className="small num">{x.periodo}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        {equipe.length > 15 && <button className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar menos" : `Mostrar as ${equipe.length} linhas`}</button>}
      </>}
    </section>
  );
}

function Votos({ p }: { p: Politico }) {
  const { data: vots } = useData<VotacaoResumo[]>("votacoes.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const [filtro, setFiltro] = useState<"todos" | "contra">("todos");
  const porId = useMemo(() => new Map((vots || []).map((v) => [v.id, v])), [vots]);
  if (!p.votos.length) return <div className="empty">Ainda não há votos nominais registrados para {p.nome} no período.</div>;
  const contra = p.votos.filter((v) => v.partido && (v.voto === "Sim" || v.voto === "Não") && v.voto !== v.partido);
  const lista = filtro === "contra" ? contra : p.votos;
  const colegas = (pols || []).filter((x) => x.casa === p.casa && x.posicao != null);
  return (
    <>
      <section className="grid">
        <div className="card stat"><span className="label">Posição pelos votos</span><span className="value">{p.rotulo}</span><span className="hint">Calculada a partir de {p.n_votos} votos nominais.</span></div>
        <div className="card stat"><span className="label">Vota com o próprio partido</span><span className="value">{pct(p.fidelidade_partido)}</span><span className="hint">das vezes em que votou Sim ou Não.</span></div>
        {p.alinhamento_governo != null && (
          <div className="card stat"><span className="label">Vota com o governo</span><span className="value">{pct(p.alinhamento_governo)}</span><span className="hint">quando o líder do governo orientou a votação.</span></div>
        )}
      </section>
      {p.posicao != null && colegas.length > 0 && (
        <section>
          <h2>Onde fica entre os colegas da {casaNome(p.casa)}</h2>
          <Espectro destaque={p.id} pontos={colegas.map((c) => ({ id: c.id, pos: c.posicao!, label: `${c.nome} (${c.partido}-${c.uf})`, href: `/p/${c.id}` }))} />
          <p className="muted small">O ponto amarelo é {p.nome}. Passe o mouse sobre os outros pontos para ver quem são.</p>
        </section>
      )}
      <section>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Como votou</h2>
          <select id="filtro-votos" aria-label="Filtrar votos" value={filtro} onChange={(e) => setFiltro(e.target.value as "todos" | "contra")}>
            <option value="todos">Todas as votações ({p.votos.length})</option>
            <option value="contra">Só quando votou contra o partido ({contra.length})</option>
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Data</th><th>O que foi votado</th><th>Voto</th><th>Maioria do partido</th></tr></thead>
            <tbody>
              {lista.slice(0, 300).map((v) => {
                const info = porId.get(v.votacao);
                return (
                  <tr key={v.votacao}>
                    <td className="num">{info ? dataBR(info.data) : ""}</td>
                    <td><Link to={`/v/${v.votacao}`}>{info ? (proposicaoNome(info.proposicao) || "Votação") : v.votacao}</Link>
                      {info && <div className="small muted">{(info.proposicao?.ementa || info.descricao).slice(0, 180)}</div>}</td>
                    <td><VotoChip voto={v.voto} /></td>
                    <td>{v.partido ? <VotoChip voto={v.partido} /> : <span className="muted">—</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {lista.length > 300 && <p className="muted small">Mostrando as 300 votações mais recentes.</p>}
      </section>
    </>
  );
}
