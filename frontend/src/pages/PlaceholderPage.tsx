import { Construction } from 'lucide-react';

interface Props {
  title: string;
  description: string;
  phase: number;
}

/** Stand-in page shown until a route's feature is built in its phase. */
export function PlaceholderPage({ title, description, phase }: Props) {
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <div className="mt-6 flex flex-col items-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center dark:border-slate-700 dark:bg-slate-900">
        <Construction className="size-10 text-slate-400" aria-hidden />
        <p className="mt-4 max-w-md text-slate-600 dark:text-slate-400">{description}</p>
        <span className="mt-4 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300">
          Coming in Phase {phase}
        </span>
      </div>
    </section>
  );
}
