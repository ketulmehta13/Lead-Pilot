import type { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { leadsApi } from '../../api/crm';
import { ContactSelect } from '../../components/ContactSelect';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextAreaField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { leadSchema } from '../../lib/schemas';
import { LEAD_SOURCE_OPTIONS, LEAD_STATUS_OPTIONS } from '../../lib/options';
import type { Lead, LeadSource, LeadStatus } from '../../types';

type FormValues = z.infer<typeof leadSchema>;
const FIELDS = ['contact', 'source', 'status', 'budget', 'notes'] as const;
const empty: FormValues = { contact: '', source: 'web', status: 'new', budget: '', notes: '' };

interface Props {
  open: boolean;
  lead?: Lead | null;
  onClose: () => void;
}

export function LeadFormModal({ open, lead, onClose }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(leadSchema),
    defaultValues: empty,
  });

  useEffect(() => {
    if (!open) return;
    reset(
      lead
        ? {
            contact: String(lead.contact),
            source: lead.source,
            status: lead.status,
            budget: lead.budget ? String(Number(lead.budget)) : '',
            notes: lead.notes,
          }
        : empty,
    );
  }, [open, lead, reset]);

  const mutation = useMutation({
    mutationFn: (v: FormValues) => {
      const payload = {
        contact: Number(v.contact),
        source: v.source as LeadSource,
        status: v.status as LeadStatus,
        budget: v.budget === '' ? null : v.budget,
        notes: v.notes,
      };
      return lead ? leadsApi.update(lead.id, payload) : leadsApi.create(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [leadsApi.key] });
      toast.success(lead ? 'Lead updated' : 'Lead created');
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const e = formState.errors;
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={lead ? 'Edit lead' : 'New lead'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="lead-form" loading={mutation.isPending}>
            {lead ? 'Save changes' : 'Create lead'}
          </Button>
        </>
      }
    >
      <form
        id="lead-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-2"
      >
        <div className="sm:col-span-2">
          <ContactSelect
            required
            registration={register('contact')}
            error={e.contact?.message}
            current={lead ? { id: lead.contact, name: lead.contact_name } : null}
          />
        </div>
        <SelectField label="Source" options={LEAD_SOURCE_OPTIONS} {...register('source')} />
        <SelectField label="Status" options={LEAD_STATUS_OPTIONS} {...register('status')} />
        <div className="sm:col-span-2">
          <TextField
            label="Budget (₹)"
            inputMode="decimal"
            placeholder="250000"
            error={e.budget?.message}
            {...register('budget')}
          />
        </div>
        <div className="sm:col-span-2">
          <TextAreaField label="Notes" error={e.notes?.message} {...register('notes')} />
        </div>
      </form>
    </Modal>
  );
}
