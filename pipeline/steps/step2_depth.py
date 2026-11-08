"""Step 2: monocular depth and back-projection to a point cloud. README section 2, step 2."""
from __future__ import annotations

from typing import Any

from .datatypes import Camera

# Metric model: outputs depth in metres for indoor scenes, so scale is a measurement we can
# check (camera height, room size) instead of only an assumption.
DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"


def _device() -> str:
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


# The metric indoor model is trained on Hypersim (hfov 60 deg). It reads "how big things look"
# as distance, so a wider lens makes everything look farther. Correct by the ratio of
# normalised focal lengths (fx / image width).
TRAIN_HFOV_DEG = 60.0


def focal_correction(cam: Camera) -> float:
    """Multiply the model's depth by this to account for a lens wider/narrower than training."""
    import math
    train = 0.5 / math.tan(math.radians(TRAIN_HFOV_DEG) / 2)   # fx / width at 60 deg
    return (cam.fx / cam.width) / train


def estimate_depth(rgb: Any, cam: Camera | None = None, model_id: str = DEPTH_MODEL) -> Any:
    """Return depth[H, W] in metres (float32), same size as rgb.

    With `cam`, the depth is corrected for the photo's field of view (see focal_correction).
    """
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    device = _device()
    processor = AutoImageProcessor.from_pretrained(model_id)
    model = AutoModelForDepthEstimation.from_pretrained(model_id).to(device).eval()
    inputs = processor(images=Image.fromarray(rgb), return_tensors="pt").to(device)
    with torch.no_grad():
        predicted = model(**inputs).predicted_depth          # [1, h, w] metres
    depth = torch.nn.functional.interpolate(
        predicted.unsqueeze(1), size=rgb.shape[:2], mode="bicubic", align_corners=False
    )[0, 0]
    depth = np.clip(depth.float().cpu().numpy(), 0.05, None)
    if cam is not None:
        depth *= focal_correction(cam)
    return depth.astype(np.float32)


def backproject(depth: Any, cam: Camera) -> Any:
    """Return points[H, W, 3] in camera space (x right, y down, z forward), metres."""
    import numpy as np

    h, w = depth.shape
    u, v = np.meshgrid(np.arange(w, dtype=np.float32) + 0.5, np.arange(h, dtype=np.float32) + 0.5)
    x = (u - cam.cx) * depth / cam.fx
    y = (v - cam.cy) * depth / cam.fy
    return np.stack([x, y, depth], axis=-1)


def save_depth_png(depth: Any, path: str) -> None:
    """Colour-mapped depth for eyeballing (near = bright)."""
    import numpy as np
    from PIL import Image

    d = depth.astype(np.float64)
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    t = 1.0 - np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    rgb = np.stack([t ** 0.6, t ** 1.2, 0.35 + 0.65 * t ** 3], axis=-1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(path)
