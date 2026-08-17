# Sunday Album — Pipeline Steps Reference

**Last updated:** 2026-04-12  
**See also:** `docs/SYSTEM_ARCHITECTURE.md` for the overall architecture and execution model.

Each step is a pure function: `run(storage, stem, config, photo_index?) → dict`.  
Steps read input from `StorageBackend` and write output back to it — no side effects, no env var reads.

---

## Table of Contents

1. [load](#1-load)
2. [normalize](#2-normalize)
3. [page_detect](#3-page_detect)
4. [perspective](#4-perspective)
5. [photo_detect + photo_split](#5-photo_detect--photo_split)
6. [ai_orient](#6-ai_orient)
7. [glare_remove](#7-glare_remove)
8. [geometry](#8-geometry)
9. [color_restore](#9-color_restore)
10. [finalize](#10-finalize)

---

## 1. load

**Handler:** `sa-pipeline-load` | **RAM:** 3008 MB | **Source:** `packages/pipeline/src/steps/load.py`

### What it does
Reads the uploaded image from storage, decodes it based on format, applies EXIF orientation,
and produces a float32 RGB array normalized to [0, 1].

### Format handling
| Format | Library | Notes |
|--------|---------|-------|
| `.heic` / `.heif` | `pillow-heif` + Pillow | Must call `register_heif_opener()` before `Image.open()` |
| `.dng` / `.cr2` / `.nef` | `rawpy` | Demosaics with camera WB, sRGB output, 16-bit; divides by 65535 |
| `.jpg` / `.png` / `.tiff` | Pillow | Standard |

DNG from iPhone 17 Pro ProRAW is 48 MP (~8064×6048). HEIC is 24 MP. Both are supported;
HEIC is recommended for iteration speed.

### Output
- Writes `debug/{stem}_01_loaded.jpg` and its 400px thumbnail to storage
- Returns image shape, format, bit depth in result dict

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| _(none — load is format-driven)_ | | |

---

## 2. normalize

**Handler:** `sa-pipeline-normalize` | **Source:** `packages/pipeline/src/steps/normalize.py`

### What it does
Resizes the loaded image to a working resolution (capped at 4000px on the longest edge,
preserving aspect ratio). Also generates a 400px thumbnail for UI previews.

Uses `INTER_AREA` for downscaling (best quality for shrinking).

### Output
- Writes `debug/{stem}_02_normalized.jpg` and thumbnail

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `max_working_resolution` | `4000` | Longest edge cap in pixels. Lower = faster, less detail |

---

## 3. page_detect

**Handler:** `sa-pipeline-page-detect` | **Source:** `packages/pipeline/src/steps/page_detect.py` → `packages/pipeline/src/page_detection/detector.py`

### What it does
Finds the boundary of the album page (or individual print) within the image frame.
Returns a quadrilateral (4 corner points) for the perspective step.

### Algorithm
Uses GrabCut segmentation on a downscaled copy (max 800px) to separate the subject from the
background. Extracts the largest quadrilateral from the segmentation mask contour.

If no clear quadrilateral is found (confidence below threshold), sets `is_full_frame=True`
and returns the full image bounds — the perspective step becomes a no-op.

### Output
- Writes `debug/{stem}_02_page_detected.jpg` (corners overlaid) and thumbnail
- Writes `debug/{stem}_03_page_detection.json` (corners, confidence, `is_full_frame` flag)

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `page_detect_min_area_ratio` | `0.3` | Minimum fraction of image area the detected page must occupy |
| `page_detect_grabcut_iterations` | `5` | GrabCut iterations; more = slower but more accurate |
| `page_detect_grabcut_max_dimension` | `800` | Downscale limit for GrabCut; lower = faster |

---

## 4. perspective

**Handler:** `sa-pipeline-perspective` | **Source:** `packages/pipeline/src/steps/perspective.py` → `packages/pipeline/src/page_detection/perspective.py`

### What it does
Applies a homographic (perspective) transform using the corners from `page_detect`, producing
a fronto-parallel (undistorted, rectangular) view of the album page.

If `is_full_frame=True` from the previous step, this step is a pass-through.

Output dimensions are computed from the corner distances to preserve the original aspect ratio.
Uses `cv2.warpPerspective` with `INTER_CUBIC` for quality.

### Output
- Writes `debug/{stem}_03_page_warped.jpg` and thumbnail (only if transform was applied)

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `keystone_max_angle` | `40.0` | Maximum perspective angle (degrees) to attempt correction |

---

## 5. photo_detect + photo_split

**Handlers:** `sa-pipeline-photo-detect`, `sa-pipeline-photo-split`  
**Source:** `packages/pipeline/src/steps/photo_detect.py`, `packages/pipeline/src/steps/photo_split.py` → `packages/pipeline/src/photo_detection/`

### What it does
`photo_detect`: Finds individual photo boundaries within the (now fronto-parallel) album page.  
`photo_split`: Extracts each photo as its own perspective-corrected crop.

### Algorithm (photo_detect)
Adaptive Gaussian thresholding with a large block size (101px) to find region boundaries at
the photo level, ignoring texture within photos. Morphological open/close to clean regions.
Fallback: if initial threshold fails, inverts and retries.

Regions are filtered by:
- Minimum area ratio: 2% of page area
- Maximum aspect ratio: 6.0 (rejects thin strips)
- Vertex count: 4–12 (rejects non-rectangular noise)
- Decoration filter: removes regions smaller than 35% of the largest detected photo
  (50% threshold when >3 photos detected)

For single prints (cave, harbor, skydiving): detects the full frame as 1 photo.  
For album pages (three_pics, two_pics): detects 2–3 individual photos.  
Spine-separated album pages (photos divided by a visible spine): handled via projection-profile
fallback when contour detection produces disproportionate splits.

### Algorithm (photo_split)
For each detected region, computes a homography from the detected corner quadrilateral to a
rectangular output, then crops via `cv2.warpPerspective`.

### Forced-detection override
When automatic detection produces wrong results, you can bypass contour detection entirely
by providing explicit photo boundaries via `config.forced_detections`.

Each detection object supports two boundary formats:
- **`bbox`** — axis-aligned bounding box `[x1, y1, x2, y2]` (pixel coordinates)
- **`corners`** — free-form quadrilateral `[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]` (TL, TR, BR, BL).
  Use this when photos are rotated or keystoned; `photo_split` applies a full homographic warp
  (`cv2.getPerspectiveTransform` + `cv2.warpPerspective`) to straighten the quad to a rectangle.

If both keys are present, `corners` takes precedence. If only `bbox` is provided, axis-aligned
corners are derived from it automatically.

**CLI:** pass a JSON array of detection objects:
```bash
# Axis-aligned bbox
python -m src.cli process image.HEIC --output ./output/ \
  --forced-detections '[{"bbox":[50,80,900,700],"confidence":1.0,"region_type":"photo","orientation":"unknown"}]'

# Free-form quad (keystoned photo)
python -m src.cli process image.HEIC --output ./output/ \
  --forced-detections '[{"bbox":[50,80,900,700],"corners":[[55,85],[895,78],[905,698],[48,705]],"confidence":1.0,"region_type":"photo","orientation":"unknown"}]'
```

**Web UI:** on the Photo Split step detail, drag any of the 4 corner handles freely to form
a non-rectangular quad (useful for keystoned or rotated prints), draw new regions, or delete
unwanted ones, then click "Confirm & Re-run". The editor seeds from `05_photo_detections.json`
and posts both `bbox` and `corners` as `forced_detections`.

**macOS app:** same interactive boundary editor — each region starts as a rectangle but any
corner handle can be dragged independently to form a free-form quad.

When `forced_detections` is set, the step skips contour detection entirely, writes the
provided boundaries to `05_photo_detections.json`, and redraws the `04_photo_boundaries.jpg`
overlay from scratch.

### Output
- `photo_detect` writes `debug/{stem}_04_photo_boundaries.jpg` (bounding boxes overlaid)
- `photo_detect` writes `debug/{stem}_05_photo_detections.json` (detection list; exposed as
  the `05_photo_detections_json` debug URL so the interactive editors can seed from it)
- `photo_split` writes `debug/{stem}_05_photo_NN_raw.jpg` per extracted photo and thumbnails

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `photo_detect_method` | `"contour"` | Detection method: `"contour"`, `"yolo"`, `"claude"` (only contour is active) |
| `photo_detect_min_area_ratio` | `0.02` | Minimum photo area as fraction of page; increase to suppress small false positives |
| `photo_detect_max_count` | `8` | Maximum photos to detect per page |
| `forced_detections` | `None` | List of `{bbox, corners, confidence, region_type, orientation}` dicts; bypasses contour detection when set. `corners` is optional — if present (4×[x,y] TL→TR→BR→BL), a full homographic warp is used; otherwise axis-aligned crop from `bbox`. |

---

## 6. ai_orient

**Handler:** `sa-pipeline-ai-orient` | **Source:** `packages/pipeline/src/steps/ai_orient.py` → `packages/pipeline/src/ai/claude_vision.py`

### What it does
Detects gross orientation errors (multiples of 90°) in each extracted photo — prints are
frequently inserted sideways or upside-down in album sleeves. Corrects before glare removal
so the OpenAI model receives a semantically upright image (critical for selecting the right
output dimensions and for quality of inpainting).

One Claude Haiku API call per photo. Returns:
- `rotation_degrees`: clockwise rotation to apply (0 / 90 / 180 / 270)
- `flip_horizontal`: bool (rare; for mirror-inserted prints)
- `scene_description`: one-sentence description passed to the glare step

The prompt uses explicit spatial language ("rotate 90° clockwise: the left edge becomes the
new top") to help the model reason about direction rather than guessing.

### Skipped when
- `config.anthropic_api_key` is empty → photo passed through unchanged, no scene description
- Model returns confidence below `ai_orientation_min_confidence` threshold

### Output
- Writes `debug/{stem}_05b_photo_NN_oriented.jpg` and thumbnail
- Writes `debug/{stem}_05b_photo_NN_analysis.json` (rotation, flip, scene description, confidence)

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `use_ai_orientation` | `True` | Disable to skip this step entirely |
| `ai_orientation_model` | `"claude-haiku-4-5-20251001"` | Claude model for orientation; Haiku for cost/speed |
| `ai_orientation_min_confidence` | `"medium"` | Ignores `"low"` confidence results; pass-through instead |

---

## 7. glare_remove

**Handler:** `sa-pipeline-glare-remove` | **Timeout:** 300s | **Source:** `packages/pipeline/src/steps/glare_remove.py`

### What it does
Removes glare from each extracted photo. Two paths:

**Default path (OpenAI `gpt-image-1.5`):**  
Sends the oriented photo + scene description to OpenAI `images.edit`. The model performs
semantic, diffusion-based inpainting with scene understanding — it knows what should be there
and reconstructs it. Output is at most 1536×1024 (resolution reduction accepted for quality).
The scene description from `ai_orient` is included in the prompt so the model understands
what it's restoring.

**Fallback path (OpenCV inpainting):**  
Used when `config.openai_api_key` is empty or `--no-openai-glare` is passed.
1. `detect_glare()`: HSV-based detection — glare = high V (brightness) + low S (saturation).
   Adaptive thresholding, morphological cleanup, local texture check to suppress false positives
   on bright photo content (sky, white shirts).
2. `remove_glare_single()`: Hybrid inpainting — intensity correction for mild glare,
   `cv2.inpaint` (TELEA/NS) for moderate, contextual fill for severe. Quality is significantly
   worse than the OpenAI path.

### Two glare types
| Type | Source | Appearance |
|------|--------|------------|
| Sleeve glare | Flat plastic sleeve over album page | Broad, flat patches; shifts with viewing angle |
| Print glare | Curved surface of glossy photo paper | Contoured highlights following print curvature |

OpenAI handles both well. OpenCV fallback works adequately only on sleeve glare.

### Output
- Writes `debug/{stem}_07_photo_NN_deglared.jpg` and thumbnail
- OpenCV path only: writes `debug/{stem}_06_photo_NN_glare_mask.png` and `_06_glare_overlay.jpg`

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `use_openai_glare_removal` | `True` | Set `False` to force OpenCV fallback |
| `openai_model` | `"gpt-image-1.5"` | OpenAI model for glare removal |
| `openai_glare_quality` | `"high"` | OpenAI image quality setting |
| `forced_scene_description` | `None` | Override Claude's scene description (CLI: `--scene-desc`) |
| `glare_intensity_threshold` | `0.85` | OpenCV path: V threshold for glare detection |
| `glare_saturation_threshold` | `0.15` | OpenCV path: S threshold (glare is desaturated) |
| `glare_min_area` | `100` | OpenCV path: minimum glare region size in pixels |
| `glare_inpaint_radius` | `5` | OpenCV path: inpainting radius |
| `glare_feather_radius` | `5` | OpenCV path: mask feathering to smooth edges |
| `glare_type` | `"auto"` | OpenCV path: `"auto"`, `"sleeve"`, or `"print"` |

---

## 8. geometry

**Handler:** `sa-pipeline-geometry` | **Source:** `packages/pipeline/src/steps/geometry.py` → `packages/pipeline/src/geometry/`

### What it does
Per-photo geometry corrections. Currently acts as a **near pass-through** — both active
sub-steps are disabled due to false positive rates on real photos.

### Sub-steps and current status

**Keystone correction** (`packages/pipeline/src/geometry/keystone.py`):  
Homographic correction for per-photo perspective distortion. Available but typically not
triggered at this stage since `photo_split` already applies a homography during extraction.

**Small-angle rotation** (`packages/pipeline/src/geometry/rotation.py`) — **DISABLED:**  
`_detect_small_rotation()` uses Hough line transform to find dominant lines and computes
their median angle. Fires on image content (boat rigging, rock edges, road lines) rather
than the photo frame. Returns `0.0` unconditionally. Intended replacement: detect the white
border of the physical print and use its angle.

**Dewarp** (`packages/pipeline/src/geometry/dewarp.py`) — **DISABLED:**  
`correct_warp()` detects barrel/pincushion distortion via Hough lines. Two problems:
(1) iPhone corrects lens distortion in-camera before writing HEIC, so there's nothing to
correct. (2) Hough detector fires on curved content (rock walls, roads).
Controlled by `use_dewarp: False` in config.

### Output
- Writes `debug/{stem}_10_photo_NN_geometry_final.jpg` only if a correction was applied

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `use_dewarp` | `False` | Enable barrel distortion correction (currently produces false positives) |
| `rotation_auto_correct_max` | `15.0` | Max small-angle rotation to correct (currently a no-op) |
| `dewarp_detection_threshold` | `0.02` | Minimum curvature to trigger dewarp |

---

## 9. color_restore

**Handler:** `sa-pipeline-color-restore` | **Source:** `packages/pipeline/src/steps/color_restore.py` → `packages/pipeline/src/color/`

### What it does
Four-stage color restoration chain applied to each photo:

**Stage 1 — White balance** (`packages/pipeline/src/color/white_balance.py`):  
Gray-world method: adjusts per-channel means so the average color is neutral. Skipped when
color-cast score is below 0.08 to protect intentionally warm/cool scenes.

**Stage 2 — Deyellowing** (`packages/pipeline/src/color/deyellow.py`):  
Converts to LAB color space. Analyzes the b* channel (blue–yellow axis) and applies an
adaptive shift toward neutral. Conservative: does not remove intentional warm tones (sunsets).

**Stage 3 — Fade restoration** (`packages/pipeline/src/color/restore.py`):  
3-stage adaptive algorithm (replaced CLAHE in April 2026 — CLAHE caused dimming and grain):

- *White-point stretch*: Scales so the 99th-percentile luminance reaches 0.96.
  Self-limiting: already-bright photos barely change. Never darkens (scale capped at min 1.0).

- *Shadow lift*: Quadratic tone curve lifts dark pixels proportionally.
  `lift = shadow_lift_max × (1 − luminance)²`
  Skipped entirely when mean luminance ≥ 0.60 (image is already bright; preserves dark scenes
  like caves and candlelit interiors).

- *Vibrance saturation*: Per-pixel saturation boost weighted by existing desaturation:
  `boost = vibrance_boost × (1 − S)`. Faded/muted pixels lift most; vivid colors are
  protected. Applied unconditionally — the weighting is inherently self-limiting.

- *Ceiling guard*: If mean luminance exceeds 0.75 after the above, scales back down.

**Stage 4 — Sharpening** (`packages/pipeline/src/color/enhance.py`):  
Unsharp mask on the L channel only (luminance sharpening, no color fringing).
No sigmoid contrast — contrast is handled by Stage 3.

### Output
- `debug/{stem}_11_photo_NN_wb.jpg` — after white balance
- `debug/{stem}_12_photo_NN_deyellow.jpg` — after deyellowing
- `debug/{stem}_13_photo_NN_restored.jpg` — after fade restoration
- `debug/{stem}_14_photo_NN_enhanced.jpg` — after sharpening (final output)

### Tunable params
| Param | Default | Effect |
|-------|---------|--------|
| `color_restore_wp_percentile` | `99.0` | Percentile used for white-point detection |
| `color_restore_wp_target` | `0.96` | Target luminance for white-point stretch |
| `color_restore_shadow_lift_max` | `0.15` | Max additive lift for dark pixels (0 = no shadow lift) |
| `color_restore_brightness_ceiling` | `0.75` | Scale back if mean luminance exceeds this |
| `color_restore_vibrance_boost` | `0.25` | Base per-pixel saturation boost (effective boost on vivid pixels is much lower) |
| `sharpen_radius` | `1.5` | Unsharp mask radius |
| `sharpen_amount` | `0.5` | Unsharp mask strength |

---

## 10. finalize

**Handler:** `sa-pipeline-finalize` | **RAM:** 1024 MB | **Source:** `services/handlers/finalize.py`

### What it does
Web/Lambda path only. Collects the `14_photo_NN_enhanced.jpg` output keys produced by
`color_restore`, copies them to `output/SundayAlbum_{stem}_PhotoNN.jpg`, updates the
DynamoDB job record to `status: complete` with `photo_count` and `output_keys`,
and sets `processing_time`.

If no output photos are found, sets `status: failed`.

The CLI path writes output files directly during `color_restore` and does not use this step.

### Output
- Final output files at `{user_hash}/output/SundayAlbum_{stem}_Photo01.jpg` etc.
- DynamoDB `sa-jobs` record updated to `complete`

---

## Debug output summary

All debug files use the pattern `debug/{stem}_{NN}_{description}.jpg`. For per-photo steps,
`photo_NN` is inserted: `debug/{stem}_07_photo_01_deglared.jpg`.

```
01_loaded           After format decode + EXIF orientation
02_normalized       After resize to working resolution
02_page_detected    Page boundary quad overlaid on image
03_page_warped      After perspective correction (only if correction applied)
04_photo_boundaries Detected photo bounding boxes overlaid
05_photo_detections.json  Detection results (bbox, confidence, region_type, orientation)
05_photo_NN_raw     Extracted photo before orientation
05b_photo_NN_oriented  After AI orientation correction
06_photo_NN_glare_mask  OpenCV path only: binary glare mask
07_photo_NN_deglared   After glare removal
10_photo_NN_geometry_final  After geometry correction (only if applied)
11_photo_NN_wb      After white balance
12_photo_NN_deyellow  After deyellowing
13_photo_NN_restored  After fade restoration
14_photo_NN_enhanced  After sharpening — final output
```
