import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import type { UseFormRegisterReturn } from 'react-hook-form';
import { contactsApi } from '../api/crm';
import { useDebounced } from '../hooks/useListParams';
import { SelectField, controlClass } from './ui/Field';

interface Props {
  registration: UseFormRegisterReturn;
  error?: string;
  required?: boolean;
  /** Keeps the currently linked contact selectable even if it isn't in the search results. */
  current?: { id: number; name: string } | null;
  emptyLabel?: string;
}

/** Contact dropdown with a search box (server-side search, 25 results). */
export function ContactSelect({
  registration,
  error,
  required,
  current,
  emptyLabel = 'Select a contact',
}: Props) {
  const [search, setSearch] = useState('');
  const debounced = useDebounced(search);
  const contacts = useQuery({
    queryKey: [contactsApi.key, 'picker', debounced],
    queryFn: () => contactsApi.list({ search: debounced, page_size: 25, ordering: 'first_name' }),
    placeholderData: keepPreviousData,
  });

  const options = (contacts.data?.results ?? []).map((c) => ({
    value: String(c.id),
    label: `${c.full_name} — ${c.company_name ?? c.email}`,
  }));
  if (current && !options.some((o) => o.value === String(current.id))) {
    options.unshift({ value: String(current.id), label: current.name });
  }

  return (
    <div className="space-y-2">
      <input
        type="search"
        aria-label="Search contacts"
        placeholder="Search contacts by name, email or company…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className={controlClass}
      />
      <SelectField
        label="Contact"
        required={required}
        error={error}
        options={[{ value: '', label: contacts.isLoading ? 'Loading…' : emptyLabel }, ...options]}
        {...registration}
      />
    </div>
  );
}
