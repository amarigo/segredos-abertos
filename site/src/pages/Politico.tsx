import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Barras, COR_GRUPO, Espectro, Explain, GastoMensal, Loading, VotoChip, useData } from "../components/ui";
import {
  GRUPO_CURTO, GRUPO_EXPLICA, casaNome, cnpjFmt, dataBR, pct, proposicaoNome, reais,
  type Grupo, type Meta, type Politico, type Resumo, type VotacaoResumo,
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
        <button role="tab" aria-selected={aba === "gastos"} onClick={() => setAba("gastos")}>Gastos</button>
        <button role="tab" aria-selected={aba === "votos"} onClick={() => setAba("votos")}>Votos</button>
      </div>
      {aba === "gastos" ? <Gastos p={p} meta={meta} /> : <Votos p={p} />}
    </>
  );
}

function Gastos({ p, meta }: { p: Politico; meta: Meta | null }) {
  const media = meta?.medias[p.casa] || 0;
  const vezes = media ? p.total / media : 0;
  const [todas, setTodas] = useState(false);
  return (
    <>
      <section className="grid">
        <div className="card stat">
          <span className="label">Total pedido de reembolso{meta ? ` (${meta.anos.join(" e ")})` : ""}</span>
          <span className="value">{reais(p.total)}</span>
          {media > 0 && <span className="hint">{vezes >= 1.05 ? `${vezes.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}× a média` : vezes <= 0.95 ? `${Math.round((1 - vezes) * 100)}% abaixo da média` : "Na média"} {p.casa === "camara" ? "dos deputados" : "dos senadores"} ({reais(media)})</span>}
        </div>
        {(Object.keys(p.grupos) as Grupo[]).map((g) => (
          <div className="card stat" key={g}>
            <span className="label"><i style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: COR_GRUPO[g], marginRight: 6 }} />{GRUPO_CURTO[g]}</span>
            <span className="value">{reais(p.grupos[g])}</span>
            <span className="hint">{GRUPO_EXPLICA[g]}</span>
          </div>
        ))}
      </section>

      <section>
        <h2>Equipe do gabinete</h2>
        <Explain>Os salários dos assessores são pagos por uma verba separada da cota (verba de gabinete). Estamos incluindo esses dados na próxima etapa. Enquanto isso, a lista oficial está na <a href={p.fonte} target="_blank" rel="noreferrer">página do parlamentar</a>.</Explain>
      </section>

      <section>
        <h2>Gasto por mês</h2>
        <GastoMensal meses={p.meses} />
      </section>

      <section>
        <h2>Em que gastou</h2>
        <Barras itens={p.categorias.slice(0, todas ? 99 : 8).map((c) => ({ label: c.categoria, valor: c.valor, cor: COR_GRUPO[c.grupo] }))} />
        {p.categorias.length > 8 && <button className="link" onClick={() => setTodas(!todas)}>{todas ? "Mostrar menos" : `Mostrar todas as ${p.categorias.length} categorias`}</button>}
      </section>

      <section>
        <h2>Quem recebeu o dinheiro</h2>
        <Explain>Empresas e pessoas que emitiram as notas fiscais. Clique numa empresa para ver quem são os donos e se eles têm outras empresas que também recebem de parlamentares.</Explain>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Fornecedor e donos</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {p.fornecedores.map((f) => (
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
        <h2>Maiores notas fiscais</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Data</th><th>Fornecedor e tipo de gasto</th><th className="r">Valor</th></tr></thead>
            <tbody>
              {p.maiores_notas.map((n, i) => (
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
