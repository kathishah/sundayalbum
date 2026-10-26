# Operating the AWS deployment

**Status:** written Oct 2026 from the CDK stack and the GitHub workflows in this repo. Resource
lists are read from `services/infra/infra/sundayalbum_stack.py`; costs and restore times below
are **not measured**. This is the maintainer's own deployment: nothing here is a supported
self-hosting product (see the README for the project stance).

## What gets deployed

| Piece | How it is deployed | Where it is defined |
|---|---|---|
| Data layer, API, Step Functions, Lambdas, secrets | `cdk deploy` run by hand | `services/infra/` |
| API Lambda code (zip) and pipeline Lambda image (ARM64 container) | GitHub Actions on push to `dev` (dev stage) or `main` (prod stage) | `.github/workflows/deploy-lambda.yml` |
| Web app (Next.js in a container on App Runner) | GitHub Actions, same branch rule | `.github/workflows/deploy-web.yml` |
| macOS app | built and signed locally | `apps/mac/build-release.sh` |

Stages: `dev` (every resource name suffixed `-dev`, removal policy DESTROY) and `prod` (original
names, removal policy RETAIN).

## Configuration kept out of the repo

| Setting | Where it comes from |
|---|---|
| AWS account ID (CDK) | `CDK_DEFAULT_ACCOUNT`, set by the CDK CLI from the profile you deploy with |
| AWS account ID (workflows) | repository secret `AWS_ACCOUNT_ID` (masks the value in public logs) |
| Admin e-mail list (users exempt from the daily job limit) | `cdk deploy -c admin_emails=a@example.com,b@example.com` or `SUNDAYALBUM_ADMIN_EMAILS`. If neither is set the stack deploys with an **empty** list and prints a warning |
| SES sender | `-c ses_sender_email=...` (the stack default is `noreply@sundayalbum.com`, an address on the maintainer's verified domain: use your own) |
| Role used by the workflows | IAM role `github-actions-sundayalbum` with an OIDC trust policy for this repo (not created by the CDK stack) |
| System AI keys | Secrets Manager `sundayalbum/api-keys[-dev]`, filled by hand |

## First deploy (new account or a copy of the stack)

Prerequisites: AWS CLI profile with admin-level rights for the first deploy, Node for the CDK
CLI, Docker (the stack builds container assets), a verified SES identity.

```bash
cd services/infra
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export AWS_PROFILE=<profile-for-the-target-account>
cdk bootstrap                      # once per account/region
cdk diff  -c stage=dev -c admin_emails=you@example.com
cdk deploy -c stage=dev -c admin_emails=you@example.com
```

Always run `cdk diff` before a prod deploy and pass the admin list, otherwise the Lambdas'
`ADMIN_EMAILS` variable is overwritten with an empty value.

## Backup and restore

- **DynamoDB** (`sa-jobs`, `sa-sessions`, `sa-ws-connections`, `sa-user-settings`): on-demand
  billing. **No point-in-time recovery or backup plan is configured in the stack.** Job and
  session items expire by TTL by design; `sa-user-settings` (users' stored keys) is the only
  table whose loss matters. To add protection, enable PITR on that table in the stack.
- **S3** data bucket: no versioning. Lifecycle rules expire `uploads/` and `output/` after 30
  days and `debug/` after 7 days, so the bucket is a working area, not an archive.
- **Secrets Manager** `sundayalbum/api-keys`: re-enter the keys from their providers.
- **Code and infrastructure** are fully reproducible from this repo; the container image is
  rebuilt by the workflow.

## Teardown

- **dev:** `cdk destroy -c stage=dev` removes everything (tables, bucket with its objects).
- **prod:** `cdk destroy` leaves the RETAIN resources behind (DynamoDB tables, the S3 bucket,
  the secret). Delete those by hand after confirming nothing needs them: empty and delete the
  bucket, delete the four tables and the secret.
- Also remove, outside the stack: the App Runner services `sundayalbum-web-dev` / `-prod`, the
  ECR repositories (`sundayalbum-web`, `sundayalbum-pipeline-dev`, the CDK asset repository),
  the IAM roles `github-actions-sundayalbum` and `AppRunnerECRAccessRole` (neither is created by the stack), the Route 53 records
  and the SES identity.

## Cost notes (qualitative, not measured)

- Always-on: one App Runner service per stage (provisioned 1 vCPU / 2 GB), plus Secrets Manager
  and Route 53 charges. This is the main fixed cost.
- Per use: Lambda at 3008 MB for up to 11 pipeline steps per page, Step Functions transitions,
  S3 requests and short-lived storage, DynamoDB on-demand requests, and SES e-mail. The AI
  providers (Anthropic, OpenAI) bill separately per call.
- No budget alarm is defined in the stack; set an AWS Budget on the account.

## Permissions

Deploying the stack needs rights to create IAM roles, Lambda, Step Functions, API Gateway,
DynamoDB, S3, Secrets Manager and ECR assets (CDK bootstrap roles). The GitHub workflows only
need `lambda:UpdateFunctionCode`, ECR push, and App Runner update/describe through the OIDC
role.
