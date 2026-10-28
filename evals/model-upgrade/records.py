"""Versioned, provider-neutral local records for model-stage evaluations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SECRET_KEY = re.compile(r"(^|_)(api_key|secret|password|access_token|authorization)(_|$)", re.I)
_SIGNED_URL = re.compile(r"[?&](X-Amz-Signature|Signature|sig|token|api_key)=", re.I)
_KEY_IN_TEXT = re.compile(r"\b(?:sk-(?:ant-)?[A-Za-z0-9_-]+)\b")


def utc_now() -> str:
    """Return an ISO UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    """Hash a JSON-compatible value using stable key ordering."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def redact(value: Any) -> Any:
    """Remove credentials and signed URLs before writing a run record."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SECRET_KEY.search(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        if _SIGNED_URL.search(value):
            return "[REDACTED]"
        return _KEY_IN_TEXT.sub("[REDACTED]", value)
    return value


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized = redact(value)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as stream:
        json.dump(sanitized, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


class RunStore:
    """Own one run directory and reject incompatible resumes.

    A job key is ``<case-id>__<baseline|candidate>__<repeat>``. Each attempt
    and final fixture result is written atomically as its own JSON file so a
    process interruption cannot erase earlier work.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @staticmethod
    def _check_id(identifier: str) -> None:
        if not _SAFE_ID.fullmatch(identifier):
            raise ValueError(f"Unsafe run or job ID: {identifier}")

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        run_id: str,
        task: str,
        fixture_set: str,
        fixture_hashes: dict[str, str],
        baseline_config: dict,
        candidate_config: dict,
        pipeline_revision: str,
        harness_revision: str,
        sdk_versions: dict[str, str],
        review_context: dict,
    ) -> "RunStore":
        """Create an empty run with complete effective configuration metadata."""
        cls._check_id(run_id)
        directory = root / run_id
        directory.mkdir(parents=True, exist_ok=False)
        store = cls(directory)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "task": task,
            "fixture_set": fixture_set,
            "fixture_hashes": fixture_hashes,
            "baseline_config": baseline_config,
            "candidate_config": candidate_config,
            "baseline_config_hash": canonical_hash(redact(baseline_config)),
            "candidate_config_hash": canonical_hash(redact(candidate_config)),
            "pipeline_revision": pipeline_revision,
            "harness_revision": harness_revision,
            "sdk_versions": sdk_versions,
            "review_context": review_context,
            "created_at": utc_now(),
        }
        _atomic_json(directory / "run.json", manifest)
        return store

    @classmethod
    def resume(
        cls,
        root: Path,
        *,
        run_id: str,
        task: str,
        fixture_set: str,
        fixture_hashes: dict[str, str],
        baseline_config: dict,
        candidate_config: dict,
    ) -> "RunStore":
        """Open a run only if fixtures and effective settings match exactly."""
        cls._check_id(run_id)
        store = cls(root / run_id)
        manifest = store.manifest()
        expected = {
            "schema_version": SCHEMA_VERSION,
            "task": task,
            "fixture_set": fixture_set,
            "fixture_hashes": fixture_hashes,
            "baseline_config_hash": canonical_hash(redact(baseline_config)),
            "candidate_config_hash": canonical_hash(redact(candidate_config)),
        }
        for field, value in expected.items():
            if manifest.get(field) != value:
                raise ValueError(f"Cannot resume: {field} differs from recorded run")
        return store

    def manifest(self) -> dict:
        """Read the immutable run manifest."""
        data = json.loads((self.directory / "run.json").read_text())
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported run schema")
        return data

    def save_attempt(self, job_id: str, attempt: int, result: dict) -> Path:
        """Persist one successful or failed provider attempt."""
        self._check_id(job_id)
        if attempt < 1:
            raise ValueError("Attempt must be positive")
        path = self.directory / "attempts" / job_id / f"{attempt:03d}.json"
        if path.exists():
            raise FileExistsError(path)
        _atomic_json(path, {"schema_version": SCHEMA_VERSION, "job_id": job_id,
                            "attempt": attempt, "recorded_at": utc_now(), **result})
        return path

    def attempts(self, job_id: str) -> list[dict]:
        """Read all recorded attempts for a fixture/configuration/repeat."""
        self._check_id(job_id)
        folder = self.directory / "attempts" / job_id
        return [json.loads(path.read_text()) for path in sorted(folder.glob("*.json"))] if folder.exists() else []

    def save_result(self, job_id: str, result: dict) -> Path:
        """Persist the current aggregate outcome for one fixture job."""
        self._check_id(job_id)
        path = self.directory / "results" / f"{job_id}.json"
        _atomic_json(path, {"schema_version": SCHEMA_VERSION, "job_id": job_id,
                            "recorded_at": utc_now(), **result})
        return path

    def result(self, job_id: str) -> dict | None:
        """Read the current outcome, or None if it has not run."""
        self._check_id(job_id)
        path = self.directory / "results" / f"{job_id}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def all_results(self) -> list[dict]:
        """Read all aggregate results, including failures and not-run entries."""
        folder = self.directory / "results"
        return [json.loads(path.read_text()) for path in sorted(folder.glob("*.json"))] if folder.exists() else []

    def write_summary(self, summary: dict) -> Path:
        """Write a machine-readable run summary."""
        path = self.directory / "summary.json"
        _atomic_json(path, {"schema_version": SCHEMA_VERSION, "run_id": self.manifest()["run_id"],
                            "updated_at": utc_now(), **summary})
        return path

    def write_decision(self, *, reviewer: str, status: str, rationale: str,
                       limitations: str) -> Path:
        """Record a human decision without changing production settings."""
        if status not in {"accepted", "rejected", "inconclusive"}:
            raise ValueError("Invalid decision status")
        if not reviewer.strip() or not rationale.strip():
            raise ValueError("Reviewer and rationale are required")
        path = self.directory / "decision.json"
        _atomic_json(path, {"schema_version": SCHEMA_VERSION,
                            "run_id": self.manifest()["run_id"], "reviewer": reviewer,
                            "date": utc_now(), "status": status, "rationale": rationale,
                            "known_limitations": limitations})
        return path
