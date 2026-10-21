// Service worker simples: guarda o site e os dados já vistos para abrir mais rápido e funcionar offline.
const CACHE = "sa-v1";
self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(e.request, c)); return r; })
      .catch(() => caches.match(e.request))
  );
});
