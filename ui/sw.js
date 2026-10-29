const CACHE_NAME = 'tzi-pwa-v8';
const STATIC_ASSETS = [
  '/manifest.webmanifest',
  '/icon.svg'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (['/login', '/register', '/logout', '/trial', '/admin', '/quiz.wasm'].some(p => url.pathname.startsWith(p))) return;

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then(res => {
        if (res.ok && !res.redirected) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, clone));
        }
        return res;
      }).catch(async () => {
        const cached = await caches.match(req);
        if (cached) return cached;
        return caches.match('/');
      })
    );
    return;
  }

  if (url.pathname === '/api/sources' || url.pathname === '/api/questions' || url.pathname === '/api/recall') {
    event.respondWith(
      caches.open(CACHE_NAME).then(async cache => {
        const fetchPromise = fetch(req).then(networkRes => {
          if (networkRes.ok) cache.put(req, networkRes.clone());
          return networkRes;
        }).catch(() => cache.match(req));
        return fetchPromise;
      })
    );
    return;
  }

  event.respondWith(
    fetch(req).catch(() => caches.match(req))
  );
});
