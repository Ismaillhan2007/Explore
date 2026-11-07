"""Step 1: camera intrinsics from EXIF, or a phone-camera guess. README section 2, step 1."""
from __future__ import annotations

import math

from .datatypes import Camera

DEFAULT_HFOV_DEG = 65.0   # typical phone main camera
MAX_LONG_SIDE = 1024      # work on a downscaled image


def intrinsics_from_fov(width: int, height: int, hfov_deg: float = DEFAULT_HFOV_DEG) -> Camera:
    """Pinhole intrinsics for a given horizontal field of view. Works today."""
    fx = (width / 2) / math.tan(math.radians(hfov_deg) / 2)
    return Camera(fx=fx, fy=fx, cx=width / 2, cy=height / 2, width=width, height=height)


def intrinsics_from_f35(width: int, height: int, f35_mm: float) -> Camera:
    """Intrinsics from EXIF FocalLengthIn35mmFilm (36 mm wide full-frame equivalent)."""
    fx = f35_mm / 36.0 * width
    return Camera(fx=fx, fy=fx, cx=width / 2, cy=height / 2, width=width, height=height)


def estimate_camera(photo_path: str) -> tuple[Camera, object]:
    """Load the photo, downscale to MAX_LONG_SIDE, return (camera, rgb image).

    TODO(B):
    - open with Pillow, apply EXIF orientation (ImageOps.exif_transpose)
    - read FocalLengthIn35mmFilm (tag 0xA405); use intrinsics_from_f35 if present,
      else intrinsics_from_fov
    - compute intrinsics for the downscaled size
    """
    raise NotImplementedError("step 1: estimate_camera")
