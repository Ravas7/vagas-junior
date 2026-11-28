/* Painel instalável (PWA): guarda uma cópia do painel e da última lista de vagas.
 * Com internet, busca sempre a versão nova (rede primeiro) e atualiza a cópia.
 * Sem internet, abre com a cópia. Só arquivos do próprio site: Firebase e links externos passam direto.
 * Mudou a lista de arquivos? Troque a VERSAO para limpar as cópias antigas. */
const VERSAO = "ragas-v3";
const PAINEL = [
  "./", "index.html", "style.css", "app.js", "store.js", "sync.js", "login.js", "perfil.js", "admin.js", "kanban.js", "conta.js", "dados.html", "tema.js", "pwa.js",
  "firebase-config.js", "perfil-padrao.json", "manifest.webmanifest", "favicon.svg", "icon-192.png", "data/jobs.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSAO).then((c) => c.addAll(PAINEL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== VERSAO).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith((async () => {
    const cache = await caches.open(VERSAO);
    try {
      const res = await fetch(req);
      if (res.ok) cache.put(req.url.split("?")[0], res.clone());       // guarda sem o "?t=" de quebrar cache
      return res;
    } catch {
      const hit = await cache.match(req, { ignoreSearch: true }) || (req.mode === "navigate" && await cache.match("index.html"));
      return hit || Response.error();
    }
  })());
});
