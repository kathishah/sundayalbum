# Spec: Model Upgrade Evaluation Harness (2026-10-27)

## Goal

Create a repeatable way to compare model or prompt changes used by the photo pipeline before promoting them to the default configuration. The harness should make quality changes visible, record operational differences, and leave a reviewable result for a human to accept or reject.

The harness is for evaluating changes across providers and model families, not only the current Claude orientation or OpenAI glare-removal calls.

## Current state

- The repository has a local set of 55 HEIC fixtures across `test-images/`, `test-images-2/`, and `test-images-3/`.
- `tests/test_phase6_integration.py` checks photo detection on selected real images and writes debug output for human inspection.
- `scripts/glare_remove.py` accepts an OpenAI model override and writes a single result for manual comparison.
- `journal/2026-02-18-openai-glare-and-orientation.md` records orientation outcomes for known images and selected model defaults.
- Existing automated tests cover image-processing behavior and mocked handler wiring. They do not call candidate models and compare the returned results.
- `packages/pipeline/src/ai/quality_check.py` computes image metrics and can optionally request a Claude assessment. It is a product quality check, not a model-upgrade comparison harness.

## Users and workflow

The harness is a developer tool. A typical evaluation should:

1. Select a named fixture set and pipeline task.
2. Select a baseline and one or more candidate model/prompt configurations.
3. Run the same fixtures through each configuration with equivalent inputs and parameters.
4. Save raw outputs, metadata, and task-specific measurements in a uniquely named run directory.
5. Produce a side-by-side HTML or image report for human review, plus a machine-readable summary.
6. Record a decision and rationale before changing production defaults.

Evaluations that call paid provider APIs must be explicitly started by a developer. A run should display the fixture count and estimated or configured spend limit before sending requests. It must not run implicitly in CI or during ordinary unit tests.

## Execution environment and credentials

- The initial harness runs on the developer's local machine, reads local fixtures, and writes run artifacts locally. It calls Anthropic/OpenAI APIs directly; it does not submit jobs to the deployed web app, Lambda functions, or dev AWS stack.
- Each run uses provider keys explicitly supplied for model evaluation by the developer who starts it. Read them from `SUNDAYALBUM_EVAL_ANTHROPIC_API_KEY` and/or `SUNDAYALBUM_EVAL_OPENAI_API_KEY` environment variables. Require a key only for providers selected in that run.
- Do not fall back to the application's shared dev/prod keys, AWS Secrets Manager, user BYOK settings, or the pipeline's general-purpose `secrets.json`. This keeps evaluation spend tied to an intentional, separately configurable provider account/key.
- Fail before making any calls if a selected provider's eval key is missing. Never print keys or include them in manifests, run metadata, logs, or reports. The provider account associated with the supplied key is billed directly for its requests.
- Remote execution, including running evaluations in the dev environment, is out of scope for the initial harness. It can be considered later if local execution becomes impractical.

## Functional requirements

### 1. Fixture manifest

Use a checked-in manifest to define stable evaluation cases. Each case should include:

- Stable case ID and input file path.
- File hash so results can be tied to exact bytes.
- Task tags such as orientation, glare, album page, single print, portrait, or known edge case.
- Optional expected labels where objectively known (for example, expected rotation and flip).
- Notes describing why the case is included.

The initial manifest should select a small, representative set from the existing fixture folders, including the documented upside-down and mixed-orientation photos, clean/low-glare cases, and challenging glare cases. It should not copy or commit private user photos without confirming that they are already approved for repository use.

### 2. Configuration capture

Each run must capture enough information to reproduce or interpret it:

- Provider and exact model ID (no alias-only entries).
- Prompt template text and content hash.
- All model request parameters that affect output.
- Pipeline revision, evaluation harness revision, SDK version, and fixture hashes.
- Start time, per-call latency, status/error, and provider-reported usage/cost when available.

Do not store API keys, signed URLs, or other secrets in run artifacts.

### 3. Comparable execution

- Run every selected configuration against the same fixture bytes and the same upstream pipeline artifacts where applicable.
- Support candidate configurations that differ by model, prompt, or request parameters.
- Save the provider output unchanged as well as any normalized preview used in the report.
- Support resumable runs after failures without silently mixing results from different configuration hashes.
- Record failed calls and parse/validation failures as results; do not omit them from the summary.

### 4. Task-specific evaluation

The first implementation should support orientation and glare removal.

**Orientation**

- Report exact rotation accuracy and flip accuracy against known labels.
- Report confidence-level distribution and low-confidence/pass-through rate.
- Flag outputs with invalid or unparseable structured data.
- Let a reviewer mark ambiguous fixtures instead of forcing a potentially misleading ground-truth label.

**Glare removal**

- Generate blinded, randomized side-by-side comparisons for baseline and candidate outputs.
- Allow reviewers to rate glare reduction, detail preservation, hallucinated/changed content, color shifts, and overall preference.
- Include the original image and, when available, glare mask/overlay as context.
- Report resolution/dimension changes, latency, errors, and provider usage/cost alongside preference results.
- Do not treat generic pixel similarity or an LLM judge score as the sole quality measure for generative edits.

Other model-backed pipeline tasks can add an evaluator and result fields later without changing the run format.

### 5. Reports and decision record

Each run should produce:

- A machine-readable JSON summary with configurations, fixture coverage, metrics, errors, timing, and usage/cost.
- A local visual report with blinded comparisons and reviewer inputs.
- A final decision record: accepted, rejected, or inconclusive, including reviewer, date, rationale, and known limitations.

Reports must label the baseline and candidate consistently after the blind-review stage; preserve the mapping in the run metadata for later audit.

## Non-functional requirements

- API-backed evaluations are opt-in and separate from CI.
- Evaluation API keys are local, evaluation-specific environment variables; the harness never reads application runtime secrets.
- Unit tests may validate manifest parsing, run metadata, report generation, and evaluator logic using mocked provider responses. They must not make live API calls.
- Evaluation outputs should be reproducible enough to compare configurations even though model responses themselves may be nondeterministic.
- Keep generated images and reports out of normal source control unless explicitly selected for a small, privacy-safe fixture or documentation example. Ignore local run artifacts by default.
- Never make a new model the production default solely because one or two examples look better; require the full selected fixture set and human review of generative changes.

## Acceptance criteria

1. A developer can run the same fixture set against baseline and candidate configurations with one command and without editing pipeline source.
2. Every fixture/configuration combination has a recorded success or failure and complete non-secret configuration metadata.
3. Orientation results are scored against manifest labels, with ambiguous cases excluded from accuracy denominators and called out.
4. Glare outputs are available in a blinded side-by-side report with reviewer ratings and the original image for context.
5. The summary includes latency and provider usage/cost when supplied by the provider, and clearly marks missing cost data.
6. No live provider calls occur in CI or standard unit tests.
7. A model/prompt upgrade decision can be recorded with its supporting run ID and rationale.

## Implementation plan

Implementation should be delivered in small commits on a feature branch. Keep the eval runner independent of the web app and AWS deployment paths. The initial release is a local developer CLI; no live-provider call belongs in CI or ordinary tests.

### Phase 1 — Fixtures and configuration

- Add a JSON fixture manifest under `evals/model-upgrade/`. Give each case a stable ID, repository-relative image path, SHA-256, task tags, optional expected orientation/flip, ambiguity flag, and rationale.
- Select a compact, representative subset from the existing release-backed test image catalog. Confirm fixture redistribution/privacy suitability before adding any new image bytes; manifest entries may point to the existing downloaded files.
- Add JSON configuration files for a baseline and candidates. Each configuration identifies task, provider, exact model ID, prompt source or prompt override, and request parameters. Reject aliases and unsupported task/provider combinations.
- Add `eval-runs/` to `.gitignore`. Keep fixtures/configs tracked and run outputs local by default.

**Exit check:** manifest and configurations validate without API access; every selected fixture exists and matches its recorded hash.

### Phase 2 — Run record and artifact layout

- Define provider-neutral run, configuration, fixture-result, usage, and decision records. Version the schema from the first run.
- Use `eval-runs/<run-id>/` with a run manifest, per-call results, original inputs or references, raw provider result/parsed output, generated images, summary, reviewer ratings, and decision record. Copy fixture images only when permitted; otherwise record their local path and hash.
- Record model ID, provider, full prompt and prompt hash, parameters, input hashes, pipeline/harness Git revisions, SDK versions, timestamps, latency, response status, errors, and usage/cost when returned. Redact credentials and signed URLs.
- On resume, verify that run schema, fixture hashes, and configuration hashes match. Never append results from a changed configuration to the same run.

**Exit check:** offline serialization round-trips a complete successful and failed run, and resumed runs reject mismatched configuration hashes.

### Phase 3 — Provider adapters and safe runner

- Add a local command, for example `python -m src.eval_harness run`, with explicit task, fixture set, baseline, candidate(s), output directory, and run ID options.
- Default to a dry run that lists selected fixtures, providers, model IDs, request count, and cost estimate or configured maximum. Require an explicit execution flag and a budget/call cap before sending paid requests.
- Read only `SUNDAYALBUM_EVAL_ANTHROPIC_API_KEY` and `SUNDAYALBUM_EVAL_OPENAI_API_KEY`; fail before the first call if a selected provider's key is missing. Do not invoke `load_secrets()`, AWS, user settings, or the deployed app. Never log key values.
- Reuse production prompt builders and image encoding where possible, so prompt comparisons reflect actual pipeline behavior. Refactor provider-call boundaries as needed to expose raw outputs, request metadata, usage, and errors without changing the production call's default behavior.
- Run candidate configurations serially by default to make cost and rate-limit behavior predictable. Store each result immediately so an interrupted run can resume.
- Treat API errors, malformed outputs, and fallback/passthrough results as explicit failed or degraded results; do not count them as successful model outputs.

**Exit check:** mocked-provider execution proves dry-run, budget guard, key validation, error capture, and resume behavior without network access.

### Phase 4 — Task evaluators

- **Orientation:** compute exact rotation and flip accuracy from non-ambiguous labels; report denominator, confidence distribution, low-confidence/pass-through rate, and structured-output failures. Keep ambiguous cases visible but outside accuracy calculations.
- **Glare removal:** compute dimensions/resolution changes and provide a blinded comparison for baseline and candidates against the same original. Include the original and optional glare overlay. Collect ratings for glare reduction, detail preservation, changed/hallucinated content, color shifts, and overall preference.
- Randomize left/right placement per fixture and use neutral candidate labels during review. Keep the configuration-to-label map in the run record, and reveal it only after reviewer ratings are saved.
- Do not use SSIM, pixel difference, or an LLM judge as the sole glare quality score. Show these only as optional diagnostics if later evidence supports them.

**Exit check:** known orientation labels produce expected aggregate metrics; a reviewer can rate all glare pairs without seeing model IDs, then reveal and export ratings.

### Phase 5 — Summary, decision, and docs

- Write a machine-readable summary with coverage, metrics, failures, per-call latency, available provider usage/cost, and explicit missing-cost markers. Use a dated/versioned pricing table only when computing estimates; never imply an estimate is provider-billed actual cost.
- Generate a local HTML review page with accessible image sizing, original-image context, randomized comparisons, and locally saved reviewer ratings. Do not require an external service.
- Add a decision record with run ID, reviewer, date, accepted/rejected/inconclusive status, rationale, and known limitations. The harness reports evidence; it never updates production defaults.
- Document fixture preparation, key setup, dry-run and execution commands, spend limits, run artifact locations, privacy rules, and the model-upgrade review checklist.

**Exit check:** one end-to-end small evaluation creates a complete report and decision artifact; no run artifact or credential is tracked by Git.

### Phase 6 — Offline tests and first pilot

- Add offline tests for manifest validation, stable hashing, schema versioning, redaction, prompt/config hashing, orientation metrics, resume safety, randomized blind labels, report generation, and budget enforcement. Mock provider SDK responses; tests must not contact providers.
- Run the unit suite for the new offline components and existing relevant pipeline tests during implementation. Do not add a live API evaluation to CI.
- Before comparing a full fixture set, manually run a deliberately small, approved fixture subset using explicitly configured eval keys and a conservative budget. Review outputs and artifact redaction, then document the pilot run ID and any spec changes.

**Exit check:** all acceptance criteria above pass, the pilot is reviewed by a human, and a model change remains a separate explicit decision.

## Out of scope

- Automatically selecting or deploying a winning model.
- A provider-hosted evaluation service or centralized database.
- Using one LLM as the sole judge for image restoration quality.
- Expanding the product UI to expose model selection to end users.
- Running a live comparison as part of ordinary CI.
