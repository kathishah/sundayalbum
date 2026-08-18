"""Sunday Album settings Lambda handler.

Routes:
    GET    /settings/api-keys    Return whether user has stored their own API keys
    PUT    /settings/api-keys    Store user-supplied Anthropic and/or OpenAI API keys
    DELETE /settings/api-keys    Remove user-supplied API keys (revert to system keys)

User-supplied keys are stored in the sa-user-settings DynamoDB table, which uses
AWS-managed KMS encryption at rest. Keys are never returned in GET responses —
callers only learn whether keys are present (has_anthropic_key / has_openai_key).
"""

from __future__ import annotations

import logging
from typing import Any

from common import (
    bad_request,
    internal,
    not_found,
    ok,
    parse_body,
    require_auth,
    user_settings_table,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ── Router ─────────────────────────────────────────────────────────────────────
def handler(event: dict, context: Any) -> dict:
    auth_result = require_auth(event)
    if isinstance(auth_result, dict):
        return auth_result  # 401

    _email, user_hash = auth_result
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    try:
        if method == "PUT":
            return _handle_put(event, user_hash)
        if method == "DELETE":
            return _handle_delete(user_hash)
        return _handle_get(user_hash)
    except Exception as exc:
        logger.exception("Unhandled error in settings handler: %s", exc)
        return internal()


# ── GET /settings/api-keys ────────────────────────────────────────────────────
def _handle_get(user_hash: str) -> dict:
    """Return presence flags for stored API keys — never the key values."""
    try:
        resp = user_settings_table.get_item(Key={"user_hash": user_hash})
    except Exception as exc:
        logger.error("DynamoDB get_item failed: %s", exc)
        return internal("Could not fetch settings")

    item = resp.get("Item", {})
    return ok(
        {
            "has_anthropic_key": bool(item.get("anthropic_api_key", "").strip()),
            "has_openai_key":    bool(item.get("openai_api_key", "").strip()),
        }
    )


# ── PUT /settings/api-keys ────────────────────────────────────────────────────
def _handle_put(event: dict, user_hash: str) -> dict:
    """Store user-supplied API keys. Either or both may be provided."""
    body = parse_body(event)

    anthropic_key = (body.get("anthropic_api_key") or "").strip()
    openai_key    = (body.get("openai_api_key") or "").strip()

    if not anthropic_key and not openai_key:
        return bad_request("Provide at least one of anthropic_api_key or openai_api_key")

    # Basic format sanity checks (not a validity check — that requires an API call)
    if anthropic_key and not anthropic_key.startswith("sk-ant-"):
        return bad_request("anthropic_api_key does not look valid (expected prefix sk-ant-)")
    if openai_key and not openai_key.startswith("sk-"):
        return bad_request("openai_api_key does not look valid (expected prefix sk-)")

    # Build update expression — only update fields that were provided
    update_parts = []
    expr_values: dict[str, str] = {}

    if anthropic_key:
        update_parts.append("anthropic_api_key = :ak")
        expr_values[":ak"] = anthropic_key
    if openai_key:
        update_parts.append("openai_api_key = :ok")
        expr_values[":ok"] = openai_key

    try:
        user_settings_table.update_item(
            Key={"user_hash": user_hash},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeValues=expr_values,
        )
    except Exception as exc:
        logger.error("DynamoDB update_item failed: %s", exc)
        return internal("Could not save API keys")

    logger.info(
        "User %s... saved API keys: anthropic=%s openai=%s",
        user_hash[:8],
        bool(anthropic_key),
        bool(openai_key),
    )
    return ok(
        {
            "message": "API keys saved",
            "has_anthropic_key": bool(anthropic_key),
            "has_openai_key":    bool(openai_key),
        }
    )


# ── DELETE /settings/api-keys ─────────────────────────────────────────────────
def _handle_delete(user_hash: str) -> dict:
    """Remove all user-supplied API keys. Pipeline reverts to system keys."""
    try:
        user_settings_table.delete_item(Key={"user_hash": user_hash})
    except Exception as exc:
        logger.error("DynamoDB delete_item failed: %s", exc)
        return internal("Could not remove API keys")

    logger.info("User %s... removed API keys", user_hash[:8])
    return ok({"message": "API keys removed. System keys will be used."})
