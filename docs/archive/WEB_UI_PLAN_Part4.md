> **DEPRECATED — Historical implementation plan only.**
> This document records the design decisions made during Phases 7–9 web UI development.
> Branch references to `web-ui-implementation` are stale — the active staging branch is now `dev`.
> For the current system design, resource names, and SDLC process, see **`docs/SYSTEM_ARCHITECTURE.md`**.
> For the current CLAUDE instructions, see **`CLAUDE.md`**.

# Sunday Album Web UI — Implementation Plan (Part 4 of 4)
# Phases 7–9: Testing, Admin Tools, Production Hardening

**Version:** 1.3
**Date:** April 2026
**Status:** Phases 7.1–7.5 + 7.4 complete. Pre-commit hook added (36 moto tests + 12 Playwright E2E). Phase 8 (admin tools) not yet implemented. Phase 9 (production hardening) not yet implemented.
**See also:** WEB_UI_PLAN_Part1.md (Phases 0–2: ✅), WEB_UI_PLAN_Part2.md (Phase 3: ✅), WEB_UI_PLAN_Part3.md (Phases 4–6: ✅)

---

## Phase 7: Functional Tests

Cover the API layer, pipeline handler layer, and frontend with targeted functional tests. Priority order: API → Handlers → Frontend.

### 7.1 API Layer Tests (`tests/api/`) ✅ COMPLETE (2026-03-29)

Pure Python tests using `pytest` + `moto` to mock AWS services (DynamoDB, S3, SES, Step Functions). No real AWS calls. Fast — run on every commit.

**Auth**

| # | Test | What it asserts |
|---|------|----------------|
| 1 | `test_send_code_valid_email` | POST /auth/send-code returns 200, SES `send_email` called once |
| 2 | `test_send_code_invalid_email` | Malformed email returns 400 |
| 3 | `test_verify_code_valid` | Correct code returns `session_token`, `user_hash`, `expires_at` |
| 4 | `test_verify_code_invalid` | Wrong code returns 401 |
| 5 | `test_verify_code_expired` | Code older than TTL returns 401 |
| 6 | `test_logout` | Valid session is invalidated; subsequent calls with same token return 401 |

**Job Lifecycle**

| # | Test | What it asserts |
|---|------|----------------|
| 7 | `test_create_job_initializes_maps` | POST /jobs creates DDB item with `debug_keys: {}` AND `thumbnail_keys: {}` — both empty maps present from creation |
| 8 | `test_create_job_unsupported_format` | `.bmp` extension returns 400 |
| 9 | `test_create_job_too_large` | File size > 200 MB returns 400 |
| 10 | `test_start_job_no_s3_upload` | Start before S3 upload exists returns 400 |
| 11 | `test_get_job_returns_debug_urls` | After pipeline writes `debug_keys`, GET /jobs/{id} returns `debug_urls` with presigned URLs for all keys |
| 12 | `test_get_job_returns_thumbnail_urls` | After pipeline writes `thumbnail_keys`, GET /jobs/{id} returns `thumbnail_urls` map and `thumbnail_url` singular |
| 13 | `test_list_jobs_returns_thumbnail_url` | GET /jobs returns `thumbnail_url` for jobs that have `thumbnail_keys["01_loaded"]` set |
| 14 | `test_delete_job` | DELETE /jobs/{id} removes item from DDB; subsequent GET returns 404 |
| 15 | `test_get_job_wrong_user` | Querying another user's job_id returns 404 (not 403 — avoids leaking existence) |

**Rate Limiting**

| # | Test | What it asserts |
|---|------|----------------|
| 16 | `test_rate_limit_enforced` | 21st job creation in same UTC day returns 429 |
| 17 | `test_rate_limit_bypassed_with_own_keys` | User with both API keys stored bypasses the daily limit |
| 18 | `test_rate_limit_admin_bypass` | Admin email (in `ADMIN_EMAILS`) bypasses rate limit |

**Reprocessing**

| # | Test | What it asserts |
|---|------|----------------|
| 19 | `test_reprocess_valid_step` | POST /jobs/{id}/reprocess with valid `from_step` returns 200 and starts Step Functions execution |
| 20 | `test_reprocess_invalid_step` | Unknown `from_step` value returns 400 |
| 21 | `test_reprocess_while_processing` | Job already `processing` returns 409 |

**Settings**

| # | Test | What it asserts |
|---|------|----------------|
| 22 | `test_store_and_retrieve_api_keys` | PUT then GET returns presence flags `has_anthropic_key: true` (not raw values) |
| 23 | `test_delete_api_keys` | DELETE clears stored keys; subsequent GET returns both flags false |

---

### 7.2 Pipeline Handler Tests (`tests/handlers/`) ✅ COMPLETE (2026-03-29)

Use `moto` for DynamoDB + S3, and stub out the actual image processing step functions (e.g., `src.steps.load.run`) to return minimal valid outputs. Focus on verifying that each handler correctly writes `debug_keys` and `thumbnail_keys` to DynamoDB and puts files in S3.

**Per-step write correctness**

| # | Test | What it asserts |
|---|------|----------------|
| 23 | `test_load_writes_debug_and_thumbnail_keys` | After `load.handler`, DDB item has `debug_keys["01_loaded"]` and `thumbnail_keys["01_loaded"]`; both S3 objects exist |
| 24 | `test_normalize_writes_keys` | `debug_keys["02_normalized"]` and `thumbnail_keys["02_normalized"]` written |
| 25 | `test_page_detect_writes_keys` | `debug_keys["02_page_detected"]` and `thumbnail_keys["02_page_detected"]` written |
| 26 | `test_perspective_writes_keys` | `debug_keys["03_page_warped"]` and `thumbnail_keys["03_page_warped"]` written |
| 27 | `test_photo_split_writes_keys_per_photo` | 2-photo image produces `05_photo_01_raw` and `05_photo_02_raw` in both maps |
| 28 | `test_ai_orient_writes_keys` | `05b_photo_01_oriented` in both maps |
| 29 | `test_glare_remove_writes_keys` | `07_photo_01_deglared` in both maps |
| 30 | `test_color_restore_writes_keys` | `14_photo_01_enhanced` in both maps |

**Error and skip behavior**

| # | Test | What it asserts |
|---|------|----------------|
| 31 | `test_step_failure_marks_job_failed` | Exception raised inside a step sets DDB `status="failed"` with a non-empty `error_message` |
| 32 | `test_skip_pre_split_when_start_from_later` | `should_skip_pre_split(event, "load")` returns `True` when `event["start_from"] = "ai_orient"` |
| 33 | `test_skip_per_photo_wrong_index` | Per-photo step is skipped for photos that don't match `reprocess_photo_index` |

**Finalize**

| # | Test | What it asserts |
|---|------|----------------|
| 34 | `test_finalize_marks_complete` | `finalize.handler` sets `status="complete"`, writes `output_keys`, sets `photo_count` |
| 35 | `test_finalize_empty_results_marks_failed` | Empty `photo_results` list sets `status="failed"` |

---

### 7.3 Frontend Tests (`web/tests/e2e/` — Playwright) ✅ COMPLETE (2026-03-30, updated 2026-04-02)

Run against the dev environment (`https://dev.sundayalbum.com`). Require a logged-in session (use a dedicated test account). These are slower (~33 s with warm session cache); run locally via the pre-commit hook (see §7.6) after each deploy, not in CI.

**Library page**

| # | Test | What it asserts |
|---|------|----------------|
| 36 | `test_upload_shows_optimistic_preview` | Immediately after file drop, the card appears with a before-thumbnail from the blob URL (before API responds) |
| 37 | `test_completed_job_thumbnail_visible` | Navigating to library with a completed job shows `thumbnail_url` image in ThumbBox on both compact and expanded card |
| 38 | `test_completed_job_output_thumbs_visible` | Output photos render in AfterSection of the completed card |
| 39 | `test_delete_card` | Clicking × on a card calls DELETE and removes it from the grid |
| 40 | `test_processing_job_shows_progress_wheel` | While a job is processing, the AfterSection shows the pie wheel (not blank) |

**Step detail page**

| # | Test | What it asserts |
|---|------|----------------|
| 41 | `test_step_tree_items_enabled` | All steps with a `debug_url` are clickable (not greyed out) in the StepTree sidebar |
| 42 | `test_step_tree_auto_selects_first_available` | Navigating to `/jobs/{id}` auto-selects the first step with a debug image, not Results |
| 43 | `test_thumbnail_strip_renders` | Single-photo job shows the horizontal thumbnail strip above the step tree |
| 44 | `test_results_view_shows_output_photos` | Clicking "Results" in the step tree renders all output images |
| 45 | `test_orientation_reprocess` | Selecting 90° rotation and clicking "Apply & Reprocess" calls POST /reprocess and shows the reprocessing banner |

**WebSocket live updates**

| # | Test | What it asserts |
|---|------|----------------|
| 46 | `test_ws_step_update_advances_wheel` | Uploading a new image and watching the library page shows the pie wheel advancing as steps complete (without page refresh) |
| 47 | `test_ws_complete_shows_thumbnails` | When the job completes, the output thumbnails appear in the card AfterSection without a page refresh |

---

### 7.5 UI Polish ✅ COMPLETE (2026-03-30)

Three targeted improvements to the web frontend.

**1. Dark/Light mode — system-aware with manual override**

The app already used `darkMode: 'class'` in Tailwind and had CSS variables for dark/light tokens. This change makes the theme actually respond to the system setting and adds a manual override.

| File | Change |
|------|--------|
| `web/src/stores/theme-store.ts` | New Zustand store. Preference is `'system' \| 'light' \| 'dark'`, persisted as plain string in `localStorage` key `sa_theme` |
| `web/src/app/layout.tsx` | Inline `<script>` in `<head>` runs synchronously before React paint — reads `sa_theme`, applies `dark` class to `<html>` with no flash of wrong theme. Wraps app in `<ThemeProvider>` |
| `web/src/components/ThemeProvider.tsx` | Client component — hydrates store from localStorage on mount; watches `prefers-color-scheme` media query when preference is `'system'` |
| `web/src/components/settings/AppearanceSettings.tsx` | 3-segment toggle (System / Light / Dark) with icons, added to the Settings page |
| `web/src/app/(app)/settings/page.tsx` | Renders `<AppearanceSettings />` above `<ApiKeySettings />` |

**2. Persistent drop zone on Library page**

Previously the compact `DropZone` (drop target + "Choose Files" button) was only shown when the library was empty. Now it appears above the card grid at all times so users can add more photos without hunting for the "Add Photos" button.

| File | Change |
|------|--------|
| `web/src/app/(app)/library/page.tsx` | `<DropZone compact />` inserted above the grid in the populated-library branch |

The existing `DropZone` compact variant and full-page drag overlay are unchanged.

**3. Fixed-size output thumbnails in library card**

The `AfterSection` previously used `gridTemplateColumns: repeat(N, 1fr)` with `object-cover` — each output photo filled its column, clipping the image. With 1 photo you got a wide crop; with 3 photos you got 3 narrow slivers.

| File | Change |
|------|--------|
| `web/src/components/library/AlbumPageCard.tsx` | Each output photo now renders in a fixed `72×88px` box (`object-contain`, `bg-sa-surface` background). Photos sit in a horizontal flex row that scrolls if needed (hidden scrollbar). Shows the complete image regardless of portrait/landscape aspect ratio or output count. |

**Verification checklist — 7.5**

- [x] System dark/light mode applied on first load with no flash of wrong theme
- [x] Manually switching to Light/Dark in Settings persists across refreshes
- [x] Switching back to System follows system preference including live changes
- [x] Compact drop zone visible on Library page when jobs exist
- [x] Files dropped onto the compact zone upload correctly
- [x] Output thumbnails show complete images (no cropping) at fixed 72×88px
- [x] Multiple output photos scroll horizontally in the card
- [x] Production build (`npm run build`) passes with no TypeScript errors

---

### 7.4 CI Integration ✅ COMPLETE (2026-03-31, updated 2026-04-02)

**`.github/workflows/test-api.yml`** — triggers on push to any branch when `api/**`, `handlers/**`, or `tests/api/**` / `tests/handlers/**` change:

```yaml
on:
  push:
    paths:
      - "api/**"
      - "handlers/**"
      - "tests/api/**"
      - "tests/handlers/**"
```

Steps: checkout → setup Python 3.12 → `pip install pytest moto boto3` → `pytest tests/api/ tests/handlers/ -v`

**`.github/workflows/test-web.yml`** — Playwright E2E tests. **Removed auto-trigger on 2026-04-02.** The workflow now only has `workflow_dispatch` (manual trigger from GitHub UI). Reason: the deploy workflow (`deploy-web.yml`) and the test workflow ran in parallel — tests always ran against the pre-deploy build, causing false failures as test fixes raced with the deployment that needed to serve them. Playwright now runs locally via the pre-commit hook (§7.6) after each deploy.

```yaml
on:
  workflow_dispatch:   # manual only
```

**`.github/workflows/deploy-web.yml`** — triggers on push to `web-ui-implementation` (→ dev) or `main` (→ prod) when `web/**` changes:

- `web-ui-implementation` → `sundayalbum-web-dev` App Runner (dev.sundayalbum.com)
- `main` → `sundayalbum-web-prod` App Runner (awaiting custom domain)
- Waits for App Runner to reach `RUNNING` before the job completes (~4–5 min)

**`.github/workflows/deploy-lambda.yml`** — triggers on push to `web-ui-implementation` or `main` when `api/**`, `handlers/**`, or `src/steps/**` change. Zips and updates the API Lambda + pipeline step Lambdas.

---

### 7.5 Verification Checklist

- [x] `pytest tests/api/ -v` passes — 23 API tests green (moto, no real AWS)
- [x] `pytest tests/handlers/ -v` passes — 13 handler tests green (moto, no real AWS)
- [x] `pytest tests/api/ tests/handlers/ -v` passes together — 36 tests green (2026-03-29)
- [x] Test #7 (`test_create_job_initializes_maps`) verifies both `debug_keys: {}` and `thumbnail_keys: {}` at creation — regression guard for bug fixed 2026-03-29
- [x] CI workflow `test-api.yml` created — triggers on `api/**`, `handlers/**`, `tests/api/**`, `tests/handlers/**` changes
- [x] Playwright suite runs against `dev.sundayalbum.com` without failures — all 12 tests green (2026-03-30)
- [x] CI workflow `test-web.yml` updated to `workflow_dispatch` only — Playwright no longer runs in CI (2026-04-02)
- [x] Lambda deployment workflow deploys `api/` ZIP + pipeline Docker image to dev Lambda on push (7.4 — `.github/workflows/deploy-lambda.yml`, 2026-03-31)
- [x] Pre-commit hook installed — runs 36 pytest + 12 Playwright on every commit (2026-04-02)
- [x] PR #32 (`web-ui-implementation` → `main`) made conflict-free via `git merge -s ours main` (2026-04-02)

**Implementation notes (2026-04-02 — T38/T39 fixes):**
- **T38 strict-mode violation**: The library accumulates multiple `test_photo.jpg` cards from prior test runs (the global setup never cleans up old fixture jobs). Using `p[title="test_photo.jpg"]` triggered Playwright's strict-mode error once 2+ cards matched. Fix: added `data-job-id={job.job_id}` attribute to `AlbumPageCard`'s root `<motion.div>`, then narrowed the T38 locator to `[data-job-id="${jobId}"]` using the ID from `readCompletedJobId()`.
- **T39 optimistic-card race**: The test previously used `waitForResponse(GET /jobs)` to detect when the upload cycle's `setJobs()` had run. But `waitForResponse` resolves when the network response arrives, not when React has processed it — a background poll on GET /jobs could resolve the promise before the upload cycle's own response, leaving the card with its optimistic `job_id: "uploading-{ts}"`. Clicking delete on an optimistic card sent `DELETE /jobs/uploading-{ts}` → 404 → the `waitForResponse(DELETE, status 200)` timed out. Fix: use `[data-job-id]:not([data-job-id^="uploading-"])` scoped to the filename's card — this directly observes React state and resolves as soon as the real job is in the store. T39 now completes in ~4s.
- **Auth rate limit**: `send-code` endpoint applies a 3-requests-per-hour rate limit unconditionally, including for admin emails. The `is_admin()` bypass only applies to the daily job creation rate limit. After 3 CI runs in one hour exhausted the quota, tests must wait for the 1-hour window to reset. Mitigation: `web/.auth/session.json` and `.auth/completed-job.json` are cached locally — subsequent pre-commit hook runs reuse both, skipping auth entirely.

**Implementation notes (2026-03-30 — Phase 7.3):**
- Tests live in `web/tests/e2e/` (not `tests/web/` as originally planned) to keep them alongside the Next.js app.
- Test fixture: `web/tests/e2e/fixtures/test_photo.jpg` — real 900×1200 JPEG (253 KB) converted from `test-images/IMG_skydiving_normal.HEIC` using PIL. Committed to repo so CI doesn't need test-images downloaded.
- Global setup (`global-setup.ts`) authenticates via `send-code` → DynamoDB code read → `verify`, saves session to `.auth/session.json` (storageState), then uploads the fixture and polls `GET /jobs/{id}` every 5s until `status === complete` (3-min timeout). Both the session token and the completed `job_id` are cached across runs: subsequent `npx playwright test` calls reuse both, completing in ~33s instead of ~3.5min.
- `stepTree(page)` scoped to `page.getByRole('main').locator('nav')` to avoid matching the top-level header `<nav>`.
- SES sandbox: `<test-user-email>` verified as an email identity before tests could run (one-time setup, already done).
- T38 uses `[data-job-id="${jobId}"]` to target the exact fixture card (see T38/T39 notes above).
- All 12 tests (T36–T47) pass in ~33s on second run. First run takes ~3.5min waiting for pipeline completion.

**Implementation notes (2026-03-29):**
- Tests use `moto` 5.1.22 with `us-west-2` region throughout.
- Root `tests/conftest.py` provides single `autouse` `aws_services` fixture — prevents module-level env var conflicts when both suites run together.
- `--import-mode=importlib` added to pytest config so conftest files from different subdirectories don't shadow each other.
- Handler tests stub `src.steps.*` at the function level; only DynamoDB writes and S3 puts are exercised against moto.
- All 36 tests run in ~4–5s locally.

---

### 7.6 Pre-commit Hook ✅ COMPLETE (2026-04-02)

A git pre-commit hook runs both test suites automatically on every commit.

**Location:** `.githooks/pre-commit` (versioned in the repo)

**Install (one-time per clone):**

```bash
git config core.hooksPath .githooks
```

This tells git to load hooks from `.githooks/` instead of `.git/hooks/`. All hooks in `.githooks/` are committed to the repo and shared across the team.

**What it runs:**

1. **Python API + handler tests** (always) — `pytest tests/api/ tests/handlers/ -q --tb=short` via `.venv`. Runs in ~5s with no external dependencies (moto mocks all AWS calls).

2. **Playwright E2E tests** (when session is available) — `npx playwright test` from `web/`. Runs in ~33s. Skipped gracefully if `web/.auth/session.json` doesn't exist (e.g., fresh clone before first local auth).

**Skip hook for a one-off commit:**

```bash
SKIP_HOOKS=1 git commit -m "wip"
```

**First-time setup on a fresh clone:**

```bash
# 1. Install Python deps
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"

# 2. Install Node deps + Playwright browser
cd web && npm ci && npx playwright install chromium --with-deps && cd ..

# 3. Set env vars and run Playwright once to authenticate + seed the fixture job
export TEST_USER_EMAIL=<test-user-email>
export DEV_FRONTEND_URL=https://dev.sundayalbum.com
export DEV_API_URL=https://nodcooz758.execute-api.us-west-2.amazonaws.com
export AWS_ACCESS_KEY_ID=<from secrets.json>
export AWS_SECRET_ACCESS_KEY=<from secrets.json>
cd web && npx playwright test && cd ..

# 4. Install the hook
git config core.hooksPath .githooks
```

After step 3, `web/.auth/session.json` and `web/.auth/completed-job.json` are cached. The pre-commit hook reuses them on every subsequent commit — no re-authentication needed.

---

## Phase 8: Admin Tools — User Impersonation & Debugging

This phase adds a secure admin panel so the operator can inspect and debug any user's jobs without asking users to share screenshots or reproduce issues manually.

### 8.1 Auth System Extensions

**Backend — `is_admin` flag in auth response**

The `/auth/verify` response currently returns `{ session_token, user_hash, expires_at }`. Add `is_admin: bool` (true if the verified email is in the `ADMIN_EMAILS` environment variable). Store this in the Zustand auth store and localStorage alongside `session_token` and `user_hash`.

**Backend — `X-Impersonate-User` header support in `require_auth()`**

Extend `api/common.py` → `require_auth()`:

1. Validate the caller's Bearer token as normal → get `(email, caller_user_hash)`.
2. If the request includes `X-Impersonate-User: {target_user_hash}` AND the caller is admin (email in `ADMIN_EMAILS`), return `target_user_hash` as the effective user instead of `caller_user_hash`.
3. Log an `INFO` line for every impersonated request: `admin={email} impersonating user_hash={target}` for auditability.
4. If a non-admin sends `X-Impersonate-User`, ignore the header silently (do not error — avoids leaking admin feature existence).

No other handler (`jobs.py`, `settings.py`, etc.) needs to change — they all consume `user_hash` from `require_auth()` already.

**Backend — `/admin/users` endpoint**

Add a new route group under `/admin/*`, handled by the existing `api_fn` Lambda (or a new `admin_fn` — same Lambda is fine for now). All `/admin/*` routes call `require_auth()` first and reject non-admins with 403.

`GET /admin/users?search={email_prefix}&limit={n}`

- Scan the `sa-sessions` DynamoDB table (partition key = `email`). This table always contains the email → user_hash mapping regardless of whether a session is currently active.
- Optional `search` param: filter scanned items by `begins_with(email, search)` using a FilterExpression.
- For each unique `user_hash` found, query `sa-jobs` to get: job count total, last job date (`job_id` is a ULID so sort by SK descending), and last job status.
- Return up to `limit` users (default 50), sorted by most recent job date descending.

Response shape:
```json
{
  "users": [
    {
      "email": "user@example.com",
      "user_hash": "abc123...",
      "job_count": 12,
      "last_job_at": "2026-03-28T10:12:00Z",
      "last_job_status": "complete"
    }
  ],
  "count": 1
}
```

**Note on sa-sessions scan:** The TTL on session tokens is 7 days but the underlying email record persists (only the `session_token` field expires). A DynamoDB scan of sa-sessions returns all records including those with expired tokens — email and user_hash are always present. This makes it a reliable user directory even for users who haven't logged in recently. If a user has never verified (only sent code), their record exists but user_hash may be absent — skip those rows.

---

### 8.2 Frontend — Admin Navbar Item

**Navbar change (web/src/components/Navbar.tsx or equivalent):**

- Read `isAdmin` from the Zustand auth store.
- If `isAdmin === true`, render an "Admin" nav item between the regular nav items and the logout button.
- Style: same text weight and size as other nav items, but with a subtle `sa-amber-500` dot indicator to the left (matches the "you have elevated access" convention in developer tools).
- Route: `/admin`

**Auth store update:**

Add `isAdmin: boolean` field. Set it from the `/auth/verify` response. Persist to localStorage under key `sa_is_admin`.

---

### 8.3 Frontend — Admin Page (`/admin`)

Route: `web/src/app/(app)/admin/page.tsx`
Protected: redirect to `/library` if `!isAdmin`.

**Layout:**

```
┌─────────────────────────────────────────────────┐
│  Admin                           [search input] │  header
├─────────────────────────────────────────────────┤
│  Email                  Jobs  Last Job  Status  │
│  ─────────────────────────────────────────────  │
│  user@example.com        12   2h ago   complete │  → [Impersonate]
│  other@example.com        3   5d ago   failed   │  → [Impersonate]
│  ...                                            │
└─────────────────────────────────────────────────┘
```

- Calls `GET /admin/users` on mount; re-queries as the search input changes (debounced 300ms).
- Table columns: Email, Job Count, Last Job (relative time), Last Status (coloured badge matching library card status colours), Impersonate button.
- "Impersonate" button: amber, `controlSize(.small)`. Clicking calls `startImpersonation(user_hash, email)` in the impersonation store (see 8.4).

---

### 8.4 Frontend — Impersonation Mode

**New Zustand store: `impersonation-store.ts`**

```ts
interface ImpersonationState {
  active: boolean
  targetUserHash: string | null
  targetEmail: string | null
  start: (userHash: string, email: string) => void
  stop: () => void
}
```

Persisted to `sessionStorage` only (not localStorage — clears on tab close, prevents accidental lingering).

**`apiFetch()` change (web/src/lib/api.ts):**

When `impersonation.active === true`, append `X-Impersonate-User: {targetUserHash}` to every request header alongside the normal `Authorization: Bearer` header. No other API call sites need to change.

**Impersonation banner:**

A fixed bar at the very top of every `(app)` layout page (above the navbar), shown only when `impersonation.active`:

```
┌───────────────────────────────────────────────────────────┐
│  ⚠ Impersonating user@example.com   [View as themselves]  [Exit Impersonation ×]  │
└───────────────────────────────────────────────────────────┘
```

- Background: `sa-amber-100`, border-bottom `sa-amber-300`, text `sa-amber-800`
- "Exit Impersonation" button calls `impersonation.stop()` and navigates to `/admin`
- After starting impersonation, navigate to `/library` — the library will now show that user's jobs (the API returns results scoped to `target_user_hash` via the header)
- The admin can click into any job and use the full step detail view, including triggering a reprocess, all scoped to the impersonated user

**Flow summary:**

1. Admin logs in → `/admin` menu item appears
2. Admin opens `/admin` → sees user list → clicks "Impersonate" next to a user
3. App navigates to `/library`, impersonation banner appears at top
4. All API calls now include `X-Impersonate-User: {hash}` → backend scopes all data to target user
5. Admin browses jobs, opens step detail, can trigger reprocess to debug issues
6. Admin clicks "Exit Impersonation" → banner disappears, API calls revert to own user_hash

---

### 8.5 Verification Checklist

- [ ] `is_admin: true` returned by `/auth/verify` for admin email; `false` for all others
- [ ] "Admin" nav item only visible when `isAdmin === true`
- [ ] Non-admin user navigating to `/admin` is redirected to `/library`
- [ ] Admin page loads user list from `GET /admin/users`
- [ ] Search input filters users by email prefix (debounced)
- [ ] "Impersonate" button starts impersonation and navigates to `/library`
- [ ] Impersonation banner visible across all pages while active
- [ ] Library shows impersonated user's jobs (not admin's own)
- [ ] Step detail page works for impersonated user's jobs (debug images, reprocess)
- [ ] "Exit Impersonation" clears impersonation state and navigates to `/admin`
- [ ] Non-admin sending `X-Impersonate-User` header is silently ignored
- [ ] Every impersonated API call logged server-side (INFO: `admin=… impersonating user_hash=…`)
- [ ] Impersonation state stored in sessionStorage (cleared on tab close)

---

## Phase 9: Production Hardening

- CloudFront distribution for frontend (S3 static hosting)
- CORS configuration on API Gateway
- Per-user rate limiting (3 concurrent jobs, 50 photos/day)
- CloudWatch dashboards + alarms
- "Delete my data" endpoint
- Provisioned concurrency on critical Lambdas (optional, for cold start mitigation)

---

## Prod Deployment: app.sundayalbum.com

**Prerequisite:** Phases 4–6 complete ✅.

### Prod App Runner Service

- Service name: `sundayalbum-web-prod`
- URL: `https://yjb7t3tngm.us-west-2.awsapprunner.com` (deployed, awaiting custom domain)
- Environment variables: `NEXT_PUBLIC_API_URL=https://e1f6o1ah49.execute-api.us-west-2.amazonaws.com`

### Custom Domain Setup

1. Associate `app.sundayalbum.com` on `sundayalbum-web-prod` App Runner service
2. Add ACM cert CNAME validation record to Route 53 hosted zone
3. Add Route 53 ALIAS record: `app.sundayalbum.com` → prod App Runner domain

### Branch Strategy (for prod releases)

- Feature branches off `web-ui-implementation` → PR to `web-ui-implementation` (deploys to dev, integration test)
- When dev is verified → PR `web-ui-implementation` → `main` (deploys to prod)
- Backend (CDK) deployments remain manual

### Prod CDK Stack

- Stack name: `SundayAlbumStack` (no suffix — existing prod resources)
- API Gateway: `https://e1f6o1ah49.execute-api.us-west-2.amazonaws.com`
- WebSocket: `wss://l7t59cvhyh.execute-api.us-west-2.amazonaws.com/$default`
- S3 bucket: `sundayalbum-data-<account-id>-us-west-2`
