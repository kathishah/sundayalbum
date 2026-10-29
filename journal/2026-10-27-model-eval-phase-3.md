# Model evaluation harness — Phase 3 (2026-10-27)

Added a local CLI that selects exactly one model-backed stage per run. It
loads only approved manifest crops, checks their SHA-256 hashes, resolves the
current pipeline settings plus a sparse candidate overlay, and captures full
case-specific prompts, prompt hashes, request parameters, requested model IDs,
and value sources. The production orientation prompt was extracted into a
builder without changing its text or fallback behavior.

Dry run is the default and prints fixture count, models, repeats, worst-case
attempts, a dated planning cost estimate, and local-only fixture count. Paid
execution requires `--execute`, an attempt cap, an estimated spend limit,
provider account label, and data-retention URL. The runner reads only selected
keys from the project-root `secrets.json`; missing keys fail before client
construction. Clients receive explicit official URLs and have SDK retries
disabled. A model lookup preflight runs before any image request.

Anthropic orientation and OpenAI `images.edit` adapters capture raw provider
response metadata, parsed output, resolved model, usage, latency, and error
class. Truncation, malformed JSON, API errors, and missing images are failures.
The OpenAI returned PNG is saved unchanged. The runner writes every attempt
immediately, counts retries against the global cap, marks remaining work
`not_run`, and resumes only when fixture/configuration hashes match. Runs are
serial. No upstream pipeline stage is invoked during evaluation.

The structured adapters live in the local harness so production API fallback
and retry behavior remain untouched. Characterization tests were written
before the prompt refactor for production pass-through, confidence gating, and
OpenAI retry classification.

Offline verification: 16 eval tests passed, including exact-byte transmission,
dry-run isolation, key/budget guards, error classification, attempt cap,
resume, and explicit client URLs. Both task dry runs succeeded. No live model
request was made.
