# Model upgrade evaluations

The approved, frozen crop manifest is `fixtures.json`. Crop bytes are excluded from Git.
`orientation/` contains frozen photo-split outputs and explicitly derived
orientation challenges; `glare/` contains separately prepared upright inputs.
The runner must use these bytes directly.
The v2 fixture set adds two owner-approved, local-only orientation challenges
from `test-images-2/IMG_1247.HEIC`. Their inputs are explicitly derived by
rotating the extracted city and water-ride crops 180°; both require a 180°
correction. The manifest records the source crop hash and derivation. These
orientation-only cases have no glare-stage input, and the runner selects cases
by their task tags. The earlier v1 run remains a separate, immutable result.

Validate all local crops:

```bash
.venv/bin/python evals/model-upgrade/fixtures.py validate
```

Fetch the released core crops (the `test-images-2` and `test-images-3` cases are
local-only until separately approved for publication):

```bash
.venv/bin/python evals/model-upgrade/fixtures.py fetch
```

To prepare new drafts, run `build_fixtures.py`. It executes only the production
load-through-photo-split sequence and refuses to overwrite a draft directory.
`--refresh` regenerates in a temporary location and reports changed hashes;
it does not change frozen files or the manifest. `prepare_review.py` makes
provisional upright variants. A human must review each exact draft crop and
label before freezing a new manifest revision. Never run either script during
an evaluation.

Candidate configs in `configs/` are sparse overlays on production settings.
An optional `--baseline` config is also a sparse overlay on production
settings. This lets a reviewed model serve as the **evaluation baseline**
without changing the deployed pipeline default. Each arm resolves
independently, and the run records both effective configurations and hashes.
The Haiku 5.5 config is for orientation. It disables default adaptive thinking
and requests schema-constrained JSON: the first pilot exhausted the inherited
256-token limit on thinking, and the second emitted prose before JSON. These
request overrides were required for a production-compatible parsed result.
The image 2.5 Flare config is for a
later, separate glare evaluation; the two tasks must never share a live run.
Flare omits the production `input_fidelity=high` setting because its edits API
rejects that parameter for this model. The baseline keeps its production
setting; the candidate override records `null` to request omission.

The runner is a dry run by default. It reads the manifest's stored crop bytes
and does not execute any upstream pipeline step:

```bash
.venv/bin/python evals/model-upgrade/runner.py orientation \
  --candidate evals/model-upgrade/configs/haiku-5-5.json
```

A paid run requires `--execute`, a call cap, an estimated spend limit, and a
link to that provider's data-retention terms. The run records the last eight
characters of the selected API key as its billing identifier; it never stores
the full key.
The only credential source is the project-root gitignored `secrets.json`.
SDK clients are constructed with explicit keys and official base URLs; the
runner does not use environment fallbacks. Run artifacts go to ignored
`eval-runs/<run-id>/`. A stopped run can resume with `--resume --run-id <id>`;
recorded failures are kept unless `--retry-failed` is supplied.
When the attempt cap stops a retry, the attempted job remains `failed`; only
jobs with no attempts are marked `not_run`.

Orientation runs score raw and production confidence-gated rotation against
reviewed labels. Ambiguous crops stay visible but do not enter accuracy
denominators. The default predeclared orientation thresholds are 100% accuracy
on real rotated crops and 80% on upright crops; override with a JSON map in
`--thresholds` before execution.

Glare runs produce `review.html` and a separate historical `blind-map.json`.
The page shows the original crop and equal-size previews labelled Baseline and
Candidate with their model names. For each crop, choose Baseline, Candidate,
or Tie; there are no 1–5 ratings. Download `ratings.json`, then validate and
summarize the choices with:

```bash
.venv/bin/python evals/model-upgrade/review.py reveal eval-runs/<run-id> \
  --ratings /path/to/ratings.json
```

The `reveal` command retains its existing name for compatibility. It validates
complete pair coverage and preference values, then writes model names and
preference counts to `revealed-ratings.json`. Legacy blind ratings remain
readable, but new review pages export the simpler version 2 format.

## Paid execution and review

Put only the applicable provider keys in the project-root `secrets.json`:

```json
{"ANTHROPIC_API_KEY": "...", "OPENAI_API_KEY": "..."}
```

This file and all run artifacts are ignored by Git. The runner reads neither
AWS Secrets Manager nor user BYOK settings. It never uploads source HEICs; it
sends only the selected exact crop bytes. The seven orientation cases from
`test-images-2`/`test-images-3` remain local-only. Five of those also have
local-only glare-stage inputs. None of these bytes may be included in a public
release or committed output.

Run orientation first. The command below is an example budget for one case,
three repeats, and at most one retry per arm. Check the dry-run count and
estimate immediately before execution; adjust caps to your chosen scope.

```bash
.venv/bin/python evals/model-upgrade/runner.py orientation \
  --candidate evals/model-upgrade/configs/haiku-5-5.json \
  --cases test-images-img_two_pics_vertical_horizontal_normal-01

.venv/bin/python evals/model-upgrade/runner.py orientation \
  --candidate evals/model-upgrade/configs/haiku-5-5.json \
  --cases test-images-img_two_pics_vertical_horizontal_normal-01 \
  --execute --max-attempts 12 --max-estimated-usd 0.24 \
  --retention-url https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
```

The spend value is a **dated planning estimate**, not a billing limit enforced
by the provider. The attempt cap is enforced by the runner, including retries.
The CLI prints the generated run ID. Results, attempts, raw outputs,
normalized previews, `summary.json`, and `review.html` live in
`eval-runs/<run-id>/`. A resume requires the same candidate and fixture set:

```bash
.venv/bin/python evals/model-upgrade/runner.py orientation \
  --candidate evals/model-upgrade/configs/haiku-5-5.json \
  --cases test-images-img_two_pics_vertical_horizontal_normal-01 \
  --run-id <run-id> --resume --execute --max-attempts 12 \
  --max-estimated-usd 0.24 \
  --retention-url https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
```

After reviewing orientation output, a separate glare run can validate its
candidate scene descriptions against the baseline glare model. Use an empty
candidate `steps` map and `--scene-descriptions-from eval-runs/<orientation-run-id>`.
An accepted orientation decision requires that run or a documented waiver.

Only after orientation review, run glare as a separate evaluation:

```bash
.venv/bin/python evals/model-upgrade/runner.py glare \
  --candidate evals/model-upgrade/configs/image-2.5-flare.json
```

To compare the two GPT Image 2.5 variants directly, use Flare as the
evaluation baseline and Sunburst as candidate:

```bash
.venv/bin/python evals/model-upgrade/runner.py glare \
  --baseline evals/model-upgrade/configs/image-2.5-flare.json \
  --candidate evals/model-upgrade/configs/image-2.5-sunburst.json
```

Both configs omit the unsupported `input_fidelity` parameter. This command is
a dry run until the usual `--execute`, call cap, estimated spend limit, and
retention URL are supplied.
The glare harness requests exactly one image per call (`n=1`); an `n` override
in either arm is rejected.

The current OpenAI [pricing guide](https://developers.openai.com/api/docs/guides/image-generation)
lists equal token rates for 2.5 Flare and Sunburst; Flare is the tie-break
candidate. Record the selected key suffix and the applicable
[data-control terms](https://developers.openai.com/api/docs/guides/your-data)
on any paid glare run. The default dry run shows its separate attempt count
and planning estimate. After choosing a preference for every pair, download
ratings JSON, run `review.py reveal`, and inspect `revealed-ratings.json`.

Record a decision with reviewer, rationale, and limitations:

```bash
.venv/bin/python evals/model-upgrade/decision.py eval-runs/<run-id> inconclusive \
  --reviewer 'Your name' --rationale 'More examples are needed'
```

For an accepted orientation decision, supply `--glare-validation-run` or a
reason in `--scene-description-waiver`. For accepted glare, saved and revealed
ratings are required. A decision does not change pipeline defaults. Promotion
requires a separate production-code change and review.

Review checklist: verify all intended fixtures and hashes; inspect failures,
confidence gating, per-case agreement, and model-ID drift; review the labelled
glare pairs and saved preferences; compare estimated cost and latency; record any
privacy or corpus limits; then decide accepted, rejected, or inconclusive.
