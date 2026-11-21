import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { tokens } from './tokens';

/** Fired when the session can't be refreshed; AuthProvider listens and signs the user out. */
export const AUTH_LOGOUT_EVENT = 'leadpilot:logout';

const baseURL = import.meta.env.VITE_API_URL ?? '';

/** Shared Axios instance. In dev, /api is proxied by Vite to Django. */
export const api = axios.create({ baseURL, timeout: 15_000 });

api.interceptors.request.use((config) => {
  const access = tokens.access;
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

// One refresh at a time: concurrent 401s wait for the same promise.
let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokens.refresh;
  if (!refresh) return null;
  try {
    const { data } = await axios.post<{ access: string; refresh?: string }>(
      `${baseURL}/api/auth/refresh/`,
      { refresh },
    );
    tokens.set(data.access, data.refresh);
    return data.access;
  } catch {
    return null;
  }
}

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const isAuthCall = original?.url?.includes('/api/auth/login') ?? false;

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshing ??= refreshAccessToken().finally(() => {
        refreshing = null;
      });
      const access = await refreshing;
      if (access) {
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      }
      tokens.clear();
      window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
    }
    return Promise.reject(error);
  },
);

export interface HealthResponse {
  status: string;
  database: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/api/health/');
  return data;
}
