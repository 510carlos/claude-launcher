import { route, newDiscoveryCount } from '../state/signals';

function navigate(path: '/' | '/discover' | '/updates') {
  route.value = path;
  window.location.hash = path === '/' ? '' : `#${path}`;
}

export function BottomNav() {
  const current = route.value;

  return (
    <nav class="glass-panel bottom-nav">
      <button class={`nav-item${current === '/' ? ' active' : ''}`} onClick={() => navigate('/')}>
        <svg viewBox="0 0 24 24">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
        </svg>
        Workspaces
        {current === '/' && <span class="active-dot" />}
      </button>

      <button class={`nav-item${current === '/discover' ? ' active' : ''}`} onClick={() => navigate('/discover')} style={{ position: 'relative' }}>
        <svg viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" />
          <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
        </svg>
        Discover
        {current === '/discover' && <span class="active-dot" />}
        {current !== '/discover' && newDiscoveryCount.value > 0 && (
          <span style={{
            position: 'absolute', top: '6px', right: 'calc(50% - 24px)',
            minWidth: '16px', height: '16px', padding: '0 4px',
            borderRadius: '999px', background: 'var(--accent)',
            color: '#fff', fontSize: '9px', fontWeight: '800',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>{newDiscoveryCount.value}</span>
        )}
      </button>

      <button class={`nav-item${current === '/updates' ? ' active' : ''}`} onClick={() => navigate('/updates')}>
        <svg viewBox="0 0 24 24">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        Updates
        {current === '/updates' && <span class="active-dot" />}
      </button>
    </nav>
  );
}
