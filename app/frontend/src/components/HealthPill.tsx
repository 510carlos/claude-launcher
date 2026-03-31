import type { HealthStatus } from '../types';

interface Props {
  health: HealthStatus | undefined;
  sessionState?: 'idle' | 'pending' | 'running';
}

export function HealthPill({ health: h, sessionState }: Props) {
  if (!h) return <span class="pill">Unknown</span>;
  if (!h.runtime_ok || !h.repo_exists || !h.git_ok || !h.claude_bin_ok || !h.auth_ok) {
    return <span class="pill pill-red">Needs attention</span>;
  }
  if (sessionState === 'running') return <span class="pill pill-green">running</span>;
  if (sessionState === 'pending') return <span class="pill pill-yellow">pending</span>;
  return <span class="pill pill-green">Ready</span>;
}
