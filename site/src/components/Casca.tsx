/* Casca do site (topo, menu, abas da seção, rodapé), com os componentes do Mantine e o visual da Eleição 2026
   (tema.ts): faixa azul-escura no topo com fio verde e amarelo, seções em pílula logo abaixo.
   Menos é mais: o topo tem só a marca, o ano e cinco seções; as páginas de cada seção aparecem como abas quando a
   pessoa entra nela. Regra dos menus (vale para todos os sites): todas as abas sempre à vista. Se não couberem numa
   linha, quebram para a de baixo; nunca rolam de lado nem ficam cortadas (conferido por e2e/menu.ts). */
import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Affix, Anchor, Box, Button, Container, Divider, Group, NativeSelect, Stack, Tabs, Text } from "@mantine/core";
import { MG, SITE } from "../recorte";
import { SECOES, paginaDe } from "../menu";
import { useAno } from "./ui";

/* Os projetos do Segredos Abertos, publicados lado a lado no mesmo site (/, /mg/, /eleicao2026/ e /terras-raras/).
   Links relativos: funcionam no GitHub Pages e numa cópia local de site/dist. */
const PROJETOS = [
  { id: "brasil", nome: "Brasil", href: MG ? "../" : "./" },
  { id: "mg", nome: "Minas Nossa", href: MG ? "./" : "mg/" },
  { id: "eleicao", nome: "Eleição 2026", href: MG ? "../eleicao2026/" : "eleicao2026/" },
  { id: "terras", nome: "Terras Raras MG", href: MG ? "../terras-raras/" : "terras-raras/" },
];

/* Seletor de língua. A tradução é feita por public/i18n/tradutor.js (carregado no index.html), que troca os textos
   da página pelos do dicionário. Os links levam ao mesmo endereço com ?lang=en ou ?lang=es (o português fica sem). */
const LINGUAS = [
  { id: "pt", sigla: "PT", nome: "Português", lang: "pt-BR" },
  { id: "en", sigla: "EN", nome: "English", lang: "en" },
  { id: "es", sigla: "ES", nome: "Español", lang: "es" },
];

function Linguas() {
  const i18n = window.SA_I18N;
  const atual = i18n?.lingua || "pt";
  return (
    <Group gap={0} wrap="nowrap" className="linguas" translate="no" role="group" aria-label={atual === "en" ? "Language" : "Idioma"}>
      {LINGUAS.map((l) => (
        <Button key={l.id} component="a" size="compact-xs" variant={l.id === atual ? "white" : "subtle"} color={l.id === atual ? "gov.8" : "gray.0"}
          href={i18n ? i18n.endereco(l.id) : "#"} lang={l.lang} hrefLang={l.lang} title={l.nome}
          aria-current={l.id === atual ? "true" : undefined}
          onClick={(e: React.MouseEvent) => { if (i18n) { e.preventDefault(); i18n.trocar(l.id); } }}>{l.sigla}</Button>
      ))}
    </Group>
  );
}

function Projetos() {
  const atual = MG ? "mg" : "brasil";
  return (
    <Box className="projetos-faixa">
      <Container size="lg">
        <Group component="nav" className="projetos" aria-label="Projetos do Segredos Abertos" gap={0} style={{ columnGap: 16 }} wrap="wrap">
          <Text span size="xs" tt="uppercase" fw={600} lts="0.06em" c="#B7C3D9">Projetos:</Text>
          {PROJETOS.map((p) => (
            <Anchor key={p.id} href={p.href} size="xs" tt="uppercase" fw={p.id === atual ? 700 : 600} lts="0.06em" py={8}
              c={p.id === atual ? "var(--sa-amarelo)" : "#E3E9F4"} aria-current={p.id === atual ? "page" : undefined}>{p.nome}</Anchor>
          ))}
        </Group>
      </Container>
    </Box>
  );
}

/* O ano vale para as páginas da cota e das votações. Páginas com os próprios anos (ou sem ano) não mostram o
   seletor: ele só confundiria. */
const SEM_ANO = ["/dinheiro", "/licitacoes", "/corrupcao", "/votacoes/tribunais", "/painel", "/cultura", "/quem", "/sobre", "/verificacao", "/rede"];

export function AnoSeletor() {
  const { ano, anos, setAno } = useAno();
  const { pathname } = useLocation();
  if (!anos.length || SEM_ANO.some((r) => pathname === r || pathname.startsWith(`${r}/`))) return null;
  return (
    <NativeSelect id="ano" aria-label="Ano" size="xs" w={76} value={ano} onChange={(e) => setAno(e.currentTarget.value)}
      data={anos.slice().reverse()} />
  );
}

/** Título da aba do navegador: "<Página> | <Site>". Vale para marcadores, histórico, compartilhamento e para o
 *  formulário de aviso de erro, que usa o título da página como assunto. Na página inicial fica o título do index.html. */
export function useTituloDaPagina() {
  const { pathname } = useLocation();
  const nome = paginaDe(pathname)?.pagina.nome;
  useEffect(() => {
    const padrao = document.title;
    if (nome) document.title = `${nome} | ${SITE.titulo}`;
    return () => { document.title = padrao; };
  }, [nome]);
}

export function Topo() {
  const { pathname } = useLocation();
  const aqui = paginaDe(pathname);
  useTituloDaPagina();
  return (
    <Box component="header" className="top">
      <Projetos />
      <Box className="faixa" c="white">
        <Container size="lg">
          <Group justify="space-between" gap="sm" py="md" wrap="nowrap">
            <Anchor component={Link} to="/" className="brand" underline="never" c="inherit">
              <Group gap={10} wrap="nowrap">
                <img src="./icon.svg" alt="" width={32} height={32} />
                <Text fw={900} fz={{ base: "lg", sm: 28 }} lh={1.1} component="span">{SITE.titulo}</Text>
              </Group>
            </Anchor>
            <Group gap="xs" wrap="nowrap">
              <AnoSeletor />
              <Linguas />
            </Group>
          </Group>
        </Container>
      </Box>
      <Container size="lg">
        <Group component="nav" className="nav" aria-label="Principal" gap={6} wrap="wrap" py="sm">
          {SECOES.map((s) => {
            const ativa = aqui?.secao.id === s.id;
            return (
              <Button key={s.id} component={NavLink} to={s.paginas[0].rota} variant="subtle" color="gray" c={ativa ? undefined : "dimmed"}
                className={ativa ? "active" : undefined} aria-current={ativa ? "page" : undefined}>{s.nome}</Button>
            );
          })}
        </Group>
      </Container>
      <Divider />
    </Box>
  );
}

/** As páginas da seção aberta, como abas. Só aparece quando a seção tem mais de uma página. */
export function AbasDaSecao() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const aqui = paginaDe(pathname);
  if (!aqui || aqui.secao.paginas.length < 2) return null;
  return (
    <Tabs value={aqui.pagina.rota} onChange={(v) => v && nav(v)} className="abas-secao" aria-label={aqui.secao.nome}>
      <Tabs.List>
        {aqui.secao.paginas.map((p) => <Tabs.Tab key={p.rota} value={p.rota}>{p.nome}</Tabs.Tab>)}
      </Tabs.List>
    </Tabs>
  );
}

export function Rodape({ atualizado }: { atualizado?: string }) {
  return (
    <Box component="footer" mt="xl">
      <Divider />
      <Container size="lg" py="xl">
        <Stack gap={6}>
          <Text size="sm" c="dimmed">{SITE.fontes}{atualizado ? `, atualizados em ${atualizado}` : ""}.</Text>
          {MG && <Text size="sm" c="dimmed">O Minas Nossa é a parte de Minas Gerais do <Anchor href={SITE.nacional} inherit>Segredos Abertos Brasil</Anchor>.</Text>}
          {!MG && <Text size="sm" c="dimmed"><Anchor component={Link} to="/verificacao" inherit>Como conferimos os números</Anchor>.</Text>}
          <Text size="sm" c="dimmed">Projeto independente e sem fins lucrativos. Código aberto em <Anchor href="https://github.com/amarigo/segredos-abertos" inherit>GitHub</Anchor>.</Text>
        </Stack>
      </Container>
    </Box>
  );
}

/** Botão "Menu" que aparece depois de rolar uma página longa, para voltar ao topo sem rolar tudo. */
export function VoltarAoMenu() {
  const [ver, setVer] = useState(false);
  useEffect(() => {
    const olhar = () => setVer(window.scrollY > window.innerHeight * 1.5);
    olhar();
    window.addEventListener("scroll", olhar, { passive: true });
    return () => window.removeEventListener("scroll", olhar);
  }, []);
  if (!ver) return null;
  return (
    <Affix position={{ bottom: 20, right: 20 }}>
      <Button className="voltar-menu" onClick={() => {
        const suave = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.scrollTo({ top: 0, behavior: suave ? "smooth" : "auto" });
        document.querySelector<HTMLElement>(".top .nav a")?.focus({ preventScroll: true });
      }}>↑ Menu</Button>
    </Affix>
  );
}
