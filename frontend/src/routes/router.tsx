import { Navigate, createBrowserRouter, type RouteObject } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/LoginPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { NAV_ITEMS } from './nav';

export const routes: RouteObject[] = [
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      ...NAV_ITEMS.map((item) => ({
        path: item.path.slice(1),
        element: (
          <PlaceholderPage title={item.label} description={item.description} phase={item.phase} />
        ),
      })),
      {
        path: 'contacts/:id',
        element: (
          <PlaceholderPage
            title="Contact detail"
            description="Contact profile with activity timeline."
            phase={1}
          />
        ),
      },
      {
        path: 'invoices/:id',
        element: (
          <PlaceholderPage
            title="Invoice detail"
            description="Invoice with status, Pay Now and payment history."
            phase={7}
          />
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
