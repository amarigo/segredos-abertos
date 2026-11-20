import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import App from "./App";
import { ESTILO_ELEICAO, tema, variaveis } from "./tema";
/* Mantine primeiro; o styles.css antigo só cuida do miolo das páginas que ainda não migraram. O tema é o padrão no
   nacional e o do Eleição 2026 no Minas Nossa (tema.ts e tema-eleicao.css). */
import "@mantine/core/styles.css";
import "./styles.css";
import "./tema-eleicao.css";

if (ESTILO_ELEICAO) document.documentElement.dataset.estilo = "eleicao";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider defaultColorScheme="auto" theme={tema} cssVariablesResolver={variaveis}>
      <HashRouter>
        <App />
      </HashRouter>
    </MantineProvider>
  </React.StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
