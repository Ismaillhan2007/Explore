"""Step 4: open-vocabulary detection + SAM 2 masks. README section 2, step 4."""
from __future__ import annotations

from typing import Any

from .datatypes import Detection

DETECTOR_MODEL = "IDEA-Research/grounding-dino-tiny"  # or an OWLv2 / YOLO-World model
SAM_MODEL = "facebook/sam2.1-hiera-small"
MIN_SCORE = 0.35
MIN_MASK_FRACTION = 0.002   # drop masks smaller than 0.2 % of the image
MASK_ERODE_PX = 3


def build_prompt(labels: list[str]) -> str:
    """Grounding DINO prompt: lower-case labels separated by ' . '. Works today."""
    return " . ".join(sorted({l.lower() for l in labels})) + " ."


def detect_objects(rgb: Any, labels: list[str]) -> list[Detection]:
    """Detect only pickables we have models for, then segment each box.

    Static furniture is baked into the room (PR #4), so it is not detected as an object.

    TODO(B):
    - run the detector with build_prompt(labels); keep score >= MIN_SCORE; per-label NMS
    - SAM 2 with each box as prompt -> mask; erode by MASK_ERODE_PX
    - drop masks below MIN_MASK_FRACTION and labels not in `labels`
    - save a mask overlay PNG to pipeline/debug/
    """
    raise NotImplementedError("step 4: detect_objects")
