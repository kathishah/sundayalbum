> **DEPRECATED — Historical implementation plan only.**
> This document records the design decisions made during Phase 3 web UI development.
> For the current system design, resource names, and SDLC process, see **`docs/SYSTEM_ARCHITECTURE.md`**.
> For the current CLAUDE instructions, see **`CLAUDE.md`**.

# Sunday Album Web UI — Implementation Plan (Part 2 of 4)
# Phase 3: Real-time Progress + Library UI (dev.sundayalbum.com)

**Version:** 1.5
**Date:** March 2026
**Status:** ✅ PHASE 3 COMPLETE — `dev.sundayalbum.com` live, 3 successful jobs processed, S3 confirmed
**See also:** WEB_UI_PLAN_Part1.md (Phases 0–2: ✅), WEB_UI_PLAN_Part3.md (Phases 4–6: ✅), WEB_UI_PLAN_Part4.md (Phases 7–9: Testing, Admin, Prod)

**Current focus:** Get `dev.sundayalbum.com` fully working end-to-end.
`app.sundayalbum.com` (prod) is deferred to Part 3 / a future phase.

---

## Phase 3: Real-time Progress + Library UI

### Hosting Decision (decided 2026-03-26)

**Choice: AWS App Runner** for the Next.js frontend.

**Options considered:**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Amplify Hosting** | Native Next.js SSR, Git CI/CD, free tier | SSR on Lambda@Edge (cold starts); Amplify Gen1/Gen2 doc confusion; SSR untested in this account — only `caboose` (static HTML/JS) is deployed on Amplify here | Rejected |
| **App Runner** | Already proven in this account (`workorder-invoice` → `veritasa.ai`); Docker-based like pipeline Lambdas; same ECR repo; no cold starts; managed HTTPS | ~$15-20/month minimum; manual CI/CD setup | **Selected** |
| **EC2 + Nginx** | Full control, simple to reason about | Manual OS/cert/PM2 management; single point of failure; `vix-trading-monitor` and `SuperTrendBot` on EC2 are bots, not web frontends — no proven pattern for web | Rejected |
| **CloudFront + S3** | Pennies/month | Requires `output: 'export'`; loses SSR, server components, streaming; wrong for dynamic auth + real-time app | Rejected |

**Why App Runner won:** The `workorder-invoice` app on App Runner is already serving `veritasa.ai` with a custom domain and ACM cert — the exact pattern needed here. No unknowns. The pipeline Lambdas already use ECR, so the Docker build and push workflow is established. Amplify's SSR support is real but untested in this account.

**Environments (decided 2026-03-26):**

Two environments only — dev and prod. No local Docker Compose backend stack.

| Environment | Branch | App URL | API | Purpose |
|-------------|--------|---------|-----|---------|
| **Dev** | `dev` | `dev.sundayalbum.com` | dev API Gateway | Development + testing against real AWS |
| **Prod** | `main` | `app.sundayalbum.com` | prod API Gateway | Live users |

> **Current focus:** Dev environment only. Prod (`app.sundayalbum.com`) is deferred to Part 3.

**Rationale:** Sunday Album is being built for public distribution, not just personal use. Dev needs to run against real AWS services (real DynamoDB, real S3, real Lambda) to catch AWS-specific issues before they reach prod users — the Phase 2 bugs (presigned URL 307 redirects, OCI manifest format) would not have been caught by a local emulator. Docker on the dev Mac is used only to build and test the Next.js container image before pushing to ECR, not to run a local backend stack.

**Local development workflow:**
- `npm run dev` in `web/` → Next.js dev server on `localhost:3000`
- `.env.local` → `NEXT_PUBLIC_API_URL` points at dev API Gateway URL
- Real dev DynamoDB, real dev S3, real dev Lambda — all suffixed `-dev` via CDK `stage` context
- Docker used only for `docker build` + `docker run` to verify the container before pushing

**CDK stage parameterization:**
- Single CDK stack parameterized with `stage` context (default: `prod`)
- `cdk deploy --context stage=dev` → all resources suffixed `-dev` (tables, bucket, Lambdas, state machine)
- `cdk deploy --context stage=prod` → production resources (current naming)
- Each stage is fully isolated: separate S3 bucket, DynamoDB tables, Lambda functions, API Gateway, Step Functions

**Domain setup:**
- `sundayalbum.com` registered on Namecheap (no hosting configured yet)
- Create Route 53 hosted zone for `sundayalbum.com`
- Update Namecheap custom DNS to Route 53 NS records (one-time)
- `app.sundayalbum.com` → prod App Runner service
- `dev.sundayalbum.com` → dev App Runner service (or App Runner default URL is fine for dev)
- Future: `sundayalbum.com` and `www.sundayalbum.com` → public marketing site (separate repo, Phase 6+)

**Infrastructure:**
- Separate ECR repo: `sundayalbum-web` (distinct from CDK pipeline asset repo)
- App Runner service per stage: `sundayalbum-web-prod`, `sundayalbum-web-dev`
- Each service: 0.25 vCPU / 0.5 GB to start, auto-scale to 1 vCPU / 2 GB
- Environment variables per stage: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REGION`, `NEXT_PUBLIC_S3_BUCKET`

**CI/CD (GitHub Actions):**
- Push to `web-ui-implementation` branch → build image → push to ECR → deploy to `sundayalbum-web-dev` (dev App Runner)
- Push to `main` branch → deploy to `sundayalbum-web-prod` (deferred — see Part 3)
- Backend (CDK) deployments remain manual (`cdk deploy`) — infrastructure changes are deliberate, not automatic

### 3.0 CDK Stage Parameterization ✅ COMPLETE

Before any Phase 3 infrastructure is added, the CDK stack must be parameterized so the same code deploys both environments. This is the only change needed from Phase 1/2 — all Lambda handler code (`api/`, `handlers/`) already reads resource names from environment variables injected by CDK, so no application code changes are required.

**What changes:**

`infra/app.py` — read `stage` from CDK context, use it as the stack name suffix:
```python
stage = app.node.try_get_context("stage") or "prod"
SundayAlbumStack(app, f"SundayAlbumStack-{stage}",
    stage=stage,
    env=cdk.Environment(account="<account-id>", region="us-west-2"))
```

`infra/infra/sundayalbum_stack.py` — accept `stage` parameter, suffix all hardcoded resource names:
```python
# stage="prod" → suffix="" (prod resources keep current names for continuity)
# stage="dev"  → suffix="-dev"
suffix = "" if stage == "prod" else f"-{stage}"

bucket_name = f"sundayalbum-data-{self.account}-{self.region}{suffix}"
table_name  = f"sa-sessions{suffix}"
# ... all Lambda function names, role names, state machine name, API name
```

`RemovalPolicy` per stage:
```python
removal_policy = RemovalPolicy.RETAIN if stage == "prod" else RemovalPolicy.DESTROY
```

CfnOutput export names also suffixed so both stacks can coexist in the same account:
```python
export_name=f"SundayAlbumApiUrl-{stage}"
```

**Deployment commands:**
```bash
# Deploy / update prod (current production stack — no resource renames)
cdk deploy --context stage=prod

# Deploy dev stack (new isolated environment)
cdk deploy --context stage=dev

# Tear down dev stack cleanly (DESTROY policy)
cdk destroy --context stage=dev
```

**Post-deploy: populate the Secrets Manager secret** (done once per environment, not per Lambda):
```bash
aws secretsmanager put-secret-value \
  --secret-id sundayalbum/api-keys-dev \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":"sk-proj-..."}'
```
API keys are no longer set as Lambda environment variables — they are stored in Secrets Manager and fetched by `handlers/common.py` at cold start (see Phase 3.1).

**Verification:** two fully isolated stacks visible in CloudFormation console — `SundayAlbumStack-prod` and `SundayAlbumStack-dev`. Each has its own S3 bucket, DynamoDB tables, Lambda functions, API Gateway URL, and Step Functions state machine. A job submitted to the dev API touches only dev resources.

**Files modified in Phase 3.0:**
- `infra/app.py`
- `infra/infra/sundayalbum_stack.py`

---

### 3.1 API Key Management + Usage Rate Limiting ✅ COMPLETE

**Goal:** Store system API credentials securely, enforce per-user daily limits, and let users supply their own keys to lift those limits.

#### Background

The pipeline uses two external AI APIs:
- **Anthropic** (`claude-haiku-4-5`) — orientation correction step, once per photo
- **OpenAI** (`gpt-image-1.5`) — glare removal step, once per photo

Both keys are stored in AWS Secrets Manager (one secret per environment) and fetched by the Lambda handler at cold start. Usage is rate-limited per user for cost control. Users can supply their own keys to lift the limit.

#### Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Secret storage for system keys | AWS Secrets Manager | Auditable, rotatable, IAM-controlled; Lambda env vars are plaintext in console |
| Separate secrets per env | Yes — `sundayalbum/api-keys` (prod), `sundayalbum/api-keys-dev` (dev) | Isolated cost tracking; prod keys can be rotated without touching dev |
| What counts as "1 use" | 1 job (regardless of how many photos it contains) | Users understand "albums processed", not "API calls made" |
| Rate limit window | UTC midnight reset (calendar day) | Simpler to reason about than rolling 24h; matches user expectation of "20 per day" |
| Default daily limit | 20 jobs/user/day | Generous for normal use; cost-controlled at scale |
| Admin users (no limit) | Hardcoded `ADMIN_EMAILS` Lambda env var | Simple; no extra infra; adding new admins is a CDK redeploy (deliberate) |
| System admin email | `<admin-email>` | Identified by email, consistent with existing email auth |
| User-supplied key storage | DynamoDB `sa-user-settings` table + KMS encryption | ~$0 vs ~$0.40/month per user for Secrets Manager; keys encrypted at rest via AWS-owned KMS CMK |
| User key scope | Full replacement — user pays for all their usage | Cleaner UX; no confusion about which key is used for which call |
| Behavior at limit | Job rejected with clear error; frontend shows "Add your own API keys to continue" | AI steps are core to quality; a degraded pipeline (OpenCV fallback) is not the product |

#### 3.1.1 AWS Secrets Manager — System API Keys

Store both keys in a single JSON secret per environment:

```
Secret name (prod): sundayalbum/api-keys
Secret name (dev):  sundayalbum/api-keys-dev

Secret value (JSON):
{
  "ANTHROPIC_API_KEY": "sk-ant-...",
  "OPENAI_API_KEY": "sk-proj-..."
}
```

CDK creates the secret and grants `secretsmanager:GetSecretValue` to the pipeline Lambda IAM role. Lambdas fetch the secret once on cold start and cache it in the module-level scope (re-fetching only on cache miss or rotation).

**CDK changes:**
- Add `secretsmanager.Secret` resource per stage in `sundayalbum_stack.py`
- Grant Lambda execution role `GetSecretValue` on the secret (all Lambdas share the same role)
- Pass `SECRET_ARN` as an env var to **all** Lambdas via `common_env` (not just ai-orient / glare-remove)
- API keys are never stored in Lambda env vars — only the secret ARN reference

**`handlers/common.py` — key resolution and config injection:**
```python
import boto3, json, functools

@functools.lru_cache(maxsize=1)
def _get_system_api_keys() -> dict:
    """Fetch system API keys from Secrets Manager (cached per Lambda instance)."""
    return json.loads(
        boto3.client("secretsmanager").get_secret_value(SecretId=SECRET_ARN)["SecretString"]
    )

def get_anthropic_key(user_keys: dict | None = None) -> str:
    """User-supplied key takes priority; falls back to system key from Secrets Manager."""
    return (user_keys or {}).get("anthropic_api_key") or _get_system_api_keys().get("ANTHROPIC_API_KEY", "")

def get_openai_key(user_keys: dict | None = None) -> str:
    return (user_keys or {}).get("openai_api_key") or _get_system_api_keys().get("OPENAI_API_KEY", "")

def make_config(overrides: dict | None = None, user_keys: dict | None = None) -> PipelineConfig:
    """Build PipelineConfig with resolved API keys injected as explicit fields.

    Pipeline steps are pure functions — they read keys from config, never from
    env vars. make_config() is the single point where key resolution happens.
    """
    cfg = PipelineConfig(
        anthropic_api_key=get_anthropic_key(user_keys),
        openai_api_key=get_openai_key(user_keys),
    )
    for k, v in (overrides or {}).items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg
```

#### 3.1.2 DynamoDB — User Settings Table

New table `sa-user-settings` (suffixed per stage):

```
PK: user_hash (string)

anthropic_api_key: string (encrypted via KMS, optional)
openai_api_key:    string (encrypted via KMS, optional)
created_at:        string (ISO)
updated_at:        string (ISO)
```

No TTL — user settings persist indefinitely. KMS encryption uses the AWS-managed DynamoDB CMK (`aws/dynamodb`) — no extra cost, encryption is transparent.

#### 3.1.3 Daily Usage Tracking

Rate limiting uses the existing `sa-jobs` table — no new table or counter needed. On each `POST /jobs/{jobId}/start`, `_count_jobs_today(user_hash)` queries the jobs table for records with `created_at` beginning with today's UTC date prefix:

```python
DAILY_JOB_LIMIT = 20  # constant in api/common.py

def _count_jobs_today(user_hash: str) -> int:
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resp = jobs_table.query(
        KeyConditionExpression=Key("user_hash").eq(user_hash),
        FilterExpression=Attr("created_at").begins_with(today_prefix),
        Select="COUNT",
        Limit=100,
    )
    return int(resp.get("Count", 0))
```

The check runs only when the user has no user-supplied keys (partial or missing). If the count fails (DynamoDB unavailable), the function returns `0` — rate limiting fails open so users are never incorrectly blocked by an infrastructure issue.

When the limit is exceeded, `POST /jobs/{jobId}/start` returns:
```json
HTTP 429
{
  "error": "rate_limit_exceeded",
  "detail": "You've used all 20 free jobs for today. Add your own API keys in Settings to continue.",
  "jobs_used": 20,
  "limit": 20,
  "resets_at": "2026-03-27T00:00:00Z"
}
```

#### 3.1.4 User API Keys — API Endpoints

New endpoints (added to `api/jobs.py` or new `api/settings.py`):

```
GET  /settings/api-keys   → { has_anthropic_key: bool, has_openai_key: bool }
PUT  /settings/api-keys   { anthropic_api_key?, openai_api_key? } → 200
DELETE /settings/api-keys → 200 (remove user keys, revert to system keys + rate limit)
```

Keys are stored in `sa-user-settings`, never returned to the client (only `has_*` booleans). The `PUT` validates that provided keys are non-empty strings before storing.

#### 3.1.5 Pipeline Key Resolution

When a job starts, `_handle_start()` in `api/jobs.py`:
1. Fetches user-supplied keys from `sa-user-settings` (`_get_user_keys(user_hash)`)
2. Checks rate limit — skipped if user is an admin **or** has both keys supplied
3. Passes `user_keys: { anthropic_api_key, openai_api_key }` into the Step Functions execution input alongside the rest of the job context

All pipeline handlers call `make_config(event.get("config"), user_keys=event.get("user_keys"))`. This single call resolves the final key for each service and injects both into `PipelineConfig` as explicit fields. Steps receive `config` and read `config.anthropic_api_key` / `config.openai_api_key` directly — **no handler ever sets `os.environ` or calls `load_secrets()`**.

```
Step Functions event
  └─ user_keys: { anthropic_api_key, openai_api_key }
       └─ make_config(overrides, user_keys)
            ├─ get_anthropic_key(user_keys) → user key OR Secrets Manager key
            ├─ get_openai_key(user_keys)    → user key OR Secrets Manager key
            └─ PipelineConfig(anthropic_api_key=..., openai_api_key=...)
                 └─ step.run(storage, stem, config)  ← pure function
```

**Rate limit logic:**
- User has **both** keys → skip rate limit check entirely
- User has **partial** keys (e.g., only OpenAI) → rate limit still applies (system key still needed for Anthropic)
- User has **no** keys → rate limit applies; both system keys used

#### 3.1.6 CDK Infrastructure Changes

```python
# New: Secrets Manager secret per stage
api_keys_secret = secretsmanager.Secret(self, "ApiKeysSecret",
    secret_name=f"sundayalbum/api-keys{suffix}",
    description=f"System Anthropic + OpenAI API keys ({stage})",
    removal_policy=removal_policy,
)
api_keys_secret.grant_read(pipeline_role)

# New: user-settings DynamoDB table
user_settings_table = dynamodb.Table(self, "UserSettingsTable",
    table_name=f"sa-user-settings{suffix}",
    partition_key=dynamodb.Attribute(name="user_hash", type=dynamodb.AttributeType.STRING),
    billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
    encryption=dynamodb.TableEncryption.AWS_MANAGED,  # KMS
    removal_policy=removal_policy,
)

# SECRET_ARN added to common_env → all Lambdas (not just ai-orient / glare-remove)
# ADMIN_EMAILS and USER_SETTINGS_TABLE also in common_env → all API Lambdas
common_env = {
    ...,
    "SECRET_ARN": api_keys_secret.secret_arn,
    "USER_SETTINGS_TABLE": user_settings_table.table_name,
    "ADMIN_EMAILS": "<admin-email>",
}

# New API routes
http_api.add_routes(path="/settings/api-keys", methods=[GET, PUT, DELETE], integration=settings_int)
```

#### 3.1.7 Migration: Move Existing Keys into Secrets Manager

One-time: after CDK deploys the secret, populate it:
```bash
aws secretsmanager put-secret-value \
  --secret-id sundayalbum/api-keys \
  --secret-string '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":"sk-proj-..."}'
```

Then remove `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` from Lambda env vars (CDK deploy handles this).

#### 3.1.8 Verification

- System keys fetched from Secrets Manager (not env vars) ✓
- Admin user (`<admin-email>`) can submit unlimited jobs ✓
- Regular user blocked after 20 jobs with 429 + clear error message ✓
- Counter resets at UTC midnight ✓
- User adds own keys via `PUT /settings/api-keys` → rate limit bypassed ✓
- `GET /settings/api-keys` returns `{ has_anthropic_key: true, has_openai_key: false }` (never actual key values) ✓
- `DELETE /settings/api-keys` removes keys; user reverts to system keys + rate limit ✓
- Dev environment uses `sundayalbum/api-keys-dev` secret, never touches prod secret ✓

**Files added/modified:**
- Modified: `infra/infra/sundayalbum_stack.py` — Secrets Manager secret, `sa-user-settings` table, `common_env` updated, `sa-settings` Lambda, new API routes
- Modified: `handlers/common.py` — `_get_system_api_keys()` (Secrets Manager, lru_cache), `get_anthropic_key()`, `get_openai_key()`, `make_config()` now accepts `user_keys` and injects resolved keys into `PipelineConfig`
- Modified: `src/pipeline.py` — `PipelineConfig` gains `anthropic_api_key: str` and `openai_api_key: str` fields
- Modified: `src/steps/ai_orient.py` — removed `load_secrets()` call; reads `config.anthropic_api_key`
- Modified: `src/steps/glare_remove.py` — removed `load_secrets()` call; reads `config.openai_api_key`
- Modified: `src/cli.py` — calls `load_secrets()` once at CLI boundary; populates both `PipelineConfig` key fields
- Modified: `api/common.py` — `USER_SETTINGS_TABLE`, `ADMIN_EMAILS`, `DAILY_JOB_LIMIT`, `user_settings_table`, `is_admin()`, `too_many_requests()`
- Modified: `api/jobs.py` — `_handle_start()` checks rate limit, fetches user keys, passes `user_keys` in execution input
- Modified: `handlers/ai_orient.py` — removed `os.environ` mutation; passes `user_keys` to `make_config()`
- Modified: `handlers/glare_remove.py` — removed `os.environ` mutation; passes `user_keys` to `make_config()`
- New: `api/settings.py` — GET/PUT/DELETE `/settings/api-keys`

---

### 3.2 WebSocket Progress (backend) ✅ COMPLETE

Wire up the DynamoDB Streams → Lambda → WebSocket push path that is already stubbed in `api/websocket.py`:

- Add DynamoDB Stream trigger on `sa-jobs` table → broadcaster Lambda
- Broadcaster queries `sa-ws-connections` GSI `job-index`, pushes step update to all connected clients via `apigatewaymanagementapi`
- Add API Gateway WebSocket API alongside existing HTTP API (separate CDK construct)

Progress message format:
```json
{
  "type": "step_update",
  "jobId": "...",
  "step": "glare_remove",
  "detail": "Photo 2 of 3: glare removal",
  "progress": 0.55
}
```

Frontend fallback: poll `GET /jobs/{jobId}` every 3s if WebSocket is unavailable.

### 3.3 Next.js App Scaffold ✅ COMPLETE

```
web/
  app/
    layout.tsx              # root layout, fonts, providers
    page.tsx                # redirect → /library or /login
    login/page.tsx          # auth flow
    library/page.tsx        # main library view
    library/[jobId]/page.tsx  # step detail (Phase 4)
    settings/page.tsx       # API key management (added for 3.1)
  components/
    AlbumPageCard.tsx       # job card (before → progress → after)
    DropZone.tsx            # drag-drop upload
    ProgressWheel.tsx       # animated step progress
    AuthForm.tsx            # email + code entry
    ApiKeySettings.tsx      # add/remove personal API keys
  lib/
    api.ts                  # typed wrappers around API Gateway endpoints
    store.ts                # Zustand: jobs, auth, WebSocket
    useJobProgress.ts       # WebSocket hook with polling fallback
  Dockerfile                # FROM node:20-alpine, next build + next start
  next.config.ts
  tailwind.config.ts
```

### 3.4 Design System ✅ COMPLETE

Translate from `mac-app/SundayAlbum/Theme/DesignSystem.swift` into Tailwind config:
- Colors: `sa-amber-{50..700}`, `sa-stone-{50..950}`, `sa-success`, `sa-error`
- Fonts: Fraunces (display), DM Sans (body) via `next/font`
- Animations: `sa-standard` (200ms ease), `sa-slide` (350ms ease-out), `sa-reveal` (600ms ease-in-out)

### 3.5 Library Page ✅ COMPLETE

Replicate `mac-app/SundayAlbum/Views/LibraryView.swift`:

- Adaptive grid of `AlbumPageCard` components
- `DropZone` when library is empty (drag-drop + "Choose Files" button)
- Cards show: before thumbnail → animated progress wheel with step label → output thumbnails grid
- Single-click → expanded overlay; double-click → step detail (Phase 5)
- Real-time updates: WebSocket event → Zustand store → card re-renders

> **Note:** Basic library page is functional. Full macOS UI parity (adaptive grid, pie-chart wheel, before thumbnail from debug, debug strip, step tree) is Phase 4 in Part 3.

### 3.6 Auth Pages ✅ COMPLETE

- `/login` — email input → send code → 6-digit code entry → redirect to `/library`
- Session token in `localStorage`; auth guard on `/library` and `/library/[jobId]`

### 3.7 Verification ✅ COMPLETE (2026-03-26)

- `dev.sundayalbum.com` resolves to dev App Runner service ✅
- Login flow works end-to-end (email → code → session) ✅
- Upload HEIC from browser → card enters processing state ✅
- Step labels update in real-time as pipeline runs ✅
- Output thumbnails appear when job completes ✅
- Presigned URLs load correctly in `<img>` tags ✅
- S3 buckets verified: 3 successful job runs confirmed in `sundayalbum-data-*-dev` ✅

### 3.8 App Runner + Domain Setup (dev) ✅ COMPLETE (2026-03-26)

**Dev App Runner service:** `sundayalbum-web-dev` — RUNNING
- URL: `https://kiz3qkgvsb.us-west-2.awsapprunner.com` ✅
- Custom domain: `https://dev.sundayalbum.com` ✅ (ACM cert validated, HTTP 200)
- ECR repo: `<account-id>.dkr.ecr.us-west-2.amazonaws.com/sundayalbum-web`
- GitHub Actions deploys on every push to `web-ui-implementation` ✅

**Route 53 hosted zone:** `sundayalbum.com` (zone ID: `Z0420309YMJDXBAU344P`) ✅
- Namecheap NS records updated to Route 53 NS ✅
- CNAME validation record for ACM cert added ✅
- ALIAS record: `dev.sundayalbum.com` → `sundayalbum-web-dev` App Runner ✅

**Key fix applied:** App Runner overrides the `HOSTNAME` env var at runtime with the container's internal hostname, causing Next.js to bind to a single IP instead of 0.0.0.0. Fixed via `web/entrypoint.sh` that forces `HOSTNAME=0.0.0.0` before `node server.js`. Same pattern used in `workorder-invoice` app.

**Root page blank flash fix:** Converted `web/src/app/page.tsx` from a client component with `useEffect` redirect to a Next.js server component using `redirect('/login')` — eliminates the blank page on first load.

**Prod App Runner (`app.sundayalbum.com`) deferred to Part 3.**

---

## Phase 3 — Final Status

✅ **PHASE 3 COMPLETE** as of 2026-03-26.

All checklist items verified:
- CDK stage parameterization (3.0) ✅
- API key management + rate limiting (3.1) ✅
- WebSocket progress backend (3.2) ✅
- Next.js app scaffold (3.3) ✅
- Design system (3.4) ✅
- Library page (3.5) — functional; full macOS parity is Phase 4 ✅
- Auth pages (3.6) ✅
- Verification (3.7) ✅
- App Runner + domain setup (3.8) ✅

**Next:** Phase 4 — Library UI matching macOS app (see WEB_UI_PLAN_Part3.md)

---
