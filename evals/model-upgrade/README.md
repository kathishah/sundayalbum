# Model upgrade evaluations

The approved, frozen crop manifest is `fixtures.json`. Crop bytes are excluded from Git.
`orientation/` contains the exact unrotated photo-split output; `glare/` contains
separately prepared upright inputs. The runner must use these bytes directly.

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
The Haiku 5.5 config is for orientation. The image 2.5 Flare config is for a
later, separate glare evaluation; the two tasks must never share a live run.

The runner is a dry run by default. It reads the manifest's stored crop bytes
and does not execute any upstream pipeline step:

```bash
.venv/bin/python evals/model-upgrade/runner.py orientation \
  --candidate evals/model-upgrade/configs/haiku-5-5.json
```

A paid run requires `--execute`, a call cap, an estimated spend limit, the
provider account label, and a link to that provider's data-retention terms.
The only credential source is the project-root gitignored `secrets.json`.
SDK clients are constructed with explicit keys and official base URLs; the
runner does not use environment fallbacks. Run artifacts go to ignored
`eval-runs/<run-id>/`. A stopped run can resume with `--resume --run-id <id>`;
recorded failures are kept unless `--retry-failed` is supplied.

Orientation runs score raw and production confidence-gated rotation against
reviewed labels. Ambiguous crops stay visible but do not enter accuracy
denominators. The default predeclared orientation thresholds are 100% accuracy
on real rotated crops and 80% on upright crops; override with a JSON map in
`--thresholds` before execution.

Glare runs produce `review.html` and a separate `blind-map.json`. The page
shows the original crop and padded, equal-size left/right previews. It does
not contain model identities, dimensions, latency, or cost. Rate every field
and download `ratings.json`, then reveal with:

```bash
.venv/bin/python evals/model-upgrade/review.py reveal eval-runs/<run-id> \
  --ratings /path/to/ratings.json
```

The reveal command validates pair coverage and rating values before joining
the saved ratings to the private arm mapping.
