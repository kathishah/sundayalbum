#!/usr/bin/env python3
"""One-time backfill: generate 400px thumbnails for all debug images in existing jobs.

For each job, reads debug_keys from DynamoDB and, for any label that does not yet
have a corresponding entry in thumbnail_keys:
  1. Downloads the debug JPEG from S3 (relative key → {user_hash}/{key})
  2. Resizes to 400px wide
  3. Uploads as thumbnails/{stem}_{label}.jpg
  4. Collects all new entries, then does a single DynamoDB update per job

After this backfill:
  • GET /jobs   → thumbnail_url  (01_loaded thumbnail for library card)
  • GET /jobs/{id} → thumbnail_urls (all step thumbnails for Phase 5 step-detail)

The AWS account ID is read from the AWS_ACCOUNT_ID env var, or looked up from your
current AWS credentials (STS). It is not stored in the repo.

Usage:
    # Dry-run (shows what would happen, no writes)
    python scripts/backfill_thumbnails.py --stage dev --dry-run

    # Live run against dev
    python scripts/backfill_thumbnails.py --stage dev

    # Live run against prod
    python scripts/backfill_thumbnails.py --stage prod
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime, timezone

import boto3
from PIL import Image

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # Only needed for HEIC upload fallback; debug images are always JPEG

def _account_id() -> str:
    """AWS account ID: ``AWS_ACCOUNT_ID`` env var, else the caller's own account (STS)."""
    env = os.environ.get("AWS_ACCOUNT_ID")
    if env:
        return env
    return boto3.client("sts").get_caller_identity()["Account"]


REGION = "us-west-2"
THUMB_WIDTH = 400
THUMB_QUALITY = 85


def bucket_name(stage: str) -> str:
    base = f"sundayalbum-data-{_account_id()}-{REGION}"
    return base if stage == "prod" else f"{base}-{stage}"


def table_name(stage: str) -> str:
    return "sa-jobs" if stage == "prod" else f"sa-jobs-{stage}"


def scan_all_jobs(table) -> list[dict]:
    """Scan the full DynamoDB table (handles pagination)."""
    items: list[dict] = []
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items


def make_thumbnail(jpeg_bytes: bytes) -> bytes:
    """Resize image bytes to THUMB_WIDTH wide, return JPEG bytes."""
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    w, h = img.size
    new_h = max(1, int(round(h * THUMB_WIDTH / w)))
    thumb = img.resize((THUMB_WIDTH, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
    return buf.getvalue()


def backfill(stage: str, dry_run: bool) -> None:
    BUCKET = bucket_name(stage)
    s3 = boto3.client("s3", region_name=REGION)
    dynamo = boto3.resource("dynamodb", region_name=REGION)
    table = dynamo.Table(table_name(stage))

    print(f"Scanning {table_name(stage)} in {BUCKET}…")
    items = scan_all_jobs(table)
    print(f"Found {len(items)} total jobs\n")

    total_ok = total_skipped = total_errors = 0

    for item in items:
        user_hash: str = item.get("user_hash", "")
        job_id: str = item.get("job_id", "")
        stem: str = item.get("input_stem", job_id)
        debug_keys: dict = item.get("debug_keys", {})
        existing_thumbs: set = set(item.get("thumbnail_keys", {}).keys())

        # Determine which labels need thumbnails
        missing = {
            label: rel_key
            for label, rel_key in debug_keys.items()
            if label not in existing_thumbs
        }

        if not missing:
            continue

        print(f"Job {job_id[:16]}… stem={stem}  missing={len(missing)} thumbnail(s)")

        new_thumb_keys: dict = {}  # label → relative thumbnail key

        for label, debug_rel_key in missing.items():
            src_s3_key = f"{user_hash}/{debug_rel_key}"
            thumb_rel_key = f"thumbnails/{stem}_{label}.jpg"
            thumb_s3_key = f"{user_hash}/{thumb_rel_key}"

            print(f"  [{label}]")
            print(f"    src  s3://{BUCKET}/{src_s3_key}")
            print(f"    dest s3://{BUCKET}/{thumb_s3_key}")

            if dry_run:
                print("    [DRY RUN] would generate & upload")
                new_thumb_keys[label] = thumb_rel_key
                total_ok += 1
                continue

            # Download debug image
            try:
                resp = s3.get_object(Bucket=BUCKET, Key=src_s3_key)
                src_bytes = resp["Body"].read()
            except Exception as exc:
                print(f"    SKIP — cannot download source: {exc}")
                total_skipped += 1
                continue

            # Resize to thumbnail
            try:
                thumb_bytes = make_thumbnail(src_bytes)
            except Exception as exc:
                print(f"    ERROR resizing: {exc}")
                total_errors += 1
                continue

            # Upload thumbnail
            try:
                s3.put_object(
                    Bucket=BUCKET,
                    Key=thumb_s3_key,
                    Body=thumb_bytes,
                    ContentType="image/jpeg",
                )
                print(f"    uploaded {len(thumb_bytes) // 1024}KB")
                new_thumb_keys[label] = thumb_rel_key
                total_ok += 1
            except Exception as exc:
                print(f"    ERROR uploading: {exc}")
                total_errors += 1

        # One DynamoDB update per job with all new thumbnail_keys
        if new_thumb_keys and not dry_run:
            try:
                now = datetime.now(timezone.utc).isoformat()
                # Merge with any existing thumbnail_keys so we write the full map at once.
                # Using sub-key dot-path notation (thumbnail_keys.#tk_foo) fails when the
                # parent attribute doesn't exist yet — DynamoDB requires the map to exist
                # before you can set individual keys inside it.
                merged = dict(item.get("thumbnail_keys") or {})
                merged.update(new_thumb_keys)

                table.update_item(
                    Key={"user_hash": user_hash, "job_id": job_id},
                    UpdateExpression="SET thumbnail_keys = :tk, updated_at = :ua",
                    ExpressionAttributeValues={":tk": merged, ":ua": now},
                )
                print(f"  DynamoDB updated ({len(new_thumb_keys)} thumbnail_keys written)")
            except Exception as exc:
                print(f"  ERROR updating DynamoDB: {exc}")
                total_errors += 1

        print()

    print(f"Done.  generated={total_ok}  skipped={total_skipped}  errors={total_errors}")
    if total_errors:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill step thumbnails for all jobs")
    parser.add_argument("--stage", choices=["dev", "prod"], default="dev")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without writing anything")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN — no writes will occur ===\n")
    backfill(args.stage, args.dry_run)


if __name__ == "__main__":
    main()
