import { defineConfig, devices } from '@playwright/test';

/**
 * E2E: boots the real Django backend (fresh seeded SQLite, offline AI) on :8010 and the Vite
 * app on :5180 (separate ports so your own dev servers on 8000/5173 can keep running).
 * Python: E2E_PYTHON (default "python"; locally e.g. "../backend/.venv/Scripts/python").
 */
const python = process.env.E2E_PYTHON ?? 'python';
const backendEnv = { DJANGO_SETTINGS_MODULE: 'config.settings.e2e', HF_HUB_OFFLINE: '1' };

export default defineConfig({
  testDir: './e2e',
  testIgnore: ['screenshots/**'],
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1, // one shared database
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://localhost:5180',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
  webServer: [
    {
      command: `${python} manage.py migrate --noinput && ${python} manage.py seed_demo --flush && ${python} manage.py runserver 8010 --noreload`,
      cwd: '../backend',
      env: backendEnv,
      url: 'http://localhost:8010/api/health/',
      timeout: 600_000,
      reuseExistingServer: false,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      command: 'npm run dev -- --port 5180 --strictPort',
      env: { API_PROXY_TARGET: 'http://localhost:8010' },
      url: 'http://localhost:5180',
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
