import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import type { z } from 'zod';
import { analyticsApi } from '../../api/analytics';
import { dealsApi, leadsApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { ContactSelect } from '../../components/ContactSelect';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { SelectField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { formatDateTime } from '../../lib/format';
import { applyServerErrors } from '../../lib/forms';
import { DEAL_STAGE_OPTIONS } from '../../lib/options';
import { dealSchema } from '../../lib/schemas';
import type { Deal, DealStage } from '../../types';

type FormValues = z.infer<typeof dealSchema>;
const FIELDS = [
  'title',
  'contact',
  'value',
  'stage',
  'expected_close_date',
  'probability',
] as const;
const empty: FormValues = {
  title: '',
  contact: '',
  value: '',
  stage: 'new',
  expected_close_date: '',
  probability: '',
};

interface Props {
  open: boolean;
  deal?: Deal | null;
  onClose: () => void;
}

export function DealFormModal({ open, deal, onClose }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { register, handleSubmit, reset, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(dealSchema),
    defaultValues: empty,
  });

  useEffect(() => {
    if (!open) return;
    reset(
      deal
        ? {
            title: deal.title,
            contact: String(deal.contact),
            value: String(Number(deal.value)),
            stage: deal.stage,
            expected_close_date: deal.expected_close_date ?? '',
            probability: String(deal.probability),
          }
        : empty,
    );
  }, [open, deal, reset]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: [dealsApi.key] });
    queryClient.invalidateQueries({ queryKey: [analyticsApi.key] });
    queryClient.invalidateQueries({ queryKey: [leadsApi.key] });
  };

  const save = useMutation({
    mutationFn: (v: FormValues) => {
      const payload = {
        title: v.title,
        contact: Number(v.contact),
        value: v.value,
        stage: v.stage as DealStage,
        expected_close_date: v.expected_close_date || null,
        // Leave probability to the stage default unless the user typed one.
        ...(v.probability !== '' ? { probability: Number(v.probability) } : {}),
      };
      return deal ? dealsApi.update(deal.id, payload) : dealsApi.create(payload);
    },
    onSuccess: () => {
      refresh();
      toast.success(deal ? 'Deal updated' : 'Deal created');
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const remove = useMutation({
    mutationFn: () => dealsApi.remove(deal!.id),
    onSuccess: () => {
      refresh();
      toast.success('Deal deleted');
      setConfirmDelete(false);
      onClose();
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const e = formState.errors;
  return (
    <>
      <Modal
        open={open && !confirmDelete}
        onClose={onClose}
        title={deal ? 'Edit deal' : 'New deal'}
        footer={
          <>
            {deal && (
              <Button
                variant="ghost"
                className="mr-auto"
                aria-label="Delete deal"
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 className="size-4 text-rose-500" /> Delete
              </Button>
            )}
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="deal-form" loading={save.isPending}>
              {deal ? 'Save changes' : 'Create deal'}
            </Button>
          </>
        }
      >
        <form
          id="deal-form"
          noValidate
          onSubmit={handleSubmit((v) => save.mutate(v))}
          className="grid gap-4 sm:grid-cols-2"
        >
          <div className="sm:col-span-2">
            <TextField label="Title" required error={e.title?.message} {...register('title')} />
          </div>
          <div className="sm:col-span-2">
            <ContactSelect
              required
              registration={register('contact')}
              error={e.contact?.message}
              current={deal ? { id: deal.contact, name: deal.contact_name } : null}
            />
          </div>
          <TextField
            label="Value (₹)"
            required
            inputMode="decimal"
            placeholder="250000"
            error={e.value?.message}
            {...register('value')}
          />
          <SelectField label="Stage" options={DEAL_STAGE_OPTIONS} {...register('stage')} />
          <TextField
            label="Expected close"
            type="date"
            error={e.expected_close_date?.message}
            {...register('expected_close_date')}
          />
          <TextField
            label="Win probability (%)"
            inputMode="numeric"
            placeholder="Stage default"
            hint="Leave blank to use the stage default."
            error={e.probability?.message}
            {...register('probability')}
          />
        </form>
        {deal?.closed_at && (
          <p className="mt-4 text-xs text-slate-500">Closed {formatDateTime(deal.closed_at)}</p>
        )}
      </Modal>
      <ConfirmDialog
        open={confirmDelete}
        title="Delete deal?"
        message={`"${deal?.title}" will be permanently deleted.`}
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}
