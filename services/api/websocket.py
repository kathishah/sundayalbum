"""Sunday Album WebSocket Lambda handler (Phase 3).

Routes (API Gateway WebSocket):
    $connect     — store connection_id + job_id
    $disconnect  — remove connection_id
    $default     — handle subscribe / ping messages
    broadcast    — internal: push progress update to subscribers (invoked by DDB Streams trigger)

Phase 1 note: the WebSocket API Gateway is configured in Phase 3.
This handler is deployed now so the Lambda ARN exists for the CDK stack reference.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

from common import (
    REGION,
    internal,
    ok,
    parse_body,
    ws_table,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

WS_ENDPOINT = os.environ.get("WS_ENDPOINT", "")  # set in Phase 3


def handler(event: dict, context: Any) -> dict:
    """Route WebSocket events by requestContext.routeKey."""
    ctx = event.get("requestContext") or {}
    route = ctx.get("routeKey", "$default")
    connection_id = ctx.get("connectionId", "")
    logger.info("WebSocket route: %s  connection: %s", route, connection_id)

    try:
        if route == "$connect":
            return _handle_connect(event, connection_id)
        if route == "$disconnect":
            return _handle_disconnect(connection_id)
        if route == "broadcast":
            # Internal invocation from DynamoDB Streams processor
            return _handle_broadcast(event)
        return _handle_message(event, connection_id)
    except Exception as exc:
        logger.exception("WebSocket handler error: %s", exc)
        return {"statusCode": 500}


def _handle_connect(event: dict, connection_id: str) -> dict:
    """Store connection in DynamoDB on $connect."""
    params = event.get("queryStringParameters") or {}
    job_id = params.get("jobId", "")
    user_hash = params.get("userHash", "")

    if connection_id and job_id:
        try:
            ws_table.put_item(
                Item={
                    "connection_id": connection_id,
                    "job_id": job_id,
                    "user_hash": user_hash,
                }
            )
            logger.info("WebSocket connected: %s → job %s", connection_id, job_id)
        except Exception as exc:
            logger.warning("Could not store WebSocket connection: %s", exc)

    return {"statusCode": 200}


def _handle_disconnect(connection_id: str) -> dict:
    """Remove connection from DynamoDB on $disconnect."""
    try:
        ws_table.delete_item(Key={"connection_id": connection_id})
        logger.info("WebSocket disconnected: %s", connection_id)
    except Exception as exc:
        logger.warning("Could not remove WebSocket connection: %s", exc)

    return {"statusCode": 200}


def _handle_message(event: dict, connection_id: str) -> dict:
    """Handle $default messages (subscribe, ping)."""
    body = parse_body(event)
    action = body.get("action", "")

    if action == "ping":
        _send_to_connection(connection_id, {"type": "pong"})
        return {"statusCode": 200}

    logger.info("Unhandled WebSocket message: %s", action)
    return {"statusCode": 200}


def _handle_broadcast(event: dict) -> dict:
    """Push a progress update to all connections subscribed to a job.

    Expected event shape (from DynamoDB Streams processor or direct invoke):
    {
        "job_id": "...",
        "message": { "type": "step_update", ... }
    }
    """
    job_id = event.get("job_id", "")
    message = event.get("message", {})

    if not job_id or not message:
        return {"statusCode": 400}

    # Query connections for this job
    try:
        resp = ws_table.query(
            IndexName="job-index",
            KeyConditionExpression="job_id = :jid",
            ExpressionAttributeValues={":jid": job_id},
        )
        connections = resp.get("Items", [])
    except Exception as exc:
        logger.error("Could not query WebSocket connections: %s", exc)
        return {"statusCode": 500}

    if not connections:
        return {"statusCode": 200}

    if not WS_ENDPOINT:
        logger.warning("WS_ENDPOINT not configured — cannot broadcast")
        return {"statusCode": 200}

    apigw_mgmt = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=WS_ENDPOINT,
        region_name=REGION,
    )
    payload = json.dumps(message).encode()
    stale = []

    for conn in connections:
        cid = conn["connection_id"]
        try:
            apigw_mgmt.post_to_connection(ConnectionId=cid, Data=payload)
        except apigw_mgmt.exceptions.GoneException:
            stale.append(cid)
        except Exception as exc:
            logger.warning("Failed to send to connection %s: %s", cid, exc)

    # Clean up stale connections
    for cid in stale:
        try:
            ws_table.delete_item(Key={"connection_id": cid})
        except Exception:
            pass

    return {"statusCode": 200}


def _send_to_connection(connection_id: str, message: dict) -> None:
    """Send a message to a specific WebSocket connection."""
    if not WS_ENDPOINT:
        return
    try:
        apigw_mgmt = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=WS_ENDPOINT,
            region_name=REGION,
        )
        apigw_mgmt.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode(),
        )
    except Exception as exc:
        logger.warning("Failed to send message to %s: %s", connection_id, exc)
