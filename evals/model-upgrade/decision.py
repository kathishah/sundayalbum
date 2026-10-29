"""Record a human model-upgrade decision without touching production defaults."""

import argparse
from pathlib import Path

from records import RunStore


def main() -> None:
    """Validate review evidence and write a local decision record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("status", choices=("accepted", "rejected", "inconclusive"))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--limitations", default="")
    parser.add_argument(
        "--glare-validation-run",
        type=Path,
        help="Baseline glare run using the candidate scene descriptions",
    )
    parser.add_argument("--scene-description-waiver", help="Reason glare validation is waived")
    args = parser.parse_args()
    store = RunStore(args.run_dir)
    run = store.manifest()
    if not (store.directory / "summary.json").is_file():
        parser.error("Run summary is missing")
    evidence = {}
    if args.status == "accepted":
        if run["task"] == "orientation":
            if args.glare_validation_run and args.scene_description_waiver:
                parser.error("Supply a glare run or a waiver, not both")
            if args.glare_validation_run:
                glare_store = RunStore(args.glare_validation_run)
                glare = glare_store.manifest()
                if glare["task"] != "glare":
                    parser.error("Glare validation path is not a glare run")
                if glare["review_context"].get("orientation_scene_source_run") != run["run_id"]:
                    parser.error(
                        "Glare run does not use this orientation run's candidate descriptions"
                    )
                if glare["baseline_config"]["requested_model"] != "gpt-image-1.5":
                    parser.error("Glare validation did not use the baseline glare model")
                if not set(run["fixture_hashes"]) <= set(glare["fixture_hashes"]):
                    parser.error("Glare validation does not cover every orientation fixture")
                successful = {
                    row["case_id"]
                    for row in glare_store.all_results()
                    if row.get("arm") == "baseline" and row["status"] == "success"
                }
                if not set(run["fixture_hashes"]) <= successful:
                    parser.error(
                        "Glare validation lacks successful baseline outputs for every fixture"
                    )
                evidence["glare_validation_run"] = glare["run_id"]
            elif args.scene_description_waiver:
                evidence["scene_description_waiver"] = args.scene_description_waiver
            else:
                parser.error("Accepting orientation requires baseline glare validation or a waiver")
        elif run["task"] == "glare" and not (store.directory / "revealed-ratings.json").is_file():
            parser.error("Accepting glare requires saved and revealed reviewer ratings")
    output = store.write_decision(
        reviewer=args.reviewer,
        status=args.status,
        rationale=args.rationale,
        limitations=args.limitations,
        evidence=evidence,
    )
    print(output)


if __name__ == "__main__":
    main()
