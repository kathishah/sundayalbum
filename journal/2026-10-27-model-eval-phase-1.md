# Model evaluation harness — Phase 1 (2026-10-27)

## Frozen fixture corpus

The owner reviewed and approved ten exact photo-split crops and their separate
upright glare-stage counterparts. Five crops come from the two required core
album pages, three from `test-images-2`, and two from `test-images-3`.
`IMG_1250-02` was added after the first review sheet omitted its glare partner.
The cave formation and water-reflection cases are marked ambiguous for
orientation accuracy, but remain useful glare cases.

The checked-in `evals/model-upgrade/fixtures.json` records source and crop
SHA-256 hashes, detector coordinates, split provenance, platform, revision,
rotation/flip labels, scene descriptions, tags, and distribution status. The
twenty JPEG crop files live in ignored `test-cropped-images/`, never in Git.
The extras from `test-images-2` and `test-images-3` remain local-only pending a
separate publication decision.

`build_fixtures.py` runs production deterministic steps through photo splitting
only; `--refresh` reports changed hashes without overwriting frozen bytes.
`fixtures.py validate` checked all 20 frozen files, and a refresh reproduced
the ten orientation crop hashes exactly. `prepare_review.py` constructs the
glare-stage variants from approved rotation labels.

The core crop release asset is `v0.0.4-evaldata/eval-crops.zip`. The fetcher
checks each member against the manifest before installing it and refuses to
overwrite a different local file. Local-only crops must be supplied separately.

## Candidate settings

Sparse override configs were added for `claude-haiku-5-5` orientation and
`gpt-image-2.5-flare` glare. OpenAI lists equal standard pricing for Flare and
Sunburst on 2026-10-27, so Flare is the selected tie-break candidate. The
two evaluations will run separately, orientation first.

## Verification

- `fixtures.py validate`: 20/20 crop files passed.
- `build_fixtures.py --refresh`: 10/10 orientation hashes unchanged.
- Python compilation and `git diff --check`: passed.

No provider API call was made in this phase.
