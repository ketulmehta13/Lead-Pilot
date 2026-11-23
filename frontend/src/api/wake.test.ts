import { AxiosError, AxiosHeaders } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getHealth } from './client';
import { isWakingError, resetWakeState, wakeServer } from './wake';

vi.mock('./client', () => ({ getHealth: vi.fn() }));
const health = vi.mocked(getHealth);

function httpError(status?: number): AxiosError {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError(
    'failed',
    status ? 'ERR_BAD_RESPONSE' : 'ERR_NETWORK',
    config,
    null,
    status ? { status, statusText: '', headers: {}, config, data: '' } : undefined,
  );
}

describe('server wake-up', () => {
  beforeEach(() => {
    resetWakeState();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    health.mockReset();
  });

  it('treats network errors and 502/503/504 as "still starting", not 401/500', () => {
    expect(isWakingError(httpError())).toBe(true);
    expect(isWakingError(httpError(502))).toBe(true);
    expect(isWakingError(httpError(503))).toBe(true);
    expect(isWakingError(httpError(401))).toBe(false);
    expect(isWakingError(httpError(500))).toBe(false);
    expect(isWakingError(new Error('x'))).toBe(false);
  });

  it('keeps pinging until the server answers, and shares one wake-up', async () => {
    health
      .mockRejectedValueOnce(httpError())
      .mockRejectedValueOnce(httpError(503))
      .mockResolvedValue({ status: 'ok', database: 'ok' });
    const first = wakeServer();
    const second = wakeServer();
    expect(second).toBe(first);
    await vi.advanceTimersByTimeAsync(10_000);
    await expect(first).resolves.toBe(true);
    expect(health).toHaveBeenCalledTimes(3);
    // Once ready, no more pings are needed.
    await expect(wakeServer()).resolves.toBe(true);
    expect(health).toHaveBeenCalledTimes(3);
  });

  it('gives up on a real server error instead of waiting', async () => {
    health.mockRejectedValue(httpError(500));
    const result = wakeServer();
    await vi.advanceTimersByTimeAsync(1_000);
    await expect(result).resolves.toBe(false);
    expect(health).toHaveBeenCalledTimes(1);
  });
});
