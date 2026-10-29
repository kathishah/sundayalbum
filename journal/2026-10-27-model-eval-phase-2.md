# Model evaluation harness — Phase 2 (2026-10-27)

Added `evals/model-upgrade/records.py` as the versioned local run format.
Each run has immutable effective baseline/candidate settings and hashes,
fixture hashes, code revisions, SDK versions, review context, and creation
time. Every provider attempt and per-fixture result is written atomically to
its own JSON file; summaries and decisions have separate files. The run
directory is ignored by Git.

Resume verifies schema version, task, fixture set, fixture hashes, and both
configuration hashes before accepting more results. Recorded failures remain
available for the runner to preserve by default. Records redact credential
fields, strings resembling secret keys, and signed URLs before writing.

Offline tests round-tripped a successful and failed result, verified mismatched
resume rejection, redaction, and decision validation. All four tests passed;
Python compilation and `git diff --check` passed. No provider call was made.
