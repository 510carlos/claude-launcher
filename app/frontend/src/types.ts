// Mirrors: app/models.py — keep in sync

export type RuntimeType = 'docker' | 'host';
export type WorkspotSource = 'env' | 'file';
export type SessionStatus = 'pending' | 'running' | 'stopped' | 'failed';
export type ServerStatus = 'unknown' | 'running' | 'stopped' | 'unhealthy';

export interface Workspace {
  name: string;
  runtime: RuntimeType;
  container: string | null;
  dir: string;
  claude_bin: string;
  server_capacity: number;
  source: WorkspotSource;
}

export interface HealthStatus {
  workspot: string;
  runtime_ok: boolean;
  repo_exists: boolean;
  git_ok: boolean;
  claude_bin_ok: boolean;
  auth_ok: boolean;
  server_status: ServerStatus;
  issues: string[];
}

export interface Session {
  id: string;
  workspot: string;
  server_key: string;
  label: string;
  runtime: RuntimeType;
  container: string | null;
  repo_root: string;
  working_dir: string;
  branch: string | null;
  worktree_path: string | null;
  url: string | null;
  status: SessionStatus;
  created_at: string;
  last_seen_at: string | null;
  source: string;
  server_session_name: string | null;
  output_file: string | null;
  metadata: Record<string, unknown>;
}

export interface DiscoveredEnvironment {
  name: string;
  runtime: RuntimeType;
  dir: string;
  container: string | null;
  claude_bin: string | null;
  compatibility: 'compatible' | 'partial' | 'incompatible';
  checks: Record<string, boolean>;
  issues: string[];
  already_configured: boolean;
  image: string | null;
  container_status: string | null;
}

export interface DiscoveryResult {
  total: number;
  compatible: DiscoveredEnvironment[];
  partial: DiscoveredEnvironment[];
  incompatible: DiscoveredEnvironment[];
}

export interface StartSessionRequest {
  workspot: string;
  worktree?: boolean;
  label?: string;
  branch?: string;
  directory?: string | null;
}

export interface ApiResponse {
  status: 'ok' | 'error';
  message?: string;
  url?: string;
  [key: string]: unknown;
}
