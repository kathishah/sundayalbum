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
preference dropdowns. The owner's choices are pending; no glare decision has
been recorded.
