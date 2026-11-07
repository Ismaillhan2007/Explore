"""Step 1: load the photo and estimate camera intrinsics. README section 2, step 1."""
from __future__ import annotations

import math

from .datatypes import Camera

DEFAULT_HFOV_DEG = 65.0   # typical phone main camera, used when there is no EXIF
MAX_LONG_SIDE = 1024      # work on a downscaled image
EXIF_IFD = 0x8769
TAG_F35 = 0xA405          # FocalLengthIn35mmFilm


def intrinsics_from_fov(width: int, height: int, hfov_deg: float = DEFAULT_HFOV_DEG) -> Camera:
    """Pinhole intrinsics for a given horizontal field of view."""
    fx = (width / 2) / math.tan(math.radians(hfov_deg) / 2)
    return Camera(fx=fx, fy=fx, cx=width / 2, cy=height / 2, width=width, height=height)


def intrinsics_from_f35(width: int, height: int, f35_mm: float) -> Camera:
    """Intrinsics from EXIF FocalLengthIn35mmFilm.

    The 35 mm equivalent refers to the 36 x 24 mm frame diagonal-matched, so it maps to
    the long side of the image: f_px = f35 / 36 * long_side.
    """
    fx = f35_mm / 36.0 * max(width, height)
    return Camera(fx=fx, fy=fx, cx=width / 2, cy=height / 2, width=width, height=height)


def hfov_of(cam: Camera) -> float:
    return math.degrees(2 * math.atan(cam.width / 2 / cam.fx))


def estimate_camera(photo_path: str, hfov_deg: float | None = None) -> tuple[Camera, object, str]:
    """Load the photo, downscale to MAX_LONG_SIDE, return (camera, rgb uint8 array, source).

    Priority: explicit hfov_deg (e.g. a known render camera) > EXIF 35 mm focal length > 65 deg guess.
    `source` says which one was used, for the report.
    """
    import numpy as np
    from PIL import Image, ImageOps

    img = Image.open(photo_path)
    f35 = img.getexif().get_ifd(EXIF_IFD).get(TAG_F35)
    img = ImageOps.exif_transpose(img).convert("RGB")
    scale = min(1.0, MAX_LONG_SIDE / max(img.size))
    if scale < 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    w, h = img.size

    if hfov_deg is not None:
        cam, source = intrinsics_from_fov(w, h, hfov_deg), f"given hfov {hfov_deg:.1f} deg"
    elif f35:
        cam, source = intrinsics_from_f35(w, h, float(f35)), f"EXIF 35 mm focal length {float(f35):.0f} mm"
    else:
        cam, source = intrinsics_from_fov(w, h), f"no EXIF, assumed hfov {DEFAULT_HFOV_DEG:.0f} deg"
    return cam, np.asarray(img), source
