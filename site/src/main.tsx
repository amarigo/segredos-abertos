import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import App from "./App";
import { tema, variaveis } from "./tema";
/* Mantine primeiro, com o tema da Eleição 2026 (tema.ts); o styles.css antigo só cuida do miolo das páginas que ainda não migraram */
import "@mantine/core/styles.css";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider theme={tema} cssVariablesResolver={variaveis} defaultColorScheme="auto">
      <HashRouter>
        <App />
      </HashRouter>
    </MantineProvider>
  </React.StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
