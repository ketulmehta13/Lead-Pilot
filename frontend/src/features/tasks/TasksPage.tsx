import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, Plus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { tasksApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { Badge, FilterSelect, PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { useListParams } from '../../hooks/useListParams';
import { formatDate, todayISO } from '../../lib/format';
import {
  PRIORITY_TONE,
  TASK_PRIORITY_OPTIONS,
  TASK_STATUS_OPTIONS,
  labelOf,
} from '../../lib/options';
import type { Task, TaskStatus } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { TaskFormModal } from './TaskFormModal';

const VIEWS = [
  { value: 'open', label: 'Open' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'done', label: 'Done' },
  { value: 'all', label: 'All' },
] as const;
type View = (typeof VIEWS)[number]['value'];

function viewParams(view: View) {
  const yesterday = new Date(Date.now() - 86_400_000);
  const y = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;
  switch (view) {
    case 'open':
      return { open: true };
    case 'overdue':
      return { open: true, due_before: y };
    case 'done':
      return { open: false };
    default:
      return {};
  }
}

export function TasksPage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>('open');
  const list = useListParams({ priority: '' }, 'due_date');
  const [editing, setEditing] = useState<Task | null>(null);
  const [creating, setCreating] = useState(false);
  const params = { ...list.params, ...viewParams(view) };

  const query = useQuery({
    queryKey: [tasksApi.key, params],
    queryFn: () => tasksApi.list(params),
    placeholderData: keepPreviousData,
  });

  const toggle = useMutation({
    mutationFn: ({ id, status }: { id: number; status: TaskStatus }) =>
      tasksApi.update(id, { status }),
    onSuccess: (task) => {
      queryClient.invalidateQueries({ queryKey: [tasksApi.key] });
      toast.success(task.status === 'done' ? 'Task completed' : 'Task reopened');
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const today = todayISO();
  const columns: Column<Task>[] = [
    {
      key: 'done',
      header: '',
      className: 'w-10',
      render: (t) => (
        <input
          type="checkbox"
          aria-label={t.status === 'done' ? `Reopen ${t.title}` : `Complete ${t.title}`}
          checked={t.status === 'done'}
          disabled={toggle.isPending}
          onClick={(e) => e.stopPropagation()}
          onChange={() =>
            toggle.mutate({ id: t.id, status: t.status === 'done' ? 'todo' : 'done' })
          }
          className="size-4 rounded border-slate-300 accent-indigo-600"
        />
      ),
    },
    {
      key: 'title',
      header: 'Task',
      render: (t) => (
        <div>
          <p className={`font-medium ${t.status === 'done' ? 'text-slate-400 line-through' : ''}`}>
            {t.title}
            {t.created_by_agent && (
              <Bot
                className="ml-1.5 inline size-3.5 text-indigo-500"
                aria-label="Created by the agent"
              />
            )}
          </p>
          {t.contact && (
            <Link
              to={`/contacts/${t.contact}`}
              onClick={(e) => e.stopPropagation()}
              className="text-xs text-slate-500 hover:underline"
            >
              {t.contact_name}
            </Link>
          )}
        </div>
      ),
    },
    {
      key: 'due',
      header: 'Due',
      sortField: 'due_date',
      render: (t) => {
        const overdue = t.due_date && t.status !== 'done' && t.due_date < today;
        return (
          <span className={overdue ? 'font-medium text-rose-600 dark:text-rose-400' : ''}>
            {formatDate(t.due_date)}
            {overdue && ' · overdue'}
          </span>
        );
      },
    },
    {
      key: 'priority',
      header: 'Priority',
      sortField: 'priority',
      render: (t) => (
        <Badge tone={PRIORITY_TONE[t.priority]}>{labelOf(TASK_PRIORITY_OPTIONS, t.priority)}</Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      className: 'hidden md:table-cell',
      render: (t) => labelOf(TASK_STATUS_OPTIONS, t.status),
    },
    ...(hasRole('admin')
      ? [
          {
            key: 'assignee',
            header: 'Assigned to',
            className: 'hidden lg:table-cell',
            render: (t: Task) => t.assigned_to_name ?? '—',
          },
        ]
      : []),
  ];

  return (
    <section>
      <PageHeader
        title="Tasks"
        description="Follow-ups and reminders."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> New task
          </Button>
        }
      />
      <div
        role="tablist"
        aria-label="Task views"
        className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-800 dark:bg-slate-900"
      >
        {VIEWS.map((v) => (
          <button
            key={v.value}
            type="button"
            role="tab"
            aria-selected={view === v.value}
            onClick={() => {
              setView(v.value);
              list.setPage(1);
            }}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${view === v.value ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}`}
          >
            {v.label}
          </button>
        ))}
      </div>
      <Toolbar>
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search tasks" />
        <FilterSelect
          label="Priority"
          value={list.filters.priority}
          onChange={(v) => list.setFilter('priority', v)}
          options={TASK_PRIORITY_OPTIONS}
        />
      </Toolbar>
      <DataTable
        columns={columns}
        rows={query.data?.results}
        rowKey={(t) => t.id}
        loading={query.isFetching}
        error={query.isError ? parseApiError(query.error).message : null}
        emptyTitle={view === 'overdue' ? 'Nothing overdue 🎉' : 'No tasks here'}
        ordering={list.ordering}
        onOrderingChange={list.setOrdering}
        onRowClick={setEditing}
        page={list.page}
        total={query.data?.count}
        onPageChange={list.setPage}
      />
      <TaskFormModal
        open={creating || editing !== null}
        task={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
    </section>
  );
}
