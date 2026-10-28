"""Frozen crop integrity tests using only synthetic local images."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
import fixtures  # noqa: E402


def test_manifest_and_all_stage_hashes_validate() -> None:
    assert fixtures.load_manifest()["fixture_set"] == "synthetic-v1"
    assert fixtures.validate() == 6
    assert fixtures.validate(release_only=True) == 2


def test_changed_frozen_crop_is_rejected() -> None:
    row = fixtures.load_manifest()["cases"][0]
    path = fixtures.ROOT / row["orientation_input"]
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Hash mismatch"):
        fixtures.validate()
