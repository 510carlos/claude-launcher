import { workspaces, activeCount, route } from '../state/signals';

export function TopBar() {
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
          onClick={() => {
            route.value = route.value === '/discover' ? '/' : '/discover';
            window.location.hash = route.value === '/discover' ? '#/discover' : '#/';
          }}
        >
          {route.value === '/discover' ? 'Dashboard' : 'Discover'}
        </button>
      </div>
    </nav>
  );
}
