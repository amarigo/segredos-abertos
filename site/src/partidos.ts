/** Lados da régua esquerda-direita, calculada pelos votos. */

export const LADOS = ["Esquerda", "Centro-esquerda", "Centro", "Centro-direita", "Direita"] as const;
export type Lado = (typeof LADOS)[number];

/** Mesmos cortes de etl/sa_etl/ideologia.py (rotulo). */
export function ladoPelosVotos(pos: number): Lado {
  if (pos <= -0.5) return "Esquerda";
  if (pos <= -0.15) return "Centro-esquerda";
  if (pos < 0.15) return "Centro";
  if (pos < 0.5) return "Centro-direita";
  return "Direita";
}

/** Cor de cada lado nos gráficos: vermelho (esquerda), cinza (centro), azul (direita); os lados de centro, mais claros. */
export const COR_LADO: Record<string, string> = {
  Esquerda: "var(--esq)", "Centro-esquerda": "color-mix(in oklab, var(--esq) 55%, var(--centro))", Centro: "var(--centro)",
  "Centro-direita": "color-mix(in oklab, var(--dir) 55%, var(--centro))", Direita: "var(--dir)", "Sem posição": "var(--c-outros)",
};
