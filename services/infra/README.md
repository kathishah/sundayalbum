# services/infra: AWS CDK stack (Python)

Defines the Sunday Album AWS resources: S3 data bucket, DynamoDB tables, Secrets Manager entry,
API Lambdas, the HTTP and WebSocket APIs, the Step Functions pipeline and its 11 container
Lambdas. The web app (App Runner) and the deploy IAM roles are **not** in this stack.

Deployment configuration is kept out of the repo:

| Setting | Source |
|---|---|
| AWS account | `CDK_DEFAULT_ACCOUNT` (the CDK CLI sets it from the AWS profile you deploy with) |
| Stage | `-c stage=dev` or `-c stage=prod` (default `prod`) |
| Admin e-mail list | `-c admin_emails=a@example.com,b@example.com` or `SUNDAYALBUM_ADMIN_EMAILS` (empty = warning, nobody exempt from the job limit) |
| SES sender | `-c ses_sender_email=...` |

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export AWS_PROFILE=<profile>
cdk diff -c stage=dev -c admin_emails=you@example.com      # always diff first
cdk deploy -c stage=dev -c admin_emails=you@example.com
pytest tests/ -q                                            # synth-based unit tests, no AWS
```

Prod uses the original stack and resource names with a RETAIN removal policy; dev suffixes every
name with `-dev` and is destroyable. See `docs/OPERATIONS.md` for backup, teardown and cost
notes.
