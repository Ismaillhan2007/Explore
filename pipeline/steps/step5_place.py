"""Step 5: 3D position, resting surface, size and yaw per pickable. README section 2, step 5."""
from __future__ import annotations

from typing import Any

from .datatypes import Detection, Placement, Room


def resting_surface(x: float, z: float, surfaces: dict) -> tuple[str, float]:
    """Highest known static surface under (x, z), from model_library.json rooms.*.surfaces.

    Returns (surface name, top_y). Falls back to the floor. Works today.
    """
    best = ("floor", 0.0)
    for name, s in surfaces.items():
        if name.startswith("_"):
            continue
        cx, cz = s["center"]
        if s["shape"] == "circle":
            inside = (x - cx) ** 2 + (z - cz) ** 2 <= s["radius"] ** 2
        else:
            w, d = s["size"]
            inside = abs(x - cx) <= w / 2 and abs(z - cz) <= d / 2
        if inside and s["top_y"] > best[1]:
            best = (name, s["top_y"])
    return best


def place_objects(detections: list[Detection], points: Any, room: Room, surfaces: dict) -> list[Placement]:
    """Turn each pickable's 2D mask into a world-space placement.

    Static furniture is not placed here: it is baked into the room (PR #4).

    TODO(B):
    - points inside the mask, times room.scale, through room.cam_to_world
    - position x, z = median of the points; y = resting_surface(x, z, surfaces)[1]
    - size = extent of the points along world X/Y/Z
    - rotation_y v1: face the camera; v2 (if time): best of 12 rendered yaws by CLIP similarity
    """
    raise NotImplementedError("step 5: place_objects")
