import { LogOut, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { ApiStatus } from '../components/ApiStatus';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../features/auth/AuthContext';
import { NAV_ITEMS } from '../routes/nav';

const ROLE_LABEL = { admin: 'Admin', sales: 'Sales Rep', support: 'Support' } as const;

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { hasRole } = useAuth();
  const items = NAV_ITEMS.filter((item) => !item.roles || hasRole(...item.roles));
  return (
    <nav aria-label="Main" className="flex flex-col gap-1 p-3">
      {items.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
            }`
          }
        >
          <Icon className="size-4 shrink-0" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex h-14 items-center gap-2 px-5 font-semibold">
      <img src="/favicon.svg" alt="" className="size-7" />
      LeadPilot
    </div>
  );
}

/** App shell: sidebar (drawer on mobile), top bar, and the routed page. */
export function AppLayout() {
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 border-r border-slate-200 bg-white lg:block dark:border-slate-800 dark:bg-slate-900">
        <Brand />
        <Sidebar />
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-white shadow-xl dark:bg-slate-900">
            <div className="flex items-center justify-between pr-3">
              <Brand />
              <button
                type="button"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="rounded-md p-2 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="size-5" />
              </button>
            </div>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
            className="rounded-md p-2 hover:bg-slate-100 lg:hidden dark:hover:bg-slate-800"
          >
            <Menu className="size-5" />
          </button>
          <div className="flex-1" />
          <ApiStatus />
          <ThemeToggle />
          <UserMenu />
        </header>
        <main className="mx-auto max-w-7xl p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-2 border-l border-slate-200 pl-3 dark:border-slate-800">
      <div className="hidden text-right leading-tight sm:block">
        <p className="text-sm font-medium">{user.full_name}</p>
        <p className="text-xs text-slate-500">{ROLE_LABEL[user.role]}</p>
      </div>
      <button
        type="button"
        onClick={logout}
        aria-label="Sign out"
        title="Sign out"
        className="rounded-md p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
      >
        <LogOut className="size-5" />
      </button>
    </div>
  );
}
