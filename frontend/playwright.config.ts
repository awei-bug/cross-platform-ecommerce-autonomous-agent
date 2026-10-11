import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],
  webServer: [
    {
      command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8100',
      cwd: '../backend',
      url: 'http://127.0.0.1:8100/health',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DATABASE_URL: 'sqlite+pysqlite:///../frontend/test-results/runtime/ops_workbench-e2e.db',
        DATABASE_AUTO_CREATE: 'true',
        CELERY_TASK_ALWAYS_EAGER: 'true',
        ASSET_STORAGE_BACKEND: 'local',
        ASSET_STORAGE_LOCAL_PATH: '../frontend/test-results/runtime/assets',
      },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174',
      url: 'http://127.0.0.1:5174/',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_API_PROXY_TARGET: 'http://127.0.0.1:8100',
      },
    },
  ],
})
