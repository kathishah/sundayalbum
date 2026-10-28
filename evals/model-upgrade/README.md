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
