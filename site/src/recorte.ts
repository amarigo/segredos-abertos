/* Qual site está sendo montado: o Segredos Abertos nacional ou o Minas Nossa (vite build --mode mg).
   O código é o mesmo; mudam os dados (public-mg/data), alguns textos e o menu. */
export const MG = import.meta.env.VITE_RECORTE === "mg";

export const SITE = MG
  ? {
    nome: "Minas", destaque: "Nossa", titulo: "Minas Nossa",
    quem: "deputados federais e senadores de Minas Gerais",
    busca: "Procure seu deputado federal ou senador de Minas",
    buscaExemplo: "Nome ou partido (ex.: PT)",
    fontes: "Dados oficiais da Câmara dos Deputados, do Senado Federal, do TSE, da Receita Federal e do Portal da Transparência",
    nacional: "https://amarigo.github.io/segredos-abertos/",
  }
  : {
    nome: "Segredos Abertos", destaque: "Brasil", titulo: "Segredos Abertos Brasil",
    quem: "deputados federais e senadores em exercício",
    busca: "Procure seu deputado ou senador",
    buscaExemplo: "Nome, partido ou estado (ex.: SP)",
    fontes: "Dados oficiais da Câmara dos Deputados, do Senado Federal, da Receita Federal e do Portal da Transparência",
    nacional: "",
  };
