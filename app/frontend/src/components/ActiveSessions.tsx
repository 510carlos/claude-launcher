import { activeSessions } from '../state/signals';
import { SessionCard } from './SessionCard';

export function ActiveSessions() {
  const active = activeSessions.value;
  if (!active.length) return null;

  const hasPending = active.some(s => s.status === 'pending');

  return (
    <div>
      <div class="section-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span class="section-title">Active Sessions</span>
          <span class={`section-count ${hasPending ? 'section-count-yellow' : 'section-count-green'}`}>
            {active.length}
          </span>
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
