"""Shared utilities for Sunday Album API Lambda handlers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Environment ───────────────────────────────────────────────────────────────
SESSIONS_TABLE = os.environ["SESSIONS_TABLE"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
WS_CONNECTIONS_TABLE = os.environ["WS_CONNECTIONS_TABLE"]
USER_SETTINGS_TABLE = os.environ["USER_SETTINGS_TABLE"]
S3_BUCKET = os.environ["S3_BUCKET"]
SES_SENDER = os.environ["SES_SENDER"]
REGION = os.environ.get("AWS_DEPLOY_REGION", "us-west-2")
# ADMIN_EMAILS: comma-separated list of emails exempt from rate limits
ADMIN_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
}
# Daily job limit for non-admin users (UTC midnight reset)
DAILY_JOB_LIMIT = 20

# ── AWS clients (module-level for Lambda container reuse) ─────────────────────
dynamodb = boto3.resource("dynamodb", region_name=REGION)
# Use regional S3 endpoint + SigV4 so presigned URLs resolve without 307 redirect
s3_client = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)
ses_client = boto3.client("ses", region_name=REGION)

sessions_table = dynamodb.Table(SESSIONS_TABLE)
jobs_table = dynamodb.Table(JOBS_TABLE)
ws_table = dynamodb.Table(WS_CONNECTIONS_TABLE)
user_settings_table = dynamodb.Table(USER_SETTINGS_TABLE)


# ── ULID generation (no external deps) ───────────────────────────────────────
_ULID_ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Generate a ULID — lexicographically sortable unique ID.

    Format: 10 timestamp chars + 16 random chars (Crockford base32).
    """
    ts = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")

    ts_chars = ""
    for _ in range(10):
        ts_chars = _ULID_ENCODING[ts & 0x1F] + ts_chars
        ts >>= 5

    rand_chars = ""
    for _ in range(16):
        rand_chars = _ULID_ENCODING[rand & 0x1F] + rand_chars
        rand >>= 5

    return ts_chars + rand_chars


# ── User hash ─────────────────────────────────────────────────────────────────
def hash_email(email: str) -> str:
    """Return SHA-256 hex digest of lowercased email (used as S3/DDB user prefix)."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


# ── HTTP response helpers ─────────────────────────────────────────────────────
_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
}


def ok(body: dict[str, Any]) -> dict:
    return {"statusCode": 200, "headers": _CORS_HEADERS, "body": json.dumps(body)}


def created(body: dict[str, Any]) -> dict:
    return {"statusCode": 201, "headers": _CORS_HEADERS, "body": json.dumps(body)}


def error(status: int, message: str, detail: str = "") -> dict:
    payload: dict[str, Any] = {"error": message}
    if detail:
        payload["detail"] = detail
    return {"statusCode": status, "headers": _CORS_HEADERS, "body": json.dumps(payload)}


def bad_request(msg: str) -> dict:
    return error(400, "bad_request", msg)


def unauthorized(msg: str = "Invalid or expired session") -> dict:
    return error(401, "unauthorized", msg)


def not_found(msg: str = "Not found") -> dict:
    return error(404, "not_found", msg)


def internal(msg: str = "Internal server error") -> dict:
    return error(500, "internal_error", msg)


def too_many_requests(msg: str = "Daily job limit reached") -> dict:
    return error(429, "rate_limit_exceeded", msg)


# ── Auth middleware ───────────────────────────────────────────────────────────
def get_session(event: dict) -> Optional[tuple[str, str]]:
    """Extract and validate Bearer token from Authorization header.

    Returns:
        (email, user_hash) if valid, None otherwise.
    """
    headers = event.get("headers") or {}
    auth_header = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None

    # Look up by GSI on session_token
    try:
        resp = sessions_table.query(
            IndexName="token-index",
            KeyConditionExpression="session_token = :t",
            ExpressionAttributeValues={":t": token},
            Limit=1,
        )
    except Exception as exc:
        logger.warning("DynamoDB query for session failed: %s", exc)
        return None

    items = resp.get("Items", [])
    if not items:
        return None

    item = items[0]
    if int(item.get("token_expires_at", 0)) < int(time.time()):
        return None  # expired (DynamoDB TTL is lazy)

    return item["email"], item["user_hash"]


def require_auth(event: dict) -> tuple[str, str] | dict:
    """Return (email, user_hash) or an HTTP 401 response dict."""
    session = get_session(event)
    if session is None:
        return unauthorized()
    return session


def is_admin(email: str) -> bool:
    """Return True if the email is in the ADMIN_EMAILS set."""
    return email.strip().lower() in ADMIN_EMAILS


# ── Body parsing ──────────────────────────────────────────────────────────────
def parse_body(event: dict) -> dict[str, Any]:
    """Parse JSON body from API Gateway event, return empty dict on failure."""
    raw = event.get("body") or "{}"
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return {}


# ── S3 presigned URLs ─────────────────────────────────────────────────────────
def presign_put(key: str, expires: int = 3600) -> str:
    """Generate a presigned PUT URL for uploading to S3."""
    return s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )


def presign_get(key: str, expires: int = 3600) -> str:
    """Generate a presigned GET URL for downloading from S3."""
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )


def presign_get_if_exists(key: str, expires: int = 3600) -> Optional[str]:
    """Return presigned GET URL only if the S3 key exists."""
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        return presign_get(key, expires)
    except s3_client.exceptions.ClientError:
        return None
    except Exception:
        return None
