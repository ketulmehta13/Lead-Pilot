import { useMutation, useQuery } from '@tanstack/react-query';
import { Check, Copy, Mail, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { parseApiError } from '../../api/errors';
import { genaiApi, type Tone } from '../../api/genai';
import { Button } from '../../components/ui/Button';
import { controlClass } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import type { Contact } from '../../types';
import { OfflineNotice } from './OfflineNotice';

const TONES: { value: Tone; label: string }[] = [
  { value: 'friendly', label: 'Friendly' },
  { value: 'professional', label: 'Professional' },
  { value: 'concise', label: 'Concise' },
  { value: 'enthusiastic', label: 'Enthusiastic' },
  { value: 'formal', label: 'Formal' },
];

const GOAL_EXAMPLES = ['Follow up on the demo', 'Send the proposal', 'Book a renewal call'];

/** Draft a follow-up email with AI from the contact's history; editable before sending. */
export function DraftEmailModal({ contact, onClose }: { contact: Contact; onClose: () => void }) {
  const [goal, setGoal] = useState('');
  const [tone, setTone] = useState<Tone>('friendly');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [copied, setCopied] = useState(false);
  const status = useQuery({ queryKey: [genaiApi.key, 'status'], queryFn: genaiApi.status });

  const draft = useMutation({
    mutationFn: () => genaiApi.draftEmail({ contact_id: contact.id, goal, tone }),
    onSuccess: (d) => {
      setSubject(d.subject);
      setBody(d.body);
      setCopied(false);
    },
  });

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const mailto = `mailto:${contact.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  const hasDraft = subject !== '' || body !== '';

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Draft an email to ${contact.full_name}`}
      footer={
        hasDraft ? (
          <>
            <Button variant="secondary" onClick={copy}>
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
            <a
              href={mailto}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              <Mail className="size-4" /> Open in email app
            </a>
          </>
        ) : undefined
      }
    >
      <div className="space-y-4 text-sm">
        {status.data && !status.data.configured && <OfflineNotice />}
        <div>
          <label htmlFor="ai-goal" className="mb-1 block font-medium">
            What should the email achieve?
          </label>
          <input
            id="ai-goal"
            value={goal}
            maxLength={500}
            placeholder="e.g. send pricing for 25 seats and book a call"
            onChange={(e) => setGoal(e.target.value)}
            className={controlClass}
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {GOAL_EXAMPLES.map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setGoal(g)}
                className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-300"
              >
                {g}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-end gap-3">
          <label className="block flex-1">
            <span className="mb-1 block font-medium">Tone</span>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value as Tone)}
              className={controlClass}
            >
              {TONES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <Button onClick={() => draft.mutate()} loading={draft.isPending}>
            <Sparkles className="size-4" />
            {hasDraft ? 'Regenerate' : 'Draft with AI'}
          </Button>
        </div>
        {draft.isPending && (
          <p className="text-slate-500" role="status">
            Reading {contact.first_name}&apos;s recent activity and deals…
          </p>
        )}
        {draft.isError && (
          <p
            role="alert"
            className="rounded-lg bg-rose-50 px-3 py-2 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
          >
            {parseApiError(draft.error).message}
          </p>
        )}
        {hasDraft && (
          <div className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
            <label className="block">
              <span className="mb-1 block font-medium">Subject</span>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className={controlClass}
              />
            </label>
            <label className="block">
              <span className="mb-1 block font-medium">Body</span>
              <textarea
                rows={10}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className={controlClass}
              />
            </label>
            <p className="text-xs text-slate-500">AI draft: review and edit before sending.</p>
          </div>
        )}
      </div>
    </Modal>
  );
}
