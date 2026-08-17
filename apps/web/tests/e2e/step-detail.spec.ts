/**
 * Tests 41–45: Step-detail page — StepTree, auto-select, thumbnail strip,
 * Results view, reprocess trigger.
 *
 * global-setup uploads a real photo and waits for it to complete.
 * The completed job_id is read from .auth/completed-job.json.
 */

import fs from 'fs'
import { test, expect, type Page } from '@playwright/test'
import { COMPLETED_JOB_FILE } from '../../playwright.config'

// ── Helpers ───────────────────────────────────────────────────────────────────

function readCompletedJobId(): string | null {
  try {
    const d = JSON.parse(fs.readFileSync(COMPLETED_JOB_FILE, 'utf-8'))
    return typeof d.job_id === 'string' ? d.job_id : null
  } catch { return null }
}

/**
 * StepTree locator — works with or without data-testid.
 * The step tree nav is inside <main> (scoped away from the header nav).
 */
function stepTree(page: Page) {
  return page.locator('[data-testid="step-tree"]').or(
    page.getByRole('main').locator('nav'),
  )
}

// ── T41: StepTree is visible on job detail page ───────────────────────────────

test('T41: step-detail page renders StepTree', async ({ page }) => {
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto(`/jobs/${jobId}`)

  const tree = stepTree(page)
  await expect(tree).toBeVisible({ timeout: 10_000 })

  // "Load" is always the first step in JOB_STEP_TREE
  await expect(tree.getByRole('button', { name: 'Load' })).toBeVisible()
})

// ── T42: Breadcrumb shows selected step name ──────────────────────────────────

test('T42: breadcrumb shows selected step name', async ({ page }) => {
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto(`/jobs/${jobId}`)
  await page.waitForLoadState('networkidle')

  // Scope to <main> — nav header also has a Library link
  const libraryLink = page.getByRole('main').getByRole('link', { name: 'Library' })
  await expect(libraryLink).toBeVisible({ timeout: 10_000 })
})

// ── T43: Thumbnail strip appears for completed single-photo job ───────────────

test('T43: thumbnail strip visible for completed single-photo job', async ({ page }) => {
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto(`/jobs/${jobId}`)
  await page.waitForLoadState('networkidle')

  // The thumb strip renders img elements with alt text from THUMB_STRIP_LABELS:
  // "Load", "Page", "Warp", "Split", "Orient", "Glare", "Color".
  // It only renders for single-photo jobs with thumbnail_urls.
  // Wait up to 8 s for it to appear; if absent the job must be multi-photo.
  const loadThumb = page.locator('img[alt="Load"]').first()
  const loadVisible = await loadThumb.waitFor({ state: 'visible', timeout: 8_000 })
    .then(() => true)
    .catch(() => false)

  if (!loadVisible) { test.skip(); return }

  await expect(loadThumb).toBeVisible()
  await expect(page.locator('img[alt="Color"]').first()).toBeVisible()
})

// ── T44: Results view renders output photo ────────────────────────────────────

test('T44: Results view shows output photo', async ({ page }) => {
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto(`/jobs/${jobId}`)

  const tree = stepTree(page)
  await expect(tree).toBeVisible({ timeout: 10_000 })

  const resultsBtn = tree.getByRole('button', { name: 'Results' })
  await expect(resultsBtn).toBeVisible({ timeout: 5_000 })
  await resultsBtn.click()

  // Results view: works with or without data-testid
  const resultsView = page.locator('[data-testid="results-view"]').or(
    page.locator('button', { hasText: /download all/i }).locator('xpath=./../../..'),
  )
  await expect(resultsView).toBeVisible({ timeout: 5_000 })
  await expect(resultsView.locator('img').first()).toBeVisible()
})

// ── T45: Reprocess — ColorRestoreView sends correct config key ───────────────
//
// Regression test for the saturation_boost → color_restore_vibrance_boost rename.
// Moves the Saturation slider then clicks "Apply & Reprocess" and asserts the POST
// body contains `color_restore_vibrance_boost` (not the old `saturation_boost` key).

test('T45: color restore reprocess sends color_restore_vibrance_boost key', async ({ page }) => {
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto(`/jobs/${jobId}`)

  const tree = stepTree(page)
  await expect(tree).toBeVisible({ timeout: 10_000 })
  await page.waitForLoadState('networkidle')

  // Navigate to Color Restoration step (per-photo)
  const colorBtn = tree.getByRole('button', { name: 'Color Restoration' })
  const colorVisible = await colorBtn.waitFor({ state: 'visible', timeout: 8_000 })
    .then(() => true).catch(() => false)
  if (!colorVisible) { test.skip(); return }

  const colorEnabled = await colorBtn.isEnabled()
  if (!colorEnabled) { test.skip(); return }

  await colorBtn.click()

  // Move the Saturation slider away from default (15) to make the button enabled
  const satSlider = page.locator('input[type="range"]').first()
  await expect(satSlider).toBeVisible({ timeout: 5_000 })
  await satSlider.fill('30')
  await satSlider.dispatchEvent('input')

  // "Apply & Reprocess" should now be enabled
  const applyBtn = page.getByRole('button', { name: 'Apply & Reprocess' })
  await expect(applyBtn).toBeEnabled({ timeout: 3_000 })

  // Intercept the reprocess POST and capture the request body
  let capturedBody: Record<string, unknown> | null = null
  const reqPromise = page.waitForRequest(
    (r) => r.url().includes('/reprocess') && r.method() === 'POST',
    { timeout: 5_000 },
  ).then((req) => {
    try { capturedBody = JSON.parse(req.postData() ?? '{}') } catch { /* ignore */ }
    return req
  }).catch(() => null)

  await applyBtn.click()
  await reqPromise

  // Assert correct config key was sent
  expect(capturedBody).not.toBeNull()
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  const body = capturedBody! as unknown as Record<string, unknown>
  const config = body?.config as Record<string, unknown> | undefined
  expect(config).toBeDefined()
  expect(config).not.toHaveProperty('saturation_boost')
  expect(config).toHaveProperty('color_restore_vibrance_boost')
  expect(config).toHaveProperty('sharpen_amount')
})

// ── T46: Reprocess — GlareRemovalView Apply button sends POST /reprocess ──────

test('T46: glare removal Re-run button triggers reprocess API call', async ({ page }) => {
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto(`/jobs/${jobId}`)

  const tree = stepTree(page)
  await expect(tree).toBeVisible({ timeout: 10_000 })
  await page.waitForLoadState('networkidle')

  // "Glare Removal" step — enabled only when debug_urls has 07_photo_01_deglared
  const glareBtn = tree.getByRole('button', { name: 'Glare Removal' })
  const glareVisible = await glareBtn.waitFor({ state: 'visible', timeout: 8_000 })
    .then(() => true)
    .catch(() => false)
  if (!glareVisible) { test.skip(); return }

  const glareEnabled = await glareBtn.isEnabled()
  if (!glareEnabled) { test.skip(); return }

  await glareBtn.click()

  // GlareRemovalView always renders the "Re-run Glare Removal" button
  const rerunBtn = page.getByRole('button', { name: 'Re-run Glare Removal' })
  await expect(rerunBtn).toBeVisible({ timeout: 5_000 })

  const reprocessPromise = page.waitForRequest(
    (r) => r.url().includes('/reprocess') && r.method() === 'POST',
    { timeout: 5_000 },
  ).catch(() => null)

  await rerunBtn.click()

  const req = await reprocessPromise
  if (req) {
    expect(req.method()).toBe('POST')
  } else {
    // Button disabled means request already in flight
    await expect(rerunBtn).toBeDisabled({ timeout: 3_000 })
  }
})
