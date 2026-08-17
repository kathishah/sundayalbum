"""Glare detection and removal for glossy prints and plastic sleeves."""

from src.glare.detector import detect_glare, draw_glare_overlay, GlareDetection, GlareType
from src.glare.confidence import compute_glare_confidence
from src.glare.remover_single import remove_glare_single, GlareResult

__all__ = [
    "detect_glare",
    "draw_glare_overlay",
    "GlareDetection",
    "GlareType",
    "compute_glare_confidence",
    "remove_glare_single",
    "GlareResult",
]
