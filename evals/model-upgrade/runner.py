"""Local, opt-in model-stage evaluation runner. No calls in dry-run mode."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/pipeline"))

from evaluation import build_glare_review, build_orientation_review  # noqa: E402
from fixtures import load_manifest, sha256  # noqa: E402
from providers import (  # noqa: E402
    call_glare,
    call_orientation,
    make_client,
    preflight,
    read_eval_keys,
)
from records import RunStore  # noqa: E402
from src.ai.claude_vision import build_orientation_prompt  # noqa: E402
from src.glare.remover_openai import _build_prompt, _pick_api_size  # noqa: E402
from src.pipeline import PipelineConfig  # noqa: E402
from summary import summarize  # noqa: E402

SUPPORT = {"orientation": ("ai_orientation", "anthropic"), "glare": ("glare_remove", "openai")}
PRICING_DATE = "2026-10-27"
# Conservative planning estimates only; actual provider charges can differ.
PLANNING_USD_PER_ATTEMPT = {"orientation": 0.02, "glare": 0.30}


def revision() -> str:
    """Return the checked-out code revision."""
    import subprocess

    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_override(path: Path) -> dict:
    """Validate a sparse candidate overlay and resolve local prompt files."""
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1 or not isinstance(data.get("steps"), dict):
        raise ValueError("Candidate config must have schema_version 1 and a steps map")
    for name, step in data["steps"].items():
        if name not in {pair[0] for pair in SUPPORT.values()} or not isinstance(step, dict):
            raise ValueError(f"Unsupported step: {name}")
        if set(step) - {"provider", "model", "prompt", "prompt_file", "parameters"}:
            raise ValueError(f"Unsupported override field in {name}")
        if "prompt" in step and "prompt_file" in step:
            raise ValueError("Use prompt or prompt_file, not both")
        if "prompt_file" in step:
            prompt_path = (path.parent / step.pop("prompt_file")).resolve()
            if not prompt_path.is_file():
                raise FileNotFoundError(prompt_path)
            step["prompt"] = prompt_path.read_text()
            step["prompt_source"] = str(prompt_path)
        if "parameters" in step and not isinstance(step["parameters"], dict):
            raise ValueError("parameters must be a map")
    return data


def effective_config(task: str, override: dict, cases: list[dict]) -> tuple[dict, dict]:
    """Resolve current pipeline values and a sparse candidate overlay."""
    if task not in SUPPORT:
        raise ValueError(f"Unsupported task: {task}")
    step_name, provider = SUPPORT[task]
    production = PipelineConfig()
    if task == "orientation":
        model = production.ai_orientation_model
        parameters = {"max_tokens": 256}
        prompts = {row["case_id"]: build_orientation_prompt() for row in cases}
    else:
        model = production.openai_model
        parameters = {
            "quality": production.openai_glare_quality,
            "input_fidelity": production.openai_glare_input_fidelity,
            "n": 1,
        }
        prompts = {row["case_id"]: _build_prompt(row["scene_description"]) for row in cases}
    baseline = {
        "step": step_name,
        "provider": provider,
        "requested_model": model,
        "parameters": parameters,
        "prompts": prompts,
        "prompt_hashes": {
            key: hashlib.sha256(text.encode()).hexdigest() for key, text in prompts.items()
        },
        "sources": {
            "provider": "production",
            "model": "production",
            "prompt": "production",
            "parameters": "production",
        },
    }
    selected = override["steps"].get(step_name, {})
    if selected.get("provider", provider) != provider:
        raise ValueError(f"Unsupported {task} provider: {selected['provider']}")
    allowed_params = (
        {"max_tokens"} if task == "orientation" else {"quality", "input_fidelity", "n", "size"}
    )
    if set(selected.get("parameters", {})) - allowed_params:
        raise ValueError("Unsupported request parameter override")
    candidate = json.loads(json.dumps(baseline))
    candidate["requested_model"] = selected.get("model", model)
    candidate["parameters"].update(selected.get("parameters", {}))
    if "prompt" in selected:
        candidate["prompts"] = {row["case_id"]: selected["prompt"] for row in cases}
        candidate["prompt_hashes"] = {
            key: hashlib.sha256(value.encode()).hexdigest()
            for key, value in candidate["prompts"].items()
        }
    candidate["sources"] = {
        "provider": "override" if "provider" in selected else "production",
        "model": "override" if "model" in selected else "production",
        "prompt": selected.get("prompt_source", "override")
        if "prompt" in selected
        else "production",
        "parameters": {
            key: "override" if key in selected.get("parameters", {}) else "production"
            for key in candidate["parameters"]
        },
    }
    if task == "glare":
        for row in cases:
            with Image.open(ROOT / row["glare_input"]) as image:
                width, height = image.size
            size = _pick_api_size(width, height)
            baseline.setdefault("parameters_by_case", {})[row["case_id"]] = {
                **parameters,
                "size": size,
            }
            candidate.setdefault("parameters_by_case", {})[row["case_id"]] = {
                **candidate["parameters"],
                "size": candidate["parameters"].get("size", size),
            }
    return baseline, candidate


def selected_cases(task: str, requested: list[str]) -> tuple[dict, list[dict]]:
    """Load only manifest crop bytes and verify hashes before any request."""
    manifest = load_manifest()
    cases = [row for row in manifest["cases"] if not requested or row["case_id"] in requested]
    if not cases or (requested and set(requested) != {row["case_id"] for row in cases}):
        raise ValueError("No matching fixtures or an unknown case ID was supplied")
    for row in cases:
        path = ROOT / row[f"{task}_input"]
        if sha256(path) != row[f"{task}_sha256"]:
            raise ValueError(f"Fixture hash mismatch: {path}")
    return manifest, cases


def use_candidate_scenes(cases: list[dict], source_dir: Path) -> str:
    """Use successful candidate orientation descriptions in a later glare run."""
    source = RunStore(source_dir)
    manifest = source.manifest()
    if manifest["task"] != "orientation":
        raise ValueError("Scene description source must be an orientation run")
    results = sorted(
        source.all_results(), key=lambda row: (row.get("case_id", ""), row.get("repeat", 0))
    )
    descriptions = {}
    for row in results:
        if row.get("arm") == "candidate" and row["status"] == "success":
            descriptions.setdefault(row["case_id"], row["parsed_output"]["scene_description"])
    for case in cases:
        description = descriptions.get(case["case_id"])
        if not description:
            raise ValueError(f"No candidate scene description for {case['case_id']}")
        case["scene_description"] = description
    return manifest["run_id"]


def job_id(case_id: str, arm: str, repeat: int) -> str:
    """Build a stable result ID."""
    return f"{case_id}__{arm}__{repeat}"


def run(args: argparse.Namespace) -> Path | None:
    """Dry-run or execute one task, persisting every provider attempt."""
    manifest, cases = selected_cases(args.task, args.cases)
    scene_source = None
    if args.scene_descriptions_from:
        if args.task != "glare":
            raise ValueError("Candidate scene descriptions can only be used for glare")
        scene_source = use_candidate_scenes(cases, args.scene_descriptions_from)
    override = load_override(args.candidate)
    baseline, candidate = effective_config(args.task, override, cases)
    provider = SUPPORT[args.task][1]
    repeats = args.repeats if args.repeats is not None else (3 if args.task == "orientation" else 1)
    if repeats < 1 or args.max_retries < 0:
        raise ValueError("Repeats must be positive and max-retries nonnegative")
    thresholds = args.thresholds or (
        {"min_rotated_accuracy": 1.0, "min_upright_accuracy": 0.8}
        if args.task == "orientation"
        else {}
    )
    if not isinstance(thresholds, dict) or any(
        not isinstance(value, (int, float)) or value < 0 or value > 1
        for value in thresholds.values()
    ):
        raise ValueError("Thresholds must be a JSON map of values between 0 and 1")
    jobs = [
        (row, arm, repeat)
        for row in cases
        for arm in ("baseline", "candidate")
        for repeat in range(1, repeats + 1)
    ]
    worst_case = len(jobs) * (args.max_retries + 1)
    estimate = worst_case * PLANNING_USD_PER_ATTEMPT[args.task]
    print(f"Task: {args.task}; fixtures: {len(cases)}; repeats: {repeats}")
    print(f"Models: {baseline['requested_model']} vs {candidate['requested_model']} ({provider})")
    print(f"Worst case: {worst_case} attempts")
    print(f"Dated planning estimate: ${estimate:.2f} (USD, {PRICING_DATE})")
    print(f"Local-only fixtures: {sum(row['distribution'] == 'local-only' for row in cases)}")
    if not args.execute:
        return None
    if args.resume and not args.run_id:
        raise ValueError("--resume requires --run-id")
    if args.max_attempts is None or args.max_attempts < 1:
        raise ValueError("--execute requires a positive --max-attempts cap")
    if args.max_estimated_usd is None or args.max_estimated_usd < estimate:
        raise ValueError(f"--max-estimated-usd must cover worst-case estimate ${estimate:.2f}")
    if not args.provider_account or not args.retention_url:
        raise ValueError("--provider-account and --retention-url are required for paid calls")
    # Validate every selected credential before constructing any SDK client.
    keys = read_eval_keys(ROOT / "secrets.json", {provider})
    fixture_hashes = {row["case_id"]: row[f"{args.task}_sha256"] for row in cases}
    run_id = (
        args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    root = args.output_dir
    context = {
        "provider_account": args.provider_account,
        "retention_url": args.retention_url,
        "local_only_cases": [
            row["case_id"] for row in cases if row["distribution"] == "local-only"
        ],
        "repeats": repeats,
        "max_retries": args.max_retries,
        "max_attempts": args.max_attempts,
        "max_estimated_usd": args.max_estimated_usd,
        "planning_price_date": PRICING_DATE,
        "planning_usd_per_attempt": PLANNING_USD_PER_ATTEMPT[args.task],
        "thresholds": thresholds,
    }
    if scene_source:
        context["orientation_scene_source_run"] = scene_source
    if args.resume:
        store = RunStore.resume(
            root,
            run_id=run_id,
            task=args.task,
            fixture_set=manifest["fixture_set"],
            fixture_hashes=fixture_hashes,
            baseline_config=baseline,
            candidate_config=candidate,
            review_context=context,
        )
    else:
        store = RunStore.create(
            root,
            run_id=run_id,
            task=args.task,
            fixture_set=manifest["fixture_set"],
            fixture_hashes=fixture_hashes,
            baseline_config=baseline,
            candidate_config=candidate,
            pipeline_revision=revision(),
            harness_revision=revision(),
            sdk_versions={provider: importlib.metadata.version(provider)},
            review_context=context,
        )
    client = make_client(provider, keys[provider])
    for model in {baseline["requested_model"], candidate["requested_model"]}:
        preflight(client, model)
    used = sum(
        len(store.attempts(job_id(row["case_id"], arm, repeat))) for row, arm, repeat in jobs
    )
    for row, arm, repeat in jobs:
        key = job_id(row["case_id"], arm, repeat)
        prior = store.result(key)
        if prior and prior["status"] == "success":
            continue
        if prior and prior["status"] == "failed" and not args.retry_failed:
            continue
        config = baseline if arm == "baseline" else candidate
        path = ROOT / row[f"{args.task}_input"]
        image_bytes = path.read_bytes()
        for _ in range(args.max_retries + 1):
            if used >= args.max_attempts:
                store.save_result(
                    key,
                    {
                        "status": "not_run",
                        "reason": "attempt_cap",
                        "case_id": row["case_id"],
                        "arm": arm,
                        "repeat": repeat,
                        "input_sha256": row[f"{args.task}_sha256"],
                    },
                )
                break
            attempt = len(store.attempts(key)) + 1
            parameters = config.get("parameters_by_case", {}).get(
                row["case_id"], config["parameters"]
            )
            call = call_orientation if args.task == "orientation" else call_glare
            attempt_started_at = datetime.now(UTC).isoformat()
            result = call(
                client,
                image_bytes=image_bytes,
                model=config["requested_model"],
                prompt=config["prompts"][row["case_id"]],
                parameters=parameters,
            )
            used += 1
            output = result.pop("output_bytes", None)
            if output is not None:
                output_path = store.directory / "outputs" / key / f"attempt-{attempt:03d}.png"
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(output)
                result["output_path"] = str(output_path.relative_to(store.directory))
            result.update(
                {
                    "case_id": row["case_id"],
                    "arm": arm,
                    "repeat": repeat,
                    "input_sha256": row[f"{args.task}_sha256"],
                    "requested_model": config["requested_model"],
                    "model_drift": result.get("resolved_model")
                    not in (None, config["requested_model"]),
                    "prompt": config["prompts"][row["case_id"]],
                    "prompt_sha256": config["prompt_hashes"][row["case_id"]],
                    "parameters": parameters,
                    "attempt_started_at": attempt_started_at,
                }
            )
            store.save_attempt(key, attempt, result)
            store.save_result(key, result)
            if result["status"] == "success" or not result.get("retryable"):
                break
            time.sleep(min(2**attempt, 10))
    if args.task == "glare":
        build_glare_review(store)
    else:
        build_orientation_review(store)
    store.write_summary({**summarize(store), "attempts_used": used})
    print(f"Run saved: {store.directory}")
    return store.directory


def main() -> None:
    """Parse CLI arguments and run one model stage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=tuple(SUPPORT))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cases", nargs="*", default=[])
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "eval-runs")
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--max-estimated-usd", type=float)
    parser.add_argument("--provider-account")
    parser.add_argument("--retention-url")
    parser.add_argument(
        "--scene-descriptions-from",
        type=Path,
        help="Use successful candidate descriptions from an earlier orientation run",
    )
    parser.add_argument("--thresholds", type=json.loads, default={})
    run(parser.parse_args())


if __name__ == "__main__":
    main()
