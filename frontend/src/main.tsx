import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { wakeServer } from './api/wake';
import { ToastProvider } from './components/Toast';
import { AuthProvider } from './features/auth/AuthContext';
import './index.css';
import { router } from './routes/router';

// Start waking a sleeping (free-tier) API immediately, while the page and login form load.
void wakeServer();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Don't retry client errors (403/404/validation); retry network/server errors once.
      retry: (count, err) =>
        count < 1 && !(isAxiosError(err) && (err.response?.status ?? 500) < 500),
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <RouterProvider router={router} future={{ v7_startTransition: true }} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
