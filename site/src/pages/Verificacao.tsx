import { Explain, Loading, useData } from "../components/ui";
import { ROTULO, pct, resumoSecao } from "../components/Selo";
import { dataBR, linkSeguro, reais, type Checagem, type ItemVerificado, type MotivoDiferenca, type Verificacao } from "../data";

const ST_CHECAGEM = { conferido: "Conferido", explicado: "Diferenças explicadas", divergente: "Diferença em revisão", nao_conferido: "Não conferido" };

function valor(x: number | string) {
  return typeof x === "number" ? reais(x, true) : x;
}

function Itens({ itens, titulo, motivos }: { itens: ItemVerificado[]; titulo: string; motivos?: Record<string, MotivoDiferenca> }) {
  if (!itens.length) return null;
  const comMotivo = !!motivos && itens.some((d) => d.motivo !== undefined);
  return (
    <div className="table-wrap">
      <table>
        <caption className="small muted" style={{ textAlign: "left" }}>{titulo}</caption>
        <thead><tr><th>O que</th><th className="r">No site</th><th className="r">Na fonte oficial</th>{comMotivo && <th>Por quê</th>}<th>Fonte</th></tr></thead>
        <tbody>
          {itens.map((d, i) => (
            <tr key={i}>
              <td>{d.o_que}</td>
              <td className="r num">{valor(d.site)}</td>
              <td className="r num">{valor(d.oficial)}</td>
              {comMotivo && <td className="small" data-motivo={d.motivo || "sem_motivo"}>{d.motivo ? <a href={`#motivo-${d.motivo}`}>{motivos?.[d.motivo]?.titulo || d.motivo}</a> : <strong>Em revisão: motivo ainda não entendido</strong>}</td>}
              <td>{linkSeguro(d.fonte) ? <a href={linkSeguro(d.fonte)} target="_blank" rel="noreferrer">abrir ↗</a> : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CardChecagem({ c, motivos }: { c: Checagem; motivos?: Record<string, MotivoDiferenca> }) {
  return (
    <div className={`card checagem checagem-${c.status}`}>
      <h3>{c.titulo} <span className={`chip st-${c.status}`}>{ST_CHECAGEM[c.status]}</span></h3>
      <p className="small">{c.como}</p>
      <p className="small muted">
        Hoje: {c.conferidos.toLocaleString("pt-BR")} conferidos, {c.divergentes.toLocaleString("pt-BR")} com diferença
        {c.nao_conferidos > 0 && <>, {c.nao_conferidos.toLocaleString("pt-BR")} que a fonte não respondeu</>}
        {c.completados ? <>, {c.completados.toLocaleString("pt-BR")} meses completados com a página oficial (não contam)</> : null}.
        {linkSeguro(c.fonte) && <> Fonte da conferência: <a href={linkSeguro(c.fonte)} target="_blank" rel="noreferrer">documentação oficial ↗</a></>}
      </p>
      {c.status === "nao_conferido" && c.motivo && <p className="small"><strong>Por que não foi conferido:</strong> {c.motivo}</p>}
      <Itens itens={c.divergencias} motivos={motivos} titulo="Diferenças encontradas (cada uma com o motivo e o link para conferir)" />
      {!c.divergencias.length && <Itens itens={c.exemplos} titulo="Exemplos que bateram (para você conferir)" />}
    </div>
  );
}

export default function VerificacaoPage() {
  const { data: v, error } = useData<Verificacao>("verificacao.json");
  if (!v) return <Loading error={error} />;
  return (
    <section style={{ maxWidth: 900 }}>
      <h1>Como conferimos os números</h1>
      <Explain>
        Todo dia, depois de baixar os dados, sorteamos números já prontos para o site e perguntamos de novo a uma <strong>fonte oficial diferente</strong> daquela de onde eles vieram. Por exemplo: a cota dos deputados vem do arquivo anual da Câmara e é conferida na API da Câmara; o placar do Senado vem do painel de votação e é conferido com a ata da sessão. Quando algo não bate, mostramos aqui, com o link para você conferir.
      </Explain>
      <p className="small">
        Com <em>n</em> números conferidos e nenhuma diferença, dá para afirmar, com 95% de confiança, que pelo menos 1 − 0,05<sup>1/n</sup> dos números estão certos. Para dizer "pelo menos 99,99% certos" é preciso conferir cerca de <strong>{v.para_99_99.toLocaleString("pt-BR")}</strong> números sem nenhum erro. Por isso as conferências se somam dia a dia (últimos {v.dias_historico} dias). Uma seção só aparece como conferida se todas as suas checagens rodaram e nenhuma achou diferença. Cada diferença é investigada: quando o motivo é conhecido, o site mostra o número oficial e explica; quando ainda não é, o número fica marcado "em revisão" e, se forem mais de {Math.round((v.limite_sem_motivo ?? 0.02) * 100)}% dos conferidos de uma seção, a atualização do site é barrada até entendermos o motivo. A cota só é conferida em meses que terminaram há mais de {v.dias_mes_fechado} dias, porque antes disso a Câmara e o Senado ainda lançam notas atrasadas.
      </p>
      <p className="small muted">Última verificação: {dataBR(v.data)}.</p>
      {Object.entries(v.secoes).map(([id, s]) => (
        <div key={id} id={id} className="secao-verificada">
          <h2>{s.titulo}</h2>
          <p><span className={`selo selo-${s.status}`} data-status={s.status}><strong>{ROTULO[s.status]}</strong></span></p>
          {resumoSecao(s) && <p className="small">{resumoSecao(s)}{s.acumulado.desde && <> (desde {dataBR(s.acumulado.desde)})</>}.</p>}
          {s.acumulado.certos_min != null && s.acumulado.certos_min < 0.9999 && s.acumulado.divergentes === 0 &&
            <p className="small muted">Para chegar a 99,99% faltam {Math.max(0, v.para_99_99 - s.acumulado.conferidos).toLocaleString("pt-BR")} números conferidos sem erro (hoje: {pct(s.acumulado.certos_min)}).</p>}
          {s.motivo && <p className="small">{s.motivo}</p>}
          {s.barrar && <p className="alert small" role="note">Esta seção teve diferenças sem motivo conhecido demais na última conferência, e a atualização do site foi barrada. Os números continuam os da atualização anterior até entendermos o motivo.</p>}
          {v.checagens.filter((c) => c.secao === id).map((c) => <CardChecagem key={c.id} c={c} motivos={v.motivos} />)}
        </div>
      ))}
      {v.motivos && (
        <div className="secao-verificada" id="motivos">
          <h2>Por que os números às vezes são diferentes</h2>
          <p className="small">Quando duas publicações oficiais mostram números diferentes, procuramos o motivo e o site passa a mostrar o número oficial. Estes são os motivos que já entendemos e o que o site faz em cada um:</p>
          {Object.entries(v.motivos).map(([id, m]) => (
            <div key={id} id={`motivo-${id}`} className="card checagem">
              <h3>{m.titulo}{m.corrigido && <span className="chip st-conferido">Já corrigido no site</span>}</h3>
              <p className="small">{m.explica}</p>
              <p className="small"><strong>O que o site faz:</strong> {m.decisao}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
