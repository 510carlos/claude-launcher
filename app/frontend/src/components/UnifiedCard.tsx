import type { Workspace } from '../types';
import {
  healthOf, isHealthy, wsErrors,
  optionsWorkspace, resumeWorkspace, menuWorkspace,
  sessions, showNotice, startPhaseTimer, clearPhaseTimer,
} from '../state/signals';
import { refresh } from '../state/polling';
import { startSession, resumeSession, killSession as apiKill } from '../api/sessions';
import * as workspacesApi from '../api/workspaces';
import { randomLabel, fmtTime } from '../utils';
import { HealthPill } from './HealthPill';
import { OptionsForm } from './OptionsForm';
import { ConversationPicker } from './ConversationPicker';
import { ProgressSteps } from './ProgressSteps';

interface Props {
  workspace: Workspace;
}

export function UnifiedCard({ workspace: ws }: Props) {
  const h = healthOf(ws.name);
  const ok = isHealthy(ws);
  const errs = wsErrors(ws);

  // Derive session state for this workspace
  const allActive = sessions.value.filter(
    s => s.workspot === ws.name && (s.status === 'running' || s.status === 'pending')
  );
  const runningSessions = allActive.filter(s => s.status === 'running' && s.url);
  const pendingSessions = allActive.filter(s => s.status === 'pending');
  const primarySession = runningSessions[0] ?? pendingSessions[0] ?? null;
  const secondarySessions = allActive.filter(s => s !== primarySession);
  const hasPending = pendingSessions.length > 0;
  const hasRunning = runningSessions.length > 0;

  // Card state
  const cardState = !ok ? 'unhealthy' : hasRunning ? 'running' : hasPending ? 'pending' : 'idle';
  const sessionState = hasRunning ? 'running' as const : hasPending ? 'pending' as const : 'idle' as const;

  // Panel state
  const menuOpen = menuWorkspace.value === ws.name;
  const formOpen = ok && optionsWorkspace.value === ws.name;
  const resumeOpen = ok && resumeWorkspace.value === ws.name;

  function toggleMenu() {
    if (menuOpen) { menuWorkspace.value = null; return; }
    optionsWorkspace.value = null;
    resumeWorkspace.value = null;
    menuWorkspace.value = ws.name;
  }

  function toggleOptions() {
    menuWorkspace.value = null;
    resumeWorkspace.value = null;
    optionsWorkspace.value = optionsWorkspace.value === ws.name ? null : ws.name;
  }

  function toggleResume() {
    menuWorkspace.value = null;
    optionsWorkspace.value = null;
    resumeWorkspace.value = resumeWorkspace.value === ws.name ? null : ws.name;
  }

  async function quickLaunch() {
    if (!ok) { showNotice('Workspace needs attention.', 'error'); return; }
    await doStart(randomLabel(), null, false);
  }

  async function doStart(label: string, branch: string | null, worktree: boolean, devcontainer = false) {
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
    menuWorkspace.value = null;
    const mode = devcontainer ? 'container ' : worktree ? 'worktree ' : '';
    showNotice(`Starting ${mode}session in ${ws.name}...`);

    try {
      const r = await startSession({ workspot: ws.name, worktree, devcontainer, label, branch: branch ?? undefined });
      sessions.value = sessions.value.filter(s => s.id !== tempId);
      if (r.status !== 'ok') { showNotice(r.message || 'Failed to start session.', 'error'); return; }
      showNotice(r.url ? 'Session ready!' : (r.message || 'Session started.'));
      await refresh();
    } catch {
      sessions.value = sessions.value.filter(s => s.id !== tempId);
      showNotice('Connection failed.', 'error');
    }
  }

  async function doResume(conversationId: string) {
    const tempId = 'pending-' + Date.now();
    sessions.value = [{
      id: tempId, workspot: ws.name, label: 'Resuming...', branch: null, status: 'pending' as const,
      url: null, created_at: new Date().toISOString(),
      server_key: '', runtime: ws.runtime, container: ws.container,
      repo_root: ws.dir, working_dir: ws.dir, worktree_path: null,
      last_seen_at: null, source: 'resume', server_session_name: null,
      output_file: null, metadata: {},
    }, ...sessions.value];
    startPhaseTimer(tempId);
    resumeWorkspace.value = null;
    menuWorkspace.value = null;
    showNotice(`Resuming conversation in ${ws.name}...`);

    try {
      const r = await resumeSession({ workspot: ws.name, conversation_id: conversationId });
      sessions.value = sessions.value.filter(s => s.id !== tempId);
      if (r.status !== 'ok') { showNotice(r.message || 'Failed to resume.', 'error'); return; }
      showNotice(r.url ? 'Session resumed!' : (r.message || 'Resume started.'));
      await refresh();
    } catch {
      sessions.value = sessions.value.filter(s => s.id !== tempId);
      showNotice('Resume failed.', 'error');
    }
  }

  async function handleKill(sessionId: string) {
    const found = sessions.value.find(x => x.id === sessionId);
    if (found) found.status = 'stopped';
    sessions.value = [...sessions.value];
    clearPhaseTimer(sessionId);
    showNotice('Stopped.');
    try {
      await apiKill(sessionId);
      await refresh();
    } catch { showNotice('Failed to stop.', 'error'); await refresh(); }
  }

  async function launchInContainer() {
    menuWorkspace.value = null;
    await doStart(randomLabel(), null, false, true);
  }

  async function handleFix() {
    showNotice(`Fixing ${ws.name}...`);
    try {
      const r = await workspacesApi.fixWorkspot(ws.name);
      if (r.status !== 'ok') { showNotice(r.message || 'Fix failed.', 'error'); return; }
      const fixes = (r as any).fixes || [];
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
    menuWorkspace.value = null;
    showNotice(`Removed "${ws.name}".`);
    try {
      await workspacesApi.removeWorkspot(ws.name);
      await refresh();
    } catch { showNotice('Failed to remove.', 'error'); await refresh(); }
  }

  return (
    <article class={`unified-card unified-card--${cardState}`}>
      {/* Header */}
      <div class="card-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div class="card-title">{ws.name}</div>
          <div class="card-meta">
            {primarySession
              ? <>{primarySession.label || ws.name} &middot; {fmtTime(primarySession.created_at)}</>
              : <>{h?.branch && <span>{h.branch} &middot; </span>}{ws.container || 'Host'}</>
            }
            {allActive.length > 1 && <span class="session-count-badge">{allActive.length}</span>}
          </div>
        </div>
        <HealthPill health={h} sessionState={ok ? sessionState : undefined} />
      </div>

      {/* Path (idle and unhealthy only) */}
      {(cardState === 'idle' || cardState === 'unhealthy') && (
        <div class="card-path" title={ws.dir}>{ws.dir}</div>
      )}

      {/* Errors (unhealthy) */}
      {cardState === 'unhealthy' && errs.length > 0 && (
        <div class="errors">
          {errs.map((e, i) => <div key={i} class="err">{e}</div>)}
        </div>
      )}

      {/* Progress (pending) */}
      {cardState === 'pending' && primarySession && (
        <ProgressSteps sessionId={primarySession.id} />
      )}

      {/* Open in Claude (running) */}
      {cardState === 'running' && primarySession?.url && (
        <>
          <a class="open-btn" href={primarySession.url} target="_blank" rel="noopener">
            Open in Claude
          </a>
          <div class="open-hint">
            If it doesn't open directly, check your sessions in the Claude app.
          </div>
        </>
      )}

      {/* Secondary sessions (multiple active) */}
      {secondarySessions.length > 0 && secondarySessions.map(s => (
        <div key={s.id} class="session-mini">
          <div class="session-mini-info">
            <span class="session-mini-label">{s.label || 'session'}</span>
            <span class="session-mini-time">{fmtTime(s.created_at)}</span>
          </div>
          <div class="session-mini-actions">
            {s.url && <a class="btn btn-ghost btn-sm" href={s.url} target="_blank" rel="noopener">Open</a>}
            <button class="btn btn-danger btn-sm" onClick={() => handleKill(s.id)}>Stop</button>
          </div>
        </div>
      ))}

      {/* Actions */}
      {cardState === 'idle' && (
        <div class="unified-card-actions">
          <button class="btn btn-primary btn-launch" onClick={quickLaunch}>Launch</button>
          <button class="btn btn-ghost btn-menu" onClick={toggleMenu}>&middot;&middot;&middot;</button>
        </div>
      )}

      {cardState === 'pending' && (
        <div class="unified-card-actions unified-card-actions--end">
          <button class="btn btn-danger btn-sm" onClick={() => primarySession && handleKill(primarySession.id)}>Stop</button>
        </div>
      )}

      {cardState === 'running' && (
        <div class="unified-card-actions">
          <button class="btn btn-ghost btn-sm" onClick={quickLaunch} disabled={hasPending}>New</button>
          <button class="btn btn-danger btn-sm" onClick={() => primarySession && handleKill(primarySession.id)}>Stop</button>
          <div style={{ flex: 1 }} />
          <button class="btn btn-ghost btn-menu" onClick={toggleMenu}>&middot;&middot;&middot;</button>
        </div>
      )}

      {cardState === 'unhealthy' && (
        <div class="unified-card-actions">
          <button class="btn btn-primary btn-sm" onClick={handleFix}>Fix</button>
          <button class="btn btn-ghost btn-sm" onClick={handleRecheck}>Recheck</button>
          {ws.source === 'file' && (
            <button class="btn btn-danger btn-sm" onClick={handleRemove}>Remove</button>
          )}
        </div>
      )}

      {/* Overflow menu */}
      {menuOpen && (
        <div class="card-menu">
          <button class="card-menu-item" onClick={toggleOptions}>Launch with options</button>
          {ws.runtime === 'host' && (
            <button class="card-menu-item" onClick={toggleResume}>Resume conversation</button>
          )}
          {h?.has_devcontainer && (
            <button class="card-menu-item" onClick={launchInContainer}>Launch in container</button>
          )}
          {ws.source === 'file' && (
            <button class="card-menu-item card-menu-item--danger" onClick={handleRemove}>Remove workspace</button>
          )}
        </div>
      )}

      {/* Inline panels */}
      {formOpen && (
        <OptionsForm
          onStart={(label, branch, worktree) => doStart(label, branch, worktree)}
          onCancel={() => { optionsWorkspace.value = null; }}
        />
      )}
      {resumeOpen && (
        <ConversationPicker
          workspot={ws.name}
          onResume={(id) => doResume(id)}
          onCancel={() => { resumeWorkspace.value = null; }}
        />
      )}
    </article>
  );
}
