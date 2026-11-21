import type { User } from '../types';
import { api } from './client';

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export const authApi = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const { data } = await api.post<LoginResponse>('/api/auth/login/', { username, password });
    return data;
  },
  async me(): Promise<User> {
    const { data } = await api.get<User>('/api/auth/me/');
    return data;
  },
};
