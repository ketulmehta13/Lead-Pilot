import { Info } from 'lucide-react';

/** Shown when no LLM API key is configured, so AI output is placeholder text. */
export function OfflineNotice() {
  return (
    <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>
        AI is in offline mode: results are placeholders. Add <code>GROQ_API_KEY</code> (or{' '}
        <code>ANTHROPIC_API_KEY</code>) to the backend <code>.env</code> for real output.
      </span>
    </p>
  );
}
