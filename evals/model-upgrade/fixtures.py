"""Validate and fetch the approved, immutable model-stage crop corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("fixtures.json")
RELEASE_URL = (
    "https://github.com/kathishah/sundayalbum/releases/download/v0.0.4-evaldata/eval-crops.zip"
)


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest() -> dict:
    """Load and validate the checked-in fixture schema."""
    data = json.loads(MANIFEST.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported fixture manifest schema")
    ids: set[str] = set()
    for row in data["cases"]:
        case_id = row["case_id"]
        if case_id in ids:
            raise ValueError(f"Duplicate case ID: {case_id}")
        ids.add(case_id)
        if row["expected_rotation_degrees"] not in (None, 0, 90, 180, 270):
            raise ValueError(f"Invalid rotation label: {case_id}")
        if row["ambiguous"] != (row["expected_rotation_degrees"] is None):
            raise ValueError(f"Ambiguity/label mismatch: {case_id}")
        tasks = set(row["tags"]) & {"orientation", "glare"}
        if not tasks:
            raise ValueError(f"Fixture has no supported task: {case_id}")
        for task in sorted(tasks):
            relative = Path(row[f"{task}_input"])
            expected = Path("test-cropped-images") / task / f"{case_id}.jpg"
            if relative != expected or relative.is_absolute():
                raise ValueError(f"Unsafe or unexpected crop path: {relative}")
            digest = row[f"{task}_sha256"]
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError(f"Invalid SHA-256: {case_id}/{task}")
    return data


def validate(*, release_only: bool = False) -> int:
    """Verify approved crop bytes without loading source HEICs or calling APIs."""
    rows = load_manifest()["cases"]
    checked = 0
    for row in rows:
        if release_only and row["distribution"] == "local-only":
            continue
        for task in ("orientation", "glare"):
            if task not in row["tags"]:
                continue
            path = ROOT / row[f"{task}_input"]
            if not path.is_file():
                raise FileNotFoundError(path)
            if sha256(path) != row[f"{task}_sha256"]:
                raise ValueError(f"Hash mismatch: {path}")
            checked += 1
    return checked


def fetch() -> int:
    """Fetch released crops and install only hash-verified, absent files."""
    data = load_manifest()
    released = [row for row in data["cases"] if row["distribution"] != "local-only"]
    with tempfile.TemporaryDirectory(prefix="sa-eval-download-") as temporary:
        archive = Path(temporary) / "eval-crops.zip"
        urllib.request.urlretrieve(RELEASE_URL, archive)
        with zipfile.ZipFile(archive) as bundle:
            members = {entry.filename: entry for entry in bundle.infolist()}
            for row in released:
                for task in ("orientation", "glare"):
                    if task not in row["tags"]:
                        continue
                    relative = row[f"{task}_input"]
                    if relative not in members:
                        raise ValueError(f"Release is missing {relative}")
                    entry = members[relative]
                    if entry.is_dir():
                        raise ValueError(f"Release entry is a directory: {relative}")
                    staged = Path(temporary) / f"{row['case_id']}-{task}.jpg"
                    with bundle.open(entry) as source, staged.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    if sha256(staged) != row[f"{task}_sha256"]:
                        raise ValueError(f"Release hash mismatch: {relative}")
                    destination = ROOT / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        if sha256(destination) != row[f"{task}_sha256"]:
                            raise ValueError(f"Existing frozen crop differs: {destination}")
                    else:
                        shutil.copyfile(staged, destination)
    return validate(release_only=True)


def main() -> None:
    """Run a local hash check or fetch released fixtures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "fetch"))
    parser.add_argument("--release-only", action="store_true")
    args = parser.parse_args()
    count = validate(release_only=args.release_only) if args.command == "validate" else fetch()
    print(f"Verified {count} crop files")


if __name__ == "__main__":
    main()
