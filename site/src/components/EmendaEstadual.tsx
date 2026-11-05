import type { ReactNode } from "react";

/** O que se sabe de uma indicação de emenda estadual: para que é, quem executa e como o dinheiro é gasto.
    Campos vazios (a ALMG escreve "Não há" quando o deputado não descreve a indicação) não aparecem. */
export function DetalheEmendaEstadual({ x, autor }: {
  x: { descricao?: string; objeto?: string; orgao_nome?: string; orgao?: string; acao?: string; tipo_indicacao?: string; grupo?: string;
    area?: string; situacao?: string };
  /** quem indicou, quando a lista mistura deputados */
  autor?: ReactNode;
}) {
  const paraQue = x.descricao || x.objeto;
  const orgao = x.orgao_nome || x.orgao;
  const como = [x.tipo_indicacao, x.grupo, x.area].filter(Boolean).join(" · ");
  return (
    <div className="small emenda-det">
      {autor && <div><span className="muted">Indicada por</span> {autor}</div>}
      {paraQue && <div><span className="muted">Para quê:</span> {paraQue}{x.descricao && x.objeto && x.objeto !== x.descricao ? <span className="muted"> ({x.objeto})</span> : null}</div>}
      {orgao && <div><span className="muted">Quem executa:</span> {orgao}{x.acao ? <span className="muted"> · ação “{x.acao}”</span> : null}</div>}
      {como && <div><span className="muted">Como:</span> {como}</div>}
      {x.situacao && <div><span className="muted">Situação:</span> {x.situacao}</div>}
    </div>
  );
}
