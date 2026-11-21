import { api } from './client';

export type RunStatus = 'planning' | 'awaiting_approval' | 'running' | 'done' | 'failed';
export type StepStatus = 'done' | 'pending_approval' | 'rejected' | 'failed';

export interface AgentStep {
  id: number;
  order: number;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown> | null;
  note: string;
  requires_approval: boolean;
  approved: boolean | null;
  status: StepStatus;
  decided_at: string | null;
  created_at: string;
}

export interface AgentRun {
  id: number;
  goal: string;
  status: RunStatus;
  final_summary: string;
  error: string;
  steps: AgentStep[];
  max_steps: number;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
}

export interface AgentRunListItem {
  id: number;
  goal: string;
  status: RunStatus;
  step_count: number;
  created_at: string;
  finished_at: string | null;
}

/** Starting a run executes inline when there's no Celery worker, so allow time. */
const RUN_TIMEOUT = 5 * 60_000;

export const agentApi = {
  key: 'agent',
  async start(goal: string): Promise<AgentRun> {
    const { data } = await api.post<AgentRun>(
      '/api/agent/runs/',
      { goal },
      { timeout: RUN_TIMEOUT },
    );
    return data;
  },
  async get(id: number): Promise<AgentRun> {
    const { data } = await api.get<AgentRun>(`/api/agent/runs/${id}/`);
    return data;
  },
  async list(): Promise<AgentRunListItem[]> {
    const { data } = await api.get<{ results: AgentRunListItem[] }>('/api/agent/runs/', {
      params: { page_size: 20 },
    });
    return data.results;
  },
  async decide(stepId: number, approve: boolean): Promise<AgentRun> {
    const { data } = await api.post<AgentRun>(
      `/api/agent/steps/${stepId}/${approve ? 'approve' : 'reject'}/`,
      {},
      { timeout: RUN_TIMEOUT },
    );
    return data;
  },
};
