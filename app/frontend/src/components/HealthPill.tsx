import type { HealthStatus } from '../types';

interface Props {
  health: HealthStatus | undefined;
}

export function HealthPill({ health: h }: Props) {
  if (!h) return <span class="pill">Unknown</span>;
  if (!h.runtime_ok || !h.repo_exists || !h.git_ok || !h.claude_bin_ok || !h.auth_ok) {
    return <span class="pill pill-red">Needs attention</span>;
  }
  return <span class="pill pill-green">Ready</span>;
}
