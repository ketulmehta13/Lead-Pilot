import { expect, test } from '@playwright/test';
import { apiGet, apiToken, login, sendWebhook } from './helpers';

test.describe('LeadPilot end-to-end', () => {
  test('login: wrong password is rejected, right one opens the dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Username').fill('priya');
    await page.getByLabel('Password').fill('not-the-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toHaveText('Wrong username or password.');
    await login(page);
    await expect(page.getByText('Open pipeline')).toBeVisible();
  });

  test('create a lead and its AI score appears', async ({ page }) => {
    await login(page);
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: 'Leads' })
      .click();
    await page.getByRole('button', { name: 'New lead' }).click();
    const dialog = page.getByRole('dialog', { name: 'New lead' });
    await dialog.getByRole('combobox', { name: /^Contact/ }).selectOption({ index: 1 });
    await dialog.getByLabel('Source').selectOption('referral');
    await dialog.getByLabel('Budget (₹)').fill('450000');
    await dialog.getByLabel('Notes').fill('E2E lead: wants a demo next week');
    await dialog.getByRole('button', { name: 'Create lead' }).click();
    await expect(page.getByText('Lead created')).toBeVisible();

    // Newest first: the lead we just created is scored by the model (Celery runs inline).
    await page.getByLabel('Search').fill('E2E lead');
    const row = page
      .getByRole('row')
      .filter({ hasText: /Referral/ })
      .first();
    await expect(row.getByText(/^(Hot|Warm|Cold)$/)).toBeVisible();
    await row.getByRole('button', { name: 'Why?' }).click();
    await expect(page.getByRole('dialog', { name: /why this lead scores/i })).toContainText(
      'Top factors behind this score',
    );
  });

  test('drag a deal to Won, invoice it, and a signed webhook marks it paid', async ({
    page,
    request,
  }) => {
    await login(page);
    await page.goto('/pipeline');
    const newColumn = page.getByRole('region', { name: 'New column' });
    const wonColumn = page.getByRole('region', { name: 'Won column' });
    const card = newColumn
      .locator('li')
      .filter({ has: page.getByRole('button', { name: /^Drag / }) })
      .first();
    const title = (await card.getByRole('button').first().textContent())!.trim();

    const handle = card.getByRole('button', { name: /^Drag / });
    const from = (await handle.boundingBox())!;
    const to = (await wonColumn.boundingBox())!;
    await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
    await page.mouse.down();
    await page.mouse.move(from.x + 40, from.y + 20, { steps: 5 });
    await page.mouse.move(to.x + to.width / 2, to.y + 90, { steps: 25 });
    await page.mouse.up();
    await expect(page.getByText(new RegExp(`moved to Won`))).toBeVisible();

    // Persists after a refresh.
    await page.reload();
    await expect(
      page
        .getByRole('region', { name: 'Won column' })
        .getByRole('button', { name: title, exact: true }),
    ).toBeVisible();

    // Invoice it from the deal modal.
    await page
      .getByRole('region', { name: 'Won column' })
      .getByRole('button', { name: title, exact: true })
      .click();
    await page.getByRole('button', { name: 'Create invoice' }).click();
    const builder = page.getByRole('dialog', { name: 'New invoice' });
    await expect(builder.getByText('GST 18%')).toBeVisible();
    await builder.getByRole('button', { name: 'Create invoice' }).click();
    await expect(page.getByRole('heading', { level: 1, name: /^LP-\d{4}-\d{5}$/ })).toBeVisible();
    const invoiceId = Number(page.url().split('/').pop());

    // Razorpay confirms by webhook (signed like Razorpay does): the invoice turns Paid.
    const token = await apiToken(request);
    const invoice = await apiGet<{ total: string }>(
      request,
      token,
      `/billing/invoices/${invoiceId}/`,
    );
    const res = await sendWebhook(
      request,
      {
        event: 'payment.captured',
        payload: {
          payment: {
            entity: {
              id: `pay_e2e_${invoiceId}`,
              amount: Math.round(Number(invoice.total) * 100),
              method: 'card',
              status: 'captured',
              notes: { invoice_id: String(invoiceId) },
            },
          },
        },
      },
      `evt_e2e_${invoiceId}`,
    );
    expect(res.status()).toBe(200);
    await page.reload();
    await expect(page.getByText('Paid', { exact: true })).toBeVisible();
    await expect(page.getByText(`pay_e2e_${invoiceId}`)).toBeVisible();
  });

  test('agent pauses for approval; approve one, reject the rest', async ({ page }) => {
    await login(page);
    await page.goto('/agent');
    await page.getByRole('button', { name: /find hot leads not contacted in 7 days/i }).click();
    await page.getByRole('button', { name: 'Run agent' }).click();
    await expect(page.getByText('Needs your approval').first()).toBeVisible();
    const steps = page.getByRole('list', { name: 'Agent steps' });
    await expect(steps.getByText('Search leads')).toBeVisible();

    const approve = page.getByRole('button', { name: /^approve$/i });
    const reject = page.getByRole('button', { name: /^reject$/i });
    await approve.first().click();
    // Reject whatever is still pending.
    while ((await reject.count()) > 0) {
      await reject.first().click();
      await page.waitForTimeout(300);
    }
    await expect(page.getByText('Summary')).toBeVisible();
    await expect(steps.getByText('rejected by you').first()).toBeVisible();
    await expect(steps.getByText('approved')).toBeVisible();
  });

  test('Ask LeadPilot answers with citations to the source record', async ({ page, request }) => {
    const token = await apiToken(request);
    const now = new Date();
    const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const after = lastMonth.toISOString();
    const before = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    const acts = await apiGet<{ results: { contact: number }[] }>(
      request,
      token,
      `/crm/activities/?occurred_after=${after}&occurred_before=${before}&page_size=1`,
    );
    const contact = await apiGet<{ company_name: string | null; full_name: string }>(
      request,
      token,
      `/crm/contacts/${acts.results[0].contact}/`,
    );
    const who = contact.company_name ?? contact.full_name;

    await login(page);
    await page.goto('/ask');
    await page.getByLabel('Your question').fill(`What did we discuss with ${who} last month?`);
    await page.getByRole('button', { name: 'Send' }).click();
    const chip = page.getByRole('link', { name: /\[1\]/ }).first();
    await expect(chip).toBeVisible();
    await chip.click();
    await expect(page).toHaveURL(/\/contacts\/\d+|\/tickets\?ticket=\d+/);
  });
});
