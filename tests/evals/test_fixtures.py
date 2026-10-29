"""Frozen crop integrity tests using only synthetic local images."""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

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


def test_orientation_only_fixture_is_valid_and_excluded_from_glare() -> None:
    import runner

    manifest = fixtures.load_manifest()
    case_id = "synthetic-object-rot180"
    path = fixtures.ROOT / "test-cropped-images/orientation" / f"{case_id}.jpg"
    Image.new("RGB", (40, 30), "blue").save(path)
    row = {
        "case_id": case_id,
        "tags": ["orientation", "synthetic-rotation"],
        "expected_rotation_degrees": 180,
        "expected_flip_horizontal": False,
        "ambiguous": False,
        "distribution": "local-only",
        "orientation_input": str(path.relative_to(fixtures.ROOT)),
        "orientation_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    manifest["cases"].append(row)
    fixtures.MANIFEST.write_text(json.dumps(manifest))

    assert fixtures.validate() == 7
    assert fixtures.validate(release_only=True) == 2
    assert len(runner.selected_cases("orientation", [case_id])[1]) == 1
    assert len(runner.selected_cases("glare", [])[1]) == 3
    with pytest.raises(ValueError, match="No matching fixtures"):
        runner.selected_cases("glare", [case_id])
