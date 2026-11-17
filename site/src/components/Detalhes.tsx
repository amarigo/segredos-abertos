/* Divulgação progressiva: o detalhe de uma página fica recolhido, um clique abaixo do número principal.
   Cada item é um Accordion do Mantine com um título curto. Dentro do item, o título da seção (h2) não se repete:
   quem escreve a seção usa <TituloSecao>, que some quando a seção está dentro de um item recolhido.
   Os itens abertos ficam no endereço (?ver=equipe,notas), para um link levar direto ao detalhe. */
import { createContext, useContext, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Accordion } from "@mantine/core";

const DentroDoItem = createContext(false);

/** Título da seção. Dentro de um item de <Detalhes>, o título do item já diz o mesmo, então não aparece. */
export function TituloSecao({ children, id }: { children: ReactNode; id?: string }) {
  if (useContext(DentroDoItem)) return null;
  return <h2 id={id}>{children}</h2>;
}

export interface ItemDetalhe { id: string; titulo: ReactNode; conteudo: ReactNode }

export function Detalhes({ itens, abertos = [] }: { itens: (ItemDetalhe | false | null | undefined)[]; abertos?: string[] }) {
  const [params, setParams] = useSearchParams();
  const lista = itens.filter(Boolean) as ItemDetalhe[];
  const ver = params.get("ver");
  const valor = ver != null ? ver.split(",").filter(Boolean) : abertos;
  const mudar = (v: string[]) => {
    const p = new URLSearchParams(params);
    if (v.length) p.set("ver", v.join(",")); else p.set("ver", "");
    setParams(p, { replace: true });
  };
  return (
    <Accordion multiple variant="separated" value={valor} onChange={mudar} className="detalhes">
      {lista.map((it) => (
        <Accordion.Item key={it.id} value={it.id} id={`ver-${it.id}`}>
          <Accordion.Control>{it.titulo}</Accordion.Control>
          <Accordion.Panel>
            <DentroDoItem.Provider value={true}>{it.conteudo}</DentroDoItem.Provider>
          </Accordion.Panel>
        </Accordion.Item>
      ))}
    </Accordion>
  );
}
