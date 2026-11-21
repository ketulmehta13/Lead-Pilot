import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ListChecks, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { activitiesApi, tasksApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { genaiApi, type ActionItem } from '../../api/genai';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/misc';
import type { Activity } from '../../types';

/** Notes shorter than this aren't worth summarizing. */
const SUMMARIZE_MIN_CHARS = 200;

interface Stored {
  items?: ActionItem[];
  sentiment?: 'positive' | 'neutral' | 'negative';
}

/** "Summarize" for long activity notes: AI summary, sentiment and action items -> tasks. */
export function ActivitySummary({ activity }: { activity: Activity }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const stored = (activity.action_items ?? {}) as Stored;
  const [selected, setSelected] = useState<number[]>([]);

  const summarize = useMutation({
    mutationFn: () => genaiApi.summarize(activity.id),
    onSuccess: (r) => {
      setSelected(r.action_items.map((_, i) => i));
      queryClient.invalidateQueries({ queryKey: [activitiesApi.key] });
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const createTasks = useMutation({
    mutationFn: () => genaiApi.actionItemsToTasks(activity.id, selected),
    onSuccess: (tasks) => {
      queryClient.invalidateQueries({ queryKey: [tasksApi.key] });
      toast.success(`Created ${tasks.length} task${tasks.length === 1 ? '' : 's'}`);
      setSelected([]);
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const summary = summarize.data?.summary ?? activity.summary;
  const items = summarize.data?.action_items ?? stored.items ?? [];
  const sentiment = summarize.data?.sentiment ?? stored.sentiment;

  if (!summary) {
    if ((activity.body ?? '').trim().length < SUMMARIZE_MIN_CHARS) return null;
    return (
      <Button
        variant="ghost"
        size="sm"
        className="mt-2 -ml-2"
        loading={summarize.isPending}
        onClick={() => summarize.mutate()}
      >
        <Sparkles className="size-3.5 text-indigo-500" /> Summarize
      </Button>
    );
  }

  const toggle = (i: number) =>
    setSelected((s) => (s.includes(i) ? s.filter((x) => x !== i) : [...s, i]));

  return (
    <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 text-sm dark:border-indigo-500/20 dark:bg-indigo-500/5">
      <div className="mb-1 flex items-center gap-2 text-xs font-medium text-indigo-700 dark:text-indigo-300">
        <Sparkles className="size-3.5" aria-hidden /> AI summary
        {sentiment && (
          <Badge
            tone={
              sentiment === 'positive' ? 'emerald' : sentiment === 'negative' ? 'rose' : 'slate'
            }
          >
            {sentiment}
          </Badge>
        )}
      </div>
      <p className="text-slate-700 dark:text-slate-200">{summary}</p>
      {items.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            <ListChecks className="size-3.5" aria-hidden /> Action items
          </p>
          <ul className="space-y-1">
            {items.map((item, i) => (
              <li key={`${item.title}-${i}`}>
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    checked={selected.includes(i)}
                    onChange={() => toggle(i)}
                    className="mt-0.5 size-4 accent-indigo-600"
                  />
                  <span>
                    {item.title}
                    {item.due_in_days !== null && (
                      <span className="text-xs text-slate-500">
                        {' '}
                        · due in {item.due_in_days} days
                      </span>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <Button
            size="sm"
            className="mt-2"
            disabled={selected.length === 0}
            loading={createTasks.isPending}
            onClick={() => createTasks.mutate()}
          >
            Create {selected.length || ''} task{selected.length === 1 ? '' : 's'} from action items
          </Button>
        </div>
      )}
    </div>
  );
}
