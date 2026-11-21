import base from './playwright.config';
import { defineConfig } from '@playwright/test';

/** `npm run screenshots`: captures README screenshots into ../docs/screenshots. */
export default defineConfig({
  ...base,
  testDir: './e2e/screenshots',
  retries: 0,
  reporter: 'list',
});
