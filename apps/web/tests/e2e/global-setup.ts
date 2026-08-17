/**
 * Playwright global setup.
 *
 * Runs once before all tests and does two things:
 *
 * 1. Auth — obtains a session token for TEST_USER_EMAIL via send-code → DynamoDB
 *    code read → verify.  Reuses the saved token if it is still valid to avoid
 *    hitting the auth rate-limiter when re-running within the same hour.
 *
 * 2. Seed job — uploads tests/e2e/fixtures/test_photo.jpg to the real pipeline
 *    and polls until status === 'complete' (up to PIPELINE_TIMEOUT_MS).
 *    The completed job_id is saved to .auth/completed-job-{stage}.json so tests
 *    that require a finished job (T38, T43–T45) can read it without waiting again.
 *    If the saved job is already complete it is reused across runs.
 *
 * Required env vars:
 *   TEST_USER_EMAIL        e.g. chintan@reachto.me
 *   DEV_FRONTEND_URL       e.g. https://dev.sundayalbum.com
 *   DEV_API_URL            e.g. https://nodcooz758.execute-api.us-west-2.amazonaws.com
 *   AWS_ACCESS_KEY_ID      IAM read on sa-sessions(-dev) DynamoDB table
 *   AWS_SECRET_ACCESS_KEY
 *   AWS_DEFAULT_REGION     defaults to us-west-2
 *   SESSIONS_TABLE         DynamoDB table name (default: sa-sessions-dev)
 */

import fs from 'fs'
import path from 'path'
import { chromium } from '@playwright/test'
import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb'
import { AUTH_FILE, COMPLETED_JOB_FILE } from '../../playwright.config'

const API_URL    = process.env.DEV_API_URL ?? ''
const FRONTEND   = process.env.DEV_FRONTEND_URL ?? 'https://dev.sundayalbum.com'
const EMAIL      = process.env.TEST_USER_EMAIL ?? ''
const REGION     = process.env.AWS_DEFAULT_REGION ?? 'us-west-2'
const SESSIONS_TABLE = process.env.SESSIONS_TABLE ?? 'sa-sessions-dev'

const FIXTURE_IMAGE = path.join(__dirname, 'fixtures', 'test_photo.jpg')

/** Max time to wait for the pipeline to finish (ms). */
const PIPELINE_TIMEOUT_MS = 3 * 60 * 1000   // 3 minutes
const POLL_INTERVAL_MS    = 5_000

if (!API_URL)  throw new Error('DEV_API_URL env var is required')
if (!EMAIL)    throw new Error('TEST_USER_EMAIL env var is required')

// ── Session helpers ────────────────────────────────────────────────────────────

function readSavedToken(): string | null {
  try {
    const state = JSON.parse(fs.readFileSync(AUTH_FILE, 'utf-8'))
    for (const origin of state.origins ?? []) {
      for (const entry of origin.localStorage ?? []) {
        if (entry.name === 'sa_token') return entry.value as string
      }
    }
  } catch { /* missing or malformed */ }
  return null
}

async function isTokenValid(token: string): Promise<boolean> {
  try {
    const r = await fetch(`${API_URL}/jobs`, { headers: { Authorization: `Bearer ${token}` } })
    return r.ok
  } catch { return false }
}

async function readCodeFromDynamo(): Promise<string> {
  const ddb = new DynamoDBClient({ region: REGION })
  for (let i = 0; i < 10; i++) {
    const resp = await ddb.send(new GetItemCommand({
      TableName: SESSIONS_TABLE,
      Key: { email: { S: EMAIL } },
    }))
    const code      = resp.Item?.code?.S
    const expiresAt = resp.Item?.code_expires_at?.N
    if (code && expiresAt && parseInt(expiresAt, 10) > Math.floor(Date.now() / 1000)) {
      return code
    }
    await new Promise((r) => setTimeout(r, 1000))
  }
  throw new Error(`Verification code not found in DynamoDB for ${EMAIL} after 10 s`)
}

async function authenticate(): Promise<string> {
  // Try to reuse saved session
  const saved = readSavedToken()
  if (saved && await isTokenValid(saved)) {
    console.log('[setup] Reusing existing session token')
    return saved
  }
  console.log('[setup] Saved session expired — re-authenticating')

  const sendResp = await fetch(`${API_URL}/auth/send-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL }),
  })
  if (!sendResp.ok) {
    throw new Error(`send-code failed (${sendResp.status}): ${await sendResp.text()}`)
  }

  const code = await readCodeFromDynamo()
  console.log(`[setup] Got verification code for ${EMAIL}`)

  const verifyResp = await fetch(`${API_URL}/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, code }),
  })
  if (!verifyResp.ok) {
    throw new Error(`verify failed (${verifyResp.status}): ${await verifyResp.text()}`)
  }
  const { session_token, user_hash } = await verifyResp.json()
  if (!session_token) throw new Error('verify returned no session_token')

  // Persist to storageState so tests start authenticated
  const browser = await chromium.launch()
  const ctx     = await browser.newContext()
  const page    = await ctx.newPage()
  await page.goto(FRONTEND)
  await page.evaluate(
    ({ t, h }: { t: string; h: string }) => {
      localStorage.setItem('sa_token', t)
      if (h) localStorage.setItem('sa_user_hash', h)
    },
    { t: session_token, h: user_hash ?? '' },
  )
  await ctx.storageState({ path: AUTH_FILE })
  await browser.close()
  console.log(`[setup] Session saved to ${AUTH_FILE}`)

  return session_token
}

// ── Pipeline helpers ───────────────────────────────────────────────────────────

function authed(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

async function getJobStatus(token: string, jobId: string): Promise<string> {
  const r = await fetch(`${API_URL}/jobs/${jobId}`, { headers: authed(token) })
  if (!r.ok) throw new Error(`getJob ${jobId} failed: ${r.status}`)
  const j = await r.json()
  return j.status as string
}

/** Read saved completed job_id from the stage-scoped file, or null. */
function readSavedJobId(): string | null {
  try {
    const d = JSON.parse(fs.readFileSync(COMPLETED_JOB_FILE, 'utf-8'))
    return typeof d.job_id === 'string' ? d.job_id : null
  } catch { return null }
}

/** Persist a completed job_id for reuse across runs. */
function saveJobId(jobId: string) {
  fs.mkdirSync(path.dirname(COMPLETED_JOB_FILE), { recursive: true })
  fs.writeFileSync(COMPLETED_JOB_FILE, JSON.stringify({ job_id: jobId }))
}

/**
 * Upload fixtures/test_photo.jpg, start the pipeline, and poll until complete.
 * Returns the completed job_id.
 */
async function uploadAndProcess(token: string): Promise<string> {
  const filename = path.basename(FIXTURE_IMAGE)
  const fileBytes = fs.readFileSync(FIXTURE_IMAGE)
  const fileSize  = fileBytes.length

  // 1. Create job → get upload_url + job_id
  console.log(`[setup] Creating job for ${filename} (${Math.round(fileSize / 1024)} KB)`)
  const createResp = await fetch(`${API_URL}/jobs`, {
    method: 'POST',
    headers: { ...authed(token), 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, file_size: fileSize }),
  })
  if (!createResp.ok) throw new Error(`createJob failed: ${createResp.status} ${await createResp.text()}`)
  const { job_id, upload_url } = await createResp.json()
  console.log(`[setup] Job created: ${job_id}`)

  // 2. Upload to S3 pre-signed URL
  const uploadResp = await fetch(upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': 'image/jpeg' },
    body: fileBytes,
  })
  if (!uploadResp.ok) throw new Error(`S3 upload failed: ${uploadResp.status}`)
  console.log('[setup] File uploaded to S3')

  // 3. Start the pipeline
  const startResp = await fetch(`${API_URL}/jobs/${job_id}/start`, {
    method: 'POST',
    headers: authed(token),
  })
  if (!startResp.ok) throw new Error(`startJob failed: ${startResp.status} ${await startResp.text()}`)
  console.log('[setup] Pipeline started — polling for completion...')

  // 4. Poll until complete or timeout
  const deadline = Date.now() + PIPELINE_TIMEOUT_MS
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS))
    const status = await getJobStatus(token, job_id)
    console.log(`[setup]   job ${job_id} status: ${status}`)
    if (status === 'complete') {
      console.log(`[setup] Pipeline complete for job ${job_id}`)
      return job_id
    }
    if (status === 'failed') {
      throw new Error(`Pipeline failed for job ${job_id}`)
    }
  }
  throw new Error(`Pipeline timed out after ${PIPELINE_TIMEOUT_MS / 1000}s for job ${job_id}`)
}

// ── Main ───────────────────────────────────────────────────────────────────────

export default async function globalSetup() {
  // ── Step 1: authenticate ──────────────────────────────────────────────────
  const token = await authenticate()

  // ── Step 2: ensure a completed job exists for T38/T43–T45 ─────────────────
  const savedJobId = readSavedJobId()
  if (savedJobId) {
    // Verify it's still complete (wasn't deleted)
    try {
      const status = await getJobStatus(token, savedJobId)
      if (status === 'complete') {
        console.log(`[setup] Reusing completed job ${savedJobId}`)
        return
      }
      console.log(`[setup] Saved job ${savedJobId} is ${status} — re-uploading`)
    } catch {
      console.log(`[setup] Saved job ${savedJobId} not found — re-uploading`)
    }
  }

  const completedJobId = await uploadAndProcess(token)
  saveJobId(completedJobId)
  console.log(`[setup] Saved completed job_id to ${COMPLETED_JOB_FILE}`)
}
