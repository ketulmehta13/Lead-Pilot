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
    leadsApi: resource('leads'),
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
