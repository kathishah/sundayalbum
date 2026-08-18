"""Color restoration package for aged photo recovery.

This package provides tools for restoring color and contrast to faded, yellowed,
or discolored photos from old albums.
"""

from src.color.white_balance import (
    auto_white_balance,
    assess_white_balance_quality,
)

from src.color.deyellow import (
    remove_yellowing,
    remove_yellowing_adaptive,
    detect_intentional_warmth,
)

from src.color.restore import (
    restore_fading,
    restore_fading_conservative,
    restore_fading_aggressive,
    assess_fading,
)

from src.color.enhance import (
    enhance,
    enhance_adaptive,
    enhance_conservative,
    enhance_aggressive,
    measure_sharpness,
    assess_enhancement_need,
)

__all__ = [
    # White balance
    'auto_white_balance',
    'assess_white_balance_quality',
    # Deyellowing
    'remove_yellowing',
    'remove_yellowing_adaptive',
    'detect_intentional_warmth',
    # Fade restoration
    'restore_fading',
    'restore_fading_conservative',
    'restore_fading_aggressive',
    'assess_fading',
    # Enhancement
    'enhance',
    'enhance_adaptive',
    'enhance_conservative',
    'enhance_aggressive',
    'measure_sharpness',
    'assess_enhancement_need',
]
