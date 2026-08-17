# CLAUDE.md — Sunday Album Processing Engine

## Project Overview

Sunday Album digitizes physical photo album pages into clean individual digital photos. This
repo contains the Python CLI processing engine, the macOS SwiftUI app, the AWS web backend,
and the Next.js web frontend.

---

## Documentation — What to Read This Session

Load only what's relevant to the current task. Don't read everything.

| If this session involves… | Read |
|---------------------------|------|
| A specific pipeline step | `docs/PIPELINE_STEPS.md` → that step's section |
| Color / glare / geometry tuning | `docs/PIPELINE_STEPS.md` + recent entries in `journal/INDEX.md` |
| Web frontend (Next.js) | `docs/SYSTEM_ARCHITECTURE.md` → Web Application section |
| Web API or Lambda handlers | `docs/SYSTEM_ARCHITECTURE.md` → Web Application + API Key Resolution |
| AWS infrastructure / CDK | `docs/SYSTEM_ARCHITECTURE.md` → Web Application + SDLC sections |
| macOS app | `docs/SYSTEM_ARCHITECTURE.md` → macOS App section |
| Adding a new pipeline step | `docs/CONTRIBUTING.md` → "How to Add a Pipeline Step" |
| Debugging a specific test image | `docs/PIPELINE_STEPS.md` + `docs/CONTRIBUTING.md` → Test Image Catalog |
| Understanding a past decision | `journal/INDEX.md` → find the relevant entry |
| First session / onboarding | `docs/CONTRIBUTING.md` (read fully) |
| Full architecture orientation | `docs/SYSTEM_ARCHITECTURE.md` (read fully) |

All docs are indexed in `docs/README.md`.

---

## Development Machine

- **MacBook Air M4, 24 GB RAM**, macOS Tahoe 26.2, Apple Silicon (ARM64) — Homebrew + Python venv; never install packages globally

---

## Setup

```bash
# System dependencies
brew install opencv libheif libraw imagemagick

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r packages/pipeline/requirements.txt
# or: pip install -e ".[dev]"

# Verify
python -c "from pillow_heif import register_heif_opener; print('HEIC OK')"
python -c "import rawpy; print('DNG OK')"
python -c "import cv2; print(f'OpenCV {cv2.__version__} OK')"
```

### API keys (`secrets.json` — gitignored)

```json
{ "ANTHROPIC_API_KEY": "sk-ant-...", "OPENAI_API_KEY": "sk-..." }
```

Alternatively, set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` env vars. The CLI reads these once
at startup and injects them into `PipelineConfig`. Steps never read env vars directly.

### Pre-commit hooks

```bash
git config core.hooksPath .githooks   # runs pytest + Playwright before every commit
SKIP_HOOKS=1 git commit -m "wip: …"  # escape hatch
```

### Test images

```bash
bash scripts/fetch-test-images.sh   # downloads into test-images/ (gitignored)
```

See `docs/CONTRIBUTING.md` → Test Image Catalog for what each image exercises.

---

## CLI Usage

```bash
# Process a single image
python -m src.cli process test-images/IMG_three_pics_normal.HEIC --output ./output/

# With debug visualizations (saves intermediate images to debug/)
python -m src.cli process test-images/IMG_three_pics_normal.HEIC --output ./output/ --debug

# Batch — process all HEIC files
python -m src.cli process test-images/ --output ./output/ --batch --filter "*.HEIC"

# Force OpenCV glare fallback (no OpenAI API call)
python -m src.cli process test-images/IMG_harbor_normal.HEIC --output ./output/ --no-openai-glare

# Disable AI orientation correction
python -m src.cli process test-images/IMG_harbor_normal.HEIC --output ./output/ --no-ai-orientation

# Provide a scene description manually (skips Claude orientation call)
python -m src.cli process test-images/IMG_cave_normal.HEIC --output ./output/ \
  --scene-desc "A cave interior with warm amber light"

# Override detected photo boundaries (bypasses contour detection)
# Use bbox for axis-aligned crops, or add corners for free-form quads (keystoned photos):
python -m src.cli process test-images/IMG_three_pics_normal.HEIC --output ./output/ \
  --forced-detections '[{"bbox":[50,80,900,700],"corners":[[55,85],[895,78],[905,698],[48,705]],"confidence":1.0,"region_type":"photo","orientation":"unknown"}]'

# Run only specific pipeline steps
python -m src.cli process test-images/IMG_cave_normal.HEIC --output ./output/ \
  --steps load,normalize,page_detect

# Show pipeline status
python -m src.cli status
```

Available step IDs: `load`, `normalize`, `page_detect`, `photo_detect`, `ai_orientation`,
`glare_detect`, `keystone_correct`, `dewarp`, `rotation_correct`, `white_balance`,
`color_restore`, `deyellow`, `sharpen`

---

## Testing

### ⚠️ macOS UI Tests — DISRUPTIVE, requires explicit user permission

macOS UI tests (`SundayAlbumUITests`) **take over the screen**, launch the app visually, and
run for ~2 minutes. They are extremely disruptive to a working session.

**Rules:**
- **NEVER run UI tests unless the user explicitly asks** ("run the UI tests", "run all tests
  including UI tests", "run the full macOS test suite").
- Verifying a build or checking logic changes → run unit tests only (see below).
- A passing build (`xcodebuild build`) is sufficient to confirm Swift compiles correctly.

```bash
# ── Python pipeline tests (non-disruptive) ────────────────────────────────────────
pytest tests/ -v                            # all Python tests
pytest tests/test_loader.py -v             # specific suite
pytest tests/api/ tests/handlers/ -v       # API + Lambda handler tests (moto, ~5s)

# ── Swift unit tests only — non-disruptive, no screen takeover ───────────────────
# Use -skip-testing to exclude the UI test bundle.
xcodebuild test \
  -scheme SundayAlbum \
  -destination 'platform=macOS' \
  -skip-testing:SundayAlbumUITests

# ── Swift UI tests — ⚠️ DISRUPTIVE, only run on explicit user request ────────────
xcodebuild test \
  -scheme SundayAlbum \
  -destination 'platform=macOS' \
  -only-testing:SundayAlbumUITests

# ── Web E2E (Playwright) — requires apps/web/.auth/session.json ──────────────────
cd apps/web && npx playwright test
```

**Never use** `xcodebuild test -scheme SundayAlbum` **without a `-skip-testing` or
`-only-testing` flag** — this runs both unit AND UI tests and will hijack the screen.

---

## Project Structure (top-level)

```
sundayalbum/
├── CLAUDE.md            # This file
├── pyproject.toml
├── secrets.json         # Gitignored — API keys
├── docs/                # Architecture, pipeline, archive
├── journal/             # Development log
├── scripts/             # fetch-test-images.sh, sunday, setup-runtime.sh
├── test-images/         # Gitignored — 10 test images (5 HEIC + 5 DNG)
├── apps/
│   ├── web/             # Next.js web frontend + marketing site
│   └── mac/             # SwiftUI macOS app
├── packages/
│   └── pipeline/        # Shared image-processing engine
│       ├── src/         # Python pipeline source (package name: `src`)
│       │   ├── cli.py
│       │   ├── pipeline.py
│       │   ├── steps/   # Pure-function step implementations
│       │   ├── preprocessing/
│       │   ├── page_detection/
│       │   ├── glare/
│       │   ├── photo_detection/
│       │   ├── geometry/
│       │   ├── color/
│       │   ├── ai/
│       │   └── utils/
│       ├── requirements.txt
│       ├── requirements-lambda.txt
│       └── requirements-runtime.txt
├── services/
│   ├── api/             # Lambda handlers — auth, jobs, settings, websocket
│   ├── handlers/        # Lambda handlers — pipeline steps
│   └── infra/           # AWS CDK stack
├── tests/               # pytest suite (spans all three trees)
├── Dockerfile           # Pipeline Lambda image (context = repo root)
└── .venv/               # Stays at root (macOS dev-mode contract)
```

### macOS app builds

```bash
cd apps/mac && bash build-release.sh   # → ~/Desktop/SundayAlbum-1.0-beta1.dmg
```

`build-release.sh` stamps `apps/mac/SundayAlbum/BuildInfo.swift` with the PST build date
(`yyyy-mm-dd-hh-min`) before compiling. The file is committed with value `"dev"` so IDE
(Debug) builds show "dev" in the About panel; release builds show the real timestamp.
Do not edit `BuildInfo.swift` by hand — it is overwritten on every release build.

---

## Coding Conventions

- **Type hints** on all functions (mypy strict mode)
- **Docstrings** on public functions (Google style)
- **Logging** not print statements — `logging.debug/info/warning`
- **NumPy arrays** for image data; `np.ndarray` type hints with shape comments
- **RGB color order** internally; convert to BGR only for OpenCV calls, convert back immediately
- **float32 [0, 1] range** for processing; convert from/to uint8 at I/O boundaries
- **Immutable pipeline** — each step returns a new array; no in-place mutation
- **Config over magic numbers** — all thresholds and parameters in `PipelineConfig` dataclass
- **No `load_secrets()` in steps** — API keys come from `config.anthropic_api_key` / `config.openai_api_key`

---

## Branch Strategy (SDLC)

```
feature/my-change  ──PR──►  dev  ──PR──►  main
                              │              │
                              ▼              ▼
                          dev env         prod env
                     (auto-deploy)     (auto-deploy)
```

1. Always branch from `dev`: `git checkout dev && git checkout -b feature/my-change`
2. Open PR to `dev` — triggers CI, auto-deploys to dev environment on merge
3. Open PR from `dev` → `main` for production releases

CDK infrastructure changes: deployed manually via `cdk deploy` from `services/infra/`. Not in CI.

See `docs/SYSTEM_ARCHITECTURE.md` for GitHub Actions workflow details and AWS resource names.
