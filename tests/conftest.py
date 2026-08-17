"""Root conftest for all API and handler tests.

Sets all env vars BEFORE any api/ or handlers/ module is imported, then
provides the shared autouse `aws_services` fixture that provisions fresh
moto resources for each test.

Both api/common.py and handlers/common.py read env vars at module-import
time, so env vars must be set here — at the earliest possible collection
point — rather than inside fixtures.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# ── sys.path ─────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
for _p in [
    str(_ROOT / "packages" / "pipeline"),  # src
    str(_ROOT / "services"),               # handlers
    str(_ROOT / "services" / "api"),       # api modules (flat)
    str(_ROOT / "tests" / "api"),          # helpers.py
    str(_ROOT / "tests" / "handlers"),     # handler_helpers.py
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Env vars ─────────────────────────────────────────────────────────────────

os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-west-2",
        "AWS_DEPLOY_REGION": "us-west-2",
        # api/common.py
        "SESSIONS_TABLE": "sa-sessions-test",
        "JOBS_TABLE": "sa-jobs-test",
        "WS_CONNECTIONS_TABLE": "sa-ws-connections-test",
        "USER_SETTINGS_TABLE": "sa-user-settings-test",
        "S3_BUCKET": "sa-data-test",
        "SES_SENDER": "noreply@test.com",
        "ADMIN_EMAILS": "admin@example.com,chintan@reachto.me",
        "STATE_MACHINE_ARN": (
            "arn:aws:states:us-west-2:123456789012:stateMachine:sa-pipeline-test"
        ),
        # handlers/common.py
        "SECRET_ARN": (
            "arn:aws:secretsmanager:us-west-2:123456789012:secret:sa-keys-test"
        ),
    }
)

_REGION = "us-west-2"

# ── Shared autouse fixture ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def aws_services():
    """Fresh moto environment for every test — provisions all required resources."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=_REGION)

        ddb.create_table(
            TableName="sa-sessions-test",
            KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "email", "AttributeType": "S"},
                {"AttributeName": "session_token", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "token-index",
                    "KeySchema": [
                        {"AttributeName": "session_token", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        ddb.create_table(
            TableName="sa-jobs-test",
            KeySchema=[
                {"AttributeName": "user_hash", "KeyType": "HASH"},
                {"AttributeName": "job_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_hash", "AttributeType": "S"},
                {"AttributeName": "job_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        ddb.create_table(
            TableName="sa-user-settings-test",
            KeySchema=[{"AttributeName": "user_hash", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "user_hash", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        s3 = boto3.client("s3", region_name=_REGION)
        s3.create_bucket(
            Bucket="sa-data-test",
            CreateBucketConfiguration={"LocationConstraint": _REGION},
        )

        ses = boto3.client("ses", region_name=_REGION)
        ses.verify_email_address(EmailAddress="noreply@test.com")

        sfn = boto3.client("stepfunctions", region_name=_REGION)
        sfn.create_state_machine(
            name="sa-pipeline-test",
            definition=json.dumps(
                {
                    "Comment": "test stub",
                    "StartAt": "Done",
                    "States": {"Done": {"Type": "Succeed"}},
                }
            ),
            roleArn="arn:aws:iam::123456789012:role/test-role",
        )

        sm = boto3.client("secretsmanager", region_name=_REGION)
        sm.create_secret(
            Name="sa-keys-test",
            SecretString=json.dumps(
                {
                    "ANTHROPIC_API_KEY": "sk-ant-test",
                    "OPENAI_API_KEY": "sk-openai-test",
                }
            ),
        )

        yield
