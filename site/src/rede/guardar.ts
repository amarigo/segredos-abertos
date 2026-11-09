/* Guarda a base da Minha rede só neste navegador (IndexedDB). Nada vai para o site nem para outra pessoa.
 * Se o navegador não deixar guardar (janela anônima, armazenamento bloqueado), a base vive só enquanto a página
 * estiver aberta, e a página avisa: dá para exportar o arquivo antes de fechar. */
import { baseVazia, lerExportada, type Base } from "./modelo";

const BANCO = "minha-rede", LOJA = "base", CHAVE = "atual";

function abrir(): Promise<IDBDatabase> {
  return new Promise((ok, falha) => {
    if (typeof indexedDB === "undefined") return falha(new Error("sem IndexedDB"));
    const r = indexedDB.open(BANCO, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(LOJA);
    r.onsuccess = () => ok(r.result);
    r.onerror = () => falha(r.error);
  });
}

export async function carregarBase(): Promise<{ base: Base; guarda: boolean }> {
  try {
    const db = await abrir();
    const valor = await new Promise<unknown>((ok, falha) => {
      const r = db.transaction(LOJA).objectStore(LOJA).get(CHAVE);
      r.onsuccess = () => ok(r.result);
      r.onerror = () => falha(r.error);
    });
    db.close();
    // Passa pela mesma conferência de um arquivo importado: uma base com defeito não quebra a página
    return { base: valor ? lerExportada(JSON.stringify(valor)) : baseVazia(), guarda: true };
  } catch {
    return { base: baseVazia(), guarda: false };
  }
}

export async function salvarBase(base: Base): Promise<boolean> {
  try {
    const db = await abrir();
    await new Promise<void>((ok, falha) => {
      const t = db.transaction(LOJA, "readwrite");
      t.objectStore(LOJA).put(base, CHAVE);
      t.oncomplete = () => ok();
      t.onerror = () => falha(t.error);
    });
    db.close();
    return true;
  } catch {
    return false;
  }
}

/** Baixa a base inteira como arquivo JSON (cópia de segurança, ou para levar para outro aparelho) */
export function exportar(base: Base) {
  const blob = new Blob([JSON.stringify(base, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `minha-rede-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
