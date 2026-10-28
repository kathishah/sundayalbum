"""Offline runner guards and exact-fixture execution tests."""

import argparse
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
import runner  # noqa: E402
from providers import read_eval_keys  # noqa: E402


def arguments(tmp_path: Path, **changes) -> argparse.Namespace:
    """Build one-case orientation arguments with conservative caps."""
    values = dict(task="orientation", candidate=runner.ROOT / "evals/model-upgrade/configs/haiku-5-5.json",
                  cases=["test-images-img_two_pics_vertical_horizontal_normal-01"], repeats=1,
                  max_retries=0, output_dir=tmp_path, run_id="offline-test", resume=False,
                  retry_failed=False, execute=False, max_attempts=None, max_estimated_usd=None,
                  provider_account=None, retention_url=None, thresholds={})
    values.update(changes)
    return argparse.Namespace(**values)


def test_dry_run_never_constructs_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "make_client", lambda *args: pytest.fail("client constructed in dry run"))
    assert runner.run(arguments(tmp_path)) is None
    assert list(tmp_path.iterdir()) == []


def test_missing_key_fails_before_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "make_client", lambda *args: pytest.fail("client constructed without key"))
    monkeypatch.setattr(runner, "read_eval_keys", lambda *args: (_ for _ in ()).throw(ValueError("missing key")))
    with pytest.raises(ValueError, match="missing key"):
        runner.run(arguments(tmp_path, execute=True, max_attempts=2, max_estimated_usd=0.04,
                             provider_account="test", retention_url="https://example.org"))
    assert list(tmp_path.iterdir()) == []


def test_budget_guard_precedes_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "read_eval_keys", lambda *args: pytest.fail("credentials read before budget guard"))
    with pytest.raises(ValueError, match="max-estimated-usd"):
        runner.run(arguments(tmp_path, execute=True, max_attempts=1, max_estimated_usd=0.01,
                             provider_account="test", retention_url="https://example.org"))


def test_strict_keys_ignore_environment(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({"AWS": "unrelated"}))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sentinel-production-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://sentinel.invalid")
    with pytest.raises(ValueError, match="Missing ANTHROPIC_API_KEY"):
        read_eval_keys(path, {"anthropic"})


def test_mocked_execution_uses_exact_crop_and_honors_cap(tmp_path: Path, monkeypatch) -> None:
    inputs = []
    monkeypatch.setattr(runner, "read_eval_keys", lambda *args: {"anthropic": "test-key"})
    monkeypatch.setattr(runner, "make_client", lambda *args: object())
    monkeypatch.setattr(runner, "preflight", lambda *args: None)
    monkeypatch.setattr(runner, "revision", lambda: "a" * 40)

    def fake_call(client, *, image_bytes, model, prompt, parameters):
        inputs.append(image_bytes)
        return {"status": "success", "parsed_output": {"rotation_degrees": 270,
                "flip_horizontal": False, "confidence": "high", "scene_description": "Person"},
                "raw_response": {"model": model}, "usage": {"input_tokens": 1},
                "resolved_model": model, "latency_ms": 1, "retryable": False}

    monkeypatch.setattr(runner, "call_orientation", fake_call)
    args = arguments(tmp_path, execute=True, max_attempts=1, max_estimated_usd=0.04,
                     provider_account="test", retention_url="https://example.org")
    folder = runner.run(args)
    assert folder is not None
    expected = (runner.ROOT / "test-cropped-images/orientation/test-images-img_two_pics_vertical_horizontal_normal-01.jpg").read_bytes()
    assert inputs == [expected]
    results = [json.loads(path.read_text()) for path in (folder / "results").glob("*.json")]
    assert {result["status"] for result in results} == {"success", "not_run"}
    assert json.loads((folder / "summary.json").read_text())["attempts_used"] == 1
    args.resume = True
    args.max_attempts = 2
    runner.run(args)
    results = [json.loads(path.read_text()) for path in (folder / "results").glob("*.json")]
    assert all(result["status"] == "success" for result in results)
    assert len(inputs) == 2
