/// <reference types="vite/client" />
interface ImportMetaEnv {
  /** "mg" no Minas Nossa; vazio no Segredos Abertos nacional */
  readonly VITE_RECORTE?: string;
}
interface ImportMeta { readonly env: ImportMetaEnv }

/** Tradutor dos sites (public/i18n/tradutor.js), carregado antes do React */
interface Window {
  SA_I18N?: { lingua: "pt" | "en" | "es"; endereco: (l: string) => string; trocar: (l: string) => void; t: (s: string) => string };
}
