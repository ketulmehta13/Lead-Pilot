import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Building2, Mail, Pencil, Phone, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { activitiesApi, contactsApi, leadsApi, tasksApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Badge } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { formatDate, formatINR, timeAgo } from '../../lib/format';
import {
  LEAD_SOURCE_OPTIONS,
  LEAD_STATUS_OPTIONS,
  LEAD_STATUS_TONE,
  PRIORITY_TONE,
  labelOf,
} from '../../lib/options';
import { useAuth } from '../auth/AuthContext';
import { ChurnChip, SegmentChip } from '../../components/ml/CustomerChips';
import { ScoreBadge } from '../../components/ml/ScoreBadge';
import { ActivityTimeline } from './ActivityTimeline';
import { ContactFormModal } from './ContactFormModal';
import { LogActivityForm } from './LogActivityForm';

export function ContactDetailPage() {
  const id = Number(useParams().id);
  const { hasRole } = useAuth();
  const canEdit = hasRole('admin', 'sales');
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const contact = useQuery({
    queryKey: [contactsApi.key, 'detail', id],
    queryFn: () => contactsApi.get(id),
    enabled: Number.isFinite(id),
  });
  const activities = useQuery({
    queryKey: [activitiesApi.key, { contact: id }],
    queryFn: () => activitiesApi.list({ contact: id, ordering: '-occurred_at', page_size: 50 }),
    enabled: canEdit,
  });
  const leads = useQuery({
    queryKey: [leadsApi.key, { contact: id }],
    queryFn: () => leadsApi.list({ contact: id, page_size: 50 }),
    enabled: canEdit,
  });
  const tasks = useQuery({
    queryKey: [tasksApi.key, { contact: id, open: true }],
    queryFn: () => tasksApi.list({ contact: id, ordering: 'due_date', page_size: 50 }),
    enabled: canEdit,
  });

  const remove = useMutation({
    mutationFn: () => contactsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [contactsApi.key] });
      toast.success('Contact deleted');
      navigate('/contacts');
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  if (contact.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading contact" />
      </div>
    );
  }
  if (contact.isError || !contact.data) {
    const notFound = parseApiError(contact.error).status === 404;
    return (
      <div className="py-20 text-center">
        <p className="font-medium">
          {notFound ? 'Contact not found' : parseApiError(contact.error).message}
        </p>
        <Link
          to="/contacts"
          className="mt-3 inline-block text-indigo-600 hover:underline dark:text-indigo-400"
        >
          Back to contacts
        </Link>
      </div>
    );
  }

  const c = contact.data;
  const openTasks = (tasks.data?.results ?? []).filter((t) => t.status !== 'done');

  return (
    <section>
      <Link
        to="/contacts"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
      >
        <ArrowLeft className="size-4" /> Contacts
      </Link>

      <div className="mb-6 flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 sm:flex-row sm:items-start sm:justify-between dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-lg font-semibold text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300">
            {(c.first_name[0] ?? '') + (c.last_name[0] ?? '')}
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-semibold">{c.full_name}</h1>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
              <a
                href={`mailto:${c.email}`}
                className="inline-flex items-center gap-1 hover:underline"
              >
                <Mail className="size-3.5" /> {c.email}
              </a>
              {c.phone && (
                <a
                  href={`tel:${c.phone}`}
                  className="inline-flex items-center gap-1 hover:underline"
                >
                  <Phone className="size-3.5" /> {c.phone}
                </a>
              )}
              {c.company_name && (
                <span className="inline-flex items-center gap-1">
                  <Building2 className="size-3.5" /> {c.company_name}
                </span>
              )}
            </div>
            {(c.segment || c.churn_risk !== null) && (
              <div className="mt-2 flex flex-wrap gap-1">
                <SegmentChip segment={c.segment} />
                <ChurnChip risk={c.churn_risk} />
              </div>
            )}
            {c.tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {c.tags.map((t) => (
                  <Badge key={t}>{t}</Badge>
                ))}
              </div>
            )}
          </div>
        </div>
        {canEdit && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              <Pencil className="size-4" /> Edit
            </Button>
            <Button
              variant="secondary"
              aria-label="Delete contact"
              onClick={() => setDeleting(true)}
            >
              <Trash2 className="size-4 text-rose-500" />
            </Button>
          </div>
        )}
      </div>

      {canEdit ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <LogActivityForm contactId={c.id} />
            <div>
              <h2 className="mb-3 font-semibold">Timeline</h2>
              {activities.isLoading ? (
                <Spinner />
              ) : (
                <ActivityTimeline activities={activities.data?.results ?? []} />
              )}
            </div>
          </div>
          <aside className="space-y-6">
            <Panel title="Leads">
              {(leads.data?.results ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">No leads for this contact.</p>
              ) : (
                <ul className="space-y-3">
                  {leads.data!.results.map((l) => (
                    <li key={l.id} className="text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <ScoreBadge
                          score={l.score}
                          label={l.score_label}
                          factors={l.score_explanation}
                        />
                        <Badge tone={LEAD_STATUS_TONE[l.status]}>
                          {labelOf(LEAD_STATUS_OPTIONS, l.status)}
                        </Badge>
                        <span className="font-medium">{formatINR(l.budget)}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {labelOf(LEAD_SOURCE_OPTIONS, l.source)} · last contacted{' '}
                        {timeAgo(l.last_contacted_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Open tasks">
              {openTasks.length === 0 ? (
                <p className="text-sm text-slate-500">Nothing to do.</p>
              ) : (
                <ul className="space-y-2">
                  {openTasks.map((t) => (
                    <li key={t.id} className="flex items-center justify-between gap-2 text-sm">
                      <span>{t.title}</span>
                      <span className="flex items-center gap-2 text-xs text-slate-500">
                        {formatDate(t.due_date)}
                        <Badge tone={PRIORITY_TONE[t.priority]}>{t.priority}</Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </aside>
        </div>
      ) : (
        <p className="text-sm text-slate-500">Activity history is visible to the sales team.</p>
      )}

      <ContactFormModal open={editing} contact={c} onClose={() => setEditing(false)} />
      <ConfirmDialog
        open={deleting}
        title="Delete contact?"
        message={`${c.full_name} and their leads and activities will be permanently deleted.`}
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
        onCancel={() => setDeleting(false)}
      />
    </section>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-3 font-semibold">{title}</h2>
      {children}
    </div>
  );
}
