const CACHE = 'claude-launcher-v1';
const SHELL = ['/', '/static/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API calls always go to network
  if (['/start', '/start-worktree', '/kill', '/status', '/sessions', '/workspots'].includes(url.pathname)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Shell: cache-first
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
