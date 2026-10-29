"""Tests 1–6: Auth API — send-code, verify, logout."""

from __future__ import annotations

import hashlib
import time

import auth as auth_module
import boto3
import pytest
from helpers import REGION, SESSIONS_TABLE, make_event, make_session


def _hash(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()


# ── 1. send_code valid email ──────────────────────────────────────────────────


def test_send_code_valid_email(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /auth/send-code with a valid email returns 200 and stores a code."""
    monkeypatch.setattr(auth_module.secrets, "randbelow", lambda upper: 0)
    event = make_event("POST /auth/send-code", body={"email": "user@example.com"})
    resp = auth_module.handler(event, None)

    assert resp["statusCode"] == 200

    # Code must be stored in DynamoDB
    ddb = boto3.resource("dynamodb", region_name=REGION)
    item = ddb.Table(SESSIONS_TABLE).get_item(Key={"email": "user@example.com"}).get("Item")
    assert item is not None
    assert item.get("code") == "100000"
    assert item["code_expires_at"] > int(time.time())
    assert item["user_hash"] == _hash("user@example.com")


# ── 2. send_code invalid email ────────────────────────────────────────────────


def test_send_code_invalid_email():
    """POST /auth/send-code with a malformed email returns 400."""
    event = make_event("POST /auth/send-code", body={"email": "not-an-email"})
    resp = auth_module.handler(event, None)
    assert resp["statusCode"] == 400


# ── 3. verify valid code ──────────────────────────────────────────────────────


def test_verify_code_valid():
    """Correct code returns session_token, user_hash, and expires_at."""
    email = "user@example.com"
    user_hash = _hash(email)
    code = "123456"

    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(SESSIONS_TABLE).put_item(
        Item={
            "email": email,
            "user_hash": user_hash,
            "code": code,
            "code_expires_at": int(time.time()) + 600,
            "verify_attempts": 0,
        }
    )

    event = make_event("POST /auth/verify", body={"email": email, "code": code})
    resp = auth_module.handler(event, None)

    assert resp["statusCode"] == 200
    body = __import__("json").loads(resp["body"])
    assert "session_token" in body
    assert body["user_hash"] == user_hash
    assert body["expires_at"] > int(time.time())


# ── 4. verify wrong code ──────────────────────────────────────────────────────


def test_verify_code_invalid():
    """Wrong code returns 401."""
    email = "user@example.com"
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(SESSIONS_TABLE).put_item(
        Item={
            "email": email,
            "user_hash": _hash(email),
            "code": "111111",
            "code_expires_at": int(time.time()) + 600,
            "verify_attempts": 0,
        }
    )

    event = make_event("POST /auth/verify", body={"email": email, "code": "999999"})
    resp = auth_module.handler(event, None)
    assert resp["statusCode"] == 401


# ── 5. verify expired code ────────────────────────────────────────────────────


def test_verify_code_expired():
    """Code older than its TTL returns 401."""
    email = "user@example.com"
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(SESSIONS_TABLE).put_item(
        Item={
            "email": email,
            "user_hash": _hash(email),
            "code": "123456",
            "code_expires_at": int(time.time()) - 1,  # already expired
            "verify_attempts": 0,
        }
    )

    event = make_event("POST /auth/verify", body={"email": email, "code": "123456"})
    resp = auth_module.handler(event, None)
    assert resp["statusCode"] == 401


def test_verify_attempt_limit_is_atomic_and_bounded() -> None:
    email = "attempts@example.com"
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(SESSIONS_TABLE).put_item(
        Item={
            "email": email,
            "user_hash": _hash(email),
            "code": "123456",
            "code_expires_at": int(time.time()) + 600,
            "verify_attempts": auth_module.MAX_VERIFY_ATTEMPTS - 1,
        }
    )

    event = make_event("POST /auth/verify", body={"email": email, "code": "000000"})
    first = auth_module.handler(event, None)
    second = auth_module.handler(event, None)

    assert first["statusCode"] == 401
    assert second["statusCode"] == 429
    item = ddb.Table(SESSIONS_TABLE).get_item(Key={"email": email})["Item"]
    assert item["verify_attempts"] == auth_module.MAX_VERIFY_ATTEMPTS


def test_verify_attempt_storage_error_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = "storage-error@example.com"
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(SESSIONS_TABLE).put_item(
        Item={
            "email": email,
            "user_hash": _hash(email),
            "code": "123456",
            "code_expires_at": int(time.time()) + 600,
            "verify_attempts": 0,
        }
    )

    def fail_update(**_kwargs):
        raise RuntimeError("DynamoDB unavailable")

    monkeypatch.setattr(auth_module.sessions_table, "update_item", fail_update)
    event = make_event("POST /auth/verify", body={"email": email, "code": "000000"})
    response = auth_module.handler(event, None)

    assert response["statusCode"] == 500


# ── 6. logout invalidates token ───────────────────────────────────────────────


def test_logout():
    """After logout, the same token returns 401 on authenticated endpoints."""
    email = "user@example.com"
    user_hash = _hash(email)
    token = make_session(email, user_hash)

    # Confirm token works before logout
    list_event = make_event("GET /jobs", token=token)
    import jobs as jobs_module
    pre_resp = jobs_module.handler(list_event, None)
    assert pre_resp["statusCode"] == 200

    # Logout
    logout_event = make_event("POST /auth/logout", token=token)
    resp = auth_module.handler(logout_event, None)
    assert resp["statusCode"] == 200

    # Token must no longer be valid
    post_resp = jobs_module.handler(list_event, None)
    assert post_resp["statusCode"] == 401
