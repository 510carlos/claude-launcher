import { signal, computed } from '@preact/signals';
import type { Workspace, Session, HealthStatus, DiscoveryResult } from '../types';

// Core data
export const workspaces = signal<Workspace[]>([]);
export const sessions = signal<Session[]>([]);
export const health = signal<HealthStatus[]>([]);

// Derived
export const activeSessions = computed(() =>
  sessions.value
    .filter(s => s.status === 'running' || s.status === 'pending')
    .sort((a, b) => {
      const w: Record<string, number> = { running: 0, pending: 1 };
      return (w[a.status] ?? 9) - (w[b.status] ?? 9)
        || new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    })
);

export const endedSessions = computed(() =>
  sessions.value
    .filter(s => s.status === 'stopped' || s.status === 'failed')
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
);

export const activeCount = computed(() => activeSessions.value.length);

// UI state
export const route = signal<'/' | '/discover'>('/');
export const notices = signal<{ id: number; msg: string; kind: 'info' | 'error' }[]>([]);
export const discoveryResult = signal<DiscoveryResult | null>(null);
export const scanning = signal(false);
export const recentOpen = signal(false);
export const optionsWorkspace = signal<string | null>(null);

// Progress phase tracking for pending sessions
export const pendingPhases = signal<Record<string, { phase: number; startedAt: number }>>({});

// Helpers
export function healthOf(name: string): HealthStatus | undefined {
  return health.value.find(h => h.workspot === name);
}

export function isHealthy(ws: Workspace): boolean {
  const h = healthOf(ws.name);
  return !!(h && h.runtime_ok && h.repo_exists && h.git_ok && h.claude_bin_ok && h.auth_ok);
}

export function wsErrors(ws: Workspace): string[] {
  const h = healthOf(ws.name);
  if (!h) return ['Health unavailable'];
  if (h.issues && h.issues.length) return h.issues;
  const e: string[] = [];
  if (!h.claude_bin_ok) e.push('Claude CLI not found');
  if (!h.auth_ok) e.push('Not authenticated');
  if (!h.git_ok) e.push('Git not available');
  if (!h.repo_exists) e.push('Directory not found');
  if (!h.runtime_ok) e.push(ws.runtime === 'host' ? 'Host unreachable' : 'Container not running');
  return e;
}

let _noticeId = 0;
export function showNotice(msg: string, kind: 'info' | 'error' = 'info') {
  const id = ++_noticeId;
  notices.value = [...notices.value, { id, msg, kind }];
  if (kind === 'info') {
    setTimeout(() => {
      notices.value = notices.value.filter(n => n.id !== id);
    }, 4000);
  }
}

export function dismissNotice(id: number) {
  notices.value = notices.value.filter(n => n.id !== id);
}

export function startPhaseTimer(sessionId: string) {
  pendingPhases.value = {
    ...pendingPhases.value,
    [sessionId]: { phase: 0, startedAt: Date.now() },
  };
  const advance = () => {
    const p = pendingPhases.value[sessionId];
    if (!p) return;
    const elapsed = Date.now() - p.startedAt;
    let changed = false;
    if (p.phase === 0 && elapsed >= 3000) { p.phase = 1; changed = true; }
    if (p.phase === 1 && elapsed >= 8000) { p.phase = 2; changed = true; }
    if (changed) {
      pendingPhases.value = { ...pendingPhases.value };
    }
    if (p.phase < 2) setTimeout(advance, 1000);
  };
  setTimeout(advance, 1000);
}

export function clearPhaseTimer(sessionId: string) {
  const { [sessionId]: _, ...rest } = pendingPhases.value;
  pendingPhases.value = rest;
}
