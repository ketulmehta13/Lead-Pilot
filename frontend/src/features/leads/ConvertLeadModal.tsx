import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import type { z } from 'zod';
import { analyticsApi } from '../../api/analytics';
import { dealsApi, leadsApi } from '../../api/crm';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { OPEN_DEAL_STAGE_OPTIONS } from '../../lib/options';
import { convertLeadSchema } from '../../lib/schemas';
import type { DealStage, Lead } from '../../types';

type FormValues = z.infer<typeof convertLeadSchema>;
const FIELDS = ['title', 'value', 'stage', 'expected_close_date'] as const;

/** Mounted only while open, so default values come fresh from the lead each time. */
export function ConvertLeadModal({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const defaultTitle = `${lead.company_name ?? lead.contact_name} deal`;
  const { register, handleSubmit, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(convertLeadSchema),
    defaultValues: {
      title: defaultTitle,
      value: lead.budget ? String(Number(lead.budget)) : '',
      stage: 'qualified',
      expected_close_date: '',
    },
  });

  const mutation = useMutation({
    mutationFn: (v: FormValues) =>
      leadsApi.convert(lead.id, {
        title: v.title,
        value: v.value === '' ? null : v.value,
        stage: v.stage as DealStage,
        expected_close_date: v.expected_close_date || null,
      }),
    onSuccess: (deal) => {
      queryClient.invalidateQueries({ queryKey: [leadsApi.key] });
      queryClient.invalidateQueries({ queryKey: [dealsApi.key] });
      queryClient.invalidateQueries({ queryKey: [analyticsApi.key] });
      toast.success(`Created deal "${deal.title}"`);
      onClose();
      navigate('/pipeline');
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const e = formState.errors;
  return (
    <Modal
      open
      onClose={onClose}
      title={`Convert ${lead.contact_name} to a deal`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="convert-form" loading={mutation.isPending}>
            Create deal
          </Button>
        </>
      }
    >
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
        The lead is marked <strong>Converted</strong> and a deal is added to the pipeline.
      </p>
      <form
        id="convert-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-2"
      >
        <div className="sm:col-span-2">
          <TextField label="Deal title" error={e.title?.message} {...register('title')} />
        </div>
        <TextField
          label="Value (₹)"
          inputMode="decimal"
          hint="Defaults to the lead's budget."
          error={e.value?.message}
          {...register('value')}
        />
        <SelectField
          label="Starting stage"
          options={OPEN_DEAL_STAGE_OPTIONS}
          {...register('stage')}
        />
        <TextField
          label="Expected close"
          type="date"
          error={e.expected_close_date?.message}
          {...register('expected_close_date')}
        />
      </form>
    </Modal>
  );
}
