import { Link } from "react-router-dom";
import { Explain, useData } from "./ui";
import { cnpjFmt, dataBR, linkSeguro, reais } from "../data";

/* Punições e condenações oficiais (etl/sa_etl/sancoes.py): CEIS, CNEP e CEAF do Portal da Transparência e as listas
   do TCU. Só decisões oficiais, cada uma com o link para a fonte. CPF sempre com máscara. */

export type Cadastro = "ceis" | "cnep" | "ceaf" | "tcu_irregulares" | "tcu_eleitoral" | "tcu_inabilitados" | "tcu_inidoneos";
export interface RegistroPunicao {
  cad: Cadastro; id: string | number; nome: string; cnpj?: string; doc?: string; tipo?: string; orgao?: string;
  inicio?: string; fim?: string; transito?: string; processo?: string; portaria?: string; cargo?: string;
  decisao?: string; data_decisao?: string; uf?: string; multa?: number; fundamento?: string[]; link: string; acompanhar?: string; vigente: boolean;
}
export interface FontePunicao {
  nome: string; titulo: string; quem: string; explica: string; pagina: string; api: string;
  situacao: "ok" | "copia" | "parcial" | "falhou" | "sem_chave" | "faltando"; lida_em: string; n: number; referencia: string;
}
export interface EmpresaPunida { cnpj: string; nome: string; vigente: boolean; registros: RegistroPunicao[];
  socios: { nome: string; doc: string; qualificacao: string; registros: RegistroPunicao[] }[] }
export interface PoliticoPunido { id: string; nome: string; partido: string; uf: string; casa: string; vigente: boolean; registros: RegistroPunicao[] }
export interface Punicoes {
  atualizado_em: string; fontes: Record<Cadastro, FontePunicao>;
  cobertura: { empresas: number; socios: number; deputados: number; deputados_com_cpf: number; senadores: number };
  empresas: EmpresaPunida[]; politicos: PoliticoPunido[];
}

export const usePunicoes = () => useData<Punicoes>("sancoes.json");

const SITUACAO: Record<FontePunicao["situacao"], string> = {
  ok: "lida", copia: "cópia anterior (a leitura nova ainda não terminou)", parcial: "cópia anterior (leitura nova em andamento)",
  falhou: "a fonte não respondeu; cópia anterior", sem_chave: "não lida (falta a chave da API)", faltando: "não respondeu",
};

/** A lista de onde veio, com a explicação ao passar o mouse */
export function ChipCadastro({ cad, fontes }: { cad: Cadastro; fontes?: Punicoes["fontes"] }) {
  const f = fontes?.[cad];
  return <span className="chip" title={f ? `${f.titulo}: ${f.explica}` : undefined}>{f?.nome || cad}</span>;
}

/** Uma punição: o que é, quem puniu, desde quando, até quando, processo e o link para a fonte oficial */
export function Registro({ r, fontes }: { r: RegistroPunicao; fontes?: Punicoes["fontes"] }) {
  return (
    <li className="punicao">
      <div className="punicao-topo">
        <ChipCadastro cad={r.cad} fontes={fontes} />
        <span className={`chip ${r.vigente ? "nao" : ""}`}>{!r.vigente ? "Já terminou" : r.fim ? "Em vigor" : "Na lista hoje"}</span>
        <strong>{r.tipo}</strong>
      </div>
      <div className="small">
        {r.orgao && <><span className="muted">Quem puniu:</span> {r.orgao}. </>}
        {r.inicio && <><span className="muted">Desde</span> {dataBR(r.inicio)}</>}
        {r.fim ? <> <span className="muted">até</span> {dataBR(r.fim)}. </> : r.inicio ? ". " : null}
        {r.multa ? <><span className="muted">Multa:</span> {reais(r.multa, true)}. </> : null}
        {r.decisao && <><span className="muted">Decisão:</span> {r.decisao}{r.data_decisao && ` de ${dataBR(r.data_decisao)}`}. </>}
        {r.processo && <><span className="muted">Processo</span> <span className="mono">{r.processo}</span>. </>}
        {r.cargo && <><span className="muted">Cargo:</span> {r.cargo}. </>}
      </div>
      {r.fundamento && r.fundamento.length > 0 && <div className="small muted">Base legal: {r.fundamento.join("; ")}</div>}
      <div className="small"><span className="muted">Nome na lista:</span> {r.nome}{r.doc && !r.cnpj && <> · <span className="mono">{r.doc}</span></>}
        {" · "}<a href={linkSeguro(r.link)} target="_blank" rel="noreferrer">{r.cad.startsWith("tcu") ? "Ver o acórdão no TCU ↗" : r.cnpj ? "Ver a empresa no Portal da Transparência ↗" : "Consultar a lista oficial ↗"}</a>
        {r.acompanhar && <>{" · "}<a href={linkSeguro(r.acompanhar)} target="_blank" rel="noreferrer">Acompanhar o processo ↗</a></>}</div>
    </li>
  );
}

export function ListaRegistros({ rs, fontes }: { rs: RegistroPunicao[]; fontes?: Punicoes["fontes"] }) {
  return <ul className="punicoes">{rs.map((r) => <Registro key={`${r.cad}-${r.id}`} r={r} fontes={fontes} />)}</ul>;
}

function Rodape({ p }: { p: Punicoes }) {
  return (
    <p className="small muted">
      Fontes: {Object.values(p.fontes).map((f, i) => <span key={f.nome}>{i > 0 && " · "}<a href={linkSeguro(f.pagina)} target="_blank" rel="noreferrer">{f.nome} ({f.quem})</a>{f.lida_em && ` lida em ${dataBR(f.lida_em)}`}</span>)}.
      {" "}<Link to="/corrupcao/punicoes">Como cruzamos as listas</Link>.
    </p>
  );
}

/** No perfil do parlamentar: só aparece se ele estiver numa lista (ligado pelo CPF da API da Câmara) */
export function PunicoesPolitico({ id }: { id: string }) {
  const { data: p } = usePunicoes();
  const x = p?.politicos.find((y) => y.id === id);
  if (!p || !x) return null;
  return (
    <section data-testid="punicoes-politico">
      <h2>Punições e condenações oficiais</h2>
      <div className="alert" role="note"><span><strong>Aparece em lista oficial de punidos.</strong> A ligação é pelo CPF que a Câmara publica: não é só nome parecido. {x.vigente ? "Ao menos uma punição está em vigor." : "As punições listadas já terminaram."}</span></div>
      <ListaRegistros rs={x.registros} fontes={p.fontes} />
      <Rodape p={p} />
    </section>
  );
}

/** Na página da empresa: punições da própria empresa (pelo CNPJ) e dos sócios (nome e CPF com máscara iguais) */
export function PunicoesEmpresa({ cnpj }: { cnpj: string }) {
  const { data: p } = usePunicoes();
  const e = p?.empresas.find((y) => y.cnpj === cnpj);
  if (!p) return null;
  if (!e) {
    return <p className="small muted" data-testid="punicoes-empresa-nada">Punições oficiais: esta empresa e os sócios dela não aparecem no CEIS, no CNEP, no CEAF nem nas listas do TCU (conferido em {dataBR(p.atualizado_em)}). <Link to="/corrupcao/punicoes">Ver a lista de punidos</Link>.</p>;
  }
  return (
    <section data-testid="punicoes-empresa">
      <h2>Punições e condenações oficiais</h2>
      {e.registros.length > 0 && <>
        <h3>A própria empresa (CNPJ <span className="mono">{cnpjFmt(e.cnpj)}</span>)</h3>
        <ListaRegistros rs={e.registros} fontes={p.fontes} />
      </>}
      {e.socios.length > 0 && <>
        <h3>Sócios desta empresa</h3>
        <Explain>Ligamos o sócio à lista só quando o nome completo e os dígitos do CPF que a Receita mostra (os 6 do meio) são iguais. Mesmo assim, confira na fonte oficial antes de tirar conclusões.</Explain>
        {e.socios.map((s) => (
          <div key={s.nome + s.doc} className="punicao-socio">
            <strong>{s.nome}</strong> <span className="mono small">{s.doc.length === 14 ? cnpjFmt(s.doc) : s.doc}</span>{s.qualificacao && <span className="small muted"> · {s.qualificacao}</span>}
            {s.doc.length === 14 && <> · <Link to={`/e/${s.doc}`}>empresa sócia</Link></>}
            <ListaRegistros rs={s.registros} fontes={p.fontes} />
          </div>
        ))}
      </>}
      <Rodape p={p} />
    </section>
  );
}

/** Aviso curto no topo da página da empresa */
export function AlertaPunicaoEmpresa({ cnpj }: { cnpj: string }) {
  const { data: p } = usePunicoes();
  const e = p?.empresas.find((y) => y.cnpj === cnpj);
  if (!e || !e.vigente) return null;
  const propria = e.registros.some((r) => r.vigente);
  return <div className="alert" role="note"><strong>Punição oficial em vigor:</strong> {propria ? "a empresa aparece" : "um sócio aparece"} em lista oficial de punidos ({[...new Set([...e.registros, ...e.socios.flatMap((s) => s.registros)].filter((r) => r.vigente).map((r) => p!.fontes[r.cad]?.nome || r.cad))].join(", ")}). Detalhes mais abaixo.</div>;
}

export function situacaoFonte(f: FontePunicao): string {
  return SITUACAO[f.situacao] || f.situacao;
}
