"""Tests 7–21: Job lifecycle, rate limiting, and reprocessing."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

import boto3
import pytest
import jobs as jobs_module
from helpers import (
    JOBS_TABLE,
    REGION,
    S3_BUCKET,
    USER_SETTINGS_TABLE,
    insert_job,
    make_event,
    make_session,
)


def _hash(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()




def _auth(email: str = "user@example.com") -> tuple[str, str, str]:
    """Return (email, user_hash, token) for a fresh session."""
    user_hash = _hash(email)
    token = make_session(email, user_hash)
    return email, user_hash, token


def _create_job(token: str, filename: str = "test.heic", size: int = 1024) -> dict:
    """Call POST /jobs and return the parsed response body."""
    event = make_event("POST /jobs", body={"filename": filename, "size": size}, token=token)
    resp = jobs_module.handler(event, None)
    return json.loads(resp["body"]), resp["statusCode"]


def _put_upload(user_hash: str, job_id: str, filename: str = "test.heic") -> str:
    """Put a dummy file into the moto S3 bucket at the upload key."""
    key = f"{user_hash}/jobs/{job_id}/uploads/{filename}"
    boto3.client("s3", region_name=REGION).put_object(
        Bucket=S3_BUCKET, Key=key, Body=b"fake-image-data"
    )
    return key


# ── 7. create_job initializes empty maps ─────────────────────────────────────


def test_create_job_initializes_maps():
    """POST /jobs creates a DDB item with debug_keys:{} and thumbnail_keys:{}."""
    _, user_hash, token = _auth()
    body, status = _create_job(token)

    assert status == 201
    job_id = body["job_id"]

    ddb = boto3.resource("dynamodb", region_name=REGION)
    item = ddb.Table(JOBS_TABLE).get_item(
        Key={"user_hash": user_hash, "job_id": job_id}
    )["Item"]

    assert item["debug_keys"] == {}
    assert item["thumbnail_keys"] == {}
    assert item["status"] == "uploading"


def test_create_job_uses_size_limited_post_and_job_scoped_key() -> None:
    _, user_hash, token = _auth()
    body, status = _create_job(token, filename="Album.HEIF")

    assert status == 201
    assert body["upload_key"].startswith(
        f"{user_hash}/jobs/{body['job_id']}/uploads/"
    )
    policy = json.loads(base64.b64decode(body["upload_fields"]["policy"]))
    assert ["content-length-range", 1, 200 * 1024 * 1024] in policy["conditions"]


def test_daily_job_count_ignores_more_than_100_older_jobs() -> None:
    _, user_hash, _ = _auth("history@example.com")
    now = datetime.now(UTC)
    yesterday = (now - timedelta(days=1)).isoformat()

    for i in range(125):
        insert_job(
            user_hash,
            f"000000000000000000000000{i:02X}",
            created_at=yesterday,
        )
    today = now.strftime("%Y-%m-%d")
    for i in range(3):
        insert_job(
            user_hash,
            jobs_module.generate_ulid(),
            created_at=f"{today}T12:00:0{i}+00:00",
        )

    assert jobs_module._count_jobs_today(user_hash) == 3


def test_daily_job_count_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, user_hash, token = _auth("count-error@example.com")
    body, _ = _create_job(token)
    job_id = body["job_id"]
    _put_upload(user_hash, job_id)

    def fail_query(**_kwargs):
        raise RuntimeError("DynamoDB unavailable")

    monkeypatch.setattr(jobs_module.jobs_table, "query", fail_query)
    event = make_event("POST /jobs/start", path_params={"jobId": job_id}, token=token)
    response = jobs_module.handler(event, None)

    assert response["statusCode"] == 500


# ── 8. create_job unsupported format ─────────────────────────────────────────


def test_create_job_unsupported_format():
    """POST /jobs with a .bmp file returns 400."""
    _, _, token = _auth()
    body, status = _create_job(token, filename="photo.bmp")
    assert status == 400


# ── 9. create_job too large ───────────────────────────────────────────────────


def test_create_job_too_large():
    """POST /jobs with size > 200 MB returns 400."""
    _, _, token = _auth()
    body, status = _create_job(token, size=201 * 1024 * 1024)
    assert status == 400


# ── 10. start_job without S3 upload returns 400 ───────────────────────────────


def test_start_job_no_s3_upload():
    """POST /jobs/{id}/start before the file is in S3 returns 400."""
    _, user_hash, token = _auth()
    body, _ = _create_job(token)
    job_id = body["job_id"]

    # Do NOT put file in S3
    event = make_event(
        "POST /jobs/start",
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 400


# ── 11. get_job returns debug_urls after pipeline writes debug_keys ───────────


def test_get_job_returns_debug_urls():
    """GET /jobs/{id} returns debug_urls map with presigned URLs."""
    _, user_hash, token = _auth()
    body, _ = _create_job(token)
    job_id = body["job_id"]

    # Simulate pipeline writing debug_keys
    debug_key = "debug/test_01_loaded.jpg"
    boto3.client("s3", region_name=REGION).put_object(
        Bucket=S3_BUCKET, Key=f"{user_hash}/{debug_key}", Body=b"jpg"
    )
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(JOBS_TABLE).update_item(
        Key={"user_hash": user_hash, "job_id": job_id},
        UpdateExpression="SET debug_keys = :dk",
        ExpressionAttributeValues={":dk": {"01_loaded": debug_key}},
    )

    event = make_event("GET /jobs/{jobId}", path_params={"jobId": job_id}, token=token)
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])
    assert "01_loaded" in data.get("debug_urls", {})
    assert data["debug_urls"]["01_loaded"].startswith("https://")


# ── 12. get_job returns thumbnail_urls after pipeline writes thumbnail_keys ───


def test_get_job_returns_thumbnail_urls():
    """GET /jobs/{id} returns thumbnail_urls map and thumbnail_url singular."""
    _, user_hash, token = _auth()
    body, _ = _create_job(token)
    job_id = body["job_id"]

    thumb_key = "thumbnails/test_01_loaded.jpg"
    boto3.client("s3", region_name=REGION).put_object(
        Bucket=S3_BUCKET, Key=f"{user_hash}/{thumb_key}", Body=b"jpg"
    )
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(JOBS_TABLE).update_item(
        Key={"user_hash": user_hash, "job_id": job_id},
        UpdateExpression="SET thumbnail_keys = :tk",
        ExpressionAttributeValues={":tk": {"01_loaded": thumb_key}},
    )

    event = make_event("GET /jobs/{jobId}", path_params={"jobId": job_id}, token=token)
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])
    assert "01_loaded" in data.get("thumbnail_urls", {})
    assert data["thumbnail_url"].startswith("https://")


# ── 13. list_jobs returns thumbnail_url ───────────────────────────────────────


def test_list_jobs_returns_thumbnail_url():
    """GET /jobs returns thumbnail_url for jobs that have thumbnail_keys['01_loaded']."""
    _, user_hash, token = _auth()
    body, _ = _create_job(token)
    job_id = body["job_id"]

    thumb_key = "thumbnails/test_01_loaded.jpg"
    boto3.client("s3", region_name=REGION).put_object(
        Bucket=S3_BUCKET, Key=f"{user_hash}/{thumb_key}", Body=b"jpg"
    )
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(JOBS_TABLE).update_item(
        Key={"user_hash": user_hash, "job_id": job_id},
        UpdateExpression="SET thumbnail_keys = :tk",
        ExpressionAttributeValues={":tk": {"01_loaded": thumb_key}},
    )

    event = make_event("GET /jobs", token=token)
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200
    jobs = json.loads(resp["body"])["jobs"]
    target = next(j for j in jobs if j["job_id"] == job_id)
    assert target["thumbnail_url"].startswith("https://")


# ── 14. delete_job ────────────────────────────────────────────────────────────


def test_delete_job():
    """DELETE /jobs/{id} removes the job from DynamoDB."""
    _, user_hash, token = _auth()
    body, _ = _create_job(token)
    job_id = body["job_id"]

    event = make_event(
        "DELETE /jobs/{jobId}",
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200

    ddb = boto3.resource("dynamodb", region_name=REGION)
    item = ddb.Table(JOBS_TABLE).get_item(
        Key={"user_hash": user_hash, "job_id": job_id}
    ).get("Item")
    assert item is None


# ── 15. get_job wrong user returns 404 ────────────────────────────────────────


def test_get_job_wrong_user():
    """GET /jobs/{id} for another user's job returns 404 (not 403)."""
    _, user_hash_a, token_a = _auth("user-a@example.com")
    _, _user_hash_b, token_b = _auth("user-b@example.com")

    body, _ = _create_job(token_a)
    job_id = body["job_id"]

    event = make_event("GET /jobs/{jobId}", path_params={"jobId": job_id}, token=token_b)
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 404


# ── 16. rate_limit_enforced ───────────────────────────────────────────────────


def test_rate_limit_enforced():
    """21st job start in the same UTC day returns 429."""
    email = "limited@example.com"
    user_hash = _hash(email)
    token = make_session(email, user_hash)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Pre-insert 19 fake jobs with today's date
    ddb = boto3.resource("dynamodb", region_name=REGION)
    for i in range(19):
        insert_job(
            user_hash,
            jobs_module.generate_ulid(),
            status="complete",
            created_at=f"{today}T00:00:0{i % 10}.000000+00:00",
        )

    # Create a real job (this becomes the 20th record with today's date)
    body, _ = _create_job(token)
    job_id = body["job_id"]
    _put_upload(user_hash, job_id)

    event = make_event(
        "POST /jobs/start",
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 429


# ── 17. rate_limit_bypassed_with_own_keys ────────────────────────────────────


def test_rate_limit_bypassed_with_own_keys():
    """User with both API keys stored bypasses the daily job limit."""
    email = "power@example.com"
    user_hash = _hash(email)
    token = make_session(email, user_hash)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Pre-insert 20 fake jobs (already at the limit)
    ddb = boto3.resource("dynamodb", region_name=REGION)
    for i in range(20):
        insert_job(
            user_hash,
            jobs_module.generate_ulid(),
            status="complete",
            created_at=f"{today}T00:00:{i:02d}.000000+00:00",
        )

    # Store both user API keys
    ddb.Table(USER_SETTINGS_TABLE).put_item(
        Item={
            "user_hash": user_hash,
            "anthropic_api_key": "sk-ant-test",
            "openai_api_key": "sk-openai-test",
        }
    )

    body, _ = _create_job(token)
    job_id = body["job_id"]
    _put_upload(user_hash, job_id)

    event = make_event(
        "POST /jobs/start",
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    # Should be 200 (started) not 429
    assert resp["statusCode"] == 200
    execution_arn = json.loads(resp["body"])["execution_arn"]
    execution = boto3.client("stepfunctions", region_name=REGION).describe_execution(
        executionArn=execution_arn
    )
    assert "user_keys" not in json.loads(execution["input"])
    assert "sk-ant-test" not in execution["input"]
    assert "sk-openai-test" not in execution["input"]


def test_reprocess_rejects_api_keys_in_config() -> None:
    _, user_hash, token = _auth("config-key@example.com")
    job_id = str(uuid.uuid4())
    insert_job(user_hash, job_id, status="complete")

    event = make_event(
        "POST /jobs/reprocess",
        body={"from_step": "color_restore", "config": {"anthropic_api_key": "sk-ant-secret"}},
        path_params={"jobId": job_id},
        token=token,
    )
    response = jobs_module.handler(event, None)

    assert response["statusCode"] == 400


# ── 18. rate_limit_admin_bypass ───────────────────────────────────────────────


def test_rate_limit_admin_bypass():
    """Admin email bypasses rate limit regardless of job count."""
    email = "admin@example.com"
    user_hash = _hash(email)
    token = make_session(email, user_hash)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    ddb = boto3.resource("dynamodb", region_name=REGION)
    for i in range(20):
        insert_job(
            user_hash,
            jobs_module.generate_ulid(),
            status="complete",
            created_at=f"{today}T00:00:{i:02d}.000000+00:00",
        )

    body, _ = _create_job(token)
    job_id = body["job_id"]
    _put_upload(user_hash, job_id)

    event = make_event(
        "POST /jobs/start",
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200


# ── 19. reprocess valid step ─────────────────────────────────────────────────


def test_reprocess_valid_step():
    """POST /jobs/{id}/reprocess with a valid from_step returns 200."""
    _, user_hash, token = _auth()
    job_id = str(uuid.uuid4())
    insert_job(user_hash, job_id, status="complete", extra={"input_stem": "test", "photo_count": 1})

    event = make_event(
        "POST /jobs/reprocess",
        body={"from_step": "color_restore"},
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])
    assert "execution_arn" in data


# ── 20a. reprocess input always includes reprocess_photo_index ───────────────


def test_reprocess_sfn_input_always_has_reprocess_photo_index():
    """SFN start input always contains reprocess_photo_index (None when not targeted).

    PrepareMap and the Map item_selector both use '$.reprocess_photo_index' via
    JSONPath — the field must exist in the event even for a full reprocess,
    otherwise Step Functions raises States.Runtime.
    """
    _, user_hash, token = _auth()
    job_id = str(uuid.uuid4())
    insert_job(user_hash, job_id, status="complete", extra={"input_stem": "test", "photo_count": 1})
    boto3.resource("dynamodb", region_name=REGION).Table(USER_SETTINGS_TABLE).put_item(
        Item={
            "user_hash": user_hash,
            "anthropic_api_key": "sk-ant-reprocess-secret",
            "openai_api_key": "sk-openai-reprocess-secret",
        }
    )

    event = make_event(
        "POST /jobs/reprocess",
        body={"from_step": "page_detect"},   # no photo_index → reprocess_photo_index must be None
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 200

    # Retrieve the SFN execution input and assert reprocess_photo_index is present
    sfn = boto3.client("stepfunctions", region_name=REGION)
    executions = sfn.list_executions(
        stateMachineArn=f"arn:aws:states:{REGION}:123456789012:stateMachine:sa-pipeline-test"
    )["executions"]
    assert executions, "No SFN execution was started"
    last = sorted(executions, key=lambda e: e["startDate"], reverse=True)[0]
    execution = sfn.describe_execution(executionArn=last["executionArn"])
    sfn_input = json.loads(execution["input"])

    assert "reprocess_photo_index" in sfn_input, (
        "reprocess_photo_index must always be present in SFN input — PrepareMap uses $.reprocess_photo_index"
    )
    assert sfn_input["reprocess_photo_index"] is None
    assert "user_keys" not in sfn_input
    assert "sk-ant-reprocess-secret" not in execution["input"]
    assert "sk-openai-reprocess-secret" not in execution["input"]


# ── 20. reprocess invalid step ───────────────────────────────────────────────


def test_reprocess_invalid_step():
    """POST /jobs/{id}/reprocess with an unknown step name returns 400."""
    _, user_hash, token = _auth()
    job_id = str(uuid.uuid4())
    insert_job(user_hash, job_id, status="complete")

    event = make_event(
        "POST /jobs/reprocess",
        body={"from_step": "not_a_real_step"},
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 400


# ── 21. reprocess while processing returns 409 ───────────────────────────────


def test_reprocess_while_processing():
    """POST /jobs/{id}/reprocess on a running job returns 409."""
    _, user_hash, token = _auth()
    job_id = str(uuid.uuid4())
    insert_job(user_hash, job_id, status="processing")

    event = make_event(
        "POST /jobs/reprocess",
        body={"from_step": "color_restore"},
        path_params={"jobId": job_id},
        token=token,
    )
    resp = jobs_module.handler(event, None)
    assert resp["statusCode"] == 409
