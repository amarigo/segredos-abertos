import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Anchor, Badge, Group, Table, Text, TextInput, Title } from "@mantine/core";
import { Detalhes, TituloSecao } from "../components/Detalhes";
import { Explain, Loading, ResultadoChip, VotoBarra, VotoChip, VotoLegenda, useData } from "../components/ui";
import { casaNome, dataBR, descricaoCurta, linkSeguro, proposicaoNome, tipoVotacao, type Resumo, type Votacao, type VotacaoResumo } from "../data";
import { FotoPolitico } from "../components/Foto";
import { norm } from "./Home";
import { MG } from "../recorte";
import { AvisosFim, EmRevisao } from "../components/Selo";
import { Rosca, prepararFatias } from "../components/graficos";
import { COR_LADO } from "../partidos";

const LADOS = ["Esquerda", "Centro-esquerda", "Centro", "Centro-direita", "Direita"];

export default function VotacaoPage() {
  const { id = "" } = useParams();
  const { data: v, error } = useData<Votacao>(`v/${id}.json`);
  const { data: todas } = useData<VotacaoResumo[]>("votacoes.json");
  const { data: pols } = useData<Resumo[]>("politicos.json");
  const fotos = useMemo(() => new Map((pols || []).map((p) => [p.id, p.foto])), [pols]);
  const [q, setQ] = useState("");
  const votos = useMemo(() => (v?.votos || []).filter((x) => !q || norm(`${x.nome} ${x.partido} ${x.uf}`).includes(norm(q))), [v, q]);
  if (!v) return <Loading error={error} />;
  const nome = proposicaoNome(v.proposicao);
  const irmas = nome ? (todas || []).filter((x) => x.casa === v.casa && proposicaoNome(x.proposicao) === nome)
    .sort((a, b) => a.data.localeCompare(b.data) || a.id.localeCompare(b.id)) : [];
  const variosDias = new Set(irmas.map((x) => x.data)).size > 1;
  const partidos = Object.entries(v.por_partido).sort((a, b) => tot(b[1]) - tot(a[1]));
  const orient = Object.entries(v.orientacoes || {});
  const placarTxt = (x: { sim: number; nao: number }) => `Sim ${x.sim} · Não ${x.nao}`;
  const oficial = linkSeguro(v.proposicao?.url);
  const irmasTabela = (
    <section>
      <TituloSecao>Todas as votações de {nome}</TituloSecao>
      {!variosDias && <Text size="sm" c="dimmed">Todas em {dataBR(irmas[0]?.data)}.</Text>}
      <Explain>Uma proposta costuma ter várias votações: primeiro o texto principal e depois os destaques, que são trechos que um partido pede para votar separadamente. Cada linha abaixo é uma votação diferente.</Explain>
      <Table.ScrollContainer minWidth={420}>
        <Table verticalSpacing="xs">
          <Table.Thead><Table.Tr><Table.Th>O que foi votado</Table.Th><Table.Th ta="right">Sim</Table.Th><Table.Th ta="right">Não</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {irmas.map((x) => (
              <Table.Tr key={x.id} className={x.id === v.id ? "atual" : ""}>
                <Table.Td>
                  <Group gap="xs" wrap="wrap">
                    {x.id === v.id ? <strong>{tipoVotacao(x.descricao) || "Votação"} (esta)</strong> : <Link to={`/v/${x.id}`}>{tipoVotacao(x.descricao) || "Votação"}</Link>}
                    <ResultadoChip aprovada={x.aprovada} />
                  </Group>
                  <Text size="sm" c="dimmed">{variosDias && <>{dataBR(x.data)} · </>}{descricaoCurta(x.descricao).slice(0, 200)}</Text>
                </Table.Td>
                <Table.Td ta="right" className="num">{(x.placar_casa || x).sim}</Table.Td>
                <Table.Td ta="right" className="num">{(x.placar_casa || x).nao}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </section>
  );
  const porPartido = (
    <section>
      <TituloSecao>Por partido{MG && ", na Casa inteira"}</TituloSecao>
      <Table.ScrollContainer minWidth={520}>
        <Table verticalSpacing="xs">
          <Table.Thead><Table.Tr><Table.Th>Partido</Table.Th><Table.Th style={{ width: "45%" }}>Votos</Table.Th><Table.Th ta="right">Sim</Table.Th><Table.Th ta="right">Não</Table.Th><Table.Th>Orientação do partido</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {partidos.map(([sigla, c]) => (
              <Table.Tr key={sigla}>
                <Table.Td><strong>{sigla}</strong></Table.Td>
                <Table.Td><VotoBarra c={c} /></Table.Td>
                <Table.Td ta="right" className="num">{c["Sim"] || 0}</Table.Td>
                <Table.Td ta="right" className="num">{c["Não"] || 0}</Table.Td>
                <Table.Td>{orientDe(v.orientacoes, sigla) ? <VotoChip voto={orientDe(v.orientacoes, sigla)!} /> : <Text span c="dimmed">—</Text>}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {orient.length > 0 && (
        <Text size="sm" c="dimmed">Orientações de blocos: {orient.filter(([k]) => /gov|maioria|minoria|oposi/i.test(k)).map(([k, o]) => `${k}: ${o}`).join(" · ") || "—"}</Text>
      )}
    </section>
  );
  const votoDeCada = (
    <section>
      <TituloSecao>{MG ? "Voto de cada um de Minas" : "Voto de cada um"}</TituloSecao>
      <TextInput id="busca-voto" aria-label="Buscar parlamentar" value={q} onChange={(e) => setQ(e.currentTarget.value)} placeholder="Nome, partido ou estado" maw={420} mb="sm" />
      <Table.ScrollContainer minWidth={360}>
        <Table verticalSpacing={4}>
          <Table.Thead><Table.Tr><Table.Th>Parlamentar</Table.Th><Table.Th>Partido</Table.Th><Table.Th>Voto</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {votos.map((x) => (
              <Table.Tr key={x.politico}>
                <Table.Td><Link className="foto-mini" to={`/p/${x.politico}?aba=votos`}><FotoPolitico url={fotos.get(x.politico)} nome={x.nome} tamanho={28} decorativa />{x.nome}</Link></Table.Td>
                <Table.Td>{x.partido}-{x.uf}</Table.Td>
                <Table.Td><VotoChip voto={x.voto} /></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </section>
  );
  return (
    <>
      <section>
        <Text size="sm" c="dimmed">{casaNome(v.casa)} · {dataBR(v.data)}</Text>
        <Title order={1}>{proposicaoNome(v.proposicao) || "Votação"}{tipoVotacao(v.descricao) && <span className="h1-sub">{tipoVotacao(v.descricao)}</span>}</Title>
        {descricaoCurta(v.descricao) && <Text size="lg" mt="xs"><strong>O que foi votado:</strong> {descricaoCurta(v.descricao)}</Text>}
        {v.proposicao?.ementa && <Text c="dimmed" mt="xs"><strong>Sobre a proposta:</strong> {v.proposicao.ementa}</Text>}
        <Group gap="xs" wrap="wrap" mt="sm">
          <ResultadoChip aprovada={v.aprovada} />
          {v.placar_casa && MG
            ? <><Badge variant="light" color="gray" tt="none" size="lg">{casaNome(v.casa)}: {placarTxt(v.placar_casa)}</Badge><Badge variant="light" color="gray" tt="none" size="lg">Bancada de MG: {placarTxt(v)}</Badge></>
            : v.placar_casa
              ? <Badge variant="light" color="gray" tt="none" size="lg">Placar oficial: {placarTxt(v.placar_casa)}</Badge>
              : <Badge variant="light" color="gray" tt="none" size="lg">{placarTxt(v)}</Badge>}
        </Group>
        <Group gap="xs" wrap="wrap" mt="xs">
          {oficial && <Anchor size="sm" href={oficial} target="_blank" rel="noreferrer">Ver a proposta e as votações no site {v.casa === "camara" ? "da Câmara" : "do Senado"} ↗</Anchor>}
          {v.temas?.map((t) => <Badge key={t} component={Link} to={`/votacoes/ja-votadas?tema=${encodeURIComponent(t)}`} variant="outline" color="gray" tt="none" style={{ cursor: "pointer" }}>{t}</Badge>)}
        </Group>
      </section>

      {v.por_partido_mg && Object.keys(v.por_partido_mg).length > 0 && (
        <section>
          <Title order={2}>Como votou a bancada de Minas Gerais</Title>
          <VotoLegenda />
          <div className="bars">
            {Object.entries(v.por_partido_mg).sort((a, b) => tot(b[1]) - tot(a[1])).map(([sigla, c]) => (
              <div key={sigla} className="bar-row" style={{ gridTemplateColumns: "150px 1fr" }}>
                <span><strong>{sigla}</strong> <Text span size="sm" c="dimmed">{c["Sim"] || 0} Sim · {c["Não"] || 0} Não</Text></span><VotoBarra c={c} />
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <Title order={2}>Por tendência (esquerda e direita){MG && ", na Casa inteira"}</Title>
        <Explain>Agrupamos os parlamentares pela posição calculada a partir de todos os seus votos.</Explain>
        <VotoLegenda />
        <div className="bars">
          {LADOS.filter((l) => v.por_lado[l]).map((l) => (
            <div key={l} className="bar-row" style={{ gridTemplateColumns: "150px 1fr" }}>
              <span>{l}</span><VotoBarra c={v.por_lado[l]} />
            </div>
          ))}
        </div>
      </section>

      <Detalhes itens={[
        { id: "partidos", titulo: `Por partido${MG ? ", na Casa inteira" : ""}, com a orientação de cada um`, conteudo: porPartido },
        { id: "votos", titulo: `${MG ? "Voto de cada um de Minas" : "Voto de cada um"} (${v.votos.length})`, conteudo: votoDeCada },
        Object.values(v.contagem || {}).some((n) => n > 0) && { id: "graficos", titulo: "O placar em gráficos", conteudo: <PlacarGraficos v={v} /> },
        irmas.length > 1 && { id: "todas", titulo: `Todas as votações de ${nome} (${irmas.length})`, conteudo: irmasTabela },
      ]} />
      {linkSeguro(v.fonte) && <p className="muted small">Para programadores: <a href={linkSeguro(v.fonte)} target="_blank" rel="noreferrer">dados brutos desta votação</a> (formato para computador).</p>}
      <AvisosFim secao="votacoes">
        {v.placar_casa?.fonte === "ata" && v.placar_casa.painel &&
          <p className="small muted" role="note" data-testid="placar-ata">O placar oficial é o da ata da sessão (Sim {v.placar_casa.sim} · Não {v.placar_casa.nao}). O painel eletrônico registrou Sim {v.placar_casa.painel.sim} · Não {v.placar_casa.painel.nao}: algum voto foi corrigido depois da votação. <Link to="/verificacao#motivo-senado_painel_ata">Por quê</Link>.</p>}
        {!MG && v.placar_casa && (v.placar_casa.sim !== v.sim || v.placar_casa.nao !== v.nao) &&
          <p className="small muted">A lista de votos mostra só quem está no mandato hoje (Sim {v.sim} · Não {v.nao}). A diferença para o placar oficial são votos de {v.casa === "camara" ? "deputados" : "senadores"} que saíram do cargo depois desta votação{v.placar_casa.fonte === "ata" ? " ou correções registradas na ata" : ""}.</p>}
        <EmRevisao campo="votacao" valor={v.id} />
      </AvisosFim>
    </>
  );
}

const tot = (c: Record<string, number>) => Object.values(c).reduce((a, b) => a + b, 0);
function orientDe(o: Record<string, string>, sigla: string): string | undefined {
  const k = Object.keys(o || {}).find((k) => k.toUpperCase() === sigla.toUpperCase() || k.toUpperCase().split(/[^A-Z]/).includes(sigla.toUpperCase()));
  return k ? o[k] : undefined;
}

/* Placar em rosca e de que lado vieram os votos Sim e os votos Não */
function PlacarGraficos({ v }: { v: Votacao }) {
  const fmt = (n: number) => `${n} voto${n === 1 ? "" : "s"}`;
  const c = v.contagem || {};
  const outros = Object.entries(c).filter(([k]) => k !== "Sim" && k !== "Não").reduce((a, [, n]) => a + n, 0);
  const placar = prepararFatias([{ nome: "Sim", valor: c["Sim"] || 0, cor: "var(--sim)" }, { nome: "Não", valor: c["Não"] || 0, cor: "var(--nao)" },
    { nome: "Abstenção, obstrução ou ausência", valor: outros, cor: "var(--outro)" }]);
  const deLado = (voto: string) => prepararFatias(LADOS.map((l) => ({ nome: l, valor: v.por_lado[l]?.[voto] || 0, cor: COR_LADO[l] })), 9);
  const sim = deLado("Sim"), nao = deLado("Não");
  if (!placar.length) return null;
  return (
    <section>
      <TituloSecao>O placar em gráficos</TituloSecao>
      <p className="small muted">{MG ? "Como votou a bancada de Minas Gerais. Ao lado, na Casa inteira," : "Votos registrados de quem está no mandato hoje. Ao lado,"} de que lado (esquerda a direita, pelos votos de cada um) vieram os votos Sim e os votos Não.</p>
      <div className="secao-graficos">
        <div><h3 className="graf-titulo">{MG ? "Como votou a bancada de MG" : "Como votaram"}</h3><Rosca fatias={placar} titulo="Placar da votação" formato={fmt} centroRotulo="Votos" centro={String(placar.reduce((a, f) => a + f.valor, 0))} /></div>
        {sim.length > 0 && <div><h3 className="graf-titulo">De onde vieram os Sim</h3><Rosca fatias={sim} titulo="Votos Sim por lado" formato={fmt} centroRotulo="Sim" centro={String(c["Sim"] || 0)} /></div>}
        {nao.length > 0 && <div><h3 className="graf-titulo">De onde vieram os Não</h3><Rosca fatias={nao} titulo="Votos Não por lado" formato={fmt} centroRotulo="Não" centro={String(c["Não"] || 0)} /></div>}
      </div>
    </section>
  );
}
