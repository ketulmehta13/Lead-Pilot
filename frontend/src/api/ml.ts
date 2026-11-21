import type { ForecastResponse, Lead, MlMetricsResponse, SegmentSummary } from '../types';
import { api } from './client';

export const mlApi = {
  key: 'ml',
  async metrics(): Promise<MlMetricsResponse> {
    const { data } = await api.get<MlMetricsResponse>('/api/ml/metrics/');
    return data;
  },
  async forecast(): Promise<ForecastResponse> {
    const { data } = await api.get<ForecastResponse>('/api/ml/forecast/');
    return data;
  },
  async segments(): Promise<SegmentSummary> {
    const { data } = await api.get<SegmentSummary>('/api/ml/segments/');
    return data;
  },
  async scoreLead(
    id: number,
  ): Promise<Pick<Lead, 'id' | 'score' | 'score_label' | 'score_explanation'>> {
    const { data } = await api.post(`/api/ml/score-lead/${id}/`);
    return data;
  },
  async retrain(): Promise<{ status: string }> {
    // Training takes a few minutes when run inline (no Celery worker).
    const { data } = await api.post('/api/ml/retrain/', {}, { timeout: 15 * 60_000 });
    return data;
  },
  async rescoreAll(): Promise<{ status: string }> {
    const { data } = await api.post('/api/ml/rescore-all/', {}, { timeout: 5 * 60_000 });
    return data;
  },
};
