import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { activitiesApi, leadsApi } from '../../api/crm';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field';
import { applyServerErrors } from '../../lib/forms';
import { ACTIVITY_TYPE_OPTIONS } from '../../lib/options';
import type { ActivityType } from '../../types';

const activitySchema = z.object({
  type: z.enum(['call', 'email', 'meeting', 'note']),
  subject: z.string().trim().min(1, 'Subject is required').max(200),
  body: z.string().max(10_000),
  occurred_at: z
    .string()
    .min(1, 'Pick a date and time')
    .refine((v) => new Date(v).getTime() <= Date.now() + 60_000, 'Cannot be in the future'),
});
type FormValues = z.infer<typeof activitySchema>;
const FIELDS = ['type', 'subject', 'body', 'occurred_at'] as const;

/** Current local time in the format <input type="datetime-local"> expects. */
function nowLocal(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

export function LogActivityForm({ contactId }: { contactId: number }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const defaults = (): FormValues => ({
    type: 'call',
    subject: '',
    body: '',
    occurred_at: nowLocal(),
  });
  const { register, handleSubmit, reset, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(activitySchema),
    defaultValues: defaults(),
  });

  const mutation = useMutation({
    mutationFn: (v: FormValues) =>
      activitiesApi.create({
        ...v,
        type: v.type as ActivityType,
        contact: contactId,
        occurred_at: new Date(v.occurred_at).toISOString(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [activitiesApi.key] });
      // Calls/emails/meetings update the contact's leads (last contacted, status).
      queryClient.invalidateQueries({ queryKey: [leadsApi.key] });
      toast.success('Activity logged');
      reset(defaults());
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const e = formState.errors;
  return (
    <form
      noValidate
      onSubmit={handleSubmit((v) => mutation.mutate(v))}
      className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
      aria-label="Log activity"
    >
      <h2 className="font-semibold">Log activity</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField label="Type" options={ACTIVITY_TYPE_OPTIONS} {...register('type')} />
        <div className="sm:col-span-2">
          <TextField
            label="When"
            type="datetime-local"
            error={e.occurred_at?.message}
            {...register('occurred_at')}
          />
        </div>
      </div>
      <TextField
        label="Subject"
        required
        placeholder="e.g. Discovery call"
        error={e.subject?.message}
        {...register('subject')}
      />
      <TextAreaField label="Notes" rows={3} error={e.body?.message} {...register('body')} />
      <div className="flex justify-end">
        <Button type="submit" loading={mutation.isPending}>
          Log activity
        </Button>
      </div>
    </form>
  );
}
