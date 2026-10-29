"""Known-label orientation scoring and glare review artifact tests."""

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals/model-upgrade"))
from evaluation import (  # noqa: E402
    build_glare_review,
    build_orientation_review,
    glare_metrics,
    orientation_metrics,
    reveal_ratings,
)
from records import RunStore  # noqa: E402


def store(tmp_path: Path, task: str, ids: list[str], repeats: int = 1) -> RunStore:
    """Create one fake run with fixture IDs from the approved manifest."""
    return RunStore.create(
        tmp_path,
        run_id="offline-review",
        task=task,
        fixture_set="approved-2026-10-27-v1",
        fixture_hashes={case_id: "a" * 64 for case_id in ids},
        baseline_config={"requested_model": "baseline-model"},
        candidate_config={"requested_model": "candidate-model"},
        pipeline_revision="a" * 40,
        harness_revision="a" * 40,
        sdk_versions={},
        review_context={"repeats": repeats},
    )


def test_orientation_raw_effective_and_ambiguity(tmp_path: Path) -> None:
    rotated = "test-images-img_two_pics_vertical_horizontal_normal-01"
    upright = "test-images-2-img_1250-01"
    ambiguous = "test-images-2-img_1250-02"
    run = store(tmp_path, "orientation", [rotated, upright, ambiguous])
    for arm in ("baseline", "candidate"):
        for case_id, rotation, confidence in (
            (rotated, 270, "high"),
            (upright, 180, "low"),
            (ambiguous, 90, "high"),
        ):
            run.save_result(
                f"{case_id}__{arm}__1",
                {
                    "status": "success",
                    "case_id": case_id,
                    "arm": arm,
                    "repeat": 1,
                    "parsed_output": {
                        "rotation_degrees": rotation,
                        "flip_horizontal": False,
                        "confidence": confidence,
                        "scene_description": "Test scene",
                    },
                },
            )
    scores = orientation_metrics(run)["candidate"]
    assert scores["raw_rotation"] == {"correct": 1, "denominator": 2, "accuracy": 0.5}
    assert scores["effective_rotation"] == {"correct": 2, "denominator": 2, "accuracy": 1.0}
    assert scores["false_flip_rate"] == 0
    assert scores["low_confidence_passthrough_rate"] == 1 / 3
    assert scores["ambiguous_cases"] == [ambiguous]
    page = build_orientation_review(run)
    assert rotated in page.read_text()
    assert (run.directory / "previews" / f"{rotated}.jpg").exists()


def test_labelled_report_and_preference_export(tmp_path: Path) -> None:
    case_id = "test-images-img_two_pics_vertical_horizontal_normal-01"
    run = store(tmp_path, "glare", [case_id])
    for arm, color in (("baseline", "red"), ("candidate", "blue")):
        path = run.directory / "outputs" / f"{arm}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 150), color).save(path)
        run.save_result(
            f"{case_id}__{arm}__1",
            {
                "status": "success",
                "case_id": case_id,
                "arm": arm,
                "repeat": 1,
                "output_path": str(path.relative_to(run.directory)),
            },
        )
    page = build_glare_review(run, seed=42)
    source = page.read_text()
    assert "Baseline — baseline-model" in source
    assert "Candidate — candidate-model" in source
    assert source.count("<select data-preference>") == 1
    assert "Glare Reduction — left" not in source
    assert len(list((run.directory / "previews").glob("*.jpg"))) == 3
    native = glare_metrics(run)
    assert all(row["output_size"] == [100, 150] for row in native.values())
    mapping = json.loads((run.directory / "blind-map.json").read_text())
    assert "seed:42" not in source and str(mapping["seed"]) not in source
    pair_id = mapping["pairs"][0]["pair_id"]
    baseline_side = "left" if mapping["pairs"][0]["left"] == "baseline" else "right"
    assert (
        f'<h3>Baseline — baseline-model</h3><img src="previews/{pair_id}-{baseline_side}.jpg">'
        in source
    )
    ratings = run.directory / "ratings.json"
    ratings.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "review_id": mapping["review_id"],
                "ratings": [{"pair_id": pair_id, "preference": "candidate"}],
            }
        )
    )
    revealed = reveal_ratings(run, ratings)
    revealed_data = json.loads(revealed.read_text())
    assert revealed_data["ratings"] == [{"pair_id": pair_id, "preference": "candidate"}]
    assert revealed_data["preference_counts"] == {"baseline": 0, "candidate": 1, "tie": 0}
    assert revealed_data["models"] == {
        "baseline": "baseline-model",
        "candidate": "candidate-model",
    }
    ratings.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "review_id": mapping["review_id"],
                "ratings": [{"pair_id": pair_id, "preference": "neither"}],
            }
        )
    )
    with pytest.raises(ValueError, match="Invalid or incomplete preference"):
        reveal_ratings(run, ratings)
