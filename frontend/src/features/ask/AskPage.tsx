import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  FileText,
  LifeBuoy,
  MessageSquarePlus,
  Send,
  Sparkles,
  Target,
  Trash2,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { parseApiError } from '../../api/errors';
import { askApi, genaiApi, type Citation, type ConversationMessage } from '../../api/genai';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { controlClass } from '../../components/ui/Field';
import { PageHeader } from '../../components/ui/misc';
import { formatDate, timeAgo } from '../../lib/format';
import { useAuth } from '../auth/AuthContext';
import { OfflineNotice } from '../genai/OfflineNotice';

const EXAMPLES_SALES = [
  'What did we discuss with my top customers last month?',
  'Which contacts asked about WhatsApp integration?',
  'Who is evaluating a competitor right now?',
  'Summarize the pricing objections from this month',
];
const EXAMPLES_SUPPORT = [
  'Which customers reported login problems this week?',
  'What are the most common complaints in open tickets?',
];

const SOURCE_ICON = { activity: FileText, ticket: LifeBuoy, lead: Target } as const;
const SOURCE_LABEL = { activity: 'Activity', ticket: 'Ticket', lead: 'Lead notes' } as const;

type Msg = Pick<ConversationMessage, 'role' | 'content' | 'citations'> & { id: string | number };

export function AskPage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const status = useQuery({ queryKey: ['genai', 'status'], queryFn: genaiApi.status });
  const conversations = useQuery({ queryKey: [askApi.key, 'list'], queryFn: askApi.conversations });

  const ask = useMutation({
    mutationFn: (question: string) => askApi.ask(question, conversationId),
    onMutate: (question) => {
      setMessages((m) => [
        ...m,
        { id: `u-${Date.now()}`, role: 'user', content: question, citations: [] },
      ]);
      setDraft('');
    },
    onSuccess: (r) => {
      setConversationId(r.conversation_id);
      setMessages((m) => [
        ...m,
        { id: `a-${Date.now()}`, role: 'assistant', content: r.answer, citations: r.citations },
      ]);
      queryClient.invalidateQueries({ queryKey: [askApi.key, 'list'] });
    },
    onError: (err) => {
      toast.error(parseApiError(err).message);
      setMessages((m) => m.slice(0, -1));
    },
  });

  const open = async (id: number) => {
    try {
      const convo = await askApi.conversation(id);
      setConversationId(convo.id);
      setMessages(convo.messages);
    } catch (err) {
      toast.error(parseApiError(err).message);
    }
  };

  const remove = useMutation({
    mutationFn: (id: number) => askApi.remove(id),
    onSuccess: (_, id) => {
      if (id === conversationId) startNew();
      queryClient.invalidateQueries({ queryKey: [askApi.key, 'list'] });
    },
  });

  const startNew = () => {
    setConversationId(null);
    setMessages([]);
  };

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [messages.length, ask.isPending]);

  const send = (text: string) => {
    const q = text.trim();
    if (q && !ask.isPending) ask.mutate(q);
  };

  const examples = hasRole('admin', 'sales') ? EXAMPLES_SALES : EXAMPLES_SUPPORT;

  return (
    <section>
      <PageHeader
        title="Ask LeadPilot"
        description="Questions about your CRM, answered from your own notes, activities and tickets, with sources."
        actions={
          <Button variant="secondary" onClick={startNew}>
            <MessageSquarePlus className="size-4" /> New chat
          </Button>
        }
      />
      <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
        <aside className="hidden rounded-xl border border-slate-200 bg-white p-2 lg:block dark:border-slate-800 dark:bg-slate-900">
          <p className="px-2 py-1.5 text-xs font-medium tracking-wide text-slate-500 uppercase">
            History
          </p>
          {(conversations.data ?? []).length === 0 && (
            <p className="px-2 py-2 text-sm text-slate-500">No conversations yet.</p>
          )}
          <ul className="space-y-0.5">
            {(conversations.data ?? []).map((c) => (
              <li key={c.id} className="group flex items-center">
                <button
                  type="button"
                  onClick={() => open(c.id)}
                  className={`min-w-0 flex-1 rounded-md px-2 py-1.5 text-left text-sm ${c.id === conversationId ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  <span className="block truncate">{c.title}</span>
                  <span className="text-xs text-slate-500">{timeAgo(c.updated_at)}</span>
                </button>
                <button
                  type="button"
                  aria-label={`Delete conversation ${c.title}`}
                  onClick={() => remove.mutate(c.id)}
                  className="rounded p-1 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-rose-500 focus:opacity-100"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="flex min-h-[60vh] flex-col rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
            {status.data && !status.data.configured && <OfflineNotice />}
            {messages.length === 0 && !ask.isPending && (
              <div className="py-10 text-center">
                <Sparkles className="mx-auto size-8 text-indigo-500" aria-hidden />
                <p className="mt-3 font-medium">Ask anything about your customers</p>
                <p className="mt-1 text-sm text-slate-500">
                  Answers only use records you can see, and link to their sources.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {examples.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => send(q)}
                      className="rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-300"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {ask.isPending && (
              <div className="flex items-center gap-2 text-sm text-slate-500" role="status">
                <span className="flex gap-1" aria-hidden>
                  <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-slate-400" />
                </span>
                Searching your CRM…
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form
            className="flex items-end gap-2 border-t border-slate-200 p-3 dark:border-slate-800"
            onSubmit={(e) => {
              e.preventDefault();
              send(draft);
            }}
          >
            <textarea
              aria-label="Your question"
              rows={1}
              value={draft}
              maxLength={1000}
              placeholder="e.g. What did we discuss with Acme last month?"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(draft);
                }
              }}
              className={`${controlClass} max-h-40 resize-none`}
            />
            <Button
              type="submit"
              disabled={!draft.trim()}
              loading={ask.isPending}
              aria-label="Send"
            >
              <Send className="size-4" />
            </Button>
          </form>
        </div>
      </div>
    </section>
  );
}

function MessageBubble({ message }: { message: Msg }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-3.5 py-2 text-sm whitespace-pre-line text-white">
          {message.content}
        </p>
      </div>
    );
  }
  return (
    <div className="max-w-[90%]">
      <p className="rounded-2xl rounded-bl-sm bg-slate-100 px-3.5 py-2 text-sm whitespace-pre-line dark:bg-slate-800">
        {message.content}
      </p>
      {message.citations.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Sources">
          {message.citations.map((c, i) => (
            <CitationChip key={`${c.type}-${c.id}-${i}`} citation={c} n={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function CitationChip({ citation, n }: { citation: Citation; n: number }) {
  const Icon = SOURCE_ICON[citation.type];
  return (
    <Link
      to={citation.link || '#'}
      title={citation.snippet}
      className="inline-flex max-w-xs items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
    >
      <span className="font-semibold text-indigo-600 dark:text-indigo-400">[{n}]</span>
      <Icon className="size-3 shrink-0" aria-hidden />
      <span className="truncate">
        {SOURCE_LABEL[citation.type]} #{citation.id}
        {citation.date ? ` · ${formatDate(citation.date)}` : ''}
      </span>
    </Link>
  );
}
