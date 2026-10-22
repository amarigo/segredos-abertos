// Service worker simples: guarda o site e os dados já vistos para abrir mais rápido e funcionar offline.
// Sempre tenta a rede primeiro (dados novos todo dia) e só guarda respostas boas (nunca uma página de erro).
// O mesmo arquivo serve o nacional (/) e o Minas Nossa (/mg/): cada um tem o próprio cache e só apaga os seus.
const ESCOPO = new URL(self.registration.scope).pathname; // "/segredos-abertos/" ou "/segredos-abertos/mg/"
const PREFIXO = ESCOPO.endsWith("/mg/") ? "mg-" : "sa-";
const CACHE = PREFIXO + "v3";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE && (k.startsWith(PREFIXO) || k === "sa-v2")).map((k) => caches.delete(k))))
    .then(() => self.clients.claim())
));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // O nacional não responde pelas páginas do Minas Nossa: elas têm o próprio service worker
  if (PREFIXO === "sa-" && url.pathname.startsWith(ESCOPO + "mg/")) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok && r.type === "basic") { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(e.request, c)); }
        return r;
      })
      .catch(() => caches.match(e.request).then((r) => r || Response.error()))
  );
});
