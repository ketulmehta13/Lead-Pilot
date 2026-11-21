import { Calendar, Mail, Phone, StickyNote, type LucideIcon } from 'lucide-react';
import { formatDateTime, timeAgo } from '../../lib/format';
import type { Activity, ActivityType } from '../../types';

const ICONS: Record<ActivityType, LucideIcon> = {
  call: Phone,
  email: Mail,
  meeting: Calendar,
  note: StickyNote,
};
const TONES: Record<ActivityType, string> = {
  call: 'bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300',
  email: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300',
  meeting: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  note: 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300',
};

export function ActivityTimeline({ activities }: { activities: Activity[] }) {
  if (activities.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500 dark:border-slate-700">
        No activity yet. Log the first call, email or note.
      </p>
    );
  }
  return (
    <ol className="relative space-y-5 border-l border-slate-200 pl-6 dark:border-slate-800">
      {activities.map((a) => {
        const Icon = ICONS[a.type];
        return (
          <li key={a.id} className="relative">
            <span
              className={`absolute top-0 -left-[37px] flex size-7 items-center justify-center rounded-full ring-4 ring-slate-50 dark:ring-slate-950 ${TONES[a.type]}`}
            >
              <Icon className="size-3.5" aria-hidden />
            </span>
            <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <p className="font-medium">{a.subject}</p>
                <time
                  dateTime={a.occurred_at}
                  title={formatDateTime(a.occurred_at)}
                  className="text-xs text-slate-500"
                >
                  {timeAgo(a.occurred_at)}
                  {a.owner_name ? ` · ${a.owner_name}` : ''}
                </time>
              </div>
              {a.body && (
                <p className="mt-2 text-sm whitespace-pre-line text-slate-600 dark:text-slate-300">
                  {a.body}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
