/* Tradutor dos sites do Segredos Abertos (Brasil, Minas Nossa e Eleição 2026): português, inglês e espanhol.
 *
 * O site é escrito em português. Em inglês ou espanhol, este arquivo troca os textos da página pelos do dicionário
 * (i18n/en.json ou i18n/es.json, ao lado da página), inclusive os que aparecem depois (troca de aba, de ano...).
 * Dados oficiais (nomes de pessoas, empresas, partidos, categorias de despesa, ementas de leis) não estão no
 * dicionário e ficam como a fonte publicou.
 *
 * O dicionário usa o texto em português como chave, com os números trocados por {0}, {1}...: assim
 * "Sem gastos registrados em 2025." e "... em 2024." usam a mesma tradução. Em inglês os números mudam de formato
 * (1.234,5 vira 1,234.5); em espanhol ficam iguais ao português.
 *
 * A língua vem do endereço (?lang=en ou ?lang=es) ou da última escolha da pessoa. Sem nenhum dos dois, português.
 * Não usa a língua do navegador de propósito: o robô do Google lê em inglês, e a página principal tem que ser
 * indexada em português.
 */
(function (raiz) {
  "use strict";
  var LINGUAS = ["pt", "en", "es"];
  var NOMES = { pt: "Português", en: "English", es: "Español" };
  var HTML_LANG = { pt: "pt-BR", en: "en", es: "es" };

  /* ---------- Funções puras (também usadas pelos testes e pelo levantamento de textos, em Node) ---------- */

  var NUM = /\d+(?:[.,]\d+)*/g;

  /** Chave do dicionário: espaços juntados e números trocados por {0}, {1}... Devolve a chave e os números. */
  function chave(texto) {
    var nums = [];
    var k = String(texto).replace(/[\s  ]+/g, " ").trim().replace(NUM, function (m, pos, s) {
      // Número colado em barra ou hífen (CNPJ, data, "PL 2338/2023") vai inteiro, sem mexer no formato
      nums.push({ v: m, fixo: /[\/\-]$/.test(s.slice(0, pos)) || /^[\/\-]\d/.test(s.slice(pos + m.length)) });
      return "{" + (nums.length - 1) + "}";
    });
    return { k: k, nums: nums };
  }

  /** Número no formato do português (1.234,5) para o inglês (1,234.5). Outros números ficam como estão. */
  function numeroIngles(v) {
    if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(v) || /^\d+,\d+$/.test(v)) {
      return v.replace(/[.,]/g, function (c) { return c === "." ? "," : "."; });
    }
    return v;
  }

  function formatar(n, lingua) { return lingua === "en" && !n.fixo ? numeroIngles(n.v) : n.v; }

  /* Chaves com {*} servem para frases com um nome no meio ("Foto de {*}"): o {*} pega qualquer texto e passa igual
     (ou traduzido, se o texto pego for uma chave do dicionário, como o nome de um mês). */
  var curingas = typeof WeakMap === "function" ? new WeakMap() : null;
  var esc = function (p) { return p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); };
  function curinga(k, dic) {
    var lista = curingas && curingas.get(dic);
    if (!lista) {
      lista = Object.keys(dic).filter(function (x) { return x.indexOf("{*}") >= 0; }).map(function (x) {
        // {*} pega qualquer texto; {n} pega qualquer número, porque um nome com número ("Coligação 4") muda a contagem
        var partes = x.split(/(\{\*\}|\{\d+\})/), grupos = [], re = "";
        partes.forEach(function (p) {
          if (p === "{*}") { re += "(.+?)"; grupos.push("*"); }
          else if (/^\{\d+\}$/.test(p)) { re += "\\{(\\d+)\\}"; grupos.push(p.slice(1, -1)); }
          else re += esc(p);
        });
        return { re: new RegExp("^" + re + "$"), t: dic[x], grupos: grupos, fixo: x.replace(/\{\*\}/g, "").length };
      });
      // A chave com mais texto fixo ganha: "Em {*}," antes de "{*},"
      lista.sort(function (a, b) { return b.fixo - a.fixo; });
      if (curingas) curingas.set(dic, lista);
    }
    for (var i = 0; i < lista.length; i++) {
      var c = lista[i], m = c.re.exec(k);
      if (!m) continue;
      var nomes = [], nums = {};
      c.grupos.forEach(function (g, j) { if (g === "*") nomes.push(m[j + 1]); else nums[g] = m[j + 1]; });
      var n = 0;
      // O que o {*} pegou passa igual (nomes), a não ser que seja uma palavra do dicionário ("agosto", "Exterior").
      // Cada {n} da tradução vira o número que estava naquela posição do texto.
      return c.t.replace(/\{\*\}|\{(\d+)\}/g, function (t, d) {
        if (d != null) return nums[d] != null ? "{" + nums[d] + "}" : t;
        var x = nomes[n++];
        return dic[x] != null && x.indexOf("{") < 0 ? dic[x] : x;
      });
    }
    return null;
  }

  /** Traduz um texto. Devolve null quando o texto não está no dicionário. Mantém os espaços das pontas. */
  function traduzirTexto(texto, dic, lingua) {
    if (!texto || !/\S/.test(texto)) return null;
    var c = chave(texto);
    var t = dic[c.k];
    if (t == null) t = curinga(c.k, dic);
    if (t == null) {
      // Só número ou valor em reais ("R$ 1.234", "45%"): no inglês, muda o formato do número,
      // e qualquer texto só de números e sinais ("+10.376.694", "53,9 · 64,3", "1,5 p.p.")
      if (lingua === "en" && c.nums.length && !/[A-Za-zÀ-ÿ]/.test(c.k.replace(/R\$|p\.p\./g, ""))) t = c.k;
      else return null;
    }
    var out = t.replace(/\{(\d+)\}/g, function (m, i) { var n = c.nums[+i]; return n ? formatar(n, lingua) : m; });
    var ini = /^[\s ]*/.exec(texto)[0], fim = /[\s ]*$/.exec(texto)[0];
    return ini + out + fim;
  }

  var api = { LINGUAS: LINGUAS, NOMES: NOMES, chave: chave, numeroIngles: numeroIngles, traduzirTexto: traduzirTexto };
  if (typeof module === "object" && module.exports) { module.exports = api; return; }

  /* ---------- No navegador ---------- */

  var doc = raiz.document;
  function lerLingua() {
    var m = /[?&]lang=(pt|en|es)\b/.exec(raiz.location.search);
    if (m) { try { raiz.localStorage.setItem("lingua", m[1]); } catch (e) { /* sem armazenamento */ } return m[1]; }
    try { var s = raiz.localStorage.getItem("lingua"); if (LINGUAS.indexOf(s) >= 0) return s; } catch (e) { /* idem */ }
    return "pt";
  }
  var lingua = lerLingua();
  doc.documentElement.lang = HTML_LANG[lingua];
  api.lingua = lingua;
  api.t = function (s) { return s; };

  /** Endereço da mesma página em outra língua (o português fica sem ?lang, que é o endereço principal). */
  api.endereco = function (l) {
    var u = new URL(raiz.location.href);
    u.searchParams.delete("lang");
    if (l !== "pt") u.searchParams.set("lang", l);
    return u.toString();
  };
  api.trocar = function (l) {
    try { raiz.localStorage.setItem("lingua", l); } catch (e) { /* sem armazenamento */ }
    raiz.location.href = api.endereco(l);
  };

  /** Seletor de língua: três links (PT, EN, ES) dentro do elemento dado. */
  api.seletor = function (onde) {
    if (!onde || onde.querySelector(".linguas")) return;
    var box = doc.createElement("span");
    box.className = "linguas";
    box.setAttribute("translate", "no");
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", { pt: "Idioma", en: "Language", es: "Idioma" }[lingua]);
    LINGUAS.forEach(function (l) {
      var a = doc.createElement("a");
      a.href = api.endereco(l);
      a.lang = HTML_LANG[l];
      a.hreflang = HTML_LANG[l];
      a.textContent = l.toUpperCase();
      a.title = NOMES[l];
      if (l === lingua) a.setAttribute("aria-current", "true");
      a.addEventListener("click", function (e) { e.preventDefault(); api.trocar(l); });
      box.appendChild(a);
    });
    onde.appendChild(box);
  };
  raiz.SA_I18N = api;
  if (lingua === "pt") { api.pronto = Promise.resolve(); return; }

  // Enquanto o dicionário não chega, a página fica escondida (no máximo 2,5 s) para não piscar em português
  var estilo = doc.createElement("style");
  estilo.textContent = "html.i18n-espera body{visibility:hidden}";
  doc.head.appendChild(estilo);
  doc.documentElement.classList.add("i18n-espera");
  function mostrar() { doc.documentElement.classList.remove("i18n-espera"); }
  setTimeout(mostrar, 2500);

  var dic = {};
  var original = new WeakMap(); // nó de texto -> texto em português
  var escrito = new WeakMap();  // nó de texto -> o que este arquivo escreveu nele
  var attrOrig = new WeakMap(); // elemento -> { atributo: texto em português }
  var ATRIBUTOS = ["title", "aria-label", "placeholder", "alt"];
  var PULAR = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, CODE: 1, PRE: 1 };

  function pular(el) {
    for (var e = el; e && e.nodeType === 1; e = e.parentNode) {
      if (PULAR[e.nodeName] || e.getAttribute("translate") === "no" || (e.classList && e.classList.contains("notranslate"))) return true;
    }
    return false;
  }
  function textoOriginal(n) {
    var e = escrito.get(n);
    if (e !== undefined && e === n.nodeValue) return original.get(n);
    original.set(n, n.nodeValue);
    escrito.delete(n);
    return n.nodeValue;
  }
  function escrever(n, v) {
    if (n.nodeValue !== v) n.nodeValue = v;
    escrito.set(n, v);
  }

  /* Um elemento com vários pedaços de texto e nada mais (o React separa "Gastou {valor} em {ano}" em pedaços):
     tenta traduzir a frase inteira; se não achar, traduz pedaço por pedaço. */
  function traduzirElemento(el) {
    if (pular(el)) return;
    var textos = [], soTexto = true;
    for (var c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3) textos.push(c);
      else if (c.nodeType === 1) soTexto = false;
    }
    if (soTexto && textos.length > 1) {
      var orig = textos.map(textoOriginal);
      var t = traduzirTexto(orig.join(""), dic, lingua);
      if (t != null) {
        escrever(textos[0], t);
        for (var i = 1; i < textos.length; i++) escrever(textos[i], "");
        return;
      }
      textos.forEach(function (n, j) { var tt = traduzirTexto(orig[j], dic, lingua); escrever(n, tt != null ? tt : orig[j]); });
      return;
    }
    textos.forEach(function (n) {
      var o = textoOriginal(n);
      var tt = traduzirTexto(o, dic, lingua);
      if (tt != null) escrever(n, tt);
    });
  }

  function traduzirAtributos(el) {
    if (pular(el)) return;
    var guardados = attrOrig.get(el) || {};
    ATRIBUTOS.forEach(function (a) {
      var v = el.getAttribute(a);
      if (!v) return;
      var g = guardados[a];
      var o = g && g.escrito === v ? g.orig : v;
      var t = traduzirTexto(o, dic, lingua);
      if (t != null) { guardados[a] = { orig: o, escrito: t }; if (t !== v) el.setAttribute(a, t); }
    });
    attrOrig.set(el, guardados);
  }

  function percorrer(no) {
    if (no.nodeType === 3) { if (no.parentNode) traduzirElemento(no.parentNode); return; }
    if (no.nodeType !== 1) return;
    var w = doc.createTreeWalker(no, 1);
    for (var el = no; el; el = w.nextNode()) {
      if (PULAR[el.nodeName]) continue;
      traduzirElemento(el);
      traduzirAtributos(el);
    }
  }

  var meta = { description: 1, "og:description": 1, "og:title": 1, "twitter:title": 1, "twitter:description": 1 };
  function traduzirCabecalho() {
    var t = traduzirTexto(doc.title, dic, lingua);
    if (t != null) doc.title = t;
    Array.prototype.forEach.call(doc.querySelectorAll("meta[name],meta[property]"), function (m) {
      if (!meta[m.getAttribute("name") || m.getAttribute("property")]) return;
      var tt = traduzirTexto(m.getAttribute("content"), dic, lingua);
      if (tt != null) m.setAttribute("content", tt);
    });
  }

  function iniciar() {
    traduzirCabecalho();
    percorrer(doc.body);
    mostrar();
    new MutationObserver(function (lista) {
      lista.forEach(function (m) {
        if (m.type === "characterData") {
          var n = m.target;
          if (escrito.get(n) !== n.nodeValue && n.parentNode) traduzirElemento(n.parentNode);
        } else if (m.type === "attributes") {
          if (ATRIBUTOS.indexOf(m.attributeName) >= 0) traduzirAtributos(m.target);
        } else {
          if (m.target.nodeType === 1) traduzirElemento(m.target);
          Array.prototype.forEach.call(m.addedNodes, percorrer);
        }
      });
    }).observe(doc.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATRIBUTOS });
  }

  var base = (doc.currentScript && doc.currentScript.src) || raiz.location.href;
  api.pronto = fetch(new URL(lingua + ".json", base).toString())
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (d) {
      dic = d;
      api.t = function (s) { var t = traduzirTexto(s, dic, lingua); return t == null ? s : t; };
      if (doc.body) iniciar(); else doc.addEventListener("DOMContentLoaded", iniciar);
    })
    .catch(function (e) { console.warn("Tradução indisponível:", e); mostrar(); });
})(typeof window !== "undefined" ? window : this);
