# Sunday Album

Turns one phone photo of a photo-album page into clean, individual, restored digital photos:
it finds the page, straightens it, splits out each print, removes sleeve glare, fixes
orientation and restores faded color.

This repository is the source of the whole product: the Python processing pipeline, the AWS
backend (CDK, Lambda, Step Functions), the Next.js web app and marketing site, and the SwiftUI
macOS app. Sunday Album is a product of [ArjunTech LLC](https://arjuntech.com); the hosted web
app is at [sundayalbum.com](https://sundayalbum.com).

> **Project stance:** a solo-maintained product repository, published for reference and
> transparency. It is not packaged for others to deploy; the AWS deployment described here is the
> maintainer's own. Issues and security reports are welcome, pull requests are not expected.
> Licence: not yet chosen (see [Licence](#licence)).
>
> **Status (Oct 2026):** the web app is live; the macOS app is a 1.0 beta. The last feature work
> was in April 2026 and the last commit (a repository restructure) in Aug 2026. Maintained as time
> allows.

## Try it

- **Web app:** [sundayalbum.com](https://sundayalbum.com), free tier of 20 pages a day, or bring
  your own Anthropic and OpenAI keys for no limit.
- **macOS app (beta):** the `v1.0-beta1` [release](../../releases/tag/v1.0-beta1). Requires
  macOS 14 or later and is not notarized (right-click, Open on first launch); the first launch
  downloads about 200 MB of Python dependencies.
- **Command line:** below. It runs without any account or API key.

## Run the pipeline locally (no credentials needed)

Prerequisites: macOS or Linux, Python 3.11 or newer, and on macOS
`brew install opencv libheif libraw imagemagick`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # installs the pipeline (package `src`) and test tools
bash scripts/fetch-test-images.sh  # optional: the maintainer's sample album scans (~23 MB)
python -m src.cli process test-images/IMG_cave_normal.HEIC --output ./output/ --debug
```

Without API keys the AI steps degrade gracefully: orientation correction is skipped and glare
removal falls back to OpenCV inpainting. To enable the AI steps copy `.env.example` to `.env`
(gitignored) and add your `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`.

Useful variants: `--batch --filter "*.HEIC"` to process a folder, `python -m src.cli status` to
list the pipeline steps, `--debug` to write every intermediate image to `debug/`.

## Tests

```bash
pytest tests/api tests/handlers -q     # API and Lambda handlers against moto: no AWS, no images
pytest tests -q                        # also the image-based tests; needs test-images/
cd services/infra && pytest tests -q   # CDK stack unit tests (synth only, no AWS)
cd apps/web && npx playwright test     # end-to-end against a deployed dev stack (needs secrets)
```

The first command also runs in GitHub Actions on every push and pull request that touches the
API, handlers or pipeline steps.

## Layout

```
apps/web/               Next.js web app and marketing site (deployed to AWS App Runner)
apps/mac/               SwiftUI macOS app (wraps the same Python CLI)
packages/pipeline/src/  The image-processing engine: preprocessing, page_detection, glare,
                        photo_detection, geometry, color, ai, steps/ (one module per step),
                        storage/ (local and S3 backends), pipeline.py, cli.py
services/api/           Lambda handlers: auth (e-mail code), jobs, settings, websocket
services/handlers/      Lambda handlers: one per pipeline step (Step Functions tasks)
services/infra/         AWS CDK stack (Python)
tests/                  Pipeline, API and handler tests
scripts/                Dev utilities (fetch sample images, validation, backfill)
docs/                   Architecture, pipeline reference, operations, contributing guide
journal/                Development log, indexed in journal/INDEX.md
```

The same step code runs in all three surfaces (CLI, macOS app, AWS) behind a `StorageBackend`
interface; see `docs/SYSTEM_ARCHITECTURE.md`.

## Known limitations

- The AWS deployment is fixed to one region (`us-west-2`) and one maintainer's account; there is
  no multi-tenant or self-service install. `docs/OPERATIONS.md` documents it for reference.
- Sign-in is a one-time code sent by e-mail; there is no password or social login.
- AI steps send the photo to Anthropic (orientation) and OpenAI (glare removal) when keys are
  present. Without keys nothing leaves your machine.
- Quality varies with the input; known weak spots and disabled paths are listed per step in
  `docs/PIPELINE_STEPS.md`.
- The macOS app is not notarized and is macOS 14+ only. Local setup is documented for macOS; the
  same pipeline code runs on Linux in Lambda, other local setups are untested.
- Dependencies in `packages/pipeline/requirements*.txt` use lower bounds, not pinned versions.

## Documentation

| Doc | What it covers |
|---|---|
| `docs/SYSTEM_ARCHITECTURE.md` | Canonical architecture, AWS resources, SDLC |
| `docs/PIPELINE_STEPS.md` | Per-step behaviour, parameters, limitations |
| `docs/OPERATIONS.md` | Deploying, configuration, backup, teardown, cost notes |
| `docs/CONTRIBUTING.md` | Dev setup, test image catalog, adding a pipeline step |
| `SECURITY.md` | How to report a vulnerability |
| `CLAUDE.md` | Working notes for AI-assisted development in this repo |

## Licence

No licence has been chosen yet. Until a `LICENSE` file is added, the code is published for
reading and all rights are reserved by the copyright holder (GitHub's terms still let you view
and fork the repository on GitHub). The sample images in the release assets and
`apps/web/public/demo/` are the maintainer's own photographs. The hosted service is governed by
the [Terms of Use](https://sundayalbum.com/terms).
