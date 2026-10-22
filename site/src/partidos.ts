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
