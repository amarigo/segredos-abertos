import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Accordion, Anchor, Badge, Blockquote, Button, Card, Chip, Group, NativeSelect, Paper, SimpleGrid, Stack, Table, Text, TextInput, Title } from "@mantine/core";
import { Explain, Loading, OndeVer, useData } from "../components/ui";
import { Detalhes, TituloSecao } from "../components/Detalhes";
import { AvisosFim } from "../components/Selo";
import { dataBR, type Julgamento, type LadoVoto, type Tribunais } from "../data";
import { norm } from "./Home";
import { numero } from "../components/graficos";

/* Julgamentos do Plenário do STF: como cada ministro votou nas ações que derrubam ou mantêm leis.
   Os dados vêm de etl/sa_etl/tribunais.py (serviços do portal do STF), com link para a página oficial de cada processo. */

const LADO: Record<LadoVoto, { nome: string; cor: string }> = {
  relator: { nome: "Com o relator", cor: "var(--s1)" },
  divergencia: { nome: "Divergiu do relator", cor: "var(--s2)" },
  vista: { nome: "Pediu vista (mais tempo)", cor: "var(--c6)" },
  fora: { nome: "Não votou (impedido ou suspeito)", cor: "var(--outro)" },
  outro: { nome: "Outro voto", cor: "var(--c5)" },
};
const ORDEM: LadoVoto[] = ["relator", "divergencia", "vista", "outro", "fora"];

function Placar({ j }: { j: Julgamento }) {
  const t = ORDEM.reduce((a, k) => a + (j.placar[k] || 0), 0) || 1;
  const txt = ORDEM.filter((k) => j.placar[k]).map((k) => `${LADO[k].nome}: ${j.placar[k]}`).join(" · ");
  return (
    <div>
      <div className="stack" role="img" aria-label={`Placar: ${txt}`} title={txt}>
        {ORDEM.filter((k) => j.placar[k]).map((k) => <span key={k} style={{ width: `${(j.placar[k] / t) * 100}%`, background: LADO[k].cor }} />)}
      </div>
      <Text size="sm" mt={4}>{txt}</Text>
    </div>
  );
}

function situacao(j: Julgamento): { texto: string; cor: string } {
  if (j.situacao === "em_julgamento") return { texto: "Em julgamento", cor: "gray" };
  if (j.situacao === "vista") return { texto: "Parado: pedido de vista", cor: "gray" };
  if (j.situacao === "destaque") return { texto: "Vai ao plenário presencial", cor: "gray" };
  if (j.situacao === "sem_maioria") return { texto: "Sem maioria na sessão", cor: "gray" };
  const unanime = !j.placar.divergencia && j.maioria === "relator";
  return { texto: unanime ? "Todos com o relator" : j.maioria === "relator" ? "Relator venceu" : "Divergência venceu", cor: j.maioria === "relator" ? "green" : "red" };
}

/** O que está em julgamento, em palavras simples. Vem do relatório do relator (a primeira frase, que diz quem pediu,
 * contra o quê e por quê); a explicação troca o juridiquês e a frase oficial fica um toque abaixo, com o link.
 * Sem relatório lido (ou em RE e ação rescisória, que podem citar pessoas comuns), fica a explicação do tipo de ação. */
function OQueSeJulga({ j, explica }: { j: Julgamento; explica?: string }) {
  const o = j.objeto;
  return (
    <Paper bg="var(--mantine-color-default-hover)" p="sm" radius="md" data-testid="o-que-se-julga">
      <Text size="sm" fw={700}>O que está em julgamento</Text>
      {o ? <>
        <Text size="sm" mt={4}>{o.simples || `“${o.texto}”`}</Text>
        <Text size="xs" c="dimmed" mt={4}>
          {o.simples ? "Explicação do relatório oficial do ministro relator, com palavras do dia a dia. " : "Trecho do relatório oficial do ministro relator, copiado sem mudar palavras. "}
          <Anchor inherit href={o.link} target="_blank" rel="noreferrer">Ver o relatório ↗</Anchor>
        </Text>
      </> : <Text size="sm" mt={4}>{explica ? `${j.classe}: ${explica}` : j.classe} <Anchor inherit href={j.link} target="_blank" rel="noreferrer">Ver o processo no STF ↗</Anchor></Text>}
    </Paper>
  );
}

function CartaoJulgamento({ j, explica }: { j: Julgamento; explica?: string }) {
  const s = situacao(j);
  const autores = j.partes.filter((p) => /REQTE|AUTOR/i.test(p.tipo)).map((p) => p.nome);
  return (
    <Card withBorder radius="md" padding="md" component="article" className="proj" data-testid="julgamento">
      <Stack gap="sm">
        <Group gap="xs" wrap="wrap">
          <Badge variant="outline" color="gray" title={explica}>{j.classe}</Badge>
          <Badge variant="light" color={s.cor}>{s.texto}</Badge>
          {j.resultado && <Badge variant="light" color="gray">{j.resultado}</Badge>}
          <Text size="sm" c="dimmed">Sessão virtual de {dataBR(j.inicio)} a {dataBR(j.fim)}</Text>
        </Group>
        <Title order={3} size="h4" className="proj-titulo"><Anchor inherit href={j.link} target="_blank" rel="noreferrer">{j.processo}</Anchor>{j.uf && <Text span c="dimmed" size="sm"> ({j.uf})</Text>}</Title>
        <Text size="sm">
          Relator: <strong>{j.relator || "não informado"}</strong>
          {autores.length > 0 && <> · Quem pediu: {autores.join(", ")}</>}
          {j.vista && <> · Pedido de vista: {j.vista}</>}
          {j.destaque && <> · Destaque (vai ao plenário presencial): {j.destaque}</>}
        </Text>
        <OQueSeJulga j={j} explica={explica} />
        <Placar j={j} />
        <Accordion multiple chevronPosition="right">
          {j.objeto?.simples && (
            <Accordion.Item value="relatorio">
              <Accordion.Control px={0}><Text span fw={700}>Texto oficial do relatório, sem mudar palavras</Text></Accordion.Control>
              <Accordion.Panel>
                <Blockquote color="gray" p="xs" pl="sm" fz="sm" fs="italic">“{j.objeto.texto}”</Blockquote>
                <Anchor size="sm" href={j.objeto.link} target="_blank" rel="noreferrer">Ler o relatório inteiro do ministro relator (PDF do STF) ↗</Anchor>
              </Accordion.Panel>
            </Accordion.Item>
          )}
          {j.decisao && (
            <Accordion.Item value="decisao">
              <Accordion.Control px={0}><Text span fw={700}>O que o STF decidiu (texto oficial)</Text></Accordion.Control>
              <Accordion.Panel><Text size="sm">{j.decisao}</Text></Accordion.Panel>
            </Accordion.Item>
          )}
          <Accordion.Item value="votos" style={{ borderBottom: 0 }}>
            <Accordion.Control px={0}><Text span fw={700}>{`Voto de cada ministro (${j.votos.length})`}</Text></Accordion.Control>
            <Accordion.Panel>
              <Table.ScrollContainer minWidth={520}>
                <Table verticalSpacing="xs" fz="sm">
                  <Table.Thead><Table.Tr><Table.Th>Ministro</Table.Th><Table.Th>Voto</Table.Th><Table.Th>Lado</Table.Th><Table.Th>Íntegra</Table.Th></Table.Tr></Table.Thead>
                  <Table.Tbody>
                    {j.votos.map((v) => (
                      <Table.Tr key={v.ministro}>
                        <Table.Td>{v.ministro}</Table.Td>
                        <Table.Td>{v.voto}{v.acompanha && <Text span inherit c="dimmed"> (acompanhou {v.acompanha})</Text>}</Table.Td>
                        <Table.Td><Group gap={6} wrap="nowrap">
                          <i aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 999, background: LADO[v.lado].cor, display: "inline-block", flex: "none" }} />{LADO[v.lado].nome}</Group></Table.Td>
                        <Table.Td>{v.link ? <Anchor inherit href={v.link} target="_blank" rel="noreferrer">Ler o voto</Anchor> : <Text span inherit c="dimmed">Não publicado</Text>}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
        <Text size="sm" c="dimmed">
          Fonte: <Anchor inherit href={j.link} target="_blank" rel="noreferrer">página do processo no STF</Anchor> e <Anchor inherit href={j.fonte} target="_blank" rel="noreferrer">placar oficial da sessão virtual</Anchor>.
        </Text>
      </Stack>
    </Card>
  );
}

export default function TribunaisPage() {
  const { data, error } = useData<Tribunais>("tribunais.json");
  const [q, setQ] = useState("");
  const [classe, setClasse] = useState("");
  const [ministro, setMinistro] = useState("");
  const [sit, setSit] = useState<"" | "decidido" | "aberto" | "dividido">("");
  const [limite, setLimite] = useState(30);
  const lista = useMemo(() => (data?.julgamentos || []).filter((j) => (!classe || j.classe === classe)
    && (!ministro || j.votos.some((v) => v.ministro === ministro))
    && (!sit || (sit === "decidido" ? j.situacao === "decidido" : sit === "aberto" ? j.situacao !== "decidido" : j.placar.divergencia > 0))
    && (!q || norm(`${j.processo} ${j.relator} ${j.decisao} ${j.partes.map((p) => p.nome).join(" ")}`).includes(norm(q)))),
  [data, q, classe, ministro, sit]);

  if (!data) return <Loading error={error} />;
  const classes = Object.keys(data.classes);
  const faltando = data.situacao_fontes?.stf && data.situacao_fontes.stf !== "ok" ? data.situacao_fontes.stf : "";
  const decididos = data.julgamentos.filter((j) => j.situacao === "decidido").length;
  const filtrado = !!(q || classe || ministro || sit);
  const ministros = data.ministros.length > 0 && (
    <section>
      <TituloSecao>Como cada ministro votou</TituloSecao>
      <Text size="sm" c="dimmed" mb="xs">"Ficou com a maioria" e "Ficou vencido" contam só os julgamentos decididos: a sessão terminou e um lado teve
        6 votos ou mais (maioria dos 11). O STF publica o resultado oficial alguns dias depois. Clique no nome para ver os julgamentos do ministro.</Text>
      <Table.ScrollContainer minWidth={680}>
        <Table verticalSpacing="xs">
          <Table.Thead><Table.Tr><Table.Th>Ministro</Table.Th><Table.Th ta="right">Votos</Table.Th><Table.Th ta="right">Relator</Table.Th><Table.Th ta="right">Divergiu do relator</Table.Th><Table.Th ta="right">Ficou com a maioria</Table.Th><Table.Th ta="right">Ficou vencido</Table.Th><Table.Th>Com a maioria</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {data.ministros.map((m) => {
              const base = m.com_maioria + m.vencido;
              const pct = base ? (m.com_maioria / base) * 100 : 0;
              return (
                <Table.Tr key={m.nome}>
                  <Table.Td><Anchor component="button" type="button" fw={ministro === m.nome ? 700 : undefined} aria-pressed={ministro === m.nome} onClick={() => { setMinistro(ministro === m.nome ? "" : m.nome); setLimite(30); }}>{m.nome}</Anchor></Table.Td>
                  <Table.Td ta="right" className="num">{numero(m.votos)}</Table.Td>
                  <Table.Td ta="right" className="num">{numero(m.relator)}</Table.Td>
                  <Table.Td ta="right" className="num">{numero(m.divergencias)}</Table.Td>
                  <Table.Td ta="right" className="num">{numero(m.com_maioria)}</Table.Td>
                  <Table.Td ta="right" className="num">{numero(m.vencido)}</Table.Td>
                  <Table.Td style={{ minWidth: 120 }}>{base > 0 && <div className="stack" role="img" aria-label={`${Math.round(pct)}% com a maioria`} title={`${Math.round(pct)}% com a maioria`}>
                    <span style={{ width: `${pct}%`, background: "var(--s1)" }} /><span style={{ width: `${100 - pct}%`, background: "var(--s2)" }} /></div>}</Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </section>
  );
  const numeros: [string, number][] = [["Julgamentos na lista", data.julgamentos.length], ["Decididos", decididos],
    ["Com divergência", data.julgamentos.filter((j) => j.placar.divergencia > 0).length]];
  return (
    <section>
      <Title order={1}>Julgamentos do STF</Title>
      <Explain>
        Como cada ministro do Supremo Tribunal Federal votou nas ações que pedem para derrubar ou manter leis e atos do
        governo, e nos recursos que viram regra para todos os casos iguais (repercussão geral), julgados pelo Plenário
        (os 11 ministros) em sessão virtual nos últimos {data.meses} meses. O relator
        apresenta o voto primeiro; cada ministro acompanha o relator ou abre uma divergência. Dados do portal do STF,
        atualizados em {dataBR(data.atualizado_em)}.
      </Explain>

      <SimpleGrid cols={3} spacing="xs" my="md">
        {numeros.map(([rotulo, n]) => (
          <Paper key={rotulo} withBorder radius="md" p="sm">
            <Text size="sm" c="dimmed">{rotulo}</Text>
            <Text fz={24} fw={700} className="num">{numero(n)}</Text>
          </Paper>
        ))}
      </SimpleGrid>

      <Detalhes itens={[
        ministros && { id: "ministros", titulo: `Como cada ministro votou (${data.ministros.length})`, conteudo: ministros },
        { id: "tipos", titulo: "O que é cada tipo de ação", conteudo: <ul className="small">{classes.map((c) => <li key={c}><strong>{c}</strong>: {data.classes[c]}</li>)}</ul> },
      ]} />

      <Title order={2} mt="lg">Julgamentos <Text span c="dimmed" size="sm">({lista.length})</Text></Title>
      <Group gap="sm" align="flex-end" wrap="wrap" my="sm">
        <TextInput id="busca-julgamento" aria-label="Buscar julgamento" value={q} onChange={(e) => setQ(e.currentTarget.value)} placeholder="Número, assunto ou quem pediu (ex.: ADI 7001)" style={{ flex: "1 1 240px" }} />
        <NativeSelect aria-label="Tipo de ação" value={classe} onChange={(e) => setClasse(e.currentTarget.value)}
          data={[{ value: "", label: "Todos os tipos" }, ...classes]} />
        <NativeSelect aria-label="Ministro" value={ministro} onChange={(e) => setMinistro(e.currentTarget.value)}
          data={[{ value: "", label: "Todos os ministros" }, ...data.ministros.map((m) => m.nome)]} />
      </Group>
      <Group gap="sm" wrap="wrap" mb="md">
        <Chip.Group multiple={false} value={sit} onChange={(k) => { setSit(k as typeof sit); setLimite(30); }}>
          <Group gap={6} role="radiogroup" aria-label="Situação">
            {([["", "Todos"], ["decidido", "Decididos"], ["aberto", "Ainda sem decisão"], ["dividido", "Com divergência"]] as const).map(([k, n]) => <Chip key={k} value={k} size="sm">{n}</Chip>)}
          </Group>
        </Chip.Group>
        {filtrado && <Button variant="subtle" size="compact-sm" onClick={() => { setQ(""); setClasse(""); setMinistro(""); setSit(""); }}>Limpar filtros ✕</Button>}
      </Group>
      {lista.length === 0 && <div className="empty">Nenhum julgamento com esses filtros.</div>}
      <Stack gap="md">{lista.slice(0, limite).map((j) => <CartaoJulgamento key={j.id} j={j} explica={data.classes[j.classe]} />)}</Stack>
      {lista.length > limite && <Button variant="default" mt="md" onClick={() => setLimite(limite + 30)}>{`Mostrar mais (${lista.length - limite} restantes)`}</Button>}

      <OndeVer links={[
        { nome: "Plenário Virtual do STF", url: "https://portal.stf.jus.br/hotsites/plenariovirtual/", explica: "pauta e placar de cada sessão" },
        { nome: "Corte Aberta (painéis do STF)", url: "https://transparencia.stf.jus.br/extensions/corte_aberta/corte_aberta.html", explica: "estatísticas oficiais de julgamentos" },
      ]} />
      <Text size="sm" c="dimmed">
        Ficam de fora as Turmas, os habeas corpus e os recursos de casos individuais: são milhares por semana e decidem a
        situação de uma pessoa, não uma lei. Os julgamentos no plenário presencial ainda não entram. <Link to="/sobre">Como funciona</Link>.
      </Text>
      <AvisosFim>
        {faltando && <p className="alert">{faltando === "parcial" ? "Parte das sessões do STF ainda não foi lida; a próxima atualização continua."
          : faltando === "reserva" ? "O portal do STF não respondeu hoje; mostramos os julgamentos já lidos antes."
            : "O portal do STF não respondeu e ainda não há julgamentos guardados."}</p>}
      </AvisosFim>
    </section>
  );
}
