import axios from 'axios';

/**
 * Shared Axios instance. In dev, requests go to /api and Vite proxies them to Django.
 * JWT headers and auto-refresh interceptors are added in Phase 1.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
  timeout: 15_000,
});

export interface HealthResponse {
  status: string;
  database: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/api/health/');
  return data;
}
