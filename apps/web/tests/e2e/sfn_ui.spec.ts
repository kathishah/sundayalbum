/**
 * Layer 3 E2E tests: SFN skip-routing UI indicators (manually triggered, not CI).
 *
 * These tests verify that the library progress wheel and job detail step tree
 * correctly reflect the SFN execution state — segment count, pulsing dots, and
 * row availability — after a reprocess with `from_step`.
 *
 * They are NOT wired into CI — run manually after deploying to dev:
 *
 *   cd web
 *   STAGE=dev TEST_USER_EMAIL=... DEV_FRONTEND_URL=https://dev.sundayalbum.com \
 *     DEV_API_URL=https://nodcooz758.execute-api.us-west-2.amazonaws.com \
 *     SESSIONS_TABLE=sa-sessions-dev npx playwright test sfn_ui.spec.ts
 *
 * All tests skip if session-dev.json or completed-job-dev.json is absent.
 *
 * T-sfn-ui-01 through T-sfn-ui-04 run serially and share a single reprocess
 * execution (from page_detect) triggered in beforeAll. T-sfn-ui-05 is
 * independent: it uploads the 2-photo fixture and triggers a single-photo
 * reprocess via the UI.
 *
 * Test IDs:
 *   T-sfn-ui-01  Mid-reprocess: donut reflects active step; active step row has animate-ping
 *   T-sfn-ui-02  Mid-reprocess: Load row is enabled (debug_url preserved from prior run)
 *   T-sfn-ui-03  Mid-reprocess: Load row does NOT have animate-ping (was a Pass state)
 *   T-sfn-ui-04  Post-reprocess: donut gone / no animate-ping; all job-level rows enabled
 *   T-sfn-ui-05  Single-photo UI reprocess: only targeted photo's rows show animate-ping
 */

import fs from 'fs'
import path from 'path'
import { test, expect, type Page } from '@playwright/test'
import { COMPLETED_JOB_FILE, AUTH_FILE } from '../../playwright.config'

// 2-photo fixture used in T-sfn-ui-05
const FIXTURE_2UP = path.join(__dirname, 'fixtures', 'test_photo_2up.jpg')

// ── Config ────────────────────────────────────────────────────────────────────

const API_URL = process.env.DEV_API_URL ?? 'https://nodcooz758.execute-api.us-west-2.amazonaws.com'

const POLL_INTERVAL_MS  = 5_000
const REPROCESS_TIMEOUT = 4 * 60 * 1000   // 4 min
const UPLOAD_TIMEOUT    = 10 * 60 * 1000  // 10 min (upload + full pipeline)

// ── Helpers ───────────────────────────────────────────────────────────────────

function readToken(): string | null {
  try {
    const state = JSON.parse(fs.readFileSync(AUTH_FILE, 'utf-8'))
    for (const origin of state.origins ?? []) {
      for (const entry of origin.localStorage ?? []) {
        if (entry.name === 'sa_token') return entry.value as string
      }
    }
  } catch { /* missing */ }
  return null
}

function readCompletedJobId(): string | null {
  try {
    const d = JSON.parse(fs.readFileSync(COMPLETED_JOB_FILE, 'utf-8'))
    return typeof d.job_id === 'string' ? d.job_id : null
  } catch { return null }
}

function authed(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
}

async function getJobStatus(token: string, jobId: string): Promise<{ status: string }> {
  const r = await fetch(`${API_URL}/jobs/${jobId}`, { headers: authed(token) })
  if (!r.ok) throw new Error(`getJob ${jobId} failed: ${r.status}`)
  return r.json()
}

async function waitForIdle(token: string, jobId: string, timeoutMs = REPROCESS_TIMEOUT): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const { status } = await getJobStatus(token, jobId)
    if (status === 'complete' || status === 'failed') return
    await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS))
  }
  throw new Error(`Job ${jobId} did not reach idle state within ${timeoutMs / 1000}s`)
}

async function waitForComplete(token: string, jobId: string, timeoutMs = REPROCESS_TIMEOUT): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const { status } = await getJobStatus(token, jobId)
    if (status === 'complete') return
    if (status === 'failed') throw new Error(`Job ${jobId} failed during reprocess`)
    await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS))
  }
  throw new Error(`Job ${jobId} did not complete within ${timeoutMs / 1000}s`)
}

/**
 * Upload the given fixture, start the pipeline, and poll until complete.
 * Returns the completed job_id.
 */
async function uploadAndProcess(token: string, fixturePath: string): Promise<string> {
  const filename  = path.basename(fixturePath)
  const fileBytes = fs.readFileSync(fixturePath)

  const createResp = await fetch(`${API_URL}/jobs`, {
    method: 'POST',
    headers: authed(token),
    body: JSON.stringify({ filename, file_size: fileBytes.length }),
  })
  if (!createResp.ok) throw new Error(`createJob failed: ${createResp.status}`)
  const { job_id, upload_url } = await createResp.json()

  const uploadResp = await fetch(upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': 'image/jpeg' },
    body: fileBytes,
  })
  if (!uploadResp.ok) throw new Error(`S3 upload failed: ${uploadResp.status}`)

  const startResp = await fetch(`${API_URL}/jobs/${job_id}/start`, {
    method: 'POST',
    headers: authed(token),
  })
  if (!startResp.ok) throw new Error(`startJob failed: ${startResp.status}`)

  const deadline = Date.now() + UPLOAD_TIMEOUT
  while (Date.now() < deadline) {
    await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS))
    const { status } = await getJobStatus(token, job_id)
    if (status === 'complete') return job_id
    if (status === 'failed')   throw new Error(`Pipeline failed for job ${job_id}`)
  }
  throw new Error(`Pipeline timed out for job ${job_id}`)
}

/** Locates the step tree nav element */
function stepTree(page: Page) {
  return page.locator('[data-testid="step-tree"]').or(
    page.getByRole('main').locator('nav'),
  )
}

// ── Serial group: T-sfn-ui-01 through T-sfn-ui-04 ────────────────────────────
//
// All four tests share a single reprocess execution triggered in beforeAll.
// The execution skips Load and Normalize (Pass states) and runs everything
// from PageDetect onward. By the time the tests run, the job is mid-processing.

test.describe.serial('T-sfn-ui 01–04: reprocess from page_detect', () => {
  // Populated by beforeAll; referenced by each test
  let sharedToken = ''
  let sharedJobId = ''

  test.beforeAll(async () => {
    const token = readToken()
    const jobId = readCompletedJobId()
    if (!token || !jobId) return  // individual tests will be skipped via beforeEach

    sharedToken = token
    sharedJobId = jobId

    // Ensure job is idle before triggering a new reprocess
    await waitForIdle(token, jobId)

    const r = await fetch(`${API_URL}/jobs/${jobId}/reprocess`, {
      method: 'POST',
      headers: authed(token),
      body: JSON.stringify({ from_step: 'page_detect' }),
    })
    if (!r.ok) {
      throw new Error(`[sfn_ui] reprocess trigger failed: ${r.status} ${await r.text()}`)
    }

    // Wait up to 30 s for job status to flip to 'processing'
    const deadline = Date.now() + 30_000
    while (Date.now() < deadline) {
      await new Promise((res) => setTimeout(res, 3_000))
      const { status } = await getJobStatus(token, jobId)
      if (status === 'processing') break
    }
  })

  test.beforeEach(() => {
    if (!readToken()) {
      test.skip(true, 'No dev session — run global-setup first (session-dev.json missing)')
    }
    if (!readCompletedJobId()) {
      test.skip(true, 'No completed job — run global-setup first (completed-job-dev.json missing)')
    }
  })

  // ── T-sfn-ui-01 ──────────────────────────────────────────────────────────────

  test('T-sfn-ui-01: mid-reprocess donut reflects active step and step tree shows animate-ping', async ({ page }) => {
    test.setTimeout(2 * 60 * 1000)
    const jobId = sharedJobId

    // ── Library: progress wheel should be in-flight ─────────────────────────
    await page.goto('/library')
    const card = page.locator(`[data-job-id="${jobId}"]`)
    await expect(card).toBeVisible({ timeout: 15_000 })

    // The AfterSection renders a PipelineProgressWheel SVG while status is not
    // 'complete'. The SVG has aria-label="N of 6 steps complete".
    const donutSvg = card.locator('svg[aria-label*="of 6 steps complete"]')
    await expect(donutSvg).toBeVisible({ timeout: 15_000 })

    const ariaLabel = await donutSvg.getAttribute('aria-label')
    // page_detect → BACKEND_TO_VISUAL index 1 → "1 of 6 steps complete" initially;
    // may have advanced by the time the browser renders, but should not be 0 or 6.
    expect(
      ariaLabel,
      'Donut should reflect a mid-pipeline step (1–5 of 6), not 0 or 6',
    ).toMatch(/^[1-5] of 6 steps complete$/)

    // The "next" (unfilled) segment should be pulsing via sa-segment-pulse animation
    const pulsingPath = card.locator('path[style*="sa-segment-pulse"]')
    await expect(pulsingPath).toBeVisible({ timeout: 5_000 })

    // ── Job detail: active step row should have animate-ping ─────────────────
    await page.goto(`/jobs/${jobId}`)
    const tree = stepTree(page)
    await expect(tree).toBeVisible({ timeout: 10_000 })

    // Processing banner indicates the job is actively running
    await expect(
      page.getByText('Processing — results will update automatically when complete.'),
    ).toBeVisible({ timeout: 15_000 })

    // At least one step row should have the pulsing indicator while processing
    const pingingSpans = tree.locator('.animate-ping')
    await expect(pingingSpans.first()).toBeVisible({ timeout: 10_000 })
  })

  // ── T-sfn-ui-02 ──────────────────────────────────────────────────────────────

  test('T-sfn-ui-02: Load row is enabled when reprocessing from page_detect', async ({ page }) => {
    test.setTimeout(60_000)
    const jobId = sharedJobId

    await page.goto(`/jobs/${jobId}`)
    const tree = stepTree(page)
    await expect(tree).toBeVisible({ timeout: 10_000 })
    await page.waitForLoadState('networkidle')

    // Load was a Pass state, but its debug_url from the prior run is preserved.
    // The row must be enabled (clickable) — not grayed-out.
    const loadBtn = tree.getByRole('button', { name: 'Load' })
    await expect(loadBtn).toBeVisible({ timeout: 5_000 })
    await expect(loadBtn, 'Load row must be enabled — debug_url from prior run preserved').toBeEnabled()
  })

  // ── T-sfn-ui-03 ──────────────────────────────────────────────────────────────

  test('T-sfn-ui-03: Load row has no animate-ping when reprocessing from page_detect', async ({ page }) => {
    test.setTimeout(60_000)
    const jobId = sharedJobId

    await page.goto(`/jobs/${jobId}`)
    const tree = stepTree(page)
    await expect(tree).toBeVisible({ timeout: 10_000 })

    const loadBtn = tree.getByRole('button', { name: 'Load' })
    await expect(loadBtn).toBeVisible({ timeout: 5_000 })

    // Load was routed to a Pass (skip) state — it is never the active step.
    // Its TreeRow must not contain the pulsing amber dot.
    const loadPing = loadBtn.locator('.animate-ping')
    expect(
      await loadPing.count(),
      'Load row must not show animate-ping — it was skipped via Pass state',
    ).toBe(0)
  })

  // ── T-sfn-ui-04 ──────────────────────────────────────────────────────────────

  test('T-sfn-ui-04: post-reprocess: no animate-ping and all job-level rows enabled', async ({ page }) => {
    test.setTimeout(5 * 60 * 1000)
    const token = sharedToken
    const jobId  = sharedJobId

    // Wait for the reprocess to finish before asserting final state
    await waitForComplete(token, jobId)

    // ── Library: after completion output thumbnails replace the donut ────────
    await page.goto('/library')
    const card = page.locator(`[data-job-id="${jobId}"]`)
    await expect(card).toBeVisible({ timeout: 15_000 })
    await page.waitForLoadState('networkidle')

    // The sa-segment-pulse animation only fires when isRunning=true (processing).
    // After completion, no path in the card should carry that animation style.
    const pulsingPath = card.locator('path[style*="sa-segment-pulse"]')
    await expect(pulsingPath, 'Library card must have no pulsing segment after reprocess').toHaveCount(0)

    // ── Job detail: step tree must be clean ──────────────────────────────────
    await page.goto(`/jobs/${jobId}`)
    const tree = stepTree(page)
    await expect(tree).toBeVisible({ timeout: 10_000 })
    await page.waitForLoadState('networkidle')

    // No pulsing indicators anywhere in the step tree
    const pingingSpans = tree.locator('.animate-ping')
    expect(
      await pingingSpans.count(),
      'Step tree must contain no animate-ping elements after reprocess completes',
    ).toBe(0)

    // All four JOB_STEP_TREE rows must be enabled (debug_urls present for each)
    const loadBtn = tree.getByRole('button', { name: 'Load' })
    const pageBtn = tree.getByRole('button', { name: 'Page Detection' })
    const perspBtn = tree.getByRole('button', { name: 'Perspective' })
    const splitBtn = tree.getByRole('button', { name: 'Photo Split' })

    await expect(loadBtn, 'Load row must be enabled after reprocess').toBeEnabled({ timeout: 5_000 })
    await expect(pageBtn, 'Page Detection row must be enabled after reprocess').toBeEnabled()
    await expect(perspBtn, 'Perspective row must be enabled after reprocess').toBeEnabled()
    await expect(splitBtn, 'Photo Split row must be enabled after reprocess').toBeEnabled()
  })
})

// ── T-sfn-ui-05 ──────────────────────────────────────────────────────────────
//
// Upload the 2-photo fixture, navigate to the Orientation step for Photo 2,
// and click "Apply & Reprocess". The UI's onStarted handler sets
// reprocessingPhotoIdx = 2 and status = 'processing', which means only
// Photo 2's per-photo step rows should show animate-ping.

test('T-sfn-ui-05: single-photo UI reprocess shows animate-ping only for targeted photo', async ({ page }) => {
  test.setTimeout(12 * 60 * 1000)

  const token = readToken()
  if (!token) { test.skip(); return }

  // Upload the 2-photo fixture and wait for the full pipeline to complete
  console.log('[T-sfn-ui-05] Uploading 2-photo fixture and processing…')
  const jobId = await uploadAndProcess(token, FIXTURE_2UP)
  console.log(`[T-sfn-ui-05] Job ${jobId} complete with 2 photos`)

  // Navigate to the job detail page
  await page.goto(`/jobs/${jobId}`)
  const tree = stepTree(page)
  await expect(tree).toBeVisible({ timeout: 10_000 })
  await page.waitForLoadState('networkidle')

  // Locate Photo 2's Orientation row.
  // In a 2-photo job the step tree renders two "Orientation" buttons — one per
  // photo — in DOM order (Photo 1 first, Photo 2 second).
  const orientBtns = tree.getByRole('button', { name: 'Orientation' })
  const photo2OrientBtn = orientBtns.nth(1)
  await expect(photo2OrientBtn).toBeVisible({ timeout: 5_000 })
  await expect(photo2OrientBtn, 'Photo 2 Orientation row must be enabled').toBeEnabled()
  await photo2OrientBtn.click()

  // OrientationView: select 90° so the "Apply & Reprocess" button becomes enabled
  const rot90Btn = page.getByRole('button', { name: '90°' })
  await expect(rot90Btn).toBeVisible({ timeout: 5_000 })
  await rot90Btn.click()

  const applyBtn = page.getByRole('button', { name: 'Apply & Reprocess' })
  await expect(applyBtn).toBeEnabled({ timeout: 3_000 })

  // Intercept the reprocess request to confirm it fires before asserting UI state
  const reprocessReq = page.waitForRequest(
    (r) => r.url().includes('/reprocess') && r.method() === 'POST',
    { timeout: 5_000 },
  )
  await applyBtn.click()
  await reprocessReq  // request sent; onStarted fires → reprocessingPhotoIdx = 2

  // Processing banner should appear within seconds (optimistic status update)
  await expect(
    page.getByText('Processing — results will update automatically when complete.'),
  ).toBeVisible({ timeout: 10_000 })

  // Wait for the per-photo step (ai_orient) to show animate-ping.
  // The UI polls every ~4 s; after the first poll returns current_step='ai_orient',
  // the targeted photo's row starts pulsing.
  await expect(async () => {
    const count = await tree.locator('.animate-ping').count()
    expect(count, 'Expected at least one pulsing indicator while processing').toBeGreaterThan(0)
  }).toPass({ timeout: 30_000, intervals: [2_000] })

  // Locate the Photo 1 and Photo 2 section divs.
  // The step tree renders one direct-child <div> per photo containing the
  // "Photo N" heading span and that photo's per-photo TreeRow buttons.
  const photo1Section = page.locator('[data-testid="step-tree"] > div').filter({
    has: page.locator('span', { hasText: /^Photo 1$/ }),
  })
  const photo2Section = page.locator('[data-testid="step-tree"] > div').filter({
    has: page.locator('span', { hasText: /^Photo 2$/ }),
  })

  // Photo 2's rows should contain animate-ping (reprocessingPhotoIdx === 2)
  await expect(
    photo2Section.locator('.animate-ping').first(),
    'Photo 2 per-photo row must show animate-ping while being reprocessed',
  ).toBeVisible({ timeout: 10_000 })

  // Photo 1's rows must NOT pulse (reprocessingPhotoIdx !== 1)
  expect(
    await photo1Section.locator('.animate-ping').count(),
    'Photo 1 rows must not show animate-ping when only Photo 2 is targeted',
  ).toBe(0)
})
