import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '../api/auth';
import { NAV_ITEMS } from '../routes/nav';
import { makeUser, renderApp } from './utils';

vi.mock('../api/auth', () => ({ authApi: { me: vi.fn(), login: vi.fn() } }));
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
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
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
