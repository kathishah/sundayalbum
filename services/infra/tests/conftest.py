"""Shared fixtures for infra CDK tests.

Run from the infra/ directory using the infra venv:
    cd infra && .venv/bin/pytest tests/ -v
"""
from __future__ import annotations

import json
import sys
import os

import pytest

# Ensure the infra package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _flatten_definition(parts: list) -> dict:
    """Collapse Fn::Join parts into a parseable JSON string.

    Non-string parts (Ref, Fn::GetAtt) appear inside JSON string values
    (e.g. ARN fragments), so they can be replaced with a bare token.
    """
    raw = ""
    for p in parts:
        raw += p if isinstance(p, str) else "PLACEHOLDER"
    return json.loads(raw)


@pytest.fixture(scope="session")
def sfn_definition():
    """Return the parsed state machine definition dict from a fresh CDK synth."""
    import aws_cdk as cdk
    import aws_cdk.assertions as assertions

    os.environ.setdefault("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")

    from infra.sundayalbum_stack import SundayAlbumStack

    app = cdk.App()
    stack = SundayAlbumStack(
        app,
        "TestStack",
        env=cdk.Environment(account="123456789012", region="us-west-2"),
    )
    tmpl = assertions.Template.from_stack(stack)
    sfn_resources = tmpl.find_resources("AWS::StepFunctions::StateMachine")
    key = next(iter(sfn_resources))
    parts = sfn_resources[key]["Properties"]["DefinitionString"]["Fn::Join"][1]
    return _flatten_definition(parts)


@pytest.fixture(scope="session")
def top_level_states(sfn_definition):
    """Top-level state machine states (pre-split chain + Map)."""
    return sfn_definition["States"]


@pytest.fixture(scope="session")
def per_photo_states(sfn_definition):
    """States inside the ProcessPhotos Map item processor (per-photo chain)."""
    proc = sfn_definition["States"]["ProcessPhotos"]
    return proc.get("ItemProcessor", proc.get("Iterator", {}))["States"]
