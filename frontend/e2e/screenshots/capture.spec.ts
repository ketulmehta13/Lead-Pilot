import { expect, test } from '@playwright/test';
import { login } from '../helpers';

/** Captures README screenshots (light theme, 1440x900) into ../docs/screenshots. */
const OUT = '../docs/screenshots';

test('capture README screenshots', async ({ page }) => {
  test.setTimeout(240_000);
  await login(page, 'admin');
  const shot = async (name: string) => {
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600); // charts finish laying out
    await page.screenshot({ path: `${OUT}/${name}.png` });
  };

  await expect(page.getByText('Open pipeline')).toBeVisible();
  await shot('dashboard');

  await page.goto('/pipeline');
  await expect(page.getByRole('region', { name: 'Won column' })).toBeVisible();
  await shot('pipeline');

  await page.goto('/leads');
  await expect(page.getByRole('button', { name: 'Why?' }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Why?' }).first().click();
  await shot('leads-why');

  await page.goto('/ml-insights');
  await expect(page.getByText('Confusion matrix (held-out test set)')).toBeVisible();
  await shot('ml-insights');

  await page.goto('/tickets');
  await expect(page.getByRole('heading', { name: 'Tickets' })).toBeVisible();
  await shot('tickets');

  await page.goto('/ask');
  await page.getByLabel('Your question').fill('Which contacts asked about WhatsApp integration?');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByRole('link', { name: /\[1\]/ }).first()).toBeVisible();
  await shot('ask-leadpilot');

  await page.goto('/agent');
  await page.getByRole('button', { name: /find hot leads not contacted in 7 days/i }).click();
  await page.getByRole('button', { name: 'Run agent' }).click();
  await expect(page.getByText('Needs your approval').first()).toBeVisible();
  await shot('agent-approval');

  await page.goto('/invoices');
  await page.getByRole('row').nth(1).click();
  await expect(page.getByText('Payment history')).toBeVisible();
  await shot('invoice');

  // Dark mode
  await page.goto('/dashboard');
  await page.getByRole('button', { name: /switch to dark mode/i }).click();
  await shot('dashboard-dark');
});
