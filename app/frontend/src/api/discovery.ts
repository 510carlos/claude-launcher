import { api } from './client';
import type { DiscoveryResult } from '../types';

export const runDiscovery = (): Promise<DiscoveryResult> =>
  api('/api/discover');
