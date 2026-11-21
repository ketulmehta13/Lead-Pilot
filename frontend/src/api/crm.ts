import type { Activity, Company, Contact, ImportResult, Lead, Paginated, Task } from '../types';
import { api } from './client';

export type ListParams = Record<string, string | number | boolean | undefined | null>;

function clean(params: ListParams = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== undefined && v !== null),
  );
}

/** Typed CRUD helpers for one DRF ViewSet. */
function resource<T, TInput = Partial<T>>(path: string) {
  const base = `/api/crm/${path}/`;
  return {
    key: path,
    async list(params?: ListParams): Promise<Paginated<T>> {
      const { data } = await api.get<Paginated<T>>(base, { params: clean(params) });
      return data;
    },
    async get(id: number): Promise<T> {
      const { data } = await api.get<T>(`${base}${id}/`);
      return data;
    },
    async create(input: TInput): Promise<T> {
      const { data } = await api.post<T>(base, input);
      return data;
    },
    async update(id: number, input: Partial<TInput>): Promise<T> {
      const { data } = await api.patch<T>(`${base}${id}/`, input);
      return data;
    },
    async remove(id: number): Promise<void> {
      await api.delete(`${base}${id}/`);
    },
  };
}

export const companiesApi = resource<Company>('companies');
export const contactsApi = {
  ...resource<Contact>('contacts'),
  async importCsv(file: File): Promise<ImportResult> {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post<ImportResult>('/api/crm/contacts/import/', form, {
      timeout: 60_000,
    });
    return data;
  },
};
export const leadsApi = resource<Lead>('leads');
export const activitiesApi = resource<Activity>('activities');
export const tasksApi = resource<Task>('tasks');
