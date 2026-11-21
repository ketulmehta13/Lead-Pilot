import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Send } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { parseApiError } from '../../api/errors';
import { ticketsApi } from '../../api/support';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { controlClass } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { Spinner } from '../../components/ui/Spinner';
import { formatDateTime, timeAgo } from '../../lib/format';
import { TICKET_PRIORITY_OPTIONS, TICKET_STATUS_OPTIONS } from '../../lib/options';
import type { Ticket, TicketPriority, TicketStatus } from '../../types';
import { PriorityBadge, SentimentBadge } from './badges';

export function TicketDetailModal({
  ticket,
  canEdit,
  onClose,
}: {
  ticket: Ticket;
  canEdit: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [comment, setComment] = useState('');
  const detail = useQuery({
    queryKey: [ticketsApi.key, 'detail', ticket.id],
    queryFn: () => ticketsApi.get(ticket.id),
    initialData: ticket,
  });
  const comments = useQuery({
    queryKey: [ticketsApi.key, 'comments', ticket.id],
    queryFn: () => ticketsApi.comments(ticket.id),
  });
  const t = detail.data;

  const update = useMutation({
    mutationFn: (input: { status?: TicketStatus; priority?: TicketPriority }) =>
      ticketsApi.update(ticket.id, input),
    onSuccess: (saved) => {
      queryClient.setQueryData([ticketsApi.key, 'detail', ticket.id], saved);
      queryClient.invalidateQueries({ queryKey: [ticketsApi.key] });
      toast.success('Ticket updated');
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const addComment = useMutation({
    mutationFn: () => ticketsApi.addComment(ticket.id, comment.trim()),
    onSuccess: () => {
      setComment('');
      queryClient.invalidateQueries({ queryKey: [ticketsApi.key, 'comments', ticket.id] });
      queryClient.invalidateQueries({ queryKey: [ticketsApi.key] });
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  return (
    <Modal open onClose={onClose} size="lg" title={t.subject}>
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge priority={t.priority} urgent={t.urgent} />
          <SentimentBadge sentiment={t.sentiment} score={t.sentiment_score} />
          {t.priority_overridden && (
            <span className="text-xs text-slate-500">Priority set manually</span>
          )}
        </div>
        <p className="text-slate-500">
          <Link
            to={`/contacts/${t.contact}`}
            className="font-medium text-slate-700 hover:underline dark:text-slate-200"
          >
            {t.contact_name}
          </Link>
          {t.company_name ? ` · ${t.company_name}` : ''} · opened {timeAgo(t.created_at)}
          {t.owner_name ? ` by ${t.owner_name}` : ''}
        </p>
        <p className="rounded-lg bg-slate-50 p-3 whitespace-pre-line dark:bg-slate-800/60">
          {t.description}
        </p>

        {canEdit && (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs font-medium">Status</span>
              <select
                className={controlClass}
                value={t.status}
                disabled={update.isPending}
                onChange={(e) => update.mutate({ status: e.target.value as TicketStatus })}
              >
                {TICKET_STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium">Priority</span>
              <select
                className={controlClass}
                value={t.priority}
                disabled={update.isPending}
                onChange={(e) => update.mutate({ priority: e.target.value as TicketPriority })}
              >
                {TICKET_PRIORITY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div>
          <h3 className="mb-2 font-semibold">Comments</h3>
          {comments.isLoading ? (
            <Spinner />
          ) : (comments.data ?? []).length === 0 ? (
            <p className="text-slate-500">No comments yet.</p>
          ) : (
            <ul className="space-y-2">
              {comments.data!.map((c) => (
                <li
                  key={c.id}
                  className="rounded-lg border border-slate-200 p-2.5 dark:border-slate-700"
                >
                  <p className="text-xs text-slate-500" title={formatDateTime(c.created_at)}>
                    {c.author_name ?? 'Unknown'} · {timeAgo(c.created_at)}
                  </p>
                  <p className="mt-1 whitespace-pre-line">{c.body}</p>
                </li>
              ))}
            </ul>
          )}
          {canEdit && (
            <form
              className="mt-3 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (comment.trim()) addComment.mutate();
              }}
            >
              <input
                aria-label="Add a comment"
                placeholder="Add a comment…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className={controlClass}
              />
              <Button type="submit" loading={addComment.isPending} disabled={!comment.trim()}>
                <Send className="size-4" />
                <span className="sr-only sm:not-sr-only">Send</span>
              </Button>
            </form>
          )}
        </div>
      </div>
    </Modal>
  );
}
