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

export interface Citation {
  type: 'activity' | 'ticket' | 'lead';
  id: number;
  snippet: string;
  contact_id: number | null;
  date: string | null;
  link: string;
  similarity: number;
}

export interface AskResult {
  conversation_id: number;
  answer: string;
  citations: Citation[];
}

export interface ConversationSummary {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  created_at: string;
}

export const askApi = {
  key: 'ask',
  async ask(question: string, conversationId: number | null): Promise<AskResult> {
    const { data } = await api.post<AskResult>(
      '/api/genai/ask/',
      { question, conversation_id: conversationId },
      { timeout: LLM_TIMEOUT },
    );
    return data;
  },
  async conversations(): Promise<ConversationSummary[]> {
    const { data } = await api.get<{ results: ConversationSummary[] }>(
      '/api/genai/conversations/',
      {
        params: { page_size: 30 },
      },
    );
    return data.results;
  },
  async conversation(
    id: number,
  ): Promise<ConversationSummary & { messages: ConversationMessage[] }> {
    const { data } = await api.get(`/api/genai/conversations/${id}/`);
    return data;
  },
  async remove(id: number): Promise<void> {
    await api.delete(`/api/genai/conversations/${id}/`);
  },
};
