import { useState } from "react";
import { Link } from "react-router-dom";
import { linkSeguro } from "../data";

/** Quem publicou a foto, pelo endereço dela (para o crédito embaixo da foto no perfil) */
export function fonteDaFoto(url?: string | null): { nome: string; curto: string; url: string } | undefined {
  const u = (url || "").trim();
  if (/^fotos\/tse\//i.test(u)) return { nome: "TSE", curto: "TSE", url: "https://dadosabertos.tse.jus.br/" };
  const host = (linkSeguro(u)?.match(/^https?:\/\/([^/:?#]+)/i)?.[1] || "").toLowerCase();
  const de = (d: string) => host === d || host.endsWith("." + d);
  if (de("camara.leg.br")) return { nome: "Câmara dos Deputados", curto: "Câmara", url: "https://dadosabertos.camara.leg.br/" };
  if (de("senado.leg.br")) return { nome: "Senado Federal", curto: "Senado", url: "https://www12.senado.leg.br/dados-abertos" };
  if (de("almg.gov.br")) return { nome: "Assembleia de Minas (ALMG)", curto: "ALMG", url: "https://www.almg.gov.br/a-assembleia/deputados/" };
  if (de("tse.jus.br")) return { nome: "TSE", curto: "TSE", url: "https://dadosabertos.tse.jus.br/" };
  return undefined;
}

/** Endereço da foto: link https de fora, ou arquivo publicado junto dos dados ("fotos/tse/...jpg") */
function endereco(url?: string | null): string | undefined {
  const u = (url || "").trim();
  if (/^fotos\/[a-z0-9/_-]+\.jpe?g$/i.test(u)) return `./data/${u}`;
  // Fotos do Senado vêm da API com http://; pedimos sempre por https (o mesmo endereço responde)
  return linkSeguro(u)?.replace(/^http:\/\//i, "https://");
}

function iniciais(nome: string): string {
  const partes = nome.replace(/\(.*\)/, "").trim().split(/\s+/).filter((x) => x.length > 2);
  const ps = partes.length ? partes : [nome.trim()];
  return (ps.length > 1 ? ps[0][0] + ps[ps.length - 1][0] : ps[0].slice(0, 2)).toUpperCase();
}

/** Foto oficial do político. Sem foto (ou se ela não carregar), um círculo neutro com as iniciais do nome. */
export function FotoPolitico({ url, nome, tamanho = 48, decorativa = false }: {
  url?: string | null; nome: string; tamanho?: number; decorativa?: boolean;
}) {
  const [erro, setErro] = useState(false);
  const src = endereco(url);
  const estilo = { width: tamanho, height: tamanho };
  if (!src || erro) {
    return <span className="avatar foto-sem" style={{ ...estilo, fontSize: Math.max(10, Math.round(tamanho * 0.34)) }}
      role={decorativa ? undefined : "img"} aria-label={decorativa ? undefined : `${nome} (sem foto oficial)`} aria-hidden={decorativa || undefined}>
      {iniciais(nome)}</span>;
  }
  return <img className="avatar foto-oficial" src={src} style={estilo} alt={decorativa ? "" : `Foto oficial de ${nome}`}
    loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setErro(true)} />;
}

/** Foto grande do perfil, com o crédito de quem a publicou */
export function FotoPerfil({ url, nome }: { url?: string | null; nome: string }) {
  const f = fonteDaFoto(url);
  return (
    <figure className="foto-perfil">
      <FotoPolitico url={url} nome={nome} tamanho={112} />
      {f && endereco(url) && <figcaption className="small muted">Foto: <a href={f.url} target="_blank" rel="noreferrer" title={`Foto oficial publicada por: ${f.nome}`}>{f.curto}</a></figcaption>}
    </figure>
  );
}

/** Rótulo de uma linha de ranking com foto: posição, foto grande, nome em destaque e partido (ou outra linha) embaixo.
 *  Usado nos gráficos de "quem mais gastou" das listas de políticos. */
export function RotuloRanking({ posicao, to, foto, nome, sub, cor }: {
  posicao: number; to: string; foto?: string | null; nome: string; sub?: string; cor?: string;
}) {
  return (
    <span className="rank-foto">
      <span className="rank-n" aria-hidden="true">{posicao}</span>
      <FotoPolitico url={foto} nome={nome} tamanho={52} decorativa />
      <span className="rank-txt">
        <Link className="rank-nome" to={to}>{nome}</Link>
        {sub && <span className="rank-sub"><i style={{ background: cor || "var(--muted)" }} />{sub}</span>}
      </span>
    </span>
  );
}
