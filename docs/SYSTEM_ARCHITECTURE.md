# Sunday Album — System Architecture

**Last updated:** 2026-04-10  
**Status:** Current — canonical reference for system design, components, and SDLC.

---

## Table of Contents

1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Image Processing Pipeline](#image-processing-pipeline)
4. [Key Technical Decisions](#key-technical-decisions)
5. [Public Marketing Site](#public-marketing-site)
6. [Web Application (AWS)](#web-application-aws)
7. [macOS App](#macos-app)
8. [SDLC — Branch Strategy & Deployments](#sdlc--branch-strategy--deployments)
9. [API Key Resolution](#api-key-resolution)
10. [Authentication Flow](#authentication-flow)
11. [Live Progress (WebSocket)](#live-progress-websocket)
12. [Domains & DNS](#domains--dns)
13. [Planned / Not Yet Built](#planned--not-yet-built)

---

## Overview

Sunday Album digitizes physical photo album pages. A phone camera photo of one or more glossy
prints goes in; clean, individually corrected digital photos come out.

Three delivery surfaces share one image processing pipeline:

| Surface | Status | Entry point |
|---|---|---|
| **Python CLI** | Production | `python -m src.cli process ...` |
| **macOS app** | Production | `apps/mac/` — SwiftUI shell over Python CLI |
| **Web app** | Production (dev + prod) | Next.js → AWS Lambda pipeline |

The web app also serves a public marketing site (no auth required) at `www.sundayalbum.com`
via the `(public)` Next.js route group. See [Public Marketing Site](#public-marketing-site).

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Client surfaces                                                         │
│                                                                          │
│  ┌──────────────┐   ┌──────────────────────┐   ┌─────────────────────┐ │
│  │  Python CLI  │   │   macOS SwiftUI App  │   │  Next.js Web App    │ │
│  │  (local)     │   │   (Python CLI bridge)│   │  (App Runner)       │ │
│  └──────┬───────┘   └──────────┬───────────┘   └──────────┬──────────┘ │
│         │                      │                           │            │
└─────────┼──────────────────────┼───────────────────────────┼────────────┘
          │                      │                           │
          ▼                      ▼                           ▼
┌──────────────────────┐                        ┌───────────────────────────┐
│  Local filesystem    │                        │  AWS API Gateway (HTTP)   │
│  StorageBackend      │                        │  + WebSocket API          │
└──────────────────────┘                        └───────────────┬───────────┘
                                                                │
                                                                ▼
                                                ┌───────────────────────────┐
                                                │  API Lambda Functions     │
                                                │  sa-auth / sa-jobs /      │
                                                │  sa-settings /            │
                                                │  sa-websocket /           │
                                                │  sa-broadcaster           │
                                                └───────────────┬───────────┘
                                                                │
                                                                ▼
                                                ┌───────────────────────────┐
                                                │  AWS Step Functions       │
                                                │  sa-pipeline state machine│
                                                └───────────────┬───────────┘
                                                                │
                                                    ┌───────────┴───────────┐
                                                    │  Pipeline Lambdas     │
                                                    │  (Docker / ARM64)     │
                                                    │  11 Lambdas, one each │
                                                    └───────────────────────┘
```

---

## Image Processing Pipeline

### Execution model

All pipeline steps live in `packages/pipeline/src/steps/`. Each is a pure function:

```
run(storage: StorageBackend, stem: str, config: PipelineConfig, photo_index?) → dict
```

Steps read inputs from and write outputs to a `StorageBackend` — no hidden state, no env var
reads. The same step code runs unchanged in all three surfaces:

- **CLI / macOS:** `LocalStorage` — reads/writes local filesystem under `debug/` and `output/`
- **Web / Lambda:** `S3Storage` — reads/writes S3 under `{user_hash}/debug/` and `{user_hash}/output/`

API keys are part of `PipelineConfig` (`anthropic_api_key`, `openai_api_key`). They are
injected at the execution boundary — never read from env vars inside steps. See [API Key Resolution](#api-key-resolution).

### Pipeline steps

The pipeline runs sequentially for pre-split steps, then fans out per-photo for Steps 6–9:

```
load → normalize → page_detect → perspective → photo_detect → photo_split
    └─── per photo: ai_orient → glare_remove → geometry → color_restore ───┘
                                                                            ↓
                                                                        finalize
```

| Step | Handler | Status | What it does |
|---|---|---|---|
| `load` | `sa-pipeline-load` | Active | Decode HEIC/JPEG/PNG; apply EXIF orientation |
| `normalize` | `sa-pipeline-normalize` | Active | Resize to working resolution; generate thumbnail |
| `page_detect` | `sa-pipeline-page-detect` | Active | GrabCut segmentation → page boundary quad |
| `perspective` | `sa-pipeline-perspective` | Active | Homographic warp to fronto-parallel view |
| `photo_detect` | `sa-pipeline-photo-detect` | Active | Contour detection of individual photo boundaries |
| `photo_split` | `sa-pipeline-photo-split` | Active | Extract individual photo crops via homography |
| `ai_orient` | `sa-pipeline-ai-orient` | Active | Claude Haiku: detect rotation + get scene description |
| `glare_remove` | `sa-pipeline-glare-remove` | Active (OpenAI default) | OpenAI `gpt-image-1.5` semantic inpainting; OpenCV fallback |
| `geometry` | `sa-pipeline-geometry` | Pass-through | Dewarp + small-angle rotation (both disabled — false positives) |
| `color_restore` | `sa-pipeline-color-restore` | Active | WB → deyellow → adaptive brightness/vibrance → sharpen |
| `finalize` | `sa-pipeline-finalize` | Web only | Collect output keys; update job to `complete` |

For per-step implementation details, tunable params, and debug output: see `docs/PIPELINE_STEPS.md`.

### Resuming from a step (reprocessing)

The web app supports `POST /jobs/{jobId}/reprocess?from_step={step}`. Step Functions uses
Choice states to evaluate `start_from` in the event and route to `Pass` states for skipped steps,
avoiding unnecessary Lambda invocations.

Per-photo steps can be re-run for a single photo via `reprocess_photo_index`.

The CLI supports `--steps load,normalize,...` to run only specific steps.

---

## Key Technical Decisions

### Glare removal: OpenAI by default

OpenAI `gpt-image-1.5` (`images.edit`) is the default glare removal path. It performs semantic,
diffusion-based inpainting with scene understanding — it knows what the photo should look like
and reconstructs it. The scene description from the `ai_orient` step is included in the prompt.

The OpenCV inpainting fallback (`packages/pipeline/src/glare/remover_single.py`) is kept for when the OpenAI key
is absent or `--no-openai-glare` is passed. Quality is significantly worse, especially for
sleeve glare (album pages with plastic covers).

Two glare patterns exist in the test images:
- **Sleeve glare** (three_pics, two_pics): broad flat patches from plastic album sleeves
- **Print glare** (cave, harbor, skydiving): contoured highlights from curved glossy paper

### AI orientation before glare removal

Step 4.5 (`ai_orient`) runs before `glare_remove` for two reasons:
1. `_pick_api_size()` in `remover_openai.py` selects portrait or landscape output dimensions
   based on pixel shape — a sideways photo would request the wrong canvas size.
2. The OpenAI model inpaints more accurately when the image is semantically upright.

One Claude Haiku call per photo returns rotation (0/90/180/270°), flip flag, and scene
description. Combining all three in one call saves latency.

### Hough-line rotation detection: disabled

`_detect_small_rotation()` in `packages/pipeline/src/geometry/rotation.py` finds dominant lines via Hough
transform and computes their median angle as the correction angle. It fires on **image content**
(boat rigging, car bodies, rock edges) rather than the physical photo frame, producing false
corrections on already-correct images. The function returns `0.0` unconditionally.

Correct approach (not yet built): detect the white border of the physical print and use its
angle. The `correct_rotation()` function is the intended home for this.

### Dewarp: disabled

`correct_warp()` in `packages/pipeline/src/geometry/dewarp.py` uses Hough lines to detect curvature. Two problems:
1. iPhone corrects barrel/pincushion distortion in-camera before writing HEIC — nothing to fix.
2. The Hough detector fires on curved content edges (rock walls, curved roads).

`use_dewarp: False` in `PipelineConfig`. Code is kept for potential future use with explicit
distortion calibration data.

### Pipeline steps as pure functions

Every pipeline step is a pure function: given the same `(storage, stem, config)` inputs, it
always produces the same outputs. No step reads from env vars or calls `load_secrets()`.
API keys are part of `config`.

This pattern:
- Makes steps independently testable with any key value (including empty strings for fallback paths)
- Allows any execution context (CLI, macOS, Lambda) to inject keys at its boundary without
  touching step code
- Enables reprocessing from any step — each step can read the previous step's storage output

### Color restoration: replaced CLAHE with adaptive brightness lift (April 2026)

CLAHE (Contrast Limited Adaptive Histogram Equalization) was the original fade restoration
algorithm. It redistributes the luminance histogram across small local tiles. On well-exposed
outdoor photos it pulled highlights down (net darkening) and amplified sensor noise in
smooth-toned regions (sky, water). Replaced with a 3-stage adaptive algorithm:
white-point stretch → shadow lift → vibrance saturation. See `journal/2026-04-09-color-restore-rethink.md`.

### DNG vs HEIC workflow

- **HEIC (24 MP):** Fast, standard iPhone format. Use for all iteration.
- **DNG (48 MP ProRAW):** Maximum data for quality validation. 2× slower to process.
- The pipeline handles both transparently — the loader normalizes to float32 RGB [0, 1].


---

## Public Marketing Site

Served by the same Next.js / App Runner deployment as the authenticated web app — no separate
infrastructure. A Next.js [route group](https://nextjs.org/docs/app/building-your-application/routing/route-groups)
`(public)` owns the marketing routes; the `(app)` group owns all authenticated routes.

### Pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `(public)/page.tsx` | Landing — hero animation, demo sliders, pipeline teaser |
| `/pricing` | `(public)/pricing/page.tsx` | Free Mac app, free web tier, BYOK model |
| `/download` | `(public)/download/page.tsx` | macOS download + web app CTA |
| `/about` | `(public)/about/page.tsx` | Project motivation and contact |
| `/pipeline` | `(public)/pipeline/page.tsx` | Step-by-step pipeline walkthrough with real images; re-run controls for authenticated users |

### Components

| Component | Purpose |
|-----------|---------|
| `MarketingNav` | Top nav — logo, page links, environment-aware "Get started" CTA |
| `MarketingFooter` | Footer with links grouped by category |
| `BeforeAfterSlider` | Draggable reveal slider used on landing page |

### CTA routing

All CTAs use relative paths (`/login`, `/settings`) so the same build works on every hostname
(`www.sundayalbum.com`, `app.sundayalbum.com`, `dev.sundayalbum.com`) without environment flags.

### Demo assets

Static images served from `apps/web/public/demo/`:
- `cave-stage-{0,1,2}.jpg` — hero animation frames (raw → deglared → restored)
- `pair-a-{before,after}.jpg`, `pair-b-*.jpg` — landing page demo sliders
- `pipeline/{01–09}*.jpg` — one image per pipeline step from `IMG_1268.HEIC`

### Pipeline page re-run integration

`/pipeline?jobId={id}` loads the job via `GET /jobs/{id}` and exposes per-step config toggles
and a "Re-run from here" button. Clicking calls `POST /jobs/{id}/reprocess` with
`{ from_step, config }`. This is the same reprocessing API used by the authenticated web app.
Only available when `isAuthenticated()` returns `true` and a valid `jobId` is in the URL.

---

## Web Application (AWS)

### Environments

| Environment | Branch | App Runner | API Gateway |
|---|---|---|---|
| **dev** | `dev` | `sundayalbum-web-dev` → `dev.sundayalbum.com` | `https://nodcooz758.execute-api.us-west-2.amazonaws.com` |
| **prod** | `main` | `sundayalbum-web-prod` → `app.sundayalbum.com` | `https://e1f6o1ah49.execute-api.us-west-2.amazonaws.com` |

WebSocket (prod): `wss://l7t59cvhyh.execute-api.us-west-2.amazonaws.com/$default`

### AWS Resources

**Account:** `680073251743` | **Region:** `us-west-2`

| Resource | Dev name | Prod name |
|---|---|---|
| **S3 bucket** | `sundayalbum-data-680073251743-us-west-2` | same (single bucket, path-separated by `user_hash`) |
| **DynamoDB: jobs** | `sa-jobs-dev` | `sa-jobs` |
| **DynamoDB: sessions** | `sa-sessions-dev` | `sa-sessions` |
| **DynamoDB: WebSocket connections** | `sa-ws-connections-dev` | `sa-ws-connections` |
| **DynamoDB: user settings** | `sa-user-settings-dev` | `sa-user-settings` |
| **Step Functions** | `sa-pipeline-dev` | `sa-pipeline` |
| **ECR (pipeline image)** | `sundayalbum-pipeline-dev` (mutable tags) | `cdk-hnb659fds-container-assets-680073251743-us-west-2` (immutable tags) |
| **Secrets Manager** | `sundayalbum/api-keys-dev` | `sundayalbum/api-keys` |
| **CDK stack** | `SundayAlbumStack-dev` | `SundayAlbumStack` |

### S3 path layout

```
{user_hash}/uploads/{stem}.{ext}                        ← original upload
{user_hash}/debug/{stem}_{NN}_{description}.jpg         ← intermediate debug images + JSONs
{user_hash}/output/SundayAlbum_{stem}_PhotoNN.jpg       ← final output
```

### API Lambda functions (zip-based)

| Lambda | Handler | Purpose |
|---|---|---|
| `sa-auth{suffix}` | `api/auth.py` | Email OTP auth via SES |
| `sa-jobs{suffix}` | `api/jobs.py` | Job CRUD, presigned S3 URLs, trigger Step Functions |
| `sa-websocket{suffix}` | `api/websocket.py` | WebSocket connect/disconnect |
| `sa-settings{suffix}` | `api/settings.py` | Store/retrieve user API keys in DynamoDB |
| `sa-broadcaster{suffix}` | `api/broadcaster.py` | DynamoDB Streams → WebSocket push |

### Pipeline Lambda functions (Docker / ARM64)

Single Dockerfile builds one image; each Lambda gets a different `CMD` override.

| Lambda | RAM | Timeout |
|---|---|---|
| `sa-pipeline-load{suffix}` | 3008 MB | 60s |
| `sa-pipeline-normalize{suffix}` | 3008 MB | 60s |
| `sa-pipeline-page-detect{suffix}` | 3008 MB | 60s |
| `sa-pipeline-perspective{suffix}` | 3008 MB | 60s |
| `sa-pipeline-photo-detect{suffix}` | 3008 MB | 60s |
| `sa-pipeline-photo-split{suffix}` | 3008 MB | 60s |
| `sa-pipeline-ai-orient{suffix}` | 3008 MB | 120s |
| `sa-pipeline-glare-remove{suffix}` | 3008 MB | 300s |
| `sa-pipeline-geometry{suffix}` | 3008 MB | 60s |
| `sa-pipeline-color-restore{suffix}` | 3008 MB | 120s |
| `sa-pipeline-finalize{suffix}` | 1024 MB | 30s |

`{suffix}` is `-dev` for dev, empty for prod.

---

## macOS App

**Location:** `apps/mac/`  
**Technology:** SwiftUI (native macOS, ARM64), Python CLI bridge

The macOS app shells out to `python -m src.cli process ...` — the same CLI used for local
development. No macOS-specific processing code. Processing runs in-process on the user's Mac.

**Key integration points:**
- Drag-drop album page input via `NSOpenPanel` / drop target on the main view
- Spawns Python CLI as a subprocess; reads stdout/stderr for progress
- Step-by-step debug view mirrors the web app's step detail UI (SwiftUI components in `apps/mac/SundayAlbum/Views/`)
- Output export to Photos.app or Finder
- API keys stored in macOS Keychain (not `secrets.json`)

**Design system:** "Warm Archival" — same color tokens and animation timing as the web app
(defined in `apps/mac/SundayAlbum/Theme/DesignSystem.swift`; web equivalent in `apps/web/tailwind.config.ts`).

---

## SDLC — Branch Strategy & Deployments

### Branch model

```
feature/my-change  ──PR──►  dev  ──PR──►  main
                              │              │
                              ▼              ▼
                           dev env        prod env
                      (auto-deploy)    (auto-deploy)
```

- **Feature work:** Branch from `dev` (e.g. `feature/my-change`). Open PR to `dev`.
- **Dev environment:** Every merge to `dev` auto-deploys web + Lambdas.
- **Production release:** PR from `dev` → `main`. Merge triggers prod deploy.
- **CDK / infrastructure changes:** Deployed manually via `cdk deploy` from `services/infra/`. Not automated.

### GitHub Actions workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy-web.yml` | Push to `dev` or `main` (when `apps/web/**` changes) | Build Next.js Docker image → push to ECR → deploy to App Runner |
| `deploy-lambda.yml` | Push to `dev` or `main` (when `services/api/**`, `services/handlers/**`, `packages/pipeline/**` change) | Zip API Lambdas + build/push pipeline Docker image → update all Lambdas |
| `test-api.yml` | Push to any branch (when `services/api/**` or `tests/api\|handlers/**` change) | Run 36 pytest tests (moto, no real AWS) |
| `test-web.yml` | Manual (`workflow_dispatch`) only | Run 12 Playwright E2E tests against `dev.sundayalbum.com` |

**IAM role:** `github-actions-sundayalbum` (OIDC, no long-lived credentials).

### Pre-commit hook

Runs on every `git commit`:
1. `pytest tests/api/ tests/handlers/ -q` — 36 moto-backed tests, ~5s
2. `npx playwright test` from `apps/web/` — 12 Playwright E2E against dev.sundayalbum.com, ~33s
   (skipped if `apps/web/.auth/session.json` doesn't exist)

Install once per clone: `git config core.hooksPath .githooks`  
Skip for a one-off commit: `SKIP_HOOKS=1 git commit -m "wip"`

---

## API Key Resolution

The pipeline uses Anthropic (orientation) and OpenAI (glare removal). Resolution priority:

```
1. User-supplied keys  (DynamoDB sa-user-settings, set via PUT /settings/api-keys)
2. System keys         (AWS Secrets Manager sundayalbum/api-keys{suffix})
3. Empty string        → step falls back: OpenCV for glare, pass-through for orientation
```

Keys are resolved once at the execution boundary:
- **CLI / macOS:** `load_secrets()` in `packages/pipeline/src/utils/secrets.py` reads `secrets.json` (falling back to env vars); injects into `PipelineConfig`
- **Lambda:** `make_config(overrides, user_keys)` in `services/handlers/common.py` fetches system keys from Secrets Manager (cached via `lru_cache`) and merges with user-supplied keys

Pipeline steps never read environment variables or call `load_secrets()` directly.

---

## Authentication Flow

Email-only OTP — no passwords:

1. User enters email → `POST /auth/send-code` → SES sends 6-digit code (10-min TTL)
2. User enters code → `POST /auth/verify` → returns `session_token` (7-day TTL, stored in localStorage)
3. All API calls: `Authorization: Bearer {session_token}`
4. `require_auth()` validates token → returns `user_hash` (SHA-256 of email, used as S3 path prefix)

Rate limits: 3 code sends/email/hour; 5 verify attempts per code.  
Daily job limit: 20 jobs/user/day (bypassed for admins and users with own API keys).

### Transactional email (Amazon SES)

OTP messages are sent with **Amazon SES** in **`us-west-2`**. The **verified domain identity** is **`sundayalbum.com`** (Easy DKIM). The **From** address is **`noreply@sundayalbum.com`**, supplied to Lambda as **`SES_SENDER`** (CDK default `infra/infra/sundayalbum_stack.py`; optional deploy-time override `ses_sender_email` in `infra/cdk.json`).

**DNS:** SPF (apex TXT), DKIM (`*_domainkey` CNAMEs), and a starter **DMARC** (`_dmarc` TXT) live in the same Route 53 zone as the app. One-time setup and AWS CLI commands are recorded in **`journal/2026-04-11-ses-email-deliverability.md`**; the applied Route 53 change batch is **`infra/ses-sundayalbum-dns-changes.json`**.

**Sandbox vs production:** SES may still be in **sandbox** mode until **production access** is approved in the account. Sandbox limits who can receive mail and daily volume; approve production access for unrestricted transactional sending to real users.

---

## Live Progress (WebSocket)

1. DynamoDB Streams monitors `sa-jobs` for step completion writes
2. `sa-broadcaster` Lambda reads the stream → looks up WebSocket connection IDs for the job → sends step update messages
3. Frontend Zustand store receives updates → advances progress wheel without page refresh

Message format: `{ type: "step_update", jobId, step, detail, progress }`

Frontend fallback: polls `GET /jobs/{jobId}` every 3s if WebSocket is unavailable.

---

## Domains & DNS

| Domain | Points to | Status |
|---|---|---|
| `dev.sundayalbum.com` | App Runner `sundayalbum-web-dev` | Active |
| `app.sundayalbum.com` | App Runner `sundayalbum-web-prod` | Active |
| `www.sundayalbum.com` | App Runner `sundayalbum-web-prod` (same as above) | DNS cutover pending |
| `sundayalbum.com` (apex) | Not yet configured | Redirect to `www` not set up |

DNS hosted in Route 53 (`sundayalbum.com` zone ID: `Z0420309YMJDXBAU344P`).
Domain registered on Namecheap; NS records point to Route 53.

---

## Planned / Not Yet Built

- **Phase 8: Admin tools** — user impersonation panel for debugging user jobs. Designed in `docs/archive/WEB_UI_PLAN_Part4.md`; not implemented.
- **Phase 9: Production hardening** — CloudFront distribution, per-user concurrency limits, CloudWatch alarms, "delete my data" endpoint.
- **`www.sundayalbum.com` DNS** — marketing pages are built; Route 53 CNAME to App Runner not yet applied.
- **`sundayalbum.com` apex redirect** — naked-domain redirect to `www` not yet configured.
- **Multi-shot glare compositing** — `packages/pipeline/src/glare/remover_multi.py` exists but is not integrated. Requires multi-angle test images of the same album page.
- **Border-based small-angle rotation** — replacement for the disabled Hough-line rotation detector. Should detect the white border of the physical print to determine frame angle.
