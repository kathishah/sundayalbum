"""Helper functions for handler tests (not pytest fixtures)."""

from __future__ import annotations

import io
import time
from datetime import datetime, timezone

import boto3
import numpy as np
from PIL import Image

REGION = "us-west-2"
S3_BUCKET = "sa-data-test"
JOBS_TABLE = "sa-jobs-test"

# Minimal 4×4 RGB float32 image returned by all mocked step functions
FAKE_IMAGE = np.zeros((4, 4, 3), dtype=np.float32)


def make_base_event(user_hash: str, job_id: str, stem: str = "test") -> dict:
    """Minimal Step Functions event for a handler invocation."""
    return {
        "user_hash": user_hash,
        "job_id": job_id,
        "stem": stem,
        "upload_key": f"{user_hash}/jobs/{job_id}/uploads/{stem}.HEIF",
        "start_time": time.time(),
        "config": {},
        "user_keys": {},
    }


def create_job_record(user_hash: str, job_id: str, stem: str = "test") -> None:
    """Insert a minimal job record in the moto DynamoDB table."""
    ddb = boto3.resource("dynamodb", region_name=REGION)
    now = datetime.now(timezone.utc).isoformat()
    ddb.Table(JOBS_TABLE).put_item(
        Item={
            "user_hash": user_hash,
            "job_id": job_id,
            "status": "processing",
            "current_step": "load",
            "step_detail": "",
            "input_filename": f"{stem}.heic",
            "input_stem": stem,
            "upload_key": f"{user_hash}/jobs/{job_id}/uploads/{stem}.HEIF",
            "photo_count": 0,
            "output_keys": [],
            "debug_keys": {},
            "thumbnail_keys": {},
            "created_at": now,
            "updated_at": now,
            "ttl": int(time.time()) + 30 * 24 * 3600,
            "execution_arn": "",
            "error_message": "",
            "processing_time": 0,
        }
    )


def put_s3_image(user_hash: str, key: str) -> None:
    """Put a minimal JPEG into the moto S3 bucket."""
    img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8), "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    boto3.client("s3", region_name=REGION).put_object(
        Bucket=S3_BUCKET,
        Key=f"{user_hash}/{key}",
        Body=buf.getvalue(),
    )


def get_job(user_hash: str, job_id: str) -> dict:
    """Fetch the job record from moto DynamoDB."""
    ddb = boto3.resource("dynamodb", region_name=REGION)
    return ddb.Table(JOBS_TABLE).get_item(
        Key={"user_hash": user_hash, "job_id": job_id}
    )["Item"]
