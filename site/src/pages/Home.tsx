import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Barras, COR_GRUPO, Explain, Loading, useAno, useData } from "../components/ui";
import { basePeriodo, dataBR, comCadeiras, corPartido, cotaNoAno, nomePeriodo, GRUPO_CURTO, GRUPO_EXPLICA, reais, reaisCurto, type EmpresaResumo, type Grupo, type Meta, type Partido, type Resumo } from "../data";
import { GastoPartidos } from "./Partidos";
import { MG, SITE } from "../recorte";
import { SECOES } from "../menu";
import { Accordion, Alert, Anchor, Badge, Card, Group, List, Paper, SimpleGrid, Stack, Text, TextInput, Title } from "@mantine/core";
import type { CidadeResumo } from "../data";
import { AvisosFim, SelosResumo } from "../components/Selo";
import { Kpi, MapaAnos } from "../components/graficos";
import { ParaOndeVai } from "../components/ParaOndeVai";
import { FotoPolitico } from "../components/Foto";
import { EspectroPartidos } from "../components/EspectroPartidos";
import { BuscaCidade, cidadeGuardada } from "../components/BuscaCidade";

export default function Home() {
  const { data: meta, error } = useData<Meta>("meta.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const { data: emps } = useData<EmpresaResumo[]>("empresas.json");
  const { data: partidos } = useData<Partido[]>("partidos.json");
  const { data: cidades } = useData<CidadeResumo[]>(MG ? "cidades.json" : null);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const { ano } = useAno();

  const grupos = useMemo(() => {
    const g: Record<Grupo, number> = { pessoal: 0, escritorio: 0, servicos: 0 };
    pols?.forEach((p) => (Object.keys(g) as Grupo[]).forEach((k) => (g[k] += p.por_ano[ano]?.grupos[k] || 0)));
    return g;
  }, [pols, ano]);

  // Cota por estado: média por parlamentar de cada estado, ano a ano (estados com mais deputados não ganham por tamanho)
  const porUf = useMemo(() => {
    const r: Record<string, Record<string, number>> = {};
    const soma: Record<string, Record<string, [number, number]>> = {};
    pols?.forEach((p) => Object.entries(p.por_ano).forEach(([a, x]) => {
      if (!x.total) return;
      const s = ((soma[a] ||= {})[p.uf] ||= [0, 0]);
      s[0] += x.total; s[1] += 1;
    }));
    Object.entries(soma).forEach(([a, ufs]) => { r[a] = Object.fromEntries(Object.entries(ufs).map(([uf, [t, n]]) => [uf, t / n])); });
    return r;
  }, [pols]);
  if (!meta) return <Loading error={error} />;
  const serie = (o?: Record<string, number>): [string, number][] => meta.anos.map(String).filter((a) => o?.[a] != null).map((a) => [a, o![a]]);
  const serieMedia = (c: "camara" | "senado"): [string, number][] => meta.anos.map(String).filter((a) => meta.medias[a]?.[c]).map((a) => [a, meta.medias[a][c]]);
  const ufs = new Set((pols || []).map((p) => p.uf));
  const totalAno = (p: Resumo) => p.por_ano[ano]?.total || 0;
  const top = (pols || []).slice().sort((a, b) => totalAno(b) - totalAno(a)).slice(0, 8);
  const medias = meta.medias[ano] || { camara: 0, senado: 0 };
  // Ano em andamento: a seta compara com o mesmo período do ano anterior (jan até o mesmo mês), não com o ano inteiro
  const emAndamento = String(meta.mesmo_periodo?.ano) === ano;
  type P = NonNullable<Meta["mesmo_periodo"]>;
  const comPeriodo = (ant: (p: P, a: string) => number | undefined, atual: (p: P) => number | undefined) => {
    const b = basePeriodo(meta, ano, ant);
    if (b === undefined) return {};
    const v = atual(meta.mesmo_periodo!);
    return { anterior: b && { ...b, atual: v }, dica: <>{nomePeriodo(meta)} de {ano}: {reaisCurto(v || 0)}</> };
  };
  // Empresas do ano escolhido (dados antigos, sem detalhe por ano: total de todos os anos)
  const empsAno = !!emps?.some((e) => e.por_ano);
  const topEmps = (emps || []).map((e) => ({ e, v: cotaNoAno(e, ano) || { valor: e.total, n_politicos: e.n_politicos } }))
    .filter((x) => x.v.valor > 0).sort((a, b) => b.v.valor - a.v.valor).slice(0, 8);
  const resultados = q.trim().length >= 2 && pols
    ? pols.filter((p) => norm(`${p.nome} ${p.partido} ${p.uf}`).includes(norm(q))
      || (p.outros_nomes || []).some((n) => norm(n).includes(norm(q)))).slice(0, 8) : [];

  // Quem usou a cota no ano escolhido. meta.contagens.politicos conta todos da legislatura, inclusive quem saiu antes
  // do ano: em 2026 a frase dizia "os 1087 ... pediram em 2026", mas só 658 tinham nota no ano.
  const nNoAno = (pols || []).filter((p) => totalAno(p) > 0).length;
  const minhaCidade = cidadeGuardada();
  const fonte = <>Fonte: {SITE.fontes.replace(/^Dados oficiais d[ao]s? /, "")}. Atualizado em {dataBR(meta.atualizado_em)}.</>;
  // Cartões das seções: um caminho claro para cada pergunta (a última seção, "Como funciona", fica no menu e no rodapé)
  const tarefas = SECOES.filter((s) => s.id !== "sobre");
  return (
    <Stack gap="xl">
      <Stack gap="xs">
        <Title order={1}>{MG ? "O dinheiro público de Minas, fácil de entender" : "O dinheiro público, fácil de entender"}</Title>
        <Text c="dimmed" size="lg">Quanto cada político gasta, com quais empresas e como vota. Tudo com o link da fonte oficial.</Text>
      </Stack>

      <Paper withBorder p="lg" component="section" aria-labelledby="porta-titulo">
        <Stack gap="md">
          <Title order={2} id="porta-titulo">Quem representa você?</Title>
          <BuscaCidade rotulo="Sua cidade" id="busca-cidade" />
          {minhaCidade && <Anchor component={Link} to={`/quem/${minhaCidade}`} size="sm">Ver de novo a última cidade que você procurou</Anchor>}
          <form role="search" onSubmit={(e) => { e.preventDefault(); if (resultados[0]) nav(`/p/${resultados[0].id}`); }}>
            <TextInput id="busca" label={SITE.busca} size="md" value={q} onChange={(e) => setQ(e.currentTarget.value)} placeholder={SITE.buscaExemplo} autoComplete="off" />
          </form>
          {resultados.length > 0 && (
            <div className="list">{resultados.map((p) => <PessoaLinha key={p.id} p={p} />)}</div>
          )}
        </Stack>
      </Paper>

      <Paper withBorder p="lg" component="section" className="hero">
        <Stack gap={4}>
          <Text size="sm" c="dimmed">Cota parlamentar em {ano}</Text>
          <Text component="p" className="big">{reaisCurto(meta.total_por_ano?.[ano] || 0)}</Text>
          <Text>foi o que {nNoAno ? `os ${nNoAno.toLocaleString("pt-BR")}` : "os"} {SITE.quem} pediram de reembolso com dinheiro público em {ano}.{meta.custo_por_ano?.[ano] ? <> Somando salários e equipe dos gabinetes, o custo conhecido chega a <strong>{reaisCurto(meta.custo_por_ano[ano])}</strong>.</> : null}</Text>
          <Text size="xs" c="dimmed">{fonte}</Text>
        </Stack>
      </Paper>

      <section aria-labelledby="tarefas-titulo">
        <Title order={2} id="tarefas-titulo" mb="sm">O que você quer saber?</Title>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          {tarefas.map((s) => (
            <Card key={s.id} withBorder component={Link} to={s.paginas[0].rota} padding="lg">
              <Text fw={600} size="lg">{s.pergunta}</Text>
              <Group gap={6} mt="xs">{s.paginas.map((p) => <Badge key={p.rota} variant="light" color="gray">{p.nome}</Badge>)}</Group>
            </Card>
          ))}
        </SimpleGrid>
      </section>

      {/* Divulgação progressiva: os outros números da página inicial continuam aqui, um clique abaixo */}
      <section aria-labelledby="mais-titulo">
        <Title order={2} id="mais-titulo" mb="sm">Mais números de {ano}</Title>
        <Accordion variant="separated" multiple>
          <Accordion.Item value="resumo">
            <Accordion.Control>Médias e comparação com o ano anterior</Accordion.Control>
            <Accordion.Panel>
              <div className="grid">
                <Kpi rotulo={`Cota parlamentar em ${ano}`} valor={meta.total_por_ano?.[ano]} serie={serie(meta.total_por_ano)} ano={ano} dica="reembolsos com nota fiscal"
                  {...comPeriodo((p, a) => p.total[a], (p) => p.total[ano])} />
                {meta.custo_por_ano?.[ano] ? <Kpi rotulo={`Custo conhecido em ${ano}`} valor={meta.custo_por_ano[ano]} serie={serie(meta.custo_por_ano)} ano={ano} dica="cota, salários e equipe dos gabinetes"
                  anterior={emAndamento ? null : undefined} /> : null}
                {medias.camara > 0 && <Kpi rotulo="Média por deputado federal" valor={medias.camara} serie={serieMedia("camara")} ano={ano} dica={`cota em ${ano}, média de todos os deputados${MG ? " de MG" : ""} que usaram a cota no ano, inclusive suplentes que ficaram poucos meses`}
                  {...comPeriodo((p, a) => p.medias[a]?.camara, (p) => p.medias[ano]?.camara)} />}
                {medias.senado > 0 && <Kpi rotulo="Média por senador" valor={medias.senado} serie={serieMedia("senado")} ano={ano} dica={`cota em ${ano}, média de todos os senadores${MG ? " de MG" : ""} que usaram a cota no ano, inclusive suplentes`}
                  {...comPeriodo((p, a) => p.medias[a]?.senado, (p) => p.medias[ano]?.senado)} />}
              </div>
              <Text size="sm" c="dimmed" mt="sm">{emAndamento
                ? <>As setas comparam {ano} com o <strong>mesmo período</strong> de {Number(ano) - 1} ({nomePeriodo(meta)} dos dois anos), não com o ano inteiro. As notas de um mês chegam até 3 meses depois, então os últimos meses de {ano} ainda podem subir. O custo conhecido (salários e equipe) não tem o detalhe por mês e fica sem seta.</>
                : <>A seta compara com o ano anterior inteiro.</>} Troque o ano no topo da página. Média de cota por deputado federal: {reais(medias.camara)} · por senador: {reais(medias.senado)}. {fonte}</Text>
            </Accordion.Panel>
          </Accordion.Item>

          <Accordion.Item value="para-onde">
            <Accordion.Control>Para onde vai o dinheiro da cota</Accordion.Control>
            <Accordion.Panel>
              <Explain>Além do salário, cada parlamentar tem uma <strong>cota</strong> mensal para pagar despesas do mandato. Ele paga e pede reembolso apresentando a nota fiscal. Separamos esses gastos em três grupos e, dentro de cada um, pelo tipo de gasto.</Explain>
              {meta.temas_por_ano?.[ano]?.length ? <ParaOndeVai temas={meta.temas_por_ano[ano]} ano={ano} /> : <Barras rosca={{ titulo: `Cota parlamentar em ${ano}, pelos três grupos de gasto` }} itens={(Object.keys(grupos) as Grupo[]).map((g) => ({ nome: GRUPO_CURTO[g], label: <strong>{GRUPO_CURTO[g]}</strong>, nota: GRUPO_EXPLICA[g], valor: grupos[g], cor: COR_GRUPO[g] }))} />}
            </Accordion.Panel>
          </Accordion.Item>

          <Accordion.Item value="ranking">
            <Accordion.Control>Quem mais gastou e quais empresas mais receberam</Accordion.Control>
            <Accordion.Panel>
              <div className="two">
                <section>
                  <Title order={3}>Quem mais gastou em {ano}</Title>
                  <div className="list">{top.map((p) => <PessoaLinha key={p.id} p={p} extra={reaisCurto(totalAno(p))} />)}</div>
                  <Anchor component={Link} to="/politicos">Ver todos os políticos</Anchor>
                </section>
                <section>
                  <Title order={3}>{empsAno ? `Empresas que mais receberam em ${ano}` : `Empresas que mais receberam (${meta.anos[0]} a ${meta.anos[meta.anos.length - 1]})`}</Title>
                  <div className="list">
                    {topEmps.map(({ e, v }) => (
                      <Link key={e.cnpj} to={`/e/${e.cnpj}`} className="person" style={{ gridTemplateColumns: "1fr auto" }}>
                        <div style={{ minWidth: 0 }}><div className="pname">{e.nome}</div><div className="meta">paga por {v.n_politicos} parlamentar{v.n_politicos > 1 ? "es" : ""}</div></div>
                        <div className="num">{reaisCurto(v.valor)}</div>
                      </Link>
                    ))}
                    {empsAno && emps && !topEmps.length && <div className="empty">Nenhuma empresa recebeu da cota em {ano} até agora.</div>}
                  </div>
                  <Anchor component={Link} to="/empresas">Ver todas as empresas</Anchor>
                </section>
              </div>
            </Accordion.Panel>
          </Accordion.Item>

          {ufs.size > 1 && (
            <Accordion.Item value="estados">
              <Accordion.Control>Média de gasto por parlamentar em cada estado</Accordion.Control>
              <Accordion.Panel>
                <Explain>Quem mora longe de Brasília gasta mais com passagens, por isso Norte e Nordeste costumam aparecer mais escuros. Toque num estado para ver os parlamentares dele.</Explain>
                <MapaAnos porAno={porUf} anoInicial={ano} titulo="Média de cota por parlamentar, por estado" onUf={(uf) => nav(`/politicos?uf=${uf}`)} />
              </Accordion.Panel>
            </Accordion.Item>
          )}

          {partidos && pols && (
            <Accordion.Item value="partidos">
              <Accordion.Control>Partidos: onde cada um está pelos votos e quanto gasta</Accordion.Control>
              <Accordion.Panel>
                {partidos.some((p) => p.casa === "camara") && (
                  <>
                    <Explain>Cada partido da Câmara aparece no lado em que fica pelo voto dos seus deputados nas votações nominais. É o mesmo critério para todos. <Link to="/sobre">Entenda o cálculo</Link>.</Explain>
                    <EspectroPartidos partidos={comCadeiras(partidos, pols).filter((p) => p.casa === "camara")} />
                  </>
                )}
                <GastoPartidos partidos={partidos} ano={ano} limite={10} />
              </Accordion.Panel>
            </Accordion.Item>
          )}

          {MG && cidades && cidades.length > 0 && (
            <Accordion.Item value="cidades">
              <Accordion.Control>Cidades de Minas: prefeitos e dinheiro</Accordion.Control>
              <Accordion.Panel>
                <Explain>Quem foi prefeito e quais partidos tiveram vereadores desde 1997. E o dinheiro: onde a prefeitura gasta e quanto chegou por emendas.</Explain>
                <div className="grid">
                  {cidades.map((c) => (
                    <Link key={c.id} to={`/cidade/${c.id}`} className="card cidade-card">
                      <strong className="cidade-nome">{c.nome}</strong>
                      {c.prefeito && <span className="small"><i className="partido-cor" style={{ background: corPartido(c.prefeito.partido_hoje) }} />Prefeito: {c.prefeito.nome} ({c.prefeito.partido})</span>}
                    </Link>
                  ))}
                </div>
              </Accordion.Panel>
            </Accordion.Item>
          )}
        </Accordion>
      </section>

      <AvisosFim>
        {meta.avisos && meta.avisos.length > 0 && (
          <Alert color="yellow" title="Dados incompletos nesta atualização" role="note">
            Alguns sites oficiais não responderam na última coleta:
            <List size="sm" mt={4}>{meta.avisos.map((a) => <List.Item key={a}>{a}</List.Item>)}</List>
            {!MG && <Text size="sm" mt={4}>Tentamos de novo sozinhos a cada 2 horas, até todos os sites responderem.</Text>}
          </Alert>
        )}
        {!MG && <SelosResumo />}
      </AvisosFim>
    </Stack>
  );
}

export function PessoaLinha({ p, extra }: { p: Resumo; extra?: React.ReactNode }) {
  return (
    <Link to={`/p/${p.id}`} className="person">
      <FotoPolitico url={p.foto} nome={p.nome} decorativa />
      <div style={{ minWidth: 0 }}>
        <div className="pname">{p.nome}</div>
        <div className="meta">{p.cargo} · {p.partido}-{p.uf}{p.em_exercicio === false && <> · <span className="fora-cargo">fora do cargo hoje</span></>}</div>
      </div>
      <div className="num">{extra ?? reaisCurto(p.total)}</div>
    </Link>
  );
}

export const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
