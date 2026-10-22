// Service worker simples: guarda o site e os dados já vistos para abrir mais rápido e funcionar offline.
// Sempre tenta a rede primeiro (dados novos todo dia) e só guarda respostas boas (nunca uma página de erro).
const CACHE = "sa-v2";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())
));
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok && r.type === "basic") { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(e.request, c)); }
        return r;
      })
      .catch(() => caches.match(e.request).then((r) => r || Response.error()))
  );
});
