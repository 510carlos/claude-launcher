import { endedSessions, recentOpen, showNotice } from '../state/signals';
import { deleteEndedSessions } from '../api/sessions';
import { refresh } from '../state/polling';
import { SessionCard } from './SessionCard';

export function RecentSessions() {
  const ended = endedSessions.value;
  if (!ended.length) return null;

  async function handleClearAll(e: Event) {
    e.stopPropagation();
    const count = ended.length;
    showNotice(`Cleared ${count} sessions.`);
    try {
      await deleteEndedSessions();
      await refresh();
    } catch { showNotice('Failed to clear.', 'error'); await refresh(); }
  }

  return (
    <div>
      <div
        class={`section-head collapse-toggle ${recentOpen.value ? 'open' : ''}`}
        onClick={() => { recentOpen.value = !recentOpen.value; }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span class="arrow">&#9654;</span>
          <span class="section-title">Recent</span>
          <span class="section-count section-count-muted">{ended.length}</span>
        </div>
        {ended.length > 0 && (
          <button class="btn btn-danger btn-sm" onClick={handleClearAll}>Clear</button>
        )}
      </div>
      {recentOpen.value && (
        <div class="grid">
          {ended.map(s => (
            <SessionCard key={s.id} session={s} showDelete />
          ))}
        </div>
      )}
    </div>
  );
}
