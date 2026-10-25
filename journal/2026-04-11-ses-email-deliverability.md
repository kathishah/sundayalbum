# SES email deliverability — diagnosis and plan

**Date:** 2026-04-11  
**Branch:** `dev` (journal entry only; no feature branch required for this document)

---

## Problem

Login OTP mail was sent with **From** showing a personal Gmail address **via** `amazonses.com`. That mismatch (Gmail domain + Amazon sending infrastructure) hurts authentication alignment and inbox placement; clients show “via amazonses.com” and mail can be filtered as spam.

---

## Repo and DNS (what we checked)

- **CDK** (`infra/infra/sundayalbum_stack.py`): Lambda gets `SES_SENDER` from context or default `noreply@sundayalbum.com`. IAM allows `ses:SendEmail`. There is **no** SES domain identity or mail DNS in IaC — verification is manual in AWS + Route 53.
- **`infra/cdk.json`**: Removed the override `ses_sender_email: <admin-email>` so deploys use the stack default unless context is set elsewhere at deploy time.
- **Public DNS** (`sundayalbum.com`, Route 53 NS): No TXT (SPF) on apex, no `_dmarc`, no MX — consistent with **web** setup only, not outbound branded mail.

---

## AWS CLI — SES in `us-west-2` (2026-04-11)

Commands: `aws sesv2 list-email-identities`, `aws sesv2 get-account`, `aws ses get-send-quota`.

| Observation | Detail |
|-------------|--------|
| **`sundayalbum.com` as SES identity** | **Not** present. |
| **Verified identities relevant to early testing** | `<admin-email>` and `<test-user-email>` — **EMAIL_ADDRESS**, `SUCCESS`, sending enabled. Explains using Gmail as From. |
| **Other** | Another domain `delicioustrades.com` verified; unrelated failed single-address identities. |
| **Sandbox** | `ProductionAccessEnabled`: **false** — account is in **SES sandbox** (low quotas; sending to arbitrary users requires **production access**). |
| **Quota snapshot** | e.g. 200/day, 1 msg/s (sandbox-class limits). |

---

## Do we need “full email hosting” first?

**No** for OTP-only outbound mail. You need:

- **SES domain identity** for `sundayalbum.com` (or a subdomain if you ever prefer),
- **DKIM** (Easy DKIM CNAMEs in Route 53),
- **SPF** and **DMARC** (TXT records) as documented for your setup,

and optionally **SES configuration sets** + bounce/complaint handling for production.

**Inbound** mail at `@sundayalbum.com` (Google Workspace, etc.) is a **separate** product decision — **not** required for login codes.

---

## Overall plan (operational)

1. **SES (console)** — Create identity → **Domain** → `sundayalbum.com`; enable **Easy DKIM**.
2. **Route 53** — Add SES-supplied **DKIM CNAME** records; add **SPF** (and **DMARC**, start with `p=none` if desired).
3. Wait until SES shows domain **verified** and DKIM **successful**.
4. **Deploy** — Ensure `SES_SENDER` is an address on that domain (e.g. `noreply@sundayalbum.com` or display name `Sunday Album <noreply@sundayalbum.com>`), matching verified identity.
5. **Request SES production access** — Required to send to arbitrary recipient addresses at normal volume; describe transactional OTP use case.
6. **Later / optional** — Configuration set + SNS/SQS for bounces and complaints; tighten DMARC when stable.

---

## Branching note

This file is **documentation only**. No feature branch is required to add it on `dev`. **Infra or app changes** (CDK defaults, env, SES console work) can land on `dev` directly for small edits or via **`feature/…` → PR → `dev`** per team preference and risk.

---

## Implemented (2026-04-11) — AWS CLI

Region **`us-west-2`** throughout. Hosted zone **`Z0420309YMJDXBAU344P`** (`sundayalbum.com`).

### 1. SES domain identity + Easy DKIM

```bash
aws sesv2 create-email-identity \
  --email-identity sundayalbum.com \
  --region us-west-2 \
  --dkim-signing-attributes NextSigningKeyLength=RSA_2048_BIT
```

### 2. Route 53

Applied **`infra/ses-sundayalbum-dns-changes.json`**: three **DKIM** CNAMEs (`*_domainkey`), apex **SPF** TXT (`v=spf1 include:amazonses.com ~all`), **`_dmarc`** TXT (`v=DMARC1; p=none;`). Change ID `C0267915QFKLZ05N5PS3` (INSYNC).

If DKIM tokens ever rotate in SES, fetch new CNAME targets with `aws sesv2 get-email-identity --email-identity sundayalbum.com` and update Route 53; do not replay stale JSON blindly.

### 3. SES verification result

After DNS propagated, `aws sesv2 get-email-identity` reported **`VerificationStatus`: SUCCESS**, **`DkimAttributes.Status`: SUCCESS**, **`VerifiedForSendingStatus`: true**.

### 4. Lambda `SES_SENDER`

Updated **`sa-auth`** and **`sa-auth-dev`** environment so **`SES_SENDER=noreply@sundayalbum.com`** (was `<admin-email>`). Pattern: `get-function-configuration` → `jq` merge → `update-function-configuration` with full `Variables` map.

Future **`cdk deploy`** will keep this alignment as long as **`infra/cdk.json`** does not reintroduce `ses_sender_email` override.

### 5. Test send

```bash
aws ses send-email --region us-west-2 \
  --from "Sunday Album <noreply@sundayalbum.com>" \
  --destination "ToAddresses=<test-user-email>" \
  --message 'Subject={Data=Sunday Album SES CLI test,Charset=utf-8},Body={Text={Data=Domain verified. DKIM aligned.,Charset=utf-8}}'
```

(App OTP mail uses plain `noreply@sundayalbum.com` from env — no display name unless we change `api/auth.py`.)

### 6. Still manual: production access

`aws sesv2 get-account` → **`ProductionAccessEnabled`: false** (sandbox). Request **production access** in the **SES console** (or Support) so OTP can be sent to **any** recipient, not only verified addresses. Not available as a one-shot CLI in the same way as identity creation.
