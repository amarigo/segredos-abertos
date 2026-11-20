/* Tema do Mantine com o visual da Eleição 2026 (eleicao2026/site/corpo.html, bloco "Visual do Segredos Abertos"), para
   os sites ficarem com a mesma cara: padrão de site público brasileiro (gov.br), azul gov.br nos links e botões,
   faixa azul-escura no topo com fio verde e amarelo, botões em pílula e letra Raleway com números alinhados.
   Só muda as cores, a letra e os cantos; os componentes continuam os do Mantine. As cores das séries dos gráficos,
   dos votos e do mapa continuam em styles.css. */
import { createTheme, type CSSVariablesResolver, type MantineColorsTuple } from "@mantine/core";

/* azul gov.br: o 6 é o azul dos links e botões no claro (#1351B4), o 4 é o do escuro (#7FB0FF), o 8 é a faixa (#071D41) */
const gov: MantineColorsTuple = [
  "#EDF5FF", "#D4E5FF", "#B5D3FF", "#99C1FF", "#7FB0FF", "#4A88E6", "#1351B4", "#0C3F8F", "#071D41", "#04132E",
];

/* fundo escuro azulado da Eleição 2026: no Mantine, 0 é o texto, 2 o texto apagado, 4 a borda, 6 os campos e 7 o fundo */
const dark: MantineColorsTuple = [
  "#EEF2F8", "#C9D2E0", "#A9B4C6", "#6B7890", "#26324A", "#1F2B40", "#16233B", "#0B1220", "#08101C", "#050A14",
];

export const tema = createTheme({
  primaryColor: "gov",
  primaryShade: { light: 6, dark: 4 },
  autoContrast: true,
  colors: { gov, dark },
  fontFamily: 'Raleway, Rawline, system-ui, -apple-system, "Segoe UI", sans-serif',
  headings: { fontFamily: 'Raleway, Rawline, system-ui, sans-serif', fontWeight: "800" },
  defaultRadius: "md",
  components: {
    Button: { defaultProps: { radius: "xl" } },
    Badge: { defaultProps: { radius: "xl" } },
    SegmentedControl: { defaultProps: { radius: "xl" } },
  },
});

/* Fundo, texto e borda do claro iguais aos da Eleição 2026; faixa do topo e seção ativa do menu */
export const variaveis: CSSVariablesResolver = () => ({
  variables: {},
  light: {
    "--mantine-color-body": "#F8F8F8",
    "--mantine-color-text": "#1B2533",
    "--mantine-color-dimmed": "#4F5B6B",
    "--mantine-color-default-border": "#DCDFE5",
    "--sa-faixa": "#071D41",
    "--sa-faixa-2": "#04132E",
    "--sa-ativo": "#071D41",
    "--sa-ativo-texto": "#FFFFFF",
    "--sa-verde": "#168821",
    "--sa-amarelo": "#FFCD07",
  },
  dark: {
    "--sa-faixa": "#13284F",
    "--sa-faixa-2": "#04112A",
    "--sa-ativo": "#7FB0FF",
    "--sa-ativo-texto": "#0B1220",
    "--sa-verde": "#36C35A",
    "--sa-amarelo": "#FFCD07",
  },
});
