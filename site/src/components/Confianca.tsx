/* Confiança em cada número: média da Casa ao lado, o que falta e o link para avisar um erro (regras em ../confianca.ts) */
import { useLocation } from "react-router-dom";
import { dataBR, linkSeguro, type Politico } from "../data";
import { ESTADO_COBERTURA, linkAvisarErro, oQueFalta, type Referencia } from "../confianca";

/** A média da Casa embaixo de um número: rótulo curto, valor, comparação e, menor, de quem é a média */
export function MediaCasaLinha({ r, fmt, comparacao }: { r: Referencia; fmt: (v: number) => string; comparacao?: string }) {
  return (
    <span className="media-casa" data-testid="media-casa">
      <span><strong>{r.rotulo}:</strong> <span className="num">{fmt(r.valor)}</span>{comparacao && <> · {comparacao}</>}</span>
      <span className="media-casa-quem">{r.criterio}</span>
    </span>
  );
}

/** Quadro do perfil: o que está aqui, o que completamos com outra fonte e o que falta, para o ano escolhido */
export function OQueFaltaQuadro({ p, ano, atualizado }: { p: Politico; ano: string; atualizado?: string }) {
  const itens = oQueFalta(p, ano, p.anos[ano]);
  const ordem = ["tem", "completado", "fonte_nao_publica", "ainda_nao"] as const;
  return (
    <details className="abrir o-que-falta" data-testid="o-que-falta">
      <summary>O que está aqui e o que falta sobre {p.nome} em {ano}</summary>
      <div className="abrir-corpo">
        <p className="small muted">{atualizado ? <>Dados coletados em {dataBR(atualizado)}. </> : null}Cada linha diz de onde vem o dado ou por que ele não está aqui.</p>
        {ordem.map((estado) => {
          const doEstado = itens.filter((x) => x.estado === estado);
          if (!doEstado.length) return null;
          return (
            <div key={estado} className={`cobertura cobertura-${estado}`}>
              <h3><span aria-hidden="true">{ESTADO_COBERTURA[estado].icone}</span> {ESTADO_COBERTURA[estado].nome}</h3>
              <ul>
                {doEstado.map((x) => (
                  <li key={x.titulo}><strong>{x.titulo}.</strong> {x.texto}
                    {linkSeguro(x.link) && <> <a href={linkSeguro(x.link)} target="_blank" rel="noreferrer">{x.linkTexto || "fonte"} ↗</a></>}</li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </details>
  );
}

/** Avisar um erro sem servidor: abre um aviso público no GitHub com a página já preenchida */
export function AvisarErro({ assunto, resposta = false }: { assunto?: string; resposta?: boolean }) {
  const { pathname, search } = useLocation();
  // O site usa HashRouter: o endereço completo da página é o endereço do site + "#" + a rota
  const pagina = typeof window === "undefined" ? pathname : `${window.location.origin}${window.location.pathname}#${pathname}${search}`;
  const titulo = assunto || (typeof document !== "undefined" ? document.title : "") || pathname;
  return (
    <div className="avisar-erro" data-testid="avisar-erro">
      <strong>Achou um número errado?</strong>{" "}
      <a href={linkAvisarErro(pagina, titulo)} target="_blank" rel="noreferrer">Avise aqui</a>, de preferência com o link da fonte
      oficial que mostra o número certo. O aviso é público, no GitHub (a conta é gratuita): não escreva CPF, telefone ou outro dado pessoal.
      {resposta && <> É o próprio político ou a equipe dele? <a href={linkAvisarErro(pagina, titulo, "resposta")} target="_blank" rel="noreferrer">Peça direito de resposta</a>.</>}
      {" "}Cada aviso é conferido com a fonte oficial; se estiver certo, corrigimos e contamos o que mudou no próprio aviso.
    </div>
  );
}
