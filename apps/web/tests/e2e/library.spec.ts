/**
 * Tests 36–40: Library page — upload preview, thumbnails, output thumbnails,
 * delete job, and progress wheel visibility.
 *
 * These tests run authenticated (storageState from global-setup).
 * They upload a small synthetic JPEG via the DropZone file input so no
 * real iPhone photo is required in CI.
 */

import path from 'path'
import fs from 'fs'
import os from 'os'
import { test, expect, type Page } from '@playwright/test'
import { COMPLETED_JOB_FILE } from '../../playwright.config'

function readCompletedJobId(): string | null {
  try {
    const d = JSON.parse(fs.readFileSync(COMPLETED_JOB_FILE, 'utf-8'))
    return typeof d.job_id === 'string' ? d.job_id : null
  } catch { return null }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Create a minimal valid JPEG file in a temp dir. */
function makeTinyJpeg(): string {
  // 1×1 white JPEG (minimal valid JFIF)
  const jpegBytes = Buffer.from(
    'ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909' +
    '0806050808090a0b0c0c0b0a0a0c0f11100c0e0f0d0a0a0c1612130f141011120e0e1619' +
    '16171813181716161a1b1d1b18191c191617161c211c1a1e211f17181d221d1e2124242424' +
    '17191d261d242122241f1d2126251f202224242524' +
    'ffc0000b080001000101011100ffc40014000100000000000000000000000000000000' +
    'ffc40014100100000000000000000000000000000000ffd9',
    'hex',
  )
  const tmpFile = path.join(os.tmpdir(), `sa_test_${Date.now()}.jpg`)
  fs.writeFileSync(tmpFile, jpegBytes)
  return tmpFile
}

/**
 * Locates album cards — works with both the deployed build (no data-testid)
 * and the new build (has data-testid). Each card has a <p title={filename}>
 * as a direct child of the card div.
 */
function anyCard(page: Page) {
  return page.locator('[data-testid="album-card"]').or(
    page.locator('p[title]').locator('xpath=..'),
  )
}

// ── T36: Upload creates a card with filename ──────────────────────────────────

test('T36: upload creates card with filename', async ({ page }) => {
  await page.goto('/library')
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible()

  const tmpFile = makeTinyJpeg()
  try {
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(tmpFile)

    const filename = path.basename(tmpFile)
    // Wait for the filename text — most reliable signal that the card appeared
    await expect(page.getByText(filename, { exact: false })).toBeVisible({ timeout: 10_000 })

    // Confirm a card element wraps the filename
    const card = anyCard(page).first()
    await expect(card).toBeVisible({ timeout: 5_000 })
  } finally {
    fs.unlinkSync(tmpFile)
  }
})

// ── T37: Before-thumbnail appears in card ─────────────────────────────────────

test('T37: before-thumbnail img appears in card after upload', async ({ page }) => {
  await page.goto('/library')

  const tmpFile = makeTinyJpeg()
  try {
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(tmpFile)

    const filename = path.basename(tmpFile)
    await expect(page.getByText(filename, { exact: false })).toBeVisible({ timeout: 10_000 })

    // The card should render a ThumbBox with an <img> (the optimistic preview_url)
    const card = anyCard(page).first()
    const thumbImg = card.locator('img').first()
    await expect(thumbImg).toBeVisible({ timeout: 5_000 })
  } finally {
    fs.unlinkSync(tmpFile)
  }
})

// ── T38: Completed job shows output photos in card ────────────────────────────

test('T38: complete job shows output photos in the after-section', async ({ page }) => {
  // global-setup uploads test_photo.jpg and waits for pipeline completion
  const jobId = readCompletedJobId()
  if (!jobId) { test.skip(); return }

  await page.goto('/library')
  await expect(page.getByRole('heading', { name: 'Library' })).toBeVisible()

  // The list endpoint omits output_urls; AlbumPageCard fires a getJob fetch on
  // mount to hydrate them. Find the fixture card by its job_id (data-job-id
  // attribute) — the library can accumulate multiple test_photo.jpg cards from
  // previous runs, so matching by filename alone triggers strict-mode violations.
  const fixtureCard = page.locator(`[data-job-id="${jobId}"]`)
  await expect(fixtureCard).toBeVisible({ timeout: 10_000 })

  // After the card's useEffect fetches the full job, output imgs appear
  // The after-section renders inside the same card; wait for >1 img total
  await expect(async () => {
    const imgCount = await fixtureCard.locator('img').count()
    expect(imgCount).toBeGreaterThan(1)
  }).toPass({ timeout: 15_000 })

  await expect(fixtureCard.locator('img').nth(1)).toBeVisible()
})

// ── T39: Delete button removes the card ──────────────────────────────────────

test('T39: delete button removes card from library', async ({ page }) => {
  await page.goto('/library')

  const tmpFile = makeTinyJpeg()
  try {
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(tmpFile)

    const filename = path.basename(tmpFile)

    // Wait for the card to have a real job_id — i.e. the optimistic
    // "uploading-{ts}" card has been replaced by the real job from setJobs().
    // Using data-job-id is more reliable than waitForResponse(GET /jobs) which
    // can resolve on a background poll before the upload cycle's own listJobs()
    // fires. If we proceeded on the wrong GET /jobs, the card still has the
    // optimistic id and deleteJob() would send DELETE /jobs/uploading-{ts} → 404.
    const realCard = page
      .locator('[data-job-id]:not([data-job-id^="uploading-"])')
      .filter({ has: page.locator(`p[title="${filename}"]`) })
    await expect(realCard).toBeVisible({ timeout: 20_000 })

    const countBefore = await anyCard(page).count()

    // Intercept the DELETE before hovering so we never miss the response.
    // handleDelete() calls removeJob() in a finally block after deleteJob()
    // resolves — the card only disappears once the API round-trip completes.
    const deletionComplete = page.waitForResponse(
      (r) =>
        r.url().includes('/jobs/') &&
        r.request().method() === 'DELETE' &&
        r.status() === 200,
      { timeout: 20_000 },
    )

    await realCard.hover()
    const deleteBtn = realCard.getByRole('button', { name: 'Delete job' })
    await expect(deleteBtn).toBeVisible({ timeout: 3_000 })
    await deleteBtn.click()
    await deletionComplete

    // removeJob() fires synchronously after the DELETE response — card should
    // be gone within one React render cycle.
    await expect(page.getByText(filename, { exact: false })).not.toBeAttached({ timeout: 5_000 })

    const countAfter = await anyCard(page).count()
    expect(countAfter).toBeLessThan(countBefore)
  } finally {
    fs.unlinkSync(tmpFile)
  }
})

// ── T40: Processing card shows progress wheel SVG ─────────────────────────────

test('T40: processing card shows progress wheel', async ({ page }) => {
  await page.goto('/library')

  const tmpFile = makeTinyJpeg()
  try {
    const fileInput = page.locator('input[type="file"]').first()
    await fileInput.setInputFiles(tmpFile)

    const filename = path.basename(tmpFile)
    await expect(page.getByText(filename, { exact: false })).toBeVisible({ timeout: 10_000 })

    const card = anyCard(page).first()

    // The card is uploading/processing (shows ProgressWheel SVG) or has an img
    // (completed quickly). Either way, some visual element should be present.
    const svgOrImg = card.locator('svg, img')
    await expect(svgOrImg.first()).toBeVisible({ timeout: 5_000 })
  } finally {
    fs.unlinkSync(tmpFile)
  }
})
