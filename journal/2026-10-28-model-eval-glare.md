# Model evaluation harness — glare evaluation (2026-10-28)

## Scope and first pilot

The owner lifted the glare hold and authorized the separate glare evaluation.
The orientation acceptance and production defaults remain unchanged. The v2
manifest validates 10 glare-stage crops (five released core cases and five
local-only cases); the two new `IMG_1247` orientation-only cases are excluded.
The first dry run selected 10 fixtures, one repeat, no retries, and at most
20 calls with a dated $6.00 worst-case planning estimate.

Official OpenAI [pricing](https://developers.openai.com/api/docs/pricing)
lists equal GPT Image 2.5 Flare and Sunburst image/text token rates. Flare is
the already selected tie-break candidate. The [image edit API reference](https://developers.openai.com/api/reference/resources/images/methods/edit)
documents model-specific `input_fidelity` support.

The small paid run `glare-pilot-20261028` used only the approved local-only
cave-reflection crop, one baseline/candidate pair, and a two-attempt cap.
`gpt-image-1.5` returned an image. The `gpt-image-2.5-flare` request failed
with HTTP 400: the model does not support inherited `input_fidelity=high`.
The failed candidate request produced no image and had no available usage/cost
estimate. The baseline's dated usage estimate was $0.251439. This pilot is
not a valid quality comparison.

The candidate config now explicitly sets `input_fidelity` to `null`, and the
adapter omits the parameter when null. The baseline still sends its production
`high` value. An offline provider test checks both behaviors. All 27 offline
eval tests and Ruff checks passed. The fix was committed and pushed as
`3bd860a` before another paid call.

## Corrected pilot

Run `glare-pilot-2-20261028` repeated the same one-crop comparison under a
new immutable run ID. Both arms succeeded and returned valid 1536×1024 PNGs;
there were no provider errors or model-ID drift. The dated combined cost
estimate from available usage was $0.304700. The blind review page hides the
model names and keeps its arm map separate. A scan of JSON and HTML found no
full API key. This establishes that the current request configuration and
review artifacts work for both models; image quality still needs blind human
ratings. The next phase is the full ten-crop glare run.

## Full glare comparison

Run `glare-full-20261028` evaluated all 10 approved glare-stage crops (five
released core cases and five local-only cases), one repeat per arm, no
retries, and a 20-attempt cap. All 20 jobs succeeded and yielded valid PNGs.
There were no provider errors, not-run jobs, missing cost estimates, or
requested/returned model-ID mismatches. The run's dated combined estimate
from provider usage was $3.050472, below the $6.00 planning cap; this is not
a provider-reported bill. Median per-attempt latency was 30,637.5 ms.

The initial local `review.html` contained ten blinded pairs and a separate
private arm map. Model names were absent from that first page. A scan of run
JSON and HTML found no full provider key. These checks established complete
artifacts; they did not establish which model removes glare better or preserves
details. No production glare model has changed.

## Review simplification after owner feedback

The owner found the two sets of 1–5 criteria difficult to use and requested
direct Baseline/Candidate labels and a single preference per crop. The page
builder now shows the model names over equal-size previews beside the
original, with only Baseline, Candidate, or Tie as choices. The download uses
ratings schema version 2. The existing `reveal` CLI validates complete pair
coverage and preference values, then records model IDs and preference counts;
it still accepts legacy version 1 ratings for earlier reports. The private
randomization map remains in the run for audit but is no longer needed to
interpret the labelled page.

The existing `glare-full-20261028/review.html` was regenerated from saved
outputs without new provider calls. Its review ID and `blind-map.json` hash
were unchanged. The page has ten original/baseline/candidate triplets and ten
preference dropdowns. The simplified review code and journal were committed
and pushed as `af1dd3d`.

## Owner preferences

The owner saved preferences for all ten pairs, then changed one choice before
the glare decision. The current `ratings.json` has SHA-256
`d586994a8b509a0f193c1f12d2c564a3a1d27afe16aac8d607312c6672921e29`.
The `reveal` validator confirmed complete coverage and produced the following
current tally: nine choices for candidate `gpt-image-2.5-flare`, one for
baseline `gpt-image-1.5`, and no ties. The baseline choice is
`test-images-3-img_1270-01__1` (the shallow-water reflection crop). This
supersedes the initial all-candidate file. No glare decision has been recorded
yet; the owner will confirm the final disposition.

## Sunburst comparison setup

After reviewing the 9–1 result, the owner chose Flare as the **working
evaluation baseline** for a direct comparison with GPT Image 2.5 Sunburst.
This does not change the deployed glare model or rewrite the earlier run.
OpenAI's published standard token rates for Flare and Sunburst are equal;
actual per-run usage may differ.

The runner now accepts an optional sparse `--baseline` overlay. Baseline and
candidate are resolved independently from production settings, so the new
comparison captures Flare and Sunburst with the same canonical crop, prompt,
quality, size, and omitted `input_fidelity` setting. A new Sunburst config
records its model choice. The existing run manifest hashes both effective
arm configurations, and resume continues to reject changed settings. The
ten-crop dry run selects 20 calls with no retries and a dated $6.00 planning
estimate. All 28 offline eval tests and Ruff checks passed. Next is a small
Sunburst pilot on the one crop previously preferred under `gpt-image-1.5`,
followed by a full-set comparison if the pilot succeeds.

## Flare versus Sunburst pilot

The baseline-override code and config were committed and pushed as `6386ce1`
before the pilot. Run `glare-sunburst-pilot-20261028` compared Flare (working
evaluation baseline) and Sunburst (candidate) only on
`test-images-3-img_1270-01`, with one repeat, no retries, and a two-call cap.
Both calls succeeded, returning valid 1536×1024 PNGs. There were no provider
errors, missing cost estimates, or model-ID mismatches. The dated combined
usage estimate was $0.106512; this is not a provider-reported bill. The local
review page correctly labels the two model arms, and no full API key was
found in JSON or HTML artifacts. This verifies the technical path, not image
quality. Next is a separate full ten-crop Flare-versus-Sunburst comparison.

## Full Flare versus Sunburst comparison

Run `glare-flare-vs-sunburst-full-20261028` used the ten approved glare-stage
crops, one repeat per arm, no retries, and a 20-call cap. Flare was the
working evaluation baseline and Sunburst the candidate. All 20 jobs
succeeded and returned valid PNGs; each pair has distinct output bytes.
Five inputs remained local-only. The labelled review page has ten
original/baseline/candidate triplets and one preference selector per crop.
A scan of run JSON and HTML found no full provider key.

The dated combined cost estimate from provider usage was $1.069884:
$0.534942 for Flare and $0.534942 for Sunburst. This is an estimate, not a
provider bill. Median call latency was 19,348 ms for Flare and 32,037 ms for
Sunburst. No provider errors or missing usage were recorded. OpenAI's image
edit responses did not include a resolved model ID, so model identity is
supported by the requested IDs and authenticated preflight rather than a
returned-model comparison. The owner must review the images and save ten
preferences before any Sunburst-versus-Flare decision is recorded. Production
glare settings remain unchanged.
