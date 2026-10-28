# Model evaluation harness — orientation fixture expansion (2026-10-28)

## Review and decision

The owner reviewed the full v1 orientation report and asked for more 180°
examples featuring objects. The v1 run remains `orientation-full-20261028`.
Its local decision record is `inconclusive`: Haiku 5.5 repeatedly chose 270°
for the approved 180° car crop, while the initial set was too narrow for a
final model choice. The owner explicitly placed the glare evaluation on hold.

The production photo splitter extracted two crops from
`test-images-2/IMG_1247.HEIC`. It numbered the bottom city waterfront image
`01` and the top water-ride image `02`. Both extracted crops were upright.
The owner inspected both crops, directed that each be pre-rotated 180° for
use as a fixture, then approved the exact rotated images and 180° correction
labels. The two derived inputs remain local-only; no image bytes were
committed or added to a public release.

## Frozen v2 fixture set

Manifest `approved-2026-10-28-v2` adds these orientation-only cases:

| Case | Position | Derived input SHA-256 | Expected correction |
| --- | --- | --- | --- |
| `test-images-2-img_1247-01-rot180` | bottom city | `64e934e488e486c9c7d78bf781332759850ab9b98ffeb062b9f0159c1cbc6050` | 180° |
| `test-images-2-img_1247-02-rot180` | top water ride | `b01b4f64769496e9d2c8f20e67c9c9212fb11f02e4f3ac49cd9bf12355d03fbf` | 180° |

The derivation was Pillow 180° rotation of the production split crop, saved
as JPEG quality 95 with subsampling 0. The manifest records source HEIC and
source crop hashes, crop geometry, extraction environment, and transformation.
The fixture schema now validates and fetches only the stages declared in a
case's task tags, and the runner selects only cases for the requested task.
This keeps the new cases out of the later glare evaluation.

Validation found 22 matching local crop files: 12 orientation inputs and the
existing 10 glare inputs. All 26 offline eval tests and Ruff checks passed.
Dry runs selected 12 orientation cases and 10 glare cases without contacting
providers. The fixture/schema phase was committed and pushed as `dabf405`
before starting the next paid run.

## Focused orientation run

Run `orientation-object-180-20261028` compared Haiku 4.5 and Haiku 5.5 on
only the two new approved inputs, with three repeats per arm and no retries.
All 12 responses parsed, and there was no model-ID drift. Both models returned
180° with high confidence for the upside-down city crop in all three repeats.
Both returned 270° with high confidence for the upside-down water-ride crop in
all three repeats, missing its approved 180° label. Each model therefore
scored 3/6 on this focused set, and neither met the predeclared 100% rotated
accuracy threshold. The dated combined cost estimate was $0.017690. A scan of
run JSON and HTML found no full provider key.

This focused result does not establish that Haiku 5.5 improves orientation
over Haiku 4.5. The run's ignored local `review.html` awaits owner review;
there is no acceptance or production promotion. Glare remains on hold until
the owner lifts that hold.
