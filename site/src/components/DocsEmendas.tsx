import { useState } from "react";
import { cnpjFmt, dataBR, linkSeguro, reais } from "../data";
import { Loading, useData } from "./ui";
import "../pages/emendas.css";

/* Pagamentos feitos com dinheiro de emendas (gerados por etl/sa_etl/pagamentos.py) */
export interface DocPagamento {
  data: string; codigo: string; tipo: string; orgao: string; ug: string; favorecido: string; cnpj: string;
  valor: number; empenho: string; emenda: string; descricao: string; url: string; url_empenho: string;
}
export interface AutorEmenda { nome: string; politico: string | null; partido: string }

/** Lista de documentos de pagamento, com os links oficiais do pagamento e do empenho (a reserva do dinheiro). */
export function ListaDocumentos({ docs, comFavorecido = true, inicial = 8 }: { docs: DocPagamento[]; comFavorecido?: boolean; inicial?: number }) {
  const [n, setN] = useState(inicial);
  if (!docs.length) return <p className="small muted">Nenhum documento de pagamento encontrado.</p>;
  return (
    <>
      <ul className="emd-docs">
        {docs.slice(0, n).map((d, i) => (
          <li key={`${d.codigo}-${d.empenho}-${i}`}>
            <div className="emd-doc-topo">
              <span className="small muted num">{dataBR(d.data)}</span>
              <strong className="num">{reais(d.valor, true)}</strong>
            </div>
            {comFavorecido && <div>
              Para {d.cnpj ? <a href={`https://portaldatransparencia.gov.br/pessoa-juridica/${d.cnpj}`} target="_blank" rel="noreferrer">{d.favorecido} ↗</a> : <strong>{d.favorecido}</strong>}
              {d.cnpj && <span className="small muted mono"> {cnpjFmt(d.cnpj)}</span>}
            </div>}
            <div className="small">Pago por {d.ug || d.orgao}{d.ug && d.orgao && d.ug !== d.orgao ? <span className="muted"> ({d.orgao})</span> : null}{d.emenda && <span className="muted"> · emenda nº {d.emenda}</span>}</div>
            {d.descricao && <div className="small emd-doc-desc"><b>Para quê:</b> {d.descricao}</div>}
            <div className="small emd-doc-links">
              <a href={linkSeguro(d.url)} target="_blank" rel="noreferrer">{d.tipo || "Pagamento"} {d.codigo.slice(-12)} ↗</a>
              <a href={linkSeguro(d.url_empenho)} target="_blank" rel="noreferrer">Nota de empenho {d.empenho.slice(-12)} ↗</a>
            </div>
          </li>
        ))}
      </ul>
      {docs.length > n && <button className="link" onClick={() => setN(n + 20)}>Mostrar mais documentos ({docs.length - n} restantes)</button>}
    </>
  );
}

/** Documentos de um parlamentar num ano: o arquivo só é baixado quando a pessoa abre. */
export function DocsDoAutor({ ano, arquivo }: { ano: string | number; arquivo: string }) {
  const { data, error } = useData<{ nome: string; valor: number; n: number; docs: DocPagamento[] }>(`emendas/docs/${ano}/${arquivo}.json`);
  if (!data) return <Loading error={error} />;
  return (
    <>
      <p className="small muted">{data.n.toLocaleString("pt-BR")} pagamento{data.n > 1 ? "s" : ""} em {ano}, somando {reais(data.valor)}.{data.n > data.docs.length && ` Mostramos os ${data.docs.length} maiores.`}</p>
      <ListaDocumentos docs={data.docs} />
    </>
  );
}
