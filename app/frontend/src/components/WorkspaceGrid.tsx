import { workspaces, isHealthy, route } from '../state/signals';
import { WorkspaceCard } from './WorkspaceCard';

export function WorkspaceGrid() {
  const ws = workspaces.value;

  if (!ws.length) {
    return (
      <div>
        <div class="section-head">
          <span class="section-title">Workspaces</span>
        </div>
        <div class="empty empty-setup">
          <h2>No workspaces configured</h2>
          <p>Add workspace definitions to your <code>.env</code> file:</p>
          <pre>{`WORKSPOTS='[{"name":"my-project","container":"devcontainer-app-1","dir":"/workspaces/my-project"}]'`}</pre>
          <p>Then restart the launcher.</p>
          <div class="actions">
            <button class="btn btn-primary btn-sm" onClick={() => { route.value = '/discover'; window.location.hash = '#/discover'; }}>
              Or scan your environment
            </button>
          </div>
        </div>
      </div>
    );
  }

  const sorted = [...ws].sort((a, b) => {
    const d = (isHealthy(a) ? 0 : 1) - (isHealthy(b) ? 0 : 1);
    return d || a.name.localeCompare(b.name);
  });

  return (
    <div>
      <div class="section-head">
        <span class="section-title">Workspaces</span>
      </div>
      <div class="grid">
        {sorted.map(ws => (
          <WorkspaceCard key={ws.name} workspace={ws} />
        ))}
      </div>
    </div>
  );
}
