"""Synthetic fixture corpus and network/client blockade for all eval unit tests."""

import hashlib
import json
import socket
import sys
from pathlib import Path

import pytest
from PIL import Image

EVAL_DIR = Path(__file__).resolve().parents[2] / "evals/model-upgrade"
sys.path.insert(0, str(EVAL_DIR))


@pytest.fixture(autouse=True)
def offline_eval_environment(tmp_path: Path, monkeypatch) -> None:
    """Never allow eval unit tests to reach a provider or require real crops."""
    import anthropic
    import evaluation
    import fixtures
    import openai
    import runner

    def blocked(*args, **kwargs):
        raise AssertionError("Network or real SDK client construction in offline eval test")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(anthropic, "Anthropic", blocked)
    monkeypatch.setattr(openai, "OpenAI", blocked)

    root = tmp_path / "synthetic-project"
    cases = []
    specs = (
        ("test-images-img_two_pics_vertical_horizontal_normal-01", 270, False, "v0.0.4-evaldata"),
        ("test-images-2-img_1250-01", 0, False, "local-only"),
        ("test-images-2-img_1250-02", None, True, "local-only"),
    )
    for index, (case_id, expected, ambiguous, distribution) in enumerate(specs):
        row = {
            "case_id": case_id,
            "expected_rotation_degrees": expected,
            "expected_flip_horizontal": False,
            "ambiguous": ambiguous,
            "distribution": distribution,
            "scene_description": f"Synthetic scene {index}",
        }
        for task in ("orientation", "glare"):
            path = root / "test-cropped-images" / task / f"{case_id}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40 + index, 30 + index), (index * 30, 30, 60)).save(path)
            row[f"{task}_input"] = str(path.relative_to(root))
            row[f"{task}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        cases.append(row)
    manifest = root / "evals/model-upgrade/fixtures.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"schema_version": 1, "fixture_set": "synthetic-v1", "cases": cases})
    )
    config_dir = root / "evals/model-upgrade/configs"
    config_dir.mkdir(parents=True)
    (config_dir / "haiku-5-5.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "candidate",
                "steps": {"ai_orientation": {"model": "claude-haiku-5-5"}},
            }
        )
    )
    monkeypatch.setattr(fixtures, "ROOT", root)
    monkeypatch.setattr(fixtures, "MANIFEST", manifest)
    monkeypatch.setattr(evaluation, "ROOT", root)
    monkeypatch.setattr(runner, "ROOT", root)
