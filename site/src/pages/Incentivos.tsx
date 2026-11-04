import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Barras, Explain, Loading, useAno, useData, useVarios, useVisivel } from "../components/ui";
import { CompararAnos, Faisca, MapaAnos, curto, type Fatia } from "../components/graficos";
import { casaNome, cnpjFmt, corPartido, dataBR, linkSeguro, reais, reaisCurto, type Casa, type Resumo } from "../data";
import { COR_LADO, LADOS, ladoPelosVotos } from "../partidos";
import { Pizza } from "./Partidos";
import "./emendas.css";
import "./incentivos.css";
import { AvisosFim } from "../components/Selo";

/* Formato de data/incentivos/ (gerado por etl/sa_etl/incentivos.py) */
type Par = [string, number];
type Tipo = "empresa" | "entidade" | "publico" | "outro" | "sem_dados";
interface Dono { donos: string[]; n_outras: number; pagina: boolean }
interface AutorCurto { nome: string; politico: string | null; partido: string; valor: number }
interface Indice {
  anos: number[]; anos_renuncia: { ano: number; total: number; parcial: boolean; publicado_em?: string }[];
  fontes: Record<"pagamentos" | "pagamentos_api" | "renuncias" | "emendas" | "receita" | "pessoa_juridica", string>; ate_emendas: string;
}
interface Pagamentos {
  total: number; n: number; fora_publicos: number; top_n_receita: number;
  cobertura: { dias: number; dias_ano: number; de: string; ate: string; completo: boolean; origem?: "api"; meses?: number; pessoas_fisicas?: number };
  por_categoria: { cat: string; rotulo: string; valor: number; n: number }[];
  orgaos: Par[]; por_tipo: { tipo: Tipo; valor: number; n: number }[]; por_uf: [string, number, number][];
  top: (Dono & { cnpj: string; nome: string; tipo: Tipo; uf: string; valor: number; n: number; cats: Par[]; orgaos: Par[] })[];
  destino?: Destino;
}
type Cobertura = Pagamentos["cobertura"];
interface Destino {
  privado: { total: number; n: number };
  publico: { total: number; n: number; cobertura: Cobertura | Record<string, never>;
    por_esfera: { esfera: string; rotulo: string; valor: number; n: number }[];
    top: { cnpj: string; nome: string; esfera: string; valor: number; cats: Par[]; orgaos: Par[] }[] };
}
interface PoliticoDeu { nome: string; valor: number; n: number; recebedores: [string, string, number, boolean][]; politico?: string | null; partido?: string; uf?: string; casa?: Casa | "" }
interface Emendas {
  total: number; n: number; politicos: PoliticoDeu[]; n_politicos: number; coletivos: PoliticoDeu[];
  partidos: { sigla: string; valor: number; n: number }[]; sem_partido: number;
  por_uf_politico: [string, number, number][]; por_uf_recebedor: [string, number, number][];
  top: (Dono & { cnpj: string; nome: string; tipo: Tipo; uf: string; valor: number; n: number; autores: AutorCurto[] })[];
}
interface Ano { ano: number; pagamentos: Pagamentos | null; emendas: Emendas | null }
interface Renuncia {
  ano: number; total: number; n: number; sem_cnpj: number; parcial: boolean; fonte: string; url: string;
  por_uf: [string, number, number][]; por_setor: { setor: string; valor: number; n: number }[];
  por_beneficio: { nome: string; tributo: string; valor: number; n: number }[]; por_tributo: Par[];
  top: (Dono & { cnpj: string; nome: string; tipo: Tipo; uf: string; municipio: string; setor: string; atividade: string; valor: number; beneficios: Par[] })[];
}

const CAT_COR: Record<string, string> = { contrato: "var(--s1)", repasse: "var(--c7)", subsidio: "var(--c4)", outro: "var(--c-outros)" };
const TIPO_NOME: Record<Tipo, string> = { empresa: "Empresa", entidade: "Entidade sem fins lucrativos", publico: "Estatal", outro: "Outro tipo", sem_dados: "" };
const PORTAL_PJ = "https://portaldatransparencia.gov.br/pessoa-juridica/";
const semAcento = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const plural = (n: number, um: string, varios: string) => `${n.toLocaleString("pt-BR")} ${n === 1 ? um : varios}`;
const pctDe = (v: number, t: number) => (t ? `${((v / t) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%` : "—");

type Fonte = "pagamentos" | "renuncia" | "emendas";
const FONTE_NOME: Record<Fonte, string> = { pagamentos: "Recebeu do governo", renuncia: "Deixou de pagar imposto", emendas: "Recebeu de emendas" };

// "2026 ainda não foi publicado" ou "2025 e 2026 ainda não foram publicados": todos os anos depois do último que existe
function naoPublicados(ultimo: number | undefined, anoSite: number): string {
  const de = ultimo ? Math.min(ultimo + 1, anoSite) : anoSite;
  const anos = Array.from({ length: anoSite - de + 1 }, (_, i) => de + i);
  if (anos.length <= 1) return `${anoSite} ainda não foi publicado`;
  return `${anos.slice(0, -1).join(", ")} e ${anos[anos.length - 1]} ainda não foram publicados`;
}

export default function Incentivos() {
  const { ano: anoSite } = useAno();
  const { data: idx, error: erroIdx } = useData<Indice>("incentivos/indice.json");
  // Sem dados do ano escolhido no menu: mostra o ano mais recente que já temos (e avisa)
  const anosComDados = (idx?.anos || []).map(String);
  const ano = anosComDados.includes(anoSite) ? anoSite : (anosComDados[anosComDados.length - 1] || anoSite);
  const outroAno = ano !== anoSite;
  const tem = anosComDados.includes(ano);
  const { data, error } = useData<Ano>(tem ? `incentivos/${ano}.json` : null);
  const anosR = idx?.anos_renuncia || [];
  // A Receita publica a renúncia com atraso: abre no último ano completo e diz claramente qual é
  const padraoR = (anosR.filter((a) => !a.parcial).pop() || anosR[anosR.length - 1])?.ano;
  const ultimoR = anosR[anosR.length - 1];
  const [escolhidoR, setAnoR] = useState<number | null>(null);
  const anoR = escolhidoR && anosR.some((a) => a.ano === escolhidoR) ? escolhidoR : padraoR;
  const { data: ren } = useData<Renuncia>(anoR ? `incentivos/renuncia-${anoR}.json` : null);

  if (!idx) {
    return erroIdx ? <><h1>Dinheiro público para empresas</h1><div className="empty">Os dados desta página ainda não foram coletados. Eles aparecem aqui depois da próxima atualização diária.</div></>
      : <Loading />;
  }
  if (tem && !data) return <Loading error={error} />;
  const pag = data?.pagamentos || null;
  const emd = data?.emendas || null;

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Incentivos e dinheiro público para empresas · {ano}</span>
        <h1>Quem ganha com o dinheiro público</h1>
        <Explain>
          O dinheiro público chega às empresas, ONGs e outras entidades de três jeitos: o governo federal <strong>paga</strong> por compras, obras, serviços, convênios e subsídios;
          deixa de <strong>cobrar imposto</strong> de quem tem um benefício fiscal (a renúncia fiscal); e deputados e senadores <strong>indicam emendas</strong> que pagam empresas e entidades.
          Aqui você vê quem mais recebe, quem são os donos e de quais parlamentares, partidos e estados veio o dinheiro das emendas. Tudo com dados oficiais e link para o original.
        </Explain>
        <p className="small muted">Cada número diz de que ano é. Mostramos sempre o ano mais recente que o governo já publicou; quando um dado ainda não existe para {anoSite}, o quadro avisa.</p>
        <div className="grid">
          <div className="card stat kpi"><span className="label">Pago a empresas e entidades</span>
            <span className={`ano-tag ${ano === anoSite ? "" : "outro"}`}>{ano}{pag && !pag.cobertura.completo ? ` · até ${dataBR(pag.cobertura.ate)}` : ""}</span>
            <span className="value">{pag ? reaisCurto(pag.total) : "—"}</span>
            <span className="hint">{pag ? plural(pag.n, "recebedor", "recebedores") : `Ainda sem dados de ${ano}`}</span></div>
          <div className="card stat kpi"><span className="label">Imposto que deixou de ser cobrado (renúncia fiscal)</span>
            {anoR && <span className={`ano-tag ${String(anoR) === anoSite ? "" : "outro"}`}>{anoR}{ren?.parcial ? " · incompleto" : ""}</span>}
            <span className="value">{ren ? reaisCurto(ren.total) : "—"}</span>
            {anosR.length > 1 && <Faisca serie={anosR.filter((a) => !a.parcial).map((a) => [String(a.ano), a.total])} marcado={String(anoR)} />}
            <span className="hint">{ren ? `${plural(ren.n, "empresa", "empresas")} com benefício fiscal. ` : ""}{anosR.length
              ? <>A Receita publica com atraso{ultimoR?.publicado_em ? <>; a última publicação oficial é de {dataBR(ultimoR.publicado_em)}</> : null}. {String(anoR) === anoSite ? null
                : ultimoR && String(ultimoR.ano) === anoSite ? <>{anoSite} saiu incompleto; mostramos {anoR}, o último ano completo.</>
                : <>{naoPublicados(ultimoR?.ano, Number(anoSite))}{ultimoR && ultimoR.parcial && ultimoR.ano !== anoR ? <> e {ultimoR.ano} saiu incompleto</> : null}; mostramos {anoR}, o {ultimoR?.ano === anoR ? "ano mais recente" : "último ano completo"}.</>}</>
              : "O arquivo ainda não foi baixado do Portal da Transparência"}</span></div>
          <div className="card stat kpi"><span className="label">Emendas pagas a empresas e entidades</span>
            <span className={`ano-tag ${ano === anoSite ? "" : "outro"}`}>{ano}</span>
            <span className="value">{emd ? reaisCurto(emd.total) : "—"}</span>
            <span className="hint">{emd ? `por indicação de ${plural(emd.n_politicos, "parlamentar", "parlamentares")}`
              : <>Os pagamentos de emendas de {ano} ainda não foram lidos. Lemos os arquivos diários do Portal da Transparência em ordem, um dia depois do outro{idx.ate_emendas ? <>, e a leitura está em {dataBR(idx.ate_emendas)}</> : null}. Avança a cada atualização. O total das emendas de {ano} está em <Link to="/emendas">Emendas</Link>.</>}</span></div>
        </div>
      </section>

      {pag?.destino && <ParaOnde d={pag.destino} cob={pag.cobertura} ano={ano} />}
      <QuemRecebeu pag={pag} ren={ren} emd={emd} ano={ano} anosR={anosR} anoR={anoR} setAnoR={setAnoR} />
      {emd && <QuemDeu emd={emd} ano={ano} />}
      <PorEstado pag={pag} ren={ren} emd={emd} ano={ano} anosR={anosR} />
      <ParaQue pag={pag} ren={ren} ano={ano} anosR={anosR} />

      <section>
        <h2>De onde vêm estes dados</h2>
        <ul className="small muted emd-notas">
          {pag?.cobertura.origem === "api" ? <li><strong>Pagamentos:</strong> consulta <a href={linkSeguro(idx.fontes.pagamentos_api)} target="_blank" rel="noreferrer">recebimento de recursos por favorecido ↗</a> da API oficial do Portal da Transparência (CGU), mês a mês: o total pago em {ano} a cada CNPJ, sem corte, com os órgãos que pagaram. Esta consulta não separa compras, repasses e subsídios, e inclui todo tipo de despesa. Pagamentos a pessoas físicas ({reaisCurto(pag.cobertura.pessoas_fisicas || 0)}) não entram nas listas, porque o CPF vem mascarado. Pagamentos a órgãos públicos, estados, municípios e estatais ficam de fora das listas de empresas e aparecem em "Para onde vai o dinheiro".{!pag.cobertura.completo && <> {ano} ainda está sendo lido: por enquanto temos {pag.cobertura.meses} meses, até {dataBR(pag.cobertura.ate)}. A leitura avança toda semana.</>}</li> :
          <li><strong>Pagamentos:</strong> arquivos diários de despesas do governo federal no <a href={linkSeguro(idx.fontes.pagamentos)} target="_blank" rel="noreferrer">Portal da Transparência ↗</a> (CGU). Contamos o que foi pago no ano a cada CNPJ que não é órgão público, pela natureza da despesa de cada empenho: compras, obras e serviços; repasses a entidades (convênios, auxílios e subvenções sociais); subsídios (subvenções econômicas); e outros. Salários, aposentadorias e a dívida pública ficam de fora. Pagamentos a órgãos públicos, estados, municípios e estatais ficam de fora das listas de empresas, porque o dinheiro continua dentro do setor público{pag ? ` (${reaisCurto(pag.fora_publicos)} a estatais identificadas pela Receita em ${ano})` : ""}: eles aparecem em "Para onde vai o dinheiro".{pag && !pag.cobertura.completo && <> Os arquivos de {ano} ainda estão sendo lidos: por enquanto temos {pag.cobertura.dias} de {pag.cobertura.dias_ano} dias, de {dataBR(pag.cobertura.de)} a {dataBR(pag.cobertura.ate)}. A leitura avança a cada atualização diária.</>}</li>}
          <li><strong>Renúncia fiscal:</strong> <a href={linkSeguro(idx.fontes.renuncias)} target="_blank" rel="noreferrer">dados abertos de renúncias fiscais ↗</a> do Portal da Transparência, com dados da Receita Federal: o imposto federal que cada empresa deixou de pagar por causa de um benefício (Zona Franca, Sudene, Sudam, regimes de importação, desoneração e outros). A Receita publica com atraso, e o ano mais recente costuma vir incompleto. Não inclui ICMS e ISS, que são estaduais e municipais, nem o Simples Nacional.</li>
          <li><strong>Emendas:</strong> pagamentos feitos com dinheiro de <Link to="/emendas">emendas parlamentares</Link>, ligados à emenda pela nota de empenho, nos mesmos arquivos diários{idx.ate_emendas && ` (dados até ${dataBR(idx.ate_emendas)})`}. É o único caso em que o pagamento tem o nome de um parlamentar. Por isso os gráficos por partido e por parlamentar usam só as emendas.</li>
          <li><strong>Donos:</strong> base de CNPJ da Receita Federal, via <a href={linkSeguro(idx.fontes.receita)} target="_blank" rel="noreferrer">Minha Receita ↗</a>. Buscamos as empresas e entidades que mais receberam. Em cada uma você vê os sócios, quem está por trás das empresas sócias e as outras empresas dos mesmos donos que aparecem no site.</li>
        </ul>
      </section>
      <AvisosFim secao="incentivos">
        {outroAno && <p className="aviso-ano small">Ainda não temos os pagamentos de {anoSite}: o Portal da Transparência libera os arquivos diários aos poucos, e a leitura avança a cada atualização. Por enquanto, os pagamentos e as emendas desta página são de {ano}.</p>}
      </AvisosFim>
    </>
  );
}

/* ------------------------------------------------------------------ privado ou público */

const ESFERA_COR: Record<string, string> = { municipal: "var(--s3)", estadual: "var(--c7)", estatal: "var(--c4)", federal: "var(--s2)" };

function ParaOnde({ d, cob, ano }: { d: Destino; cob: Cobertura; ano: string }) {
  const cp = d.publico.cobertura as Cobertura;
  const temPub = !!cp?.dias;
  const mesmoPeriodo = temPub && cp.de === cob.de && cp.ate === cob.ate && cp.dias === cob.dias;
  const total = d.privado.total + d.publico.total;
  const partes = [
    { k: "privado", nome: "Setor privado: empresas, ONGs e outras entidades", valor: d.privado.total, n: d.privado.n, cor: "var(--s1)" },
    { k: "publico", nome: "Setor público: órgãos, estados, municípios e estatais", valor: d.publico.total, n: d.publico.n, cor: "var(--c-outros)" },
  ];
  return (
    <section>
      <h2>Para onde vai o dinheiro em {ano}: setor privado ou setor público</h2>
      <Explain>
        Tudo o que o governo federal pagou em {ano} a quem tem CNPJ, separado entre o setor privado (empresas, ONGs, associações) e o próprio setor público
        (prefeituras, governos estaduais, órgãos federais e empresas estatais). Salários, aposentadorias e a dívida pública não entram.
      </Explain>
      {!temPub ? <div className="empty">Os pagamentos ao setor público de {ano} começaram a ser guardados agora. Eles aparecem aqui depois das próximas atualizações.</div> : <>
        <div className="destino-barra" role="img" aria-label={partes.map((p) => `${p.nome}: ${reais(p.valor)}`).join("; ")}>
          {partes.map((p) => p.valor > 0 && <div key={p.k} style={{ flexGrow: p.valor, background: p.cor }} title={`${p.nome}: ${reais(p.valor)} (${pctDe(p.valor, total)})`} />)}
        </div>
        <div className="grid">
          {partes.map((p) => (
            <div className="card stat" key={p.k}><span className="label"><i className="destino-cor" style={{ background: p.cor }} />{p.nome}</span>
              <span className="value">{reaisCurto(p.valor)}</span><span className="hint">{pctDe(p.valor, total)} · {plural(p.n, "recebedor", "recebedores")}</span></div>
          ))}
        </div>
        {!mesmoPeriodo && <p className="aviso-ano small">Atenção: os dois lados ainda cobrem períodos diferentes. Setor privado: {cob.dias} dias ({dataBR(cob.de)} a {dataBR(cob.ate)}). Setor público: {cp.dias} dias ({dataBR(cp.de)} a {dataBR(cp.ate)}). Compare as proporções com cuidado até a leitura do ano terminar.</p>}
        <div className="two">
          <div>
            <h3>Setor público, por esfera</h3>
            <Barras formato={curto} rosca={{ titulo: `Pagamentos ao setor público em ${ano}, por esfera` }} itens={d.publico.por_esfera.map((x) => ({ nome: x.rotulo, label: x.rotulo, valor: x.valor, nota: plural(x.n, "recebedor", "recebedores"), cor: ESFERA_COR[x.esfera] }))} />
            <p className="muted small">A esfera vem do nome do recebedor no arquivo do Portal (por exemplo, "Município de…", "Fundo Estadual de…", "Banco…"). O que não se encaixa conta como órgão federal.</p>
          </div>
          <div>
            <h3>Quem mais recebeu no setor público</h3>
            <Barras formato={curto} itens={d.publico.top.slice(0, 10).map((x) => ({
              nome: x.nome, label: <Explicacao nome={x.nome} cnpj={x.cnpj} valor={x.valor} partes={[{ titulo: "Para quê", itens: x.cats }, { titulo: "Quem pagou", itens: x.orgaos }]}
                frase={<>Em {ano}, o governo federal pagou {reais(x.valor)} a {x.nome}, pelos arquivos diários de despesas do Portal da Transparência. Por ser do setor público, o dinheiro continua dentro do governo: ele repassa a quem faz a obra ou presta o serviço.</>} />, valor: x.valor,
              nota: x.orgaos.length ? `Pago por ${x.orgaos.map(([o]) => o).join(", ")}` : undefined, cor: ESFERA_COR[x.esfera],
            }))} />
          </div>
        </div>
      </>}
    </section>
  );
}

/* ------------------------------------------------------------------ quem recebeu mais */

interface Linha extends Dono { cnpj: string; nome: string; tipo: Tipo; uf: string; valor: number; detalhe: ReactNode; busca: string; partes: { titulo: string; itens: Par[] }[]; frase: ReactNode }

function QuemRecebeu({ pag, ren, emd, ano, anosR, anoR, setAnoR }: {
  pag: Pagamentos | null; ren: Renuncia | null; emd: Emendas | null; ano: string;
  anosR: Indice["anos_renuncia"]; anoR: number | undefined; setAnoR: (a: number) => void;
}) {
  const fontes = (["pagamentos", "renuncia", "emendas"] as Fonte[]).filter((f) => (f === "pagamentos" ? pag : f === "renuncia" ? ren : emd));
  const [escolhida, setFonte] = useState<Fonte>("pagamentos");
  const fonte = fontes.includes(escolhida) ? escolhida : fontes[0];
  const [tipo, setTipo] = useState<"" | "empresa" | "entidade">("");
  const [q, setQ] = useState("");
  const [n, setN] = useState(20);
  const linhas: Linha[] = useMemo(() => {
    const rotCat = (c: string) => pag?.por_categoria.find((p) => p.cat === c)?.rotulo || c;
    if (fonte === "pagamentos" && pag) return pag.top.map((x) => ({ ...x, busca: `${x.nome} ${x.orgaos.map(([o]) => o).join(" ")}`,
      partes: [{ titulo: "Para quê", itens: x.cats.map(([c, v]) => [rotCat(c), v] as Par) }, { titulo: "Quem pagou", itens: x.orgaos }],
      frase: <>Em {ano}, o governo federal pagou {reais(x.valor)} a {x.nome} ({plural(x.n, "pagamento", "pagamentos")}), pelos arquivos diários de despesas do Portal da Transparência. Cada pagamento tem a nota de empenho, que diz para que foi o dinheiro e qual órgão pagou.</>,
      detalhe: <>{x.cats.map(([c, v]) => `${pag.por_categoria.find((p) => p.cat === c)?.rotulo.split(" (")[0] || c}: ${reaisCurto(v)}`).join(" · ")}{x.orgaos.length > 0 && <div className="muted">Pago por {x.orgaos.map(([o]) => o).join(", ")}</div>}</> }));
    if (fonte === "renuncia" && ren) return ren.top.map((x) => ({ ...x, busca: `${x.nome} ${x.setor} ${x.municipio}`,
      partes: [{ titulo: "Quais benefícios fiscais", itens: x.beneficios }],
      frase: <>Em {ren.ano}, {x.nome} deixou de pagar {reais(x.valor)} de impostos federais por causa de benefícios fiscais, segundo a Receita Federal. É dinheiro que o governo deixou de arrecadar.{x.atividade ? ` Atividade: ${x.atividade}.` : ""}</>,
      detalhe: <>{x.beneficios.map(([b, v]) => `${b}: ${reaisCurto(v)}`).join(" · ")}<div className="muted">{[x.atividade, x.municipio && `${x.municipio}-${x.uf}`].filter(Boolean).join(" · ")}</div></> }));
    if (fonte === "emendas" && emd) return emd.top.map((x) => ({ ...x, busca: `${x.nome} ${x.autores.map((a) => `${a.nome} ${a.partido}`).join(" ")}`,
      partes: [{ titulo: "De quem eram as emendas", itens: x.autores.map((a) => [`${a.nome}${a.partido ? ` (${a.partido})` : ""}`, a.valor] as Par) }],
      frase: <>Em {ano}, {x.nome} recebeu {reais(x.valor)} em pagamentos feitos com dinheiro de emendas parlamentares. A emenda diz qual deputado ou senador indicou o dinheiro.</>,
      detalhe: <>Emendas de {x.autores.map((a, i) => <Fragment key={i}>{i > 0 && ", "}{a.politico ? <Link to={`/p/${a.politico}`}>{a.nome}</Link> : a.nome}{a.partido && <span className="muted"> ({a.partido})</span>}</Fragment>)}</> }));
    return [];
  }, [fonte, pag, ren, emd]);
  const filtradas = linhas.filter((x) => (!tipo || x.tipo === tipo || (tipo === "empresa" && x.tipo === "publico"))
    && (!q.trim() || semAcento(x.busca).includes(semAcento(q.trim())) || x.cnpj.includes(q.replace(/\D/g, "") || "x")));
  if (!fontes.length) return null;
  const total = fonte === "pagamentos" ? pag?.total : fonte === "renuncia" ? ren?.total : emd?.total;
  return (
    <section>
      <h2>Quem recebeu mais</h2>
      <div className="toggle inc-abas" role="group" aria-label="De onde vem o dinheiro">
        {fontes.map((f) => <button key={f} aria-pressed={fonte === f} onClick={() => { setFonte(f); setN(20); }}>{FONTE_NOME[f]}</button>)}
      </div>
      <Explain>
        {fonte === "pagamentos" && <>Empresas e entidades que mais receberam pagamentos do governo federal em {ano}: compras, obras, serviços, convênios e subsídios.</>}
        {fonte === "renuncia" && <>Empresas que mais deixaram de pagar impostos federais por causa de benefícios fiscais no ano-calendário {anoR}. É dinheiro que o governo deixa de arrecadar.</>}
        {fonte === "emendas" && <>Empresas e entidades que mais receberam pagamentos feitos com dinheiro de emendas parlamentares em {ano}, e de quem eram as emendas.</>}
        {" "}Toque no nome para ver de onde veio o dinheiro, em detalhe, com os links oficiais para conferir.
      </Explain>
      <div className="row" style={{ gap: 8 }}>
        {fonte === "renuncia" && anosR.length > 1 && (
          <label className="ano-sel"><span className="muted small">Ano-calendário</span>
            <select value={anoR} onChange={(e) => setAnoR(Number(e.target.value))}>
              {anosR.slice().reverse().map((a) => <option key={a.ano} value={a.ano}>{a.ano}{a.parcial ? " (incompleto)" : ""}</option>)}
            </select>
          </label>
        )}
        <div className="toggle" role="group" aria-label="Tipo de recebedor">
          <button aria-pressed={tipo === ""} onClick={() => setTipo("")}>Todos</button>
          <button aria-pressed={tipo === "empresa"} onClick={() => setTipo("empresa")}>Empresas</button>
          <button aria-pressed={tipo === "entidade"} onClick={() => setTipo("entidade")}>Entidades e ONGs</button>
        </div>
      </div>
      <h3 className="inc-sub">As 10 maiores</h3>
      <Barras formato={curto} itens={filtradas.slice(0, 10).map((x) => ({
        nome: x.nome, label: <ExplicaLinha x={x} />, valor: x.valor, nota: `${pctDe(x.valor, total || 0)} do total${x.uf ? ` · ${x.uf}` : ""}`,
        cor: fonte === "renuncia" ? "var(--c4)" : fonte === "emendas" ? "var(--c7)" : "var(--s1)",
      }))} />
      <div className="search" style={{ marginTop: 12 }}>
        <input aria-label="Procurar empresa, entidade ou CNPJ" value={q} onChange={(e) => { setQ(e.target.value); setN(20); }}
          placeholder={fonte === "emendas" ? "Empresa, CNPJ, parlamentar ou partido" : "Empresa, entidade, CNPJ ou órgão"} />
      </div>
      <div className="table-wrap">
        <table className="inc-tabela">
          <thead><tr><th className="r">#</th><th>Quem recebeu</th><th className="r">Valor</th></tr></thead>
          <tbody>
            {filtradas.slice(0, n).map((x) => (
              <tr key={x.cnpj}>
                <td className="r num muted">{linhas.indexOf(x) + 1}</td>
                <td>
                  <ExplicaLinha x={x} />
                  <div className="small muted">{[TIPO_NOME[x.tipo], cnpjFmt(x.cnpj), x.uf].filter(Boolean).join(" · ")}</div>
                  <div className="small">{x.detalhe}</div>
                  <Donos x={x} />
                  <div className="small"><a href={`${PORTAL_PJ}${x.cnpj}`} target="_blank" rel="noreferrer">Tudo o que recebeu, no Portal da Transparência ↗</a></div>
                </td>
                <td className="r num">{reais(x.valor)}</td>
              </tr>
            ))}
            {!filtradas.length && <tr><td colSpan={3} className="muted">Nada encontrado.</td></tr>}
          </tbody>
        </table>
      </div>
      {filtradas.length > n && <button className="link" onClick={() => setN(n + 40)}>Mostrar mais ({filtradas.length - n} restantes)</button>}
      {fonte === "renuncia" && ren && <p className="small muted">Valores declarados pelas próprias empresas à Receita. <a href={linkSeguro(ren.url)} target="_blank" rel="noreferrer">{ren.url.endsWith(".zip") ? "Arquivo" : "Consulta"} oficial de {ren.ano} ↗</a>{ren.sem_cnpj > 0 && <> · {reais(ren.sem_cnpj)} estão no total sem um CNPJ válido no arquivo.</>}</p>}
    </section>
  );
}

function ExplicaLinha({ x }: { x: Linha }) {
  const chip = x.tipo === "entidade" ? <span className="chip">entidade</span> : x.tipo === "publico" ? <span className="chip">estatal</span> : null;
  return <Explicacao nome={x.nome} cnpj={x.cnpj} valor={x.valor} partes={x.partes} frase={x.frase} pagina={x.pagina} chip={chip} />;
}


function Donos({ x }: { x: Dono & { tipo: Tipo } }) {
  if (!x.donos.length && !x.n_outras) return null;
  const quem = x.tipo === "entidade" ? "Dirigentes" : "Sócios";
  return (
    <div className="small inc-donos">
      {x.donos.length > 0 && <>{quem}: {x.donos.join(", ")}</>}
      {x.n_outras > 0 && <> · <strong>{x.n_outras} outra{x.n_outras > 1 ? "s" : ""} empresa{x.n_outras > 1 ? "s" : ""} dos mesmos donos</strong> no site</>}
    </div>
  );
}

/* ------------------------------------------------------------------ quem deu mais (emendas) */

function QuemDeu({ emd, ano }: { emd: Emendas; ano: string }) {
  const [casa, setCasa] = useState<Casa | "">("");
  const [q, setQ] = useState("");
  const [n, setN] = useState(15);
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const lista = emd.politicos.filter((p) => (!casa || p.casa === casa) && (!q.trim() || semAcento(`${p.nome} ${p.partido} ${p.uf}`).includes(semAcento(q.trim()))));
  const max = Math.max(1, ...lista.slice(0, 1).map((p) => p.valor));
  const principais = new Set(emd.partidos.slice(0, 8).map((p) => p.sigla));
  const lados = useMemo(() => {
    const pos = new Map((pols || []).map((p) => [p.id, p.posicao]));
    const soma = new Map<string, [number, number]>();
    emd.politicos.forEach((p) => {
      const x = p.politico ? pos.get(p.politico) : null;
      const lado = x == null ? "Sem posição" : ladoPelosVotos(x);
      const s = soma.get(lado) || [0, 0];
      soma.set(lado, [s[0] + p.valor, s[1] + 1]);
    });
    return [...LADOS, "Sem posição"].filter((l) => soma.has(l)).map((l) => ({ lado: l, valor: soma.get(l)![0], n: soma.get(l)![1] }));
  }, [pols, emd]);
  return (
    <section>
      <h2>Quem deu mais: parlamentares, partidos e estados</h2>
      <Explain>
        Deputados e senadores indicam para onde vai o dinheiro das emendas. Quando um ministério paga uma empresa ou entidade com esse dinheiro, o pagamento fica ligado ao parlamentar.
        Em {ano}, foram {reaisCurto(emd.total)} para {emd.n.toLocaleString("pt-BR")} empresas e entidades.
      </Explain>

      <h3 className="inc-sub">Por parlamentar</h3>
      <div className="row" style={{ gap: 8 }}>
        <div className="toggle" role="group" aria-label="Casa">
          <button aria-pressed={casa === ""} onClick={() => setCasa("")}>Todos</button>
          {(["camara", "senado"] as Casa[]).map((c) => <button key={c} aria-pressed={casa === c} onClick={() => setCasa(c)}>{casaNome(c)}</button>)}
        </div>
        <div className="search" style={{ flex: "1 1 240px" }}>
          <input aria-label="Procurar parlamentar" value={q} onChange={(e) => { setQ(e.target.value); setN(15); }} placeholder="Nome, partido ou estado" />
        </div>
      </div>
      <div className="emd-autores">
        {lista.slice(0, n).map((p, i) => (
          <details key={`${p.nome}-${i}`} className="emd-autor">
            <summary>
              <span className="emd-pos num muted">{i + 1}</span>
              <span className="emd-quem">
                <strong>{p.nome}</strong>
                <span className="small muted">{p.partido ? <><i className="partido-cor" style={{ background: corPartido(p.partido) }} />{p.partido}</> : "Partido não identificado"}{p.uf && `-${p.uf}`}{p.casa && ` · ${casaNome(p.casa)}`} · {p.n} recebedor{p.n > 1 ? "es" : ""}</span>
              </span>
              <span className="num emd-valor">{reaisCurto(p.valor)}</span>
              <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${(p.valor / max) * 100}%`, background: p.partido ? corPartido(p.partido) : "var(--c-outros)" }} /></span>
            </summary>
            <div className="emd-det">
              <div style={{ gridColumn: "1 / -1" }}>
                <h4>Empresas e entidades que mais receberam das emendas de {p.nome}</h4>
                <ul>{p.recebedores.map(([nome, cnpj, v, pagina]) => (
                  <li key={cnpj}><span>{pagina ? <Link to={`/e/${cnpj}`}>{nome}</Link> : nome} <span className="muted small mono">{cnpjFmt(cnpj)}</span></span><span className="num">{reaisCurto(v)}</span></li>
                ))}</ul>
                {p.politico && <p className="small"><Link to={`/p/${p.politico}`}>Ver gastos e votos de {p.nome}</Link> · <Link to="/emendas">Todas as emendas de {ano}</Link></p>}
              </div>
            </div>
          </details>
        ))}
        {!lista.length && <div className="empty">Ninguém encontrado.</div>}
      </div>
      {lista.length > n && <button className="link" onClick={() => setN(n + 30)}>Mostrar mais ({lista.length - n} restantes)</button>}

      <div className="two" style={{ marginTop: 16 }}>
        <div>
          <h3 className="inc-sub">Por partido</h3>
          <Pizza fatias={emd.partidos.map((p) => ({ sigla: p.sigla, valor: p.valor, cor: corPartido(p.sigla), outros: !principais.has(p.sigla) }))}
            titulo={`Emendas pagas a empresas e entidades por partido em ${ano}`} />
          <Barras formato={curto} itens={emd.partidos.slice(0, 12).map((p) => ({
            label: <Link to={`/politicos?partido=${encodeURIComponent(p.sigla)}`}><i className="partido-cor" style={{ background: corPartido(p.sigla) }} /><strong>{p.sigla}</strong></Link>,
            nota: `${p.n} parlamentar${p.n > 1 ? "es" : ""} · ${reaisCurto(p.valor / p.n)} por parlamentar`, valor: p.valor, cor: corPartido(p.sigla),
          }))} />
          {emd.sem_partido > 0 && <p className="small muted">Sem partido identificado: {reaisCurto(emd.sem_partido)} (ex-parlamentares que não achamos).</p>}
        </div>
        <div>
          <h3 className="inc-sub">Da esquerda à direita</h3>
          <p className="small muted" style={{ margin: "4px 0 12px" }}>Cada parlamentar no lado em que vota, pela régua calculada com os votos de cada um no Plenário (a mesma das páginas de políticos e partidos).</p>
          <Barras formato={curto} rosca={{ titulo: `Emendas pagas a empresas e entidades em ${ano}, por lado` }} itens={lados.map((l) => ({ nome: l.lado, label: <strong>{l.lado}</strong>, nota: `${l.n} parlamentar${l.n > 1 ? "es" : ""}`, valor: l.valor, cor: COR_LADO[l.lado] }))} />
          <h3 className="inc-sub" style={{ marginTop: 20 }}>Pelo estado do parlamentar</h3>
          <MapaAnos porAno={{ [ano]: Object.fromEntries(emd.por_uf_politico.map(([uf, v]) => [uf, v])) }} titulo={`Emendas pagas a empresas e entidades em ${ano}, pelo estado do parlamentar`} formato={curto} />
        </div>
      </div>
      {emd.coletivos.length > 0 && <>
        <h3 className="inc-sub">Emendas de bancada, comissão e relator</h3>
        <p className="small muted">Decididas em grupo; não entram nas contas por parlamentar e por partido.</p>
        <Barras formato={curto} itens={emd.coletivos.slice(0, 8).map((c) => ({ label: <strong>{c.nome}</strong>, nota: `${c.n} recebedor${c.n > 1 ? "es" : ""}`, valor: c.valor, cor: "var(--c-outros)" }))} />
      </>}
    </section>
  );
}

/* ------------------------------------------------------------------ por estado */

function PorEstado({ pag, ren, emd, ano, anosR }: { pag: Pagamentos | null; ren: Renuncia | null; emd: Emendas | null; ano: string; anosR: Indice["anos_renuncia"] }) {
  const fontes = (["pagamentos", "renuncia", "emendas"] as Fonte[]).filter((f) => (f === "pagamentos" ? pag : f === "renuncia" ? ren : emd));
  const [escolhida, setFonte] = useState<Fonte>("renuncia");
  const fonte = fontes.includes(escolhida) ? escolhida : fontes[0];
  // Renúncia: todos os anos publicados, para ver no mapa como mudou (baixados quando a pessoa chega aqui)
  const [ref, visivel] = useVisivel<HTMLElement>();
  const rens = useVarios<Renuncia>(visivel && fonte === "renuncia" ? anosR.map((a) => `incentivos/renuncia-${a.ano}.json`) : null);
  if (!fonte) return null;
  const lista = fonte === "pagamentos" ? pag!.por_uf : fonte === "renuncia" ? ren!.por_uf : emd!.por_uf_recebedor;
  const total = lista.reduce((a, [, v]) => a + v, 0);
  const rotR = (r: Renuncia) => `${r.ano}${r.parcial ? " (incompleto)" : ""}`;
  const porAno: Record<string, Record<string, number>> = fonte === "renuncia"
    ? Object.fromEntries([...Object.values(rens), ren!].map((r) => [rotR(r), Object.fromEntries(r.por_uf.map(([uf, v]) => [uf, v]))]))
    : { [ano]: Object.fromEntries(lista.map(([uf, v]) => [uf, v])) };
  return (
    <section ref={ref}>
      <h2>Em que estado ficam as empresas que mais recebem</h2>
      <div className="toggle inc-abas" role="group" aria-label="De onde vem o dinheiro">
        {fontes.map((f) => <button key={f} aria-pressed={fonte === f} onClick={() => setFonte(f)}>{FONTE_NOME[f]}</button>)}
      </div>
      <Explain>
        {fonte === "renuncia" && <>Pelo endereço da empresa na Receita, no ano-calendário. Inclui todas as empresas com renúncia fiscal. Toque em “Ver os anos passando” para ver cada ano publicado.</>}
        {fonte === "pagamentos" && <>Pelo endereço na Receita das {pag?.top_n_receita.toLocaleString("pt-BR")} empresas e entidades que mais receberam em {ano} ({pctDe(total, pag?.total || 0)} do valor pago). Empresas com sede num estado podem trabalhar em outros.</>}
        {fonte === "emendas" && <>Pelo endereço na Receita das empresas e entidades pagas com emendas em {ano}.</>}
      </Explain>
      <MapaAnos key={fonte} porAno={porAno} anoInicial={fonte === "renuncia" ? rotR(ren!) : ano} titulo={`${FONTE_NOME[fonte]}, por estado da empresa`} formato={curto} />
    </section>
  );
}

/* ------------------------------------------------------------------ para quê */

function ParaQue({ pag, ren, ano, anosR }: { pag: Pagamentos | null; ren: Renuncia | null; ano: string; anosR: Indice["anos_renuncia"] }) {
  const [ref, visivel] = useVisivel<HTMLElement>();
  const rens = useVarios<Renuncia>(visivel && ren ? anosR.map((a) => `incentivos/renuncia-${a.ano}.json`) : null);
  const rot = (r: Renuncia) => `${r.ano}${r.parcial ? " (incompleto)" : ""}`;
  const setores: Record<string, Fatia[]> = Object.fromEntries(Object.values(rens).map((r) => [rot(r), r.por_setor.map((x) => ({ nome: x.setor, valor: x.valor }))]));
  const beneficios: Record<string, Fatia[]> = Object.fromEntries(Object.values(rens).map((r) => [rot(r), r.por_beneficio.map((x) => ({ nome: x.nome, valor: x.valor }))]));
  if (!pag && !ren) return null;
  return (
    <section ref={ref}>
      <h2>Para quê</h2>
      <div>
        {pag && <div>
          <h3 className="inc-sub">O que o governo pagou em {ano}</h3>
          <Barras formato={curto} rosca={{ titulo: `O que o governo pagou em ${ano}` }} itens={pag.por_categoria.map((c) => ({ nome: c.rotulo, label: <strong>{c.rotulo}</strong>, nota: `${plural(c.n, "recebedor", "recebedores")} · ${pctDe(c.valor, pag.total)}`, valor: c.valor, cor: CAT_COR[c.cat] }))} />
          <h3 className="inc-sub" style={{ marginTop: 20 }}>Quem pagou: ministérios e órgãos</h3>
          <Barras formato={curto} rosca={{ titulo: `Quem pagou em ${ano}`, total: pag.total, paleta: true }} itens={pag.orgaos.slice(0, 10).map(([o, v]) => ({ nome: o, label: <strong>{o}</strong>, nota: pctDe(v, pag.total), valor: v, cor: "var(--s1)" }))} />
        </div>}
        {ren && <div>
          <h3 className="inc-sub">Os benefícios fiscais que mais custaram em {ren.ano}</h3>
          <Barras formato={curto} rosca={{ titulo: `Renúncia fiscal em ${ren.ano}, por benefício`, total: ren.total, paleta: true }} itens={ren.por_beneficio.slice(0, 10).map((b) => ({ nome: b.nome, label: <strong>{b.nome}</strong>, nota: `${b.tributo ? `${b.tributo} · ` : ""}${plural(b.n, "empresa", "empresas")}`, valor: b.valor, cor: "var(--c4)" }))} />
          <h3 className="inc-sub" style={{ marginTop: 20 }}>Por setor da economia</h3>
          <Barras formato={curto} rosca={{ titulo: `Renúncia fiscal em ${ren.ano}, por setor`, total: ren.total, paleta: true }} itens={ren.por_setor.slice(0, 10).map((s) => ({ nome: s.setor, label: <strong>{s.setor}</strong>, nota: `${plural(s.n, "empresa", "empresas")} · ${pctDe(s.valor, ren.total)}`, valor: s.valor, cor: "var(--c4)" }))} />
        </div>}
      </div>
      {ren && (
        <div className="secao-graficos">
          <CompararAnos porAno={setores} titulo="Renúncia fiscal por setor, ano a ano" anoInicial={rot(ren)} limite={8} nota="Pelo ano-calendário. Ano marcado como incompleto ainda não foi publicado inteiro pela Receita." />
          <CompararAnos porAno={beneficios} titulo="Os benefícios fiscais, ano a ano" anoInicial={rot(ren)} limite={8} />
        </div>
      )}
    </section>
  );
}

/* Explicação ao tocar no nome: quanto recebeu, para quê, quem pagou e os links oficiais para conferir */
function Explicacao({ nome, cnpj, valor, frase, partes, pagina, chip }: {
  nome: string; cnpj: string; valor: number; frase: ReactNode; partes: { titulo: string; itens: Par[] }[]; pagina?: boolean; chip?: ReactNode;
}) {
  return (
    <details className="inc-explica">
      <summary><strong>{nome}</strong>{chip && <> {chip}</>} <span className="inc-explica-dica small">ver de onde veio o dinheiro</span></summary>
      <div className="inc-explica-corpo small">
        <p>{frase}</p>
        {partes.filter((p) => p.itens.length).map((p) => (
          <div key={p.titulo}>
            <strong>{p.titulo}</strong>
            <ul>{p.itens.slice(0, 8).map(([n, v]) => (
              <li key={n}><span>{n}</span><span className="num">{curto(v)} <span className="muted">· {pctDe(v, valor)}</span></span>
                <i aria-hidden="true" style={{ width: `${Math.min(100, (v / (valor || 1)) * 100)}%` }} /></li>
            ))}</ul>
          </div>
        ))}
        <p className="inc-explica-links">
          {cnpj && <a href={`${PORTAL_PJ}${cnpj}`} target="_blank" rel="noreferrer">Cada pagamento, contrato e convênio no Portal da Transparência ↗</a>}
          {cnpj && <a href={`https://minhareceita.org/${cnpj}`} target="_blank" rel="noreferrer">Cadastro na Receita Federal (CNPJ {cnpjFmt(cnpj)}) ↗</a>}
          {pagina && <Link to={`/e/${cnpj}`}>Donos, outras empresas dos mesmos donos e tudo o que recebeu</Link>}
        </p>
      </div>
    </details>
  );
}
