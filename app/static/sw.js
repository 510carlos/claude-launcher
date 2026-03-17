const CACHE = 'claude-launcher-v3';
const SHELL = ['/', '/static/manifest.json'];
const API_PATHS = ['/api/', '/start', '/start-worktree', '/kill', '/status', '/sessions', '/workspots'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API endpoints: always network
  if (url.pathname.startsWith('/api/') || API_PATHS.includes(url.pathname)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // HTML (navigation): network-first, cache fallback
  if (e.request.mode === 'navigate' || url.pathname === '/') {
    e.respondWith(
      fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }

  // Static assets: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
      const clone = res.clone();
      caches.open(CACHE).then(c => c.put(e.request, clone));
      return res;
    }))
  );
});
