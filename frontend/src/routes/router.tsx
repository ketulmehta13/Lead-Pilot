import type { ReactNode } from 'react';
import { Navigate, createBrowserRouter, type RouteObject } from 'react-router-dom';
import { CompaniesPage } from '../features/companies/CompaniesPage';
import { ContactDetailPage } from '../features/contacts/ContactDetailPage';
import { ContactsPage } from '../features/contacts/ContactsPage';
import { LeadsPage } from '../features/leads/LeadsPage';
import { TasksPage } from '../features/tasks/TasksPage';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/LoginPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { RequireAuth, RequireRole } from './guards';
import { NAV_ITEMS } from './nav';

/** Pages that are built; everything else in NAV_ITEMS shows a placeholder. */
const PAGES: Record<string, ReactNode> = {
  '/contacts': <ContactsPage />,
  '/companies': <CompaniesPage />,
  '/leads': <LeadsPage />,
  '/tasks': <TasksPage />,
};

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      ...NAV_ITEMS.map((item) => ({
        path: item.path.slice(1),
        element: (
          <RequireRole roles={item.roles}>
            {PAGES[item.path] ?? (
              <PlaceholderPage
                title={item.label}
                description={item.description}
                phase={item.phase}
              />
            )}
          </RequireRole>
        ),
      })),
      { path: 'contacts/:id', element: <ContactDetailPage /> },
      {
        path: 'invoices/:id',
        element: (
          <RequireRole roles={['admin', 'sales']}>
            <PlaceholderPage
              title="Invoice detail"
              description="Invoice with status, Pay Now and payment history."
              phase={7}
            />
          </RequireRole>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
