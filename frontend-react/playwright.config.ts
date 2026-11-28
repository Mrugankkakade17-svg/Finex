import { defineConfig, devices } from '@playwright/test';

const API_PORT = process.env.FINEX_E2E_API_PORT || '8010';
const APP_PORT = process.env.FINEX_E2E_APP_PORT || '3000';
const API_BASE_URL = `http://127.0.0.1:${API_PORT}`;
const APP_BASE_URL = `http://127.0.0.1:${APP_PORT}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : [['list']],
  use: {
    baseURL: APP_BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'node e2e/fixture-server.mjs',
      url: `${API_BASE_URL}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        ...process.env,
        FINEX_E2E_API_PORT: API_PORT,
        FINEX_E2E_ALLOWED_ORIGIN: APP_BASE_URL,
      },
    },
    {
      command: 'npm start',
      url: `${APP_BASE_URL}/login`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        CI: process.env.CI || 'true',
        BROWSER: 'none',
        HOST: '127.0.0.1',
        PORT: APP_PORT,
        REACT_APP_FINEX_API_BASE_URL: API_BASE_URL,
        REACT_APP_MARKET_MODE: process.env.REACT_APP_MARKET_MODE || 'fixture',
        REACT_APP_ENABLE_REAL_AUTH: 'false',
      },
    },
  ],
});
