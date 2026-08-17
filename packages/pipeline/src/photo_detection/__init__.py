"""Photo detection and splitting module."""

from src.photo_detection.detector import (
    PhotoDetection,
    detect_photos,
    draw_photo_detections,
)
from src.photo_detection.splitter import split_photos
from src.photo_detection.classifier import classify_region, RegionType

__all__ = [
    "PhotoDetection",
    "detect_photos",
    "draw_photo_detections",
    "split_photos",
    "classify_region",
    "RegionType",
]
