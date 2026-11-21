import { createHmac } from 'node:crypto';
import { expect, type APIRequestContext, type Page } from '@playwright/test';

export const API = 'http://localhost:8010/api';
export const PASSWORD = 'LeadPilot@123';
export const WEBHOOK_SECRET = 'e2e_webhook_secret';

export async function login(page: Page, username = 'priya') {
  await page.goto('/login');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
}

/** A JWT for direct API calls from tests (setup / assertions). */
export async function apiToken(request: APIRequestContext, username = 'priya'): Promise<string> {
  const res = await request.post(`${API}/auth/login/`, { data: { username, password: PASSWORD } });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).access;
}

export async function apiGet<T>(
  request: APIRequestContext,
  token: string,
  path: string,
): Promise<T> {
  const res = await request.get(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  expect(res.ok(), `${path} -> ${res.status()}`).toBeTruthy();
  return res.json();
}

/** Send a webhook signed exactly like Razorpay does (HMAC-SHA256 of the raw body). */
export async function sendWebhook(request: APIRequestContext, event: unknown, eventId: string) {
  const body = JSON.stringify(event);
  const signature = createHmac('sha256', WEBHOOK_SECRET).update(body).digest('hex');
  return request.post(`${API}/billing/webhook/`, {
    data: body,
    headers: {
      'Content-Type': 'application/json',
      'X-Razorpay-Signature': signature,
      'X-Razorpay-Event-Id': eventId,
    },
  });
}
