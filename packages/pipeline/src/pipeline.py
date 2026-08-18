"""Main pipeline orchestrator for Sunday Album processing."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from src.preprocessing.loader import ImageMetadata, load_image
from src.page_detection.detector import PageDetection
from src.glare.detector import GlareDetection
from src.glare.remover_single import GlareResult
from src.photo_detection.detector import PhotoDetection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline step registry (used by CLI `status` command)
# ---------------------------------------------------------------------------

PIPELINE_STEPS = [
    {
        'id': 'load',
        'name': 'Load Image',
        'description': 'Load HEIC, DNG, JPEG, or PNG image with format detection',
        'priority': 1,
        'implemented': True,
    },
    {
        'id': 'normalize',
        'name': 'Normalize & Preprocess',
        'description': 'Resize, apply EXIF orientation, generate working copy',
        'priority': 1,
        'implemented': True,
    },
    {
        'id': 'page_detect',
        'name': 'Page Detection',
        'description': 'Detect album page boundaries and apply perspective correction',
        'priority': 3,
        'implemented': True,
    },
    {
        'id': 'glare_detect',
        'name': 'Glare Detection & Removal',
        'description': 'Detect and remove glare — OpenAI gpt-image-1.5 by default, OpenCV inpainting fallback',
        'priority': 1,
        'implemented': True,
    },
    {
        'id': 'ai_orientation',
        'name': 'AI Orientation Correction',
        'description': 'Claude Haiku call per photo — corrects 90°/180°/270° rotation errors and produces scene description',
        'priority': 2,
        'implemented': True,
    },
    {
        'id': 'photo_detect',
        'name': 'Photo Detection',
        'description': 'Detect individual photo boundaries on album pages',
        'priority': 2,
        'implemented': True,
    },
    {
        'id': 'photo_split',
        'name': 'Photo Splitting',
        'description': 'Extract individual photos as separate images',
        'priority': 2,
        'implemented': True,
    },
    {
        'id': 'keystone_correct',
        'name': 'Keystone Correction',
        'description': 'Per-photo perspective correction for tilted shots',
        'priority': 3,
        'implemented': True,
    },
    {
        'id': 'dewarp',
        'name': 'Dewarping',
        'description': 'Correct bulge/curvature from bowed photo surfaces',
        'priority': 3,
        'implemented': True,
    },
    {
        'id': 'rotation_correct',
        'name': 'Rotation Correction',
        'description': 'Auto-detect and correct rotation angle',
        'priority': 3,
        'implemented': True,
    },
    {
        'id': 'white_balance',
        'name': 'White Balance',
        'description': 'Auto white balance correction',
        'priority': 4,
        'implemented': True,
    },
    {
        'id': 'color_restore',
        'name': 'Color Restoration',
        'description': 'Adaptive brightness lift (white-point stretch + shadow lift) and vibrance saturation boost',
        'priority': 4,
        'implemented': True,
    },
    {
        'id': 'deyellow',
        'name': 'Deyellowing',
        'description': 'Remove yellowing from aged photos',
        'priority': 4,
        'implemented': True,
    },
    {
        'id': 'sharpen',
        'name': 'Sharpening',
        'description': 'Unsharp mask and final enhancement',
        'priority': 4,
        'implemented': True,
    },
]


def get_step_status(step_id: str) -> dict:
    """Return implementation status for a pipeline step.

    Args:
        step_id: Step identifier (e.g. ``'load'``, ``'glare_detect'``).

    Returns:
        Dict with ``'implemented'`` (bool) and optional ``'notes'`` (str).
    """
    for step in PIPELINE_STEPS:
        if step['id'] == step_id:
            return {'implemented': step['implemented'], 'notes': step.get('notes', '')}
    return {'implemented': False, 'notes': 'Unknown step'}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """All tunable parameters in one place."""

    # Preprocessing
    max_working_resolution: int = 4000  # px, longest edge
    prefer_heic_for_iteration: bool = True

    # Page detection (GrabCut)
    page_detect_min_area_ratio: float = 0.3
    page_detect_grabcut_iterations: int = 5
    page_detect_grabcut_max_dimension: int = 800

    # Glare detection — OpenCV fallback path only
    glare_intensity_threshold: float = 0.85
    glare_saturation_threshold: float = 0.15
    glare_min_area: int = 100
    glare_inpaint_radius: int = 5
    glare_feather_radius: int = 5
    glare_type: str = "auto"  # "auto", "sleeve", or "print"

    # Photo detection
    photo_detect_method: str = "contour"  # "contour", "yolo", or "claude"
    photo_detect_min_area_ratio: float = 0.02
    photo_detect_max_count: int = 8

    # Geometry
    keystone_max_angle: float = 40.0
    rotation_auto_correct_max: float = 15.0
    dewarp_detection_threshold: float = 0.02
    use_dewarp: bool = False

    # Color — brightness lift + vibrance (see src/color/restore.py)
    color_restore_wp_percentile: float = 99.0   # white-point percentile for stretch
    color_restore_wp_target: float = 0.96       # target brightness after stretch
    color_restore_shadow_lift_max: float = 0.15 # max lift applied to darkest pixels
    color_restore_brightness_ceiling: float = 0.75  # scale back if mean lum exceeds this
    color_restore_vibrance_boost: float = 0.25  # base per-pixel saturation boost
    sharpen_radius: float = 1.5
    sharpen_amount: float = 0.5

    # Output
    output_format: str = "jpeg"
    jpeg_quality: int = 92

    # AI (legacy flags, not in active pipeline)
    use_ai_quality_check: bool = False
    use_ai_fallback_detection: bool = False
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # Photo detection override — when set, photo_detect writes these directly to
    # the detection JSON and skips contour detection entirely.  Each dict must have
    # at minimum a ``bbox`` key ([x1, y1, x2, y2] in page-image pixel coordinates).
    forced_detections: Optional[list[dict]] = None

    # AI orientation correction — Claude Haiku, one call per photo
    use_ai_orientation: bool = True
    ai_orientation_model: str = "claude-haiku-4-5-20251001"
    ai_orientation_min_confidence: str = "medium"
    # When set, skip the AI call and apply this exact clockwise rotation (0/90/180/270°)
    forced_rotation_degrees: Optional[int] = None

    # OpenAI glare removal (default)
    use_openai_glare_removal: bool = True
    openai_model: str = "gpt-image-1.5"
    openai_glare_quality: str = "high"
    openai_glare_input_fidelity: str = "high"
    forced_scene_description: Optional[str] = None

    # API keys — passed explicitly so steps are pure functions with no env-var reads.
    # Set by the caller (CLI, Lambda handler, macOS bridge) before running the pipeline.
    # Empty string means "not provided" — steps will skip or fall back as configured.
    anthropic_api_key: str = ""
    openai_api_key: str = ""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Result of pipeline processing."""

    output_images: List[np.ndarray]
    metadata: ImageMetadata
    processing_time: float
    steps_completed: List[str]
    page_detection: Optional[PageDetection] = None
    glare_detection: Optional[GlareDetection] = None
    glare_confidence: Optional[float] = None
    glare_removal: Optional[GlareResult] = None
    photo_detections: Optional[List[PhotoDetection]] = None
    num_photos_extracted: int = 0


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """Main processing pipeline for album page digitisation.

    Uses a pluggable :class:`~src.storage.backend.StorageBackend` for all
    image I/O so the same step logic runs locally (LocalStorage) and in AWS
    Lambda (S3Storage, added in Phase 2).

    The pipeline is constructed with an optional *storage* argument.  When
    called from the CLI, :class:`~src.storage.local.LocalStorage` is passed
    in so the existing ``--output`` / ``--debug-dir`` flags continue to work.
    When *storage* is ``None`` a temporary LocalStorage rooted at the current
    working directory is used (backwards-compatible default).
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        storage: Optional[object] = None,
    ) -> None:
        """Initialise pipeline.

        Args:
            config: Pipeline configuration.  Defaults to ``PipelineConfig()``.
            storage: StorageBackend instance.  If ``None``, a default
                     LocalStorage rooted at ``"."`` is created at
                     process-time (so ``--output`` / ``--debug-dir`` can
                     still be overridden per-file via :meth:`process`).
        """
        self.config = config or PipelineConfig()
        self._default_storage = storage
        self.step_times: dict = {}

    def process(
        self,
        input_path: str,
        debug_output_dir: Optional[str] = None,
        steps_filter: Optional[List[str]] = None,
        storage: Optional[object] = None,
    ) -> "PipelineResult":
        """Process a single image through the pipeline.

        Args:
            input_path: Path to input image file.
            debug_output_dir: Directory for debug images.  When provided, a
                              ``LocalStorage`` with this as its ``debug_dir``
                              is created unless *storage* is also passed.
            steps_filter: Optional list of step IDs to run (skips all others).
            storage: Override the instance-level storage backend for this call.

        Returns:
            :class:`PipelineResult` with processed images and metadata.
        """
        from src.storage.local import LocalStorage
        import src.steps.load as _load
        import src.steps.normalize as _normalize
        import src.steps.page_detect as _page_detect
        import src.steps.perspective as _perspective
        import src.steps.photo_detect as _photo_detect
        import src.steps.photo_split as _photo_split
        import src.steps.ai_orient as _ai_orient
        import src.steps.glare_remove as _glare_remove
        import src.steps.geometry as _geometry
        import src.steps.color_restore as _color_restore

        start_time = time.time()
        steps_completed: List[str] = []
        input_file = Path(input_path)
        stem = input_file.stem

        # Resolve storage backend ----------------------------------------
        active_storage = (
            storage
            or self._default_storage
            or LocalStorage(
                base_dir=Path("."),
                debug_dir=Path(debug_output_dir) if debug_output_dir else None,
            )
        )

        # Upload source file into storage ---------------------------------
        active_storage.put_file(input_path, f"uploads/{input_file.name}")

        logger.info("Processing: %s (stem=%s)", input_path, stem)

        # Load original image for metadata (needed for PipelineResult) ----
        _, metadata = load_image(input_path)

        # ------------------------------------------------------------------
        # Step 1: load
        # ------------------------------------------------------------------
        if steps_filter is None or 'load' in steps_filter:
            step_start = time.time()
            _load.run(active_storage, stem, self.config)
            self.step_times['load'] = time.time() - step_start
            steps_completed.append('load')
            logger.info("load: %.3fs", self.step_times['load'])

        # ------------------------------------------------------------------
        # Step 2: normalize
        # ------------------------------------------------------------------
        if steps_filter is None or 'normalize' in steps_filter:
            step_start = time.time()
            _normalize.run(active_storage, stem, self.config)
            self.step_times['normalize'] = time.time() - step_start
            steps_completed.append('normalize')
            logger.info("normalize: %.3fs", self.step_times['normalize'])

        # ------------------------------------------------------------------
        # Step 3a: page_detect
        # ------------------------------------------------------------------
        should_run_page = steps_filter is None or 'page_detect' in steps_filter
        if should_run_page:
            step_start = time.time()
            try:
                _page_detect.run(active_storage, stem, self.config)
                self.step_times['page_detect'] = time.time() - step_start
                steps_completed.append('page_detect')
                logger.info("page_detect: %.3fs", self.step_times['page_detect'])
            except Exception as exc:
                logger.warning("page_detect failed, attempting graceful fallback: %s", exc)
                # Write a minimal fallback JSON so downstream steps don't break
                import json
                from src.preprocessing.normalizer import normalize as _norm
                _fallback_img = active_storage.read_image(f"debug/{stem}_02_normalized.jpg")
                h, w = _fallback_img.shape[:2]
                _fallback_corners = [[0, 0], [w, 0], [w, h], [0, h]]
                active_storage.write_json(f"debug/{stem}_03_page_detection.json", {
                    "confidence": 0.0,
                    "is_full_frame": True,
                    "corners": _fallback_corners,
                    "photo_quads": [],
                })
                active_storage.write_image(
                    f"debug/{stem}_02_page_detected.jpg",
                    _fallback_img,
                    format="jpeg",
                    quality=90,
                )
                self.step_times['page_detect'] = time.time() - step_start

        # ------------------------------------------------------------------
        # Step 3b: perspective
        # ------------------------------------------------------------------
        if steps_filter is None or 'page_detect' in steps_filter:
            step_start = time.time()
            try:
                perspective_result = _perspective.run(active_storage, stem, self.config)
                self.step_times['perspective'] = time.time() - step_start
                steps_completed.append('perspective')
            except Exception as exc:
                logger.warning("perspective failed, passing through: %s", exc)
                # Copy normalised image as the warped image
                _norm_img = active_storage.read_image(f"debug/{stem}_02_normalized.jpg")
                active_storage.write_image(
                    f"debug/{stem}_03_page_warped.jpg", _norm_img, format="jpeg", quality=95
                )
                perspective_result = {"warped": False, "multi_blob": False, "blob_count": 0}
                self.step_times['perspective'] = time.time() - step_start
        else:
            perspective_result = {"warped": False, "multi_blob": False, "blob_count": 0}

        # ------------------------------------------------------------------
        # Step 4: photo_detect
        # ------------------------------------------------------------------
        # photo_split can be run independently (to re-use existing detection JSON)
        # by including 'photo_split' in steps_filter without 'photo_detect'.
        should_run_photo_detect = steps_filter is None or 'photo_detect' in steps_filter
        should_run_photo_split = (
            steps_filter is None
            or 'photo_detect' in steps_filter
            or 'photo_split' in steps_filter
        )
        if should_run_photo_detect:
            step_start = time.time()
            try:
                photo_detect_result = _photo_detect.run(active_storage, stem, self.config)
                self.step_times['photo_detect'] = time.time() - step_start
                steps_completed.append('photo_detect')
                logger.info(
                    "photo_detect: %.3fs, %d photo(s)",
                    self.step_times['photo_detect'],
                    photo_detect_result.get("photo_count", 0),
                )
            except Exception as exc:
                logger.warning("photo_detect failed, passing through: %s", exc)
                photo_detect_result = {"photo_count": 0, "multi_blob": False, "detections": []}
                active_storage.write_json(f"debug/{stem}_05_photo_detections.json", photo_detect_result)
                self.step_times['photo_detect'] = time.time() - step_start
        else:
            photo_detect_result = {"photo_count": 0, "multi_blob": False, "detections": []}

        # ------------------------------------------------------------------
        # Step 4b: photo_split
        # ------------------------------------------------------------------
        if should_run_photo_split:
            step_start = time.time()
            try:
                split_result = _photo_split.run(active_storage, stem, self.config)
                photo_count = split_result["photo_count"]
                self.step_times['photo_split'] = time.time() - step_start
                steps_completed.append('photo_split')
                logger.info("photo_split: %.3fs, %d photo(s)", self.step_times['photo_split'], photo_count)
            except Exception as exc:
                logger.warning("photo_split failed, using full page: %s", exc)
                page_img = active_storage.read_image(f"debug/{stem}_03_page_warped.jpg")
                active_storage.write_image(
                    f"debug/{stem}_05_photo_01_raw.jpg", page_img, format="jpeg", quality=95
                )
                photo_count = 1
                self.step_times['photo_split'] = time.time() - step_start
        else:
            # When steps_filter skips all photo steps, assume 1 photo (full page)
            photo_count = 1
            if not active_storage.exists(f"debug/{stem}_05_photo_01_raw.jpg"):
                page_img = active_storage.read_image(f"debug/{stem}_03_page_warped.jpg")
                active_storage.write_image(
                    f"debug/{stem}_05_photo_01_raw.jpg", page_img, format="jpeg", quality=95
                )

        # ------------------------------------------------------------------
        # Per-photo steps (4.5 → 7): ai_orient, glare, geometry, color
        # ------------------------------------------------------------------
        should_run_orient = (
            self.config.use_ai_orientation
            and (steps_filter is None or 'ai_orientation' in steps_filter)
        )
        should_run_glare = steps_filter is None or 'glare_detect' in steps_filter
        should_run_geom = steps_filter is None or any(
            s in steps_filter for s in ('keystone_correct', 'rotation_correct', 'dewarp')
        )
        should_run_color = steps_filter is None or any(
            s in steps_filter for s in ('white_balance', 'deyellow', 'color_restore', 'sharpen')
        )

        for photo_idx in range(1, photo_count + 1):
            idx_str = f"{photo_idx:02d}"
            logger.info("--- Photo %d/%d ---", photo_idx, photo_count)

            # Step 4.5: AI orientation
            if should_run_orient:
                step_start = time.time()
                try:
                    _ai_orient.run(active_storage, stem, self.config, photo_index=photo_idx)
                    self.step_times[f'ai_orient_{photo_idx}'] = time.time() - step_start
                    if photo_idx == 1:
                        steps_completed.append('ai_orientation')
                        logger.info("ai_orient: %.3fs", self.step_times[f'ai_orient_{photo_idx}'])
                except Exception as exc:
                    logger.warning("ai_orient[%d] failed: %s", photo_idx, exc)
                    _raw = active_storage.read_image(f"debug/{stem}_05_photo_{idx_str}_raw.jpg")
                    active_storage.write_image(
                        f"debug/{stem}_05b_photo_{idx_str}_oriented.jpg", _raw, format="jpeg", quality=95
                    )
            else:
                # Copy raw → oriented so the glare step finds its input
                if not active_storage.exists(f"debug/{stem}_05b_photo_{idx_str}_oriented.jpg"):
                    _raw = active_storage.read_image(f"debug/{stem}_05_photo_{idx_str}_raw.jpg")
                    active_storage.write_image(
                        f"debug/{stem}_05b_photo_{idx_str}_oriented.jpg", _raw, format="jpeg", quality=95
                    )
                active_storage.write_json(f"debug/{stem}_05b_photo_{idx_str}_analysis.json", {
                    "rotation_degrees": 0,
                    "flip_horizontal": False,
                    "orientation_confidence": "skipped",
                    "scene_description": "",
                })

            # Step 5: Glare removal
            if should_run_glare:
                step_start = time.time()
                try:
                    _glare_remove.run(active_storage, stem, self.config, photo_index=photo_idx)
                    self.step_times[f'glare_{photo_idx}'] = time.time() - step_start
                    if photo_idx == 1:
                        steps_completed.append('glare_detect')
                        logger.info("glare: %.3fs", self.step_times[f'glare_{photo_idx}'])
                except Exception as exc:
                    logger.warning("glare_remove[%d] failed: %s", photo_idx, exc)
                    _oriented = active_storage.read_image(
                        f"debug/{stem}_05b_photo_{idx_str}_oriented.jpg"
                    )
                    active_storage.write_image(
                        f"debug/{stem}_07_photo_{idx_str}_deglared.jpg",
                        _oriented,
                        format="jpeg",
                        quality=95,
                    )
            else:
                if not active_storage.exists(f"debug/{stem}_07_photo_{idx_str}_deglared.jpg"):
                    _oriented = active_storage.read_image(
                        f"debug/{stem}_05b_photo_{idx_str}_oriented.jpg"
                    )
                    active_storage.write_image(
                        f"debug/{stem}_07_photo_{idx_str}_deglared.jpg",
                        _oriented,
                        format="jpeg",
                        quality=95,
                    )

            # Step 6: Geometry
            if should_run_geom:
                step_start = time.time()
                try:
                    _geometry.run(active_storage, stem, self.config, photo_index=photo_idx)
                    self.step_times[f'geometry_{photo_idx}'] = time.time() - step_start
                    if photo_idx == 1:
                        steps_completed.append('geometry')
                        logger.info("geometry: %.3fs", self.step_times[f'geometry_{photo_idx}'])
                except Exception as exc:
                    logger.warning("geometry[%d] failed: %s", photo_idx, exc)
                    _deglared = active_storage.read_image(
                        f"debug/{stem}_07_photo_{idx_str}_deglared.jpg"
                    )
                    active_storage.write_image(
                        f"debug/{stem}_10_photo_{idx_str}_geometry_final.jpg",
                        _deglared,
                        format="jpeg",
                        quality=95,
                    )
            else:
                if not active_storage.exists(f"debug/{stem}_10_photo_{idx_str}_geometry_final.jpg"):
                    _deglared = active_storage.read_image(
                        f"debug/{stem}_07_photo_{idx_str}_deglared.jpg"
                    )
                    active_storage.write_image(
                        f"debug/{stem}_10_photo_{idx_str}_geometry_final.jpg",
                        _deglared,
                        format="jpeg",
                        quality=95,
                    )

            # Step 7: Color restoration
            if should_run_color:
                step_start = time.time()
                try:
                    _color_restore.run(active_storage, stem, self.config, photo_index=photo_idx)
                    self.step_times[f'color_{photo_idx}'] = time.time() - step_start
                    if photo_idx == 1:
                        steps_completed.append('color_restoration')
                        logger.info("color_restore: %.3fs", self.step_times[f'color_{photo_idx}'])
                except Exception as exc:
                    logger.warning("color_restore[%d] failed: %s", photo_idx, exc)
                    _geom = active_storage.read_image(
                        f"debug/{stem}_10_photo_{idx_str}_geometry_final.jpg"
                    )
                    out_key = f"output/SundayAlbum_{stem}_Photo{idx_str}.jpg"
                    active_storage.write_image(out_key, _geom, format="jpeg", quality=self.config.jpeg_quality)
            else:
                _geom = active_storage.read_image(
                    f"debug/{stem}_10_photo_{idx_str}_geometry_final.jpg"
                )
                out_key = f"output/SundayAlbum_{stem}_Photo{idx_str}.jpg"
                if not active_storage.exists(out_key):
                    active_storage.write_image(out_key, _geom, format="jpeg", quality=self.config.jpeg_quality)

        # ------------------------------------------------------------------
        # Collect output images
        # ------------------------------------------------------------------
        output_images: List[np.ndarray] = []
        for photo_idx in range(1, photo_count + 1):
            idx_str = f"{photo_idx:02d}"
            out_key = f"output/SundayAlbum_{stem}_Photo{idx_str}.jpg"
            if active_storage.exists(out_key):
                output_images.append(active_storage.read_image(out_key))
            else:
                logger.warning("Output image not found: %s", out_key)

        total_time = time.time() - start_time
        logger.info("Total processing time: %.3fs", total_time)

        return PipelineResult(
            output_images=output_images,
            metadata=metadata,
            processing_time=total_time,
            steps_completed=steps_completed,
            num_photos_extracted=photo_count,
        )

    def process_batch(
        self,
        input_paths: List[str],
        debug_output_dir: Optional[str] = None,
        steps_filter: Optional[List[str]] = None,
    ) -> List["PipelineResult"]:
        """Process multiple images through the pipeline.

        Args:
            input_paths: List of image file paths.
            debug_output_dir: Optional directory for debug output.
            steps_filter: Optional list of step IDs to run.

        Returns:
            List of :class:`PipelineResult` objects.
        """
        results = []
        for i, path in enumerate(input_paths, 1):
            logger.info("Processing %d/%d: %s", i, len(input_paths), path)
            try:
                result = self.process(
                    path,
                    debug_output_dir=debug_output_dir,
                    steps_filter=steps_filter,
                )
                results.append(result)
            except Exception as exc:
                logger.error("Error processing %s: %s", path, exc, exc_info=True)
        return results
