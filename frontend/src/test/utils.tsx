import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { tokens } from '../api/tokens';
import { ToastProvider } from '../components/Toast';
import { AuthProvider } from '../features/auth/AuthContext';
import { routes } from '../routes/router';
import type { Role, User } from '../types';

export function makeUser(role: Role): User {
  return {
    id: 1,
    username: role,
    email: `${role}@test.io`,
    first_name: 'Test',
    last_name: role,
    full_name: `Test ${role}`,
    role,
  };
}

export const emptyPage = { count: 0, next: null, previous: null, results: [] };

/** Renders the whole app at `path`. Pass `signedIn` to start with a saved token. */
export function renderApp(path: string, { signedIn = true } = {}) {
  if (signedIn) tokens.set('test-access', 'test-refresh');
  else tokens.clear();
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}
