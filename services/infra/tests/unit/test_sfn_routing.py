"""CDK template assertions: Step Functions skip-routing correctness.

These tests synthesize the CDK stack in-process and assert that every
Choice state has exactly the right StringEquals conditions. They catch
mistakes like a missing step name in skip_when(), a guard wired to the
wrong Pass state, or a step accidentally skipping itself.

Run from infra/:
    cd infra && ../.venv/bin/pytest tests/unit/test_sfn_routing.py -v
"""
from __future__ import annotations

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _skip_values(state: dict) -> set[str]:
    """Return the set of start_from values that trigger the skip branch."""
    choices = state["Choices"]
    assert len(choices) == 1, "Each guard should have exactly one Choices entry"
    choice = choices[0]
    if "Or" in choice:
        return {c["StringEquals"] for c in choice["Or"]}
    # Single condition (no Or wrapper)
    return {choice["StringEquals"]}


def _default_target(state: dict) -> str:
    return state["Default"]


def _skip_target(state: dict) -> str:
    return state["Choices"][0]["Next"]


# ── Step order constants (mirrors CDK skip_when() calls) ──────────────────────

# All reprocessable step names in pipeline order
PRE_SPLIT = ["load", "normalize", "page_detect", "perspective", "photo_detect", "photo_split"]
PER_PHOTO = ["ai_orient", "glare_remove", "geometry", "color_restore"]
ALL_STEPS = PRE_SPLIT + PER_PHOTO


# ── 1. Existence: all expected Choice states are present ─────────────────────


def test_pre_split_choice_states_exist(top_level_states):
    """All 6 pre-split Choice guards exist in the top-level state machine."""
    expected = {
        "SkipLoad?", "SkipNormalize?", "SkipPageDetect?",
        "SkipPerspective?", "SkipPhotoDetect?", "SkipPhotoSplit?",
    }
    actual = {n for n, s in top_level_states.items() if s["Type"] == "Choice"}
    assert expected == actual


def test_per_photo_choice_states_exist(per_photo_states):
    """All 3 per-photo Choice guards exist inside the ProcessPhotos Map."""
    expected = {"SkipAiOrient?", "SkipGlareRemove?", "SkipGeometry?"}
    actual = {n for n, s in per_photo_states.items() if s["Type"] == "Choice"}
    assert expected == actual


def test_color_restore_has_no_guard(per_photo_states):
    """ColorRestore is a Task with no preceding Choice guard (it's the terminal step)."""
    assert per_photo_states["ColorRestore"]["Type"] == "Task"
    assert "SkipColorRestore?" not in per_photo_states


# ── 2. Default / skip targets are wired correctly ────────────────────────────


@pytest.mark.parametrize("choice_name,task_name,pass_name", [
    ("SkipLoad?",        "Load",        "LoadSkipped"),
    ("SkipNormalize?",   "Normalize",   "NormalizeSkipped"),
    ("SkipPageDetect?",  "PageDetect",  "PageDetectSkipped"),
    ("SkipPerspective?", "Perspective", "PerspectiveSkipped"),
    ("SkipPhotoDetect?", "PhotoDetect", "PhotoDetectSkipped"),
    ("SkipPhotoSplit?",  "PhotoSplit",  "PhotoSplitSkipped"),
])
def test_pre_split_guard_wiring(top_level_states, choice_name, task_name, pass_name):
    """Each pre-split guard routes to the right Task (default) and Pass (skip)."""
    state = top_level_states[choice_name]
    assert _default_target(state) == task_name, f"{choice_name} default should be {task_name}"
    assert _skip_target(state) == pass_name, f"{choice_name} skip should go to {pass_name}"


@pytest.mark.parametrize("choice_name,task_name,pass_name", [
    ("SkipAiOrient?",    "AiOrient",    "AiOrientSkipped"),
    ("SkipGlareRemove?", "GlareRemove", "GlareRemoveSkipped"),
    ("SkipGeometry?",    "Geometry",    "GeometrySkipped"),
])
def test_per_photo_guard_wiring(per_photo_states, choice_name, task_name, pass_name):
    """Each per-photo guard routes to the right Task (default) and Pass (skip)."""
    state = per_photo_states[choice_name]
    assert _default_target(state) == task_name
    assert _skip_target(state) == pass_name


# ── 3. Each step does NOT skip itself ────────────────────────────────────────


@pytest.mark.parametrize("choice_name,own_step", [
    ("SkipLoad?",        "load"),
    ("SkipNormalize?",   "normalize"),
    ("SkipPageDetect?",  "page_detect"),
    ("SkipPerspective?", "perspective"),
    ("SkipPhotoDetect?", "photo_detect"),
    ("SkipPhotoSplit?",  "photo_split"),
])
def test_pre_split_step_does_not_skip_itself(top_level_states, choice_name, own_step):
    """A step's own name must not appear in its guard's skip conditions."""
    state = top_level_states[choice_name]
    assert own_step not in _skip_values(state), (
        f"{choice_name} incorrectly skips when start_from='{own_step}'"
    )


@pytest.mark.parametrize("choice_name,own_step", [
    ("SkipAiOrient?",    "ai_orient"),
    ("SkipGlareRemove?", "glare_remove"),
    ("SkipGeometry?",    "geometry"),
])
def test_per_photo_step_does_not_skip_itself(per_photo_states, choice_name, own_step):
    """A step's own name must not appear in its guard's skip conditions."""
    state = per_photo_states[choice_name]
    assert own_step not in _skip_values(state)


# ── 4. Skip conditions are exactly the right "later" steps ───────────────────


@pytest.mark.parametrize("choice_name,steps_that_must_skip", [
    # load is skipped when reprocessing from any later step
    ("SkipLoad?",
     {"normalize", "page_detect", "perspective", "photo_detect", "photo_split",
      "ai_orient", "glare_remove", "geometry", "color_restore"}),
    # normalize is skipped when reprocessing from page_detect onward
    ("SkipNormalize?",
     {"page_detect", "perspective", "photo_detect", "photo_split",
      "ai_orient", "glare_remove", "geometry", "color_restore"}),
    # page_detect is skipped from perspective onward
    ("SkipPageDetect?",
     {"perspective", "photo_detect", "photo_split",
      "ai_orient", "glare_remove", "geometry", "color_restore"}),
    # perspective is skipped from photo_detect onward
    ("SkipPerspective?",
     {"photo_detect", "photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"}),
    # photo_detect is skipped from photo_split onward
    ("SkipPhotoDetect?",
     {"photo_split", "ai_orient", "glare_remove", "geometry", "color_restore"}),
    # photo_split is skipped when reprocessing any per-photo step
    ("SkipPhotoSplit?",
     {"ai_orient", "glare_remove", "geometry", "color_restore"}),
])
def test_pre_split_skip_conditions_exact(top_level_states, choice_name, steps_that_must_skip):
    """Pre-split guard conditions match exactly the expected set of later steps."""
    actual = _skip_values(top_level_states[choice_name])
    assert actual == steps_that_must_skip, (
        f"{choice_name}: expected skip set {steps_that_must_skip}, got {actual}"
    )


@pytest.mark.parametrize("choice_name,steps_that_must_skip", [
    ("SkipAiOrient?",    {"glare_remove", "geometry", "color_restore"}),
    ("SkipGlareRemove?", {"geometry", "color_restore"}),
    ("SkipGeometry?",    {"color_restore"}),
])
def test_per_photo_skip_conditions_exact(per_photo_states, choice_name, steps_that_must_skip):
    """Per-photo guard conditions match exactly the expected set of later steps."""
    actual = _skip_values(per_photo_states[choice_name])
    assert actual == steps_that_must_skip


# ── 5. Boundary: reprocessing from step X skips all earlier guards ────────────


@pytest.mark.parametrize("start_from,should_skip,should_run", [
    # Reprocess from page_detect: skip load+normalize, run page_detect onward
    ("page_detect",
     {"SkipLoad?", "SkipNormalize?"},
     {"SkipPageDetect?", "SkipPerspective?", "SkipPhotoDetect?", "SkipPhotoSplit?"}),
    # Reprocess from photo_split: skip all 5 pre-split steps before it
    ("photo_split",
     {"SkipLoad?", "SkipNormalize?", "SkipPageDetect?", "SkipPerspective?", "SkipPhotoDetect?"},
     {"SkipPhotoSplit?"}),
    # Reprocess from ai_orient (per-photo): ALL pre-split guards skip
    ("ai_orient",
     {"SkipLoad?", "SkipNormalize?", "SkipPageDetect?", "SkipPerspective?",
      "SkipPhotoDetect?", "SkipPhotoSplit?"},
     set()),
])
def test_pre_split_boundary(top_level_states, start_from, should_skip, should_run):
    """For a given start_from, exactly the right pre-split guards fire."""
    for name in should_skip:
        assert start_from in _skip_values(top_level_states[name]), (
            f"start_from='{start_from}' should trigger {name} but doesn't"
        )
    for name in should_run:
        assert start_from not in _skip_values(top_level_states[name]), (
            f"start_from='{start_from}' should NOT trigger {name} but does"
        )


@pytest.mark.parametrize("start_from,should_skip,should_run", [
    # Reprocess from glare_remove: skip ai_orient, run glare_remove onward
    ("glare_remove",
     {"SkipAiOrient?"},
     {"SkipGlareRemove?", "SkipGeometry?"}),
    # Reprocess from color_restore: skip ai_orient + glare_remove + geometry
    ("color_restore",
     {"SkipAiOrient?", "SkipGlareRemove?", "SkipGeometry?"},
     set()),
    # Reprocess from ai_orient: no per-photo guards fire
    ("ai_orient",
     set(),
     {"SkipAiOrient?", "SkipGlareRemove?", "SkipGeometry?"}),
])
def test_per_photo_boundary(per_photo_states, start_from, should_skip, should_run):
    """For a given start_from, exactly the right per-photo guards fire."""
    for name in should_skip:
        assert start_from in _skip_values(per_photo_states[name]), (
            f"start_from='{start_from}' should trigger {name} but doesn't"
        )
    for name in should_run:
        assert start_from not in _skip_values(per_photo_states[name]), (
            f"start_from='{start_from}' should NOT trigger {name} but does"
        )


# ── 6. Pass states exist for every skipped step ───────────────────────────────


@pytest.mark.parametrize("pass_name", [
    "LoadSkipped", "NormalizeSkipped", "PageDetectSkipped",
    "PerspectiveSkipped", "PhotoDetectSkipped", "PhotoSplitSkipped",
])
def test_pre_split_pass_states_exist(top_level_states, pass_name):
    """All expected pre-split Pass (skipped) states are present."""
    assert pass_name in top_level_states
    assert top_level_states[pass_name]["Type"] == "Pass"


@pytest.mark.parametrize("pass_name", [
    "AiOrientSkipped", "GlareRemoveSkipped", "GeometrySkipped",
])
def test_per_photo_pass_states_exist(per_photo_states, pass_name):
    """All expected per-photo Pass (skipped) states are present."""
    assert pass_name in per_photo_states
    assert per_photo_states[pass_name]["Type"] == "Pass"
