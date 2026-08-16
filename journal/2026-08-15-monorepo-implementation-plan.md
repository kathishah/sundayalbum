# 2026-08-15 — Monorepo Layout Implementation Plan

**Issue:** [#59](https://github.com/kathishah/sundayalbum-claude/issues/59)
**Spec:** `journal/2026-08-15-monorepo-layout.md`
**Branch:** `feature/monorepo-layout` (cut from `dev`)
**Status:** Plan. Implementation comes after review.

---

## Strategy

- One PR to `dev`, multiple commits. Each commit keeps tests/CI green where
  possible.
- No monorepo framework (Turborepo, nx, pnpm workspaces). Folders + path
  updates only.
- Do **not** rename the Python package `src` → `sundayalbum`. That is a
  follow-up issue.
- Reserve `apps/native`, `apps/android`, `apps/windows` conventions in docs,
  but create **no empty folders** in this PR.
- **Prerequisite:** GitHub repo rename `sundayalbum-claude` → `sundayalbum`
  ([#60](https://github.com/kathishah/sundayalbum-claude/issues/60)) completed
  before cutting the refactor branch.

---

## Commit sequence

### C1 — `chore: git-mv into apps/ packages/ services/`

Mechanical moves only. No content changes. Expected: tests/CI red until C2.

```bash
# From repo root
mkdir -p apps packages/pipeline services

git mv web          apps/web
git mv mac-app      apps/mac
git mv src          packages/pipeline/src
git mv api          services/api
git mv handlers     services/handlers
git mv infra        services/infra

git mv requirements.txt         packages/pipeline/
git mv requirements-lambda.txt  packages/pipeline/
git mv requirements-runtime.txt packages/pipeline/
```

**Files deleted from root:** `src/`, `web/`, `mac-app/`, `api/`, `handlers/`,
`infra/`, `requirements*.txt`

**Files added to new locations:** everything above.

**Tests expected:** `pytest tests/api/ tests/handlers/` fails — import paths
broken. Fixed in C2.

---

### C2 — `chore: retarget pyproject, conftest, scripts, gitignore`

Restore local pytest and editable install. Run after C1 in the same PR.

**`pyproject.toml` (root)**

Replace the existing `[tool.setuptools] packages = ["src"]` (line 48–49) with
the find table below. Do not leave both — they conflict.

```toml
[tool.setuptools.packages.find]
where = ["packages/pipeline"]

[project.scripts]
sundayalbum = "src.cli:main"

[tool.pytest.ini_options]
addopts = "--import-mode=importlib"
testpaths = ["tests"]
pythonpath = [
  "packages/pipeline",
  "services",
  "services/api",
]
```

**`tests/conftest.py`** — update `_ROOT` inserts:

```python
_ROOT = Path(__file__).resolve().parent.parent
for _p in [
    str(_ROOT / "packages" / "pipeline"),  # src
    str(_ROOT / "services"),               # handlers
    str(_ROOT / "services" / "api"),       # api modules (flat)
    str(_ROOT / "tests" / "api"),
    str(_ROOT / "tests" / "handlers"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
```

**`scripts/sunday`** — add `PYTHONPATH` fallback (optional if editable install
works):

```bash
export PYTHONPATH="${PROJECT_ROOT}/packages/pipeline:${PYTHONPATH:-}"
```

**`scripts/generate-assets.py`** — replace any `mac-app/` output paths with
`apps/mac/`.

**`.gitignore`** — update ignored paths:

```
apps/mac/.build/
apps/mac/SundayAlbum.xcodeproj/project.xcworkspace/
apps/mac/SundayAlbum.xcodeproj/xcuserdata/
apps/mac/SundayAlbum/BuildInfo.swift
apps/web/tsconfig.tsbuildinfo
```

**Verify:** `pip install -e ".[dev]" && pytest tests/api/ tests/handlers/ -q`
→ 40 passed.

---

### C3 — `chore: update Docker, CDK image context, GHA paths`

Production-facing path changes. Docker build, Lambda deploys, and CI must all
point at the new locations.

**Root `Dockerfile`**

```dockerfile
COPY packages/pipeline/requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt

COPY packages/pipeline/src/ ${LAMBDA_TASK_ROOT}/src/
COPY services/handlers/     ${LAMBDA_TASK_ROOT}/handlers/
```

**Root `.dockerignore`** — update exclusions:

```
apps/web/
apps/mac/
services/infra/
```

**`services/infra/infra/sundayalbum_stack.py`**

```python
# API zip asset — unchanged because both are now under services/
lambda_code = lambda_.Code.from_asset("../api")   # still correct

# Pipeline Docker image context — was "../" (infra/.. == repo root)
# Now from services/infra/ root is two levels up:
code=lambda_.DockerImageCode.from_image_asset(
    "../../",
    cmd=[handler],
    platform=ecr_assets.Platform.LINUX_ARM64,
)
```

**`.github/workflows/deploy-lambda.yml`**

- Path filters:
  - `api/**` → `services/api/**`
  - `handlers/**` → `services/handlers/**`
  - `src/**` → `packages/pipeline/**`
  - `requirements-lambda.txt` → `packages/pipeline/requirements-lambda.txt`
- Zip step: `cd api` → `cd services/api`
- Docker build still runs from repo root (unchanged)

**`.github/workflows/deploy-web.yml`**

- Path filters: `web/**` → `apps/web/**`
- `working-directory: web` → `apps/web`

**`.github/workflows/test-api.yml`**

- Path filters: update to new paths
- `PYTHONPATH: ${{ github.workspace }}` still works (repo root has
  `packages/pipeline` and `services` on the path via conftest)

**`.github/workflows/test-web.yml`**

- `working-directory: web` → `apps/web`
- `cache-dependency-path: web/package-lock.json` → `apps/web/package-lock.json`
- Artifact path: `web/playwright-report/` → `apps/web/playwright-report/`

**.githooks/pre-commit**

- `SESSION_FILE="$REPO_ROOT/web/.auth/session-dev.json"` → `apps/web/.auth/…`
- `PLAYWRIGHT_BIN="$REPO_ROOT/web/node_modules/.bin/playwright"` →
  `apps/web/node_modules/.bin/playwright`
- `cd "$REPO_ROOT/web"` → `apps/web`

**Verify:**
- `docker build --platform linux/arm64 -t sa-pipeline:check .` (no push)
- `cd services/infra && cdk synth` (no deploy)

---

### C4 — `fix(mac): set PYTHONPATH to packages/pipeline in dev`

Keep macOS dev launch working. CWD stays repo root; add `PYTHONPATH` for the
moved `src` package.

**`apps/mac/SundayAlbum/Bridge/RuntimeManager.swift`**

```swift
/// Extra `PYTHONPATH` to inject in production so the bundled `src/` is importable.
/// Returns `nil` in dev (CWD already covers it).
/// Returns the packages/pipeline path in dev so `src` resolves.
var extraPythonPath: String? {
    if let devRoot = Self.devProjectRoot {
        return devRoot.appendingPathComponent("packages/pipeline").path
    }
    return Bundle.main.resourceURL?.path
}
```

**`apps/mac/project.yml`** — update resource paths (from `apps/mac/..`):

```yaml
- path: ../../scripts/setup-runtime.sh
- path: ../../packages/pipeline/requirements-runtime.txt
- path: ../../packages/pipeline/src
  type: folder
```

**`apps/mac/scripts/sunday`** wrapper (if it exists) — add same `PYTHONPATH`
export.

**Verify:**
- `cd apps/mac && xcodebuild test -scheme SundayAlbum -destination 'platform=macOS' -skip-testing:SundayAlbumUITests` → 45 passed
- Xcode Debug run: `python -m src.cli process …` still works, finds `.venv`

---

### C5 — `docs: update paths for monorepo layout`

Documentation-only. No behavior change.

**`CLAUDE.md`** — project structure tree, CLI usage (command unchanged).

**`docs/CONTRIBUTING.md`** — paths; drop the stale `should_skip()` note in "How
to Add a Pipeline Step" (handlers no longer call it after 2026-04-13 SFN
refactor).

**`docs/SYSTEM_ARCHITECTURE.md`** — `mac-app/` → `apps/mac`, `web/` → `apps/web`,
`src/steps` → `packages/pipeline/src/steps`.

**`docs/PIPELINE_STEPS.md`** — file paths.

**`docs/README.md`** — if it cites old folders.

**`README.md`** — still Phase-1 tree; refresh or replace with pointer to
`CLAUDE.md`.

**Do NOT rewrite:** `journal/**` historical entries.

---

## Verification checklist (must all pass on `dev` before `dev` → `main` PR)

| # | Check | Command |
|---|---|---|
| 1 | Directory tree matches spec | `tree -L 2 -I 'node_modules|.git|.venv|debug|output|uploads|logs'` |
| 2 | API + handler tests | `pytest tests/api/ tests/handlers/ -q` → 40 passed |
| 3 | CLI smoke run | `python -m src.cli process test-images/IMG_three_pics_normal.HEIC --output ./output/ --steps load,normalize,page_detect` |
| 4 | SFN routing unit tests | `cd services/infra && .venv/bin/pytest tests/unit/test_sfn_routing.py -q` → 45 passed |
| 5 | Pipeline Docker build | `docker build --platform linux/arm64 -t sa-pipeline:check .` |
| 6 | macOS unit tests | `cd apps/mac && xcodebuild test -scheme SundayAlbum -destination 'platform=macOS' -skip-testing:SundayAlbumUITests` |
| 7 | Web build / typecheck | `cd apps/web && npm ci && npm run build` (or `npm run typecheck` if added) |
| 8 | Pre-commit hook points at `apps/web` | Check `.githooks/pre-commit` paths |
| 9 | Merge to `dev` triggers both deploy workflows | Push to `dev`, watch GHA |
| 10 | Manual smoke on `dev.sundayalbum.com` | One job including reprocess from `page_detect` |

---

## Risk mitigations (from spec)

| Risk | Mitigation in this plan |
|---|---|
| GHA path filters miss new trees | C3 updates every filter; verify first `dev` push runs both deploy workflows |
| CDK image context wrong | Only needed if `cdk deploy` run; `cdk synth` validates. GHA builds independently from repo root. |
| macOS prod bundle misses `src/` | `project.yml` path `../../packages/pipeline/src` verified by checking `Contents/Resources/src` in built .app |
| `PYTHONPATH` forgotten in dev | C4 adds `extraPythonPath` for dev; Xcode run validates |
| `conftest.py` adds `services` not `services/api` | C2 inserts `services/api` explicitly |
| Tauri/Android/Windows migration mixed in | D9 + non-goals explicitly forbid; reserved folder names documented but not created |

---

## Branch mechanics

```bash
# Prerequisite: #60 (repo rename) completed
# Prerequisite: #58 (build-release.sh changes) committed or stashed — see Out-of-band note
git checkout dev
git checkout -b feature/monorepo-layout
# C1–C5 as separate commits in this branch
git push origin feature/monorepo-layout
# Open PR to dev
# Run local/manual checks before PR:
#   - pytest tests/api/ tests/handlers/
#   - docker build (pipeline image)
#   - macOS unit tests
#   - apps/web build/typecheck
# Deploy workflows (deploy-lambda.yml, deploy-web.yml) run ONLY after merge to dev.
# test-api.yml runs on push; test-web.yml is manual-only.
# Verify on dev.sundayalbum.com after merge
# Merge to dev
# Later: PR dev → main
```

Do not force-push `dev`. Do not rewrite history.

---

## What is explicitly **not** in this plan

- Renaming Python package `src` → `sundayalbum`
- Nested `packages/pipeline/pyproject.toml`
- Turborepo / nx / pnpm workspaces / uv workspaces
- Tauri evaluation, Windows/Android deliverables
- `apps/native/`, `apps/android/`, `apps/windows/` empty folders
- #56 rate-limit countdown, #57 video, #58 notarized Mac download

These are separate issues / follow-ups.

---

## Commit message template

```
<type>: <summary>

<optional body>

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
```

Types: `chore` (C1–C3), `fix` (C4), `docs` (C5).

---

## Out-of-band note

The uncommitted `mac-app/build-release.sh` (version bump + GitHub Release) is
tracked in #58. **Before C1**, either commit it on a separate branch, stash it,
or revert it — otherwise `git mv mac-app apps/mac` will carry the #58 changes
into the monorepo PR. This plan does not modify it; it should land in a
separate PR after the monorepo move.