import { api } from './client';

export interface UpdateCheck {
  status: string;
  behind: number;
  commits: string[];
  current: string;
  message?: string;
}

export interface UpdateApply {
  status: string;
  message?: string;
  steps?: { step: string; ok: boolean; output: string }[];
}

export function checkUpdates(): Promise<UpdateCheck> {
  return api<UpdateCheck>('/api/updates/check');
}

export function applyUpdate(): Promise<UpdateApply> {
  return api<UpdateApply>('/api/updates/apply', { method: 'POST' });
}
