import type { Ticket, TicketComment } from '../types';
import { api } from './client';
import { resource } from './crm';

export const ticketsApi = {
  ...resource<Ticket>('tickets', '/api/support'),
  async comments(id: number): Promise<TicketComment[]> {
    const { data } = await api.get<TicketComment[]>(`/api/support/tickets/${id}/comments/`);
    return data;
  },
  async addComment(id: number, body: string): Promise<TicketComment> {
    const { data } = await api.post<TicketComment>(`/api/support/tickets/${id}/comments/`, {
      body,
    });
    return data;
  },
};
