import { useEffect, useState } from 'react';

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

/**
 * Search + filters + ordering + page for a list page.
 * Changing search/filters/ordering jumps back to page 1.
 */
export function useListParams<F extends Record<string, string>>(
  initialFilters: F,
  initialOrdering = '',
) {
  const [search, setSearchRaw] = useState('');
  const [filters, setFiltersRaw] = useState<F>(initialFilters);
  const [ordering, setOrderingRaw] = useState(initialOrdering);
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  return {
    search,
    setSearch: (value: string) => {
      setSearchRaw(value);
      setPage(1);
    },
    filters,
    setFilter: (key: keyof F, value: string) => {
      setFiltersRaw((f) => ({ ...f, [key]: value }));
      setPage(1);
    },
    ordering,
    setOrdering: (value: string) => {
      setOrderingRaw(value);
      setPage(1);
    },
    page,
    setPage,
    /** Params to send to the API (debounced search). */
    params: { search: debouncedSearch, ordering, page, ...filters },
  };
}
