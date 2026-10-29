# Model evaluation harness — Phase 4 (2026-10-27)

Orientation scoring now reports raw and production confidence-gated accuracy,
separate real rotated/upright scores, denominator counts, confidence
distribution, low-confidence pass-through rate, false-flip rate, structured
output failures, per-case repeat agreement, ambiguous exclusions, and scene
descriptions. Default acceptance thresholds are recorded before paid requests.

Glare scoring records native output dimensions and pixel-area ratio outside
the blind page. The generated HTML shows the original upright crop and two
fixed-size padded previews in a seeded random left/right order. It offers
1–5 ratings for glare reduction, detail preservation, changed content, and
color shift on both sides, plus an overall preference. It downloads ratings
JSON without needing file write access. Model mapping lives only in a separate
`blind-map.json`; the HTML contains no model IDs, arm labels, latency,
dimensions, or cost. `review.py reveal` validates complete ratings before
joining them to the mapping.

Offline tests verified known orientation labels and confidence gating,
ambiguous exclusions, blind HTML, normalized previews, native dimensions, and
ratings reveal. All 18 eval tests passed. No provider call was made.
