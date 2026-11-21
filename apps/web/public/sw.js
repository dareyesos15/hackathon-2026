/* Service worker de Dacora (research R4): mejora progresiva para recargar sin red.
 * Solo se registra en contextos seguros (https o localhost). Nunca cachea la API:
 * los reportes sin conexión viven en IndexedDB (outbox), no aquí. */
const CACHE = "dacora-shell-v1";
const SHELL = ["/", "/reportar/", "/manifest.json", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/openapi.json") return;

  // Recursos con hash (inmutables): primero caché.
  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/vendor/")) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(event.request, copy));
            return res;
          }),
      ),
    );
    return;
  }

  // Páginas: primero red, y si no hay señal, la copia guardada.
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(event.request, copy));
        return res;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("/reportar/"))),
  );
});
