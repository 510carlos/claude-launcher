import type { Workspace } from '../types';
import { healthOf, isHealthy, wsErrors, optionsWorkspace, sessions, showNotice, startPhaseTimer } from '../state/signals';
import { refresh } from '../state/polling';
import { startSession } from '../api/sessions';
import * as workspacesApi from '../api/workspaces';
import { randomLabel } from '../utils';
import { HealthPill } from './HealthPill';
import { OptionsForm } from './OptionsForm';

interface Props {
  workspace: Workspace;
}

export function WorkspaceCard({ workspace: ws }: Props) {
  const h = healthOf(ws.name);
  const ok = isHealthy(ws);
  const errs = wsErrors(ws);
  const activeCount = sessions.value.filter(
    s => s.workspot === ws.name && (s.status === 'running' || s.status === 'pending')
  ).length;
  const formOpen = ok && optionsWorkspace.value === ws.name;

  async function quickLaunch() {
    if (!ok) { showNotice('Workspace needs attention.', 'error'); return; }
    const label = randomLabel();
    await doStart(label, null, false);
  }

  function toggleOptions() {
    if (!ok) return;
    optionsWorkspace.value = optionsWorkspace.value === ws.name ? null : ws.name;
  }

  async function doStart(label: string, branch: string | null, worktree: boolean) {
    const tempId = 'pending-' + Date.now();
    sessions.value = [{
      id: tempId, workspot: ws.name, label, branch, status: 'pending' as const,
      url: null, created_at: new Date().toISOString(),
      server_key: '', runtime: ws.runtime, container: ws.container,
      repo_root: ws.dir, working_dir: ws.dir, worktree_path: null,
      last_seen_at: null, source: 'launcher', server_session_name: null,
      output_file: null, metadata: {},
    }, ...sessions.value];
    startPhaseTimer(tempId);
    optionsWorkspace.value = null;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    showNotice(`Starting ${worktree ? 'worktree ' : ''}session in ${ws.name}...`);

    try {
      const r = await startSession({ workspot: ws.name, worktree, label, branch: branch ?? undefined });
      sessions.value = sessions.value.filter(s => s.id !== tempId);
      if (r.status !== 'ok') {
        showNotice(r.message || 'Failed to start session.', 'error');
        return;
      }
      showNotice(r.url ? 'Session ready!' : (r.message || 'Session started.'));
      await refresh();
    } catch {
      sessions.value = sessions.value.filter(s => s.id !== tempId);
      showNotice('Connection failed.', 'error');
    }
  }

  async function handleFix() {
    showNotice(`Fixing ${ws.name}...`);
    try {
      const r = await workspacesApi.fixWorkspot(ws.name);
      if (r.status !== 'ok') { showNotice(r.message || 'Fix failed.', 'error'); return; }
      const fixes = r.fixes || [];
      await refresh();
      showNotice(fixes.length ? `Fixed: ${fixes.join(', ')}` : `Could not auto-fix ${ws.name}.`, fixes.length ? 'info' : 'error');
    } catch { showNotice('Fix failed.', 'error'); }
  }

  async function handleRecheck() {
    showNotice(`Rechecking ${ws.name}...`);
    try {
      await workspacesApi.recheckWorkspot(ws.name);
      await refresh();
    } catch { showNotice('Recheck failed.', 'error'); }
  }

  async function handleRemove() {
    showNotice(`Removed "${ws.name}".`);
    try {
      await workspacesApi.removeWorkspot(ws.name);
      await refresh();
    } catch { showNotice('Failed to remove.', 'error'); await refresh(); }
  }

  return (
    <article class="card">
      <div class="card-head">
        <div>
          <div class="card-title">{ws.name}</div>
          <div class="card-meta">
            {ws.container || 'Host'}{activeCount ? ` \u00b7 ${activeCount} active` : ''}
          </div>
        </div>
        <HealthPill health={h} />
      </div>

      <div class="card-path" title={ws.dir}>{ws.dir}</div>

      {!ok && errs.length > 0 && (
        <div class="errors">
          {errs.map((e, i) => <div key={i} class="err">{e}</div>)}
        </div>
      )}

      <div class="actions">
        <button class="btn btn-primary btn-sm" onClick={quickLaunch} disabled={!ok}>Launch</button>
        <button class="btn btn-ghost btn-sm" onClick={toggleOptions} disabled={!ok}>Options</button>
        {!ok && (
          <>
            <button class="btn btn-primary btn-sm" onClick={handleFix}>Fix</button>
            <button class="btn btn-ghost btn-sm" onClick={handleRecheck}>Recheck</button>
          </>
        )}
        {ws.source === 'file' && (
          <button class="btn btn-danger btn-sm" onClick={handleRemove}>Remove</button>
        )}
      </div>

      {formOpen && (
        <OptionsForm
          onStart={(label, branch, worktree) => doStart(label, branch, worktree)}
          onCancel={() => { optionsWorkspace.value = null; }}
        />
      )}
    </article>
  );
}
