import { beforeEach, describe, expect, it, vi } from 'vitest';

async function freshTokens() {
  vi.resetModules();
  return (await import('./tokens')).tokens;
}

describe('token storage', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('keeps a default sign-in for this browser session only', async () => {
    const tokens = await freshTokens();
    tokens.set('a1', 'r1', false);
    expect(sessionStorage.getItem('leadpilot-access')).toBe('a1');
    expect(localStorage.getItem('leadpilot-access')).toBeNull();
    expect(tokens.remembered).toBe(false);
    // A token refresh stays in the same place.
    tokens.set('a2', 'r2');
    expect(sessionStorage.getItem('leadpilot-access')).toBe('a2');
    expect(tokens.access).toBe('a2');
  });

  it('"Keep me signed in" survives a browser restart', async () => {
    let tokens = await freshTokens();
    tokens.set('a1', 'r1', true);
    sessionStorage.clear(); // the browser was closed
    tokens = await freshTokens();
    expect(tokens.access).toBe('a1');
    expect(tokens.remembered).toBe(true);
    tokens.set('a2'); // refresh keeps it remembered
    expect(localStorage.getItem('leadpilot-access')).toBe('a2');
  });

  it('signs out sessions saved before "Keep me signed in" existed', async () => {
    localStorage.setItem('leadpilot-access', 'old');
    localStorage.setItem('leadpilot-refresh', 'old');
    const tokens = await freshTokens();
    expect(tokens.access).toBeNull();
    expect(localStorage.getItem('leadpilot-refresh')).toBeNull();
  });

  it('clear() signs out everywhere', async () => {
    const tokens = await freshTokens();
    tokens.set('a', 'r', true);
    tokens.clear();
    expect(tokens.access).toBeNull();
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });
});
