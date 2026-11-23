import { isAxiosError } from 'axios';
import { useSyncExternalStore } from 'react';
import { getHealth } from './client';

/**
 * Free hosting puts the API to sleep after ~15 idle minutes; the first request then takes
 * 30-60 s while it starts (meanwhile the host may answer 502/503 or drop the connection).
 * The app starts waking it as soon as the page opens, and the login retries until it's up.
 */
export type WakeState = 'checking' | 'waking' | 'ready' | 'down';

const WAKE_TIMEOUT_MS = 90_000;
const SLOW_AFTER_MS = 2_500; // answered slower than this: tell the user it's starting
const RETRY_EVERY_MS = 3_000;

let state: WakeState = 'checking';
let pending: Promise<boolean> | null = null;
const listeners = new Set<() => void>();

function set(next: WakeState) {
  if (state === next) return;
  state = next;
  listeners.forEach((l) => l());
}

/** True when an error looks like "the server is still starting", not a real failure. */
export function isWakingError(err: unknown): boolean {
  if (!isAxiosError(err)) return false;
  if (!err.response) return true; // network error / timeout / CORS-less 5xx page
  return [502, 503, 504].includes(err.response.status);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Ping /api/health/ until it answers (shared by every caller). Resolves true when ready. */
export function wakeServer(): Promise<boolean> {
  if (state === 'ready') return Promise.resolve(true);
  if (pending) return pending;
  pending = (async () => {
    const started = Date.now();
    const slow = setTimeout(() => state === 'checking' && set('waking'), SLOW_AFTER_MS);
    try {
      while (Date.now() - started < WAKE_TIMEOUT_MS) {
        try {
          const health = await getHealth();
          if (health.status === 'ok') {
            set('ready');
            return true;
          }
        } catch (err) {
          if (!isWakingError(err)) break; // a real error (e.g. 500): stop and report
          set('waking');
        }
        await sleep(RETRY_EVERY_MS);
      }
      set('down');
      return false;
    } finally {
      clearTimeout(slow);
      pending = null;
    }
  })();
  return pending;
}

export function useWakeState(): WakeState {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
  );
}

/** Test helper. */
export function resetWakeState(): void {
  state = 'checking';
  pending = null;
}
