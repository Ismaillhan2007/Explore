"""Step 2: monocular depth and back-projection to a point cloud. README section 2, step 2."""
from __future__ import annotations

from typing import Any

from .datatypes import Camera

DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"  # try -Base-hf if quality is poor


def estimate_depth(rgb: Any) -> Any:
    """Return depth[H, W] (relative units, larger = farther).

    TODO(B):
    - transformers.pipeline("depth-estimation", model=DEPTH_MODEL)
    - the model outputs relative inverse depth: convert to depth (1 / (d + eps))
    - resize to the image size; save a colour-mapped PNG to pipeline/debug/
    """
    raise NotImplementedError("step 2: estimate_depth")


def backproject(depth: Any, cam: Camera) -> Any:
    """Return points[H, W, 3] in camera space: X = (u-cx)Z/fx, Y = (v-cy)Z/fy, Z = depth.

    TODO(B): vectorise with numpy meshgrid.
    """
    raise NotImplementedError("step 2: backproject")
