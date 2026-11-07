"""Step 3: floor, walls, metric scale, wall colour, room shell. README section 2, step 3."""
from __future__ import annotations

from typing import Any

from .datatypes import Detection, Room

CAMERA_HEIGHT_M = 1.5     # phone held at chest height
RANSAC_ITERS = 500
RANSAC_THRESHOLD = 0.02   # relative units; tune on the demo photos
WALL_MAX_UP_DOT = 0.2     # |normal . up| below this = vertical plane
ROOM_SHELLS = {           # shell name -> floor size (width, depth) in metres; built by hand in Unity
    "RoomShell_A": (4.0, 5.0),
    "RoomShell_B": (3.0, 4.0),
}


def fit_room(points: Any, rgb: Any, detections: list[Detection]) -> Room:
    """Fit floor and walls, fix the scale, read the wall colour, choose a shell.

    TODO(B):
    1. RANSAC plane on points from the bottom third of the image; normal closest to -Y = floor
    2. remove floor inliers, RANSAC again for vertical planes, keep the 1-3 largest walls
    3. scale = CAMERA_HEIGHT_M / distance(origin, floor); cross-check with door/ceiling
    4. wall colour = median RGB of wall inliers not inside any detection mask -> "#rrggbb"
    5. build cam_to_world: flip Y, floor normal -> +Y, camera forward projected on floor -> +Z,
       floor centre -> origin
    6. choose the ROOM_SHELLS entry whose size best fits the floor/wall extent
    """
    raise NotImplementedError("step 3: fit_room")


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """0-255 channels to '#rrggbb'. Works today."""
    clamp = lambda c: max(0, min(255, round(c)))
    return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))
