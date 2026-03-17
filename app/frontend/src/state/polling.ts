import { listWorkspaces, getHealth } from '../api/workspaces';
import { listSessions } from '../api/sessions';
import { workspaces, sessions, health, activeSessions, clearPhaseTimer, pendingPhases } from './signals';

let timer: ReturnType<typeof setTimeout> | null = null;
let lastHash = '';

function hashState(ws: unknown[], h: unknown[], s: unknown[]) {
  return JSON.stringify([ws, h, s]);
}

export async function refresh(): Promise<boolean> {
  const [ws, hl, ss] = await Promise.all([
    listWorkspaces(), getHealth(), listSessions(),
  ]);
  const hash = hashState(ws, hl, ss);
  if (hash === lastHash) return false;
  lastHash = hash;
  workspaces.value = ws;
  health.value = hl;
  sessions.value = ss;

  // Cache for instant next load
  try {
    localStorage.setItem('launcher-cache', JSON.stringify({ workspaces: ws, health: hl, sessions: ss }));
  } catch { /* quota exceeded or private mode */ }

  // Clean up phase timers for sessions no longer pending
  for (const id of Object.keys(pendingPhases.value)) {
    const s = ss.find(s => s.id === id);
    if (!s || s.status !== 'pending') clearPhaseTimer(id);
  }

  return true;
}

export function loadFromCache() {
  try {
    const cached = localStorage.getItem('launcher-cache');
    if (cached) {
      const data = JSON.parse(cached);
      workspaces.value = data.workspaces || [];
      health.value = data.health || [];
      sessions.value = data.sessions || [];
    }
  } catch { /* corrupt cache */ }
}

export function startPolling() {
  const poll = async () => {
    try { await refresh(); } catch (e) { console.error('Poll failed:', e); }
    const fast = activeSessions.value.some(s => s.status === 'pending');
    timer = setTimeout(poll, fast ? 3000 : 15000);
  };
  poll();
}

export function stopPolling() {
  if (timer) { clearTimeout(timer); timer = null; }
}
