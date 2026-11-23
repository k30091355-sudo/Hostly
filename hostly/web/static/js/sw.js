// Hostly Service-Worker: Design-Dateien zwischenspeichern, ohne Internet eine Hinweis-Seite zeigen.
const CACHE = "hostly-v4";
const ASSETS = ["/static/css/hostly.css", "/static/js/hostly.js", "/static/js/htmx.min.js",
                "/static/favicon.svg", "/static/icon-192.png", "/offline"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith("/static/")) {
    // Design-Dateien: erst Netz, sonst Zwischenspeicher
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(req, copy));
      return res;
    }).catch(() => caches.match(req)));
  } else if (req.mode === "navigate") {
    // Seiten immer frisch vom Server (Coins, Status …); ohne Verbindung: Hinweis-Seite
    e.respondWith(fetch(req).catch(() => caches.match("/offline")));
  }
});
