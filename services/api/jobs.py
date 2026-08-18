"""Sunday Album jobs Lambda handler.

Routes:
    GET    /jobs                         list user's jobs
    POST   /jobs                         create job + presigned upload URL
    GET    /jobs/{jobId}                 job status + presigned output/debug URLs
    DELETE /jobs/{jobId}                 cancel / delete
    POST   /jobs/{jobId}/start           trigger pipeline (Step Functions in Phase 2)
    POST   /jobs/{jobId}/reprocess       reprocess from step (Phase 5 placeholder)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from boto3.dynamodb.conditions import Key

from common import (
    DAILY_JOB_LIMIT,
    S3_BUCKET,
    bad_request,
    created,
    error,
    generate_ulid,
    internal,
    is_admin,
    jobs_table,
    not_found,
    ok,
    parse_body,
    presign_get,
    presign_get_if_exists,
    presign_put,
    require_auth,
    s3_client,
    too_many_requests,
    unauthorized,
    user_settings_table,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = {".heic", ".heif", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_MB = 200
JOB_TTL_DAYS = 30

# Step Functions state machine ARN (filled in Phase 2)
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")


# ── Router ─────────────────────────────────────────────────────────────────────
def handler(event: dict, context: Any) -> dict:
    route = event.get("routeKey", "") or event.get("rawPath", "")
    path_params = event.get("pathParameters") or {}
    job_id = path_params.get("jobId")
    logger.info("Jobs route: %s  jobId=%s", route, job_id)

    # All jobs routes require auth
    auth_result = require_auth(event)
    if isinstance(auth_result, dict):
        return auth_result  # 401 response
    email, user_hash = auth_result

    try:
        if "reprocess" in route:
            return _handle_reprocess(job_id, event, user_hash)
        if "start" in route:
            return _handle_start(job_id, user_hash, email)
        if job_id:
            method = event.get("requestContext", {}).get("http", {}).get("method", "")
            if method == "DELETE":
                return _handle_delete(job_id, user_hash)
            return _handle_get(job_id, user_hash)
        # /jobs
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        if method == "POST":
            return _handle_create(event, user_hash)
        return _handle_list(user_hash)
    except Exception as exc:
        logger.exception("Unhandled error in jobs handler: %s", exc)
        return internal()


# ── List jobs ─────────────────────────────────────────────────────────────────
def _handle_list(user_hash: str) -> dict:
    try:
        resp = jobs_table.query(
            KeyConditionExpression=Key("user_hash").eq(user_hash),
            ScanIndexForward=False,  # newest first (ULID sort key)
            Limit=50,
        )
    except Exception as exc:
        logger.error("DynamoDB query failed: %s", exc)
        return internal()

    TTL = 7 * 24 * 3600
    jobs = []
    for item in resp.get("Items", []):
        job = _serialize_job(item)
        user_hash_item = item.get("user_hash", "")
        # Only presign the 01_loaded thumbnail for the library card before-image.
        # Full thumbnail_urls map is returned by GET /jobs/{id} for the step-detail page.
        thumb_keys_map = item.get("thumbnail_keys", {})
        before_key = thumb_keys_map.get("01_loaded", "")
        if before_key:
            try:
                job["thumbnail_url"] = presign_get(f"{user_hash_item}/{before_key}", expires=TTL)
            except Exception:
                pass
        elif item.get("thumbnail_key"):
            # Backwards compat: old single thumbnail_key stored as full path
            try:
                job["thumbnail_url"] = presign_get(item["thumbnail_key"], expires=TTL)
            except Exception:
                pass
        jobs.append(job)
    return ok({"jobs": jobs, "count": len(jobs)})


# ── Create job ─────────────────────────────────────────────────────────────────
def _handle_create(event: dict, user_hash: str) -> dict:
    body = parse_body(event)
    filename = (body.get("filename") or "").strip()
    file_size = body.get("size", 0)

    if not filename:
        return bad_request("filename is required")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return bad_request(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if file_size and file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return bad_request(f"File too large (max {MAX_FILE_SIZE_MB} MB)")

    # Build job record
    job_id = generate_ulid()
    stem = Path(filename).stem
    now_iso = datetime.now(timezone.utc).isoformat()
    now_ts = int(time.time())

    upload_key = f"{user_hash}/uploads/{filename}"

    item: dict[str, Any] = {
        "user_hash": user_hash,
        "job_id": job_id,
        "status": "uploading",
        "current_step": "",
        "step_detail": "",
        "input_filename": filename,
        "input_stem": stem,
        "upload_key": upload_key,
        "photo_count": 0,
        "output_keys": [],
        "debug_keys": {},
        "thumbnail_keys": {},
        "created_at": now_iso,
        "updated_at": now_iso,
        "ttl": now_ts + JOB_TTL_DAYS * 24 * 3600,
        "execution_arn": "",
        "error_message": "",
        "processing_time": 0,
    }

    try:
        jobs_table.put_item(Item=item)
    except Exception as exc:
        logger.error("DynamoDB put_item failed: %s", exc)
        return internal("Could not create job")

    # Generate presigned PUT URL for direct browser-to-S3 upload
    try:
        upload_url = presign_put(upload_key, expires=3600)
    except Exception as exc:
        logger.error("Failed to generate presigned PUT URL: %s", exc)
        return internal("Could not generate upload URL")

    logger.info("Created job %s for user %s...", job_id, user_hash[:8])
    return created(
        {
            "job_id": job_id,
            "upload_url": upload_url,
            "upload_key": upload_key,
            "expires_in": 3600,
        }
    )


# ── Get job ────────────────────────────────────────────────────────────────────
def _handle_get(job_id: str, user_hash: str) -> dict:
    item = _get_job_or_none(job_id, user_hash)
    if item is None:
        return not_found(f"Job {job_id} not found")

    # Enrich with presigned URLs for debug + output images
    # All URLs use 7-day expiry — access is already controlled by the session token;
    # expiry is not an additional security boundary and short expiry breaks the UI.
    TTL = 7 * 24 * 3600
    enriched = _serialize_job(item)
    enriched["output_urls"] = _presign_keys(item.get("output_keys", []))

    # debug_keys are stored relative (without user_hash prefix) — prefix when presigning
    enriched["debug_urls"] = {
        label: presign_get(f"{user_hash}/{key}", expires=TTL)
        for label, key in item.get("debug_keys", {}).items()
        if key
    }

    # thumbnail_keys: 400px versions of each debug image, same label namespace.
    # All step thumbnails returned for Phase 5 step-detail page.
    # thumbnail_url (singular) = 01_loaded thumbnail = card before-image convenience field.
    thumb_keys_map = item.get("thumbnail_keys", {})
    if thumb_keys_map:
        enriched["thumbnail_urls"] = {
            label: presign_get(f"{user_hash}/{key}", expires=TTL)
            for label, key in thumb_keys_map.items()
            if key
        }
        if "01_loaded" in thumb_keys_map:
            enriched["thumbnail_url"] = presign_get(
                f"{user_hash}/{thumb_keys_map['01_loaded']}", expires=TTL
            )
    elif item.get("thumbnail_key"):
        # Backwards compat: old single thumbnail_key stored as full path
        enriched["thumbnail_url"] = presign_get(item["thumbnail_key"], expires=TTL)

    # Presigned URL for original upload (download / raw access)
    upload_key = item.get("upload_key", "")
    if upload_key:
        enriched["upload_url"] = presign_get_if_exists(upload_key, expires=TTL)

    return ok(enriched)


# ── Delete job ─────────────────────────────────────────────────────────────────
def _handle_delete(job_id: str, user_hash: str) -> dict:
    item = _get_job_or_none(job_id, user_hash)
    if item is None:
        return not_found(f"Job {job_id} not found")

    try:
        jobs_table.delete_item(Key={"user_hash": user_hash, "job_id": job_id})
    except Exception as exc:
        logger.error("DynamoDB delete_item failed: %s", exc)
        return internal("Could not delete job")

    logger.info("Deleted job %s for user %s...", job_id, user_hash[:8])
    return ok({"message": "Job deleted", "job_id": job_id})


# ── Rate limit check ──────────────────────────────────────────────────────────
def _count_jobs_today(user_hash: str) -> int:
    """Count jobs started today (UTC) for rate limiting.

    Queries all jobs for the user today using created_at as a filter.
    ``created_at`` is an ISO-8601 string (e.g. "2026-03-26T14:23:00+00:00").
    We filter client-side after a partition-key-only query and cap at 50 items —
    more than enough to evaluate the 20-job limit without a table scan.
    """
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        from boto3.dynamodb.conditions import Attr, Key as DKey
        resp = jobs_table.query(
            KeyConditionExpression=DKey("user_hash").eq(user_hash),
            FilterExpression=Attr("created_at").begins_with(today_prefix),
            Select="COUNT",
            Limit=100,  # cap pages; 20-job limit makes this sufficient
        )
        return int(resp.get("Count", 0))
    except Exception as exc:
        logger.error("Rate limit count query failed: %s", exc)
        return 0  # fail open — don't block users if DynamoDB is unavailable


def _get_user_keys(user_hash: str) -> dict:
    """Fetch user-supplied API keys from user_settings table. Returns {} if none."""
    try:
        resp = user_settings_table.get_item(Key={"user_hash": user_hash})
        item = resp.get("Item", {})
        return {
            "anthropic_api_key": item.get("anthropic_api_key", ""),
            "openai_api_key":    item.get("openai_api_key", ""),
        }
    except Exception as exc:
        logger.warning("Could not fetch user API keys: %s", exc)
        return {}


# ── Start pipeline ─────────────────────────────────────────────────────────────
def _handle_start(job_id: str, user_hash: str, email: str) -> dict:
    item = _get_job_or_none(job_id, user_hash)
    if item is None:
        return not_found(f"Job {job_id} not found")

    if item.get("status") not in ("uploading", "failed"):
        return error(409, "conflict", f"Job is already {item.get('status')}")

    # Verify upload exists in S3
    upload_key = item.get("upload_key", "")
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=upload_key)
    except Exception:
        return bad_request(
            "Upload not found in S3. Please upload the file before starting."
        )

    # Fetch user-supplied API keys (may be empty — pipeline will use system keys)
    user_keys = _get_user_keys(user_hash)
    has_both_user_keys = bool(
        user_keys.get("anthropic_api_key") and user_keys.get("openai_api_key")
    )

    # Rate limit check: skip for admins and users who supply their own keys
    if not is_admin(email) and not has_both_user_keys:
        jobs_today = _count_jobs_today(user_hash)
        if jobs_today >= DAILY_JOB_LIMIT:
            logger.info(
                "Rate limit hit for user %s... (%d jobs today)", user_hash[:8], jobs_today
            )
            return too_many_requests(
                f"You've reached the daily limit of {DAILY_JOB_LIMIT} free jobs. "
                "Add your own API keys in Settings to continue."
            )

    now_iso = datetime.now(timezone.utc).isoformat()

    if STATE_MACHINE_ARN:
        # Phase 2: trigger Step Functions
        import json
        import boto3

        sfn = boto3.client("stepfunctions")
        execution_input = json.dumps(
            {
                "user_hash": user_hash,
                "job_id": job_id,
                "stem": item["input_stem"],
                "upload_key": upload_key,
                "start_time": time.time(),
                "config": {},
                "user_keys": user_keys,
                # Always present so PrepareMap and item_selector can safely use .$
                "start_from": "",
                "reprocess_photo_index": None,
            }
        )
        try:
            sfn_resp = sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=f"{job_id}",
                input=execution_input,
            )
            execution_arn = sfn_resp["executionArn"]
        except Exception as exc:
            logger.error("Step Functions start_execution failed: %s", exc)
            return internal("Could not start pipeline")

        jobs_table.update_item(
            Key={"user_hash": user_hash, "job_id": job_id},
            UpdateExpression=(
                "SET #s = :s, current_step = :cs, execution_arn = :ea, updated_at = :ua"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "processing",
                ":cs": "load",
                ":ea": execution_arn,
                ":ua": now_iso,
            },
        )
        logger.info("Started Step Functions execution %s for job %s", execution_arn, job_id)
        return ok({"status": "processing", "execution_arn": execution_arn})

    else:
        # Fallback: mark as processing without Step Functions (should not occur in prod)
        jobs_table.update_item(
            Key={"user_hash": user_hash, "job_id": job_id},
            UpdateExpression="SET #s = :s, current_step = :cs, updated_at = :ua",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "processing",
                ":cs": "load",
                ":ua": now_iso,
            },
        )
        logger.info(
            "Job %s marked processing (Step Functions not yet configured)", job_id
        )
        return ok(
            {
                "status": "processing",
                "note": "Pipeline not yet deployed. File is in S3.",
            }
        )


# ── Reprocess ─────────────────────────────────────────────────────────────────
_VALID_REPROCESS_STEPS = [
    "load", "normalize", "page_detect", "perspective", "photo_detect", "photo_split",
    "ai_orient", "glare_remove", "geometry", "color_restore",
]


def _handle_reprocess(job_id: str | None, event: dict, user_hash: str) -> dict:
    if not job_id:
        return bad_request("jobId is required")

    item = _get_job_or_none(job_id, user_hash)
    if item is None:
        return not_found(f"Job {job_id} not found")

    if item.get("status") not in ("complete", "failed"):
        return error(409, "conflict", f"Job is '{item.get('status')}' — only complete or failed jobs can be reprocessed")

    body = parse_body(event)
    from_step = (body.get("from_step") or "").strip()
    photo_index = body.get("photo_index")  # optional int
    config_overrides = body.get("config") or {}

    if from_step and from_step not in _VALID_REPROCESS_STEPS:
        return bad_request(
            f"Unknown step '{from_step}'. Valid steps: {', '.join(_VALID_REPROCESS_STEPS)}"
        )

    if photo_index is not None:
        try:
            photo_index = int(photo_index)
        except (TypeError, ValueError):
            return bad_request("photo_index must be an integer")

    if not STATE_MACHINE_ARN:
        return error(501, "not_implemented", "Pipeline not deployed")

    user_keys = _get_user_keys(user_hash)
    now_iso = datetime.now(timezone.utc).isoformat()

    import json
    import boto3

    sfn = boto3.client("stepfunctions")
    execution_input: dict = {
        "user_hash": user_hash,
        "job_id": job_id,
        "stem": item["input_stem"],
        "upload_key": item.get("upload_key", ""),
        "start_time": time.time(),
        "config": config_overrides,
        "user_keys": user_keys,
        "start_from": from_step,
        # photo_count is needed by PrepareMap when photo_split is skipped
        "photo_count": int(item.get("photo_count", 1)),
        # Always present so PrepareMap and Map item_selector can safely use .$
        "reprocess_photo_index": photo_index,  # None when not targeting a single photo
    }

    execution_name = f"{job_id}-r{int(time.time())}"
    try:
        sfn_resp = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(execution_input),
        )
        execution_arn = sfn_resp["executionArn"]
    except Exception as exc:
        logger.error("Step Functions start_execution (reprocess) failed: %s", exc)
        return internal("Could not start reprocessing")

    jobs_table.update_item(
        Key={"user_hash": user_hash, "job_id": job_id},
        UpdateExpression=(
            "SET #s = :s, current_step = :cs, step_detail = :sd, "
            "execution_arn = :ea, error_message = :em, updated_at = :ua"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "processing",
            ":cs": from_step,
            ":sd": f"Reprocessing from {from_step}"
            + (f" (photo {photo_index})" if photo_index is not None else ""),
            ":ea": execution_arn,
            ":em": "",
            ":ua": now_iso,
        },
    )
    logger.info(
        "Reprocess job %s from=%s photo_index=%s execution=%s",
        job_id, from_step, photo_index, execution_arn,
    )
    return ok({"status": "processing", "execution_arn": execution_arn, "from_step": from_step})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_job_or_none(job_id: str, user_hash: str) -> dict | None:
    """Fetch a job record, returning None if not found or not owned by user_hash."""
    try:
        resp = jobs_table.get_item(Key={"user_hash": user_hash, "job_id": job_id})
        return resp.get("Item")
    except Exception as exc:
        logger.error("DynamoDB get_item failed: %s", exc)
        return None


def _serialize_job(item: dict) -> dict:
    """Return a JSON-safe subset of a job record (strip DDB-specific types)."""
    return {
        "job_id": item.get("job_id", ""),
        "status": item.get("status", ""),
        "current_step": item.get("current_step", ""),
        "step_detail": item.get("step_detail", ""),
        "input_filename": item.get("input_filename", ""),
        "input_stem": item.get("input_stem", ""),
        "photo_count": int(item.get("photo_count", 0)),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
        "error_message": item.get("error_message", ""),
        "processing_time": float(item.get("processing_time", 0)),
        "execution_arn": item.get("execution_arn", ""),
        "output_keys": list(item.get("output_keys", [])),
    }


def _presign_keys(keys: list, expires: int = 7 * 24 * 3600) -> list[str]:
    """Generate presigned GET URLs for a list of S3 keys."""
    urls = []
    for key in keys:
        try:
            urls.append(presign_get(str(key), expires=expires))
        except Exception:
            pass
    return urls
