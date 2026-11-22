import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { accountApi, authApi, usersApi } from '../api/auth';
import { NAV_ITEMS } from '../routes/nav';
import { makeUser, renderApp } from './utils';

vi.mock('../api/auth', () => ({
  authApi: { me: vi.fn(), login: vi.fn() },
  accountApi: { updateMe: vi.fn(), changePassword: vi.fn() },
  usersApi: {
    key: 'users',
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    setPassword: vi.fn(),
  },
}));
vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  getHealth: vi.fn().mockResolvedValue({ status: 'ok', database: 'ok' }),
}));
vi.mock('../api/analytics', () => ({
  analyticsApi: {
    key: 'analytics',
    summary: vi.fn().mockResolvedValue({
      generated_at: new Date().toISOString(),
      totals: {
        leads: 400,
        open_leads: 250,
        open_deals: 42,
        pipeline_value: '1250000.00',
        weighted_pipeline_value: '500000.00',
      },
      leads_by_source: [{ source: 'web', label: 'Web', count: 120 }],
      deals_by_stage: [{ stage: 'new', label: 'New', count: 5, value: '50000.00' }],
      win_rate: 64.5,
      revenue_this_month: '320000.00',
      collected_this_month: '118000.00',
      invoices_outstanding: '59000.00',
      revenue_trend: [{ month: '2026-11', revenue: '320000.00', deals: 3 }],
      tasks_due_today: 4,
      tasks_overdue: 2,
    }),
  },
}));
vi.mock('../api/ml', () => ({
  mlApi: {
    key: 'ml',
    metrics: vi.fn().mockResolvedValue({ available: {}, models: {} }),
    forecast: vi.fn().mockResolvedValue({ ok: false, reason: 'Need more history' }),
    segments: vi.fn().mockResolvedValue({ segments: [], silhouette: null }),
    scoreLead: vi.fn(),
    retrain: vi.fn(),
    rescoreAll: vi.fn(),
  },
}));
vi.mock('../api/genai', () => ({
  genaiApi: {
    key: 'genai',
    status: vi.fn().mockResolvedValue({ configured: true, provider: 'groq', model: 'llama' }),
    draftEmail: vi.fn(),
    summarize: vi.fn(),
    actionItemsToTasks: vi.fn(),
  },
  askApi: {
    key: 'ask',
    ask: vi.fn().mockResolvedValue({
      conversation_id: 9,
      answer: 'You discussed pricing for 40 seats.',
      citations: [
        {
          type: 'activity',
          id: 42,
          snippet: 'Meeting with Meera Shah (Nimbus) - pricing for 40 seats',
          contact_id: 7,
          date: '2026-10-12',
          link: '/contacts/7',
          similarity: 0.61,
        },
      ],
    }),
    conversations: vi.fn().mockResolvedValue([]),
    conversation: vi.fn(),
    remove: vi.fn(),
  },
}));
vi.mock('../api/agent', () => {
  const step = (id: number, tool: string, status: string, extra = {}) => ({
    id,
    order: id,
    tool_name: tool,
    tool_input: {},
    tool_output: status === 'pending_approval' ? null : { ok: true },
    note: '',
    requires_approval: status === 'pending_approval',
    approved: null,
    status,
    decided_at: null,
    created_at: new Date().toISOString(),
    ...extra,
  });
  const base = {
    id: 5,
    goal: 'Find hot leads not contacted in 7 days, draft follow-ups and create tasks',
    final_summary: '',
    error: '',
    max_steps: 10,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    finished_at: null,
  };
  const paused = {
    ...base,
    status: 'awaiting_approval',
    steps: [
      step(1, 'search_leads', 'done'),
      step(2, 'draft_email', 'done', {
        tool_output: { to: 'asha@acme.io', subject: 'Quick follow-up', body: 'Hi Asha' },
      }),
      step(3, 'create_task', 'pending_approval'),
    ],
  };
  const finished = {
    ...paused,
    status: 'done',
    final_summary: 'Drafted 1 follow-up and created 1 task.',
    steps: [...paused.steps.slice(0, 2), { ...paused.steps[2], status: 'done', approved: true }],
  };
  return {
    agentApi: {
      key: 'agent',
      start: vi.fn().mockResolvedValue(paused),
      get: vi.fn().mockResolvedValueOnce(paused).mockResolvedValue(finished),
      list: vi.fn().mockResolvedValue([]),
      decide: vi.fn().mockResolvedValue(finished),
    },
  };
});
vi.mock('../api/billing', () => ({
  invoicesApi: {
    key: 'invoices',
    list: vi.fn().mockResolvedValue({ count: 0, next: null, previous: null, results: [] }),
    get: vi.fn(),
    create: vi.fn(),
    config: vi.fn().mockResolvedValue({ configured: false, key_id: '', test_mode: true }),
  },
}));
vi.mock('../api/support', () => ({
  ticketsApi: {
    key: 'tickets',
    list: vi.fn().mockResolvedValue({ count: 0, next: null, previous: null, results: [] }),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    comments: vi.fn().mockResolvedValue([]),
    addComment: vi.fn(),
  },
}));
vi.mock('../api/crm', () => {
  const resource = (key: string) => ({
    key,
    list: vi.fn().mockResolvedValue({ count: 0, next: null, previous: null, results: [] }),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  });
  return {
    companiesApi: resource('companies'),
    contactsApi: { ...resource('contacts'), importCsv: vi.fn() },
    leadsApi: { ...resource('leads'), convert: vi.fn() },
    dealsApi: { ...resource('deals'), board: vi.fn().mockResolvedValue([]), move: vi.fn() },
    activitiesApi: resource('activities'),
    tasksApi: resource('tasks'),
  };
});

const me = vi.mocked(authApi.me);
const login = vi.mocked(authApi.login);
const updateMe = vi.mocked(accountApi.updateMe);
const listUsers = vi.mocked(usersApi.list);
const updateUser = vi.mocked(usersApi.update);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe('auth', () => {
  it('sends signed-out users to the login page', async () => {
    renderApp('/leads', { signedIn: false });
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(me).not.toHaveBeenCalled();
  });

  it('shows a friendly error for a wrong password', async () => {
    const { AxiosError } = await import('axios');
    login.mockRejectedValue(
      new AxiosError('401', '401', undefined, undefined, {
        status: 401,
        data: { error: { code: 'no_active_account', message: 'No active account' } },
      } as never),
    );
    const user = userEvent.setup();
    renderApp('/login', { signedIn: false });
    await user.type(screen.getByLabelText('Username'), 'priya');
    await user.type(screen.getByLabelText('Password'), 'nope');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password.');
  });

  it('validates the login form before calling the API', async () => {
    const user = userEvent.setup();
    renderApp('/login', { signedIn: false });
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Enter your username')).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('signs in and returns to the page the user wanted', async () => {
    login.mockResolvedValue({ access: 'a', refresh: 'r', user: makeUser('sales') });
    const user = userEvent.setup();
    renderApp('/login', { signedIn: false });
    await user.type(screen.getByLabelText('Username'), 'priya');
    await user.type(screen.getByLabelText('Password'), 'LeadPilot@123');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }, { timeout: 15_000 }),
    ).toBeInTheDocument();
    expect(localStorage.getItem('leadpilot-access')).toBe('a');
  });

  it('signs out from the top bar', async () => {
    me.mockResolvedValue(makeUser('admin'));
    const user = userEvent.setup();
    renderApp('/dashboard');
    await user.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(localStorage.getItem('leadpilot-access')).toBeNull();
  });
});

describe('navigation by role', () => {
  it('admin can open every page from the sidebar', async () => {
    me.mockResolvedValue(makeUser('admin'));
    const user = userEvent.setup();
    renderApp('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    for (const item of NAV_ITEMS) {
      await user.click(within(nav).getByRole('link', { name: item.label }));
      expect(
        await screen.findByRole('heading', { level: 1, name: item.label }),
      ).toBeInTheDocument();
    }
  });

  it('support only sees the pages its role allows', async () => {
    me.mockResolvedValue(makeUser('support'));
    renderApp('/dashboard');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    const labels = within(nav)
      .getAllByRole('link')
      .map((a) => a.textContent);
    expect(labels).toEqual(['Dashboard', 'Contacts', 'Tickets', 'Ask LeadPilot', 'Settings']);
  });

  it('sales reps see tickets read-only; support can create them', async () => {
    me.mockResolvedValue(makeUser('sales'));
    renderApp('/tickets');
    expect(await screen.findByRole('heading', { name: 'Tickets' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new ticket/i })).not.toBeInTheDocument();
  });

  it('support can create tickets', async () => {
    me.mockResolvedValue(makeUser('support'));
    renderApp('/tickets');
    expect(await screen.findByRole('button', { name: /new ticket/i })).toBeInTheDocument();
  });

  it('support gets "No access" on a sales page opened by URL', async () => {
    me.mockResolvedValue(makeUser('support'));
    renderApp('/leads');
    expect(await screen.findByRole('heading', { name: 'No access' })).toBeInTheDocument();
  });

  it('support sees contacts read-only (no create or import)', async () => {
    me.mockResolvedValue(makeUser('support'));
    renderApp('/contacts');
    expect(await screen.findByRole('heading', { name: 'Contacts' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new contact/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /import csv/i })).not.toBeInTheDocument();
  });

  it('sales rep sees empty states on CRM pages', async () => {
    me.mockResolvedValue(makeUser('sales'));
    renderApp('/leads');
    expect(await screen.findByText('No leads yet')).toBeInTheDocument();
  });
});

describe('dashboard', () => {
  it('shows KPI tiles from the summary', async () => {
    me.mockResolvedValue(makeUser('sales'));
    renderApp('/dashboard');
    expect(await screen.findByText('₹12,50,000')).toBeInTheDocument();
    expect(screen.getByText('64.5%')).toBeInTheDocument();
    expect(screen.getByText('₹3,20,000')).toBeInTheDocument();
    expect(screen.getByText('2 overdue')).toBeInTheDocument();
  });

  it('offers a data table for each chart', async () => {
    me.mockResolvedValue(makeUser('admin'));
    const user = userEvent.setup();
    renderApp('/dashboard');
    const buttons = await screen.findAllByRole('button', { name: 'Show data' });
    expect(buttons).toHaveLength(3);
    await user.click(buttons[0]);
    expect(await screen.findByRole('columnheader', { name: 'Deals won' })).toBeInTheDocument();
  });

  it('gives support staff a dashboard without sales data', async () => {
    me.mockResolvedValue(makeUser('support'));
    renderApp('/dashboard');
    expect(await screen.findByText(/Support metrics arrive/)).toBeInTheDocument();
  });
});

describe('Ask LeadPilot', () => {
  it('answers with clickable citations to the source record', async () => {
    me.mockResolvedValue(makeUser('sales'));
    const user = userEvent.setup();
    renderApp('/ask');
    await user.type(
      await screen.findByLabelText('Your question'),
      'What did we discuss with Nimbus last month?{Enter}',
    );
    expect(await screen.findByText('You discussed pricing for 40 seats.')).toBeInTheDocument();
    const chip = screen.getByRole('link', { name: /\[1\].*activity #42/i });
    expect(chip).toHaveAttribute('href', '/contacts/7');
    expect(screen.getByText('What did we discuss with Nimbus last month?')).toBeInTheDocument();
  });
});

describe('Agent', () => {
  it('pauses on a write step and finishes after approval', async () => {
    me.mockResolvedValue(makeUser('sales'));
    const user = userEvent.setup();
    renderApp('/agent');
    await user.click(
      await screen.findByRole('button', { name: /find hot leads not contacted in 7 days/i }),
    );
    await user.click(screen.getByRole('button', { name: /run agent/i }));
    expect(await screen.findByText('Needs your approval')).toBeInTheDocument();
    expect(screen.getByText('Quick follow-up')).toBeInTheDocument();
    expect(screen.getByText(/this changes your crm/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^approve$/i }));
    expect(await screen.findByText('Drafted 1 follow-up and created 1 task.')).toBeInTheDocument();
  });
});

describe('settings', () => {
  it('a sales rep edits their profile but has no team management', async () => {
    const rep = makeUser('sales');
    me.mockResolvedValue(rep);
    updateMe.mockResolvedValue({ ...rep, first_name: 'Priya', full_name: 'Priya sales' });
    const user = userEvent.setup();
    renderApp('/settings');
    expect(await screen.findByRole('heading', { name: 'Profile' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Password' })).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'Theme' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Team' })).not.toBeInTheDocument();

    const first = screen.getByLabelText('First name');
    await user.clear(first);
    await user.type(first, 'Priya');
    await user.click(screen.getByRole('button', { name: 'Save profile' }));
    expect(updateMe).toHaveBeenCalledWith(expect.objectContaining({ first_name: 'Priya' }));
    expect(await screen.findByText('Profile saved')).toBeInTheDocument();
  });

  it('an admin manages the team and sees the system status', async () => {
    const admin = makeUser('admin');
    const rep = { ...makeUser('sales'), id: 2, username: 'rahul', full_name: 'Rahul Verma' };
    me.mockResolvedValue(admin);
    listUsers.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        { ...admin, is_active: true },
        { ...rep, is_active: true },
      ],
    });
    updateUser.mockResolvedValue({ ...rep, is_active: false });
    const user = userEvent.setup();
    renderApp('/settings');

    const team = await screen.findByRole('region', { name: 'Team' });
    expect(await within(team).findByText('Rahul Verma')).toBeInTheDocument();
    // Admins can't deactivate themselves: only one Deactivate button (for Rahul).
    const buttons = within(team).getAllByRole('button', { name: 'Deactivate' });
    expect(buttons).toHaveLength(1);
    await user.click(buttons[0]);
    expect(updateUser).toHaveBeenCalledWith(2, { is_active: false });
    expect(await screen.findByText('Rahul Verma deactivated')).toBeInTheDocument();

    const system = screen.getByRole('region', { name: 'System status' });
    expect(await within(system).findByText(/Connected: groq/)).toBeInTheDocument();
    expect(within(system).getByText(/Pay Now and payment links are off/)).toBeInTheDocument();
  });
});
