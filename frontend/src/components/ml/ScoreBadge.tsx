import { ArrowDownRight, ArrowUpRight, HelpCircle } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import type { ScoreFactor, ScoreLabel } from '../../types';

const TONE: Record<ScoreLabel, string> = {
  hot: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/15 dark:text-rose-300 dark:ring-rose-500/30',
  warm: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/30',
  cold: 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-500/30',
};
const LABEL: Record<ScoreLabel, string> = { hot: 'Hot', warm: 'Warm', cold: 'Cold' };

interface Props {
  score: number | null;
  label: ScoreLabel | null;
  factors: ScoreFactor[] | null;
}

/** AI lead score (0-100) with a "Why?" popover listing the top SHAP factors. */
export function ScoreBadge({ score, label, factors }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (score === null || label === null) {
    return <span className="text-xs text-slate-400">Not scored</span>;
  }

  return (
    <div
      ref={ref}
      className="relative inline-flex items-center gap-1"
      onClick={(e) => e.stopPropagation()}
    >
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ring-1 ring-inset ${TONE[label]}`}
      >
        {score}
        <span className="font-medium">{LABEL[label]}</span>
      </span>
      {factors && factors.length > 0 && (
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-0.5 rounded px-1 text-xs text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400"
        >
          <HelpCircle className="size-3.5" aria-hidden />
          Why?
        </button>
      )}
      {open && factors && (
        <div
          id={panelId}
          role="dialog"
          aria-label={`Why this lead scores ${score}`}
          className="absolute top-full right-0 z-30 mt-1 w-72 rounded-lg border border-slate-200 bg-white p-3 text-left text-xs shadow-lg dark:border-slate-700 dark:bg-slate-800"
        >
          <p className="mb-2 font-medium text-slate-900 dark:text-slate-100">
            Top factors behind this score
          </p>
          <ul className="space-y-2">
            {factors.map((f) => (
              <li key={f.feature} className="flex items-start gap-2">
                {f.direction === 'up' ? (
                  <ArrowUpRight
                    className="mt-0.5 size-3.5 shrink-0 text-emerald-600"
                    aria-label="raises score"
                  />
                ) : (
                  <ArrowDownRight
                    className="mt-0.5 size-3.5 shrink-0 text-rose-600"
                    aria-label="lowers score"
                  />
                )}
                <span className="text-slate-700 dark:text-slate-200">
                  <span className="font-medium">{f.label}</span>: {f.value}
                  <span className="block text-slate-500">
                    {f.direction === 'up' ? 'Raises' : 'Lowers'} the score (impact{' '}
                    {f.impact > 0 ? '+' : ''}
                    {f.impact.toFixed(2)})
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 border-t border-slate-100 pt-2 text-slate-500 dark:border-slate-700">
            XGBoost model · SHAP values. Updates automatically when the lead or its activity
            changes.
          </p>
        </div>
      )}
    </div>
  );
}
