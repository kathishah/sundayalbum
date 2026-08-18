import { defineConfig, devices } from '@playwright/test'
import path from 'path'

/**
 * Playwright E2E configuration.
 *
 * Targets dev.sundayalbum.com by default. Set STAGE=prod to run against
 * app.sundayalbum.com without conflating auth/job state between environments.
 *
 * Auth and completed-job files are scoped per stage:
 *   .auth/session-dev.json  /  .auth/session-prod.json
 *   .auth/completed-job-dev.json  /  .auth/completed-job-prod.json
 *
 * Required env vars:
 *   TEST_USER_EMAIL        e.g. chintan@reachto.me
 *   DEV_FRONTEND_URL       e.g. https://dev.sundayalbum.com (or set STAGE=prod)
 *   DEV_API_URL            e.g. https://nodcooz758.execute-api.us-west-2.amazonaws.com
 *   SESSIONS_TABLE         DynamoDB table (default: sa-sessions-dev; prod: sa-sessions)
 *   AWS_ACCESS_KEY_ID      IAM key with read access to the sessions DynamoDB table
 *   AWS_SECRET_ACCESS_KEY
 *   STAGE                  dev (default) | prod — scopes auth/job state files
 */

const STAGE = process.env.STAGE ?? 'dev'

const BASE_URL = process.env.DEV_FRONTEND_URL ?? 'https://dev.sundayalbum.com'

export const AUTH_FILE = path.join(__dirname, `.auth/session-${STAGE}.json`)
export const COMPLETED_JOB_FILE = path.join(__dirname, `.auth/completed-job-${STAGE}.json`)

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,       // tests may share server state; run serially
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [['github'], ['html', { open: 'never' }]]
    : [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  globalSetup: './tests/e2e/global-setup.ts',

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: AUTH_FILE,
      },
    },
  ],
})
