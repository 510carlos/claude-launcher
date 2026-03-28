import { listWorkspaces, getHealth } from '../api/workspaces';
import { listSessions } from '../api/sessions';
import { runDiscovery } from '../api/discovery';
import { api } from '../api/client';
import { workspaces, sessions, health, activeSessions, clearPhaseTimer, pendingPhases, discoveryResult, scanning, appName } from './signals';

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

async function backgroundScan() {
  if (scanning.value) return;
  scanning.value = true;
  try {
    discoveryResult.value = await runDiscovery();
  } catch (e) {
    console.error('Background scan failed:', e);
  } finally {
    scanning.value = false;
  }
}

export function startPolling() {
  // Fetch app name once
  api<{ app_name: string }>('/api/config').then(c => { appName.value = c.app_name; }).catch(() => {});

  const poll = async () => {
    try { await refresh(); } catch (e) { console.error('Poll failed:', e); }
    const fast = activeSessions.value.some(s => s.status === 'pending');
    timer = setTimeout(poll, fast ? 3000 : 15000);
  };
  poll();
  // Silently scan for new workspots after a short delay so it doesn't block initial load
  setTimeout(backgroundScan, 3000);
}

export function stopPolling() {
  if (timer) { clearTimeout(timer); timer = null; }
}
