"""Step 6: choose a library prefab and a scale per object. README section 2, step 6."""
from __future__ import annotations

from typing import Any

from .datatypes import Placement, SceneObject

SCALE_MIN, SCALE_MAX = 0.7, 1.4


def clamp_scale(measured_height_m: float, model_height_m: float) -> tuple[float, bool]:
    """Return (scale, ok). Out-of-range ratios are treated as measurement errors -> 1.0. Works today."""
    if model_height_m <= 0 or measured_height_m <= 0:
        return 1.0, False
    ratio = measured_height_m / model_height_m
    if SCALE_MIN <= ratio <= SCALE_MAX:
        return round(ratio, 2), True
    return 1.0, False


def match_models(placements: list[Placement], rgb: Any, library: dict) -> list[SceneObject]:
    """Pick the best library model for each placement and compute its scale.

    `scale` is relative to the model's real height_m (the loader fits each instance to
    height_m * scale), so 1.0 = a typical object of that kind.

    TODO(B):
    - candidates = library models with the same label, kind "pickable", status "available"
    - several candidates: CLIP (open_clip ViT-B/32) similarity between the masked crop and
      each model's thumbnail; keep the best
    - scale via clamp_scale(placement.size[1], model["height_m"]); log when not ok
    """
    raise NotImplementedError("step 6: match_models")
