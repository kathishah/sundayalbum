"""Pipeline step functions — thin, independently callable wrappers.

Each module exports a single ``run(storage, stem, config, photo_index)``
function that:

1. Reads its input from *storage* using the project key conventions.
2. Runs the processing logic.
3. Writes its output image(s) and/or JSON to *storage*.
4. Returns a metadata ``dict`` (never the raw image array).

Key conventions
---------------
``uploads/{stem}.{ext}``              — original uploaded file
``debug/{stem}_01_loaded.jpg``        — load step output
``debug/{stem}_02_normalized.jpg``    — normalize step output
``debug/{stem}_02_page_detected.jpg`` — page-detection overlay
``debug/{stem}_03_page_detection.json``
``debug/{stem}_03_page_warped.jpg``   — perspective-corrected image
``debug/{stem}_03b_blob_NN_extracted.jpg`` — multi-blob path
``debug/{stem}_04_photo_boundaries.jpg``
``debug/{stem}_05_photo_detections.json``
``debug/{stem}_05_photo_NN_raw.jpg``
``debug/{stem}_05b_photo_NN_oriented.jpg``
``debug/{stem}_05b_photo_NN_analysis.json``
``debug/{stem}_07_photo_NN_deglared.jpg``
``debug/{stem}_10_photo_NN_geometry_final.jpg``
``debug/{stem}_11_photo_NN_wb.jpg``
``debug/{stem}_12_photo_NN_deyellow.jpg``
``debug/{stem}_13_photo_NN_restored.jpg``
``debug/{stem}_14_photo_NN_enhanced.jpg``
``output/SundayAlbum_{stem}_PhotoNN.jpg``
"""

from src.steps import (  # noqa: F401
    load,
    normalize,
    page_detect,
    perspective,
    photo_detect,
    photo_split,
    ai_orient,
    glare_remove,
    geometry,
    color_restore,
)

__all__ = [
    "load",
    "normalize",
    "page_detect",
    "perspective",
    "photo_detect",
    "photo_split",
    "ai_orient",
    "glare_remove",
    "geometry",
    "color_restore",
]
