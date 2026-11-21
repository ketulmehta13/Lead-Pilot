import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { ticketsApi } from '../../api/support';
import { ContactSelect } from '../../components/ContactSelect';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { ticketSchema } from '../../lib/schemas';
import type { TicketPriority } from '../../types';
import { TICKET_PRIORITY_OPTIONS } from '../../lib/options';

type FormValues = z.infer<typeof ticketSchema>;
const FIELDS = ['subject', 'description', 'contact', 'priority'] as const;

/** New ticket. Priority defaults to "Auto": the sentiment model sets it from the text. */
export function TicketFormModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(ticketSchema),
    defaultValues: { subject: '', description: '', contact: '', priority: '' },
  });

  const mutation = useMutation({
    mutationFn: (v: FormValues) =>
      ticketsApi.create({
        subject: v.subject,
        description: v.description,
        contact: Number(v.contact),
        ...(v.priority ? { priority: v.priority as TicketPriority } : {}),
      }),
    onSuccess: (t) => {
      queryClient.invalidateQueries({ queryKey: [ticketsApi.key] });
      toast.success(
        t.sentiment
          ? `Ticket logged: ${t.sentiment} sentiment, ${t.priority} priority`
          : 'Ticket logged',
      );
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const e = formState.errors;
  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="New ticket"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="ticket-form" loading={mutation.isPending}>
            Create ticket
          </Button>
        </>
      }
    >
      <form
        id="ticket-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="space-y-4"
      >
        <TextField label="Subject" required error={e.subject?.message} {...register('subject')} />
        <TextAreaField
          label="Description"
          required
          rows={5}
          placeholder="What is the customer reporting?"
          error={e.description?.message}
          {...register('description')}
        />
        <ContactSelect required registration={register('contact')} error={e.contact?.message} />
        <SelectField
          label="Priority"
          hint="Auto: set from the text's sentiment and urgency."
          options={[{ value: '', label: 'Auto (AI)' }, ...TICKET_PRIORITY_OPTIONS]}
          {...register('priority')}
        />
      </form>
    </Modal>
  );
}
