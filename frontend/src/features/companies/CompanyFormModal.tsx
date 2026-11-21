import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { companiesApi } from '../../api/crm';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { SelectField, TextField } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { applyServerErrors } from '../../lib/forms';
import { INDUSTRY_OPTIONS, SIZE_OPTIONS } from '../../lib/options';
import type { Company, CompanySize, Industry } from '../../types';

const companySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(200),
  industry: z.string().min(1),
  size: z.string(),
  website: z.union([z.literal(''), z.url('Enter a full URL, e.g. https://acme.com')]),
  city: z.string().trim().max(100),
});
type FormValues = z.infer<typeof companySchema>;
const FIELDS = ['name', 'industry', 'size', 'website', 'city'] as const;

const empty: FormValues = { name: '', industry: 'other', size: '', website: '', city: '' };

interface Props {
  open: boolean;
  company?: Company | null;
  onClose: () => void;
}

export function CompanyFormModal({ open, company, onClose }: Props) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const form = useForm<FormValues>({ resolver: zodResolver(companySchema), defaultValues: empty });
  const { register, handleSubmit, reset, setError, formState } = form;

  useEffect(() => {
    if (open) reset(company ? { ...empty, ...pick(company) } : empty);
  }, [open, company, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        ...values,
        industry: values.industry as Industry,
        size: values.size as CompanySize,
      };
      return company ? companiesApi.update(company.id, payload) : companiesApi.create(payload);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: [companiesApi.key] });
      toast.success(company ? 'Company updated' : `Created ${saved.name}`);
      onClose();
    },
    onError: (err) => toast.error(applyServerErrors(err, setError, FIELDS)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={company ? 'Edit company' : 'New company'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="company-form" loading={mutation.isPending}>
            {company ? 'Save changes' : 'Create company'}
          </Button>
        </>
      }
    >
      <form
        id="company-form"
        noValidate
        onSubmit={handleSubmit((v) => mutation.mutate(v))}
        className="grid gap-4 sm:grid-cols-2"
      >
        <div className="sm:col-span-2">
          <TextField
            label="Name"
            required
            error={formState.errors.name?.message}
            {...register('name')}
          />
        </div>
        <SelectField label="Industry" options={INDUSTRY_OPTIONS} {...register('industry')} />
        <SelectField
          label="Size"
          options={[{ value: '', label: 'Unknown' }, ...SIZE_OPTIONS]}
          {...register('size')}
        />
        <TextField
          label="Website"
          type="url"
          placeholder="https://"
          error={formState.errors.website?.message}
          {...register('website')}
        />
        <TextField label="City" error={formState.errors.city?.message} {...register('city')} />
      </form>
    </Modal>
  );
}

function pick(c: Company): FormValues {
  return { name: c.name, industry: c.industry, size: c.size, website: c.website, city: c.city };
}
