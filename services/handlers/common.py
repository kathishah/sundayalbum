"""Shared utilities for Sunday Album Step Functions Lambda handlers.

Different from api/common.py (which serves HTTP API routes).
This module serves the pipeline step handlers invoked by Step Functions.
"""

from __future__ import annotations

import functools
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Environment ───────────────────────────────────────────────────────────────
S3_BUCKET = os.environ["S3_BUCKET"]
JOBS_TABLE = os.environ["JOBS_TABLE"]
SECRET_ARN = os.environ["SECRET_ARN"]
REGION = os.environ.get("AWS_DEPLOY_REGION", "us-west-2")

# ── AWS clients ───────────────────────────────────────────────────────────────
_dynamodb = boto3.resource("dynamodb", region_name=REGION)
jobs_table = _dynamodb.Table(JOBS_TABLE)
_secrets_client = boto3.client("secretsmanager", region_name=REGION)


# ── API key resolution ────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _get_system_api_keys() -> dict:
    """Fetch system API keys from Secrets Manager (cached per Lambda instance)."""
    try:
        resp = _secrets_client.get_secret_value(SecretId=SECRET_ARN)
        return json.loads(resp["SecretString"])
    except Exception as exc:
        logger.error("Failed to fetch system API keys from Secrets Manager: %s", exc)
        return {}


def get_anthropic_key(user_keys: dict | None = None) -> str:
    """Return the Anthropic API key: user-supplied if present, else system key."""
    if user_keys:
        user_key = user_keys.get("anthropic_api_key", "").strip()
        if user_key:
            return user_key
    return _get_system_api_keys().get("ANTHROPIC_API_KEY", "")


def get_openai_key(user_keys: dict | None = None) -> str:
    """Return the OpenAI API key: user-supplied if present, else system key."""
    if user_keys:
        user_key = user_keys.get("openai_api_key", "").strip()
        if user_key:
            return user_key
    return _get_system_api_keys().get("OPENAI_API_KEY", "")


# ── Storage factory ───────────────────────────────────────────────────────────

def make_storage(user_hash: str):
    """Return an S3Storage instance scoped to *user_hash*."""
    from src.storage.s3 import S3Storage
    return S3Storage(bucket=S3_BUCKET, prefix=user_hash, region=REGION)


# ── Pipeline config ───────────────────────────────────────────────────────────

def make_config(overrides: dict | None = None, user_keys: dict | None = None):
    """Return a PipelineConfig with API keys and optional overrides.

    API keys are resolved here — user-supplied keys take priority over system
    keys fetched from Secrets Manager — and injected as explicit fields on the
    config so that pipeline steps are pure functions with no env-var reads.

    Args:
        overrides: Optional dict of PipelineConfig field overrides from the
                   Step Functions event ``config`` payload.
        user_keys: Optional dict with ``anthropic_api_key`` and/or
                   ``openai_api_key`` supplied by the user via the settings UI.
    """
    from src.pipeline import PipelineConfig
    cfg = PipelineConfig(
        anthropic_api_key=get_anthropic_key(user_keys),
        openai_api_key=get_openai_key(user_keys),
    )
    if overrides:
        for k, v in overrides.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
    return cfg


# ── DynamoDB helpers ──────────────────────────────────────────────────────────

def _safe(key: str) -> str:
    """Make a DynamoDB expression attribute name safe (no hyphens, dots, slashes)."""
    return key.replace("-", "_").replace(".", "_").replace("/", "_")


def write_thumbnail(storage, debug_key: str, thumb_key: str) -> None:
    """Read the debug image at *debug_key*, resize to 400 px wide, write to *thumb_key*.

    Both keys are relative to the storage backend's prefix (user_hash).
    Non-fatal: logs a warning on failure so a thumbnail error never aborts the pipeline.
    """
    import numpy as np
    from PIL import Image

    try:
        image = storage.read_image(debug_key)
        h, w = image.shape[:2]
        thumb_w = 400
        thumb_h = max(1, int(round(h * thumb_w / w)))
        img_u8 = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
        pil_thumb = Image.fromarray(img_u8, "RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
        thumb_arr = np.array(pil_thumb).astype(np.float32) / 255.0
        storage.write_image(thumb_key, thumb_arr, format="jpeg", quality=85)
        logger.debug("write_thumbnail: %s → %s (%dx%d)", debug_key, thumb_key, thumb_w, thumb_h)
    except Exception as exc:
        logger.warning("write_thumbnail failed for %s: %s (non-fatal)", debug_key, exc)


def update_step(
    user_hash: str,
    job_id: str,
    step_name: str,
    detail: str = "",
    debug_keys: dict | None = None,
    thumbnail_keys: dict | None = None,
) -> None:
    """Update job record to reflect the currently running step.

    Args:
        user_hash: User partition key.
        job_id: Job sort key.
        step_name: Name of the step now running (e.g. ``"load"``).
        detail: Human-readable detail shown in the UI.
        debug_keys: Mapping of label → relative S3 key for full-res debug images.
            Stored in the ``debug_keys`` DynamoDB map. API prefixes user_hash when presigning.
        thumbnail_keys: Mapping of label → relative S3 key for 400px thumbnails.
            Same label namespace as debug_keys (e.g. ``"01_loaded"``, ``"07_photo_01_deglared"``).
            Stored in the ``thumbnail_keys`` DynamoDB map. API presigns all entries for the
            step-detail page and the ``01_loaded`` entry as the card before-thumbnail.
    """
    now = datetime.now(timezone.utc).isoformat()
    update_expr = "SET current_step = :cs, step_detail = :sd, updated_at = :ua"
    expr_values: dict[str, Any] = {":cs": step_name, ":sd": detail, ":ua": now}
    expr_names: dict[str, str] = {}

    if debug_keys:
        for attr_key, s3_key in debug_keys.items():
            s = _safe(attr_key)
            update_expr += f", debug_keys.#dk_{s} = :dkv_{s}"
            expr_values[f":dkv_{s}"] = s3_key
            expr_names[f"#dk_{s}"] = attr_key

    if thumbnail_keys:
        for attr_key, s3_key in thumbnail_keys.items():
            s = _safe(attr_key)
            update_expr += f", thumbnail_keys.#tk_{s} = :tkv_{s}"
            expr_values[f":tkv_{s}"] = s3_key
            expr_names[f"#tk_{s}"] = attr_key

    try:
        kw: dict[str, Any] = {
            "Key": {"user_hash": user_hash, "job_id": job_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values,
        }
        if expr_names:
            kw["ExpressionAttributeNames"] = expr_names
        jobs_table.update_item(**kw)
    except Exception as exc:
        logger.warning("update_step DynamoDB error (non-fatal): %s", exc)


def finalize_job(
    user_hash: str,
    job_id: str,
    output_keys: list[str],
    processing_time: float = 0.0,
) -> None:
    """Mark job as complete with final output keys.

    output_keys are relative to the user_hash prefix (e.g. "output/Photo01.jpg").
    We store them with the user_hash prefix so api/jobs.py can generate correct
    presigned URLs directly: "{user_hash}/output/Photo01.jpg".
    """
    now = datetime.now(timezone.utc).isoformat()
    # Prefix keys with user_hash so full S3 paths are stored in DynamoDB
    full_keys = [
        k if k.startswith(f"{user_hash}/") else f"{user_hash}/{k}"
        for k in output_keys
    ]
    try:
        jobs_table.update_item(
            Key={"user_hash": user_hash, "job_id": job_id},
            UpdateExpression=(
                "SET #s = :s, current_step = :cs, step_detail = :sd, "
                "output_keys = :ok, photo_count = :pc, "
                "processing_time = :pt, updated_at = :ua"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "complete",
                ":cs": "done",
                ":sd": f"{len(full_keys)} photo(s) processed",
                ":ok": full_keys,
                ":pc": len(full_keys),
                ":pt": int(processing_time),
                ":ua": now,
            },
        )
        logger.info("Job %s marked complete (%d photos)", job_id, len(full_keys))
    except Exception as exc:
        logger.error("finalize_job DynamoDB error: %s", exc)


# ── Reprocess skip helpers ────────────────────────────────────────────────────

def skip_this_photo(event: dict) -> bool:
    """Return True if this photo iteration should be skipped.

    Only relevant when reprocess_photo_index targets a single photo.
    Has no knowledge of step order — that decision lives in the state machine.
    """
    reprocess_idx = event.get("reprocess_photo_index")
    photo_idx = event.get("photo_index")
    if reprocess_idx is not None and photo_idx is not None:
        return int(photo_idx) != int(reprocess_idx)
    return False


def get_existing_output_key(user_hash: str, job_id: str, photo_index: int) -> str:
    """Return the relative output_key for *photo_index* from the DynamoDB job record.

    Used by the color_restore handler when a photo is skipped during reprocess
    so that finalize() still receives a valid output_key for every photo.
    Falls back to the predictable key pattern if the DynamoDB lookup fails.
    """
    idx = f"{photo_index:02d}"
    try:
        resp = jobs_table.get_item(Key={"user_hash": user_hash, "job_id": job_id})
        item = resp.get("Item", {})
        for key in item.get("output_keys", []):
            key_str = str(key)
            # output_keys are stored with user_hash prefix
            if f"Photo{idx}." in key_str or f"_Photo{idx}." in key_str:
                if key_str.startswith(f"{user_hash}/"):
                    return key_str[len(f"{user_hash}/"):]
                return key_str
    except Exception as exc:
        logger.warning("get_existing_output_key failed for photo %d: %s (using fallback)", photo_index, exc)
    return ""  # caller falls back to predictable pattern


def fail_job(user_hash: str, job_id: str, error_message: str) -> None:
    """Mark job as failed."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        jobs_table.update_item(
            Key={"user_hash": user_hash, "job_id": job_id},
            UpdateExpression="SET #s = :s, error_message = :em, updated_at = :ua",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "failed",
                ":em": error_message[:2000],  # truncate long errors
                ":ua": now,
            },
        )
        logger.error("Job %s marked failed: %s", job_id, error_message[:200])
    except Exception as exc:
        logger.error("fail_job DynamoDB error: %s", exc)
