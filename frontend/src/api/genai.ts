import type { Task } from '../types';
import { api } from './client';

export type Tone = 'friendly' | 'professional' | 'concise' | 'enthusiastic' | 'formal';

export interface EmailDraft {
  subject: string;
  body: string;
}

export interface ActionItem {
  title: string;
  due_in_days: number | null;
}

export interface ActivitySummaryResult {
  activity_id: number;
  summary: string;
  action_items: ActionItem[];
  sentiment: 'positive' | 'neutral' | 'negative';
}

export interface GenAIStatus {
  configured: boolean;
  provider: string;
  model: string;
}

/** LLM calls can take a while; allow up to 90 s. */
const LLM_TIMEOUT = 90_000;

export const genaiApi = {
  key: 'genai',
  async status(): Promise<GenAIStatus> {
    const { data } = await api.get<GenAIStatus>('/api/genai/status/');
    return data;
  },
  async draftEmail(input: { contact_id: number; goal: string; tone: Tone }): Promise<EmailDraft> {
    const { data } = await api.post<EmailDraft>('/api/genai/draft-email/', input, {
      timeout: LLM_TIMEOUT,
    });
    return data;
  },
  async summarize(activityId: number): Promise<ActivitySummaryResult> {
    const { data } = await api.post<ActivitySummaryResult>(
      '/api/genai/summarize-activity/',
      { activity_id: activityId },
      { timeout: LLM_TIMEOUT },
    );
    return data;
  },
  async actionItemsToTasks(activityId: number, items: number[]): Promise<Task[]> {
    const { data } = await api.post<Task[]>('/api/genai/action-items-to-tasks/', {
      activity_id: activityId,
      items,
    });
    return data;
  },
};
