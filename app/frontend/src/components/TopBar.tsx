import { workspaces, activeCount, route, newDiscoveryCount } from '../state/signals';

export function TopBar() {
  const count = newDiscoveryCount.value;
  return (
    <nav class="topbar">
      <div>
        <div class="brand-title">Claude Launcher</div>
        <div class="brand-sub">
          {workspaces.value.length} workspaces &middot; {activeCount.value} active
        </div>
      </div>
      <div class="topbar-actions">
        <button
          class="topbar-btn"
          style={{ position: 'relative' }}
          onClick={() => {
            route.value = route.value === '/discover' ? '/' : '/discover';
            window.location.hash = route.value === '/discover' ? '#/discover' : '#/';
          }}
        >
          {route.value === '/discover' ? 'Dashboard' : 'Discover'}
          {count > 0 && route.value !== '/discover' && (
            <span style={{
              position: 'absolute', top: '-6px', right: '-6px',
              background: 'var(--accent)', color: '#fff',
              borderRadius: '999px', fontSize: '0.7rem', fontWeight: 800,
              minWidth: '18px', height: '18px', lineHeight: '18px',
              textAlign: 'center', padding: '0 4px',
            }}>{count}</span>
          )}
        </button>
      </div>
    </nav>
  );
}
