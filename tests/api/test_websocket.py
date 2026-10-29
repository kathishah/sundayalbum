"""Authentication and ownership checks for WebSocket subscriptions."""

from __future__ import annotations

import hashlib

import boto3
import websocket as websocket_module
from helpers import REGION, insert_job, make_session


def _hash(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()


def _make_connections_table() -> None:
    boto3.resource("dynamodb", region_name=REGION).create_table(
        TableName="sa-ws-connections-test",
        KeySchema=[{"AttributeName": "connection_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "connection_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


def test_connect_rejects_missing_or_invalid_token() -> None:
    event = {"queryStringParameters": {"jobId": "job-1"}}
    assert websocket_module._handle_connect(event, "connection-1")["statusCode"] == 401

    event["queryStringParameters"]["token"] = "invalid"
    assert websocket_module._handle_connect(event, "connection-1")["statusCode"] == 401


def test_connect_rejects_jobs_owned_by_another_user() -> None:
    _make_connections_table()
    email = "ws-owner@example.com"
    user_hash = _hash(email)
    token = make_session(email, user_hash)
    insert_job("different-owner", "job-1")

    event = {"queryStringParameters": {"jobId": "job-1", "token": token}}
    assert websocket_module._handle_connect(event, "connection-1")["statusCode"] == 403


def test_connect_stores_authenticated_user_for_owned_job() -> None:
    _make_connections_table()
    email = "ws-valid@example.com"
    user_hash = _hash(email)
    token = make_session(email, user_hash)
    insert_job(user_hash, "job-1")

    event = {"queryStringParameters": {"jobId": "job-1", "token": token}}
    response = websocket_module._handle_connect(event, "connection-1")

    assert response["statusCode"] == 200
    item = boto3.resource("dynamodb", region_name=REGION).Table(
        "sa-ws-connections-test"
    ).get_item(Key={"connection_id": "connection-1"})["Item"]
    assert item["user_hash"] == user_hash
