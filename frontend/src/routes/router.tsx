/* eslint-disable react-refresh/only-export-components -- route config, not a component module */
import { lazy, type ReactNode } from 'react';
import { Navigate, createBrowserRouter, type RouteObject } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/LoginPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { RequireAuth, RequireRole } from './guards';
import { NAV_ITEMS } from './nav';

// Each page is its own chunk, so charts and drag-and-drop load only where used.
const CompaniesPage = lazy(() =>
  import('../features/companies/CompaniesPage').then((m) => ({ default: m.CompaniesPage })),
);
const DashboardPage = lazy(() =>
  import('../features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const ContactDetailPage = lazy(() =>
  import('../features/contacts/ContactDetailPage').then((m) => ({ default: m.ContactDetailPage })),
);
const ContactsPage = lazy(() =>
  import('../features/contacts/ContactsPage').then((m) => ({ default: m.ContactsPage })),
);
const LeadsPage = lazy(() =>
  import('../features/leads/LeadsPage').then((m) => ({ default: m.LeadsPage })),
);
const PipelinePage = lazy(() =>
  import('../features/pipeline/PipelinePage').then((m) => ({ default: m.PipelinePage })),
);
const TasksPage = lazy(() =>
  import('../features/tasks/TasksPage').then((m) => ({ default: m.TasksPage })),
);

const AskPage = lazy(() => import('../features/ask/AskPage').then((m) => ({ default: m.AskPage })));
const AgentPage = lazy(() =>
  import('../features/agent/AgentPage').then((m) => ({ default: m.AgentPage })),
);
const InvoicesPage = lazy(() =>
  import('../features/invoices/InvoicesPage').then((m) => ({ default: m.InvoicesPage })),
);
const InvoiceDetailPage = lazy(() =>
  import('../features/invoices/InvoiceDetailPage').then((m) => ({ default: m.InvoiceDetailPage })),
);
const TicketsPage = lazy(() =>
  import('../features/tickets/TicketsPage').then((m) => ({ default: m.TicketsPage })),
);
const MlInsightsPage = lazy(() =>
  import('../features/ml/MlInsightsPage').then((m) => ({ default: m.MlInsightsPage })),
);
const SettingsPage = lazy(() =>
  import('../features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);

/** Pages that are built; everything else in NAV_ITEMS shows a placeholder. */
const PAGES: Record<string, ReactNode> = {
  '/dashboard': <DashboardPage />,
  '/pipeline': <PipelinePage />,
  '/contacts': <ContactsPage />,
  '/companies': <CompaniesPage />,
  '/leads': <LeadsPage />,
  '/tasks': <TasksPage />,
  '/tickets': <TicketsPage />,
  '/ask': <AskPage />,
  '/agent': <AgentPage />,
  '/invoices': <InvoicesPage />,
  '/ml-insights': <MlInsightsPage />,
  '/settings': <SettingsPage />,
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
            <InvoiceDetailPage />
          </RequireRole>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

/** Opt in to React Router v7 behaviour now (silences the v6 future-flag warnings). */
export const ROUTER_FUTURE = {
  v7_relativeSplatPath: true,
  v7_fetcherPersist: true,
  v7_normalizeFormMethod: true,
  v7_partialHydration: true,
  v7_skipActionErrorRevalidation: true,
} as const;

export const router = createBrowserRouter(routes, { future: ROUTER_FUTURE });
