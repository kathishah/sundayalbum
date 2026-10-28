"""Create provisional upright glare crops and a review manifest from drafts.

This script does not freeze, publish, or overwrite any reviewed fixture.
Run ``python evals/model-upgrade/prepare_review.py`` once after extraction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DRAFTS = ROOT / "test-cropped-images" / "drafts"

# Clockwise rotation to make each extracted crop upright, inspected visually.
# These are provisional until the owner approves the exact image bytes.
REVIEW = {
    "test-images-img_two_pics_vertical_horizontal_normal-01": (270, "A man in a light jacket standing outdoors."),
    "test-images-img_two_pics_vertical_horizontal_normal-02": (180, "A white car with a person in the driver's seat."),
    "test-images-img_three_pics_normal-01": (180, "People standing and talking outdoors near a building."),
    "test-images-img_three_pics_normal-02": (180, "A large group posing together outdoors."),
    "test-images-img_three_pics_normal-03": (180, "A large group posing together outdoors."),
    "test-images-2-img_1250-01": (0, "Two people posing inside a cave."),
    "test-images-2-img_1250-02": (0, "A cave formation with a bright reflection near the bottom edge."),
    "test-images-2-img_1251-01": (0, "A group sitting on rocks outdoors in bright sunlight."),
    "test-images-3-img_1267-01": (0, "Four people sitting in front of a fountain."),
    "test-images-3-img_1270-01": (0, "Shallow water with bright reflections and a vertical pole."),
}


def sha256(path: Path) -> str:
    """Return the SHA-256 of a local file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Build separate glare inputs and record provisional labels."""
    review_path = DRAFTS / "review-manifest.json"
    if review_path.exists():
        raise FileExistsError(review_path)
    rows = json.loads((DRAFTS / "draft-manifest.json").read_text())["cases"]
    by_id = {row["case_id"]: row for row in rows}
    if not set(REVIEW) <= set(by_id):
        raise ValueError("Required crop drafts are missing")
    selected = []
    for case_id, (rotation, scene) in REVIEW.items():
        row = by_id[case_id]
        source = DRAFTS / "orientation" / f"{case_id}.jpg"
        target = DRAFTS / "glare" / f"{case_id}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        with Image.open(source) as image:
            upright = image.rotate(-rotation, expand=True)
            upright.save(target, quality=95, subsampling=0)
        ambiguous = case_id in {
            "test-images-2-img_1250-02",
            "test-images-3-img_1270-01",
        }
        row.update({
            "expected_rotation_degrees": None if ambiguous else rotation,
            "expected_flip_horizontal": False,
            "ambiguous": ambiguous,
            "glare_input": str(target.relative_to(ROOT)),
            "glare_sha256": sha256(target),
            "glare_transform": {"rotation_clockwise_degrees": rotation, "flip_horizontal": False},
            "scene_description": scene,
            "review_status": "pending_owner_approval",
            "distribution": "local-only" if row["source_path"].startswith(("test-images-2/", "test-images-3/")) else "pending-release",
        })
        selected.append(row)
    review_path.write_text(json.dumps({"schema_version": 1, "cases": selected}, indent=2) + "\n")
    print(f"Prepared {len(selected)} provisional orientation/glare pairs in {DRAFTS}")


if __name__ == "__main__":
    main()
