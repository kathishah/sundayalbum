# Security policy

## Reporting a vulnerability

Please report security issues **privately**, not in a public issue.

1. Preferred: use GitHub's private reporting, **Security > Report a vulnerability** on this
   repository.
2. Otherwise e-mail **support@arjuntech.com** with "Sunday Album security" in the subject.

Include what you found, how to reproduce it, and which part is affected (web app, API, AWS
infrastructure, macOS app, pipeline). Please do not test with other people's accounts or photos,
do not run load or denial-of-service tests against sundayalbum.com, and give me reasonable time
to fix the problem before disclosing it.

This is a solo-maintained project. I will acknowledge reports on a best-effort basis; there is no
guaranteed response time or bug bounty.

## What is covered

- The hosted web app and API at sundayalbum.com and its dev counterpart.
- The code in this repository: Lambda/API handlers, CDK stack, GitHub workflows, web app, macOS
  app, processing pipeline.
- How user-supplied API keys and uploaded photos are handled.

Only the latest commit on `main` is supported. The AWS deployment is the maintainer's own; there
is no supported way for others to deploy it, so issues in someone else's deployment are out of
scope unless they come from a flaw in this code.

## Secrets and configuration

No credentials are stored in this repository. Deployment-specific values (AWS account, admin
e-mail list, test accounts) are supplied through repository secrets, CDK context or environment
variables; see `docs/OPERATIONS.md`. If you find a credential or personal data in the tree or its
history, please report it the same way.
