/* Botão "Compartilhar" do perfil de um político: monta no navegador a imagem do cartão (src/cartao.ts) para o feed
   ou para os stories do Instagram, e o link da página simples dele (politico/<nome>-<id>.html), que já abre com a
   imagem de prévia no WhatsApp e nas outras redes. Nenhum dado sai do navegador: a imagem é feita aqui mesmo. */
import { useEffect, useState } from "react";
import { TAMANHO, dadosCartao, desenharCartao, paginaPolitico, type Formato } from "../cartao";
import type { Meta, Resumo } from "../data";
import { SITE } from "../recorte";

const NOMES: Record<Exclude<Formato, "link">, string> = { feed: "Feed (4:5)", stories: "Stories (9:16)" };

async function gerar(p: Resumo, meta: Meta, ano: string, formato: Formato, endereco: string): Promise<Blob | null> {
  const dados = dadosCartao(p, meta, { ano, site: SITE.titulo, endereco });
  if (!dados) return null;
  // Espera a letra do site; sem ela, o cartão sai com a letra padrão
  try { await Promise.all([500, 600, 700, 800].map((w) => document.fonts.load(`${w} 40px Raleway`))); } catch { /* segue */ }
  const [w, h] = TAMANHO[formato];
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) return null;
  desenharCartao(ctx, dados, formato, document.fonts.check("800 40px Raleway") ? "Raleway" : "sans-serif");
  return new Promise((ok) => c.toBlob((b) => ok(b), "image/png"));
}

export function Compartilhar({ p, meta, ano }: { p: Resumo; meta: Meta | null; ano: string }) {
  const [aberto, setAberto] = useState(false);
  const [formato, setFormato] = useState<"feed" | "stories">("feed");
  const [imagem, setImagem] = useState<{ blob: Blob; url: string } | null>(null);
  const [aviso, setAviso] = useState("");
  const raiz = `${location.origin}${location.pathname}`;
  const link = new URL(paginaPolitico(p), raiz).href;
  const temGasto = !!p.por_ano?.[ano]?.total;

  useEffect(() => {
    if (!aberto || !meta || !temGasto) return;
    let vivo = true;
    let url = "";
    gerar(p, meta, ano, formato, raiz).then((blob) => {
      if (!vivo || !blob) return;
      url = URL.createObjectURL(blob);
      setImagem({ blob, url });
    });
    return () => { vivo = false; if (url) URL.revokeObjectURL(url); };
  }, [aberto, meta, p, ano, formato, raiz, temGasto]);

  const arquivo = `${p.nome.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9]+/g, "-")}-${ano}-${formato}.png`;
  const podeEnviar = !!imagem && typeof navigator.canShare === "function"
    && navigator.canShare({ files: [new File([imagem.blob], arquivo, { type: "image/png" })] });

  async function enviar() {
    if (!imagem) return;
    try {
      await navigator.share({ files: [new File([imagem.blob], arquivo, { type: "image/png" })], title: p.nome, text: link });
    } catch { /* quem lê cancelou */ }
  }
  async function copiar() {
    try { await navigator.clipboard.writeText(link); setAviso("Link copiado"); } catch { setAviso(link); }
  }

  return (
    <>
      <button type="button" className="chip" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>Compartilhar</button>
      {aberto && (
        <div className="compartilhar" role="region" aria-label="Compartilhar">
          {!temGasto ? <p className="small muted">Sem gasto da cota em {ano}: escolha outro ano no topo para gerar a imagem.</p> : <>
            <div className="compartilhar-formatos" role="group" aria-label="Formato da imagem">
              {(Object.keys(NOMES) as ("feed" | "stories")[]).map((f) => (
                <button key={f} type="button" className="chip" aria-pressed={formato === f} onClick={() => setFormato(f)}>{NOMES[f]}</button>
              ))}
            </div>
            {imagem
              ? <img className={`compartilhar-previa ${formato}`} src={imagem.url} alt={`Cartão de ${p.nome} com a cota parlamentar de ${ano}`} />
              : <p className="small muted">Montando a imagem…</p>}
            <div className="compartilhar-acoes">
              {podeEnviar && <button type="button" className="btn" onClick={enviar}>Enviar imagem</button>}
              {imagem && <a className={podeEnviar ? "btn alt" : "btn"} href={imagem.url} download={arquivo}>Baixar imagem</a>}
              <button type="button" className="btn alt" onClick={copiar}>Copiar link da página</button>
            </div>
          </>}
          {aviso && <p className="small" role="status">{aviso}</p>}
          <p className="small muted">A imagem leva a fonte oficial e a data da atualização. O link abre uma página simples de {p.nome}, que aparece com a imagem de prévia no WhatsApp e nas redes.</p>
        </div>
      )}
    </>
  );
}
