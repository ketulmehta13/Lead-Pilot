import {
  Bot,
  Brain,
  Building2,
  CheckSquare,
  Kanban,
  LayoutDashboard,
  LifeBuoy,
  MessageSquareText,
  Receipt,
  Settings,
  Target,
  Users,
  type LucideIcon,
} from 'lucide-react';
import type { Role } from '../types';

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  /** Shown on the placeholder page until the feature is built. */
  description: string;
  phase: number;
  /** Roles that see this page; undefined = everyone signed in. */
  roles?: Role[];
}

const SALES: Role[] = ['admin', 'sales'];

/** Sidebar entries — one per main page in CLAUDE.md. */
export const NAV_ITEMS: NavItem[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
    phase: 2,
    description: 'KPI cards, pipeline by stage, leads by source and revenue trend.',
  },
  {
    path: '/contacts',
    label: 'Contacts',
    icon: Users,
    phase: 1,
    description: 'Contact list with search and filters; detail page with activity timeline.',
  },
  {
    path: '/companies',
    label: 'Companies',
    icon: Building2,
    phase: 1,
    description: 'Companies with industry, size and city.',
    roles: SALES,
  },
  {
    path: '/leads',
    label: 'Leads',
    icon: Target,
    phase: 1,
    description: 'Leads with AI score badges and a "Why?" explanation.',
    roles: SALES,
  },
  {
    path: '/pipeline',
    label: 'Pipeline',
    icon: Kanban,
    phase: 2,
    description: 'Drag-and-drop Kanban of deals by stage.',
    roles: SALES,
  },
  {
    path: '/tasks',
    label: 'Tasks',
    icon: CheckSquare,
    phase: 1,
    description: 'Your tasks and reminders.',
    roles: SALES,
  },
  {
    path: '/tickets',
    label: 'Tickets',
    icon: LifeBuoy,
    phase: 3,
    description: 'Support tickets with automatic sentiment and priority.',
    roles: ['admin', 'support', 'sales'],
  },
  {
    path: '/ask',
    label: 'Ask LeadPilot',
    icon: MessageSquareText,
    phase: 5,
    description: 'Ask questions about your CRM; answers cite their sources.',
  },
  {
    path: '/agent',
    label: 'Agent',
    icon: Bot,
    phase: 6,
    description: 'Give the agent a goal, then approve or reject each write action.',
    roles: SALES,
  },
  {
    path: '/invoices',
    label: 'Invoices',
    icon: Receipt,
    phase: 7,
    description: 'Invoices from won deals, paid through Razorpay (test mode).',
    roles: SALES,
  },
  {
    path: '/ml-insights',
    label: 'ML Insights',
    icon: Brain,
    phase: 3,
    description: 'Model metrics, confusion matrix, segments and revenue forecast.',
    roles: SALES,
  },
  {
    path: '/settings',
    label: 'Settings',
    icon: Settings,
    phase: 8,
    description: 'Profile, preferences and user management.',
  },
];
