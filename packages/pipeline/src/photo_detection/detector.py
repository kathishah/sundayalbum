"""Photo detection — identify individual photos on album pages."""

import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PhotoDetection:
    """Information about a detected photo."""

    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    corners: np.ndarray  # 4x2 array of corner points (clockwise from top-left)
    confidence: float  # 0.0 to 1.0
    orientation: str  # "portrait", "landscape", or "square"
    area_ratio: float  # Ratio of photo area to page area
    contour: np.ndarray  # Original contour from detection


def detect_photos(
    page_image: np.ndarray,
    min_area_ratio: float = 0.02,  # Lowered from 0.05 to 0.02 (2%) to handle album pages with visible background
    max_count: int = 8,
    method: str = "contour",
    page_was_corrected: bool = False,
) -> List[PhotoDetection]:
    """Detect individual photos on an album page or single print.

    Critical test cases:
    - IMG_three_pics: album page with 3 photos → should return 3 detections
    - IMG_two_pics_vertical_horizontal: 2 photos (portrait + landscape) → should return 2
    - IMG_cave, IMG_harbor, IMG_skydiving: single prints → should return 1 each

    Args:
        page_image: Album page image, float32 RGB [0, 1]
        min_area_ratio: Minimum photo area as ratio of total image area
        max_count: Maximum number of photos to detect
        method: Detection method ("contour", "claude", or "auto")
        page_was_corrected: True when the image has already been perspective-corrected
            by page detection (i.e. the image IS the isolated subject, not the full
            camera frame).  When True, a pre-check determines whether the image
            contains clear album-page borders between photos.  If no borders are
            found the image is treated as a single print and returned whole, avoiding
            false splits on rich photographic content (cave, harbor, skydiving).

    Returns:
        List of PhotoDetection objects, sorted top-to-bottom, left-to-right
    """
    if method == "contour" or method == "auto":
        # Single-print guard: only applies after perspective correction has already
        # isolated the subject.  Album pages have white/neutral paper borders between
        # photos; single prints don't.  If no borders are detected, return the whole
        # image as one detection rather than letting contour analysis fragment the
        # photographic content into spurious sub-regions.
        if page_was_corrected and not _has_album_page_borders(page_image):
            h, w = page_image.shape[:2]
            if w > h * 1.1:
                orientation = "landscape"
            elif h > w * 1.1:
                orientation = "portrait"
            else:
                orientation = "square"
            logger.info(
                f"No album page borders detected on perspective-corrected image "
                f"({w}×{h}) — treating as single print"
            )
            # Try a brightness-profile crop to strip dark or bright background
            # material that GrabCut page detection may have included at the edges
            # (e.g. dark leather below the print, patterned album material above).
            cropped = _find_print_crop_by_brightness(page_image, min_area_ratio)
            if cropped is not None:
                logger.info(
                    f"Brightness-profile crop applied to single print: "
                    f"({cropped.bbox[0]},{cropped.bbox[1]})→"
                    f"({cropped.bbox[2]},{cropped.bbox[3]})"
                )
                return [cropped]
            return [PhotoDetection(
                bbox=(0, 0, w, h),
                corners=np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32),
                confidence=0.90,
                orientation=orientation,
                area_ratio=1.0,
                contour=np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]], dtype=np.int32),
            )]

        detections = _detect_photos_contour(page_image, min_area_ratio, max_count)
    elif method == "claude":
        raise NotImplementedError("Claude Vision API fallback not yet implemented")
    else:
        raise ValueError(f"Unknown detection method: {method}")

    logger.info(f"Detected {len(detections)} photos using method '{method}'")

    return detections


def _has_album_page_borders(
    image: np.ndarray,
    pixel_threshold_ratio: float = 0.05,
    row_low_fraction: float = 0.95,
    min_consecutive: int = 3,
    center_margin: float = 0.20,
) -> bool:
    """Detect whether a perspective-corrected image has clear borders between photos.

    Album pages contain white/neutral paper strips between individual photos.
    These appear as bands of near-zero Sobel-edge magnitude that span the full
    width (horizontal borders) or full height (vertical borders) of the image.
    Single prints have photographic content throughout — even smooth regions
    retain enough texture/grain to stay above the low-edge threshold.

    Args:
        image: Float32 RGB [0, 1].
        pixel_threshold_ratio: A pixel is "low-edge" when its Sobel magnitude is
            below this fraction of the image-wide maximum Sobel magnitude.
        row_low_fraction: Fraction of pixels in a row (or column) that must be
            low-edge for that line to be classified as a border line.
        min_consecutive: Minimum consecutive border lines required to confirm a
            border band (guards against isolated quiet rows inside a photo).
        center_margin: Ignore this fraction of rows/columns at the edges so that
            image borders are not confused with album-page borders.

    Returns:
        True if at least one clear border band is found (album page).
        False if no clear borders exist (single print).
    """
    h, w = image.shape[:2]

    image_uint8 = (image * 255).astype(np.uint8)
    gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    edge_mag = np.sqrt(sobelx ** 2 + sobely ** 2)

    max_edge = edge_mag.max()
    if max_edge < 1.0:
        return False  # Essentially blank image

    pixel_threshold = max_edge * pixel_threshold_ratio
    low_edge = edge_mag < pixel_threshold  # bool mask (H, W)

    # Album page borders are near-neutral in color (white/cream paper), not just
    # low-edge.  Photographic content that is also low-edge (e.g. dark cave walls,
    # uniform blue sky) typically has higher color saturation.  Requiring low
    # saturation as a second condition eliminates both dark neutral-ish photo areas
    # and saturated sky, while correctly accepting the white/cream album paper.
    hsv = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1].astype(np.float32) / 255.0
    is_neutral = saturation < 0.30  # Album paper saturation is well below 0.30

    border_mask = low_edge & is_neutral  # (H, W)

    margin_h = max(1, int(h * center_margin))
    margin_w = max(1, int(w * center_margin))

    def _has_consecutive_run(bool_1d: np.ndarray, min_run: int) -> bool:
        count = 0
        for val in bool_1d:
            if val:
                count += 1
                if count >= min_run:
                    return True
            else:
                count = 0
        return False

    # Horizontal border bands (full-width rows of low-edge AND neutral-color).
    # These indicate photos stacked vertically, separated by horizontal strips.
    center_rows = border_mask[margin_h: h - margin_h, :]  # (center_h, W)
    row_frac = center_rows.mean(axis=1)
    has_h_border = _has_consecutive_run(row_frac >= row_low_fraction, min_consecutive)

    # Vertical border bands (full-height columns of low-edge AND neutral-color).
    # These indicate photos placed side-by-side, separated by vertical strips.
    center_cols = border_mask[:, margin_w: w - margin_w]  # (H, center_w)
    col_frac = center_cols.mean(axis=0)
    has_v_border = _has_consecutive_run(col_frac >= row_low_fraction, min_consecutive)

    result = has_h_border or has_v_border
    logger.debug(
        f"Album border check: max_edge={max_edge:.1f}, "
        f"pixel_thresh={pixel_threshold:.2f}, "
        f"has_h_border={has_h_border}, has_v_border={has_v_border}"
    )
    return result


def _detect_photos_contour(
    page_image: np.ndarray,
    min_area_ratio: float,
    max_count: int,
) -> List[PhotoDetection]:
    """Detect photos using contour-based approach.

    The algorithm:
    1. Convert to grayscale
    2. Apply adaptive thresholding to separate photos from album page background
    3. Find contours
    4. Filter by area, aspect ratio, and shape
    5. Approximate to quadrilaterals
    6. Sort and return

    Args:
        page_image: Album page image, float32 RGB [0, 1]
        min_area_ratio: Minimum area ratio
        max_count: Maximum detections

    Returns:
        List of PhotoDetection objects
    """
    h, w = page_image.shape[:2]
    total_area = h * w
    min_area = total_area * min_area_ratio

    # Convert to uint8 for OpenCV
    image_uint8 = (page_image * 255).astype(np.uint8)

    # Convert to grayscale
    gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive thresholding works well for album pages where local contrast varies
    # Use a large block size to capture photo-level boundaries, not texture details
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # Gaussian weights for smoother results
        cv2.THRESH_BINARY_INV,  # Invert: photos are often darker than album background
        blockSize=101,  # Large block to ignore local details
        C=15,  # Constant to subtract
    )

    # Morphological operations to clean up photo regions
    # Balance: kernels must be large enough to connect fragmented photos,
    # but small enough to NOT merge separate photos together
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31))  # Connect fragments
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_close)

    # Remove small noise
    kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))  # Clean noise
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)

    # Find contours - use RETR_LIST to get ALL contours, not just external ones
    # This is critical for album pages where individual photos are INSIDE the page boundary
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # If we found too few large contours, try the inverted threshold
    large_contours = [c for c in contours if cv2.contourArea(c) > min_area]

    if len(large_contours) == 0:
        # Try normal threshold (photos lighter than background)
        binary_alt = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,  # Not inverted
            blockSize=101,
            C=15,
        )
        # Use same balanced morphological operations
        kernel_close_alt = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31))
        kernel_open_alt = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        binary_alt = cv2.morphologyEx(binary_alt, cv2.MORPH_CLOSE, kernel_close_alt)
        binary_alt = cv2.morphologyEx(binary_alt, cv2.MORPH_OPEN, kernel_open_alt)

        contours_alt, _ = cv2.findContours(binary_alt, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        # Only count contours that survive the second-pass area filter (< 98% of image).
        # A nearly-full-frame contour (e.g. 99.8%) means the threshold made the entire
        # image white and is not a useful detection; fall through to Canny in that case.
        large_contours_alt = [
            c for c in contours_alt
            if min_area < cv2.contourArea(c) <= total_area * 0.98
        ]

        if len(large_contours_alt) > 0:
            contours = contours_alt
            binary = binary_alt
            large_contours = large_contours_alt
            logger.debug(f"Using non-inverted threshold ({len(large_contours_alt)} large contours)")
        else:
            # Both adaptive thresholds failed - try Canny edge detection as last resort
            logger.debug(f"Both thresholds found 0 large contours - trying Canny edge detection fallback")

            # Canny edge detection with moderate thresholds
            edges = cv2.Canny(blurred, 50, 150)

            # Dilate edges to connect broken boundaries
            kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            edges_dilated = cv2.dilate(edges, kernel_dilate, iterations=2)

            # Fill holes to create solid regions
            kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
            binary_canny = cv2.morphologyEx(edges_dilated, cv2.MORPH_CLOSE, kernel_close)

            contours_canny, _ = cv2.findContours(binary_canny, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            large_contours_canny = [c for c in contours_canny if cv2.contourArea(c) > min_area]

            if len(large_contours_canny) > 0:
                contours = contours_canny
                binary = binary_canny
                large_contours = large_contours_canny
                logger.debug(f"Canny fallback successful: {len(large_contours_canny)} large contours")
            else:
                logger.debug(f"Canny fallback also found 0 large contours - will return empty list")
    else:
        logger.debug(f"Using inverted threshold ({len(large_contours)} large contours)")

    logger.debug(f"Found {len(contours)} contours before area/shape filtering")

    # Filter and classify contours
    detections: List[PhotoDetection] = []
    filtered_reasons = []

    # First pass: collect all potentially valid contours
    # We'll apply different max_area thresholds based on whether this looks like a single print or album page
    potential_detections = []

    for idx, contour in enumerate(contours):
        # Filter by area
        area = cv2.contourArea(contour)
        area_ratio = area / total_area

        # Too small: likely noise/decoration
        if area < min_area:
            filtered_reasons.append(f"Contour {idx}: area too small ({area:.0f} px, {area_ratio:.3f} ratio)")
            continue

        # Skip extremely large contours (>98%) - these are definitely full-frame/page boundaries
        # Note: Single prints can be 95-98% of image, so we use 0.98 here and let adaptive logic handle it
        if area_ratio > 0.98:
            filtered_reasons.append(f"Contour {idx}: area too large ({area:.0f} px, {area_ratio:.3f} ratio) - likely full frame")
            continue

        # Store for later analysis
        potential_detections.append((idx, contour, area, area_ratio))

    # Determine if this is a single print or multi-photo page
    # Single print scenario: 1-2 large contours (30-95% of image)
    # Multi-photo page: multiple smaller contours (each 2-30% of image)
    large_contours = [d for d in potential_detections if d[3] >= 0.30]  # >= 30% area
    medium_contours = [d for d in potential_detections if 0.10 <= d[3] < 0.30]

    is_single_print = (len(large_contours) == 1 and len(medium_contours) == 0)

    logger.debug(
        f"Detection scenario analysis: large_contours={len(large_contours)}, "
        f"medium_contours={len(medium_contours)}, "
        f"total_potential={len(potential_detections)}, "
        f"is_single_print={is_single_print}"
    )

    # Apply appropriate max_area threshold based on scenario
    if is_single_print:
        # Single print: allow contours up to 98% (we filtered >98% in first pass)
        # Single prints can be very close to image edges, so we're generous here
        max_area_threshold = 0.98
        logger.debug("Using single-print mode: max_area_threshold=0.98")
    else:
        # Multi-photo page: individual photos typically < 40% of total image
        # Page boundary would be >90%, so use 0.90 as max
        max_area_threshold = 0.90
        logger.debug("Using multi-photo mode: max_area_threshold=0.90")

    # Second pass: apply max_area filter and shape analysis
    for idx, contour, area, area_ratio in potential_detections:
        # Apply max_area threshold
        if area_ratio > max_area_threshold:
            filtered_reasons.append(
                f"Contour {idx}: area too large ({area:.0f} px, {area_ratio:.3f} ratio) - "
                f"exceeds threshold {max_area_threshold}"
            )
            continue

        # Filter by shape — photos should be roughly rectangular
        # Compute perimeter and check if the contour is convex-ish
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            filtered_reasons.append(f"Contour {idx}: zero perimeter")
            continue

        # Approximate to polygon
        epsilon = 0.02 * perimeter  # Approximation accuracy
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # We expect 4-sided shapes (quadrilaterals) for photos
        # But be flexible — 4 to 12 sides is OK (relaxed from 8)
        num_vertices = len(approx)
        if num_vertices < 4 or num_vertices > 12:
            filtered_reasons.append(f"Contour {idx}: bad vertex count ({num_vertices})")
            continue

        # Get bounding box
        x, y, bw, bh = cv2.boundingRect(contour)

        # Filter by aspect ratio — photos are typically 3:2, 4:3, 1:1, etc.
        # Reject extremely elongated shapes (likely not photos)
        aspect_ratio = max(bw, bh) / (min(bw, bh) + 1e-6)
        if aspect_ratio > 6.0:  # Too elongated (relaxed from 5.0)
            filtered_reasons.append(
                f"Contour {idx}: aspect ratio too high ({aspect_ratio:.2f}, area={area:.0f}, ratio={area_ratio:.3f})"
            )
            continue

        # If we have more than 4 vertices, find best-fit quadrilateral
        if num_vertices > 4:
            # Use minimum area rectangle as approximation
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            corners = np.array(box, dtype=np.float32)
        else:
            corners = approx.reshape(-1, 2).astype(np.float32)

        # Order corners: top-left, top-right, bottom-right, bottom-left
        corners = _order_corners(corners)

        # Determine orientation based on aspect ratio of bounding box
        if bw > bh * 1.1:
            orientation = "landscape"
        elif bh > bw * 1.1:
            orientation = "portrait"
        else:
            orientation = "square"

        # Compute confidence based on:
        # 1. How rectangular the shape is (ratio of area to bounding box area)
        # 2. How clean the approximation is (fewer vertices = cleaner)
        rect_area = bw * bh
        rectangularity = area / (rect_area + 1e-6)
        vertex_score = 1.0 - (abs(num_vertices - 4) / 10.0)  # 4 vertices is ideal
        confidence = (rectangularity + vertex_score) / 2.0
        confidence = np.clip(confidence, 0.0, 1.0)

        detection = PhotoDetection(
            bbox=(x, y, x + bw, y + bh),
            corners=corners,
            confidence=confidence,
            orientation=orientation,
            area_ratio=area_ratio,
            contour=contour,
        )

        detections.append(detection)

    # Sort detections by confidence (descending)
    detections.sort(key=lambda d: d.confidence, reverse=True)

    # Limit to max_count
    detections = detections[:max_count]

    # Filter out small decorations that are significantly smaller than real photos
    # Use adaptive threshold based on number of detections
    if len(detections) > 1:
        areas = [d.area_ratio * total_area for d in detections]
        max_area = max(areas)

        # Adaptive threshold for decoration filtering:
        # Album pages can have photos of varying sizes (e.g., 3×5 mixed with 4×6)
        # Use relaxed threshold to avoid filtering out legitimately smaller photos.
        # - If we have many detections (> 4), use moderate filter (30%)
        # - If we have few detections (2-4), use tight filter (10%) so that a
        #   portrait photo significantly smaller in pixel area than a landscape
        #   photo (which can be as low as ~17% of the larger contour's area) is
        #   kept rather than discarded.  Genuine decorative elements (captions,
        #   stamps) are typically < 5% and will still be removed.
        threshold = 0.30 if len(detections) > 4 else 0.10

        logger.debug(
            f"Decoration filter check: {len(detections)} detections, "
            f"max_area={max_area:.0f}px, threshold={threshold*100:.0f}%"
        )

        filtered_detections = []
        for i, (detection, area) in enumerate(zip(detections, areas), 1):
            ratio = area / max_area
            if ratio >= threshold:
                filtered_detections.append(detection)
                logger.debug(f"  Detection {i}: {area:.0f}px ({ratio*100:.1f}%) -> KEEP")
            else:
                logger.debug(f"  Detection {i}: {area:.0f}px ({ratio*100:.1f}%) -> FILTER")

        logger.debug(f"After decoration filter: {len(filtered_detections)} remaining")
        detections = filtered_detections

    # Remove overlapping detections (keep higher confidence / larger ones)
    detections = _remove_overlapping_detections(detections, iou_threshold=0.3)

    # Re-sort by position (top-to-bottom, left-to-right) for user-friendly ordering
    detections.sort(key=lambda d: (d.bbox[1], d.bbox[0]))

    logger.debug(
        f"After filtering: {len(detections)} detections "
        f"(min_area={min_area:.0f}px, min_ratio={min_area_ratio:.3f})"
    )

    # Log filtering reasons for debugging
    if filtered_reasons:
        logger.debug(f"Filtered out {len(filtered_reasons)} contours:")
        for reason in filtered_reasons[:10]:  # Limit to first 10
            logger.debug(f"  {reason}")

    # Sanity check: if 2+ detections have badly disproportionate bounding-box areas
    # (one is >2.5× another), the contour method likely found wrong boundaries.
    # Uses bounding-box area rather than contour area because highly skewed contours
    # can have a very small contour area but a massive bounding box (e.g. a diagonal
    # stripe contour), masking the true disproportion from the contour-area ratio.
    fell_back_via_imbalance = False
    if len(detections) >= 2:
        bbox_areas = [
            (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]) / total_area
            for d in detections
        ]
        area_imbalance = max(bbox_areas) / (min(bbox_areas) + 1e-6)
        if area_imbalance > 2.5:
            logger.warning(
                f"Contour detections are disproportionate (imbalance={area_imbalance:.1f}x). "
                f"Falling back to detection."
            )
            fell_back_via_imbalance = True

            # Try brightness-based spine detection first: it directly finds the
            # white album-spine band and splits there — more reliable than
            # edge-density projection when the spine fabric has its own edges.
            # The function returns [] if conditions are not met (not exactly one
            # qualifying band in 33–67% of page height).
            bright_detections = _detect_photos_by_whiteness(page_image, min_area_ratio)
            if bright_detections:
                detections = bright_detections
            else:
                # Brightness spine detection didn't apply; use projection-profile.
                proj_detections = _detect_photos_by_projection(page_image, min_area_ratio)
                if proj_detections:
                    # Projection may over-split the page into many strips when there
                    # is no white paper gap (e.g. two prints on a dark album
                    # background).  When it returns more than 3 photos, fall back to
                    # GrabCut segmentation which correctly separates photo blobs from
                    # the background.
                    if len(proj_detections) > 3:
                        logger.warning(
                            f"Projection over-splits ({len(proj_detections)} photos). "
                            f"Trying GrabCut photo-detection fallback."
                        )
                        grab_detections = _detect_photos_grabcut(page_image, min_area_ratio)
                        if grab_detections:
                            detections = grab_detections
                        else:
                            detections = proj_detections
                    else:
                        detections = proj_detections

    # Secondary quality check: if ALL contour detections are badly non-rectangular
    # (max rectangularity < 0.45), every contour found a diagonal/skewed shape
    # rather than a photo border.  Try the brightness-based spine detector as a
    # last resort before returning the bad contour results.
    # Only runs when the imbalance check above did NOT already fire.
    if not fell_back_via_imbalance and len(detections) >= 2:
        rects = [
            cv2.contourArea(d.contour)
            / ((d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1]) + 1e-6)
            for d in detections
        ]
        if max(rects) < 0.45:
            logger.warning(
                f"All contour detections are non-rectangular "
                f"(max_rect={max(rects):.2f}). "
                f"Trying brightness-based separator detection."
            )
            bright_detections = _detect_photos_by_whiteness(page_image, min_area_ratio)
            if bright_detections:
                detections = bright_detections

    # Single-photo quality check: when exactly one photo is detected but its
    # contour is badly non-rectangular, the detector found a diagonal edge stripe
    # within the photo content (e.g. dark tablecloth edges, angled wine-glass
    # highlights) rather than the actual photo boundary.  Applying perspective
    # correction using these skewed corners produces a severely distorted crop.
    # Try a brightness-profile crop first; fall back to [] (full page) if it
    # doesn't find a meaningful tighter boundary.
    if len(detections) == 1:
        bw = detections[0].bbox[2] - detections[0].bbox[0]
        bh = detections[0].bbox[3] - detections[0].bbox[1]
        rect = cv2.contourArea(detections[0].contour) / (bw * bh + 1e-6)
        if rect < 0.45:
            logger.warning(
                f"Single-photo contour is badly non-rectangular (rect={rect:.2f}). "
                f"Trying brightness-profile crop to find photo print boundary."
            )
            cropped = _find_print_crop_by_brightness(page_image, min_area_ratio)
            if cropped is not None:
                return [cropped]
            logger.warning(
                "Brightness-profile crop found no clear boundary; "
                "returning [] so the pipeline uses the full page as the photo."
            )
            return []

    return detections


def _find_print_crop_by_brightness(
    page_image: np.ndarray,
    min_area_ratio: float,
    dark_thresh: float = 0.25,
    bright_thresh: float = 0.65,
    margin_frac: float = 0.015,
) -> Optional[PhotoDetection]:
    """Find a tight crop of the actual photo print within a warped page.

    Handles two common backgrounds that appear after perspective correction:

    * **Dark background** (e.g. black leather/cloth): row-mean brightness below
      ``dark_thresh``.  These rows are stripped from the top/bottom/sides.
    * **Bright non-photo background** (e.g. patterned album material):
      row-mean brightness above ``bright_thresh`` that forms a *contiguous block
      at the image edge*.  Only edge-adjacent bright rows are stripped; isolated
      bright rows inside the photo (e.g. a white tablecloth) are kept.

    Args:
        page_image: Perspective-corrected album page, float32 RGB [0, 1].
        min_area_ratio: Minimum crop area as fraction of page area.
        dark_thresh: Rows darker than this are background.
        bright_thresh: Contiguous edge rows brighter than this are background.
        margin_frac: Small fractional margin to restore around detected crop.

    Returns:
        A single PhotoDetection for the found crop, or None if the crop would
        be too small or not meaningfully tighter than the full page.
    """
    h, w = page_image.shape[:2]
    total_area = float(h * w)
    gray = page_image.mean(axis=2)

    row_bright = np.array([gray[y, :].mean() for y in range(h)])
    col_bright = np.array([gray[:, x].mean() for x in range(w)])

    def _find_axis_bounds(profile: np.ndarray, size: int) -> Tuple[int, int]:
        """Strip dark and edge-adjacent bright background from one axis."""
        # Step 1: strip dark from both ends
        lo = 0
        while lo < size and profile[lo] < dark_thresh:
            lo += 1
        hi = size - 1
        while hi > lo and profile[hi] < dark_thresh:
            hi -= 1

        # Step 2: strip contiguous bright background from the low end (edge)
        while lo < hi and profile[lo] > bright_thresh:
            lo += 1

        # Step 3: strip contiguous bright background from the high end (edge)
        while hi > lo and profile[hi] > bright_thresh:
            hi -= 1

        return lo, hi

    y1, y2 = _find_axis_bounds(row_bright, h)
    x1, x2 = _find_axis_bounds(col_bright, w)

    # Add a small margin so we don't clip the white paper border
    margin_y = max(1, int(h * margin_frac))
    margin_x = max(1, int(w * margin_frac))
    y1 = max(0, y1 - margin_y)
    y2 = min(h - 1, y2 + margin_y)
    x1 = max(0, x1 - margin_x)
    x2 = min(w - 1, x2 + margin_x)

    crop_h = y2 - y1
    crop_w = x2 - x1
    area_ratio = (crop_h * crop_w) / total_area

    # Sanity checks: crop must be large enough and meaningfully smaller
    if area_ratio < min_area_ratio:
        logger.debug(
            f"Brightness-profile crop too small (area_ratio={area_ratio:.3f})"
        )
        return None

    # If the crop is nearly the same as the full page (< 5% reduction), don't
    # bother — it would be misleading to claim we found a tight boundary.
    if area_ratio > 0.95:
        logger.debug(
            f"Brightness-profile crop not meaningfully tighter "
            f"(area_ratio={area_ratio:.3f})"
        )
        return None

    orientation: str
    if crop_w > crop_h * 1.1:
        orientation = "landscape"
    elif crop_h > crop_w * 1.1:
        orientation = "portrait"
    else:
        orientation = "square"

    corners = np.array(
        [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32
    )
    contour = np.array(
        [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32
    ).reshape(-1, 1, 2)

    logger.info(
        f"Brightness-profile crop: ({x1},{y1})→({x2},{y2}) "
        f"area_ratio={area_ratio:.3f}"
    )
    return PhotoDetection(
        bbox=(x1, y1, x2, y2),
        corners=corners,
        confidence=0.75,
        orientation=orientation,
        area_ratio=area_ratio,
        contour=contour,
    )


def _find_projection_gaps(
    smooth_profile: np.ndarray,
    start: int,
    end: int,
    primary_threshold_ratio: float = 0.55,
    secondary_depth_multiplier: float = 1.20,
    min_separation_ratio: float = 0.20,
) -> List[int]:
    """Find positions of physical gaps between photos in a projection profile.

    Uses a primary + secondary approach:
    1. The primary gap is the single deepest valley in the search range.
       It must be below ``primary_threshold_ratio * mean`` to count.
    2. Additional gaps are local minima that are:
       a. Within ``secondary_depth_multiplier`` of the primary gap's depth.
          Album-page dividers are all made of the same white paper, so real
          secondary gaps should be nearly as quiet as the primary one.
          Smooth photographic regions (uniform sky, background) are louder
          relative to the primary, so they are rejected by this check.
       b. Separated from every already-accepted gap by at least
          ``min_separation_ratio * (end - start)`` positions.

    Args:
        smooth_profile: Smoothed 1-D projection (row or column edge sums).
        start: First index of the search range (exclusive of image borders).
        end: One-past-last index of the search range.
        primary_threshold_ratio: The deepest valley must be below this
            fraction of the search-range mean to count as a real gap.
        secondary_depth_multiplier: Secondary gaps must have absolute depth
            ≤ primary_depth × multiplier.  Use 1.20 — real album-page borders
            are within 20% of each other; smooth photo areas are 30%+ louder.
        min_separation_ratio: Minimum spacing between accepted gap positions,
            as a fraction of ``end - start``.  Prevents double-counting a
            single wide border band.

    Returns:
        Sorted list of gap positions (absolute indices into ``smooth_profile``).
    """
    search = smooth_profile[start:end]
    n = len(search)
    if n < 3:
        return []

    mean_val = search.mean() + 1e-6

    # --- Primary gap: the single deepest valley -----------------------
    primary_rel = int(np.argmin(search))
    primary_abs = primary_rel + start
    primary_depth = float(smooth_profile[primary_abs])
    primary_depth_ratio = primary_depth / mean_val

    if primary_depth_ratio >= primary_threshold_ratio:
        # Even the deepest point is not deep enough to be a real gap
        return []

    gaps: List[int] = [primary_abs]

    # --- Secondary gaps: similar-depth, well-separated local minima ---
    min_separation = max(5, int((end - start) * min_separation_ratio))
    # Secondary must be nearly as quiet as the primary (same white paper).
    secondary_threshold = primary_depth * secondary_depth_multiplier

    # Collect all local minima (both neighbours strictly higher)
    local_minima: List[Tuple[float, int]] = []
    for i in range(1, n - 1):
        if search[i] < search[i - 1] and search[i] < search[i + 1]:
            abs_i = i + start
            if smooth_profile[abs_i] <= secondary_threshold:
                local_minima.append((float(smooth_profile[abs_i]), abs_i))

    # Sort by depth ascending so we try the deepest candidates first
    local_minima.sort()

    for _depth, idx in local_minima:
        if all(abs(idx - g) >= min_separation for g in gaps):
            gaps.append(idx)

    return sorted(gaps)


def _detect_photos_by_projection(
    page_image: np.ndarray,
    min_area_ratio: float,
) -> List[PhotoDetection]:
    """Detect photo split lines using edge-density projection profiles.

    For pages where contour detection produces badly disproportionate regions
    this approach is more robust.  It computes Sobel-edge magnitude sums across
    every row and column, locates bands where the energy drops sharply (physical
    gaps / album-page dividers between photos), and uses those as split lines.

    Supports any number of photos stacked vertically or placed side-by-side.

    Args:
        page_image: Album page image, float32 RGB [0, 1].
        min_area_ratio: Minimum photo area as fraction of total image area.

    Returns:
        List of PhotoDetection objects (one per region), or empty list if no
        clear gaps are found.
    """
    h, w = page_image.shape[:2]
    total_area = float(h * w)

    image_uint8 = (page_image * 255).astype(np.uint8)
    gray = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Sobel edge magnitude captures structural boundaries between photos
    sobelx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    edge_mag = np.sqrt(sobelx ** 2 + sobely ** 2)

    # Smooth projection profiles to find broad valleys (album dividers are wide)
    smooth_k = max(11, min(h, w) // 30)

    row_profile = edge_mag.sum(axis=1)  # (h,)  — rows with few edges = horizontal gap
    col_profile = edge_mag.sum(axis=0)  # (w,)  — cols with few edges = vertical gap

    row_smooth = np.convolve(row_profile, np.ones(smooth_k) / smooth_k, mode='same')
    col_smooth = np.convolve(col_profile, np.ones(smooth_k) / smooth_k, mode='same')

    # Search only in the central 20–80% of each axis so that album-page outer
    # borders (top/bottom/left/right) are not mistaken for photo dividers.
    margin_h = max(1, int(h * 0.20))
    margin_w = max(1, int(w * 0.20))

    h_gaps = _find_projection_gaps(row_smooth, margin_h, h - margin_h)
    v_gaps = _find_projection_gaps(col_smooth, margin_w, w - margin_w)

    logger.debug(
        f"Projection gaps — horizontal (stacked): {h_gaps}, "
        f"vertical (side-by-side): {v_gaps}"
    )

    # Prefer the axis that yields more splits (more photos detected).
    # Break ties by choosing the axis whose gaps are relatively deeper.
    def _mean_relative_depth(gaps: List[int], profile: np.ndarray) -> float:
        if not gaps:
            return 1.0  # No gaps → no depth improvement
        mean_val = profile.mean() + 1e-6
        return float(np.mean([profile[g] / mean_val for g in gaps]))

    if not h_gaps and not v_gaps:
        logger.debug("Projection: no clear gaps found — returning empty")
        return []

    use_vertical: bool
    if len(v_gaps) > len(h_gaps):
        use_vertical = True
    elif len(h_gaps) > len(v_gaps):
        use_vertical = False
    else:
        # Equal number of gaps — pick the axis with deeper (lower-ratio) valleys
        v_depth = _mean_relative_depth(v_gaps, col_smooth)
        h_depth = _mean_relative_depth(h_gaps, row_smooth)
        use_vertical = v_depth <= h_depth

    if use_vertical:
        splits = sorted(v_gaps)
        boundaries = [0] + splits + [w]
        regions: List[Tuple[int, int, int, int]] = [
            (boundaries[i], 0, boundaries[i + 1], h)
            for i in range(len(boundaries) - 1)
        ]
        logger.debug(f"Projection: {len(splits)} vertical split(s) at x={splits}")
    else:
        splits = sorted(h_gaps)
        boundaries = [0] + splits + [h]
        regions = [
            (0, boundaries[i], w, boundaries[i + 1])
            for i in range(len(boundaries) - 1)
        ]
        logger.debug(f"Projection: {len(splits)} horizontal split(s) at y={splits}")

    detections: List[PhotoDetection] = []
    for x1, y1, x2, y2 in regions:
        bw, bh = x2 - x1, y2 - y1
        area_ratio = (bw * bh) / total_area

        if area_ratio < min_area_ratio:
            continue

        corners = np.array(
            [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32
        )

        if bw > bh * 1.1:
            orientation = "landscape"
        elif bh > bw * 1.1:
            orientation = "portrait"
        else:
            orientation = "square"

        contour = np.array(
            [[[x1, y1]], [[x2, y1]], [[x2, y2]], [[x1, y2]]], dtype=np.int32
        )

        detections.append(PhotoDetection(
            bbox=(x1, y1, x2, y2),
            corners=corners,
            confidence=0.75,
            orientation=orientation,
            area_ratio=area_ratio,
            contour=contour,
        ))

    logger.debug(f"Projection detection produced {len(detections)} regions")
    return detections


def _detect_photos_by_whiteness(
    page_image: np.ndarray,
    min_area_ratio: float,
) -> List[PhotoDetection]:
    """Detect two photos separated by a single bright album-spine band.

    Album pages that have an album spine (white or cream textured band)
    visually dividing two prints are accurately split here.  The edge-density
    projection approach fails on these pages because the spine fabric has
    sufficient texture to produce Sobel edges, masking the gap.

    Strict acceptance criteria prevent false splits on 3-photo pages or pages
    with a photo-content bright patch near an edge:

    * Exactly **one** qualifying interior separator band.
    * Band maximum row-brightness ≥ 0.80 (true spine; distinguishes white
      album fabric from a slightly bright patch inside photo content).
    * Band center between 33 % and 67 % of page height (the spine of a
      two-photo page lies near the vertical midpoint).

    Args:
        page_image: Perspective-corrected album page, float32 RGB [0, 1].
        min_area_ratio: Minimum photo area as fraction of total page area.

    Returns:
        List of two PhotoDetection objects if exactly one qualifying spine
        band is found; empty list otherwise.
    """
    h, w = page_image.shape[:2]
    total_area = float(h * w)

    row_brightness = page_image.mean(axis=(1, 2))

    # Smooth with ~1.5% of page height to suppress row-level noise.
    window = max(5, int(h * 0.015))
    smooth = np.convolve(row_brightness, np.ones(window) / window, mode="same")

    # Collect bright runs (threshold 0.74 passes all real spine candidates).
    bright_threshold = 0.74
    is_bright = smooth > bright_threshold
    raw_bands: List[Tuple[int, int]] = []
    in_band = False
    start = 0
    for y in range(h):
        if is_bright[y] and not in_band:
            in_band = True
            start = y
        elif not is_bright[y] and in_band:
            in_band = False
            raw_bands.append((start, y - 1))
    if in_band:
        raw_bands.append((start, h - 1))

    # Merge sub-bands within 100 rows of each other.
    merged: List[Tuple[int, int]] = []
    for band in raw_bands:
        if merged and band[0] - merged[-1][1] < 100:
            merged[-1] = (merged[-1][0], band[1])
        else:
            merged.append(band)

    # Filter: interior (5%–95%), at least 30 rows wide, and max per-row
    # brightness ≥ 0.80 (true album-spine fabric; not a bright photo patch).
    edge_margin = 0.05
    min_brightness = 0.80
    qualifying: List[int] = []  # separator center y-coordinates
    for start, end in merged:
        width = end - start + 1
        center = (start + end) // 2
        max_bright = float(row_brightness[start : end + 1].max())
        if (
            width >= 30
            and start > h * edge_margin
            and end < h * (1.0 - edge_margin)
            and max_bright >= min_brightness
        ):
            qualifying.append(center)

    # Accept only when exactly ONE qualifying band exists and it lies in the
    # central third of the page (33%–67%).  This rejects:
    #   – 3-photo pages whose second separator lands near 69% (outside range)
    #   – 2-photo side-by-side pages with multiple bright strips
    if len(qualifying) != 1:
        logger.debug(
            f"Whiteness separator: {len(qualifying)} qualifying band(s); "
            f"need exactly 1 — falling through."
        )
        return []

    separator_y = qualifying[0]
    if not (h * 0.33 <= separator_y <= h * 0.67):
        logger.debug(
            f"Whiteness separator: band at y={separator_y} "
            f"({separator_y/h*100:.0f}%) is outside 33–67% range — falling through."
        )
        return []

    separators = [separator_y]
    logger.info(
        f"Whiteness separator detection: 1 qualifying band at y={separator_y} "
        f"({separator_y/h*100:.0f}%)"
    )

    split_points = [0] + separators + [h]
    detections: List[PhotoDetection] = []
    for i in range(len(split_points) - 1):
        y1 = split_points[i]
        y2 = split_points[i + 1]
        region_h = y2 - y1
        area_ratio = (w * region_h) / total_area
        if area_ratio < min_area_ratio:
            continue

        bbox = (0, y1, w, y2)
        corners = np.array(
            [[0, y1], [w, y1], [w, y2], [0, y2]], dtype=np.float32
        )

        if w > region_h * 1.1:
            orientation = "landscape"
        elif region_h > w * 1.1:
            orientation = "portrait"
        else:
            orientation = "square"

        detections.append(
            PhotoDetection(
                bbox=bbox,
                corners=corners,
                confidence=0.70,
                orientation=orientation,
                area_ratio=area_ratio,
                contour=np.array(
                    [[0, y1], [w, y1], [w, y2], [0, y2]], dtype=np.int32
                ).reshape(-1, 1, 2),
            )
        )

    detections.sort(key=lambda d: (d.bbox[1], d.bbox[0]))
    logger.info(f"Whiteness separator detection: {len(detections)} photo(s)")
    return detections


def _detect_photos_grabcut(
    page_image: np.ndarray,
    min_area_ratio: float,
) -> List[PhotoDetection]:
    """Detect photo regions using GrabCut segmentation on the page image.

    Last-resort fallback for pages where neither contour detection nor
    projection-profile detection finds the correct photo boundaries — typically
    when two or more prints are placed on a dark album background without white
    paper gaps between them.

    GrabCut treats the large photo-content regions as foreground and the dark
    album background as background, returning one blob per physical photo.

    Args:
        page_image: Perspective-corrected album page, float32 RGB [0, 1].
        min_area_ratio: Minimum photo area as fraction of total page area.

    Returns:
        List of PhotoDetection objects (one per detected blob), sorted
        top-to-bottom, left-to-right.  Empty list if GrabCut fails or finds
        no qualifying regions.
    """
    h, w = page_image.shape[:2]
    total_area = float(h * w)

    # Downscale for speed — coarse segmentation is all we need.
    max_dim = 600
    scale = max_dim / max(h, w)
    gc_h = max(50, int(h * scale))
    gc_w = max(50, int(w * scale))
    scale_x = w / gc_w
    scale_y = h / gc_h

    gc_uint8 = cv2.resize(
        (page_image * 255).astype(np.uint8),
        (gc_w, gc_h),
        interpolation=cv2.INTER_AREA,
    )
    gc_bgr = cv2.cvtColor(gc_uint8, cv2.COLOR_RGB2BGR)

    margin_x = max(2, int(gc_w * 0.02))
    margin_y = max(2, int(gc_h * 0.02))
    rect = (margin_x, margin_y, gc_w - 2 * margin_x, gc_h - 2 * margin_y)

    gc_mask = np.zeros((gc_h, gc_w), dtype=np.uint8)
    bg_model = np.zeros((1, 65), dtype=np.float64)
    fg_model = np.zeros((1, 65), dtype=np.float64)

    try:
        cv2.grabCut(
            gc_bgr, gc_mask, rect,
            bg_model, fg_model,
            5, cv2.GC_INIT_WITH_RECT,
        )
    except cv2.error as e:
        logger.warning(f"GrabCut photo-detection fallback failed: {e}")
        return []

    fg_mask = np.where(
        (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD),
        np.uint8(255),
        np.uint8(0),
    )

    # Morphological cleanup — same approach as page_detection.detector.
    kernel_size = max(15, int(min(gc_h, gc_w) * 0.015))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    cleaned = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Require each blob to cover at least 5 % of the (downscaled) image area so
    # that dust/noise specks do not produce spurious detections.
    component_min = float(gc_h * gc_w) * max(0.05, min_area_ratio * 0.15)
    significant = [c for c in contours if cv2.contourArea(c) >= component_min]

    if not significant:
        logger.debug("GrabCut fallback: no significant photo blobs found")
        return []

    logger.debug(
        f"GrabCut fallback: {len(significant)} blob(s) above "
        f"component_min={component_min:.0f}px"
    )

    detections: List[PhotoDetection] = []
    for contour in significant:
        # Scale contour points back to full-resolution page coordinates.
        contour_full = (contour.astype(np.float32)
                        * np.array([[[scale_x, scale_y]]])).astype(np.int32)

        x, y, bw, bh = cv2.boundingRect(contour_full)
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        bw = min(bw, w - x)
        bh = min(bh, h - y)

        area_ratio = (bw * bh) / total_area
        if area_ratio < min_area_ratio:
            logger.debug(
                f"  GrabCut blob skipped: area_ratio={area_ratio:.3f} < min={min_area_ratio}"
            )
            continue

        # Convex hull → minAreaRect → ordered 4-corner quad.
        hull = cv2.convexHull(contour_full)
        rect = cv2.minAreaRect(hull)
        box = cv2.boxPoints(rect)
        corners = np.array(box, dtype=np.float32)
        corners[:, 0] = np.clip(corners[:, 0], 0, w - 1)
        corners[:, 1] = np.clip(corners[:, 1], 0, h - 1)
        corners = _order_corners(corners)

        if bw > bh * 1.1:
            orientation = "landscape"
        elif bh > bw * 1.1:
            orientation = "portrait"
        else:
            orientation = "square"

        contour_area = cv2.contourArea(contour_full)
        rectangularity = contour_area / float(bw * bh + 1)
        confidence = float(np.clip(0.60 + rectangularity * 0.20, 0.0, 0.80))

        detections.append(PhotoDetection(
            bbox=(x, y, x + bw, y + bh),
            corners=corners,
            confidence=confidence,
            orientation=orientation,
            area_ratio=area_ratio,
            contour=contour_full,
        ))

    detections.sort(key=lambda d: (d.bbox[1], d.bbox[0]))
    logger.info(f"GrabCut fallback detected {len(detections)} photo(s)")
    return detections


def _compute_iou(bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]) -> float:
    """Compute Intersection over Union (IoU) between two bounding boxes.

    Args:
        bbox1: First bbox as (x1, y1, x2, y2)
        bbox2: Second bbox as (x1, y1, x2, y2)

    Returns:
        IoU value between 0.0 and 1.0
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2

    # Compute intersection
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)

    if x2_i < x1_i or y2_i < y1_i:
        return 0.0  # No overlap

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Compute union
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def _remove_overlapping_detections(
    detections: List[PhotoDetection],
    iou_threshold: float = 0.3
) -> List[PhotoDetection]:
    """Remove overlapping detections using Non-Maximum Suppression.

    Keep detections with higher confidence when IoU > threshold.

    Args:
        detections: List of detections (should be sorted by confidence desc)
        iou_threshold: IoU threshold for considering detections as overlapping

    Returns:
        Filtered list with no significant overlaps
    """
    if len(detections) <= 1:
        return detections

    # Sort by confidence (descending) to prioritize keeping high-confidence detections
    sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)

    keep = []
    for i, det1 in enumerate(sorted_dets):
        # Check if det1 overlaps significantly with any already-kept detection
        overlaps = False
        for det2 in keep:
            iou = _compute_iou(det1.bbox, det2.bbox)
            if iou > iou_threshold:
                overlaps = True
                logger.debug(f"Removing overlapping detection (IoU={iou:.2f}): "
                           f"area={det1.area_ratio:.2%}, conf={det1.confidence:.2f}")
                break

        if not overlaps:
            keep.append(det1)

    logger.debug(f"Non-maximum suppression: {len(detections)} -> {len(keep)} detections")
    return keep


def _order_corners(corners: np.ndarray) -> np.ndarray:
    """Order corners in clockwise order starting from top-left.

    Args:
        corners: Nx2 array of corner points (N should be 4)

    Returns:
        4x2 array ordered as: top-left, top-right, bottom-right, bottom-left
    """
    # If we have exactly 4 corners, use standard ordering
    if len(corners) == 4:
        # Sum and difference of coordinates to find corners
        # Top-left has smallest sum (x+y)
        # Bottom-right has largest sum
        # Top-right has smallest difference (y-x)
        # Bottom-left has largest difference
        sums = corners.sum(axis=1)
        diffs = np.diff(corners, axis=1).flatten()

        top_left = corners[np.argmin(sums)]
        bottom_right = corners[np.argmax(sums)]
        top_right = corners[np.argmin(diffs)]
        bottom_left = corners[np.argmax(diffs)]

        return np.array([top_left, top_right, bottom_right, bottom_left], dtype=np.float32)
    else:
        # If not exactly 4 corners, just return as-is
        # (This shouldn't happen if filtering worked correctly)
        logger.warning(f"Expected 4 corners, got {len(corners)}")
        return corners


def draw_photo_detections(
    page_image: np.ndarray,
    detections: List[PhotoDetection],
) -> np.ndarray:
    """Draw detected photo boundaries on the page image for visualization.

    Args:
        page_image: Album page image, float32 RGB [0, 1]
        detections: List of photo detections

    Returns:
        Visualization image with colored boxes and labels, float32 RGB [0, 1]
    """
    # Convert to uint8 for drawing
    vis = (page_image * 255).astype(np.uint8).copy()

    # Color palette for multiple photos (BGR for OpenCV)
    colors = [
        (0, 255, 0),    # Green
        (255, 0, 0),    # Blue
        (0, 0, 255),    # Red
        (255, 255, 0),  # Cyan
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Yellow
        (128, 255, 0),  # Spring green
        (255, 128, 0),  # Orange
    ]

    for i, detection in enumerate(detections):
        color = colors[i % len(colors)]

        # Draw corners as polygon
        corners_int = detection.corners.astype(np.int32)
        cv2.polylines(vis, [corners_int], isClosed=True, color=color, thickness=3)

        # Draw corner dots
        for corner in corners_int:
            cv2.circle(vis, tuple(corner), 8, (0, 0, 255), -1)  # Red dots

        # Draw bounding box (lighter, dashed-like)
        x1, y1, x2, y2 = detection.bbox
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness=1)

        # Label with photo number and confidence
        label = f"Photo {i+1} ({detection.confidence:.2f}) {detection.orientation}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2

        # Draw text background
        (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        cv2.rectangle(
            vis,
            (x1, y1 - text_h - 10),
            (x1 + text_w + 10, y1),
            color,
            -1  # Filled
        )

        # Draw text
        cv2.putText(
            vis,
            label,
            (x1 + 5, y1 - 5),
            font,
            font_scale,
            (255, 255, 255),  # White text
            thickness,
        )

    # Convert back to float32
    return vis.astype(np.float32) / 255.0
