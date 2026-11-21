export type Role = 'admin' | 'sales' | 'support';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: Role;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

interface Owned {
  id: number;
  owner: number | null;
  owner_name: string | null;
  created_at: string;
  updated_at: string;
}

export type Industry =
  | 'technology'
  | 'finance'
  | 'healthcare'
  | 'retail'
  | 'manufacturing'
  | 'education'
  | 'real_estate'
  | 'hospitality'
  | 'other';
export type CompanySize = '' | '1-10' | '11-50' | '51-200' | '201-1000' | '1000+';

export interface Company extends Owned {
  name: string;
  industry: Industry;
  size: CompanySize;
  website: string;
  city: string;
  contact_count?: number;
}

export interface Contact extends Owned {
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  company: number | null;
  company_name: string | null;
  tags: string[];
  segment: string | null;
  churn_risk: number | null;
}

export type LeadSource = 'web' | 'referral' | 'ads' | 'event' | 'cold';
export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'unqualified' | 'converted';
export type ScoreLabel = 'hot' | 'warm' | 'cold';

export interface Lead extends Owned {
  contact: number;
  contact_name: string;
  contact_email: string;
  company_name: string | null;
  source: LeadSource;
  status: LeadStatus;
  budget: string | null;
  notes: string;
  score: number | null;
  score_label: ScoreLabel | null;
  score_explanation: ScoreFactor[] | null;
  last_contacted_at: string | null;
  /** Deal created when this lead was converted. */
  deal: number | null;
}

export type ActivityType = 'call' | 'email' | 'meeting' | 'note';

export interface Activity extends Owned {
  type: ActivityType;
  subject: string;
  body: string;
  contact: number;
  contact_name: string;
  summary: string | null;
  action_items: unknown;
  occurred_at: string;
}

export type TaskStatus = 'todo' | 'in_progress' | 'done';
export type TaskPriority = 'low' | 'medium' | 'high';

export interface Task extends Owned {
  title: string;
  description: string;
  due_date: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assigned_to: number | null;
  assigned_to_name: string | null;
  contact: number | null;
  contact_name: string | null;
  created_by_agent: boolean;
}

export interface ImportResult {
  total_rows: number;
  created: number;
  errors: { row: number; errors: Record<string, string[]> }[];
}

export type DealStage = 'new' | 'qualified' | 'proposal' | 'negotiation' | 'won' | 'lost';

export interface Deal extends Owned {
  title: string;
  contact: number;
  contact_name: string;
  company_name: string | null;
  lead: number | null;
  value: string;
  stage: DealStage;
  expected_close_date: string | null;
  probability: number;
  position: number;
  closed_at: string | null;
}

export interface BoardColumn {
  stage: DealStage;
  label: string;
  count: number;
  total_value: string;
  deals: Deal[];
}

export interface DashboardSummary {
  generated_at: string;
  totals: {
    leads: number;
    open_leads: number;
    open_deals: number;
    pipeline_value: string;
    weighted_pipeline_value: string;
  };
  leads_by_source: { source: LeadSource; label: string; count: number }[];
  deals_by_stage: { stage: DealStage; label: string; count: number; value: string }[];
  win_rate: number | null;
  revenue_this_month: string;
  revenue_trend: { month: string; revenue: string; deals: number }[];
  tasks_due_today: number;
  tasks_overdue: number;
}

export interface ScoreFactor {
  feature: string;
  label: string;
  value: string;
  impact: number;
  direction: 'up' | 'down';
}

export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed';
export type TicketPriority = 'low' | 'medium' | 'high';
export type Sentiment = 'positive' | 'neutral' | 'negative';

export interface Ticket extends Owned {
  subject: string;
  description: string;
  contact: number;
  contact_name: string;
  company_name: string | null;
  status: TicketStatus;
  priority: TicketPriority;
  priority_overridden: boolean;
  sentiment: Sentiment | null;
  sentiment_score: number | null;
  urgent: boolean;
  assigned_to: number | null;
  assigned_to_name: string | null;
  resolved_at: string | null;
  comment_count: number;
}

export interface TicketComment {
  id: number;
  body: string;
  author: number | null;
  author_name: string | null;
  created_at: string;
}

export interface ConfusionMatrix {
  labels: [string, string];
  matrix: [[number, number], [number, number]];
}

export interface ModelMetrics {
  model: string;
  trained_at: string;
  task: 'classification' | 'clustering' | 'regression';
  dataset: string;
  rows: number;
  chosen_model: string;
  selection: string;
  comparison?: Record<string, number | string | null>[];
  test?: {
    accuracy?: number;
    precision?: number;
    recall?: number;
    f1?: number;
    roc_auc?: number;
    mae?: number;
    rmse?: number;
    r2?: number | null;
    confusion_matrix?: ConfusionMatrix;
  };
  silhouette?: number;
  k_comparison?: { k: number; inertia: number; silhouette: number }[];
  profile?: {
    segment: string;
    customers: number;
    recency_days: number;
    frequency: number;
    monetary: number;
  }[];
}

export interface MlMetricsResponse {
  available: Record<string, boolean>;
  models: Record<string, ModelMetrics | null>;
}

export interface ForecastResponse {
  ok: boolean;
  reason?: string;
  chosen?: string;
  history?: { month: string; revenue: number }[];
  forecast?: { month: string; forecast: number; lower: number; upper: number }[];
  methods?: { method: string; mae: number; rmse: number; r2: number | null }[];
}

export interface SegmentSummary {
  segments: { segment: string; customers: number; avg_churn_risk: number | null }[];
  silhouette: number | null;
}
