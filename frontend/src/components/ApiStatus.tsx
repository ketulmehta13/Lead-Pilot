import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../api/client';

/** Small pill in the top bar showing whether the backend /api/health/ answers. */
export function ApiStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

  const ok = data?.status === 'ok';
  const label = isLoading
    ? 'Checking API…'
    : ok
      ? 'API online'
      : isError
        ? 'API offline'
        : 'API degraded';
  const dot = isLoading ? 'bg-slate-400' : ok ? 'bg-emerald-500' : 'bg-rose-500';

  return (
    <span className="hidden items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 sm:inline-flex dark:border-slate-700 dark:text-slate-300">
      <span className={`size-2 rounded-full ${dot}`} aria-hidden />
      {label}
    </span>
  );
}
