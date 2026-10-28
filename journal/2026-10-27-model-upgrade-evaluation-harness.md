# Spec: Model Upgrade Evaluation Harness (2026-10-27)

## Goal

Create a repeatable way to compare model or prompt changes used by individual photo-pipeline stages before promoting them to the default configuration. The harness should make quality changes visible, record operational differences, and leave a reviewable result for a human to accept or reject.

The harness format is provider-neutral, but its initial support matrix is narrow: orientation uses Anthropic and glare removal uses OpenAI `images.edit`. Add a future provider/task by implementing its adapter and evaluator against the versioned run/result interface, then adding it to the support matrix and offline tests. Model-stage inputs are pre-created crops, so runs do not depend on page detection, photo splitting, or another upstream result.

## Current state

- Source HEICs are full capture/page inputs, not canonical model-stage inputs. The downloaded contents of `test-images-2/` and `test-images-3/` are local-only today and are not covered by the existing test-image release. Use actual local paths and hashes, not names inferred from catalog aliases.
- There is not yet a frozen crop corpus. Crop bytes are all-rights-reserved and must not be committed to this public repository. The repository will contain the manifest, labels, hashes, and scene descriptions; reviewed crop bytes will be distributed as a versioned GitHub release asset (for example, `v0.0.4-evaldata`) and fetched with a script modeled on `scripts/fetch-test-images.sh`.
- `tests/test_phase6_integration.py` checks photo detection on selected real images and writes debug output for human inspection.
- `scripts/glare_remove.py` accepts an OpenAI model override and `--n` for multiple outputs, but comparisons can still be confounded by upstream crop/orientation differences.
- `journal/2026-02-18-openai-glare-and-orientation.md` records prior experiments, but contains inconsistent rotation labels for one image; it is not authoritative for fixture ground truth.
- Existing automated tests cover image-processing behavior and mocked handler wiring. They do not call candidate models and compare the returned results.
- `packages/pipeline/src/ai/quality_check.py` computes image metrics and can optionally request a Claude assessment. It is a product quality check, not a model-upgrade comparison harness.

## Users and workflow

The harness is a developer tool. A typical evaluation should:

1. Select a named fixture set and pipeline task; the fixture set points directly to immutable, pre-created crop files.
2. Select the current pipeline setup as the baseline and provide one sparse override config for the candidate. The config only needs entries for steps being changed.
3. Run the same fixtures through the baseline and candidate, resolving omitted step settings from the existing pipeline setup.
4. Save raw outputs, metadata, and task-specific measurements in a uniquely named run directory.
5. Produce a side-by-side HTML or image report for human review, plus a machine-readable summary.
6. Record a decision and rationale before changing production defaults.

Evaluations that call paid provider APIs must be explicitly started by a developer. A run should display the fixture count and estimated or configured spend limit before sending requests. It must not run implicitly in CI or during ordinary unit tests.

## Execution environment and credentials

- The initial harness runs on the developer's local machine, reads local fixtures, and writes run artifacts locally. It calls Anthropic/OpenAI APIs directly; it does not submit jobs to the deployed web app, Lambda functions, or dev AWS stack.
- Read the selected provider keys from the gitignored project-root `secrets.json` (`~/dev/sundayalbum/secrets.json` in the current checkout), using its existing `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` fields. Ignore unrelated fields such as `AWS`. Reuse or extend `load_secrets()` with the root file path passed explicitly and strict local-file mode, since its default points inside `packages/pipeline/` and falls back to environment variables.
- Do not read application runtime secrets from AWS Secrets Manager, user BYOK settings, or the deployed dev/prod stack. The local file is the only credential source for eval runs; the account associated with those keys is billed directly.
- Fail before making any calls if the local file or a selected provider's key is missing. Never print keys or include them in manifests, run metadata, logs, or reports. Keep the secret file excluded from Git.
- Construct provider clients inside the harness with the selected key and an explicit base URL. Never pass a missing key to a provider function, import `src.cli` (which loads `.env` at import time), or allow SDK defaults to read keys or base URLs from the environment. Use each provider's documented default URL explicitly unless a future spec adds a deliberate endpoint override.
- Remote execution, including running evaluations in the dev environment, is out of scope for the initial harness. It can be considered later if local execution becomes impractical.

## Functional requirements

### 1. Fixture manifest

Use a checked-in manifest to define stable evaluation cases whose direct input is a fetched, pre-created crop under local `test-cropped-images/`. Each case should include:

- Stable case ID, task-specific input path, and SHA-256 so results can be tied to the exact bytes sent to the model.
- Source HEIC path/hash, photo position (such as `top` or `bottom`) and index, crop coordinates/corners, extraction tool/version, pipeline Git revision, platform/architecture, and the steps/configuration that produced the crop. This provenance is descriptive; the eval runner must not regenerate the crop.
- Task tags such as orientation, glare, album page, single print, portrait, or known edge case.
- Optional expected labels where objectively known (for example, expected rotation and flip), reviewed against the cropped input itself.
- Notes describing why the case is included.

The initial orientation corpus must include these five photo crops, extracted once from the source HEICs and manually reviewed against each exact frozen crop:

- The two individual photos from `test-images/IMG_two_pics_vertical_horizontal_normal.HEIC`.
- The three individual photos from `test-images/IMG_three_pics_normal.HEIC`.

Add at least two more selected crops from each of `test-images-2/` and `test-images-3/`, chosen to broaden orientation and glare coverage. Keep the set compact and curated, not every photo from every source image. Store reviewed crop files locally under `test-cropped-images/`; distribute approved bytes through the eval-data release asset. Evaluations must not depend on source albums or rerunning extraction. Create a correctly oriented glare-stage counterpart for each of the five core crops at minimum, plus any additional selected crops needed for glare coverage.

Owner-confirmed expectations to verify against the frozen crop itself: `IMG_two_pics_vertical_horizontal_normal.HEIC` top photo = 270° clockwise and bottom photo = 180°; all three photos in `IMG_three_pics_normal.HEIC` = 180°; selected photos from `test-images-2/` and `test-images-3/` = 0°. These page-derived expectations are starting points; freeze a label only after confirming it relative to the actual crop bytes.

Keep distinct stage inputs where necessary. Orientation evaluation uses the direct, unrotated crop output from photo splitting. Glare evaluation uses a pre-created crop rotated upright using the human label, never a model's output, and a fixed scene description (hand-written or taken from one baseline run and reviewed once). Every glare configuration receives identical image bytes and prompt text. Link both artifacts through a shared fixture/source ID and record the exact orientation transform used to prepare the glare input.

Crop bytes from `test-images-2/` and `test-images-3/` must be approved for the eval release or marked `local-only`; run summaries identify local-only fixture use. Before a paid run, documentation and metadata identify the provider account used and link or record applicable provider data-retention terms. Verify every fetched fixture hash before a run. A refresh command may regenerate draft crops and report changed hashes, but must never overwrite frozen fixtures; re-baselining requires explicit human review. Frozen crops intentionally do not detect upstream photo-detection changes that alter production model inputs; those remain covered by existing pipeline tests.

Optionally derive 90°, 180°, and 270° synthetic rotations from upright crops to enlarge orientation coverage. Report synthetic and real results separately; real crops remain decisive.

Future orientation experiment proposed after the 2026-10-28 review: send four
views of the same crop, rotated 0°, 90°, 180°, and 270°, in one model request.
Ask the model to identify the most plausible upright view and provide a scene
description for it; map the chosen view to the correction for the original
crop. Evaluate this separately from the existing single-image prompt, with
real and derived fixtures reported separately and repeatability, latency,
token use, and cost recorded. This is a research idea, not part of the current
harness or production defaults.

### 2. Sparse override configuration and capture

The CLI takes one candidate config file. It is an overlay on the existing pipeline configuration, not a complete replacement. Its `steps` map contains only the steps being overridden. A step entry can specify provider/model, an optional prompt override, and request parameter overrides. An omitted step keeps its existing production setup. Within an included step, an omitted provider, prompt, or request parameter keeps its existing value; supplied fields override only those values. A prompt override may be inline or referenced from a local prompt file; the resolved full prompt is captured in the run record.

Example: this candidate changes only the `ai_orientation` model. It keeps the current prompt and request parameters. Other pipeline steps remain unchanged.

```json
{
  "schema_version": 1,
  "name": "orientation-openai-candidate",
  "steps": {
    "ai_orientation": {
      "provider": "openai",
      "model": "<model-id>"
    }
  }
}
```

To change the prompt, add a `prompt` string or prompt-file reference to that step entry. To change request settings, add only the keys to override under `parameters`. The provider field is needed when changing providers; otherwise the existing provider is inherited. A config may contain more than one step entry, but every omitted step continues to use the current pipeline setup.

The baseline is the current pipeline setup at the recorded pipeline revision. For every run, resolve and capture the effective configuration for both baseline and candidate, including:

- Step name, provider, requested and provider-resolved model ID. Use an accepted-ID policy or record the resolved ID (for Anthropic, `response.model`) and flag drift; do not reject a baseline solely because its published ID is an alias without a dated snapshot.
- Full resolved prompt text and content hash, whether it came from the existing prompt builder or an override, plus all effective request parameters.
- Pipeline revision, evaluation harness revision, SDK version, and fixture hashes.
- Start time, per-attempt latency, status/error, and provider-reported usage when available. Cost is a dated-pricing-table estimate, clearly labelled as such; do not expect current APIs to report dollar cost.

Do not store API keys, signed URLs, or other secrets in run artifacts.

### 3. Comparable execution

- Run every selected configuration against the same exact manifest input bytes. Upstream source/crop provenance is recorded for traceability but is not recomputed or consumed during an eval run.
- For model-stage evaluations, load only the pre-created crop path from the manifest. Never run page detection, photo splitting, orientation, or another upstream stage during that task's candidate comparison.
- Orientation and glare comparisons use their own stage-appropriate crop variant. Glare comparisons must not consume each candidate's orientation output.
- Support a candidate config that overrides only the selected step's model/provider, prompt, and/or request parameters; preserve current pipeline values for all omitted fields and steps.
- Save the provider output unchanged as well as any normalized preview used in the report.
- Support resumable runs after failures without silently mixing results from different configuration hashes. Keep recorded failures on resume by default; retry them only with explicit `--retry-failed`.
- Record failed calls and parse/validation failures as results; do not omit them from the summary.

### 4. Task-specific evaluation

The first implementation should support orientation and glare removal: Anthropic for orientation and OpenAI `images.edit` for glare removal.

**Orientation**

- Use the stored photo-split crop bytes directly as orientation inputs. Store expected rotation/flip against that exact crop, not the full source page.
- Report raw rotation accuracy and effective accuracy after production's confidence gate; effective accuracy is the user-visible measure. Report confidence distribution and low-confidence/pass-through rate. Do not expose the currently unread `ai_orientation_min_confidence` as tunable unless production is changed to honor it.
- Report false-flip rate because no fixture currently has a positive flip label. Record candidate scene descriptions; before accepting an orientation change, require a glare run using those descriptions with the baseline glare model or a recorded waiver.
- Flag outputs with invalid or unparseable structured data.
- Support configurable repeats per fixture (default more than one for orientation) and report per-fixture agreement. Record acceptance thresholds in the run configuration before calls begin, such as no regression on real rotated crops and a minimum upright-crop score.
- Let a reviewer mark ambiguous fixtures instead of forcing a potentially misleading ground-truth label.

**Glare removal**

- Use the stored upright glare-stage crop directly as the shared input. Keep its hash fixed across baseline/candidate calls and exclude orientation inference from this comparison.
- Generate blinded, randomized side-by-side comparisons for baseline and candidate outputs. Normalize preview display size and hide dimensions, latency, and cost until ratings are saved. Keep the model-to-label mapping out of the review page; export ratings JSON and use a separate CLI `reveal` command to join ratings to the mapping. Record the randomization seed.
- Allow reviewers to rate glare reduction, detail preservation, hallucinated/changed content, color shifts, and overall preference.
- Include the original image and, when available, glare mask/overlay as context.
- Report resolution/dimension changes, latency, errors, and provider usage alongside preference results; any dollar cost is an explicitly dated estimate.
- Do not treat generic pixel similarity or an LLM judge score as the sole quality measure for generative edits.

Other model-backed pipeline tasks can add an evaluator and result fields later without changing the run format.

### 5. Post-evaluation promotion

An accepted evaluation records a recommendation; it does not change production behavior. Promoting a candidate requires a separate production-code change through the repository's normal review and deployment process. That change must apply the accepted provider/model, prompt, and request parameters to the relevant pipeline step, reference the accepted run and decision record, and verify that the production effective configuration matches the evaluated candidate. Provider changes must include production credential, client, permission, and failure-handling integration. The harness must not copy an eval config into runtime configuration, update production defaults, merge code, or deploy. Once deployed, record the promoted configuration as the baseline for future evaluations.

### 6. Reports and decision record

Each run should produce:

- A machine-readable JSON summary with configurations, fixture coverage, metrics, errors, timing, and usage/cost.
- A local visual report with blinded comparisons and reviewer inputs.
- A final decision record: accepted, rejected, or inconclusive, including reviewer, date, rationale, and known limitations.

Keep model/config mapping out of the blind-review page, then reveal it only after ratings are saved; preserve the mapping separately in run metadata for later audit. Ratings export must work without `file://` write access (download JSON or use a small local server).

## Non-functional requirements

- API-backed evaluations are opt-in and separate from CI.
- Evaluation API keys come only from the gitignored project-root `secrets.json`; the harness never reads application runtime secrets or deployed keys.
- Unit tests may validate manifest parsing, run metadata, report generation, and evaluator logic using mocked provider responses. They must not make live API calls. Offline eval tests run in CI, block network access and SDK client construction by default, and are included in the workflow path filters.
- Evaluation outputs should be reproducible enough to compare configurations even though model responses themselves may be nondeterministic.
- Treat the curated crop corpus as intentional test data, but keep image bytes out of Git; distribute approved crops through the versioned release asset and fetch them locally. Do not regenerate or overwrite frozen crops during an eval run; crop changes require review, a new hash/version, and an updated manifest.
- Keep generated model outputs and reports out of normal source control. Ignore local run artifacts by default.
- Never make a new model the production default solely because one or two examples look better; require the full selected fixture set and human review of generative changes.

## Acceptance criteria

1. A developer can run the same fixture set against baseline and candidate configurations with one command and without editing pipeline source; the runner sends the manifest's stored crop bytes unchanged as model-stage inputs.
2. Every fixture/configuration combination has a recorded success or failure, the exact crop hash used, and complete non-secret configuration metadata.
3. Orientation results are scored against manifest labels, with ambiguous cases excluded from accuracy denominators and called out.
4. Glare outputs are available in a blinded side-by-side report with reviewer ratings and the original image for context.
5. The summary includes latency and provider usage when supplied by the provider; dollar costs are dated estimates clearly labelled as estimates, and missing usage/cost is marked.
6. No live provider calls occur in CI or standard unit tests.
7. A model/prompt upgrade decision can be recorded with its supporting run ID and rationale.
8. The orientation crop corpus includes the two photos from `IMG_two_pics_vertical_horizontal_normal.HEIC`, the three photos from `IMG_three_pics_normal.HEIC`, and at least two additional reviewed crops from each of `test-images-2/` and `test-images-3/`; each of the five core crops also has a reviewed upright glare-stage counterpart.
9. Orientation and glare fixtures are separately identified when their stage-appropriate inputs differ; glare inputs are already upright before any candidate glare call.
10. Frozen crops are fetched from the eval-data release and hash-verified; no image bytes are committed to Git. The manifest records crop provenance, labels rechecked against exact crop bytes, and local-only status where applicable.
11. The dry run reports worst-case attempts (fixtures × configurations × repeats × max attempts). The cap counts every attempt, including retries; reaching it stops the run, marks remaining combinations `not_run`, and leaves the run resumable.
12. Runs support repeats and predeclared thresholds, raw/effective orientation metrics, false-flip rate, blinded ratings export/reveal, and resolved-model drift reporting.

## Implementation plan

Implementation should be delivered in small commits on a feature branch. Keep the eval runner independent of the web app and AWS deployment paths. The initial release is a local developer CLI; no live-provider call belongs in CI or ordinary tests.

### Phase 1 — Create the frozen cropped-image corpus and configuration

- Create local `test-cropped-images/` with stage-specific subdirectories, initially `orientation/` and `glare/`. Do not commit crop image bytes.
- Use the production photo splitter once to extract two crops from `IMG_two_pics_vertical_horizontal_normal.HEIC` and three crops from `IMG_three_pics_normal.HEIC`. Review each crop visually, preserve its orientation as extracted, and add an expected rotation/flip label only after checking the exact crop.
- Select at least two additional source photos from each of `test-images-2/` and `test-images-3/` based on orientation/glare diversity. Extract and review those crops the same way.
- For every orientation crop included in glare evaluation, create a separate upright glare-stage crop with a recorded rotation/flip transform. Review the result so glare comparisons start from a fixed production-stage input.
- Create a glare-stage counterpart for each of the five required core crops at minimum; choose and document additional glare-stage crops from the other source collections for coverage.
- Add top-level `evals/model-upgrade/build_fixtures.py` (or equivalent) to run only deterministic loading through photo splitting, with AI orientation and OpenAI glare removal off, and write candidate crops/draft manifest. It is never invoked by the eval runner. Record source/crop hashes, photo position, coordinates, extraction version, pipeline Git revision, platform/architecture, steps/configuration, and label relative to the exact frozen crop. Human review finalizes crops and manifest.
- Add a refresh command that reports changed crop hashes without overwriting frozen fixtures. Re-baselining is a separate explicit reviewed action.
- Publish approved bytes in a versioned GitHub release asset and add a fetch script modeled on `scripts/fetch-test-images.sh`. Verify downloaded hashes before runs. Mark non-approved crops from `test-images-2/` or `test-images-3/` as `local-only`; report that in run summaries. Record provider account and data-retention reference before sending images to either provider.
- Add a JSON fixture manifest under `evals/model-upgrade/`. Each case records stable ID, task-specific crop path and hash, source HEIC path/hash, photo index, crop coordinates/corners, extraction version, task tags, optional expected orientation/flip, ambiguity flag, and rationale.
- Track only manifest, labels, hashes, descriptions, and configs in `evals/model-upgrade/`; keep bytes in the release asset/local fetched directory. The eval runner must not require source HEICs to be present.
- Store sparse candidate override configs under `evals/model-upgrade/configs/`. Each file has a `steps` map keyed by pipeline step name; include only steps to override. An entry may set provider/model, prompt override, and request parameter overrides. Omitted steps and fields inherit the existing pipeline setup. For example, a config that changes only orientation's model leaves the existing orientation prompt and parameters in force and leaves every other step untouched. Configs may select any provider for which that step has an implemented adapter and evaluator; adding a provider requires implementing and testing the adapter. Record provider-resolved model IDs and flag drift. Reject unsupported step/provider combinations.
- Add `eval-runs/` and fetched crop bytes to `.gitignore`. Track the manifest/configs and keep run outputs local by default.

**Exit check:** the corpus contains the required 2 + 3 crops plus at least two additional crops from each other source folder; orientation and glare variants are reviewed, and the manifest validates hashes without API access or a live splitter run.

### Phase 2 — Run record and artifact layout

- Define provider-neutral run, sparse override configuration, fixture-result, usage, and decision records. Version the schema from the first run.
- Use top-level `eval-runs/<run-id>/` with a run manifest, per-attempt results, crop fixture IDs/hashes, raw provider result/parsed output, generated images, summary, exported reviewer ratings, and decision record. Do not recopy source HEICs into run directories.
- Record baseline and candidate effective settings, requested and resolved model IDs, provider, full resolved prompt and prompt hash, effective parameters, which values were inherited or overridden, input hashes, pipeline/harness Git revisions, SDK versions, timestamps, per-attempt latency, response status, errors, and usage when returned. Store dated cost estimates separately and label them. Redact credentials and signed URLs.
- On resume, verify schema, fixture hashes, and configuration hashes. Never append results from a changed configuration. Keep recorded failures by default; retry only with `--retry-failed`.

**Exit check:** offline serialization round-trips a complete successful and failed run, and resumed runs reject mismatched configuration hashes.

### Phase 3 — Provider adapters and safe runner

- Put the harness outside `packages/pipeline/src` (for example top-level `evals/model-upgrade/`) so it is not copied into the Lambda image or bundled macOS runtime. Add a local CLI with explicit task, fixture set, one candidate override config path, output directory, and run ID options. The baseline is automatically resolved from the existing pipeline setup at the recorded revision; the candidate is that baseline plus the sparse overrides in the file.
- Before provider refactors, add characterization tests for current passthrough-on-error, retry classification, and confidence gating. Refactor each provider boundary into a lower-level structured result containing status, raw response/bytes, parsed output, usage, attempts, latency, and error class. Keep production wrappers and their passthrough behavior unchanged. The harness consumes structured results and records API errors, parse failures, and truncation as failures, with truncation a distinct class. Merging changes under `packages/pipeline/src` triggers the configured Lambda deploy.
- Add offline isolation tests with sentinel production key/base-URL environment variables, proving they never reach clients, and prove missing eval keys fail before client construction. Build provider clients with explicit keys and base URLs; never import `src.cli`.
- Before the first paid request, make a cheap authenticated preflight for each selected provider and abort on authentication/permission errors.
- The command loads the canonical crop path from the fixture manifest and passes those exact bytes to the selected stage adapter; it has no code path that invokes photo splitting or an earlier pipeline step.
- Default to a dry run that lists selected fixtures, providers, model IDs, request count, and cost estimate or configured maximum. Require an explicit execution flag and a budget/call cap before sending paid requests.
- Read `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY` from project-root `secrets.json`; ignore other entries. Reuse or extend `load_secrets()` with the repository-root path explicitly supplied and environment fallback disabled. Fail before client construction if file/key is missing. Do not access AWS, user settings, or deployed app. Never log keys.
- Resolve omitted prompts, model settings, and parameters from the existing production setup; call the existing prompt builder when no prompt override is present. Capture the effective baseline and candidate configurations. Initial support is Anthropic orientation and OpenAI `images.edit` glare; other step/provider pairs require an implemented adapter.
- Run candidate configurations serially by default to make cost and rate-limit behavior predictable. Store each result immediately so an interrupted run can resume.
- Treat API errors, malformed outputs, truncation, and fallback/passthrough results as failed/degraded, never model outputs. Count every attempt, including retries, against the cap. At the cap, stop, mark remaining combinations `not_run`, and preserve resumability. Cost is an estimate from a dated pricing table. Dry run shows worst-case attempts (fixtures × configurations × repeats × maximum attempts). Configure repeats and acceptance thresholds before starting; default orientation repeats to more than one.

**Exit check:** mocked-provider execution proves dry-run, budget guard, key validation, error capture, and resume behavior without network access.

### Phase 4 — Task evaluators

- **Orientation:** compute raw and confidence-gated effective rotation accuracy from non-ambiguous labels; report denominator, confidence distribution, low-confidence/pass-through rate, structured-output failures, repeat agreement, and false-flip rate. Keep ambiguous cases visible but outside accuracy calculations. Store candidate scene descriptions; acceptance requires a baseline glare run with candidate descriptions or a recorded waiver.
- **Glare removal:** compute dimensions/resolution changes and provide a blinded comparison for baseline and candidates against the same canonical, upright glare-stage crop. Include that crop and an optional precomputed glare overlay. Collect ratings for glare reduction, detail preservation, changed/hallucinated content, color shifts, and overall preference.
- Randomize left/right using a recorded seed and neutral candidate labels. Normalize preview size, hide dimensions/latency/cost until ratings are saved, keep model mapping out of the review page, and export ratings JSON for a separate `reveal` CLI. Reference the exact glare crop.
- Do not use SSIM, pixel difference, or an LLM judge as the sole glare quality score. Show these only as optional diagnostics if later evidence supports them.

**Exit check:** known orientation labels produce expected aggregate metrics; a reviewer can rate all glare pairs without seeing model IDs, then reveal and export ratings.

### Phase 5 — Summary, decision, and docs

- Write a machine-readable summary with coverage, metrics, failures, per-attempt latency, available provider usage, and cost estimates from a dated/versioned pricing table clearly labelled as estimates. Include local-only fixture use and provider account/data-retention reference.
- Generate a local HTML review page with normalized previews, canonical glare-crop context, randomized comparisons, and downloadable ratings JSON (or a small local server). Do not embed model mapping or reveal dimensions/latency/cost before ratings are saved. A separate `reveal` CLI joins ratings with the mapping.
- Add a decision record with run ID, reviewer, date, accepted/rejected/inconclusive status, rationale, and known limitations. The harness reports evidence; it never updates production defaults.
- Document fixture preparation, project-root `secrets.json` setup, dry-run and execution commands, spend limits, run artifact locations, privacy rules, and the model-upgrade review checklist.

**Exit check:** one end-to-end small evaluation creates a complete report and decision artifact; no run artifact or credential is tracked by Git.

### Phase 6 — Offline tests and first pilot

- Add characterization tests before provider refactors for production passthrough-on-error, retry classification, and confidence gating. Add offline tests for manifest/provenance/hash validation, schemas, redaction, prompt/config hashing, orientation and repeat metrics, resume and retry-failed, randomized blind labels/seed, ratings export/reveal, report generation, cap behavior, model-ID drift, and client isolation. Mock provider SDK responses; tests must not contact providers.
- Add an autouse eval-test fixture that blocks network and SDK client construction unless mocked; include the offline eval tests in CI and update workflow path filters. No live API evaluation runs in CI.
- Before comparing a full fixture set, manually run a deliberately small, approved fixture subset using explicitly configured eval keys and a conservative budget. Review outputs and artifact redaction, then document the pilot run ID and any spec changes.

**Exit check:** all acceptance criteria above pass, the pilot is reviewed by a human, and a model change remains a separate explicit decision.

### Phase 7 — Promote an accepted model (separate production change)

An `accepted` decision does not change production behavior. Promotion is a separate, explicit production-code change that follows the repository's normal feature-branch, review, and deployment process.

- Create a production change that applies the accepted provider/model, prompt, and request-parameter values to the relevant pipeline step. If the provider changes, include the required production client, credential, permissions, and failure-handling integration. Do not copy the eval-only config file into runtime configuration or expose model selection to end users.
- Reference the accepted run ID and decision record in the change description. Confirm the production implementation resolves to the same effective configuration as the accepted candidate, accounting for any deployment-specific settings.
- Update or add offline regression tests and user/developer documentation for the production default. Run the repository's relevant checks and review the diff through the normal PR process.
- Deploy through the existing release workflow after approval. The eval harness does not merge, deploy, or mutate production defaults.
- After deployment, retain the decision/run record and mark the promoted configuration as the new evaluation baseline for future comparisons.

**Exit check:** the reviewed production change is deployed through the normal process, and a future evaluation can identify it as the baseline.

## Out of scope

- Automatically selecting or deploying a winning model.
- A provider-hosted evaluation service or centralized database.
- Using one LLM as the sole judge for image restoration quality.
- Evaluating page detection/photo splitting or other upstream image-processing steps through these model-stage comparisons; those retain their separate regression/integration tests.
- Expanding the product UI to expose model selection to end users.
- Running a live comparison as part of ordinary CI.
