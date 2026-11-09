/* Regra comum dos menus principais de todos os sites: todas as abas sempre à vista, sem rolar de lado e sem corte.
   O problema que motivou: com as abas novas (Minha rede, Licitações, Shows e cultura), as últimas ("Como funciona",
   "Minha rede") ficavam cortadas no fim da linha, sem nenhum sinal de que havia mais. Este ajudante confere a regra em
   larguras de celular pequeno até monitor grande, então uma aba nova que não couber quebra o teste, não o site. */
import { expect, type Page } from "@playwright/test";

export const LARGURAS = [320, 390, 700, 760, 1024, 1280, 1366, 1920];

export async function abasAVista(page: Page, seletorMenu: string, seletorAba = "a, button") {
  const original = page.viewportSize();
  try {
    for (const largura of LARGURAS) {
      await page.setViewportSize({ width: largura, height: 900 });
      await page.evaluate(() => window.scrollTo(0, 0));
      const problemas = await page.$eval(seletorMenu, (menu, sel) => {
        const out: string[] = [];
        menu.scrollIntoView({ block: "nearest" });
        if (menu.scrollWidth > menu.clientWidth + 1) out.push(`menu rola de lado (${menu.scrollWidth} > ${menu.clientWidth})`);
        const caixa = menu.getBoundingClientRect();
        const abas = [...menu.querySelectorAll<HTMLElement>(sel)];
        if (abas.length === 0) out.push("menu sem abas");
        for (const a of abas) {
          const r = a.getBoundingClientRect(); const nome = (a.textContent || "").trim();
          if (r.width < 1 || r.height < 1) { out.push(`${nome}: sem tamanho`); continue; }
          if (r.left < -1 || r.right > window.innerWidth + 1) out.push(`${nome}: fora da tela`);
          if (r.left < caixa.left - 1 || r.right > caixa.right + 1) out.push(`${nome}: cortada pelo menu`);
          const no = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          if (!no || !a.contains(no)) out.push(`${nome}: coberta por outro elemento`);
        }
        return out;
      }, seletorAba);
      expect(problemas, `largura ${largura}px`).toEqual([]);
    }
  } finally {
    if (original) await page.setViewportSize(original);
  }
}
