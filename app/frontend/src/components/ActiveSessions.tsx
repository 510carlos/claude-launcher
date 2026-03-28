import { activeSessions, showNotice } from '../state/signals';
import { killSession } from '../api/sessions';
import { refresh } from '../state/polling';
import { SessionCard } from './SessionCard';

export function ActiveSessions() {
  const active = activeSessions.value;
  if (!active.length) return null;

  const hasPending = active.some(s => s.status === 'pending');

  async function handleStopAll() {
    try {
      showNotice('Stopping all sessions...');
      for (const s of active) {
        await killSession(s.id);
      }
      await refresh();
    } catch {
      showNotice('Failed to stop some sessions.', 'error');
    }
  }

  return (
    <div>
      <div class="section-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span class="section-title">Active Sessions</span>
          <span class={`section-count ${hasPending ? 'section-count-yellow' : 'section-count-green'}`}>
            {active.length}
          </span>
          {active.length > 1 && (
            <button class="btn btn-danger btn-sm" onClick={handleStopAll}>
              Stop All
            </button>
          )}
        </div>
      </div>
      <div class="grid">
        {active.map(s => (
          <SessionCard key={s.id} session={s} showKill />
        ))}
      </div>
    </div>
  );
}
