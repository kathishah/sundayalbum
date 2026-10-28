# Model evaluation harness — Phase 6 (2026-10-27–2026-10-28)

## Offline gate complete

Eval tests now use generated synthetic crops instead of the ignored local
corpus. An autouse fixture blocks network connections and real Anthropic/OpenAI
SDK client construction, so CI can exercise manifest validation, hash tamper
rejection, run records, redaction, exact-byte transmission, prompt inheritance,
unsupported provider rejection, budget and key guards, attempt caps, resume,
retry-failed, output parsing, model drift, scoring, blind review, cost estimates,
and decisions without a paid request.

The `test-api.yml` workflow now triggers on eval code/tests and relevant
pipeline provider modules, and runs API, handler, and offline eval tests.
Locally, 64 combined tests passed; 24 of those were eval tests. Ruff checks
passed after formatting the harness and test files. All 20 approved crop
hashes still validate. Both full-corpus task dry runs succeed independently.

The blind page no longer exposes the randomization seed. It carries an opaque
review ID for ratings export; the seed and arm mapping remain in the private
run file. Resume now checks immutable review context in addition to fixture
and effective configuration hashes. Decision acceptance checks actual baseline
glare coverage when linked as orientation scene validation.

## Small orientation pilot (2026-10-28)

The owner directed that paid run metadata identify the selected credential by
its last eight characters. The runner now derives and stores that suffix after
reading the local key; it never prints or stores the full key. A scan of all
three pilot run artifacts confirmed that neither full provider key appears.

Three deliberately small orientation pilots used one approved 270° crop,
one repeat, two configurations, no retries, and a two-attempt cap per run:

1. `orientation-pilot-20261028`: baseline correct; Haiku 5.5 exhausted
   `max_tokens=256` almost entirely on default adaptive thinking and stopped
   before a text answer. The harness recorded `truncated`.
2. `orientation-pilot-2-20261028`: with thinking disabled, baseline correct;
   Haiku 5.5 returned explanatory text before valid JSON. The production-style
   strict parser rejected it as `parse_failure`.
3. `orientation-pilot-3-20261028`: with thinking disabled and Anthropic's JSON
   schema output constraint, both models returned 270° with high confidence.
   Both jobs succeeded; the dated combined cost estimate from reported usage
   was $0.002955. Full keys were absent from run JSON and HTML.

The candidate config now captures both request overrides. The adapter selects
the text content block by type, as Anthropic recommends for newer models.
Offline tests (24) and Ruff checks passed after these changes. The owner
reviewed the successful pilot and approved the full orientation run.

## Full orientation evaluation (2026-10-28)

Run `orientation-full-20261028` evaluated all 10 approved crops with three
repeats per arm, no retries, and 60 total attempts. The run used only the
orientation step. Its ignored local artifacts are in
`eval-runs/orientation-full-20261028/`, including `review.html` and
`summary.json`. The five crops from `test-images-2`/`test-images-3` remain
local-only.

Haiku 5.5 returned 30/30 parseable outputs and agreed across all three
repeats on every crop. It chose 270° on
`test-images-img_two_pics_vertical_horizontal_normal-02`, whose approved
label is 180°, on all three repeats. It was correct on the other nine crops:
27/30 overall and 12/15 on the real rotated cases. Its upright accuracy was
9/9 and false-flip rate was zero. The predeclared 100% rotated-case threshold
was therefore **not met**. No production model change is justified by this
result.

The Haiku 4.5 baseline had four parse failures across two upright crops,
leaving 26/30 parseable outputs. All 26 parsed baseline rotations matched the
approved labels. The summary's paired comparison uses only the 24 repeats
where both arms parsed: 24/24 baseline versus 21/24 candidate. The candidate's
27/30 figure above is its own unpaired output accuracy, so the two
denominators must not be conflated. No requested/returned model-ID drift was
detected. The combined dated cost estimate from reported usage was $0.086929;
all attempts had available cost estimates. A scan of run JSON and HTML found
neither full provider key; only the selected key's last eight characters are
recorded in metadata.

The full report needs owner review and an explicit orientation decision before
any glare evaluation. No glare calls have started. The harness implementation
and offline gate are complete; production promotion remains a separate phase.
