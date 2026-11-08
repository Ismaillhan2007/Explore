"""Step 6: choose a library prefab and a scale per placement. README section 2, step 6."""
from __future__ import annotations

from .datatypes import Placement, SceneObject

SCALE_MIN, SCALE_MAX = 0.7, 1.4


def clamp_scale(measured_m: float, model_m: float) -> tuple[float, bool]:
    """Return (scale, ok). Out-of-range ratios are treated as measurement errors -> 1.0."""
    if model_m <= 0 or measured_m <= 0:
        return 1.0, False
    ratio = measured_m / model_m
    if SCALE_MIN <= ratio <= SCALE_MAX:
        return round(ratio, 2), True
    return 1.0, False


def expected_box(p: Placement, m: dict) -> tuple[float, float]:
    """(measured box size, what the real model's box would measure from this viewpoint), in metres.

    Seen from above, a box around an object also contains its top: apparent height is about
    height * cos(a) + depth * sin(a) for a view a degrees below horizontal. A book lying flat is
    measured by its width instead; depending on how it is turned that is between its long side and
    its diagonal, so the average of the two is used.
    """
    import math
    fp = m.get("footprint_m", [m["height_m"], m["height_m"]])
    if m.get("scale_from") == "width":
        return p.size[0], (max(fp) + math.hypot(*fp)) / 2
    a = math.radians(p.view_down_deg)
    return p.size[1], m["height_m"] * math.cos(a) + min(fp) * math.sin(a)


def candidates(label: str, library: dict) -> list[tuple[str, dict]]:
    return [(name, m) for name, m in library["models"].items()
            if m.get("label") == label and m.get("kind") == "pickable" and m.get("status") == "available"]


def match_models(placements: list[Placement], library: dict) -> tuple[list[SceneObject], list[str]]:
    """Model per placement (a lookup while each label has one model) and its scale.

    `scale` is relative to the model's real size: the loader fits each instance to height_m * scale.
    Placement.size is (width, height, depth) in metres as measured in step 5.
    Returns (scene objects, warnings).
    """
    objects, warnings = [], []
    for p in placements:
        options = candidates(p.label, library)
        if not options:
            warnings.append(f"no available model for '{p.label}'"); continue
        if len(options) > 1:
            warnings.append(f"{len(options)} models for '{p.label}', taking {options[0][0]} (no thumbnail matching yet)")
        name, m = options[0]
        measured, real = expected_box(p, m)
        scale, ok = clamp_scale(measured, real)
        if not ok:
            warnings.append(f"{p.label}: measured {measured:.2f} m vs real {real:.2f} m is out of range, scale set to 1.0")
        objects.append(SceneObject(label=p.label, model=name, position=p.position, rotation_y=p.rotation_y, scale=scale))
    return objects, warnings
