import { ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spinner } from '../components/ui/Spinner';
import { useAuth } from '../features/auth/AuthContext';
import type { Role } from '../types';

/** Sends signed-out users to /login, remembering where they were going. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading your workspace" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

/** Shows a friendly "no access" message when the user's role can't use a page. */
export function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { hasRole } = useAuth();
  if (roles && !hasRole(...roles)) {
    return (
      <div className="flex flex-col items-center py-20 text-center">
        <ShieldAlert className="size-10 text-slate-400" aria-hidden />
        <h1 className="mt-4 text-xl font-semibold">No access</h1>
        <p className="mt-1 text-slate-600 dark:text-slate-400">
          Your role doesn&apos;t include this page. Ask an admin if you need it.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
