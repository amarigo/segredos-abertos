/// <reference types="vite/client" />
interface ImportMetaEnv {
  /** "mg" no Minas Nossa; vazio no Segredos Abertos nacional */
  readonly VITE_RECORTE?: string;
}
interface ImportMeta { readonly env: ImportMetaEnv }
