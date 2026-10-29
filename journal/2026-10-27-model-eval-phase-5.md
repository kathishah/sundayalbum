# Model evaluation harness — Phase 5 (2026-10-27)

The runner now writes a complete `summary.json` with fixture coverage,
effective baseline/candidate settings and hashes, task metrics, all errors,
per-attempt usage, latency, model-ID drift, provider-account label, retention
reference, and local-only case IDs. `pricing-2026-10-27.json` records dated
official rates for the two Anthropic and three relevant OpenAI image model
IDs. Dollar values are explicitly estimates; missing or incomplete provider
usage is marked, never silently treated as zero cost.

Orientation runs now create a visual `review.html` with each exact crop and
per-repeat model labels alongside the machine-readable score. Glare runs
retain the blinded page and separate mapping. A decision CLI records reviewer,
date, accepted/rejected/inconclusive status, rationale, limitations, and
evidence. It cannot change production defaults. Accepting orientation requires
a linked glare validation run using candidate scene descriptions or an explicit
waiver; accepting glare requires saved and revealed ratings.

The developer README now documents fixture setup, strict local keys, separate
orientation and glare commands, budget and attempt caps, resume, privacy,
retention references, run artifacts, blind review, and the decision checklist.

Offline tests covered dated cost calculations, missing usage, complete summary
fields, and a mocked end-to-end run with report and decision files. All 20
eval tests passed, along with Python compilation and diff checks. No live
provider call was made.
