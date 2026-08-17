"""Sunday Album DynamoDB Streams broadcaster.

Triggered by DynamoDB Streams on the sa-jobs table. For each INSERT or MODIFY
event, pushes a step_update WebSocket message to all connections subscribed to
that job via API Gateway Management API.

Keeps the WebSocket protocol (connect/disconnect/$default) in websocket.py
and the pipeline event processing here — clear separation of concerns.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

from common import REGION, ws_table

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

WS_ENDPOINT = os.environ.get("WS_ENDPOINT", "")

# Step name → progress fraction (0.0 – 1.0).
# These are approximate midpoints; the frontend smooths between them.
_STEP_PROGRESS: dict[str, float] = {
    "load":          0.05,
    "normalize":     0.10,
    "page_detect":   0.20,
    "perspective":   0.25,
    "photo_detect":  0.30,
    "photo_split":   0.35,
    "ai_orient":     0.50,
    "glare_remove":  0.70,
    "geometry":      0.85,
    "color_restore": 0.95,
    "done":          1.00,
}


# ── Lambda entry point ────────────────────────────────────────────────────────

def handler(event: dict, context: Any) -> None:
    """Process DynamoDB Streams records from sa-jobs and broadcast to WebSocket clients."""
    records = event.get("Records", [])
    logger.info("Broadcaster: %d DDB stream record(s)", len(records))

    for record in records:
        if record.get("eventName") not in ("INSERT", "MODIFY"):
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            continue

        _process_record(new_image)


# ── Record processing ─────────────────────────────────────────────────────────

def _process_record(new_image: dict) -> None:
    """Build and broadcast a step_update message from a DDB stream NewImage."""
    job_id       = _s(new_image.get("job_id"))
    status       = _s(new_image.get("status"))
    current_step = _s(new_image.get("current_step"))
    step_detail  = _s(new_image.get("step_detail"))
    photo_count  = int(_n(new_image.get("photo_count")) or 0)

    if not job_id:
        return

    # Compute progress
    if status == "complete":
        progress = 1.0
    elif status == "failed":
        progress = -1.0  # sentinel — frontend shows error state
    else:
        progress = _STEP_PROGRESS.get(current_step, 0.0)

    message = {
        "type":        "step_update",
        "jobId":       job_id,
        "status":      status,
        "step":        current_step,
        "detail":      step_detail,
        "progress":    progress,
        "photoCount":  photo_count,
    }

    logger.info(
        "Broadcasting job=%s status=%s step=%s progress=%.2f",
        job_id, status, current_step, progress,
    )
    _broadcast(job_id, message)


# ── WebSocket broadcast ───────────────────────────────────────────────────────

def _broadcast(job_id: str, message: dict) -> None:
    """Push message to every WebSocket connection subscribed to job_id."""
    if not WS_ENDPOINT:
        logger.warning("WS_ENDPOINT not configured — skipping broadcast for job %s", job_id)
        return

    # Find all connections for this job
    try:
        resp = ws_table.query(
            IndexName="job-index",
            KeyConditionExpression="job_id = :jid",
            ExpressionAttributeValues={":jid": job_id},
        )
        connections = resp.get("Items", [])
    except Exception as exc:
        logger.error("Could not query ws-connections for job %s: %s", job_id, exc)
        return

    if not connections:
        logger.debug("No WebSocket connections for job %s", job_id)
        return

    apigw = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=WS_ENDPOINT,
        region_name=REGION,
    )
    payload = json.dumps(message).encode()
    stale: list[str] = []

    for conn in connections:
        cid = conn["connection_id"]
        try:
            apigw.post_to_connection(ConnectionId=cid, Data=payload)
        except apigw.exceptions.GoneException:
            # Client disconnected without a clean $disconnect
            stale.append(cid)
        except Exception as exc:
            logger.warning("Failed to push to connection %s: %s", cid, exc)

    logger.info(
        "Broadcast to %d connection(s) for job %s (%d stale)",
        len(connections) - len(stale), job_id, len(stale),
    )

    # Purge stale connections
    for cid in stale:
        try:
            ws_table.delete_item(Key={"connection_id": cid})
        except Exception:
            pass


# ── DynamoDB attribute helpers ────────────────────────────────────────────────

def _s(attr: dict | None) -> str:
    """Extract a String value from a DDB stream attribute."""
    return (attr or {}).get("S", "")


def _n(attr: dict | None) -> str:
    """Extract a Number value (as string) from a DDB stream attribute."""
    return (attr or {}).get("N", "0")
