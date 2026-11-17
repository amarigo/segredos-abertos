import { useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Accordion, Anchor, Badge, Blockquote, Button, Card, Checkbox, Group, NativeSelect, SimpleGrid, Stack, Tabs, Text, TextInput, Title } from "@mantine/core";
import { Explain, Loading, useData } from "../components/ui";
import { TEMAS, autorSigla, nomeTipo, casaNome, dataBR, dataHoraBR, linkSeguro, type ArgumentoProjeto, type GrupoProjeto, type NoticiaContra, type Projeto, type Tramitacao, type TramitacaoAlmg } from "../data";
import { norm } from "./Home";
import { MG } from "../recorte";
import { AvisosFim } from "../components/Selo";
import CaminhoLei from "../components/CaminhoLei";

const ETAPAS_CONGRESSO = ["Apresentada", "Comissões", "Plenário", "Outra Casa", "Sanção ou promulgação"];
const ETAPAS_ALMG = ["Apresentado", "Comissões", "Plenário", "Sanção do governador"];
const ABAS: { id: GrupoProjeto | "almg"; nome: string; explica: string }[] = [
  { id: "pauta", nome: "Na pauta", explica: "Marcadas para votação nas próximas sessões do Plenário e reuniões das comissões. A pauta pode mudar até a hora da reunião." },
  { id: "mpv", nome: "Medidas provisórias", explica: "Já valem como lei, mas o Congresso precisa aprovar dentro do prazo, senão perdem a validade." },
  { id: "nova", nome: "Recém-apresentadas", explica: "Propostas que acabaram de chegar. A maioria ainda espera o presidente da Casa dizer por quais comissões vai passar." },
];
const CASA_NOME: Record<string, string> = { camara: "Câmara", senado: "Senado", almg: "Assembleia de Minas" };

function etapaAlmg(i: number) { return i >= 4 ? 3 : Math.min(i, 2); }

export function Etapas({ p }: { p: Projeto }) {
  const almg = p.casa === "almg";
  const nomes = almg ? ETAPAS_ALMG : ETAPAS_CONGRESSO;
  const atual = almg ? etapaAlmg(p.etapa) : p.etapa;
  return (
    <div>
    <ol className="proj-etapas" aria-label={`Etapa atual: ${nomes[atual]}`}>
      {nomes.map((n, i) => (
        <li key={n} className={i < atual ? "feita" : i === atual ? "atual" : ""} aria-current={i === atual ? "step" : undefined}>
          <span>{n}</span>
        </li>
      ))}
    </ol>
    <p className="small so-celular proj-etapa-txt">Etapa {atual + 1} de {nomes.length}: <b>{nomes[atual]}</b></p>
    </div>
  );
}

function Autores({ p }: { p: Projeto }) {
  if (!p.autores.length) return null;
  const mais = p.n_autores - p.autores.length;
  const origem = linkSeguro(p.url_origem);
  return (
    <Text size="sm"><b>Quem propôs: </b>
      {p.autores.map((a, k) => (
        <span key={k}>{k > 0 && ", "}{a.id ? <Link to={`/p/${a.id}`}>{a.nome}</Link> : a.nome}{autorSigla(a)}
          {a.cargo && a.cargo !== "Poder Executivo" && `, ${a.cargo.toLowerCase()}`}</span>
      ))}
      {mais > 0 && ` e mais ${mais}`}
      {p.veio_da_camara && <> · começou na Câmara, que aprovou e enviou ao Senado{origem && <> (<a href={origem} target="_blank" rel="noreferrer">ver na Câmara ↗</a>)</>}</>}
      {p.veio_do_senado && " · começou no Senado, que aprovou e enviou à Câmara"}
    </Text>
  );
}

/** Frase copiada do documento, sem mudar palavras. A cor da borda diz o lado (a favor ou contra). */
function Trecho({ cor, children }: { cor: string; children: ReactNode }) {
  return <Blockquote color={cor} p="xs" pl="sm" fz="sm" fs="italic" className="proj-trecho">{children}</Blockquote>;
}

function Argumento({ a, tudo, cor }: { a: ArgumentoProjeto; tudo: boolean; cor: string }) {
  const u = linkSeguro(a.url);
  const trechos = tudo ? a.trechos : a.trechos.slice(0, 1);
  return (
    <Stack gap={4} className="proj-arg">
      <Text size="sm"><b>{a.quem || "Relator"}</b> · {a.papel}{a.casa && ` · ${a.casa}`}{a.data && `, ${dataBR(a.data)}`}
        {a.conclusao && <> · concluiu pela <b>{a.conclusao}</b></>}</Text>
      {trechos.map((t, k) => <Trecho key={k} cor={cor}>“{t}”</Trecho>)}
      {a.trechos.length === 0 && <Text size="sm" c="dimmed">Sem frase curta que explique o motivo; o argumento está no documento.</Text>}
      {u && <Anchor size="sm" href={u} target="_blank" rel="noreferrer">Ler o documento oficial ↗</Anchor>}
    </Stack>
  );
}

/** Quem fala contra numa notícia: veículo, data, quem fala (como está no trecho) e o link da publicação original. */
function Noticia({ n, tudo }: { n: NoticiaContra; tudo: boolean }) {
  const u = linkSeguro(n.url);
  const trechos = tudo ? n.trechos : n.trechos.slice(0, 1);
  return (
    <Stack gap={4} className="proj-noticia">
      <Badge color="yellow" variant="light" style={{ alignSelf: "flex-start" }}>Notícia · fonte não oficial</Badge>
      {n.quem && <Text size="sm">{"Quem fala: "}<b>{n.quem}</b></Text>}
      <Text size="sm">{"Publicado em "}<b>{n.veiculo}</b>{n.data && `, ${dataBR(n.data)}`}
        {n.autor && <Text span c="dimmed" inherit>{` · texto de ${n.autor}`}</Text>}</Text>
      {trechos.map((t, k) => <Trecho key={k} cor="gray">{/^[“"]/.test(t) ? t : `“${t}”`}</Trecho>)}
      {u && <Anchor size="sm" href={u} target="_blank" rel="noreferrer">{n.titulo ? `Ler a notícia original: ${n.titulo} ↗` : "Ler a notícia original ↗"}</Anchor>}
    </Stack>
  );
}

/** Contagem do título do item recolhido: quantos a favor e quantos contra, sem abrir. */
function DebateResumo({ p }: { p: Projeto }) {
  const d = p.debate!;
  const nots = d.contra.length ? [] : d.noticias_contra || [];
  return (
    <Group gap="4px 12px" wrap="wrap" align="baseline" component="span" style={{ display: "inline-flex" }}>
      <Text span fw={700}>O que dizem a favor e contra</Text>
      <Text span size="sm"><Text span inherit c="var(--sim-ink)" fw={700}>{`${d.favor.length} a favor`}</Text>{" · "}
        <Text span inherit c="var(--nao-ink)" fw={700}>{`${d.contra.length} contra`}</Text>
        {nots.length > 0 && <>{" · "}<Text span inherit c="var(--nao-ink)" fw={700}>{`${nots.length} contra em notícias`}</Text></>}</Text>
    </Group>
  );
}

/** O que dizem a favor e contra: trechos copiados de documentos oficiais (o coletor explica em debate.py). Quando
 * nenhum documento oficial é contra, o lado contra mostra quem fala contra em notícias, marcado como fonte não oficial. */
export function Debate({ p }: { p: Projeto }) {
  const [tudo, setTudo] = useState(false);
  const d = p.debate;
  if (!d) return null;
  const nots = d.contra.length ? [] : d.noticias_contra || [];
  const temMais = [...d.favor, ...d.contra, ...nots].some((a) => a.trechos.length > 1) || d.favor.length > 2 || d.contra.length > 2 || nots.length > 2;
  const lado = (titulo: string, cls: string, cor: string, corTitulo: string, xs: ArgumentoProjeto[], vazio: string, extra?: ReactNode) => (
    <Stack gap="sm" className={`proj-lado ${cls}`}>
      <Title order={4} size="h5" c={corTitulo}>{titulo} <Text span size="sm" c="dimmed">({xs.length})</Text></Title>
      {xs.length === 0
        ? <Text size="sm" c="dimmed">{vazio}</Text>
        : (tudo ? xs : xs.slice(0, 2)).map((a, k) => <Argumento key={k} a={a} tudo={tudo} cor={cor} />)}
      {extra}
    </Stack>
  );
  // Sem documento oficial contra: o que achamos em notícias (ou o aviso de que procuramos e não achamos)
  const emNoticias = !d.contra.length && d.noticias_buscadas_em ? (
    nots.length > 0 ? (
      <>
        <Text size="sm"><b>{`Em notícias (${nots.length})`}</b>{": como nenhum documento oficial é contra, procuramos quem fala contra na imprensa."}</Text>
        {(tudo ? nots : nots.slice(0, 2)).map((n, k) => <Noticia key={k} n={n} tudo={tudo} />)}
        <Text size="sm" c="dimmed">Notícia não é documento oficial. A frase foi copiada da notícia sem mudar palavras e escolhida automaticamente; confira o contexto no link.</Text>
      </>
    ) : <Text size="sm" c="dimmed">{`Também procuramos em notícias (em ${dataBR(d.noticias_buscadas_em)}) e não achamos ninguém falando contra esta proposta pelo número dela.`}</Text>
  ) : null;
  return (
    <Stack gap="sm">
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg" verticalSpacing="md">
        {lado("A favor", "favor", "var(--sim)", "var(--sim-ink)", d.favor, "Ainda não há documento oficial a favor nesta proposta (justificação do autor ou parecer pela aprovação).")}
        {lado("Contra", "contra", "var(--nao)", "var(--nao-ink)", d.contra, "Ninguém registrou documento oficial contra até agora (parecer pela rejeição ou voto em separado). Pode haver quem discorde sem ter posto isso por escrito.", emNoticias)}
      </SimpleGrid>
      {temMais && <Button variant="subtle" size="compact-sm" style={{ alignSelf: "flex-start" }} onClick={() => setTudo(!tudo)}>{tudo ? "Mostrar menos" : "Ver todos os trechos"}</Button>}
      <Text size="sm" c="dimmed">Frases copiadas dos documentos oficiais, sem mudar palavras: a justificação de quem propôs, o parecer dos relatores e os votos em separado. Escolhemos as frases que falam do efeito e do motivo; o documento completo está no link.</Text>
    </Stack>
  );
}

function proximoAlmg(p: Projeto): string {
  const onde = [p.fase, p.onde].filter(Boolean).join(", ");
  return `Situação oficial: ${p.situacao || "sem informação"}${onde ? ` (${onde})` : ""}. A ALMG não publica nos dados abertos a data da próxima votação; veja a agenda na página do projeto.`;
}

/** Texto oficial e o resto do detalhe da proposta: ementa, situação, regime, temas e últimos passos. */
function MaisDetalhes({ p }: { p: Projeto }) {
  const texto = linkSeguro(p.texto);
  return (
    <Stack gap="xs" fz="sm">
      {p.resumo && <Text inherit><b>Ementa oficial: </b>{p.ementa}</Text>}
      {p.resumo_oficial && p.resumo_oficial !== p.ementa && <Text inherit><b>Resumo da ALMG: </b>{p.resumo_oficial}</Text>}
      {p.o_que_e && <Text inherit><b>O que significa {p.sigla}: </b>{p.o_que_e}</Text>}
      {p.situacao && <Text inherit><b>Situação oficial: </b>{p.situacao}{p.onde && ` · ${p.onde}`}{p.atualizada && ` (desde ${dataBR(p.atualizada)})`}</Text>}
      {p.regime && <Text inherit><b>Regime: </b>{p.regime}</Text>}
      {p.tranca_pauta && !p.suspenso && <Text inherit>A partir de {dataBR(p.tranca_pauta)}, se ainda não tiver sido votada, ela <b>tranca a pauta</b>: a Casa onde está não pode votar outros projetos de lei antes dela.</Text>}
      {p.temas && p.temas.length > 0 && <Text inherit><b>Temas: </b>{p.temas.join(" · ")}</Text>}
      {p.passos && p.passos.length > 0 && (
        <div><b>Últimos passos</b>
          <ul style={{ margin: "4px 0 0" }}>{p.passos.map((x, k) => <li key={k}>{dataBR(x.data)} · {x.onde}: {x.texto}</li>)}</ul>
        </div>
      )}
      {texto && <Anchor inherit href={texto} target="_blank" rel="noreferrer">Ler o texto completo da proposta ↗</Anchor>}
    </Stack>
  );
}

export function CartaoProjeto({ p }: { p: Projeto }) {
  const titulo = p.resumo || p.ementa;
  const oficial = linkSeguro(p.url);
  const casa = CASA_NOME[p.casa] || p.casa;
  return (
    <Card withBorder radius="md" padding="md" component="article" className="proj" id={p.id}>
      <Stack gap="sm">
        <Group gap="xs" wrap="wrap">
          <Badge variant="outline" color="gray">{p.nome}</Badge>
          {p.grupos.includes("pauta") && <Badge variant="light" color="green">Na pauta</Badge>}
          {p.sigla === "MPV" && p.prazo && !p.suspenso && <Badge variant="light" color="yellow">Prazo: {dataBR(p.prazo)}</Badge>}
          {p.suspenso && <Badge variant="light" color="gray">Prazo suspenso</Badge>}
          {p.do_estado && <Badge variant="light" color="gray">Autor de MG</Badge>}
          <Text size="sm" c="dimmed">{casa}{p.apresentada && ` · apresentada em ${dataBR(p.apresentada)}`}</Text>
        </Group>
        <Title order={3} size="h4" className="proj-titulo">{titulo}</Title>
        <Autores p={p} />
        <Etapas p={p} />
        <Card.Section withBorder inheritPadding py="xs" bg="var(--mantine-color-default-hover)">
          <Text><b>Próximo passo: </b>{p.casa === "almg" ? proximoAlmg(p) : p.proximo}</Text>
          {p.pauta && p.pauta.length > 0 && (
            <ul className="proj-pauta">
              {p.pauta.map((x, k) => {
                const u = linkSeguro(x.url);
                return (
                  <li key={k}><Text size="sm" span><b>{dataHoraBR(x.data)}</b> · {u ? <Anchor inherit href={u} target="_blank" rel="noreferrer">{x.onde}</Anchor> : x.onde}
                    {x.urgencia && " · pedido de urgência"}{x.relator && ` · relator: ${x.relator}`}</Text>
                    {x.parecer && <Text size="sm" c="dimmed">Parecer: {x.parecer}</Text>}</li>
                );
              })}
            </ul>
          )}
        </Card.Section>
        <Accordion multiple variant="default" chevronPosition="right">
          {p.debate && (
            <Accordion.Item value="debate" className="proj-debate">
              <Accordion.Control className="proj-debate-abre" px={0}><DebateResumo p={p} /></Accordion.Control>
              <Accordion.Panel><Debate p={p} /></Accordion.Panel>
            </Accordion.Item>
          )}
          <Accordion.Item value="texto" style={{ borderBottom: 0 }}>
            <Accordion.Control px={0}><Text span fw={700}>Texto oficial e mais detalhes</Text></Accordion.Control>
            <Accordion.Panel><MaisDetalhes p={p} /></Accordion.Panel>
          </Accordion.Item>
        </Accordion>
        {oficial && <Anchor size="sm" href={oficial} target="_blank" rel="noreferrer">Ver na página oficial {p.casa === "camara" ? "da Câmara" : p.casa === "senado" ? "do Senado" : "da ALMG"} ↗</Anchor>}
      </Stack>
    </Card>
  );
}


export default function TramitacaoPage() {
  const { data, error } = useData<Tramitacao>("tramitacao.json");
  const { data: almg } = useData<TramitacaoAlmg>(MG ? "almg/tramitacao.json" : null);
  const [params, setParams] = useSearchParams();
  const aba = (params.get("aba") || "pauta") as GrupoProjeto | "almg";
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [tipo, setTipo] = useState("");
  const [tema, setTema] = useState("");
  const [soMG, setSoMG] = useState(false);
  const [limite, setLimite] = useState(40);
  const mudarAba = (a: string) => { setParams(a === "pauta" ? {} : { aba: a }, { replace: true }); setLimite(40); };

  const abas = useMemo(() => [...ABAS, ...(MG ? [{ id: "almg" as const, nome: "Assembleia de Minas", explica: `Projetos de deputados estaduais e do governo de Minas que ainda não viraram lei e tiveram algum passo nos últimos ${almg?.dias_andamento || 30} dias.` }] : [])], [almg]);
  const base = useMemo(() => {
    if (aba === "almg") return almg?.itens || [];
    return (data?.itens || []).filter((p) => p.grupos.includes(aba as GrupoProjeto));
  }, [data, almg, aba]);
  const tipos = useMemo(() => [...new Set(base.map((p) => p.sigla))].sort(), [base]);
  const lista = useMemo(() => base.filter((p) => (!casa || p.casa === casa) && (!tipo || p.sigla === tipo)
    && (!tema || !!p.temas?.includes(tema)) && (!soMG || p.do_estado || p.casa === "almg")
    && (!q || norm(`${p.nome} ${p.sigla} ${p.numero} ${p.ementa} ${p.resumo || ""} ${p.autores.map((a) => `${a.nome} ${a.partido}`).join(" ")}`).includes(norm(q)))),
  [base, casa, tipo, tema, soMG, q]);
  const conta = (id: string) => id === "almg" ? (almg?.itens.length || 0) : (data?.itens || []).filter((p) => p.grupos.includes(id as GrupoProjeto)).length;

  if (!data) return <Loading error={error} />;
  const atual = abas.find((a) => a.id === aba) || abas[0];
  const titulo = aba === "nova" ? `Apresentadas nos últimos ${data.dias_novas} dias` : atual.nome;
  // Na pauta: agrupado por dia da primeira reunião em que aparece
  const porDia: [string, Projeto[]][] = [];
  if (aba === "pauta") {
    for (const p of lista.slice(0, limite)) {
      const d = (p.pauta?.[0]?.data || "").slice(0, 10);
      const g = porDia.find(([k]) => k === d);
      if (g) g[1].push(p); else porDia.push([d, [p]]);
    }
  }
  const faltando = Object.entries(data.situacao_fontes || {}).filter(([, s]) => s !== "ok");

  return (
    <section>
      <Title order={1}>Projetos em andamento</Title>
      <Explain>
        O que está sendo proposto agora no Congresso{MG && " e na Assembleia de Minas"}, quem propôs e qual é o próximo passo.
        Tudo vem das APIs oficiais da Câmara e do Senado{MG && " e dos dados abertos da ALMG"}, atualizado em {dataBR(data.atualizado_em)}.
        Esta página mostra o momento atual e não depende do ano escolhido no topo.
      </Explain>

      <CaminhoLei />

      <Tabs value={aba} onChange={(a) => a && mudarAba(a)} mt="md">
        <Tabs.List aria-label="O que acompanhar">
          {abas.map((a) => <Tabs.Tab key={a.id} value={a.id}>{`${a.nome} (${conta(a.id)})`}</Tabs.Tab>)}
        </Tabs.List>
      </Tabs>
      <Text size="sm" c="dimmed" mt="xs">{atual.explica}</Text>

      <Group gap="sm" align="flex-end" wrap="wrap" my="md">
        <TextInput id="busca-projeto" aria-label="Buscar projeto" value={q} onChange={(e) => setQ(e.currentTarget.value)} placeholder="Assunto, número ou autor (ex.: PEC 7)" style={{ flex: "1 1 240px" }} />
        {aba !== "almg" && (
          <NativeSelect aria-label="Casa" value={casa} onChange={(e) => setCasa(e.currentTarget.value)}
            data={[{ value: "", label: "Câmara e Senado" }, { value: "camara", label: "Câmara" }, { value: "senado", label: "Senado" }]} />
        )}
        <NativeSelect aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.currentTarget.value)}
          data={[{ value: "", label: "Todos os tipos" }, ...tipos.map((t) => ({ value: t, label: nomeTipo(t) }))]} />
        {aba !== "almg" && (
          <NativeSelect aria-label="Tema" value={tema} onChange={(e) => setTema(e.currentTarget.value)}
            data={[{ value: "", label: "Todos os temas" }, ...TEMAS]} />
        )}
        {MG && aba !== "almg" && <Checkbox label="Só de autores de Minas" checked={soMG} onChange={(e) => setSoMG(e.currentTarget.checked)} mb={8} />}
      </Group>

      <Title order={2}>{titulo} <Text span c="dimmed" size="sm">({lista.length})</Text></Title>
      {lista.length === 0 && <div className="empty">{aba === "pauta" ? `Nenhuma proposta marcada para votação nos próximos ${data.dias_pauta} dias com esses filtros.` : "Nenhuma proposta com esses filtros."}</div>}
      <Stack gap="md" mt="sm">
        {aba === "pauta"
          ? porDia.map(([d, ps]) => (
            <Stack key={d} gap="sm">
              <Title order={3} size="h5" c="dimmed">{d ? dataHoraBR(d) : "Sem data"}</Title>
              {ps.map((p) => <CartaoProjeto key={p.id} p={p} />)}
            </Stack>
          ))
          : lista.slice(0, limite).map((p) => <CartaoProjeto key={p.id} p={p} />)}
      </Stack>
      {lista.length > limite && <Button variant="default" mt="md" onClick={() => setLimite(limite + 40)}>{`Mostrar mais (${lista.length - limite} restantes)`}</Button>}
      <Text size="sm" c="dimmed" mt="md">
        Fontes: <a href="https://dadosabertos.camara.leg.br/swagger/api.html" target="_blank" rel="noreferrer">API da Câmara</a> (eventos, pautas e proposições) e{" "}
        <a href="https://legis.senado.leg.br/dadosabertos/docs/" target="_blank" rel="noreferrer">API do Senado</a> (agenda do Plenário, das comissões e processos)
        {MG && <>, e o <a href="https://dadosabertos.almg.gov.br/" target="_blank" rel="noreferrer">arquivo de proposições da ALMG</a></>}.
        O resumo em linguagem simples troca o número da lei pelo nome conhecido e o juridiquês por palavras do dia a dia; a ementa oficial fica sempre nos detalhes. <Link to="/sobre">Como funciona</Link>.
      </Text>
      <AvisosFim>
        {faltando.length > 0 && (
          <p className="alert">{faltando.map(([c, s]) => `${casaNome(c as "camara" | "senado")}: ${s === "reserva" ? "a API não respondeu hoje; mostramos a última lista que conseguimos" : "a API não respondeu; essa Casa está faltando"}`).join(". ")}.</p>
        )}
      </AvisosFim>
    </section>
  );
}
