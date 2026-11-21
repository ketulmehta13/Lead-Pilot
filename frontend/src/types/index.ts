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
  score_explanation: unknown;
  last_contacted_at: string | null;
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
