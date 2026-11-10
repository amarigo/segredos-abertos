import { useEffect, useMemo, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { Explain, Loading, OndeVer, useData } from "../components/ui";
import { FotoPolitico } from "../components/Foto";
import { corPartido, dataBR, linkSeguro, numero, type CidadeResumo } from "../data";
import { MG } from "../recorte";
import { BuscaCidade, cidadeGuardada, guardar, normal, useRep, type AvisoTSE, type Eleito, type Parlamentar, type RepCidade, type RepEstado, type RepIndice } from "../components/BuscaCidade";

/* Quem me representa: a pessoa digita a cidade e vê todos os cargos eleitos por quem vota ali, do vereador ao
   presidente. Os arquivos vêm de etl/sa_etl/representantes.py (TSE, Câmara e Senado), em data/representantes/. */

export default function Representantes() {
  const { ue = "" } = useParams();
  if (!ue) return <Inicio />;
  if (!/^(\d{4,6}|DF)$/.test(ue)) return <div className="empty">Cidade não encontrada. <Link to="/quem">Procure a sua cidade</Link></div>;
  return <PaginaCidade ue={ue} />;
}

function Inicio() {
  const guardada = cidadeGuardada();
  return (
    <section>
      <h1>Quem me representa</h1>
      <Explain>Digite a sua cidade e veja todas as pessoas eleitas por quem vota ali: vereadores e prefeito, deputados estaduais e
        governador, deputados federais e senadores do seu estado e o presidente. De cada um, o partido, o que faz o cargo e, dos que
        estão em Brasília, quanto gastam e como votam.</Explain>
      <BuscaCidade rotulo="Digite a sua cidade" id="busca-cidade-quem" autoFocus />
      {guardada && <p className="small"><Link to={`/quem/${guardada}`}>Voltar para a última cidade que você procurou</Link></p>}
    </section>
  );
}

function PaginaCidade({ ue }: { ue: string }) {
  const df = ue === "DF";
  const { data: idx, error: e1 } = useRep<RepIndice>("indice.json");
  const { data: cid, error: e2 } = useRep<RepCidade>(df ? null : `m/${ue}.json`);
  const uf = df ? "DF" : cid?.uf;
  const { data: est, error: e3 } = useRep<RepEstado>(uf ? `uf/${uf}.json` : null);
  const { data: mgCidades } = useData<CidadeResumo[]>(MG ? "cidades.json" : null);
  useEffect(() => { guardar(ue); }, [ue]);
  if (!idx || (!df && !cid) || !est) return <Loading error={e1 || e2 || e3} />;
  if (MG && est.uf !== "MG") return <div className="empty">O Minas Nossa mostra só as cidades de Minas. <a href={`../#/quem/${ue}`}>Ver no Segredos Abertos Brasil</a></div>;
  const nome = df ? "Brasília" : cid!.nome;
  const mgCidade = MG && mgCidades?.find((c) => normal(c.nome) === normal(nome));
  const nVer = cid?.vereadores.length || 0;
  const total = (df ? 0 : nVer + (cid?.prefeito ? 1 : 0) + (cid?.vice_prefeito ? 1 : 0)) + est.deputados_estaduais.length
    + (est.governador ? 1 : 0) + (est.vice_governador ? 1 : 0) + est.deputados_federais.length + est.senadores.length
    + (idx.presidente ? 1 : 0) + (idx.vice_presidente ? 1 : 0);
  const el = idx.eleicoes;
  const casaEst = est.casa_estadual;

  return (
    <>
      <section className="rep-topo">
        <Link to="/quem" className="small">‹ Procurar outra cidade</Link>
        <span className="eyebrow">Quem me representa · {df ? "Distrito Federal" : `${nome} · ${est.nome}`}</span>
        <h1>Quem representa {nome}{df ? "" : ` (${est.uf})`}</h1>
        <p className="rep-lead">
          {df ? <>Quem vota em Brasília escolhe <strong>{numero(total)} pessoas</strong>. O Distrito Federal não tem prefeito nem vereadores: o
            governador cuida também do que seria da prefeitura, e os {est.deputados_estaduais.length} deputados distritais fazem as leis locais.</>
            : <><strong>{numero(total)} pessoas</strong> foram escolhidas por quem vota em {nome}: {nVer} vereadores e o prefeito cuidam da cidade,
              {" "}{est.deputados_estaduais.length} deputados estaduais e o governador cuidam de {est.nome}, {est.deputados_federais.length} deputados
              federais e {est.senadores.length} senadores representam o estado no Congresso, e o presidente governa o país.</>}
        </p>
        <nav className="rep-atalhos" aria-label="Partes desta página">
          {!df && <a href="#rep-cidade">Na cidade</a>}
          <a href="#rep-estado">No estado</a>
          <a href="#rep-congresso">No Congresso</a>
          <a href="#rep-presidencia">Presidência</a>
        </nav>
      </section>

      {!df && cid && <SecaoCidade c={cid} mgCidade={mgCidade ? mgCidade.id : ""} el={el} />}

      <section id="rep-estado">
        <h2>{df ? "Governo do Distrito Federal" : `Governo de ${est.nome}`}</h2>
        <Explain>O governador cuida do que é do estado: polícias, hospitais estaduais, escolas de ensino médio, estradas estaduais e o
          orçamento do estado. Eleito em {est.eleicao}, mandato até 2026.{MG && <> <Link to="/governo">Salários e viagens do governo de Minas</Link>.</>}</Explain>
        {est.governador ? (
          <div className="grid rep-chefes">
            <CartaoEleito cargo="Governador(a)" p={est.governador} ano={est.eleicao} titular />
            {est.vice_governador && <CartaoEleito cargo="Vice-governador(a)" p={est.vice_governador} ano={est.eleicao} doTitular={est.governador} />}
          </div>
        ) : <div className="empty">O arquivo do TSE não trouxe o governador eleito em {est.eleicao} neste estado.</div>}
      </section>

      <section>
        <h2>{casaEst}: {est.deputados_estaduais.length} {df ? "deputados distritais" : "deputados estaduais"}</h2>
        <Explain>Fazem as leis {df ? "do Distrito Federal" : "do estado"}, aprovam o orçamento e fiscalizam o governador. São eleitos por todo o
          {df ? " Distrito Federal" : " estado"}, não só pela sua cidade. Eleitos em {est.eleicao}, com o partido daquela eleição.
          {MG && <> Gastos e projetos de cada um: <Link to="/assembleia">Deputados estaduais</Link>.</>}</Explain>
        <Contagem n={est.deputados_estaduais.length} vagas={est.vagas_estaduais} oque={df ? "deputados distritais" : "deputados estaduais"} />
        <ListaEleitos pessoas={est.deputados_estaduais} ano={est.eleicao} />
      </section>

      <section id="rep-congresso">
        <h2>No Congresso, por {est.nome}</h2>
        <Explain>Deputados federais e senadores fazem as leis do país, aprovam o orçamento federal e podem mandar dinheiro de emendas para as
          cidades. Estes são os que estão no cargo hoje, pela lista oficial da Câmara e do Senado: toque num nome para ver quanto gasta,
          com quais empresas e como vota.</Explain>
        <h3>{est.senadores.length} senadores</h3>
        <ListaParlamentares lista={est.senadores} />
        <h3>{est.deputados_federais.length} deputados federais</h3>
        {est.vagas_federais != null && est.vagas_federais !== est.deputados_federais.length && (
          <p className="small muted">{est.nome} tem {est.vagas_federais} cadeiras na Câmara; {est.deputados_federais.length} estão ocupadas hoje
            na lista da Câmara (uma cadeira pode ficar vaga enquanto o suplente não toma posse).</p>
        )}
        <ListaParlamentares lista={est.deputados_federais} />
      </section>

      <section id="rep-presidencia">
        <h2>Presidência da República</h2>
        <Explain>O presidente governa o país: ministérios, orçamento federal, SUS, INSS, Polícia Federal. Pode propor leis e vetar as que o
          Congresso aprova. Eleito em {el.geral}, mandato até 2026.</Explain>
        {idx.presidente ? (
          <div className="grid rep-chefes">
            <CartaoEleito cargo="Presidente" p={idx.presidente} ano={el.geral} titular />
            {idx.vice_presidente && <CartaoEleito cargo="Vice-presidente" p={idx.vice_presidente} ano={el.geral} doTitular={idx.presidente} />}
          </div>
        ) : <div className="empty">O arquivo do TSE não trouxe o presidente eleito.</div>}
      </section>

      <section>
        <h2>Quem assume em 2027</h2>
        <Explain>Em outubro de {el.seguinte} o país escolheu presidente, governadores, senadores e deputados para o mandato de 2027 a 2030. Até
          a posse, em 2027, ficam os eleitos em {el.geral} que aparecem acima. Prefeito e vereadores ficam até o fim de 2028.</Explain>
        <a className="card cidade-card destaque-card" href={MG ? "../eleicao2026/eleitos/" : "eleicao2026/eleitos/"}>
          <strong>Os eleitos de {el.seguinte}</strong>
          <span className="small muted">Governadores, senadores e deputados de cada estado, com partido, votos e quem foi reeleito (TSE).</span>
        </a>
      </section>

      <Fontes idx={idx} df={df} />
    </>
  );
}

function SecaoCidade({ c, mgCidade, el }: { c: RepCidade; mgCidade: string; el: RepIndice["eleicoes"] }) {
  const s = c.suplementar;
  const sv = c.suplementar_vereadores;
  const av = c.aviso_tse || {};
  return (
    <section id="rep-cidade">
      <h2>Prefeitura de {c.nome}</h2>
      <Explain>O prefeito administra a cidade: postos de saúde, escolas de educação infantil e do ensino fundamental, ruas, coleta de lixo,
        transporte e o orçamento da prefeitura. Mandato de 2025 a 2028.{mgCidade && <> <Link to={`/cidade/${mgCidade}`}>Quem já governou {c.nome} e onde a prefeitura gasta</Link>.</>}</Explain>
      {s && (
        <div className="alert rep-aviso" role="note"><div>
          A eleição de {c.eleicao} para prefeito foi refeita em <strong>{dataBR(s.data)}</strong> (eleição suplementar, quando a Justiça
          Eleitoral anula a primeira).{s.eleitos_2024.prefeito && <> Em {c.eleicao} tinham sido eleitos {s.eleitos_2024.prefeito.nome} ({s.eleitos_2024.prefeito.partido})
          {s.eleitos_2024.vice_prefeito && <> e {s.eleitos_2024.vice_prefeito.nome} ({s.eleitos_2024.vice_prefeito.partido})</>}.</>}
          {s.fonte && <> <a href={linkSeguro(s.fonte)} target="_blank" rel="noreferrer">Resultado da eleição suplementar no TSE</a>.</>}
        </div></div>
      )}
      {c.prefeito && av.prefeito && <AvisoDoTSE a={av.prefeito} oque="prefeito" />}
      {c.prefeito ? (
        <div className="grid rep-chefes">
          <CartaoEleito cargo="Prefeito(a)" p={c.prefeito} ano={s ? Number(s.data.slice(0, 4)) : c.eleicao} titular />
          {c.vice_prefeito && <CartaoEleito cargo="Vice-prefeito(a)" p={c.vice_prefeito} ano={s ? Number(s.data.slice(0, 4)) : c.eleicao} doTitular={c.prefeito} />}
        </div>
      ) : (
        <div className="empty">O TSE não tem prefeito eleito em {c.eleicao} nesta cidade. Isso acontece quando a eleição foi anulada
          ou ainda está em julgamento na Justiça Eleitoral.
          {av.prefeito && <AvisoDoTSE a={av.prefeito} oque="prefeito" dentro />}</div>
      )}

      <h2>Câmara Municipal: {c.vereadores.length} vereadores</h2>
      <Explain>Os vereadores fazem as leis da cidade, aprovam o orçamento da prefeitura e fiscalizam o prefeito. Eleitos em {c.eleicao}, com o
        partido daquela eleição; mandato de 2025 a 2028.</Explain>
      {sv && (
        <div className="alert rep-aviso" role="note"><div>
          {sv.eleitos ? <>Em <strong>{dataBR(sv.data)}</strong> a Justiça Eleitoral refez a eleição de {sv.cadeiras === 1 ? "1 cadeira" : `${sv.cadeiras} cadeiras`} da
            Câmara (eleição suplementar). Eleito(s): {sv.eleitos.map((p) => `${p.nome} (${p.partido})`).join(", ")}. A lista abaixo é a da eleição
            de {c.eleicao}; o TSE não informa no resultado quem deixou a cadeira.</>
            : <>A eleição de {c.eleicao} para vereador foi refeita em <strong>{dataBR(sv.data)}</strong> (eleição suplementar). A lista abaixo é
            a dos eleitos nela.</>}{" "}
          <a href={linkSeguro(sv.fonte)} target="_blank" rel="noreferrer">Resultado no TSE</a>.
        </div></div>
      )}
      <Contagem n={c.vereadores.length} vagas={c.vagas_vereadores} oque="vereadores" aviso={av.vereadores} />
      <ListaEleitos pessoas={c.vereadores} ano={c.eleicao} seguinte={el.seguinte} />
    </section>
  );
}

/** Bancada por partido, maior primeiro, e a lista de nomes em ordem alfabética */
function ListaEleitos({ pessoas, ano, seguinte = 2026 }: { pessoas: Eleito[]; ano: number; seguinte?: number }) {
  const porPartido = useMemo(() => {
    const m = new Map<string, number>();
    pessoas.forEach((p) => m.set(p.partido, (m.get(p.partido) || 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [pessoas]);
  if (!pessoas.length) return <div className="empty">Sem nomes no arquivo do TSE.</div>;
  return (
    <>
      <p className="rep-partidos" aria-label={`Cadeiras por partido na eleição de ${ano}`}>
        {porPartido.map(([p, n]) => <span key={p} className="partido-tag rep-bancada"><i className="partido-cor" style={{ background: corPartido(p) }} />{p} {n}</span>)}
      </p>
      <ul className="rep-nomes">
        {pessoas.map((p) => (
          <li key={`${p.nome}-${p.numero}`}>
            <span className="pname">{p.nome}</span> <span className="muted small">{p.partido}{p.numero ? ` · nº ${p.numero}` : ""}</span>
            {p.nome_completo && <span className="muted small rep-civil">{p.nome_completo}</span>}
            <Notas p={p} titular={false} seguinte={seguinte} />
          </li>
        ))}
      </ul>
    </>
  );
}

function ListaParlamentares({ lista }: { lista: Parlamentar[] }) {
  if (!lista.length) return <div className="empty">A lista oficial não trouxe ninguém deste estado nesta atualização.</div>;
  return (
    <div className="list rep-parlamentares">
      {lista.map((p) => (
        <Link key={p.id} to={`/p/${p.id}`} className="person" style={{ gridTemplateColumns: "48px 1fr auto" }}>
          <FotoPolitico url={p.foto} nome={p.nome} decorativa />
          <div style={{ minWidth: 0 }}><div className="pname">{p.nome}</div><div className="meta">{p.partido}</div></div>
          <span className="small rep-ver">gastos e votos ›</span>
        </Link>
      ))}
    </div>
  );
}

function Contagem({ n, vagas, oque, aviso }: { n: number; vagas: number | null; oque: string; aviso?: AvisoTSE }) {
  if (vagas == null || vagas === n) return aviso ? <AvisoDoTSE a={aviso} oque={oque} /> : null;
  return (
    <div className="small rep-diferenca">
      <p>O TSE lista {n} {oque} eleitos para {vagas} cadeiras.{" "}
        {aviso?.totalizado === false ? <>O TSE ainda não terminou a contagem dos votos para {oque} nesta cidade (ela é refeita quando a Justiça
          Eleitoral anula votos depois da eleição). Quando terminar, a lista acompanha.</>
          : <>A diferença costuma vir de recontagem ou de votos anulados pela Justiça Eleitoral depois da eleição; quando o TSE atualizar o
          arquivo, a lista acompanha.</>}</p>
      {aviso && <AvisoDoTSE a={aviso} oque={oque} dentro />}
    </div>
  );
}

/** O aviso oficial do site de resultados do TSE (eleição anulada, nova eleição marcada...), com o link para o arquivo */
function AvisoDoTSE({ a, oque, dentro = false }: { a: AvisoTSE; oque: string; dentro?: boolean }) {
  const corpo = (
    <>
      {a.suplementar && <p>A Justiça Eleitoral marcou nova eleição (suplementar) para {oque} em <strong>{dataBR(a.suplementar)}</strong>; o TSE
        ainda não publicou quem venceu.</p>}
      {a.mensagens.length > 0 && <><p>O que o TSE informa sobre a eleição de {oque} nesta cidade:</p>
        <ul>{a.mensagens.map((m) => <li key={m}>{m}</li>)}</ul></>}
      <p><a href={linkSeguro(a.fonte)} target="_blank" rel="noreferrer">Arquivo oficial no site de resultados do TSE</a></p>
    </>
  );
  if (!a.suplementar && !a.mensagens.length && dentro) return <p className="small"><a href={linkSeguro(a.fonte)} target="_blank" rel="noreferrer">Arquivo oficial no site de resultados do TSE</a></p>;
  if (!a.suplementar && !a.mensagens.length) return null;
  return dentro ? <div className="rep-aviso-tse small">{corpo}</div> : <div className="alert rep-aviso" role="note"><div className="rep-aviso-tse">{corpo}</div></div>;
}

function CartaoEleito({ cargo, p, ano, titular = false, doTitular }: { cargo: string; p: Eleito; ano: number; titular?: boolean; doTitular?: Eleito }) {
  return (
    <div className="card rep-cartao">
      <span className="eyebrow">{cargo}</span>
      <strong className="rep-nome">{p.nome}</strong>
      <span className="small"><i className="partido-cor" style={{ background: corPartido(p.partido) }} />{p.partido}{p.numero ? ` · nº ${p.numero}` : ""}</span>
      {p.nome_completo && <span className="small muted">{p.nome_completo}</span>}
      <span className="small muted">Eleito(a) em {ano}{p.turnos === 2 ? ", no 2º turno" : ""}.</span>
      <Notas p={p} titular={titular} />
      {doTitular?.em_2026?.renunciou && <p className="small rep-nota"><strong>Pela regra, assumiu o cargo</strong> quando {doTitular.nome} saiu para
        disputar a eleição de 2026.</p>}
    </div>
  );
}

const RESULTADO: Record<string, string> = { "eleito": "foi eleito(a)", "não eleito": "não foi eleito(a)", "suplente": "ficou como suplente", "2º turno": "foi ao 2º turno" };

/** O que o TSE diz depois da eleição: candidatura cassada, quem disputou 2026 e por qual partido */
function Notas({ p, titular, seguinte = 2026 }: { p: Eleito; titular: boolean; seguinte?: number }) {
  const e = p.em_2026;
  const out: ReactNode[] = [];
  if (p.situacao) out.push(<>Situação da candidatura no TSE: {p.situacao.toLowerCase()}.</>);
  if (e) {
    const res = RESULTADO[e.resultado] || e.resultado;
    const onde = e.uf && e.uf !== "BR" ? ` por ${e.uf}` : "";
    const partido = e.partido && e.partido !== p.partido ? `, pelo ${e.partido}` : "";
    if (e.renunciou && titular) {
      out.push(<><strong>Deixou o cargo para disputar {e.cargo.toLowerCase()}{onde} em {seguinte}</strong>{partido}, e {res}. A{" "}
        <a href={linkSeguro("https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art14%C2%A76")} target="_blank" rel="noreferrer">Constituição (art. 14, § 6º)</a>{" "}
        obriga quem ocupa o cargo a renunciar 6 meses antes de disputar outro; o vice assume.</>);
    } else if (e.reeleicao) {
      out.push(<>Tentou a reeleição em {seguinte}{partido}: {res}.</>);
    } else {
      out.push(<>Em {seguinte} disputou {e.cargo.toLowerCase()}{onde}{partido}: {res}{e.resultado === "eleito" ? "; assume o novo cargo em 2027" : ""}.</>);
    }
  }
  if (!out.length) return null;
  return <>{out.map((x, i) => <p key={i} className="small rep-nota">{x}</p>)}</>;
}

function Fontes({ idx, df }: { idx: RepIndice; df: boolean }) {
  const f = idx.fontes;
  const tse = (k: string, nome: string, explica: string) => {
    const x = f[k];
    return x && typeof x === "object" ? [{ nome, url: x.pagina, explica: `${explica}; arquivo lido em ${dataBR(x.lido_em)}` }] : [];
  };
  return (
    <section className="rep-fontes">
      <h2>De onde vêm os nomes</h2>
      <p className="small">Vereadores, prefeito, deputados estaduais, governador e presidente: quem foi eleito, pelo arquivo oficial de candidatos
        do TSE. Se alguém saiu do cargo depois (cassação, licença, morte) e um suplente ou o vice assumiu, o arquivo do TSE não mostra; a
        exceção é quem saiu para disputar a eleição de {idx.eleicoes.seguinte}, que aparece aqui. Deputados federais e senadores são os que
        estão no cargo hoje, pelas listas oficiais da Câmara e do Senado. Atualizado em {dataBR(idx.atualizado_em)}.</p>
      <OndeVer titulo="Fontes oficiais" links={[
        ...(df ? [] : tse("candidatos_municipal", `Candidatos e eleitos de ${idx.eleicoes.municipal} (TSE)`, "prefeitos, vices e vereadores")),
        ...tse("candidatos_geral", `Candidatos e eleitos de ${idx.eleicoes.geral} (TSE)`, "presidente, governadores e deputados estaduais"),
        ...tse("candidatos_seguinte", `Candidatos de ${idx.eleicoes.seguinte} (TSE)`, "quem deixou o cargo para concorrer"),
        ...(df ? [] : tse("resultados", "Site de resultados do TSE", "eleições suplementares e avisos de eleição anulada")),
        ...(typeof f.camara === "string" ? [{ nome: "Deputados em exercício (API da Câmara)", url: f.camara }] : []),
        ...(typeof f.senado === "string" ? [{ nome: "Senadores em exercício (API do Senado)", url: f.senado }] : []),
        ...(typeof f.divulga === "string" ? [{ nome: "Página de cada candidato no TSE (DivulgaCandContas)", url: f.divulga, explica: "bens, propostas e contas de campanha" }] : []),
      ]} />
    </section>
  );
}
