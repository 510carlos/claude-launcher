import { workspaces, activeCount, route, newDiscoveryCount } from '../state/signals';

function navTo(target: '/' | '/discover' | '/updates') {
  route.value = target;
  window.location.hash = target === '/' ? '#/' : `#${target}`;
}

export function TopBar() {
  const count = newDiscoveryCount.value;
  const r = route.value;
  return (
    <nav class="topbar">
      <div onClick={() => navTo('/')} style={{ cursor: 'pointer' }}>
        <div class="brand-title">Claude Launcher</div>
        <div class="brand-sub">
          {workspaces.value.length} workspaces &middot; {activeCount.value} active
        </div>
      </div>
      <div class="topbar-actions">
        <button class="topbar-btn" style={{ position: 'relative' }}
          onClick={() => navTo(r === '/discover' ? '/' : '/discover')}>
          {r === '/discover' ? 'Dashboard' : 'Discover'}
          {count > 0 && r !== '/discover' && (
            <span style={{
              position: 'absolute', top: '-6px', right: '-6px',
              background: 'var(--accent)', color: '#fff',
              borderRadius: '999px', fontSize: '0.7rem', fontWeight: 800,
              minWidth: '18px', height: '18px', lineHeight: '18px',
              textAlign: 'center', padding: '0 4px',
            }}>{count}</span>
          )}
        </button>
        <button class="topbar-btn" onClick={() => navTo(r === '/updates' ? '/' : '/updates')}>
          {r === '/updates' ? 'Dashboard' : 'Updates'}
        </button>
      </div>
    </nav>
  );
}
