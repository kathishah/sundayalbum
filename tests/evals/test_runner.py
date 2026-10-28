"""Offline runner guards and exact-fixture execution tests."""

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
import runner  # noqa: E402
from providers import read_eval_keys  # noqa: E402
from records import RunStore  # noqa: E402


def arguments(tmp_path: Path, **changes) -> argparse.Namespace:
    """Build one-case orientation arguments with conservative caps."""
    values = dict(
        task="orientation",
        baseline=None,
        candidate=runner.ROOT / "evals/model-upgrade/configs/haiku-5-5.json",
        cases=["test-images-img_two_pics_vertical_horizontal_normal-01"],
        repeats=1,
        max_retries=0,
        output_dir=tmp_path / "runs",
        run_id="offline-test",
        resume=False,
        retry_failed=False,
        execute=False,
        max_attempts=None,
        max_estimated_usd=None,
        retention_url=None,
        scene_descriptions_from=None,
        thresholds={},
    )
    values.update(changes)
    return argparse.Namespace(**values)


def test_dry_run_never_constructs_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        runner, "make_client", lambda *args: pytest.fail("client constructed in dry run")
    )
    assert runner.run(arguments(tmp_path)) is None
    assert not (tmp_path / "runs").exists()


def test_missing_key_fails_before_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        runner, "make_client", lambda *args: pytest.fail("client constructed without key")
    )
    monkeypatch.setattr(
        runner, "read_eval_keys", lambda *args: (_ for _ in ()).throw(ValueError("missing key"))
    )
    with pytest.raises(ValueError, match="missing key"):
        runner.run(
            arguments(
                tmp_path,
                execute=True,
                max_attempts=2,
                max_estimated_usd=0.04,
                retention_url="https://example.org",
            )
        )
    assert not (tmp_path / "runs").exists()


def test_budget_guard_precedes_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        runner, "read_eval_keys", lambda *args: pytest.fail("credentials read before budget guard")
    )
    with pytest.raises(ValueError, match="max-estimated-usd"):
        runner.run(
            arguments(
                tmp_path,
                execute=True,
                max_attempts=1,
                max_estimated_usd=0.01,
                retention_url="https://example.org",
            )
        )


def test_strict_keys_ignore_environment(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({"AWS": "unrelated"}))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sentinel-production-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://sentinel.invalid")
    with pytest.raises(ValueError, match="Missing ANTHROPIC_API_KEY"):
        read_eval_keys(path, {"anthropic"})


def test_sparse_overlay_inherits_prompt_and_parameters(tmp_path: Path) -> None:
    config = tmp_path / "candidate.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "model only",
                "steps": {"ai_orientation": {"model": "claude-haiku-5-5"}},
            }
        )
    )
    manifest, cases = runner.selected_cases(
        "orientation", ["test-images-img_two_pics_vertical_horizontal_normal-01"]
    )
    baseline, candidate = runner.effective_config(
        "orientation", runner.load_override(config), cases
    )
    assert candidate["prompts"] == baseline["prompts"]
    assert candidate["parameters"] == baseline["parameters"]
    assert candidate["sources"]["model"] == "override"
    assert candidate["sources"]["prompt"] == "production"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "bad",
                "steps": {"ai_orientation": {"provider": "openai"}},
            }
        )
    )
    with pytest.raises(ValueError, match="Unsupported orientation provider"):
        runner.effective_config("orientation", runner.load_override(config), cases)


def test_real_haiku_candidate_captures_json_schema_and_thinking_override() -> None:
    config = Path(__file__).resolve().parents[2] / "evals/model-upgrade/configs/haiku-5-5.json"
    _, cases = runner.selected_cases(
        "orientation", ["test-images-img_two_pics_vertical_horizontal_normal-01"]
    )
    _, candidate = runner.effective_config("orientation", runner.load_override(config), cases)
    assert candidate["parameters"]["thinking"] == {"type": "disabled"}
    assert candidate["parameters"]["output_config"]["format"]["type"] == "json_schema"


def test_glare_arms_can_overlay_production_independently(tmp_path: Path) -> None:
    configs = Path(__file__).resolve().parents[2] / "evals/model-upgrade/configs"
    case_id = "test-images-img_two_pics_vertical_horizontal_normal-01"
    _, cases = runner.selected_cases("glare", [case_id])
    baseline, candidate = runner.effective_config(
        "glare",
        runner.load_override(configs / "image-2.5-sunburst.json"),
        cases,
        runner.load_override(configs / "image-2.5-flare.json"),
    )
    assert baseline["requested_model"] == "gpt-image-2.5-flare"
    assert candidate["requested_model"] == "gpt-image-2.5-sunburst"
    assert baseline["prompts"] == candidate["prompts"]
    assert baseline["parameters_by_case"][case_id] == candidate["parameters_by_case"][case_id]
    assert baseline["parameters_by_case"][case_id]["input_fidelity"] is None
    assert baseline["sources"]["model"] == "override"
    assert candidate["sources"]["model"] == "override"
    assert (
        runner.run(
            arguments(
                tmp_path,
                task="glare",
                baseline=configs / "image-2.5-flare.json",
                candidate=configs / "image-2.5-sunburst.json",
                cases=[case_id],
            )
        )
        is None
    )


def test_mocked_execution_uses_exact_crop_and_honors_cap(tmp_path: Path, monkeypatch) -> None:
    inputs = []
    monkeypatch.setattr(runner, "read_eval_keys", lambda *args: {"anthropic": "test-key"})
    monkeypatch.setattr(runner, "make_client", lambda *args: object())
    monkeypatch.setattr(runner, "preflight", lambda *args: None)
    monkeypatch.setattr(runner, "revision", lambda: "a" * 40)

    def fake_call(client, *, image_bytes, model, prompt, parameters):
        inputs.append(image_bytes)
        return {
            "status": "success",
            "parsed_output": {
                "rotation_degrees": 270,
                "flip_horizontal": False,
                "confidence": "high",
                "scene_description": "Person",
            },
            "raw_response": {"model": model},
            "usage": {"input_tokens": 1},
            "resolved_model": model,
            "latency_ms": 1,
            "retryable": False,
        }

    monkeypatch.setattr(runner, "call_orientation", fake_call)
    args = arguments(
        tmp_path,
        execute=True,
        max_attempts=1,
        max_estimated_usd=0.04,
        retention_url="https://example.org",
    )
    folder = runner.run(args)
    assert folder is not None
    expected = (
        runner.ROOT
        / "test-cropped-images/orientation"
        / "test-images-img_two_pics_vertical_horizontal_normal-01.jpg"
    ).read_bytes()
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
    assert (folder / "review.html").exists()
    RunStore(folder).write_decision(
        reviewer="Offline reviewer",
        status="inconclusive",
        rationale="Mocked outputs only",
        limitations="No live calls",
    )
    assert (folder / "decision.json").exists()


def test_failures_stay_recorded_until_retry_failed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "read_eval_keys", lambda *args: {"anthropic": "test-key"})
    monkeypatch.setattr(runner, "make_client", lambda *args: object())
    monkeypatch.setattr(runner, "preflight", lambda *args: None)
    monkeypatch.setattr(runner, "revision", lambda: "a" * 40)
    calls = []

    def fake_call(client, *, image_bytes, model, prompt, parameters):
        calls.append(model)
        if len(calls) == 1:
            return {
                "status": "failed",
                "error_class": "provider_error",
                "retryable": False,
                "latency_ms": 1,
                "usage": None,
            }
        return {
            "status": "success",
            "parsed_output": {
                "rotation_degrees": 270,
                "flip_horizontal": False,
                "confidence": "high",
                "scene_description": "Person",
            },
            "raw_response": {},
            "usage": None,
            "resolved_model": model,
            "latency_ms": 1,
            "retryable": False,
        }

    monkeypatch.setattr(runner, "call_orientation", fake_call)
    args = arguments(
        tmp_path,
        execute=True,
        max_attempts=3,
        max_estimated_usd=0.04,
        retention_url="https://example.org",
    )
    folder = runner.run(args)
    assert len(calls) == 2
    args.resume = True
    runner.run(args)
    assert len(calls) == 2
    args.retry_failed = True
    runner.run(args)
    assert len(calls) == 3
    failed_job = f"{args.cases[0]}__baseline__1"
    assert len(RunStore(folder).attempts(failed_job)) == 2
