import type {
  Activity,
  BoardColumn,
  Company,
  Contact,
  Deal,
  DealStage,
  ImportResult,
  Lead,
  Paginated,
  Task,
} from '../types';
import { api } from './client';

export type ListParams = Record<string, string | number | boolean | undefined | null>;

export function clean(params: ListParams = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== undefined && v !== null),
  );
}

/** Typed CRUD helpers for one DRF ViewSet. */
export function resource<T, TInput = Partial<T>>(path: string, prefix = '/api/crm') {
  const base = `${prefix}/${path}/`;
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
export const leadsApi = {
  ...resource<Lead>('leads'),
  async convert(
    id: number,
    input: {
      title?: string;
      value?: string | null;
      stage?: DealStage;
      expected_close_date?: string | null;
    },
  ): Promise<Deal> {
    const { data } = await api.post<Deal>(`/api/crm/leads/${id}/convert/`, input);
    return data;
  },
};
export const dealsApi = {
  ...resource<Deal>('deals'),
  async board(params?: ListParams): Promise<BoardColumn[]> {
    const { data } = await api.get<BoardColumn[]>('/api/crm/deals/board/', {
      params: clean(params),
    });
    return data;
  },
  async move(id: number, stage: DealStage, position: number): Promise<Deal> {
    const { data } = await api.post<Deal>(`/api/crm/deals/${id}/move/`, { stage, position });
    return data;
  },
};
export const activitiesApi = resource<Activity>('activities');
export const tasksApi = resource<Task>('tasks');
