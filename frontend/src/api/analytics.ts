import type { DashboardSummary } from '../types';
import { api } from './client';

export const analyticsApi = {
  key: 'analytics',
  async summary(): Promise<DashboardSummary> {
    const { data } = await api.get<DashboardSummary>('/api/analytics/summary/');
    return data;
  },
};
