import { render } from 'preact';
import { App } from './app';
import { route, installPrompt } from './state/signals';
import { loadFromCache, startPolling, refresh } from './state/polling';
import './app.css';

// PWA install prompt — stash the event so the UI can trigger it
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  installPrompt.value = e;
});

// Hash routing
function syncRoute() {
  const h = (window.location.hash || '#/').replace(/^#/, '');
  route.value = h === '/discover' ? '/discover' : h === '/updates' ? '/updates' : '/';
}
window.addEventListener('hashchange', syncRoute);
syncRoute();

// Refresh on visibility change (returning from Claude app)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    refresh().catch(() => {});
  }
});

// Service worker (Workbox-powered, built by vite-plugin-pwa)
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js', { type: 'module' }).catch(() => {});
}

// Boot: load cached data first for instant render, then poll
loadFromCache();
render(<App />, document.getElementById('app')!);
startPolling();
