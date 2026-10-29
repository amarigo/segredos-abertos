import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain } from "../components/ui";
import { corPartido, dataBR, reaisCurto } from "../data";
import { ATUALIZADO_EM, CASOS } from "../corrupcao/dados";
import { corCampo, FONTE_IDEOLOGIA, infoPartido } from "../corrupcao/partidos";
import { NIVEL_NOME, ORDEM, PADRAO, placar, porCampo, resumoGeral, STATUS, type LinhaPlacar } from "../corrupcao/placar";
import type { Caso, Situacao, Status } from "../corrupcao/tipos";
import "./corrupcao.css";

export const SITUACAO: Record<Situacao, { nome: string; cls: string }> = {
  encerrado: { nome: "Encerrado", cls: "sit-fim" },
  parcial: { nome: "Parte julgada, parte em aberto", cls: "sit-parcial" },
  investigacao: { nome: "Em investigação", cls: "sit-aberto" },
};

export function SituacaoChip({ s }: { s: Situacao }) {
  return <span className={`chip sit ${SITUACAO[s].cls}`}>{SITUACAO[s].nome}</span>;
}

/** Sigla com a cor do partido e, se mudou de nome, o nome de hoje */
export function PartidoChip({ sigla }: { sigla: string }) {
  const hoje = infoPartido(sigla).hoje;
  return (
    <span className="partido-chip" title={hoje !== sigla ? `${sigla} hoje se chama ${hoje}` : undefined}>
      <i className="partido-cor" style={{ background: corPartido(hoje) }} />
      {sigla}{hoje !== sigla && <span className="muted"> (hoje {hoje})</span>}
    </span>
  );
}

function partidosDoCaso(c: Caso): string[] {
  const s = new Set<string>();
  for (const p of c.pessoas) if (p.partido && p.status !== "sem_acusacao") s.add(p.partido);
  for (const g of c.grupos || []) s.add(g.partido);
  return [...s];
}

function CartaoCaso({ c }: { c: Caso }) {
  const partidos = partidosDoCaso(c);
  const n = c.pessoas.length + (c.grupos || []).reduce((a, g) => a + g.n, 0);
  return (
    <Link to={`/corrupcao/${c.id}`} className="card caso-card">
      <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
        <span className="muted small">{c.periodo}</span>
        <SituacaoChip s={c.situacao} />
      </div>
      <h3 style={{ margin: 0 }}>{c.nome}</h3>
      <p className="small" style={{ margin: 0 }}>{c.subtitulo}</p>
      {c.valorNum > 0 && <div><span className="caso-valor">{c.valor.texto}</span></div>}
      <div className="muted small">{n} pessoas e grupos citados</div>
      <div className="caso-partidos">{partidos.map((p) => <PartidoChip key={p} sigla={p} />)}</div>
    </Link>
  );
}

/** Barra empilhada de um partido no placar, uma cor por situação */
function BarraPlacar({ l, incluir, max }: { l: LinhaPlacar; incluir: Status[]; max: number }) {
  return (
    <div className="placar-barra" aria-hidden="true" style={{ width: `${(l.total / max) * 100}%` }}>
      {ORDEM.filter((s) => incluir.includes(s) && l.por[s] > 0).map((s) => (
        <span key={s} style={{ flex: l.por[s], background: STATUS[s].cor }} title={`${STATUS[s].nome}: ${l.por[s]}`} />
      ))}
    </div>
  );
}

export function Placar() {
  const [incluir, setIncluir] = useState<Status[]>(PADRAO);
  const linhas = useMemo(() => placar(CASOS, incluir), [incluir]);
  const campos = useMemo(() => porCampo(linhas), [linhas]);
  const max = Math.max(1, ...linhas.map((l) => l.total));
  const opcoes: Status[] = ["condenado", "condenado_recorre", "anulado", "reu", "indiciado", "investigado", "citado", "absolvido"];
  const alternar = (s: Status) => setIncluir((xs) => (xs.includes(s) ? xs.filter((x) => x !== s) : [...xs, s]));
  const nomeCaso = (id: string) => CASOS.find((c) => c.id === id)?.nome.split(" (")[0] || id;
  return (
    <section id="placar">
      <h2>Placar por partido</h2>
      <Explain>
        Quantas pessoas de cada partido aparecem nos {CASOS.length} casos, pela situação de cada uma na Justiça. Vale o partido <strong>da época dos fatos</strong>, somado com o nome de hoje (PMDB e MDB contam juntos; PR e PL também).
        Escolha abaixo o que entra na conta: por padrão vão de condenados a investigados. Citados e absolvidos ficam de fora, mas dá para incluir.
      </Explain>
      <fieldset className="placar-filtro">
        <legend className="muted small">O que contar</legend>
        {opcoes.map((s) => (
          <label key={s} className="placar-opcao" title={STATUS[s].explica}>
            <input type="checkbox" checked={incluir.includes(s)} onChange={() => alternar(s)} />
            <i style={{ background: STATUS[s].cor }} />{STATUS[s].nome}
          </label>
        ))}
      </fieldset>
      {!linhas.length && <div className="empty">Escolha pelo menos uma situação.</div>}
      <ol className="placar">
        {linhas.map((l, i) => (
          <li key={l.partido} className="placar-linha">
            <span className="placar-pos num">{i + 1}º</span>
            <div className="placar-nome">
              <strong><i className="partido-cor" style={{ background: corPartido(l.partido) }} />{l.partido}</strong>
              {l.siglas.some((s) => s !== l.partido) && <span className="muted small"> (na época: {l.siglas.join(", ")})</span>}
              <div><span className="campo-chip" style={{ borderColor: corCampo(l.campo), color: "var(--ink-2)" }}>{l.campo}</span>
                {l.nota != null && <span className="muted small"> nota {l.nota.toLocaleString("pt-BR")} de 10</span>}</div>
            </div>
            <span className="placar-total num">{l.total}</span>
            <div className="placar-detalhe">
              <BarraPlacar l={l} incluir={incluir} max={max} />
              <div className="small muted">
                {ORDEM.filter((s) => incluir.includes(s) && l.por[s] > 0).map((s) => `${l.por[s]} ${STATUS[s].nome.toLowerCase()}`).join(" · ")}
              </div>
              <div className="small">
                Em {l.casos.length} caso{l.casos.length > 1 ? "s" : ""}: {l.casos.map((id, k) => <Fragment key={id}>{k > 0 && ", "}<Link to={`/corrupcao/${id}`}>{nomeCaso(id)}</Link></Fragment>)}
              </div>
              {l.maior && <div className="small"><span className="muted">Cargo mais alto envolvido:</span> {l.maior.papel} ({l.maior.nome})</div>}
            </div>
          </li>
        ))}
      </ol>
      <div className="legend" style={{ marginTop: 12 }}>
        {ORDEM.filter((s) => incluir.includes(s)).map((s) => <span key={s} title={STATUS[s].explica}><i style={{ background: STATUS[s].cor }} />{STATUS[s].nome}</span>)}
      </div>

      <h3>Por campo político</h3>
      <p className="small muted">
        Esquerda, centro ou direita segundo a nota de 0 a 10 dada por 519 cientistas políticos na pesquisa de <a href={FONTE_IDEOLOGIA.url} target="_blank" rel="noreferrer">{FONTE_IDEOLOGIA.nome}</a>.
        É uma fonte independente do site. O MDB tem nota 7,01, no limite entre centro-direita e direita.
      </p>
      <div className="bars">
        {campos.map((c) => (
          <div className="bar-row" key={c.campo}>
            <div style={{ minWidth: 0 }}><strong>{c.campo}</strong><div className="muted small">{c.partidos.join(", ")}</div></div>
            <div className="num">{c.total}</div>
            <div className="track" aria-hidden="true"><div className="fill" style={{ width: `${(c.total / Math.max(1, ...campos.map((x) => x.total))) * 100}%`, background: corCampo(c.campo) }} /></div>
          </div>
        ))}
      </div>
      <p className="small muted">
        Ler com cuidado: partidos grandes e que estavam no governo têm mais gente em cargos onde o dinheiro passa, e por isso aparecem mais.
        O número também depende de quais casos estão aqui: começamos por {CASOS.length} e vamos acrescentar outros.
      </p>
    </section>
  );
}

export default function Corrupcao() {
  const r = resumoGeral(CASOS);
  const comValor = CASOS.filter((c) => c.valorNum > 0).sort((a, b) => b.valorNum - a.valorNum);
  return (
    <>
      <section className="hero">
        <span className="eyebrow">Corrupção</span>
        <h1 style={{ margin: 0 }}>Os maiores escândalos, quem estava envolvido e em que pé estão</h1>
        <p className="muted" style={{ margin: 0 }}>
          Linha do tempo, pessoas e partidos, empresas, delações e acordos, e o que dizem a esquerda, a direita e a Justiça. Cada informação tem o link para a fonte original.
          Situação conferida em {dataBR(ATUALIZADO_EM)}.
        </p>
      </section>

      <div className="grid stats" style={{ marginTop: 16 }}>
        <div className="card stat"><span className="label">Casos</span><span className="value">{r.casos}</span><span className="hint">{r.emInvestigacao} ainda em investigação</span></div>
        <div className="card stat"><span className="label">Pessoas citadas</span><span className="value">{r.pessoas}</span><span className="hint">políticos, empresários e servidores</span></div>
        <div className="card stat"><span className="label">Condenações mantidas</span><span className="value">{r.condenados}</span><span className="hint">entre as pessoas com nome nesta seção</span></div>
      </div>

      <Explain>
        <strong>Como ler:</strong> ser citado ou investigado não é ser culpado. Mostramos sempre a situação de cada pessoa:
        {" "}{(["condenado", "anulado", "reu", "indiciado", "investigado", "citado", "absolvido"] as Status[]).map((s, i) => <Fragment key={s}>{i > 0 && ", "}<abbr title={STATUS[s].explica}>{STATUS[s].nome.toLowerCase()}</abbr></Fragment>)}.
        {" "}Condenação anulada não é absolvição: quer dizer que o processo teve um erro e a Justiça não chegou a julgar de novo.
      </Explain>

      <section>
        <h2>Os casos</h2>
        <div className="grid casos-grid">{CASOS.map((c) => <CartaoCaso key={c.id} c={c} />)}</div>
      </section>

      <Placar />

      <section>
        <h2>Dinheiro envolvido</h2>
        <p className="small muted">Estimativas oficiais de cada caso. São medidas diferentes (prejuízo, valor desviado, valor devolvido): clique no caso para ver o que cada número quer dizer.</p>
        <Barras itens={comValor.map((c) => ({
          label: <Link to={`/corrupcao/${c.id}`}><strong>{c.nome}</strong></Link>,
          nota: `${c.valor.texto}. ${c.valor.nota}`,
          valor: c.valorNum,
          cor: "var(--flag-r)",
        }))} />
        <p className="small muted">Valores em reais da época, sem correção pela inflação. {comValor.map((c) => `${c.nome}: ${reaisCurto(c.valorNum)}`).join("; ")}.</p>
      </section>

      <section>
        <h2>Como montamos esta seção</h2>
        <ul className="small">
          <li>As informações vêm do STF, da Polícia Federal, do Ministério Público, da CGU, da Câmara, do Senado e de jornais reconhecidos. Cada pessoa e cada evento tem o link.</li>
          <li>Não existe API oficial que junte processos, delações e cassações; por isso esta seção é escrita à mão e conferida na data indicada no topo. Casos em investigação mudam rápido.</li>
          <li>No placar, cada pessoa conta uma vez por caso. Quem aparece em dois casos pelo mesmo fato (por exemplo, cassado no Mensalão) conta uma vez só. Empresários e servidores sem partido aparecem nos casos, mas não no placar.</li>
          <li>Na CPI dos Sanguessugas, a lista de 72 parlamentares foi publicada por partido; usamos esses números.</li>
          <li>Fotos: as oficiais da Câmara e do Senado. Quem está no mandato hoje tem link para o perfil no site, com gastos e votos.</li>
          <li>{NIVEL_NOME[1]}, {NIVEL_NOME[2].toLowerCase()}, {NIVEL_NOME[3].toLowerCase()} e {NIVEL_NOME[4].toLowerCase()}: é a ordem que usamos para dizer qual o cargo mais alto envolvido de cada partido.</li>
          <li>Achou um erro ou algo desatualizado? Abra um aviso no <a href="https://github.com/amarigo/segredos-abertos/issues" target="_blank" rel="noreferrer">GitHub</a>.</li>
        </ul>
      </section>
    </>
  );
}
