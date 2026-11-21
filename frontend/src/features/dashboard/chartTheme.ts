import { useSyncExternalStore } from 'react';

/**
 * Chart colours (single-series charts use categorical slot 1 from the reference palette).
 * Dark values are separately stepped for the dark surface, not an automatic flip.
 */
const LIGHT = {
  series: '#2a78d6',
  seriesFill: 'rgba(42, 120, 214, 0.12)',
  grid: '#e2e8f0', // one step off the white card surface
  axis: '#64748b', // secondary text
  surface: '#ffffff',
};
const DARK = {
  series: '#3987e5',
  seriesFill: 'rgba(57, 135, 229, 0.18)',
  grid: '#1e293b',
  axis: '#94a3b8',
  surface: '#0f172a',
};
export type ChartTheme = typeof LIGHT;

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  return () => observer.disconnect();
}

const isDark = () => document.documentElement.classList.contains('dark');

/** Re-renders charts when the theme toggle flips the `dark` class on <html>. */
export function useChartTheme(): ChartTheme {
  const dark = useSyncExternalStore(subscribe, isDark, () => false);
  return dark ? DARK : LIGHT;
}

const compactINR = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  notation: 'compact',
  maximumFractionDigits: 1,
});

/** Short rupee labels for axes: ₹12L, ₹1.2Cr. */
export function formatCompactINR(value: number): string {
  return compactINR.format(value);
}

/** "2026-11" -> "Nov 26" */
export function formatMonth(month: string): string {
  const [y, m] = month.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
}
