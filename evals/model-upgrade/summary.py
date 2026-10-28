"""Build complete machine-readable summaries from persisted run artifacts."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from evaluation import glare_metrics, orientation_metrics
from records import RunStore

PRICING = json.loads(Path(__file__).with_name("pricing-2026-10-27.json").read_text())


def estimate_cost(model: str, usage: dict | None) -> dict:
    """Estimate USD from dated public token rates; mark missing inputs."""
    if usage is None:
        return {"status": "missing_usage", "usd_estimate": None}
    rates = PRICING["models"].get(model)
    if rates is None:
        return {"status": "unpriced_model", "usd_estimate": None}
    try:
        if "input" in rates:
            dollars = (usage["input_tokens"] * rates["input"] +
                       usage["output_tokens"] * rates["output"]) / 1_000_000
        else:
            details = usage["input_tokens_details"]
            output_details = usage.get("output_tokens_details") or {}
            image_output = output_details.get("image_tokens", usage.get("output_tokens"))
            if image_output is None:
                raise KeyError("output_tokens")
            dollars = (details["image_tokens"] * rates["image_input"] +
                       details["text_tokens"] * rates["text_input"] +
                       image_output * rates["image_output"]) / 1_000_000
    except (KeyError, TypeError):
        return {"status": "incomplete_usage", "usd_estimate": None}
    return {"status": "estimated", "usd_estimate": round(dollars, 6),
            "pricing_date": PRICING["as_of"], "source": rates["source"]}


def summarize(store: RunStore) -> dict:
    """Aggregate coverage, attempts, errors, latency, usage, cost, and metrics."""
    run = store.manifest()
    results = store.all_results()
    attempts = []
    for result in results:
        attempts.extend(store.attempts(result["job_id"]))
    costs = []
    for attempt in attempts:
        costs.append({"job_id": attempt["job_id"], "attempt": attempt["attempt"],
                      "requested_model": attempt.get("requested_model"),
                      "usage": attempt.get("usage"),
                      "cost": estimate_cost(attempt.get("requested_model", ""), attempt.get("usage"))})
    latencies = [row["latency_ms"] for row in attempts if isinstance(row.get("latency_ms"), (int, float))]
    estimated = [row["cost"]["usd_estimate"] for row in costs if row["cost"]["status"] == "estimated"]
    metrics = orientation_metrics(store) if run["task"] == "orientation" else glare_metrics(store)
    return {
        "task": run["task"], "fixture_set": run["fixture_set"],
        "fixture_hashes": run["fixture_hashes"],
        "baseline_config": run["baseline_config"], "candidate_config": run["candidate_config"],
        "configuration_hashes": {"baseline": run["baseline_config_hash"],
                                 "candidate": run["candidate_config_hash"]},
        "provider_account": run["review_context"].get("provider_account"),
        "retention_url": run["review_context"].get("retention_url"),
        "local_only_cases": run["review_context"].get("local_only_cases", []),
        "thresholds": run["review_context"].get("thresholds", {}),
        "coverage": {"fixtures": len(run["fixture_hashes"]),
                     "successful_jobs": sum(row["status"] == "success" for row in results),
                     "failed_jobs": sum(row["status"] == "failed" for row in results),
                     "not_run_jobs": sum(row["status"] == "not_run" for row in results)},
        "attempts": len(attempts),
        "errors": dict(Counter(row.get("error_class", "unknown") for row in attempts
                               if row["status"] == "failed")),
        "latency_ms": {"mean": round(statistics.mean(latencies), 1) if latencies else None,
                       "median": round(statistics.median(latencies), 1) if latencies else None,
                       "values": latencies},
        "usage_and_cost": {"pricing_date": PRICING["as_of"], "currency": "USD",
                           "label": "Dated estimate, not provider-reported dollar cost",
                           "estimated_total_usd_for_available_usage": round(sum(estimated), 6),
                           "missing_cost_count": sum(row["cost"]["status"] != "estimated" for row in costs),
                           "per_attempt": costs},
        "model_id_drift": [row["job_id"] for row in attempts if row.get("model_drift")],
        "metrics": metrics,
    }
