"""Step 3: floor, walls, metric scale, wall tint, room. README section 2, step 3."""
from __future__ import annotations

from typing import Any

from .datatypes import Detection, Room

# Same camera height PR #4 used for room 1's reference camera (RenderedRoom, y = 1.85 m).
# Cross-check per photo: a phone held at chest height is closer to 1.4-1.6 m.
CAMERA_HEIGHT_M = 1.85
RANSAC_ITERS = 500
RANSAC_THRESHOLD = 0.02   # relative units; tune on the demo photos
WALL_MAX_UP_DOT = 0.2     # |normal . up| below this = vertical plane


def fit_room(points: Any, rgb: Any, detections: list[Detection], library: dict) -> Room:
    """Fit floor and walls, fix the scale, estimate the wall tint, choose a room.

    TODO(B):
    1. RANSAC plane on points from the bottom third of the image; normal closest to -Y = floor
    2. remove floor inliers, RANSAC again for vertical planes, keep the 1-3 largest walls
    3. scale = CAMERA_HEIGHT_M / distance(origin, floor); cross-check against the room's
       known size_m in model_library.json when the room already exists (room 1)
    4. wall tint: rooms are baked (PR #4), wallColor MULTIPLIES the baked texture.
       Default to the room's default_tint ("#ffffff" = unchanged). Only emit another tint
       if the photo's wall is clearly a different colour than the baked one.
    5. build cam_to_world: flip Y, floor normal -> +Y, camera forward projected on floor -> +Z,
       floor centre -> origin
    6. room: for an existing room (RenderedRoom) use it; a new room needs a hand-built
       Blender room first (tools/room/), then an entry in model_library.json
    """
    raise NotImplementedError("step 3: fit_room")


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """0-255 channels to '#rrggbb'. Works today."""
    clamp = lambda c: max(0, min(255, round(c)))
    return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))
