# Model evaluation harness — Phase 6 (in progress, 2026-10-27)

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

The small paid pilot and human artifact review are pending the provider billing
account label required in run metadata. No live provider request has been made
by this phase yet.
