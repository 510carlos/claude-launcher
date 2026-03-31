/// <reference lib="webworker" />
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';

declare const self: ServiceWorkerGlobalScope;

// Workbox injects the precache manifest here at build time
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

const API_PATHS = ['/api/', '/start', '/start-worktree', '/kill', '/status', '/sessions', '/workspots'];

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // API endpoints: always network, never cache
  if (url.pathname.startsWith('/api/') || API_PATHS.includes(url.pathname)) {
    e.respondWith(fetch(e.request));
    return;
  }

  // HTML (navigation): network-first, cache fallback
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const clone = res.clone();
          caches.open('claude-launcher-nav').then((c) => c.put(e.request, clone));
          return res;
        })
        .catch(async () => {
          const cached = await caches.match(e.request) || await caches.match('/');
          return cached || new Response('Offline', { status: 503, headers: { 'Content-Type': 'text/plain' } });
        })
    );
    return;
  }

  // Everything else (non-precached assets): let Workbox handle via precache,
  // or fall through to network
});
