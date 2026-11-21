import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bot,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Hand,
  Play,
  ShieldCheck,
  X,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { agentApi, type AgentRun, type AgentStep, type RunStatus } from '../../api/agent';
import { parseApiError } from '../../api/errors';
import { genaiApi } from '../../api/genai';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { controlClass } from '../../components/ui/Field';
import { Badge, PageHeader, type Tone } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { timeAgo } from '../../lib/format';
import { OfflineNotice } from '../genai/OfflineNotice';

const EXAMPLES = [
  'Find hot leads not contacted in 7 days, draft follow-ups and create tasks',
  'Which of my deals in negotiation need attention this week?',
  'Summarize what my top 3 leads asked about recently',
];

const RUN_STATUS: Record<RunStatus, { label: string; tone: Tone }> = {
  planning: { label: 'Planning', tone: 'sky' },
  running: { label: 'Running', tone: 'sky' },
  awaiting_approval: { label: 'Needs your approval', tone: 'amber' },
  done: { label: 'Done', tone: 'emerald' },
  failed: { label: 'Failed', tone: 'rose' },
};

const TOOL_LABEL: Record<string, string> = {
  search_leads: 'Search leads',
  get_contact_history: 'Read contact history',
  draft_email: 'Draft email',
  ask_crm: 'Ask the CRM',
  create_task: 'Create task',
  update_deal_stage: 'Move deal stage',
  create_invoice: 'Create invoice',
  create_payment_link: 'Create payment link',
};

const isActive = (s?: RunStatus) => s === 'planning' || s === 'running';

export function AgentPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [goal, setGoal] = useState('');
  const [runId, setRunId] = useState<number | null>(null);

  const status = useQuery({ queryKey: ['genai', 'status'], queryFn: genaiApi.status });
  const runs = useQuery({ queryKey: [agentApi.key, 'list'], queryFn: agentApi.list });
  const run = useQuery({
    queryKey: [agentApi.key, 'run', runId],
    queryFn: () => agentApi.get(runId!),
    enabled: runId !== null,
    // Live step timeline: poll every 2 s while the agent is working.
    refetchInterval: (q) => (isActive(q.state.data?.status) ? 2000 : false),
  });

  const refresh = (r: AgentRun) => {
    queryClient.setQueryData([agentApi.key, 'run', r.id], r);
    queryClient.invalidateQueries({ queryKey: [agentApi.key, 'list'] });
    queryClient.invalidateQueries({ queryKey: [agentApi.key, 'run', r.id] });
  };

  const start = useMutation({
    mutationFn: (g: string) => agentApi.start(g),
    onSuccess: (r) => {
      setRunId(r.id);
      setGoal('');
      refresh(r);
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const decide = useMutation({
    mutationFn: ({ stepId, approve }: { stepId: number; approve: boolean }) =>
      agentApi.decide(stepId, approve),
    onSuccess: refresh,
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const current = run.data;

  return (
    <section>
      <PageHeader
        title="Agent"
        description="Give the agent a goal. It plans, uses CRM tools, and asks before changing anything."
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-4">
          <form
            className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
            onSubmit={(e) => {
              e.preventDefault();
              if (goal.trim().length >= 5) start.mutate(goal.trim());
            }}
          >
            {status.data && !status.data.configured && (
              <div className="mb-3">
                <OfflineNotice />
              </div>
            )}
            <label htmlFor="agent-goal" className="mb-1 block text-sm font-medium">
              Goal
            </label>
            <textarea
              id="agent-goal"
              rows={2}
              value={goal}
              maxLength={1000}
              placeholder="e.g. Find hot leads not contacted in 7 days, draft follow-ups and create tasks"
              onChange={(e) => setGoal(e.target.value)}
              className={controlClass}
            />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {EXAMPLES.map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => setGoal(g)}
                  className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-300"
                >
                  {g}
                </button>
              ))}
              <Button
                type="submit"
                className="ml-auto"
                loading={start.isPending}
                disabled={goal.trim().length < 5}
              >
                <Play className="size-4" /> Run agent
              </Button>
            </div>
            <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
              <ShieldCheck className="size-3.5" aria-hidden /> Read actions run automatically.
              Anything that changes data waits for your approval. Max 10 steps; it never sends
              emails, deletes data or moves money.
            </p>
          </form>

          {start.isPending && (
            <div className="flex justify-center py-10">
              <Spinner label="The agent is working" />
            </div>
          )}
          {current && !start.isPending && (
            <RunView
              run={current}
              deciding={decide.isPending ? decide.variables?.stepId : undefined}
              onDecide={(stepId, approve) => decide.mutate({ stepId, approve })}
            />
          )}
        </div>

        <aside className="rounded-xl border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
          <p className="px-2 py-1.5 text-xs font-medium tracking-wide text-slate-500 uppercase">
            Recent runs
          </p>
          {(runs.data ?? []).length === 0 && (
            <p className="px-2 py-2 text-sm text-slate-500">No runs yet.</p>
          )}
          <ul className="space-y-0.5">
            {(runs.data ?? []).map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setRunId(r.id)}
                  className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${r.id === runId ? 'bg-indigo-50 dark:bg-indigo-500/15' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  <span className="line-clamp-2">{r.goal}</span>
                  <span className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                    <Badge tone={RUN_STATUS[r.status].tone}>{RUN_STATUS[r.status].label}</Badge>
                    {timeAgo(r.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </section>
  );
}

function RunView({
  run,
  deciding,
  onDecide,
}: {
  run: AgentRun;
  deciding?: number;
  onDecide: (stepId: number, approve: boolean) => void;
}) {
  const meta = RUN_STATUS[run.status];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-slate-500">Goal</p>
          <p className="font-medium">{run.goal}</p>
        </div>
        <div className="flex items-center gap-2">
          {isActive(run.status) && <Spinner label="Working" />}
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <span className="text-xs text-slate-500 tabular-nums">
            {run.steps.length}/{run.max_steps} steps
          </span>
        </div>
      </div>

      <ol className="mt-4 space-y-3" aria-label="Agent steps">
        {run.steps.map((step) => (
          <StepCard
            key={step.id}
            step={step}
            busy={deciding === step.id}
            onDecide={(approve) => onDecide(step.id, approve)}
          />
        ))}
        {run.steps.length === 0 && isActive(run.status) && (
          <li className="text-sm text-slate-500">Planning…</li>
        )}
      </ol>

      {run.status === 'done' && run.final_summary && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm dark:border-emerald-500/30 dark:bg-emerald-500/10">
          <p className="mb-1 flex items-center gap-1.5 font-medium text-emerald-800 dark:text-emerald-300">
            <Bot className="size-4" aria-hidden /> Summary
          </p>
          <p className="whitespace-pre-line text-slate-700 dark:text-slate-200">
            {run.final_summary}
          </p>
        </div>
      )}
      {run.status === 'failed' && (
        <p
          role="alert"
          className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
        >
          The agent stopped: {run.error || 'unknown error'}
        </p>
      )}
    </div>
  );
}

const STEP_ICON = {
  done: <CheckCircle2 className="size-4 text-emerald-500" aria-label="done" />,
  pending_approval: <Hand className="size-4 text-amber-500" aria-label="waiting for approval" />,
  rejected: <XCircle className="size-4 text-slate-400" aria-label="rejected" />,
  failed: <XCircle className="size-4 text-rose-500" aria-label="failed" />,
};

function StepCard({
  step,
  busy,
  onDecide,
}: {
  step: AgentStep;
  busy: boolean;
  onDecide: (approve: boolean) => void;
}) {
  const pending = step.status === 'pending_approval';
  return (
    <li
      className={`rounded-lg border p-3 text-sm ${pending ? 'border-amber-300 bg-amber-50/60 dark:border-amber-500/40 dark:bg-amber-500/5' : 'border-slate-200 dark:border-slate-700'}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        {STEP_ICON[step.status]}
        <span className="font-medium">
          {step.order}. {TOOL_LABEL[step.tool_name] ?? step.tool_name}
        </span>
        {step.requires_approval && <Badge tone="amber">write</Badge>}
        {step.status === 'rejected' && <Badge>rejected by you</Badge>}
        {step.approved === true && <Badge tone="emerald">approved</Badge>}
      </div>
      {step.note && <p className="mt-1 text-slate-600 dark:text-slate-300">{step.note}</p>}

      {step.tool_name === 'draft_email' && step.tool_output && 'body' in step.tool_output ? (
        <EmailPreview output={step.tool_output} />
      ) : null}

      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-slate-500 select-none hover:text-slate-800 dark:hover:text-slate-200">
          Input
        </summary>
        <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-xs dark:bg-slate-800">
          {JSON.stringify(step.tool_input, null, 2)}
        </pre>
      </details>
      {step.tool_output && (
        <details className="mt-1">
          <summary className="cursor-pointer text-xs text-slate-500 select-none hover:text-slate-800 dark:hover:text-slate-200">
            Output
          </summary>
          <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs dark:bg-slate-800">
            {JSON.stringify(step.tool_output, null, 2)}
          </pre>
        </details>
      )}

      {pending && (
        <div className="mt-3 flex items-center gap-2">
          <Clock className="size-3.5 text-amber-600" aria-hidden />
          <span className="text-xs text-amber-800 dark:text-amber-300">
            This changes your CRM. Approve to run it.
          </span>
          <div className="ml-auto flex gap-2">
            <Button size="sm" variant="secondary" loading={busy} onClick={() => onDecide(false)}>
              <X className="size-3.5" /> Reject
            </Button>
            <Button size="sm" loading={busy} onClick={() => onDecide(true)}>
              <Check className="size-3.5" /> Approve
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

function EmailPreview({ output }: { output: Record<string, unknown> }) {
  const [copied, setCopied] = useState(false);
  const subject = String(output.subject ?? '');
  const body = String(output.body ?? '');
  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-white p-2.5 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-slate-500">
          To {String(output.to ?? '')} · <span className="font-medium">{subject}</span>
        </p>
        <button
          type="button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
              setCopied(true);
            } catch {
              setCopied(false);
            }
          }}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600"
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <p className="mt-1 text-sm whitespace-pre-line">{body}</p>
    </div>
  );
}
