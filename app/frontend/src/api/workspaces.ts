import { api } from './client';
import type { Workspace, HealthStatus, ApiResponse } from '../types';

export const listWorkspaces = (): Promise<Workspace[]> =>
  api('/api/workspots');

export const getHealth = (): Promise<HealthStatus[]> =>
  api('/api/workspots/health');

export const fixWorkspot = (name: string): Promise<ApiResponse & { fixes?: string[]; health?: HealthStatus }> =>
  api(`/api/workspots/${encodeURIComponent(name)}/fix`, { method: 'POST' });

export const recheckWorkspot = (name: string): Promise<HealthStatus> =>
  api(`/api/workspots/${encodeURIComponent(name)}/recheck`, { method: 'POST' });

export const addWorkspot = (data: {
  name: string; runtime: string; dir: string;
  container?: string | null; claude_bin?: string;
  server_capacity?: number; env?: Record<string, string>;
}): Promise<ApiResponse> =>
  api('/api/workspots', { method: 'POST', body: JSON.stringify(data) });

export const removeWorkspot = (name: string): Promise<ApiResponse> =>
  api(`/api/workspots/${encodeURIComponent(name)}`, { method: 'DELETE' });
