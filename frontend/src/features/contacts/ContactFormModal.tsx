import type { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { companiesApi, contactsApi } from '../../api/crm';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { contactSchema, parseTags } from '../../lib/schemas';
import type { Contact } from '../../types';

type FormValues = z.infer<typeof contactSchema>;
const FIELDS = ['first_name', 'last_name', 'email', 'phone', 'company', 'tags'] as const;
const empty: FormValues = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  company: '',
  tags: '',
};

/** Companies for the dropdown (the API caps pages at 100). */
// eslint-disable-next-line react-refresh/only-export-components
export function useCompanyOptions(enabled = true) {
  return useQuery({
    queryKey: [companiesApi.key, 'options'],
    queryFn: () => companiesApi.list({ page_size: 100, ordering: 'name' }),
    enabled,
    staleTime: 60_000,
  });
}

interface Props {
  open: boolean;
  contact?: Contact | null;
  onClose: () => void;
  onSaved?: (contact: Contact) => void;
}

export function ContactFormModal({ open, contact, onClose, onSaved }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const companies = useCompanyOptions(open);
  const { register, handleSubmit, reset, setError, formState } = useForm<FormValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: empty,
  });

  useEffect(() => {
    if (!open) return;
    reset(
      contact
        ? {
            first_name: contact.first_name,
            last_name: contact.last_name,
            email: contact.email,
            phone: contact.phone,
            company: contact.company ? String(contact.company) : '',
            tags: contact.tags.join(', '),
          }
        : empty,
    );
  }, [open, contact, reset]);

  const mutation = useMutation({
    mutationFn: (v: FormValues) => {
      const payload = {
        ...v,
        company: v.company ? Number(v.company) : null,
        tags: parseTags(v.tags),
      };
      return contact ? contactsApi.update(contact.id, payload) : contactsApi.create(payload);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: [contactsApi.key] });
      queryClient.invalidateQueries({ queryKey: [companiesApi.key] });
      toast.success(contact ? 'Contact updated' : `Added ${saved.full_name}`);
      onSaved?.(saved);
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  const companyOptions = [
    { value: '', label: 'No company' },
    ...(companies.data?.results ?? []).map((c) => ({ value: String(c.id), label: c.name })),
  ];
  // Keep the current company selectable even if it isn't in the first 100.
  if (contact?.company && !companyOptions.some((o) => o.value === String(contact.company))) {
    companyOptions.push({
      value: String(contact.company),
      label: contact.company_name ?? 'Current',
    });
  }
  const e = formState.errors;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={contact ? 'Edit contact' : 'New contact'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="contact-form" loading={mutation.isPending}>
            {contact ? 'Save changes' : 'Create contact'}
          </Button>
        </>
      }
    >
      <form
        id="contact-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-2"
      >
        <TextField
          label="First name"
          required
          error={e.first_name?.message}
          {...register('first_name')}
        />
        <TextField label="Last name" error={e.last_name?.message} {...register('last_name')} />
        <TextField
          label="Email"
          type="email"
          required
          error={e.email?.message}
          {...register('email')}
        />
        <TextField label="Phone" type="tel" error={e.phone?.message} {...register('phone')} />
        <div className="sm:col-span-2">
          <SelectField
            label="Company"
            options={companyOptions}
            error={e.company?.message}
            disabled={companies.isLoading}
            {...register('company')}
          />
        </div>
        <div className="sm:col-span-2">
          <TextField
            label="Tags"
            placeholder="vip, newsletter"
            hint="Separate tags with commas."
            error={e.tags?.message}
            {...register('tags')}
          />
        </div>
      </form>
    </Modal>
  );
}
