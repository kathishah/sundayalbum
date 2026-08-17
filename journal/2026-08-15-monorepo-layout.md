# 2026-08-15 — Monorepo Layout Spec

**Issue:** [#59](https://github.com/kathishah/sundayalbum-claude/issues/59)
**Branch:** not yet cut — spec only
**Status:** Spec. Implementation plan and code come later.

---

## Problem

The repo grew from a Python CLI into three delivery surfaces plus AWS infrastructure,
but the directory layout is still a flat Phase-1 scaffold. Everything that later
became an "app" or a "service" lives at the repository root:

```
sundayalbum-claude/
├── src/            # Python pipeline (shared engine)
├── api/            # AWS API Lambda handlers
├── handlers/       # AWS pipeline Lambda wrappers
├── infra/          # AWS CDK stack
├── web/            # Next.js frontend + marketing site
├── mac-app/        # SwiftUI macOS app
├── tests/          # Python tests spanning pipeline + api + handlers
├── docs/ journal/ scripts/
├── Dockerfile      # pipeline Lambda image (copies src/ + handlers/)
└── pyproject.toml  # single Python package: sundayalbum
```

This is already a multi-surface system. The layout does not say so.

**Consequences:**
- New contributors cannot tell which directories are products, which are shared
  libraries, and which are deployable services.
- Path filters in CI (`.github/workflows/deploy-*.yml`) and docs (`CLAUDE.md`,
  `docs/CONTRIBUTING.md`) have to enumerate a growing list of root folders.
- Adding another surface (e.g. an Android app, Windows desktop app, or second
  Python package) would add yet another root directory.
- `README.md` still describes the Phase-1 CLI-only tree.

This is a layout problem, not a tooling problem. There is one Next.js app, one
Swift app, one Python engine. A JS monorepo tool (pnpm / turbo / nx) would add
machinery without a second JS package to share.

---

## Goal

Rearrange the repository so that:

1. Each **application** lives under `apps/`.
2. Each **deployable backend unit** lives under `services/`.
3. The **shared image-processing engine** lives under `packages/`.
4. Root stays for workspace config, docs, tests, and runtime artifacts.

No pipeline, API, or UI behavior changes. After the move, the same CLI command,
the same Lambda handler names, and the same Step Functions state machine must
work.

---

## Non-goals

- Renaming the Python package `src` → `sundayalbum`. Import paths
  (`from src.steps…`, `python -m src.cli`, `CMD ["handlers.load.handler"]`)
  stay as they are. A rename is a follow-up issue.
- Renaming the GitHub repository `sundayalbum-claude` → `sundayalbum`.
  Tracked separately as [#60](https://github.com/kathishah/sundayalbum-claude/issues/60).
  This is a **prerequisite** for the monorepo refactor; do it before cutting the
  refactor branch.
- Introducing nx, turbo, pnpm workspaces, uv workspaces, or a second package
  manager.
- Introducing Tauri, replacing the SwiftUI macOS app, or adding Android /
  Windows desktop deliverables. The layout should leave room for those, but
  they are product/platform migrations and belong in follow-up issues.
- Splitting `tests/` into per-app folders. Tests already span pipeline + API +
  handlers and should stay at the repo root.
- Changing Step Functions ASL, Lambda function names, S3 layout, or CDK resource
  names.
- Shipping the uncommitted `mac-app/build-release.sh` GitHub-release work
  (tracked separately as #58).
- Rewriting historical journal entries to match new paths.

---

## Current couplings (must survive the move)

These are the hard constraints. Any target layout that breaks one of them
without an explicit migration step is wrong.

### 1. Pipeline package name is `src`

Every surface imports the engine as `src`:

| Caller | How |
|---|---|
| CLI / scripts | `python -m src.cli` (`scripts/sunday`, `pyproject.toml` `[project.scripts]`) |
| Lambda handlers | `import src.steps.<step> as step`; `from src.pipeline import PipelineConfig` |
| Pipeline Dockerfile | `COPY src/ ${LAMBDA_TASK_ROOT}/src/` then `CMD ["handlers.load.handler"]` |
| macOS app (dev) | CWD = repo root, `python -m src.cli` |
| macOS app (prod) | `src/` copied into `Contents/Resources/`; `PYTHONPATH` set to that folder |
| pytest | `from src.preprocessing.loader import …`, etc. |

Keeping the on-disk folder named `src` *inside* `packages/pipeline/` preserves
all of these.

### 2. Handlers import `src`; they are not a subpackage of `src`

`handlers/*.py` are thin Lambda wrappers. They live next to `src/` today so both
can be copied into the same Lambda image with no install step. After the move
they still need to be siblings **inside the Docker image**, even if they live
in different repo folders.

### 3. API Lambdas are a flat zip of `api/`

`deploy-lambda.yml` does `cd api && zip -r ../api.zip .`. CDK does
`lambda_.Code.from_asset("../api")`. Handler strings are `auth.handler`,
`jobs.handler` — not `api.auth.handler`. `tests/conftest.py` puts `api/` itself
on `sys.path` for that reason. The zip root must remain the contents of `api/`,
not a parent folder.

### 4. macOS RuntimeManager treats repo root as project root

`RuntimeManager.devProjectRoot` walks up from the Xcode bundle until it finds
`.venv/`. `cliWorkingDirectory` is that root (so `test-images/`, `debug/`,
`output/`, `secrets.json` resolve). `pythonURL` is `{root}/.venv/bin/python`.

Implication: `.venv/` **stays at the repository root**. Moving it under
`packages/pipeline/` would break the walk-up heuristic and every dev-mode
launch from Xcode.

In production the app copies `../src`, `../scripts/setup-runtime.sh`, and
`../requirements-runtime.txt` into the bundle (`mac-app/project.yml`). Those
relative paths change; the in-bundle layout (`Contents/Resources/src/`) does
not.

### 5. CDK image asset is built from the repo root

```python
lambda_.DockerImageCode.from_image_asset(
    "../",   # infra/.. == repo root
    cmd=[handler],
    platform=ecr_assets.Platform.LINUX_ARM64,
)
```

The root `Dockerfile` + `.dockerignore` are the build context. After the move
the context must still be the **repository root** so one `COPY` can reach both
`packages/pipeline/src/` and `services/handlers/`.

The API zip asset is `from_asset("../api")` relative to `infra/`. If `infra/`
and `api/` become siblings under `services/`, that relative path is unchanged.

### 6. Web Docker build is self-contained

`deploy-web.yml` builds with `working-directory: web`. `web/Dockerfile` only
copies the Next.js tree. The web app has **no compile-time dependency** on
`src/` or `handlers/`. Moving `web/` is a path-filter and `working-directory`
change only.

### 7. Tests span three trees via `PYTHONPATH`

`tests/conftest.py` inserts:

```
repo root          → handlers/, src/
repo root / api    → auth, jobs, settings, …  (flat)
tests/api
tests/handlers
```

Algorithm tests (`tests/test_loader.py`, `test_photo_detection.py`, …) import
`src.*`. Handler tests import `handlers.*`. API tests import the flat `api`
modules. After the move, `pythonpath` / `sys.path` must be updated so **no
test file has to change its imports**.

### 8. Day-to-day Lambda deploys do not go through CDK

Merges to `dev` / `main` run `deploy-lambda.yml`, which zips `api/` and
`docker build`s the root `Dockerfile`, then `aws lambda update-function-code`.
CDK (`cdk deploy` from `infra/`) is manual and is how the state machine and
function *definitions* were last published. The monorepo move must keep GHA
working; a CDK deploy is only required if the image-asset *directory* recorded
in the stack needs to change.

---

## Target layout

```
sundayalbum-claude/
├── apps/
│   ├── web/                      # was web/
│   └── mac/                      # was mac-app/; current SwiftUI macOS app
├── packages/
│   └── pipeline/                 # shared image-processing engine
│       ├── src/                  # still the Python package named `src`
│       ├── requirements.txt
│       ├── requirements-lambda.txt
│       └── requirements-runtime.txt
├── services/
│   ├── api/                      # was api/          — zip Lambda source
│   ├── handlers/                 # was handlers/     — container Lambda wrappers
│   └── infra/                    # was infra/        — AWS CDK
├── tests/                        # unchanged location; spans all three trees
│   ├── api/
│   ├── handlers/
│   ├── test_loader.py
│   └── …
├── docs/
├── journal/
├── scripts/                      # sunday, setup-runtime.sh, fetch-test-images.sh
├── test-images/                  # gitignored
├── Dockerfile                    # pipeline Lambda; context = repo root
├── .dockerignore
├── .github/
├── .githooks/
├── pyproject.toml                # workspace: setuptools + pytest/ruff/mypy
├── CLAUDE.md
├── README.md
└── .venv/                        # stays at root
```

Runtime / gitignored dirs (`debug/`, `output/`, `uploads/`, `logs/`,
`secrets.json`) stay at the root. CLI relative paths (`--output ./output/`,
`--debug`) keep working when CWD is the repo root.

### Why these three top-level buckets

| Bucket | Rule of thumb | Today |
|---|---|---|
| `apps/` | Something a human launches | Next.js, macOS; future Android / Windows |
| `packages/` | Imported by more than one surface, not deployed alone | pipeline (`src`) |
| `services/` | Deployed to AWS, not a user-facing app | api, handlers, infra |

CLI is **not** a separate app folder. It is the `__main__` of
`packages/pipeline` (`python -m src.cli`). The macOS app shells out to that
same entry point; inventing `apps/cli/` would imply a second product.

`handlers/` is a service, not a package: nothing except Lambda and handler
tests imports it. It stays next to `api/` under `services/`.

### Future native apps

The layout should support Android and Windows desktop without changing the
Issue #59 move:

```
apps/
├── web/             # current Next.js app
├── mac/             # current SwiftUI macOS app
├── native/          # future cross-platform shell, if Tauri/Flutter/etc. wins
├── android/         # future Android-native app, if not covered by apps/native
└── windows/         # future Windows-native desktop app, if not covered by apps/native
```

Do not create empty future folders in this PR. Add one when there is real code
and a platform decision.

If Tauri is chosen later, use `apps/native/` for the Tauri project, matching the
Multifactor convention. Keep `apps/mac/` until the Tauri app reaches feature
parity, then remove or archive the SwiftUI app in that separate migration.

Shared client code that appears during that migration should go under
`packages/` only when at least two apps import it. Likely examples are
`packages/api-client`, `packages/ui`, or `packages/native-bridge`. Do not add a
JS workspace manager until such shared JS/TS packages exist.

---

## Design decisions

### D1 — Folders only; no monorepo framework

One JS app, one Python package, one Swift app. Path updates in CI, Docker,
CDK, and docs are sufficient. Revisit only if a second JS package or a second
Python library appears.

Future Android and Windows targets do not change this decision by themselves.
They change it only if they introduce shared JS/TS packages, shared native
bridge code, or a cross-platform app that benefits from workspace orchestration.

### D2 — Keep the Python package name `src`

Renaming to `sundayalbum` is the right long-term name, but it touches every
handler, every pipeline test, the macOS subprocess argv, `scripts/sunday`,
the Docker `COPY` + Lambda `CMD`, and `pyproject.toml` scripts. Doing it in
the same PR as the directory move mixes two failure modes.

Follow-up (not this spec): `feat: rename src package to sundayalbum`.

### D3 — No compatibility shims at the old paths

Do not leave `src/` → `packages/pipeline/src/` symlinks, or a stub `web/` that
re-exports `apps/web`. One `git mv`, every caller updated in the same change.
Shims would let stale CI path filters and docs linger.

### D4 — Root `.venv` and root `tests/` stay

`.venv` location is part of the macOS dev-mode contract (see coupling 4).
`tests/` already is the workspace test suite; moving it under `packages/` or
splitting it would force import and CI churn with no isolation benefit.

### D5 — Root `Dockerfile` stays at the root

The pipeline image must `COPY` from both `packages/pipeline/src/` and
`services/handlers/`. A Dockerfile inside `packages/pipeline/` cannot reach
`services/handlers/` without a parent context, which is the same as keeping
the file at the root. CDK `from_image_asset` continues to point at the
repository root (the relative path from `services/infra/` becomes `../../`
instead of `../`).

### D6 — Dev-mode macOS sets `PYTHONPATH`; CWD stays repo root

After the move, `src/` is no longer at `{repo}/src`. Two options:

1. Set `PYTHONPATH={repo}/packages/pipeline` in dev (and keep CWD = repo root).
2. Change CWD to `packages/pipeline`.

(1) is required. (2) breaks `test-images/`, `--output ./output/`, `--debug`
(writes `debug/`), and `SecretsLoader(projectRoot:)` which reads
`{cwd}/secrets.json`.

Production is unchanged: the bundle still contains a top-level `src/` folder
inside `Contents/Resources/`.

### D7 — Editable install remains `pip install -e ".[dev]"` from the repo root

Root `pyproject.toml` tells setuptools to find packages under
`packages/pipeline`. Optional later: a nested `packages/pipeline/pyproject.toml`.
Not required to satisfy this spec.

### D8 — API modules stay flat inside the zip

`services/api/` is zipped as `.` (contents, not the parent). Handler names
`auth.handler` / `jobs.handler` do not change. `tests/conftest.py` adds
`services/api` to `sys.path`, not `services`.

### D9 — Keep `apps/mac`, reserve `apps/native` for later Tauri

`apps/mac` is intentionally named for the current implementation: a SwiftUI
macOS app with XcodeGen, Photos.framework, and a bundled Python runtime. Calling
it `apps/native` now would imply a cross-platform native shell that does not
exist yet.

If Windows desktop and Android become concrete product targets, evaluate Tauri
then. A Tauri app can live at `apps/native` and can reuse `apps/web` output or
shared packages if that is the selected architecture. That work should not be
combined with this path-only monorepo move.

---

## Path map

| Current | New |
|---|---|
| `src/` | `packages/pipeline/src/` |
| `requirements.txt` | `packages/pipeline/requirements.txt` |
| `requirements-lambda.txt` | `packages/pipeline/requirements-lambda.txt` |
| `requirements-runtime.txt` | `packages/pipeline/requirements-runtime.txt` |
| `web/` | `apps/web/` |
| `mac-app/` | `apps/mac/` |
| future cross-platform native app | `apps/native/` (not created in this PR) |
| future Android-native app | `apps/android/` (not created in this PR) |
| future Windows-native app | `apps/windows/` (not created in this PR) |
| `api/` | `services/api/` |
| `handlers/` | `services/handlers/` |
| `infra/` | `services/infra/` |
| `tests/` | `tests/` (unchanged) |
| `Dockerfile` | `Dockerfile` (unchanged location; COPY paths change) |
| `scripts/` | `scripts/` (unchanged) |
| `docs/` `journal/` | unchanged |
| `.venv/` | unchanged |

Python import strings that do **not** change:

```
src.cli
src.pipeline
src.steps.*
src.preprocessing.*
src.storage.*
handlers.load.handler
handlers.common.skip_this_photo
auth.handler
jobs.handler
```

---

## Surfaces after the move

Unchanged architecture, new paths:

```
CLI (local)                    macOS app                      Web app (AWS)
python -m src.cli              apps/mac → CLI                 apps/web → Lambda
        │                            │                                │
        └────────────────────────────┴────────────────────────────────┘
                    packages/pipeline/src/steps/*.py
                    same PipelineConfig
                    LocalStorage vs S3Storage
```

AWS deployables:

```
services/api        → zip  → sa-auth / sa-jobs / sa-settings / sa-websocket / sa-broadcaster
services/handlers
  + packages/pipeline/src
  + root Dockerfile → image → sa-pipeline-*
services/infra      → cdk deploy (manual)
```

---

## Files that must be updated (inventory)

These are the known callers. The implementation plan should treat this as a
checklist, not as optional cleanup.

### Packaging and tests
- `pyproject.toml` — `packages.find.where`, `pythonpath`, `[project.scripts]`
- `tests/conftest.py` — `sys.path` inserts
- `scripts/sunday` — `PYTHONPATH` (or rely on the editable install)
- `scripts/generate-assets.py` — `mac-app/` output paths become `apps/mac/`
- `.gitignore` — `mac-app/` → `apps/mac/`, `web/` → `apps/web/`

### Docker / CDK / CI
- `Dockerfile` — `COPY` sources and `packages/pipeline/requirements-lambda.txt`
- `.dockerignore` — exclude `apps/web`, `apps/mac`, `services/infra`
- `services/infra/infra/sundayalbum_stack.py` — image asset `../` → `../../`;
  API asset `../api` stays valid if both live under `services/`
- `.github/workflows/deploy-lambda.yml` — path filters, `cd api`, requirements path
- `.github/workflows/deploy-web.yml` — path filters, `working-directory`
- `.github/workflows/test-api.yml` — path filters, `PYTHONPATH`
- `.github/workflows/test-web.yml` — `working-directory`, cache path, artifact path
- `.githooks/pre-commit` — `web/` → `apps/web/`

### macOS
- `apps/mac/project.yml` — resource paths to `src/`, `setup-runtime.sh`,
  `requirements-runtime.txt`
- `apps/mac/SundayAlbum/Bridge/RuntimeManager.swift` — `extraPythonPath` in dev
- `apps/mac/SundayAlbum/Bridge/PipelineRunner.swift` — only if argv or CWD
  assumptions change (they should not)

### Docs (paths only; do not rewrite journal history)
- `CLAUDE.md` — project structure tree
- `docs/CONTRIBUTING.md` — paths; also the stale `should_skip()` note in
  "How to Add a Pipeline Step" (handlers no longer call it after the 2026-04-13
  SFN skip-routing change)
- `docs/SYSTEM_ARCHITECTURE.md` — `mac-app/` → `apps/mac`, `web/` → `apps/web`,
  `src/steps` → `packages/pipeline/src/steps`
- `docs/PIPELINE_STEPS.md` — file paths
- `docs/README.md` — if it cites old folders
- `README.md` — still the Phase-1 tree; refresh or point at `CLAUDE.md`

### Leave alone
- `journal/**` historical entries
- Lambda function names, Step Functions definition, S3 key layout
- `src.cli` / `handlers.*.handler` / `auth.handler` strings

---

## Acceptance criteria

The spec is satisfied when all of the following are true on `dev` (and then
`main`):

1. Directory tree matches **Target layout**. No leftover `src/`, `web/`,
   `mac-app/`, `api/`, `handlers/`, or `infra/` at the repo root (other than
   gitignored runtime dirs).
2. `pytest tests/api/ tests/handlers/` — 40 passed. No test file import
   rewrites required.
3. `python -m src.cli process test-images/IMG_three_pics_normal.HEIC --output ./output/ --steps load,normalize,page_detect` succeeds from the repo root.
4. `cd services/infra && … pytest tests/unit/test_sfn_routing.py` — 45 passed.
5. `docker build` of the root pipeline Dockerfile succeeds (including
   `packages/pipeline/requirements-lambda.txt`; no need to push for local
   sign-off).
6. macOS unit tests pass (`xcodebuild test … -skip-testing:SundayAlbumUITests`).
   Dev launch from Xcode still finds `.venv` and runs the CLI.
7. `cd apps/web && npm ci` + either `npm run build` or a newly added
   `npm run typecheck` succeeds. Playwright path in the pre-commit hook points
   at `apps/web`.
8. Merge to `dev` triggers `deploy-lambda.yml` and `deploy-web.yml` against
   the **dev** environment. One manual smoke job on `dev.sundayalbum.com`
   (including reprocess from `page_detect`) succeeds before a `dev` → `main` PR.

---

## Risks

| Risk | Why | Mitigation |
|---|---|---|
| GHA path filters miss the new trees | Workflows would silently stop deploying | Update filters in the same PR as `git mv`; verify the first `dev` push actually runs both deploy workflows |
| CDK image context `../../` is wrong | `cdk deploy` (manual) would bake a broken image | Only needed if someone runs CDK; GHA builds from repo root independently. Confirm with `cdk synth` |
| macOS prod bundle misses `src/` | `project.yml` relative path off by one | Resource path becomes `../../packages/pipeline/src`; verify the copied folder still appears as `src` in `Contents/Resources/` |
| `PYTHONPATH` forgotten in dev | Xcode launch: `No module named src` | Set `extraPythonPath` for both dev and prod (D6) |
| `conftest.py` puts `services` on `sys.path` instead of `services/api` | API tests import `auth` / `jobs` as top-level modules | Insert `services/api`, not `services` |
| Future native plans distort this move | Tauri/Android/Windows migration would mix layout churn with a new app runtime | Reserve `apps/native`, `apps/android`, and `apps/windows` conventions, but create no empty folders and ship no platform rewrite in this PR |
| Partial merge (dirs moved, CI not updated) | `dev` auto-deploy would update nothing or fail | Single PR; do not land the `git mv` alone |

---

## Branching and sequencing

- Cut `feature/monorepo-layout` from `dev`.
- One PR to `dev`. Several commits inside the PR are fine (move → packaging →
  CI/Docker/CDK → macOS → docs) so bisect stays useful.
- Verify on `dev.sundayalbum.com` before opening `dev` → `main`.
- Do not force-push `dev` or rewrite history. This is a forward move, not a
  reset.

An implementation plan (file-level steps, commit messages, verification
commands) will be written after this spec is accepted. No code until then.

---

## Follow-ups (explicitly not this spec)

- Rename Python package `src` → `sundayalbum`.
- Nested `packages/pipeline/pyproject.toml` if we ever publish the engine
  separately.
- Evaluate Tauri for Windows desktop and Android. If selected, add it as
  `apps/native/` and migrate from `apps/mac/` only after feature parity.
- Add shared client packages such as `packages/api-client`, `packages/ui`, or
  `packages/native-bridge` if multiple apps need them.
- #56 rate-limit countdown, #57 How-it-works video, #58 notarized Mac
  download — independent of layout.
