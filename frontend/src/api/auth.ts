import type { Paginated, Role, User } from '../types';
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

export interface ProfileInput {
  first_name: string;
  last_name: string;
  email: string;
}

export const accountApi = {
  async updateMe(input: Partial<ProfileInput>): Promise<User> {
    const { data } = await api.patch<User>('/api/auth/me/', input);
    return data;
  },
  async changePassword(current_password: string, new_password: string): Promise<void> {
    await api.post('/api/auth/me/password/', { current_password, new_password });
  },
};

export interface NewUserInput extends ProfileInput {
  username: string;
  role: Role;
  password: string;
}

/** Team management (admins only). Users are deactivated, never deleted. */
export const usersApi = {
  key: 'users',
  async list(params: { search?: string; include_inactive?: boolean } = {}) {
    const { data } = await api.get<Paginated<User>>('/api/auth/users/', {
      params: { page_size: 100, ...params },
    });
    return data;
  },
  async create(input: NewUserInput): Promise<User> {
    const { data } = await api.post<User>('/api/auth/register/', input);
    return data;
  },
  async update(
    id: number,
    input: Partial<ProfileInput & { role: Role; is_active: boolean }>,
  ): Promise<User> {
    const { data } = await api.patch<User>(`/api/auth/users/${id}/`, input);
    return data;
  },
  async setPassword(id: number, password: string): Promise<void> {
    await api.post(`/api/auth/users/${id}/set-password/`, { password });
  },
};
