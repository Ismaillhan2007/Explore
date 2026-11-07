"""Step 5: 3D position, resting surface, size and yaw per object. README section 2, step 5."""
from __future__ import annotations

from typing import Any

from .datatypes import Detection, Placement, Room

FLOOR_LABELS = {"chair", "table", "sofa", "lamp", "plant", "bin"}  # always rest on the floor


def place_objects(detections: list[Detection], points: Any, room: Room) -> list[Placement]:
    """Turn each 2D mask into a world-space placement.

    TODO(B):
    - points inside the mask, times room.scale, through room.cam_to_world
    - position = median; FLOOR_LABELS snap to y = 0, small objects snap to the top of the
      closest larger object below them (else the floor)
    - size = extent of the points along world X/Y/Z
    - rotation_y v1: face away from the nearest wall, else face the camera
    - rotation_y v2 (if time): best of 12 rendered yaws by CLIP/DINOv2 similarity
    """
    raise NotImplementedError("step 5: place_objects")
