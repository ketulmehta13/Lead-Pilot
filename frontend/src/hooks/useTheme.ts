import { useCallback, useSyncExternalStore } from 'react';

export type Theme = 'light' | 'dark';
const STORAGE_KEY = 'leadpilot-theme';

// One shared theme for the whole app (top-bar toggle and Settings stay in sync).
const listeners = new Set<() => void>();

function current(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Apply a theme: class on <html>, remembered in localStorage when available. */
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark');
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage can be unavailable (private mode); the theme still applies for this visit.
  }
  listeners.forEach((l) => l());
}

/** Light/dark theme shared across components. */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, current, () => 'light' as Theme);
  const setTheme = useCallback((t: Theme) => applyTheme(t), []);
  const toggle = useCallback(() => applyTheme(current() === 'dark' ? 'light' : 'dark'), []);
  return { theme, setTheme, toggle };
}
