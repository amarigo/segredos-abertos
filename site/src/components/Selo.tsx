import { Link } from "react-router-dom";
import { useData } from "./ui";
import type { Verificacao, SecaoVerificada, StatusVerificacao } from "../data";

/* Selo de verificação de cada seção do site. Mostra só o que a verificação diária de fato conferiu
   (etl/sa_etl/verificar.py): sem o arquivo, ou sem conferência, nunca aparece como conferido. */

export const ROTULO: Record<StatusVerificacao, string> = {
  conferido: "Conferido com uma segunda fonte oficial",
  parcial: "Conferido em parte",
  divergente: "Diferença encontrada na conferência",
  nao_conferido: "Não conferido nesta atualização",
  sem_segunda_fonte: "Sem segunda fonte para conferir",
};
const ICONE: Record<StatusVerificacao, string> = { conferido: "✓", parcial: "◐", divergente: "!", nao_conferido: "○", sem_segunda_fonte: "○" };

const inteiro = (n: number) => n.toLocaleString("pt-BR");
export const pct = (x: number) => `${(Math.floor(x * 10000) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}%`;

export function resumoSecao(s: SecaoVerificada): string {
  const a = s.acumulado;
  if (!a.conferidos) return "";
  const dif = a.divergentes ? `${inteiro(a.divergentes)} com diferença` : "nenhum com diferença";
  const certos = a.certos_min != null ? `; com 95% de confiança, pelo menos ${pct(a.certos_min)} estão certos` : "";
  return `${inteiro(a.conferidos)} números conferidos em ${a.dias} ${a.dias === 1 ? "dia" : "dias"}, ${dif}${certos}`;
}

export default function Selo({ secao }: { secao: string }) {
  const { data } = useData<Verificacao>("verificacao.json");
  const s = data?.secoes?.[secao];
  if (!s) return null;
  const txt = resumoSecao(s);
  return (
    <Link to={`/verificacao#${secao}`} className={`selo selo-${s.status}`} data-status={s.status}>
      <span className="selo-icone" aria-hidden="true">{ICONE[s.status]}</span>
      <span><strong>{ROTULO[s.status]}</strong>{txt && <span className="selo-txt"> · {txt}</span>} <span className="selo-ver">Ver como conferimos</span></span>
    </Link>
  );
}

/* Todas as seções numa lista curta, para a página inicial */
export function SelosResumo() {
  const { data } = useData<Verificacao>("verificacao.json");
  if (!data?.secoes) return null;
  return (
    <section>
      <h2>Os números conferem?</h2>
      <p className="explain">Todo dia sorteamos números do site e conferimos cada um com uma segunda fonte oficial. Diferenças aparecem aqui, sem esconder nada.</p>
      <div className="selos">
        {Object.entries(data.secoes).map(([id, s]) => (
          <Link key={id} to={`/verificacao#${id}`} className={`selo selo-${s.status}`} data-status={s.status}>
            <span className="selo-icone" aria-hidden="true">{ICONE[s.status]}</span>
            <span><strong>{s.titulo}</strong> · {ROTULO[s.status].toLowerCase()}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
