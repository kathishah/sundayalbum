# Security findings F1–F8: reassessment and branch implementation

Rechecked the October 24 assessment against `origin/dev` at `ace87d8` before making
changes. All eight findings remained present. Implemented the fixes on local branch
`security/f-series` in a separate worktree.

## Changes

- **F1:** Count today's jobs from the ULID range beginning at UTC midnight, paginate,
  and fail closed when DynamoDB cannot verify the count.
- **F2:** Use S3 presigned POST with a 1-byte to 200-MB content-length policy; update
  the web client and S3 CORS methods.
- **F3:** Increment verification attempts atomically with a maximum-attempt condition;
  fail closed on storage errors.
- **F4:** Generate verification codes with `secrets.randbelow`.
- **F5:** Remove user API keys from Step Functions inputs and fetch them from the
  settings table in pipeline handlers. Reject API-key fields in reprocess config.
- **F6:** Resolve the default local `secrets.json` path at repository root.
- **F7:** Configure the API and load handler from the same extension setting, support
  `.heif` and case-insensitive suffixes, and scope uploaded objects by job.
- **F8:** Authenticate WebSocket connections and verify job ownership before storing
  the connection.

## Verification

- `pytest tests/api/ tests/handlers/ tests/evals/ tests/test_secrets.py -q`: **81 passed**.
- Web typecheck, lint, and production build: **passed**.
- Ruff diagnostics on changed Python files: **0 new diagnostics** compared with
  `origin/dev` (the baseline itself has existing lint findings).
- Read-only Step Functions input review: inspected 62 dev and 7 prod executions
  starting on or after 2026-10-24. None contained nonempty `user_keys` or API-key
  fields in config. No key values were printed.

## Remaining deployment steps

No push, PR, workflow, CDK diff, or deployment was done. CDK changes need the owner to
run `cdk diff` and deploy with the admin e-mail setting preserved, as described in
`docs/OPERATIONS.md`. The implementation is currently combined on one branch; split
it into one PR per finding before creating PRs if following the original PR plan.
