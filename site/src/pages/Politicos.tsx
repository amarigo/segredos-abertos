import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Loading, useAno, useData } from "../components/ui";
import { atuacaoAtiva, reaisCurto, taxaPresenca, type Resumo } from "../data";
import { PessoaLinha, norm } from "./Home";
import Selo from "../components/Selo";

type Ordem = "total" | "nome" | "posicao" | "presenca" | "autoria" | "relatadas" | "discursos";
const ROTULO: Record<string, [string, string]> = { autoria: ["proposta", "propostas"], relatadas: ["relatoria", "relatorias"], discursos: ["discurso", "discursos"] };

export default function Politicos() {
  const { data, error } = useData<Resumo[]>("politicos.json");
  const [q, setQ] = useState("");
  const [casa, setCasa] = useState("");
  const [uf, setUf] = useState("");
  const [params] = useSearchParams();
  const [partido, setPartido] = useState(params.get("partido") || "");
  const [ordem, setOrdem] = useState<Ordem>("total");
  const { ano } = useAno();
  const t = (p: Resumo) => p.por_ano[ano]?.total || 0;
  /** Valor da atuação no ano para ordenar (-1 quando não há dado: vai para o fim da lista). */
  const atu = (p: Resumo): number => {
    const a = p.por_ano[ano]?.atuacao;
    if (!atuacaoAtiva(a)) return -1;
    if (ordem === "presenca") return taxaPresenca(a.plenario) ?? -1;
    return (a as Record<string, unknown>)[ordem] as number ?? -1;
  };
  const extra = (p: Resumo) => {
    if (ordem === "posicao") return p.rotulo;
    if (ordem === "total" || ordem === "nome") return reaisCurto(t(p));
    const v = atu(p);
    if (v < 0) return "sem dado";
    if (ordem === "presenca") return `${Math.round(v * 100)}%`;
    return `${v.toLocaleString("pt-BR")} ${v === 1 ? ROTULO[ordem][0] : ROTULO[ordem][1]}`;
  };

  const ufs = useMemo(() => [...new Set((data || []).map((p) => p.uf))].sort(), [data]);
  const partidos = useMemo(() => [...new Set((data || []).map((p) => p.partido))].sort(), [data]);
  const lista = useMemo(() => {
    let l = (data || []).filter((p) => (!casa || p.casa === casa) && (!uf || p.uf === uf) && (!partido || p.partido === partido)
      && (!q || norm(p.nome).includes(norm(q))));
    l = l.slice().sort((a, b) => ordem === "nome" ? a.nome.localeCompare(b.nome)
      : ordem === "posicao" ? (a.posicao ?? 9) - (b.posicao ?? 9) : ordem === "total" ? t(b) - t(a) : atu(b) - atu(a) || a.nome.localeCompare(b.nome));
    return l;
  }, [data, q, casa, uf, partido, ordem, ano]);

  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Políticos</h1>
        <Selo secao="cota" />
      <div className="search">
        <input id="filtro-nome" aria-label="Nome" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome" />
        <select id="filtro-casa" aria-label="Casa" value={casa} onChange={(e) => setCasa(e.target.value)}>
          <option value="">Câmara e Senado</option><option value="camara">Deputados federais</option><option value="senado">Senadores</option>
        </select>
        {ufs.length > 1 && (
          <select id="filtro-uf" aria-label="Estado" value={uf} onChange={(e) => setUf(e.target.value)}>
            <option value="">Todos os estados</option>{ufs.map((u) => <option key={u}>{u}</option>)}
          </select>
        )}
        <select id="filtro-partido" aria-label="Partido" value={partido} onChange={(e) => setPartido(e.target.value)}>
          <option value="">Todos os partidos</option>{partidos.map((u) => <option key={u}>{u}</option>)}
        </select>
        <select id="filtro-ordem" aria-label="Ordenar" value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
          <option value="total">Maior gasto de cota em {ano}</option><option value="nome">Nome</option><option value="posicao">Da esquerda para a direita</option>
          <option value="presenca">Maior presença no Plenário em {ano}</option><option value="autoria">Mais propostas apresentadas em {ano}</option>
          <option value="relatadas">Mais relatorias em {ano}</option><option value="discursos">Mais discursos em {ano}</option>
        </select>
      </div>
      <p className="muted small">{lista.length} resultado{lista.length === 1 ? "" : "s"}</p>
      <div className="list">
        {lista.map((p) => <PessoaLinha key={p.id} p={p} extra={extra(p)} />)}
      </div>
    </section>
  );
}
