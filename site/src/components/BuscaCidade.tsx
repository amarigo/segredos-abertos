import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MG } from "../recorte";
import { buscarCidades, normal } from "../busca-cidades";

export { normal };

/* Quem me representa: tipos dos arquivos de data/representantes/ (etl/sa_etl/representantes.py), a leitura deles e o
   campo "digite sua cidade", usado na página inicial e na página Quem me representa (pages/Representantes.tsx).
   O Minas Nossa (/mg/) lê os mesmos arquivos do site nacional (../data/), só com as cidades de Minas. */

export interface Em2026 { cargo: string; uf: string; partido: string; resultado: string; reeleicao?: boolean; renunciou?: boolean }
export interface Eleito { nome: string; partido: string; numero?: string; nome_completo?: string; situacao?: string; turnos?: number; em_2026?: Em2026;
  /** soma dos bens declarados ao TSE na candidatura (só quem está no arquivo de candidatos) */
  patrimonio?: number; sem_bens?: boolean }
export interface Parlamentar { id: string; nome: string; partido: string; foto?: string; cargo?: string }
type Fonte = { url: string; pagina: string; lido_em: string };
export interface RepIndice {
  atualizado_em: string;
  eleicoes: { municipal: number; geral: number; seguinte: number };
  municipios: [string, string, string][];
  presidente: Eleito | null; vice_presidente: Eleito | null;
  fontes: Record<string, string | Fonte | undefined>;
}
export interface RepEstado {
  uf: string; nome: string; eleicao: number;
  governador: Eleito | null; vice_governador: Eleito | null;
  deputados_estaduais: Eleito[]; vagas_estaduais: number | null; casa_estadual: string; cargo_estadual: string;
  deputados_federais: Parlamentar[]; vagas_federais: number | null; senadores: Parlamentar[];
}
export interface RepCidade {
  ue: string; nome: string; uf: string; eleicao: number;
  prefeito?: Eleito; vice_prefeito?: Eleito; vereadores: Eleito[]; vagas_vereadores: number | null;
  suplementar?: { data: string; fonte?: string; eleitos_2024: { prefeito: Eleito | null; vice_prefeito: Eleito | null } };
  /** eleição suplementar para a Câmara: com `eleitos`, foi só para algumas cadeiras e a lista de 2024 fica */
  suplementar_vereadores?: { data: string; fonte: string; cadeiras: number; eleitos_2024: number; eleitos?: Eleito[] };
  /** o que o TSE diz no site de resultados quando falta prefeito ou vereador eleito */
  aviso_tse?: { prefeito?: AvisoTSE; vereadores?: AvisoTSE };
}
export interface AvisoTSE { mensagens: string[]; fonte: string; totalizado?: boolean; suplementar?: string }

/* O Minas Nossa é publicado em /mg/, e os arquivos ficam no site nacional, um nível acima */
const BASE = MG ? "../data/representantes/" : "./data/representantes/";
const guardados = new Map<string, Promise<unknown>>();
function carregar<T>(rel: string): Promise<T> {
  if (!guardados.has(rel)) {
    guardados.set(rel, fetch(BASE + rel).then((r) => {
      if (!r.ok) throw new Error(`Não encontrado: ${rel}`);
      return r.json();
    }).catch((e) => { guardados.delete(rel); throw e; }));
  }
  return guardados.get(rel) as Promise<T>;
}
export function useRep<T>(rel: string | null): { data: T | null; error: string | null } {
  const [s, set] = useState<{ data: T | null; error: string | null }>({ data: null, error: null });
  useEffect(() => {
    if (!rel) return;
    let vivo = true;
    set({ data: null, error: null });
    carregar<T>(rel).then((d) => vivo && set({ data: d, error: null }), (e) => vivo && set({ data: null, error: String(e.message || e) }));
    return () => { vivo = false; };
  }, [rel]);
  return s;
}

const MINHA = "minha-cidade";
export function cidadeGuardada(): string {
  try { return localStorage.getItem(MINHA) || ""; } catch { return ""; }
}
export function guardar(ue: string) {
  try { localStorage.setItem(MINHA, ue); } catch { /* sem armazenamento */ }
}

/** Campo "digite sua cidade". Só baixa a lista de cidades quando a pessoa começa a usar o campo. */
export function BuscaCidade({ rotulo, id = "busca-cidade", autoFocus = false }: { rotulo: ReactNode; id?: string; autoFocus?: boolean }) {
  const [ativo, setAtivo] = useState(autoFocus);
  const [q, setQ] = useState("");
  const { data, error } = useRep<RepIndice>(ativo ? "indice.json" : null);
  const nav = useNavigate();
  const lista = useMemo(() => (data?.municipios || []).filter((c) => !MG || c[2] === "MG"), [data]);
  const achadas = useMemo(() => buscarCidades(lista, q), [lista, q]);
  const ir = (ue: string) => { guardar(ue); nav(`/quem/${ue}`); };
  return (
    <div className="rep-busca">
      <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); if (achadas[0]) ir(achadas[0][0]); }}>
        <label htmlFor={id} className="muted small" style={{ flexBasis: "100%" }}>{rotulo}</label>
        <input id={id} value={q} autoFocus={autoFocus} autoComplete="off" placeholder={MG ? "Ex.: Itajubá" : "Ex.: Campinas ou Recife PE"}
          onFocus={() => setAtivo(true)} onChange={(e) => { setAtivo(true); setQ(e.target.value); }}
          aria-describedby={`${id}-ajuda`} />
      </form>
      <span id={`${id}-ajuda`} className="sr-only">Digite pelo menos duas letras; a lista de cidades aparece embaixo.</span>
      {error && ativo && <div className="empty small">A lista de cidades não carregou agora. Tente de novo em instantes.</div>}
      {ativo && !data && !error && normal(q).length >= 2 && <div className="muted small">Carregando a lista de cidades…</div>}
      {achadas.length > 0 && (
        <ul className="list rep-sugestoes" aria-label="Cidades encontradas">
          {achadas.map(([ue, nome, uf]) => (
            <li key={ue}><Link to={`/quem/${ue}`} onClick={() => guardar(ue)} className="person rep-cidade-linha">
              <span className="pname">{nome}</span><span className="meta">{uf === "DF" && ue === "DF" ? "Distrito Federal" : uf}</span>
            </Link></li>
          ))}
        </ul>
      )}
      {data && normal(q).length >= 2 && !achadas.length && <div className="empty small">Nenhuma cidade com esse nome{MG ? " em Minas Gerais" : ""}. Confira a grafia.</div>}
    </div>
  );
}

