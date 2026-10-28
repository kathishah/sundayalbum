"""Prepare reviewable model-stage crop drafts; never modify frozen fixtures.

Run from the repository root with ``python evals/model-upgrade/build_fixtures.py``.
This tool performs only the production load-through-photo-split steps. It never
calls a model. Drafts are deliberately kept outside Git until human review.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/pipeline"))

from src.pipeline import PipelineConfig  # noqa: E402
from src.steps import load, normalize, page_detect, perspective, photo_detect, photo_split  # noqa: E402
from src.storage.local import LocalStorage  # noqa: E402

SOURCES = (
    "test-images/IMG_two_pics_vertical_horizontal_normal.HEIC",
    "test-images/IMG_three_pics_normal.HEIC",
    "test-images-2/IMG_1250.HEIC",
    "test-images-2/IMG_1251.HEIC",
    "test-images-3/IMG_1267.HEIC",
    "test-images-3/IMG_1270.HEIC",
)
DRAFT_ROOT = ROOT / "test-cropped-images" / "drafts"


def sha256(path: Path) -> str:
    """Hash a local file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def revision() -> str:
    """Return the pipeline revision used to create these drafts."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def prepare(source_name: str, config: PipelineConfig, output: Path) -> list[dict]:
    """Extract a source with the production deterministic splitter."""
    source = ROOT / source_name
    if not source.is_file():
        raise FileNotFoundError(source)
    with tempfile.TemporaryDirectory(prefix="sa-eval-crops-") as temporary:
        storage = LocalStorage(temporary)
        stem = source.stem
        storage.put_file(str(source), f"uploads/{source.name}")
        for step in (load, normalize, page_detect, perspective, photo_detect):
            step.run(storage, stem, config)
        detection = storage.read_json(f"debug/{stem}_05_photo_detections.json")
        split = photo_split.run(storage, stem, config)
        rows = []
        for index in range(1, split["photo_count"] + 1):
            case_id = f"{source.parent.name}-{stem.lower()}-{index:02d}"
            draft = output / "orientation" / f"{case_id}.jpg"
            draft.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(storage._resolve(f"debug/{stem}_05_photo_{index:02d}_raw.jpg"), draft)
            crop = (
                detection["detections"][index - 1]
                if not detection["multi_blob"] and index <= len(detection["detections"])
                else {"photo_quad": storage.read_json(f"debug/{stem}_03_page_detection.json")
                      .get("photo_quads", [])[index - 1] if detection["multi_blob"] else None}
            )
            rows.append({
                "case_id": case_id,
                "source_path": source_name,
                "source_sha256": sha256(source),
                "photo_index": index,
                "crop": crop,
                "orientation_input": f"test-cropped-images/drafts/orientation/{case_id}.jpg",
                "orientation_sha256": sha256(draft),
                "extraction_tool": "production load/normalize/page_detect/perspective/photo_detect/photo_split",
                "extraction_config": asdict(config),
                "pipeline_revision": revision(),
                "platform": platform.platform(),
                "architecture": platform.machine(),
                "review_status": "draft",
            })
        return rows


def main() -> None:
    """Write new drafts or compare regenerated hashes; never overwrite a draft."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Report hash changes without overwriting drafts")
    args = parser.parse_args()
    if not args.refresh and DRAFT_ROOT.exists():
        parser.error(f"Draft directory already exists: {DRAFT_ROOT}; use --refresh")
    config = PipelineConfig(use_ai_orientation=False, use_openai_glare_removal=False)
    with tempfile.TemporaryDirectory(prefix="sa-eval-refresh-") as temporary:
        output = Path(temporary) if args.refresh else DRAFT_ROOT
        rows = [row for source in SOURCES for row in prepare(source, config, output)]
        if args.refresh:
            for row in rows:
                path = DRAFT_ROOT / "orientation" / f"{row['case_id']}.jpg"
                before = sha256(path) if path.exists() else "MISSING"
                after = row["orientation_sha256"]
                print(f"{row['case_id']}: {'same' if before == after else 'CHANGED'} {before} -> {after}")
        else:
            (DRAFT_ROOT / "draft-manifest.json").write_text(
                json.dumps({"schema_version": 1, "cases": rows}, indent=2) + "\n"
            )
            print(f"Wrote {len(rows)} draft crops to {DRAFT_ROOT}")


if __name__ == "__main__":
    main()
