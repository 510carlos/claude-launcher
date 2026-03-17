import { api } from './client';
import type { Session, StartSessionRequest, ApiResponse } from '../types';

export const listSessions = (workspot?: string): Promise<Session[]> =>
  api(workspot ? `/api/sessions?workspot=${encodeURIComponent(workspot)}` : '/api/sessions');

export const getSession = (id: string): Promise<Session> =>
  api(`/api/sessions/${id}`);

export const startSession = (req: StartSessionRequest): Promise<ApiResponse> =>
  api('/api/sessions', { method: 'POST', body: JSON.stringify(req) });

export const killSession = (id: string): Promise<ApiResponse> =>
  api(`/api/sessions/${id}/kill`, { method: 'POST' });

export const deleteSession = (id: string): Promise<ApiResponse> =>
  api(`/api/sessions/${id}`, { method: 'DELETE' });

export const deleteEndedSessions = (): Promise<ApiResponse> =>
  api('/api/sessions', { method: 'DELETE' });

export const getSessionOutput = (id: string, tail = 80): Promise<{ status: string; output?: string }> =>
  api(`/api/sessions/${id}/output?tail=${tail}`);
