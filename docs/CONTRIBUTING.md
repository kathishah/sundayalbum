# Contributing to Sunday Album

New to the project? Start here. This guide takes you from a fresh clone to a working
development setup, and explains how to navigate the codebase for common contribution tasks.

**Already set up?** See `docs/SYSTEM_ARCHITECTURE.md` for architecture decisions and
`docs/PIPELINE_STEPS.md` for per-step implementation details.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding the Project](#understanding-the-project)
3. [Test Image Catalog](#test-image-catalog)
4. [Where Do I Start?](#where-do-i-start)
5. [How to Add a Pipeline Step](#how-to-add-a-pipeline-step)
6. [Testing Guide](#testing-guide)
7. [Commit & PR Conventions](#commit--pr-conventions)

---

## Quick Start

Five commands from clone to first processed image:

```bash
# 1. Install system dependencies
brew install opencv libheif libraw imagemagick

# 2. Create Python environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Add API keys (Anthropic + OpenAI — both optional, see PIPELINE_STEPS.md for fallbacks)
echo '{ "ANTHROPIC_API_KEY": "sk-ant-...", "OPENAI_API_KEY": "sk-..." }' > secrets.json

# 4. Download test images
bash scripts/fetch-test-images.sh

# 5. Process your first image (add --debug to save intermediate images to debug/)
python -m src.cli process test-images/IMG_three_pics_normal.HEIC --output ./output/ --debug
```

**Expected output:** 3 files in `output/` — one JPEG per detected photo. The `debug/` folder
will contain ~14 intermediate images showing each pipeline step.

If you don't have API keys yet, the pipeline still runs — orientation correction is skipped
and glare removal falls back to OpenCV inpainting. See `docs/PIPELINE_STEPS.md` for details
on each step's fallback behaviour.

---

## Understanding the Project

Sunday Album takes a phone camera photo of an album page containing one or more glossy prints
and produces clean, individually corrected digital photos.

**Three surfaces, one pipeline:**

```
CLI (local)           macOS app             Web app (AWS)
python -m src.cli  →  SwiftUI → CLI    →    Next.js → Lambda → Step Functions
        │                  │                               │
        └──────────────────┴───────────────────────────────┘
                    same packages/pipeline/src/steps/*.py code
                    same PipelineConfig params
                    different StorageBackend (local vs S3)
```

The key architectural insight: every pipeline step is a pure function that reads from and
writes to a `StorageBackend`. Swap the backend and the same step code runs in any context.
API keys are part of `PipelineConfig` — steps never touch environment variables.

For full architecture detail: `docs/SYSTEM_ARCHITECTURE.md`.

---

## Test Image Catalog

14 test images covering distinct failure modes. Use this table to pick the right image(s)
when working on a specific step.

| Image | Photos | Primary scenario | Step(s) it stresses |
|-------|--------|-----------------|---------------------|
| `IMG_three_pics_normal.HEIC` | 3 | Standard album page, plastic sleeve glare | `photo_detect`, `glare_remove` |
| `IMG_two_pics_vertical_horizontal_normal.HEIC` | 2 | Mixed orientations, sleeve glare | `photo_detect`, `ai_orient`, `glare_remove` |
| `IMG_cave_normal.HEIC` | 1 | Dark tones, print glare on curved surface | `glare_remove`, `color_restore` |
| `IMG_harbor_normal.HEIC` | 1 | Bright water reflections; distinguish glare from water content | `glare_remove` |
| `IMG_skydiving_normal.HEIC` | 1 | Bright sky — must NOT be flagged as glare | `glare_remove` |
| `bhavik_2_images.HEIC` | 2 | Album spine (dark background) — contour gives 1 wrong crop | `photo_detect` (spine fallback) |
| `devanshi_school_picnic_bus_2_images.HEIC` | 2 | Album spine — contour gives 3 wrong crops | `photo_detect` (spine fallback) |
| `devanshi_school_picnic_girls_2_images.HEIC` | 2 | Album spine with texture — split at wrong position | `photo_detect` (spine fallback) |
| `devanshi_prachi_sadhna.HEIC` | 1 | Clean single print, standard contour detection | `photo_detect` |
| `chintan_on_razr.HEIC` | 1 | 0 contours detected → full-page fallback | `photo_detect` (edge case) |
| `scuba_divers_getting_ready.HEIC` | 1 | Clean single print, contour direct | `photo_detect` |
| `scuba_divers_in_water.HEIC` | 1 | Print on dark brown surface — background stripping needed | `page_detect`, `photo_split` |
| `st_jude_dinner_w_taral_black_bg.HEIC` | 1 | Print on black leather — background stripping + diagonal crop | `page_detect`, `photo_split` |
| `st_jude_dinner_w_taral_contrast_bg.HEIC` | 1 | Same print on patterned grey/white album surface | `page_detect`, `photo_split` |

**Tip:** When fixing a regression, also run the full 14-image batch to check for new
regressions: `python -m src.cli process test-images/ --output ./output/ --batch --filter "*.HEIC"`

---

## Where Do I Start?

| I want to… | Start here |
|------------|------------|
| Fix photo detection (wrong count, bad split) | `packages/pipeline/src/photo_detection/detector.py` + test images above |
| Manually override detected photo boundaries | Web/macOS: Photo Split step → drag any corner handle freely (non-rectangular quads supported) → "Confirm & Re-run"; CLI: `--forced-detections` JSON with `bbox` and/or `corners` — see `docs/PIPELINE_STEPS.md` → Step 5 |
| Fix page detection (background in output) | `packages/pipeline/src/page_detection/detector.py` + `packages/pipeline/src/page_detection/perspective.py` |
| Tune color / fade restoration | `packages/pipeline/src/color/restore.py` — params in `docs/PIPELINE_STEPS.md` → Step 9 |
| Tune white balance or deyellowing | `packages/pipeline/src/color/white_balance.py`, `packages/pipeline/src/color/deyellow.py` |
| Fix glare removal (OpenCV path) | `packages/pipeline/src/glare/` — `detector.py`, `remover_single.py` |
| Change orientation correction | `packages/pipeline/src/steps/ai_orient.py` → `packages/pipeline/src/ai/claude_vision.py` |
| Add or change a pipeline step | See [How to Add a Pipeline Step](#how-to-add-a-pipeline-step) below |
| Fix a web API bug | `services/api/` + `tests/api/` |
| Fix a Lambda handler bug | `services/handlers/` + `tests/handlers/` |
| Change AWS infrastructure (CDK) | `services/infra/infra/sundayalbum_stack.py` |
| Update the macOS app | `apps/mac/SundayAlbum/` |
| Edit a public marketing page | `apps/web/src/app/(public)/` |
| Edit the marketing nav or footer | `apps/web/src/components/MarketingNav.tsx`, `MarketingFooter.tsx` |
| Replace pipeline page demo images | Resize from `debug/` into `apps/web/public/demo/pipeline/` (see `journal/2026-04-10-public-website.md`) |
| Understand a past algorithm decision | `journal/INDEX.md` → find the relevant entry |

---

## How to Add a Pipeline Step

Adding a step involves **five files**. Follow the existing steps as templates.

### 1. Create the step function — `packages/pipeline/src/steps/mystep.py`

Every step is a pure function with this signature:

```python
def run(
    storage: StorageBackend,
    stem: str,
    config: PipelineConfig,
    photo_index: Optional[int] = None,
) -> dict:
    """What this step does. (Google-style docstring)"""
    # Read inputs from storage
    # Do processing
    # Write outputs back to storage
    # Return a result dict (passed to next step via Step Functions event)
    return {"my_step_result_key": value}
```

Rules:
- Never read `os.environ` or call `load_secrets()` — API keys come from `config`
- Never mutate arrays in-place — return a new array
- All thresholds and tunable values go in `PipelineConfig`, not as magic numbers
- Write at least one `debug/{stem}_NN_mystep.jpg` output when `config.debug` is set
- Use `logging.debug/info/warning` — never `print()`

### 2. Register it in the CLI — `packages/pipeline/src/pipeline.py`

Add an entry to the `PIPELINE_STEPS` list so it appears in `python -m src.cli status`:

```python
{
    'id': 'mystep',
    'name': 'My Step Name',
    'description': 'One sentence description',
    'priority': 2,
    'implemented': True,
},
```

Wire the step into `run_pipeline()` in the same file.

### 3. Create the Lambda handler — `services/handlers/mystep.py`

The handler wraps the step function for the Step Functions / Lambda execution context.
Copy `services/handlers/normalize.py` as a starting point — it's the simplest handler.
Key responsibilities:
- Call `update_step()` to write progress to DynamoDB (triggers WebSocket push)
- Call `fail_job()` on exceptions
- Return the updated event dict for the next Step Functions state

### 4. Define the Lambda in CDK — `services/infra/infra/sundayalbum_stack.py`

Add a `pipeline_fn()` call alongside the others:

```python
mystep_fn = pipeline_fn(
    "MyStepFunction",
    "sa-pipeline-mystep",
    "handlers.mystep.handler",
    timeout_secs=60,
    memory_mb=3008,
    description="What my step does",
)
```

Then add `invoke("MyStep", mystep_fn)` to the Step Functions chain definition.

### 5. Add tests — `tests/handlers/test_mystep.py`

Copy `tests/handlers/test_normalize.py` as a template. Tests use `moto` to mock AWS —
no real S3 or DynamoDB needed. The pre-commit hook runs these on every commit.

---

## Testing Guide

### Test suites at a glance

| Suite | Command | What it tests | Needs test images? | Needs AWS? |
|-------|---------|---------------|--------------------|------------|
| `tests/api/` | `pytest tests/api/ -v` | API Lambda handlers (auth, jobs, settings) | No | No (moto) |
| `tests/handlers/` | `pytest tests/handlers/ -v` | Pipeline Lambda handlers | No | No (moto) |
| `tests/test_loader.py` | `pytest tests/test_loader.py -v` | HEIC/DNG loading, EXIF orientation | Yes | No |
| `tests/test_glare.py` | `pytest tests/test_glare.py -v` | Glare detection (OpenCV) | Yes | No |
| `tests/test_photo_detection.py` | `pytest tests/test_photo_detection.py -v` | Photo boundary detection | Yes | No |
| `tests/test_phase6_integration.py` | `pytest tests/test_phase6_integration.py -v` | End-to-end photo split | Yes | No |
| Playwright E2E | `cd web && npx playwright test` | Full web UI on dev.sundayalbum.com | No | Yes (dev env) |

**Run the fast suite before committing** (the pre-commit hook does this automatically):
```bash
pytest tests/api/ tests/handlers/ -v   # 36 tests, ~5s, no dependencies
```

### Writing a new test

- For handler tests: mock S3/DynamoDB with `moto`, put a test fixture in `tests/fixtures/`,
  follow the pattern in `tests/handlers/test_normalize.py`
- For algorithm tests: load a test image, run the function, assert on the output shape /
  detected count / pixel value range
- Test image access: use `pytest.fixture` in `conftest.py` that skips if `test-images/`
  is not present (run `bash scripts/fetch-test-images.sh` to populate)

### Pre-commit hook

The hook runs automatically on every `git commit`. Install once per clone:
```bash
git config core.hooksPath .githooks
```

Escape hatch for work-in-progress commits:
```bash
SKIP_HOOKS=1 git commit -m "wip: ..."
```

---

## Commit & PR Conventions

### Commit message format (conventional commits)

```
<type>: <short summary in present tense>

Optional body — explain the "why", not the "what".

Co-Authored-By: ...
```

Common types:

| Type | Use for |
|------|---------|
| `feat:` | New feature or capability |
| `fix:` | Bug fix |
| `refactor:` | Code change with no behaviour change |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `chore:` | Build, infra, dependency changes |

Examples:
```
fix: prevent projection fallback from splitting on spine texture
feat: add vibrance saturation stage to color_restore step
docs: add test image catalog to CONTRIBUTING.md
```

### PR workflow

1. Branch from `dev`: `git checkout dev && git checkout -b feature/my-change`
2. Open PR to `dev` (not `main`)
3. CI runs `pytest tests/api/ tests/handlers/` automatically
4. Merge to `dev` → auto-deploys to `dev.sundayalbum.com`
5. PR from `dev` → `main` for production releases

See `docs/SYSTEM_ARCHITECTURE.md` for full SDLC and GitHub Actions workflow details.
