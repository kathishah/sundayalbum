"""Sunday Album auth Lambda handler.

Routes:
    POST /auth/send-code    { email } → sends 6-digit code via SES
    POST /auth/verify       { email, code } → { session_token, user_hash }
    POST /auth/logout       (Authorization: Bearer token) → {}
"""

from __future__ import annotations

import logging
import random
import re
import time
import uuid
from typing import Any

from common import (
    bad_request,
    error,
    get_session,
    hash_email,
    internal,
    jobs_table,
    not_found,
    ok,
    parse_body,
    ses_client,
    sessions_table,
    SES_SENDER,
    unauthorized,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Verification code TTL: 10 minutes
CODE_TTL_SECONDS = 600
# Session token TTL: 7 days
TOKEN_TTL_SECONDS = 7 * 24 * 3600
# Rate limits
MAX_CODE_SENDS_PER_HOUR = 3
MAX_VERIFY_ATTEMPTS = 5

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Router ─────────────────────────────────────────────────────────────────────
def handler(event: dict, context: Any) -> dict:
    """Lambda entry point — route to sub-handler by routeKey."""
    route = event.get("routeKey", "") or event.get("rawPath", "")
    logger.info("Auth route: %s", route)

    try:
        if "send-code" in route:
            return _handle_send_code(event)
        if "verify" in route:
            return _handle_verify(event)
        if "logout" in route:
            return _handle_logout(event)
        return error(404, "not_found", f"Unknown auth route: {route}")
    except Exception as exc:
        logger.exception("Unhandled error in auth handler: %s", exc)
        return internal()


# ── send-code ─────────────────────────────────────────────────────────────────
def _handle_send_code(event: dict) -> dict:
    body = parse_body(event)
    email = (body.get("email") or "").strip().lower()

    if not email or not _EMAIL_RE.match(email):
        return bad_request("Valid email is required")

    user_hash = hash_email(email)
    now = int(time.time())

    # Rate limit: check existing session record
    try:
        existing = sessions_table.get_item(Key={"email": email}).get("Item", {})
    except Exception as exc:
        logger.error("DynamoDB get_item failed: %s", exc)
        return internal("Could not check rate limit")

    send_count = existing.get("send_count", 0)
    send_window_start = existing.get("send_window_start", 0)

    # Reset counter if window has expired (1 hour)
    if now - send_window_start > 3600:
        send_count = 0
        send_window_start = now

    if send_count >= MAX_CODE_SENDS_PER_HOUR:
        return error(429, "rate_limited", "Too many code requests. Try again in an hour.")

    # Generate 6-digit code
    code = str(random.randint(100000, 999999))
    code_expires_at = now + CODE_TTL_SECONDS

    # Store in DynamoDB — session_token is omitted if not yet issued
    # (DynamoDB GSI key cannot be an empty string)
    item: dict = {
        "email": email,
        "user_hash": user_hash,
        "code": code,
        "code_expires_at": code_expires_at,
        "verify_attempts": 0,
        "send_count": send_count + 1,
        "send_window_start": send_window_start,
    }
    # Preserve existing active session_token if present
    existing_token = existing.get("session_token", "")
    if existing_token:
        item["session_token"] = existing_token
        item["token_expires_at"] = existing.get("token_expires_at", now + TOKEN_TTL_SECONDS)

    try:
        sessions_table.put_item(Item=item)
    except Exception as exc:
        logger.error("DynamoDB put_item failed: %s", exc)
        return internal("Could not store verification code")

    # Send email via SES
    try:
        ses_client.send_email(
            Source=SES_SENDER,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": "Your Sunday Album verification code"},
                "Body": {
                    "Text": {
                        "Data": (
                            f"Your Sunday Album verification code is: {code}\n\n"
                            f"This code expires in 10 minutes.\n\n"
                            f"If you didn't request this, you can safely ignore this email."
                        )
                    },
                    "Html": {
                        "Data": (
                            f"<p>Your <strong>Sunday Album</strong> verification code is:</p>"
                            f"<h1 style='letter-spacing:0.15em;font-family:monospace'>{code}</h1>"
                            f"<p>This code expires in <strong>10 minutes</strong>.</p>"
                            f"<p style='color:#888;font-size:12px'>If you didn't request this, you can safely ignore this email.</p>"
                        )
                    },
                },
            },
        )
        logger.info("Sent verification code to %s", email)
    except Exception as exc:
        logger.error("SES send_email failed for %s: %s", email, exc)
        return internal("Could not send verification email. Please try again.")

    return ok({"message": "Verification code sent", "expires_in": CODE_TTL_SECONDS})


# ── verify ─────────────────────────────────────────────────────────────────────
def _handle_verify(event: dict) -> dict:
    body = parse_body(event)
    email = (body.get("email") or "").strip().lower()
    code = str(body.get("code") or "").strip()

    if not email or not code:
        return bad_request("email and code are required")

    now = int(time.time())

    try:
        item = sessions_table.get_item(Key={"email": email}).get("Item")
    except Exception as exc:
        logger.error("DynamoDB get_item failed: %s", exc)
        return internal()

    if not item:
        return unauthorized("No verification code found for this email")

    # Check attempt limit
    attempts = item.get("verify_attempts", 0)
    if attempts >= MAX_VERIFY_ATTEMPTS:
        return error(429, "rate_limited", "Too many attempts. Request a new code.")

    # Increment attempt counter regardless of success
    try:
        sessions_table.update_item(
            Key={"email": email},
            UpdateExpression="SET verify_attempts = verify_attempts + :one",
            ExpressionAttributeValues={":one": 1},
        )
    except Exception:
        pass  # non-fatal

    # Check expiry
    if now > item.get("code_expires_at", 0):
        return unauthorized("Verification code has expired. Please request a new one.")

    # Check code
    if item.get("code") != code:
        remaining = MAX_VERIFY_ATTEMPTS - attempts - 1
        return unauthorized(
            f"Invalid code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
        )

    # Code valid — issue session token
    session_token = str(uuid.uuid4())
    token_expires_at = now + TOKEN_TTL_SECONDS
    user_hash = item["user_hash"]

    try:
        sessions_table.update_item(
            Key={"email": email},
            UpdateExpression=(
                "SET session_token = :t, token_expires_at = :e, "
                "verify_attempts = :zero, #c = :empty"
            ),
            ExpressionAttributeNames={"#c": "code"},
            ExpressionAttributeValues={
                ":t": session_token,
                ":e": token_expires_at,
                ":zero": 0,
                ":empty": "",  # invalidate the code
            },
        )
    except Exception as exc:
        logger.error("DynamoDB update_item failed: %s", exc)
        return internal()

    logger.info("Issued session token for %s (hash: %s...)", email, user_hash[:8])
    return ok(
        {
            "session_token": session_token,
            "user_hash": user_hash,
            "expires_at": token_expires_at,
        }
    )


# ── logout ─────────────────────────────────────────────────────────────────────
def _handle_logout(event: dict) -> dict:
    session = get_session(event)
    if session is None:
        return ok({"message": "Logged out"})  # idempotent

    email, _ = session
    try:
        sessions_table.update_item(
            Key={"email": email},
            UpdateExpression="REMOVE session_token SET token_expires_at = :zero",
            ExpressionAttributeValues={":zero": 0},
        )
    except Exception as exc:
        logger.warning("Logout DynamoDB update failed: %s", exc)

    logger.info("Logged out session for %s", email)
    return ok({"message": "Logged out"})
