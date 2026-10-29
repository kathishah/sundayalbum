"""Offline run-record contract tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
from records import RunStore  # noqa: E402


def create_store(tmp_path: Path) -> RunStore:
    """Create one fully versioned run for round-trip tests."""
    return RunStore.create(
        tmp_path,
        run_id="test-run",
        task="orientation",
        fixture_set="set-v1",
        fixture_hashes={"case-1": "a" * 64},
        baseline_config={
            "model": "baseline",
            "prompt": "Full prompt",
            "parameters": {"max_tokens": 512},
        },
        candidate_config={
            "model": "candidate",
            "prompt": "Full prompt",
            "parameters": {"max_tokens": 512},
        },
        pipeline_revision="a" * 40,
        harness_revision="b" * 40,
        sdk_versions={"anthropic": "1.0"},
        review_context={
            "provider_key_suffix": "12345678",
            "retention_url": "https://example.org/terms",
        },
    )


def test_success_and_failure_round_trip(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    success = {
        "status": "success",
        "input_sha256": "a" * 64,
        "latency_ms": 43,
        "usage": {"input_tokens": 123},
        "raw_response": {"model": "candidate", "text": "{}"},
        "parsed_output": {"rotation_degrees": 0},
    }
    failure = {
        "status": "failed",
        "error_class": "truncated",
        "error": "Provider stopped at max_tokens",
        "latency_ms": 41,
    }
    store.save_attempt("case-1__candidate__1", 1, success)
    store.save_result("case-1__candidate__1", success)
    store.save_attempt("case-1__baseline__1", 1, failure)
    store.save_result("case-1__baseline__1", failure)
    assert store.result("case-1__candidate__1")["parsed_output"]["rotation_degrees"] == 0
    assert store.result("case-1__baseline__1")["error_class"] == "truncated"
    assert len(store.all_results()) == 2
    assert len(store.attempts("case-1__candidate__1")) == 1
    assert store.manifest()["schema_version"] == 1


def test_resume_rejects_config_or_fixture_changes(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    manifest = store.manifest()
    matching = dict(
        root=tmp_path,
        run_id="test-run",
        task="orientation",
        fixture_set="set-v1",
        fixture_hashes={"case-1": "a" * 64},
        baseline_config=manifest["baseline_config"],
        candidate_config=manifest["candidate_config"],
    )
    assert RunStore.resume(**matching).directory == store.directory
    with pytest.raises(ValueError, match="candidate_config_hash"):
        RunStore.resume(**{**matching, "candidate_config": {"model": "changed"}})
    with pytest.raises(ValueError, match="fixture_hashes"):
        RunStore.resume(**{**matching, "fixture_hashes": {"case-1": "b" * 64}})
    with pytest.raises(ValueError, match="review_context.provider_key_suffix"):
        RunStore.resume(**{**matching, "review_context": {"provider_key_suffix": "different"}})


def test_redacts_credentials_and_signed_urls(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    store.save_attempt(
        "case-1__candidate__1",
        1,
        {
            "status": "failed",
            "api_key": "sk-secret",
            "error": "sk-secret",
            "raw_response": {"url": "https://example.org/a?X-Amz-Signature=abc"},
        },
    )
    record = store.attempts("case-1__candidate__1")[0]
    assert record["api_key"] == "[REDACTED]"
    assert record["error"] == "[REDACTED]"
    assert record["raw_response"]["url"] == "[REDACTED]"


def test_decision_requires_reviewer_and_rationale(tmp_path: Path) -> None:
    store = create_store(tmp_path)
    with pytest.raises(ValueError):
        store.write_decision(reviewer="", status="accepted", rationale="yes", limitations="")
    store.write_decision(
        reviewer="Owner",
        status="inconclusive",
        rationale="More samples needed",
        limitations="Small corpus",
    )
    assert (store.directory / "decision.json").exists()
