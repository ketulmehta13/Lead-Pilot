import { Link } from 'react-router-dom';
import { ThemeToggle } from '../components/ThemeToggle';

/** Login placeholder. Real JWT login (React Hook Form + Zod) arrives in Phase 1. */
export function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2 text-lg font-semibold">
          <img src="/favicon.svg" alt="" className="size-8" />
          LeadPilot
        </div>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Sign-in is added in Phase 1.
        </p>
        <Link
          to="/dashboard"
          className="mt-6 block rounded-lg bg-indigo-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-indigo-500"
        >
          Continue to app
        </Link>
      </div>
    </div>
  );
}
