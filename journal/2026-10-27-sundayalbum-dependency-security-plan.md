# sundayalbum: web security and dependency plan (2026-10-27)

Repo `kathishah/sundayalbum` (local checkout `~/dev/sundayalbum`). Written after the October 2026 public-repo cleanup, which turned on Dependabot alerts and security updates. Everything needed is in this file and in `docs/OPERATIONS.md`. Execution started 2026-10-27; section 0 is the live tracker, sections 9-11 hold the results.

## 0. Progress tracker (last updated 2026-10-27, after alert query on main)
Legend: done / in progress / pending / needs owner decision.

| Step | Status | Where | Notes |
|---|---|---|---|
| 1. Sync and branch | done | `dev` pushed with `main` merged | |
| 2. PR check for the web app | done | #87 (merged) | `Build Web` passes; a deliberately broken commit (#88, closed) failed at Type-check |
| 3. Interim mitigation | done | #89 (merged) | `/_next/image` 404 on dev and prod |
| 4. Upgrade (Next 15.5.28, React 19.3.1, Node 24, lockfile fixes) | done | #90 (merged) | local checks and Docker build on node:24-alpine passed |
| 5. Verify on dev | done | dev deploy of #90 | 12 routes 200; Playwright 20 passed / 1 skipped, before and after the upgrade |
| 6. Promote to prod | done | #92 (`b9ce386`), then #96 (`8662550`) | after #96, prod web deploy (run 40555227210) and Lambda deploy (run 40555227063) succeeded; `www` and `app` `/` and `/api/version` returned 200 |
| 7. Dependabot tidy-up | done | see below | #94/#95 promoted; #85 closed; 0 open Dependabot alerts on `main` |

Step 7 detail:

| Item | Status | Next action |
|---|---|---|
| #94 `dependabot.yml`: ignore majors | merged into dev (`72668a6`) and main via #96 | takes effect from `main`; deploys nothing |
| #95 `overrides` for next's vendored postcss (clears 4 alerts; `npm audit` 0) | merged into dev (`efee6c0`) and main via #96; dev web deploy succeeded (run 40551728284) | prod web and Lambda deploys succeeded (runs 40555227210, 40555227063) |
| Closed with comments: #93 (Next 16), #65, #77, #72, #81, #68, #79, #66, #75 | done | none |
| Auto-closed by Dependabot (superseded): #74, #78, #80, #82, #83, #84, #86 | done | none |
| Merged into dev: #67 constructs, #70 pytest 9.1.1, #71 aws-cdk-lib | done | none (no deploy path) |
| #69 rawpy, #76 python-dotenv: merged into dev | done | dev Lambda deploys after each succeeded (runs 40537063888, 40538185202). Note: both only change `requirements.txt` / `requirements-runtime.txt` (the Mac app's runtime), not `requirements-lambda.txt`, so the Lambda image gained no new pins; its unpinned `>=` deps re-resolve on every rebuild |
| #91 web minor/patch group: merged into dev | done | dev web deploy succeeded (run 40539127593); Playwright run 40539943227: 19 passed, 1 flaky, 1 skipped |
| #64 GitHub Actions majors (SHAs verified against tags): merged into dev | done | dev web and Lambda deploys both succeeded on the new actions (runs 40542254827, 40542254778) |
| Playwright on dev after #69/#76/#91 (run 40539943227) | 19 passed, 1 flaky, 1 skipped | `T-sfn-smoke-02` timed out once (240s) and passed on retry; cause unproven (cold starts after the Lambda rebuilds is the likely one). Re-run on final dev state (run 40547099640): 20 passed, 1 skipped |
| #85 pytest 9.0.3 (security PR into `main`) | closed as superseded | #70's pytest 9.1.1 is on `main` via #96 |
| Promote `dev` to `main` (merge commit, no squash) | done, PR #96 merge commit `8662550` | prod web run 40555227210 and Lambda run 40555227063 succeeded; `www` and `app` `/` and `/api/version` returned 200 |
| Re-run alert query on `main` | done: 0 open alerts | checked after #96 and closing #85 |

Remaining order (each step needs the owner's explicit OK; approvals do not carry over between sessions): (1) re-run Playwright on dev — done, run 40547099640 (20 passed, 1 skipped); (2) merge #94 and #95 into dev, including the local journal commits — done; (3) promote `dev` to `main` with a merge commit — done, PR #96 commit `8662550`; prod web and Lambda deploys succeeded; (4) close #85 and re-run the alert query on `main` — done, #85 closed and 0 open alerts; (5) update this tracker — done; (6) re-check the orientation difference in prod (non-blocking follow-up; deferred here because it requires production photo processing in AWS, which is outside the owner's no-AWS instruction).

Gotchas: Dependabot reads `dependabot.yml` from `main` and evaluates alerts on `main`; its security PRs target `main` and must not be merged directly; Playwright tests the deployed dev site; GitHub shows mergeable `UNKNOWN` for a few seconds after a merge; `requirements-lambda.txt` is unpinned, so every Lambda rebuild re-resolves it.

Open Dependabot alerts after #96 (on `main`): 0, including 0 critical.

Follow-ups, none started: **photo orientation differs between the local macOS venv and the Linux Lambda image** (two_pics Photo01 rotated 90 degrees, three_pics Photo01 rotated 180 degrees, AI orientation off; cause unproven, see section 12). Re-check it in prod with AI orientation on; deferred here because it requires production photo processing in AWS, which is outside the owner's no-AWS instruction; not a blocker for this plan. Other follow-ups: pin `requirements-lambda.txt` (constraints file); drop the unused `matplotlib` and `scikit-image` requirements; Lambda Python 3.12 to 3.14 as its own task; `/api/version` `is_latest` is always false because it queries commit path `web` instead of `apps/web` (found while reading the route); items in section 7 (OIDC for `test-web.yml`, stale branches, `ADMIN_EMAILS`).

## 1. State on 2026-10-27
- `main` = `bfc66a0` (licence A merged). `dev` = `9600632` (a merge commit that took `main`'s tree as of `f9a8ef6`); `dev` does **not** yet contain the licence commit `bfc66a0`, and merging `main` into `dev` should be clean.
- Deploys: push to `main` deploys **prod** (App Runner `sundayalbum-web-prod`, `www.` and `app.sundayalbum.com`); push to `dev` deploys the dev stage. Path filters: web deploys on `apps/web/**` and its workflow; Lambdas on `services/api`, `services/handlers`, `packages/pipeline`, `Dockerfile`. `[skip ci]` in the head commit message skips both. OIDC role comes from the repo secret `AWS_ACCOUNT_ID` (set 2026-10-26, works: the dev deploy passed).
- 23 open Dependabot PRs (#64-#86). Version updates target `dev`; **security** updates (#80, #82-#86) target `main` because Dependabot ignores `target-branch` for them, so merging those deploys prod.
- **No PR runs any web check.** `test-web.yml` is `workflow_dispatch` only (Playwright); `test-api.yml` runs only for API/handler/pipeline-storage paths. Nothing proves an `apps/web` change still builds before it reaches a deploy.

## 2. Findings
**Next.js 14.2.29 in prod, with 3 critical and 26 high open alerts** (totals: 3 critical, 26 high, 23 medium, 4 low; all in `apps/web/package-lock.json`). Query: `gh api repos/kathishah/sundayalbum/dependabot/alerts --paginate -q '.[]|select(.state=="open")|[.security_vulnerability.severity,.dependency.package.name,.security_vulnerability.first_patched_version.identifier]|@tsv'`.
- Criticals are three Next.js remote-code-execution advisories (image optimisation with AVIF, with SVG, and Windows-hosted servers). **The patches exist only in 15.x (15.5.24 and 15.5.28); there is no 14.x fix.**
- Applicability, from reading the code (not proven): the app has no `next/image` use, but `/_next/image` is on by default, and `next.config.mjs` allows `*.s3.us-west-2.amazonaws.com`, which matches **any** S3 bucket, so an attacker's bucket is a valid image source. Windows advisory: not applicable. SVG advisory is glibc-only and the container is Alpine (musl): probably not applicable. AVIF advisory: not ruled out. No Server Actions and no middleware, which removes several of the high DoS/SSRF advisories. Treat the exposure as real until the upgrade lands.
- The alerts existed before the cleanup; enabling Dependabot only surfaced them.
- **Node 20 is end-of-life (April 2026).** `apps/web/Dockerfile` uses `node:20-alpine` in three stages; `test-web.yml` pins Node 20. PR #65 proposes `node:26-alpine`.
- `apps/web/package.json`: `next` 14.2.29, `eslint-config-next` 14.2.29, `react`/`react-dom` ^18. Next 15's App Router expects React 19, so PR #80 (Next only) should not be merged alone.

## 3. Decisions
Made by the owner: do the work in a separate session scoped to this repo; verify the build locally before pushing; use `dev` first.
Recommendations awaiting the owner's yes (ask before acting): (a) Node **24**, not 26 (an LTS I am confident about; confirm current LTS status first); (b) interim `images: { unoptimized: true }` in `next.config.mjs` (the app uses no `next/image`; verify no `/_next/image` use first); (c) ignore **major** version updates in `dependabot.yml` (security updates still flow); (d) close the PRs marked "close" in section 5.

## 4. Steps (each ends with its check)
1. **Sync and branch.** `git switch dev && git pull`, merge `main` into `dev` (expect clean), branch `deps/security-2026-10` from `dev`. Pushing `dev` deploys the dev stage: show the command first.
2. **PR check for the web app.** New workflow `.github/workflows/build-web.yml`: on `pull_request` for `apps/web/**` (bases `main` and `dev`), `permissions: contents: read`, actions pinned to SHAs like the other workflows, Node from one place (`.nvmrc` or the Dockerfile version), `npm ci`, type-check, lint, `next build`. Check: it runs and passes on its own PR, and fails on a deliberately broken commit (try it on a throwaway branch).
3. **Interim mitigation** (if approved): `images.unoptimized`. Check: `next build` passes; after the dev deploy, `GET /_next/image?...` no longer optimises.
4. **Upgrade in one branch:** Next to the latest 15.5.x (>= 15.5.28), React/ReactDOM 19, `@types/react*`, `eslint-config-next` to match, Node 24 in `apps/web/Dockerfile` and CI, `@types/node` to the Node major, plus the lockfile security bumps (`npm audit` / Dependabot's #82-#86 content). Read the Next 14 to 15 and React 18 to 19 upgrade guides first; expect async `cookies()/headers()/params`, changed fetch/route-handler caching defaults, and type changes (try `npx @next/codemod@canary upgrade`). Check locally before any push: `npm ci`, type-check, lint, `next build`, then `docker build` of `apps/web` and run the container; click through the public pages, upload flow and login against dev if possible; run the Playwright suite (`test-web.yml` via `workflow_dispatch` on the branch).
5. **PR into `dev`, merge (merge commit, not squash), watch the dev deploy,** click through `dev.sundayalbum.com`. Re-run the alert query: criticals must be 0 for `next`.
6. **Promote:** PR `dev` into `main` with a **merge commit** (squashing is what made `dev` and `main` diverge in October). Merging deploys prod: owner approves, then watch the prod web deploy and check `www.` and `app.sundayalbum.com`.
7. **Dependabot tidy-up** (after 5): add the major-version ignore, then handle the 23 PRs per section 5. Close with a short comment, never merge to clear the list.

## 5. Open Dependabot PRs (as of 2026-10-27)
| PRs | Plan |
|---|---|
| #80 Next 14 to 15.5.28, #78 react-dom | Superseded by step 4; close with a pointer to the upgrade PR |
| #65 node 26-alpine, #77 @types/node 26 | Superseded by step 4 (Node 24); close |
| #82 js-yaml, #83 brace-expansion, #84 source-map-js, #86 postcss-selector-parser/tailwind | Lockfile security patches; fold into step 4 or merge after the build check exists. They target `main`: do not merge to `main` directly |
| #64 actions group (7 updates) | Review the diff, merge into `dev` after the build check, watch the dev deploy |
| #72 TypeScript 7, #81 framer-motion 14 | Close; major ignore |
| #79 Lambda Python 3.14 | Close for now: changes the runtime under OpenCV/rawpy; own task if wanted |
| #66 matplotlib, #75 scikit-image | Close; unused according to the cleanup report (confirm with a grep) |
| #67 constructs, #69 rawpy, #70/#85 pytest, #71 aws-cdk-lib, #74 web minor/patch group, #68 mypy 2, #76 python-dotenv | Python and CDK changes need `pytest` and `cdk diff`; merge only after those pass, else close |

## 6. Guardrails
- Ask before: any push, merge, PR close, Dependabot or repo setting change, and any workflow run on `dev`/`main`. Show the exact commands first. Wait for CI before the next step.
- Never push to `main` directly; `main` requires a PR. Prod deploys follow every merge touching `apps/web`: that is the owner's call each time. Do not use `[skip ci]` for a promotion; do use it for a docs-only merge.
- No AWS write, no `cdk deploy`, no secret change. If a check needs AWS, ask. Mask 12-digit account IDs in output; never print secret values.
- The owner is fine with this plan, and with advisories being named, in the public repo. Commit it as a journal entry with a row in `journal/INDEX.md` (Fixes & decisions), in the first PR into `dev`. PR titles and commit messages may name advisories and package versions; do not describe exploit steps.

## 7. Out of scope here (tracked separately)
Security findings F1-F8; Privacy/Terms/Pricing text that disagrees with the code; the March `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` secrets still read by `test-web.yml` (move to OIDC and rotate); the 40 stale branches; the apex `sundayalbum.com` redirect; the next `cdk deploy` blanking `ADMIN_EMAILS`.

## 8. Unknowns to resolve first
Whether the app builds on Next 15 and React 19 (never tried); whether Playwright still passes; current Node LTS status; whether `/_next/image` is used by any page or the Mac app; whether Dependabot's lockfile PRs conflict with the upgrade branch.

## 9. Owner decisions and findings (added 2026-10-27, start of execution)
Decisions: (a) Node **24** for the Dockerfile and CI; (b) add `images.unoptimized: true` as the interim mitigation; (c) ignore **major** updates in every ecosystem in `dependabot.yml`; (d) the close list in section 5 is approved in principle, with each `gh pr close` still confirmed at step 7.

Findings that resolve or change section 8:
- Node: 20 reached end-of-life 2026-04-30; 24 is LTS (maintenance since 2026-10-20, supported to 2028-04-30); 26 becomes LTS on 2026-10-28 and Next 15.5 only declares `node >=20.9`, so 24 is the conservative pick.
- `/_next/image`: no `next/image` import and no reference to `/_next/image` anywhere in `apps/`, `packages/`, `services/` or `docs/`, including the Mac app. The four `<img>` tags use their `src` directly.
- The highest first-patched `next` version across all open alerts is 15.5.28, which is also the latest 15.5.x on npm.
- Dependabot #82-#86 all edit `package-lock.json`, so they will conflict textually with the upgrade branch; fold their content into it.
- `main` is protected (PR required, admins enforced, no required status checks); `dev` is unprotected. Merging `main` into `dev` touched `apps/web/**`, so pushing `dev` deploys the dev web stage.
- Baseline before any change (Next 14.2.29, Node 22 locally): `next build` passes; `tsc --noEmit` failed on one narrowing error in `tests/e2e/websocket.spec.ts`; `apps/web` had **no ESLint config**, so `next lint` stopped at an interactive setup prompt (it would hang or fail in CI). Fixed in the first PR: `.eslintrc.json` (`next/core-web-vitals`, with `react/no-unescaped-entities` off, which was the only rule failing, 5 times, in marketing copy), a `typecheck` script, the test-file type fix, and `apps/web/.nvmrc` (20 for now, 24 in the upgrade PR).
- Playwright, Next 15 / React 19 build compatibility: still unknown, resolved in step 4.

## 10. Step 4 results (upgrade branch `deps/security-2026-10`)
Done: `next` 15.5.28 (exact pin), `eslint-config-next` 15.5.28, `react`/`react-dom` ^19.3.1, `@types/react*` ^19, `@types/node` ^24, Node 24 in `apps/web/Dockerfile` and `apps/web/.nvmrc` (`test-web.yml` now reads `.nvmrc` too), plus a non-breaking `npm audit fix` for the lockfile (js-yaml 4.3.2, postcss 8.5.32, source-map-js 1.2.2, brace-expansion, nanoid, postcss-selector-parser, browserslist and others: the content of Dependabot #82-#86).

Code changes needed: only `jobs/[jobId]/page.tsx` (a client component; `params` is now a Promise, read with `use(params)`). `tsconfig.json` gains `"target": "ES2017"` (Next adds it itself). No middleware, Server Actions, `cookies()`/`headers()` or `next/image` in the app. `/api/version` (GET) stops being prerendered at build time, which matches its in-code 10-minute cache.

Verified locally: `npm ci`, `typecheck`, `lint`, `build` pass; `docker build` of `apps/web` on `node:24-alpine` (runs Node v24.22.1) passes and the container serves all 13 routes (200, `/nope` 404, `/jobs/<id>` redirects to `/login` when signed out); `/_next/image` 404; no console errors; the home page renders the same as on Next 14.

Remaining audit items: `npm audit` still lists the copy of `postcss` vendored inside `next` itself (the fix is Next 16, a major bump) and one moderate issue. These are build-time CSS-processing code paths, not request-time ones.

Playwright note: the suite (`tests/e2e`) runs against the **deployed** dev site (`DEV_FRONTEND_URL`) and its global setup reads the DynamoDB sessions table with AWS keys. Dispatching `test-web.yml` on a branch therefore tests whatever is deployed on dev, not the branch. Run it after the upgrade has deployed to dev (and ideally once before, as the baseline).

## 11. Promotion to prod and the postcss override (2026-10-27)
Step 6 done: PR #92 (dev to main, merge commit `b9ce386`) deployed prod web. Before/after: prod ran Next 14.2.29; after the deploy `www.` and `app.sundayalbum.com` return 200 on 9 routes and `/_next/image` is 404 on both; `/api/version` reports `b9ce386`. Playwright against dev: 20 passed / 1 skipped both before the upgrade (8.3 min) and after it (6.9 min). Dependabot alerts on `main` after the deploy: 0 critical, 0 `next`; left: 4 `postcss` (the copy vendored inside `next`) and 1 `pytest`.

Dependabot's answer to the postcss alerts was PR #93, which bumps `next` 15.5.28 to **16.4.3** (a major) into `main`. Not taken. Instead `package.json` gets `"overrides": { "next": { "postcss": "^8.5.32" } }`, and the locked nested copy (8.4.31) is dropped so npm re-resolves it to the top-level 8.5.32. Verified: clean `npm ci`, `typecheck`, `lint`, `build`, `docker build` on `node:24-alpine`, container serves all routes, `/_next/image` 404, `npm audit` reports 0 vulnerabilities. Revisit when Next is upgraded again: remove the override if Next's own `postcss` pin moves past 8.5.23.

Note for the next person: Dependabot reads `dependabot.yml` from `main`, and its security PRs target `main` regardless of `target-branch`, so merging one deploys prod. Handle them by applying the same change on a branch into `dev` and promoting.

## 12. Local test of the rebuilt Lambda image on real HEIC photos (2026-10-27)
The Lambda image installs `requirements-lambda.txt`, whose `>=` dependencies re-resolve on every rebuild (it has no pins). #69 and #76 do not touch that file (they change the Mac app's `requirements*.txt` only), but the two dev Lambda deploys rebuilt the image anyway.

Check: built the root `Dockerfile` locally for `linux/arm64` (the platform the workflow deploys) and ran the pipeline inside it on four HEICs from `test-images/` (three-photo page, two-photo page, two single-photo pages), AI steps off, no network, no keys. Resolved versions: Pillow 13.0.0, pillow-heif 1.8.1, numpy 2.5.4, scipy 1.18.1, OpenCV 5.0.0.
- All four images processed (ok): 3, 2, 1 and 1 photos, matching expectations and a local macOS venv.
- Same image with the older versions pinned back (Pillow 12.3.0, pillow-heif 1.5.0, numpy 2.5.2, scipy 1.18.0): **7 of 7 output files byte-identical** (md5). The package drift changed nothing for these images.
- The local macOS venv output differs from the Linux image: a few pixels of crop on most photos, `two_pics` Photo01 rotated 90 degrees and `three_pics` Photo01 rotated 180 degrees (owner's visual check). The Linux runs with new and old pins are identical, so Pillow/pillow-heif/numpy/scipy drift is not the cause. **The cause is not established**: the likely candidate is a native difference (OpenCV build, BLAS) between the macOS venv and the Linux image, but I did not compare the exact OpenCV wheels, so that is an inference. The loader's `_getexif()` is a no-op for HEIC in both environments, so EXIF handling is ruled out.
- Why the rotation shows at all: the check ran with AI orientation off. `ai_orient` then returns 0 degrees, and in `geometry/rotation.py` `_detect_small_rotation` is disabled and `_detect_orientation_error` always returns 0, so nothing corrects gross orientation. Output orientation is whatever the detected corner order produces (`_order_corners` in `photo_detection/detector.py`: top-left = smallest x+y, top-right = smallest y-x, and so on). A small change in the detected hull/minAreaRect can flip that choice and swap width and height (the 90 degree case). I found no simple mechanism for the in-place 180 degree case. With AI orientation on (production), `ai_orient` normally corrects gross rotation, which would mask this; not tested here.

Limits: four photos, no pixel-level assertion against a known-good result, and the previous Lambda image from ECR could not be pulled (no AWS), so "old" means the older pins rather than the actually deployed image. `requirements-lambda.txt` would still benefit from pins or a constraints file; not started.
