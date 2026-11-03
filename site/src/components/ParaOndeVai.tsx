/* "Para onde vai o dinheiro": a cota de todos os parlamentares no ano, pelos três grupos e, dentro de cada grupo,
   por tema (viagens, combustível, divulgação...). Cada tema mostra as categorias oficiais que entraram nele.
   Os valores vêm de meta.json (temas_por_ano), que o coletor soma nota por nota; a soma dos temas é o total do ano
   (validar.py confere). */
import { useState } from "react";
import { GRUPO_CURTO, GRUPO_EXPLICA, type Grupo, type TemaCota } from "../data";
import { COR_GRUPO } from "./ui";
import { Rosca, curto, porcento } from "./graficos";

const ORDEM: Grupo[] = ["pessoal", "escritorio", "servicos"];
const pctTxt = (p: number) => (p < 0.01 ? "<1%" : porcento(p, p < 0.1 ? 1 : 0));

export function ParaOndeVai({ temas, ano }: { temas: TemaCota[]; ano: string }) {
  const total = temas.reduce((a, t) => a + t.valor, 0);
  const [aberto, setAberto] = useState<string | null>(null);
  if (!total) return null;
  const porGrupo = ORDEM.map((g) => {
    const ts = temas.filter((t) => t.grupo === g && t.valor > 0).sort((a, b) => b.valor - a.valor);
    return { g, ts, valor: ts.reduce((a, t) => a + t.valor, 0) };
  }).filter((x) => x.valor > 0);
  const fatias = porGrupo.map((x) => ({ nome: GRUPO_CURTO[x.g], valor: x.valor, cor: COR_GRUPO[x.g], pct: x.valor / total }));
  return (
    <div className="pov">
      <Rosca fatias={fatias} titulo={`Cota parlamentar em ${ano}, pelos três grupos de gasto`} centroRotulo={`Cota de todos em ${ano}`} legenda={false} />
      <div className="pov-grupos">
        {porGrupo.map(({ g, ts, valor }) => {
          const maxT = ts[0]?.valor || 1;
          return (
            <details key={g} className="pov-grupo" open style={{ borderTopColor: COR_GRUPO[g] }}>
              <summary>
                <span className="pov-nome"><i style={{ background: COR_GRUPO[g] }} />{GRUPO_CURTO[g]}</span>
                <span className="pov-valor num">{curto(valor)} <small>{`${pctTxt(valor / total)} da cota`}</small></span>
                <span className="muted small pov-explica">{GRUPO_EXPLICA[g]}</span>
                <span className="pov-abrir small"><span className="pov-mais">▸ ver o que entra aqui</span><span className="pov-menos">▾ ver menos</span></span>
              </summary>
              <ul>
                {ts.map((t) => {
                  const id = `${g}:${t.tema}`;
                  return (
                    <li key={t.tema}>
                      <button type="button" className="pov-tema" aria-expanded={aberto === id} onClick={() => setAberto(aberto === id ? null : id)}
                        title="Ver as categorias oficiais que entram aqui">
                        <span>{t.tema}</span>
                        <span className="num">{curto(t.valor)} <small>{pctTxt(t.valor / valor)}</small></span>
                        <span className="track" aria-hidden="true"><span className="fill" style={{ width: `${(t.valor / maxT) * 100}%`, background: COR_GRUPO[g] }} /></span>
                      </button>
                      {aberto === id && (
                        <ul className="pov-cats small">
                          {t.categorias.map(([c, v]) => <li key={c}><span>{c}</span><span className="num">{curto(v)}</span></li>)}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            </details>
          );
        })}
      </div>
      <p className="small muted">Soma das notas fiscais de todos os deputados federais e senadores em {ano}. Toque num tipo de gasto para ver os nomes usados pela Câmara e pelo Senado. A porcentagem ao lado de cada tipo é a parte dele no grupo.</p>
    </div>
  );
}
