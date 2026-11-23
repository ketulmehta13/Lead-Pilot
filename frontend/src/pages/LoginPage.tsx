import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { parseApiError } from '../api/errors';
import { isWakingError, useWakeState, wakeServer } from '../api/wake';
import { ThemeToggle } from '../components/ThemeToggle';
import { Button } from '../components/ui/Button';
import { TextField } from '../components/ui/Field';
import { useAuth } from '../features/auth/AuthContext';

const loginSchema = z.object({
  username: z.string().trim().min(1, 'Enter your username'),
  password: z.string().min(1, 'Enter your password'),
  remember: z.boolean(),
});
type FormValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const wake = useWakeState();
  const { register, handleSubmit, formState } = useForm<FormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: '', password: '', remember: false },
  });

  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  if (user) return <Navigate to={from} replace />;

  const onSubmit = handleSubmit(async ({ username, password, remember }) => {
    setError(null);
    try {
      try {
        await login(username, password, remember);
      } catch (err) {
        // The server was asleep: wait for it to start, then try once more.
        if (!isWakingError(err) || !(await wakeServer())) throw err;
        await login(username, password, remember);
      }
      navigate(from, { replace: true });
    } catch (err) {
      const parsed = parseApiError(err);
      setError(
        parsed.status === 401
          ? 'Wrong username or password.'
          : isWakingError(err)
            ? 'The server is taking longer than usual to start. Please try again in a minute.'
            : parsed.message,
      );
    }
  });

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <img src="/favicon.svg" alt="" className="size-8" />
          LeadPilot
        </div>
        <h1 className="mt-6 text-xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Welcome back. Use the account your admin gave you.
        </p>
        {wake === 'waking' && (
          <p
            role="status"
            className="mt-4 flex items-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300"
          >
            <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
            Starting the server… this can take up to a minute after a quiet period. You can sign in
            now; we’ll wait for it.
          </p>
        )}
        <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
          <TextField
            label="Username"
            autoComplete="username"
            autoFocus
            error={formState.errors.username?.message}
            {...register('username')}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            error={formState.errors.password?.message}
            {...register('password')}
          />
          <label className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              className="mt-0.5 size-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              {...register('remember')}
            />
            <span>
              Keep me signed in
              <span className="block text-xs text-slate-500">
                Leave unticked on shared computers: closing the browser signs you out.
              </span>
            </span>
          </label>
          {error && (
            <p
              role="alert"
              className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
            >
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" loading={formState.isSubmitting}>
            Sign in
          </Button>
        </form>
        {import.meta.env.DEV && (
          <p className="mt-6 text-xs text-slate-500">
            Demo (after <code>seed_demo</code>): <code>admin</code>, <code>priya</code>,{' '}
            <code>sneha</code> / <code>LeadPilot@123</code>
          </p>
        )}
      </div>
    </div>
  );
}
