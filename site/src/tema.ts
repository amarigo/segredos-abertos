/* Tema do Mantine de cada site. O Segredos Abertos nacional usa o tema padrão, sem mudança.
   O Minas Nossa usa o estilo do Eleição 2026 (eleicao2026/site/corpo.html, "Cores do Brasil"): fundo de papel,
   tinta verde-escura, títulos com serifa e as cores da bandeira na moldura. As mesmas cores, letras e réguas,
   passadas para o tema do Mantine; o que o tema não alcança (faixa do topo, abas sublinhadas, blocos sem caixa)
   fica em tema-eleicao.css. Só a aparência muda: dados, textos e fontes são os mesmos. */
import { createTheme, type CSSVariablesResolver, type MantineColorsTuple } from "@mantine/core";
import { MG } from "./recorte";

/* Verde da bandeira, do mais claro ao mais escuro: 7 é o verde da faixa (#009C3B), 9 a tinta (#00672A) */
const bandeira: MantineColorsTuple = [
  "#e6f7ec", "#cdeed8", "#9cdcb2", "#67ca89", "#3dbb67", "#22b152", "#0ea646", "#009c3b", "#008433", "#00672a",
];

/* Tema escuro do Eleição 2026: tons de verde quase preto em vez do cinza-azulado padrão.
   Mesma ordem do Mantine: 0 texto, 2 texto apagado, 4 linhas, 5 fundo ao passar o mouse, 6 campos, 7 fundo. */
const escuro: MantineColorsTuple = [
  "#eaf1ec", "#c9d3cc", "#a3b0a7", "#7c8a81", "#2c3a31", "#223028", "#16241b", "#0e1611", "#0a110d", "#060b08",
];

export const ESTILO_ELEICAO = MG;

export const tema = ESTILO_ELEICAO
  ? createTheme({
    primaryColor: "bandeira",
    primaryShade: { light: 9, dark: 4 },
    colors: { bandeira, dark: escuro },
    fontFamily: '"Atkinson Hyperlegible", Verdana, "Segoe UI", sans-serif',
    headings: { fontFamily: '"Source Serif 4", Georgia, "Times New Roman", serif', fontWeight: "800" },
    defaultRadius: "sm",
    autoContrast: true,
  })
  : createTheme({});

/* Fundo de papel, tinta e linhas do Eleição 2026 no tema claro (o escuro já vem da paleta acima) */
const PAPEL: Record<string, string> = {
  "--mantine-color-body": "#f6f8f3",
  "--mantine-color-text": "#13211a",
  "--mantine-color-dimmed": "#4d5a52",
  "--mantine-color-default-border": "#d2dcd3",
  "--mantine-color-default-hover": "#e6f0e7",
};
export const variaveis: CSSVariablesResolver = () => ({ variables: {}, light: ESTILO_ELEICAO ? PAPEL : {}, dark: {} });
