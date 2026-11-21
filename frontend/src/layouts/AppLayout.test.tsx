import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { NAV_ITEMS } from '../routes/nav';
import { routes } from '../routes/router';

vi.mock('../api/client', () => ({
  getHealth: vi.fn().mockResolvedValue({ status: 'ok', database: 'ok' }),
}));

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe('App shell', () => {
  it('redirects / to the dashboard', async () => {
    renderAt('/');
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('opens every placeholder page from the sidebar', async () => {
    const user = userEvent.setup();
    renderAt('/dashboard');
    const nav = screen.getByRole('navigation', { name: 'Main' });

    for (const item of NAV_ITEMS) {
      await user.click(within(nav).getByRole('link', { name: item.label }));
      expect(await screen.findByRole('heading', { name: item.label })).toBeInTheDocument();
    }
  });

  it('shows the API status from /api/health/', async () => {
    renderAt('/dashboard');
    expect(await screen.findByText('API online')).toBeInTheDocument();
  });
});
