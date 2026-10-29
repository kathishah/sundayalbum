"""Task-specific offline metrics and blinded glare review artifacts."""

from __future__ import annotations

import html
import json
import random
import secrets
from collections import Counter, defaultdict
from pathlib import Path

from fixtures import ROOT, load_manifest
from PIL import Image
from records import RunStore


def orientation_metrics(store: RunStore) -> dict:
    """Score raw and production confidence-gated orientation by arm."""
    cases = {row["case_id"]: row for row in load_manifest()["cases"]}
    groups: dict[str, list[dict]] = defaultdict(list)
    for result in store.all_results():
        groups[result.get("arm", "unknown")].append(result)
    report: dict = {}
    for arm in ("baseline", "candidate"):
        rows = groups[arm]
        scored = []
        confidence = Counter()
        agreement: dict[str, dict] = {}
        by_case: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_case[row.get("case_id", "unknown")].append(row)
            if row["status"] != "success":
                continue
            output = row["parsed_output"]
            confidence[output["confidence"]] += 1
            case = cases[row["case_id"]]
            if not case["ambiguous"]:
                scored.append((case, output))
        for case_id, attempts in by_case.items():
            outputs = [r["parsed_output"] for r in attempts if r["status"] == "success"]
            labels = {(x["rotation_degrees"], x["flip_horizontal"]) for x in outputs}
            agreement[case_id] = {
                "successful_repeats": len(outputs),
                "all_agree": len(labels) <= 1 if len(outputs) > 1 else None,
            }

        def accuracy(pairs: list[tuple[dict, dict]], *, effective: bool) -> dict:
            correct = 0
            for case, output in pairs:
                rotation = output["rotation_degrees"]
                if effective and output["confidence"] == "low":
                    rotation = 0
                correct += rotation == case["expected_rotation_degrees"]
            return {
                "correct": correct,
                "denominator": len(pairs),
                "accuracy": correct / len(pairs) if pairs else None,
            }

        successes = sum(r["status"] == "success" for r in rows)
        false_flips = sum(output["flip_horizontal"] for _, output in scored)
        report[arm] = {
            "raw_rotation": accuracy(scored, effective=False),
            "effective_rotation": accuracy(scored, effective=True),
            "real_rotated": accuracy(
                [(c, o) for c, o in scored if c["expected_rotation_degrees"] != 0], effective=True
            ),
            "real_upright": accuracy(
                [(c, o) for c, o in scored if c["expected_rotation_degrees"] == 0], effective=True
            ),
            "false_flip_rate": false_flips / len(scored) if scored else None,
            "false_flips": false_flips,
            "confidence_distribution": dict(confidence),
            "low_confidence_passthrough_rate": confidence["low"] / successes if successes else None,
            "ambiguous_cases": sorted(
                case_id for case_id in by_case if cases[case_id]["ambiguous"]
            ),
            "structured_failures": sum(
                r.get("error_class") in {"parse_failure", "truncated"} for r in rows
            ),
            "failures": sum(r["status"] == "failed" for r in rows),
            "repeat_agreement": agreement,
            "scene_descriptions": {
                r["case_id"]: r["parsed_output"]["scene_description"]
                for r in rows
                if r["status"] == "success"
            },
        }
    return report


def build_orientation_review(store: RunStore) -> Path:
    """Create a local visual report with crop context and per-repeat labels."""
    run = store.manifest()
    if run["task"] != "orientation":
        raise ValueError("Orientation report requires an orientation run")
    cases = {row["case_id"]: row for row in load_manifest()["cases"]}
    by_case: dict[str, list[dict]] = defaultdict(list)
    for result in store.all_results():
        by_case[result.get("case_id", "unknown")].append(result)
    cards = []
    for case_id in run["fixture_hashes"]:
        case = cases[case_id]
        preview = store.directory / "previews" / f"{case_id}.jpg"
        _preview(ROOT / case["orientation_input"], preview)
        rows = []
        for result in sorted(
            by_case[case_id], key=lambda item: (item.get("arm", ""), item.get("repeat", 0))
        ):
            output = result.get("parsed_output") or {}
            cells = (
                result.get("arm", ""),
                result.get("repeat", ""),
                result["status"],
                output.get("rotation_degrees", ""),
                output.get("flip_horizontal", ""),
                output.get("confidence", ""),
                output.get("scene_description", ""),
            )
            rows.append(
                "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>"
            )
        expected = "ambiguous" if case["ambiguous"] else str(case["expected_rotation_degrees"])
        cards.append(
            f"<section><h2>{html.escape(case_id)}</h2>"
            f"<p>Expected clockwise rotation: {expected}</p>"
            f'<img src="{preview.relative_to(store.directory)}" width="400">'
            "<table><tr><th>Arm</th><th>Repeat</th><th>Status</th><th>Rotation</th>"
            "<th>Flip</th><th>Confidence</th><th>Scene description</th></tr>"
            + "".join(rows)
            + "</table></section>"
        )
    target = store.directory / "review.html"
    target.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        "<title>Orientation evaluation</title><style>body{font:16px system-ui;margin:2rem}"
        "section{border-bottom:1px solid #aaa;padding:1rem 0}"
        "table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:.4rem}</style>"
        "<h1>Orientation evaluation</h1>" + "".join(cards) + "</html>"
    )
    return target


def _preview(source: Path, target: Path) -> None:
    """Normalize an image to a fixed square without leaking native dimensions."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((480, 480), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (512, 512), "#e8e5df")
        canvas.paste(rgb, ((512 - rgb.width) // 2, (512 - rgb.height) // 2))
        canvas.save(target, quality=88)


def glare_metrics(store: RunStore) -> dict:
    """Report native output dimensions and resolution changes outside blind HTML."""
    if store.manifest()["task"] != "glare":
        raise ValueError("Glare metrics require a glare run")
    cases = {row["case_id"]: row for row in load_manifest()["cases"]}
    metrics: dict[str, dict] = {}
    for result in store.all_results():
        if result["status"] != "success" or not result.get("output_path"):
            continue
        case = cases[result["case_id"]]
        with Image.open(ROOT / case["glare_input"]) as original:
            original_size = original.size
        with Image.open(store.directory / result["output_path"]) as output:
            output_size = output.size
        metrics[result["job_id"]] = {
            "input_size": list(original_size),
            "output_size": list(output_size),
            "pixel_area_ratio": (output_size[0] * output_size[1])
            / (original_size[0] * original_size[1]),
        }
    return metrics


def build_glare_review(store: RunStore, *, seed: int | None = None) -> Path:
    """Create a labelled side-by-side review from the saved run outputs."""
    manifest = store.manifest()
    if manifest["task"] != "glare":
        raise ValueError("Image review is only for glare runs")
    mapping_path = store.directory / "blind-map.json"
    if mapping_path.exists():
        mapping = json.loads(mapping_path.read_text())
        if seed is not None and mapping["seed"] != seed:
            raise ValueError("Existing blind-review seed differs")
        seed = mapping["seed"]
        review_id = mapping["review_id"]
    else:
        seed = secrets.randbits(64) if seed is None else seed
        review_id = secrets.token_hex(16)
    rng = random.Random(seed)
    saved_pairs = {row["pair_id"]: row for row in mapping["pairs"]} if mapping_path.exists() else {}
    results = {row["job_id"]: row for row in store.all_results()}
    cases = {row["case_id"]: row for row in load_manifest()["cases"]}
    repeats = manifest["review_context"]["repeats"]
    cards = []
    private_pairs = []
    for case_id in manifest["fixture_hashes"]:
        for repeat in range(1, repeats + 1):
            pair_id = f"{case_id}__{repeat}"
            if pair_id in saved_pairs:
                left_arm, right_arm = saved_pairs[pair_id]["left"], saved_pairs[pair_id]["right"]
            else:
                left_arm, right_arm = (
                    ("baseline", "candidate") if rng.getrandbits(1) else ("candidate", "baseline")
                )
            pair = {"pair_id": pair_id, "left": left_arm, "right": right_arm}
            private_pairs.append(pair)
            source = ROOT / cases[case_id]["glare_input"]
            context = store.directory / "previews" / f"{pair_id}-original.jpg"
            _preview(source, context)
            arms = {}
            for side, arm in (("left", left_arm), ("right", right_arm)):
                result = results.get(f"{case_id}__{arm}__{repeat}")
                if result and result["status"] == "success" and result.get("output_path"):
                    preview = store.directory / "previews" / f"{pair_id}-{side}.jpg"
                    _preview(store.directory / result["output_path"], preview)
                    arms[side] = str(preview.relative_to(store.directory))
                else:
                    arms[side] = None
            arm_previews = {left_arm: arms["left"], right_arm: arms["right"]}
            cards.append((pair_id, str(context.relative_to(store.directory)), arm_previews))
    if not mapping_path.exists():
        mapping_path.write_text(
            json.dumps(
                {"schema_version": 1, "seed": seed, "review_id": review_id, "pairs": private_pairs},
                indent=2,
            )
            + "\n"
        )
    page = _review_html(
        cards,
        review_id,
        manifest["baseline_config"]["requested_model"],
        manifest["candidate_config"]["requested_model"],
    )
    target = store.directory / "review.html"
    target.write_text(page)
    return target


def _review_html(
    cards: list[tuple[str, str, dict]], review_id: str, baseline_model: str, candidate_model: str
) -> str:
    """Build a stand-alone page with one direct preference per crop."""
    body = []
    for pair_id, context, arms in cards:
        safe_id = html.escape(pair_id, quote=True)
        images = [f'<div><h3>Original</h3><img src="{html.escape(context, quote=True)}"></div>']
        for arm, model in (("baseline", baseline_model), ("candidate", candidate_model)):
            image_path = arms[arm]
            inner = (
                f'<img src="{html.escape(image_path, quote=True)}">'
                if image_path
                else "<p>Output unavailable</p>"
            )
            images.append(f"<div><h3>{arm.title()} — {html.escape(model)}</h3>{inner}</div>")
        body.append(
            f'<section class="pair" data-pair="{safe_id}"><h2>{safe_id}</h2>'
            f'<div class="images">{"".join(images)}</div>'
            "<label>Which result do you prefer? <select data-preference>"
            '<option value="">Select one</option><option value="baseline">Baseline</option>'
            '<option value="candidate">Candidate</option><option value="tie">Tie</option>'
            "</select></label></section>"
        )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Glare comparison review</title>
<style>body{{font:16px system-ui;margin:2rem;background:#f8f6f2;color:#222}}
.pair{{background:white;padding:1rem;margin:1.5rem 0;border:1px solid #ccc}}
.images{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}}
.images img{{width:100%;max-width:512px;aspect-ratio:1;object-fit:contain;background:#e8e5df}}
label{{display:flex;align-items:center;gap:1rem;margin-top:1rem}}select{{min-width:10rem}}</style>
<h1>Glare comparison</h1><p>For each crop, compare the two edits with the original.
Choose the result you would keep, or choose Tie. Then download your choices.</p>
{"".join(body)}<button id="download">Download ratings JSON</button>
<script>document.getElementById('download').onclick=()=>{{
const ratings=[...document.querySelectorAll('.pair')].map(p=>({{
pair_id:p.dataset.pair,preference:p.querySelector('[data-preference]').value
}}));
if(ratings.some(x=>!x.preference)){{
  alert('Choose a preference for every crop before saving.');return;
}}
const data={{schema_version:2,review_id:'{review_id}',ratings}};
const a=document.createElement('a');
a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));
a.download='ratings.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}};</script></html>"""


def reveal_ratings(store: RunStore, ratings_path: Path) -> Path:
    """Validate downloaded choices and write a decision-ready record."""
    mapping = json.loads((store.directory / "blind-map.json").read_text())
    ratings = json.loads(ratings_path.read_text())
    if ratings.get("review_id") != mapping["review_id"]:
        raise ValueError("Ratings review ID does not match the blind mapping")
    by_pair = {row["pair_id"]: row for row in mapping["pairs"]}
    if {row["pair_id"] for row in ratings["ratings"]} != set(by_pair):
        raise ValueError("Ratings do not cover exactly the mapped pairs")
    if len(ratings["ratings"]) != len(by_pair):
        raise ValueError("Ratings contain duplicate pairs")
    if ratings.get("schema_version") == 2:
        for row in ratings["ratings"]:
            if set(row) != {"pair_id", "preference"} or row["preference"] not in (
                "baseline",
                "candidate",
                "tie",
            ):
                raise ValueError("Invalid or incomplete preference")
        joined = ratings["ratings"]
    elif ratings.get("schema_version") == 1:
        fields = {
            f"{criterion}_{side}"
            for criterion in (
                "glare_reduction",
                "detail_preservation",
                "changed_content",
                "color_shift",
            )
            for side in ("left", "right")
        }
        for row in ratings["ratings"]:
            values = row["ratings"]
            if set(values) != fields | {"overall_preference"}:
                raise ValueError("Ratings fields are incomplete")
            if values["overall_preference"] not in ("left", "right", "tie"):
                raise ValueError("Invalid overall preference")
            if any(str(values[field]) not in {"1", "2", "3", "4", "5"} for field in fields):
                raise ValueError("Ratings must be 1–5")
        joined = [{**row, "mapping": by_pair[row["pair_id"]]} for row in ratings["ratings"]]
    else:
        raise ValueError("Unsupported ratings schema")
    record = {"schema_version": ratings["schema_version"], "ratings": joined}
    if ratings["schema_version"] == 2:
        run = store.manifest()
        record["models"] = {
            arm: run[f"{arm}_config"]["requested_model"] for arm in ("baseline", "candidate")
        }
        counts = Counter(row["preference"] for row in joined)
        record["preference_counts"] = {
            choice: counts[choice] for choice in ("baseline", "candidate", "tie")
        }
    target = store.directory / "revealed-ratings.json"
    target.write_text(json.dumps(record, indent=2) + "\n")
    return target
