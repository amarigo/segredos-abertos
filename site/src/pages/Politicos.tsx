import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Loading, useAno, useData } from "../components/ui";
import { reaisCurto, type Resumo } from "../data";
import { PessoaLinha, norm } from "./Home";

type Ordem = "total" | "nome" | "posicao";

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

  const ufs = useMemo(() => [...new Set((data || []).map((p) => p.uf))].sort(), [data]);
  const partidos = useMemo(() => [...new Set((data || []).map((p) => p.partido))].sort(), [data]);
  const lista = useMemo(() => {
    let l = (data || []).filter((p) => (!casa || p.casa === casa) && (!uf || p.uf === uf) && (!partido || p.partido === partido)
      && (!q || norm(p.nome).includes(norm(q))));
    l = l.slice().sort((a, b) => ordem === "nome" ? a.nome.localeCompare(b.nome)
      : ordem === "posicao" ? (a.posicao ?? 9) - (b.posicao ?? 9) : t(b) - t(a));
    return l;
  }, [data, q, casa, uf, partido, ordem, ano]);

  if (!data) return <Loading error={error} />;
  return (
    <section>
      <h1>Políticos</h1>
      <div className="search">
        <input id="filtro-nome" aria-label="Nome" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome" />
        <select id="filtro-casa" aria-label="Casa" value={casa} onChange={(e) => setCasa(e.target.value)}>
          <option value="">Câmara e Senado</option><option value="camara">Deputados federais</option><option value="senado">Senadores</option>
        </select>
        <select id="filtro-uf" aria-label="Estado" value={uf} onChange={(e) => setUf(e.target.value)}>
          <option value="">Todos os estados</option>{ufs.map((u) => <option key={u}>{u}</option>)}
        </select>
        <select id="filtro-partido" aria-label="Partido" value={partido} onChange={(e) => setPartido(e.target.value)}>
          <option value="">Todos os partidos</option>{partidos.map((u) => <option key={u}>{u}</option>)}
        </select>
        <select id="filtro-ordem" aria-label="Ordenar" value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
          <option value="total">Maior gasto de cota em {ano}</option><option value="nome">Nome</option><option value="posicao">Da esquerda para a direita</option>
        </select>
      </div>
      <p className="muted small">{lista.length} resultado{lista.length === 1 ? "" : "s"}</p>
      <div className="list">
        {lista.map((p) => <PessoaLinha key={p.id} p={p} extra={ordem === "posicao" ? p.rotulo : reaisCurto(t(p))} />)}
      </div>
    </section>
  );
}
