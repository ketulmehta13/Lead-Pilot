import { useCallback, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';
const STORAGE_KEY = 'leadpilot-theme';

function readInitialTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

/** Light/dark theme stored in localStorage and applied as a class on <html>. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Storage can be unavailable (private mode); the theme still applies for this visit.
    }
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === 'dark' ? 'light' : 'dark')), []);
  return { theme, toggle };
}
