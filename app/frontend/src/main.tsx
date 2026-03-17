import { render } from 'preact';
import { App } from './app';
import { route } from './state/signals';
import { loadFromCache, startPolling, refresh } from './state/polling';
import './app.css';

// Hash routing
function syncRoute() {
  const h = (window.location.hash || '#/').replace(/^#/, '');
  route.value = h === '/discover' ? '/discover' : '/';
}
window.addEventListener('hashchange', syncRoute);
syncRoute();

// Refresh on visibility change (returning from Claude app)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    refresh().catch(() => {});
  }
});

// Service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// Boot: load cached data first for instant render, then poll
loadFromCache();
render(<App />, document.getElementById('app')!);
startPolling();
