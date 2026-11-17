import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, Chip, Group, NativeSelect, Table, Text, TextInput, Title } from "@mantine/core";
import { Colunas, Explain, Loading, OndeVer, ResultadoChip, useData } from "../components/ui";
import { MESES_LONGOS, TEMAS, nomeTipo, casaNome, dataBR, descricaoCurta, proposicaoNome, tipoVotacao, type VotacaoResumo } from "../data";
import { norm } from "./Home";
import { MG } from "../recorte";
import { AvisosFim } from "../components/Selo";
import { ColunasAnos, Rosca, numero, prepararFatias } from "../components/graficos";
import { Detalhes } from "../components/Detalhes";

export default function Votacoes() {
  const { data, error } = useData<VotacaoResumo[]>("votacoes.json");
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [tipo, setTipo] = useState("");
  const [mes, setMes] = useState("");
  const [resultado, setResultado] = useState<"" | "sim" | "nao">("");
  const [mostrar, setMostrar] = useState(200);
  const [params, setParams] = useSearchParams();
  const tema = params.get("tema") || "";
  const setTema = (t: string) => setParams(t ? { tema: t } : {}, { replace: true });
  const contTema = useMemo(() => { const c: Record<string, number> = {}; (data || []).forEach((v) => v.temas?.forEach((t) => (c[t] = (c[t] || 0) + 1))); return c; }, [data]);
  const tipos = useMemo(() => [...new Set((data || []).map((v) => v.proposicao?.sigla).filter(Boolean) as string[])].sort(), [data]);
  const meses = useMemo(() => [...new Set((data || []).map((v) => (v.data || "").slice(0, 7)).filter((m) => m.length === 7))].sort().reverse(), [data]);
  const lista = useMemo(() => (data || []).filter((v) => (!casa || v.casa === casa) && (!tipo || v.proposicao?.sigla === tipo) && (!tema || !!v.temas?.includes(tema))
    && (!mes || (mes.length === 4 ? v.data?.startsWith(mes) : v.data?.slice(0, 7) === mes))
    && (!resultado || (resultado === "sim") === !!v.aprovada)
    && (!q || norm(`${proposicaoNome(v.proposicao)} ${v.proposicao?.ementa || ""} ${v.descricao}`).includes(norm(q)))), [data, q, casa, tipo, tema, mes, resultado]);
  const filtrado = !!(q || casa || tipo || tema || mes || resultado);
  const graf = useMemo(() => {
    const ap = lista.filter((v) => v.aprovada).length;
    const tipos: Record<string, number> = {};
    const anos: Record<string, number> = {};
    lista.forEach((v) => { const t = v.proposicao?.sigla || "Outras"; tipos[t] = (tipos[t] || 0) + 1; const a = v.data.slice(0, 4); if (a) anos[a] = (anos[a] || 0) + 1; });
    return {
      resultado: prepararFatias([{ nome: "Aprovadas", valor: ap, cor: "var(--sim)" }, { nome: "Rejeitadas", valor: lista.length - ap, cor: "var(--nao)" }]),
      tipos: prepararFatias(Object.entries(tipos).sort((a, b) => b[1] - a[1]).map(([nome, valor]) => ({ nome, valor })), 6),
      anos: Object.entries(anos).sort() as [string, number][],
    };
  }, [lista]);
  const porMes = useMemo(() => {
    const m: Record<string, number[]> = {};
    lista.forEach((v) => { const k = (v.data || "").slice(0, 7); if (k.length === 7) { const x = (m[k] ||= [0, 0]); x[v.aprovada ? 0 : 1] += 1; } });
    return Object.keys(m).sort().slice(-12).map((k) => ({ label: `${k.slice(5)}/${k.slice(2, 4)}`, valores: m[k] }));
  }, [lista]);
  if (!data) return <Loading error={error} />;
  const fmtN = (v: number) => `${numero(v)} votaç${v === 1 ? "ão" : "ões"}`;
  const anos = [...new Set(meses.map((m) => m.slice(0, 4)))];
  const placar = (v: VotacaoResumo) => v.placar_casa || v;
  return (
    <section>
      <Title order={1}>Votações</Title>
      <Explain>Votações nominais do plenário, em que cada parlamentar registra o próprio voto.{MG ? " Sim e Não mostram o placar da Casa inteira; ao lado, como votou a bancada de Minas Gerais." : " Sim e Não mostram o placar oficial da Casa inteira."} PEC é proposta de emenda à Constituição, PL é projeto de lei, MPV é medida provisória e PLP é projeto de lei complementar.</Explain>
      <Group gap="sm" align="flex-end" wrap="wrap" my="md">
        <TextInput id="busca-votacao" aria-label="Buscar votação" value={q} onChange={(e) => setQ(e.currentTarget.value)} placeholder="Assunto ou número (ex.: PEC 45)" style={{ flex: "1 1 240px" }} />
        <NativeSelect id="filtro-casa-v" aria-label="Casa" value={casa} onChange={(e) => setCasa(e.currentTarget.value)}
          data={[{ value: "", label: "Câmara e Senado" }, { value: "camara", label: "Câmara" }, { value: "senado", label: "Senado" }]} />
        <NativeSelect id="filtro-tipo" aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.currentTarget.value)}
          data={[{ value: "", label: "Todos os tipos" }, ...tipos.map((t) => ({ value: t, label: nomeTipo(t) }))]} />
        <NativeSelect id="filtro-mes" aria-label="Mês" value={mes} onChange={(e) => { setMes(e.currentTarget.value); setMostrar(200); }}
          data={[{ value: "", label: "Todos os meses" }, ...anos.map((a) => ({ group: a, items: [{ value: a, label: `Todo o ano de ${a}` },
            ...meses.filter((m) => m.startsWith(a)).map((m) => ({ value: m, label: `${MESES_LONGOS[Number(m.slice(5)) - 1]} de ${a}` }))] }))]} />
      </Group>
      <Group gap="sm" wrap="wrap" mb="sm">
        <Chip.Group multiple={false} value={resultado} onChange={(k) => { setResultado(k as "" | "sim" | "nao"); setMostrar(200); }}>
          <Group gap={6} role="radiogroup" aria-label="Resultado">
            {([["", "Todas"], ["sim", "Aprovadas (Sim venceu)"], ["nao", "Rejeitadas (Não venceu)"]] as const).map(([k, n]) => <Chip key={k} value={k} size="sm">{n}</Chip>)}
          </Group>
        </Chip.Group>
        {filtrado && <Button variant="subtle" size="compact-sm" onClick={() => { setQ(""); setCasa(""); setTipo(""); setTema(""); setMes(""); setResultado(""); }}>Limpar filtros ✕</Button>}
      </Group>
      <Chip.Group multiple={false} value={tema} onChange={(t) => setTema(t)}>
        <Group gap={6} role="group" aria-label="Temas" mb="xs">
          <Chip value="" size="sm" variant="outline">Todos os temas</Chip>
          {TEMAS.filter((t) => contTema[t]).map((t) => <Chip key={t} value={t} size="sm" variant="outline">{`${t} (${contTema[t]})`}</Chip>)}
        </Group>
      </Chip.Group>
      <Text size="sm" c="dimmed">{lista.length} votações{tema ? ` sobre ${tema.toLowerCase()}` : ""}. Os temas são definidos por palavras da ementa. <Link to="/sobre">Entenda</Link>. Para o que ainda vai ser votado, veja <Link to="/votacoes">projetos em andamento</Link>.</Text>
      {lista.length > 0 && <Detalhes itens={[{
        id: "graficos", titulo: "Resultado em gráficos: aprovadas, tipos e votações por ano e por mês",
        conteudo: <>
          <div className="secao-graficos">
            <div><Title order={3} size="h5" className="graf-titulo">Resultado</Title><Rosca fatias={graf.resultado} titulo="Votações aprovadas e rejeitadas" formato={fmtN} centroRotulo="Votações" centro={numero(lista.length)} /></div>
            <div><Title order={3} size="h5" className="graf-titulo">O que foi votado</Title><Rosca fatias={graf.tipos} titulo="Votações por tipo de proposta" formato={fmtN} centroRotulo="Votações" centro={numero(lista.length)} /></div>
            {graf.anos.length > 1 && <div><Title order={3} size="h5" className="graf-titulo">Votações por ano</Title><ColunasAnos serie={graf.anos} titulo="Votações nominais por ano" formato={numero} /></div>}
          </div>
          {porMes.length > 1 && <>
            <Title order={3} size="h5" className="graf-titulo">Votações por mês</Title>
            <Colunas rotulo="Votações por mês, aprovadas e rejeitadas" fmt={(v) => v.toLocaleString("pt-BR")}
              partes={[{ nome: "Aprovadas", cor: "var(--sim)" }, { nome: "Rejeitadas", cor: "var(--nao)" }]} itens={porMes} />
          </>}
        </>,
      }]} />}
      <Table.ScrollContainer minWidth={560} mt="md">
        <Table striped highlightOnHover verticalSpacing="xs">
          <Table.Thead><Table.Tr><Table.Th>Data</Table.Th><Table.Th>Casa</Table.Th><Table.Th>O que foi votado</Table.Th><Table.Th ta="right">Sim</Table.Th><Table.Th ta="right">Não</Table.Th>{MG && <Table.Th>Bancada de MG</Table.Th>}<Table.Th>Resultado</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {lista.slice(0, mostrar).map((v) => (
              <Table.Tr key={v.id}>
                <Table.Td className="num">{dataBR(v.data)}</Table.Td>
                <Table.Td>{casaNome(v.casa)}</Table.Td>
                <Table.Td><Link to={`/v/${v.id}`}>{proposicaoNome(v.proposicao) || "Votação"}</Link>{tipoVotacao(v.descricao) && <> <span className="chip">{tipoVotacao(v.descricao)}</span></>}
                  {descricaoCurta(v.descricao) && <Text size="sm">{descricaoCurta(v.descricao).slice(0, 220)}</Text>}
                  {v.proposicao?.ementa && <Text size="sm" c="dimmed">{v.proposicao.ementa.slice(0, 160)}</Text>}
                  {v.temas && v.temas.length > 0 && <Text size="sm" mt={2}>{v.temas.join(" · ")}</Text>}</Table.Td>
                <Table.Td ta="right" className="num">{placar(v).sim}</Table.Td>
                <Table.Td ta="right" className="num">{placar(v).nao}</Table.Td>
                {MG && <Table.Td className="small num" style={{ whiteSpace: "nowrap" }}>{v.sim} Sim · {v.nao} Não</Table.Td>}
                <Table.Td><ResultadoChip aprovada={v.aprovada} /></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {lista.length > mostrar && (
        <Group gap="sm" my="sm"><Text size="sm" className="filtros-conta">{`Mostrando ${numero(mostrar)} de ${numero(lista.length)} votações.`}</Text>
          <Button variant="default" size="xs" onClick={() => setMostrar((m) => m + 200)}>Mostrar mais 200</Button>
          <Button variant="subtle" size="xs" onClick={() => setMostrar(lista.length)}>Mostrar todas</Button></Group>
      )}
      <OndeVer links={[
        { nome: "Votações na Câmara (dados abertos)", url: "https://dadosabertos.camara.leg.br/swagger/api.html#/Vota%C3%A7%C3%B5es/votos", explica: "o voto de cada deputado" },
        { nome: "Votações no Senado (dados abertos)", url: "https://legis.senado.leg.br/dadosabertos/docs/", explica: "o voto de cada senador" },
      ]} />
      <AvisosFim secao="votacoes" />
    </section>
  );
}
