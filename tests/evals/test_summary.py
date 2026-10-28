"""Dated cost and full-summary tests with no live provider calls."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
from summary import estimate_cost, summarize  # noqa: E402
from records import RunStore  # noqa: E402


def test_dated_cost_estimates_and_missing_usage() -> None:
    haiku = estimate_cost("claude-haiku-5-5", {"input_tokens": 1000, "output_tokens": 100})
    assert haiku["status"] == "estimated"
    assert haiku["usd_estimate"] == 0.00015
    image = estimate_cost("gpt-image-2.5-flare", {
        "input_tokens_details": {"image_tokens": 1000, "text_tokens": 100},
        "output_tokens_details": {"image_tokens": 2000},
    })
    assert image["usd_estimate"] == 0.0685
    assert estimate_cost("gpt-image-1.5", None)["status"] == "missing_usage"
    assert estimate_cost("unknown", {"input_tokens": 1})["status"] == "unpriced_model"


def test_summary_keeps_failed_attempt_and_local_only_context(tmp_path: Path) -> None:
    case = "test-images-2-img_1250-01"
    run = RunStore.create(tmp_path, run_id="summary-test", task="orientation",
                          fixture_set="approved-2026-10-27-v1", fixture_hashes={case: "a" * 64},
                          baseline_config={"requested_model": "claude-haiku-4-5-20251001"},
                          candidate_config={"requested_model": "claude-haiku-5-5"},
                          pipeline_revision="a" * 40, harness_revision="b" * 40,
                          sdk_versions={}, review_context={"provider_account": "test",
                          "retention_url": "https://example.org", "local_only_cases": [case],
                          "thresholds": {"min_upright_accuracy": 0.8}})
    job = f"{case}__candidate__1"
    row = {"status": "failed", "case_id": case, "arm": "candidate", "repeat": 1,
           "requested_model": "claude-haiku-5-5", "error_class": "truncated",
           "latency_ms": 50, "usage": None}
    run.save_attempt(job, 1, row)
    run.save_result(job, row)
    summary = summarize(run)
    assert summary["errors"] == {"truncated": 1}
    assert summary["local_only_cases"] == [case]
    assert summary["usage_and_cost"]["missing_cost_count"] == 1
    assert summary["coverage"]["failed_jobs"] == 1
