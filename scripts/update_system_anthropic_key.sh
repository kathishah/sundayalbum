#!/usr/bin/env bash
# Update only the production system Anthropic key in AWS Secrets Manager.
# The key is prompted for without echo and is never placed in shell history.
set -euo pipefail

readonly AWS_REGION="us-west-2"
readonly SECRET_ID="sundayalbum/api-keys"

if ! command -v aws >/dev/null 2>&1; then
  printf 'aws CLI is required.\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'python3 is required.\n' >&2
  exit 1
fi

# Confirm credentials are available without printing account or identity data.
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null

umask 077
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"; unset ANTHROPIC_KEY' EXIT

if ! IFS= read -r -s -p 'New Anthropic API key (input hidden): ' ANTHROPIC_KEY </dev/tty; then
  printf 'Could not read the key from a terminal; no update made.\n' >&2
  exit 1
fi
printf '\n' >/dev/tty

if [[ "$ANTHROPIC_KEY" != sk-ant-* ]]; then
  printf 'Key does not start with sk-ant-; no update made.\n' >&2
  exit 1
fi
printf '%s' "$ANTHROPIC_KEY" > "$workdir/new-key"
unset ANTHROPIC_KEY

# Keep the existing OpenAI key and any other secret fields unchanged.
aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ID" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text |
  python3 -c '
import json, pathlib, sys

data = json.load(sys.stdin)
if not isinstance(data, dict):
    raise SystemExit("Secret is not a JSON object; no update made.")

key = pathlib.Path(sys.argv[1]).read_text()
if not key.startswith("sk-ant-"):
    raise SystemExit("Invalid Anthropic key prefix; no update made.")

data["ANTHROPIC_API_KEY"] = key
json.dump(data, sys.stdout)
' "$workdir/new-key" > "$workdir/secret.json"

version_id=$(aws secretsmanager update-secret \
  --secret-id "$SECRET_ID" \
  --region "$AWS_REGION" \
  --secret-string "file://$workdir/secret.json" \
  --query VersionId \
  --output text)

printf 'Updated %s in %s (version %s).\n' "$SECRET_ID" "$AWS_REGION" "$version_id"
