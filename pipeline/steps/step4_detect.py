"""Step 4: find our pickables in the image and outline them. README section 2, step 4.

Grounding DINO (open-vocabulary detector) finds boxes for text prompts built from the
pickable labels in model_library.json; SAM turns each box into a pixel mask.
Both are open-weights models loaded through `transformers` (no API key).
"""
from __future__ import annotations

from typing import Any

from .datatypes import Detection

DETECTOR_MODEL = "IDEA-Research/grounding-dino-tiny"
SAM_MODEL = "facebook/sam-vit-base"
MIN_SCORE = 0.30           # box score threshold
TEXT_THRESHOLD = 0.25
NMS_IOU = 0.5              # same-label boxes overlapping more than this are one object
MIN_BOX_FRACTION = 0.0001  # drop boxes smaller than 0.01 % of the image
MAX_BOX_FRACTION = 0.25    # ...or larger than 25 % (a "lamp" box covering the room is not our lamp)
MASK_ERODE_PX = 2

# What we say to the detector for each library label. Plain "lamp" also fires on floor
# lamps and wall sconces; "table lamp" is closer to our 0.57 m lamp.
PROMPTS = {"lamp": "table lamp", "mug": "mug", "book": "book", "box": "cardboard box"}


def build_prompt(labels: list[str]) -> str:
    """Grounding DINO prompt: lower-case phrases separated by ' . '."""
    return " . ".join(PROMPTS.get(l.lower(), l.lower()) for l in sorted(set(labels))) + " ."


def phrase_to_label(phrase: str, labels: list[str]) -> str | None:
    """Map the detector's matched phrase back to a library label."""
    phrase = phrase.lower().strip()
    for label in sorted(labels, key=len, reverse=True):
        p = PROMPTS.get(label, label)
        if phrase == p or p in phrase or label in phrase.split():
            return label
    return None


def iou(a: tuple, b: tuple) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def nms(dets: list[tuple[str, float, tuple]], thr: float = NMS_IOU) -> list[tuple[str, float, tuple]]:
    """Per-label non-maximum suppression on (label, score, box)."""
    keep: list[tuple[str, float, tuple]] = []
    for d in sorted(dets, key=lambda d: -d[1]):
        if all(k[0] != d[0] or iou(k[2], d[2]) < thr for k in keep):
            keep.append(d)
    return keep


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")


def _run(model, inputs, device):
    """Run on the GPU if possible, else fall back to CPU (some ops are missing on Apple MPS)."""
    import torch

    def move(v):
        if not hasattr(v, "to"):
            return v
        if getattr(v, "dtype", None) == torch.float64:   # Apple MPS has no float64
            v = v.float()
        return v.to(device)
    try:
        model.to(device)
        with torch.no_grad():
            return model(**{k: move(v) for k, v in inputs.items()}), device
    except (NotImplementedError, RuntimeError, TypeError):
        model.to("cpu")
        with torch.no_grad():
            return model(**inputs), "cpu"


def detect_boxes(image: Any, labels: list[str], min_score: float = MIN_SCORE) -> list[tuple[str, float, tuple]]:
    """Return [(label, score, (x0, y0, x1, y1))] in pixels of `image` (a PIL image)."""
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    processor = AutoProcessor.from_pretrained(DETECTOR_MODEL)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(DETECTOR_MODEL).eval()
    inputs = processor(images=image, text=build_prompt(labels), return_tensors="pt")
    outputs, _ = _run(model, inputs, _device())
    outputs = {k: v.cpu() if hasattr(v, "cpu") else v for k, v in outputs.items()}
    import warnings
    from types import SimpleNamespace
    warnings.filterwarnings("ignore", message=".*text_labels.*", category=FutureWarning)
    res = processor.post_process_grounded_object_detection(
        SimpleNamespace(**outputs), inputs["input_ids"], threshold=min_score, text_threshold=TEXT_THRESHOLD,
        target_sizes=[(image.height, image.width)])[0]
    phrases = res.get("text_labels", res.get("labels"))
    area = image.width * image.height
    dets = []
    for box, score, phrase in zip(res["boxes"].tolist(), res["scores"].tolist(), phrases):
        label = phrase_to_label(str(phrase), labels)
        frac = (box[2] - box[0]) * (box[3] - box[1]) / area
        if label and MIN_BOX_FRACTION <= frac <= MAX_BOX_FRACTION:
            dets.append((label, float(score), tuple(float(v) for v in box)))
    return nms(dets)


def segment(image: Any, boxes: list[tuple]) -> list[Any]:
    """One boolean mask [H, W] per box, using SAM with the box as the prompt."""
    import numpy as np
    from transformers import SamModel, SamProcessor

    if not boxes:
        return []
    processor = SamProcessor.from_pretrained(SAM_MODEL)
    model = SamModel.from_pretrained(SAM_MODEL).eval()
    inputs = processor(image, input_boxes=[[list(b) for b in boxes]], return_tensors="pt")
    outputs, _ = _run(model, dict(inputs, multimask_output=False), _device())
    masks = processor.image_processor.post_process_masks(
        outputs.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu())[0]
    out = []
    for m in masks[:, 0].numpy().astype(bool):
        if MASK_ERODE_PX:
            from PIL import Image, ImageFilter
            m = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(2 * MASK_ERODE_PX + 1))) > 127
        out.append(m)
    return out


def detect_objects(photo_path: str, labels: list[str], working_size: tuple[int, int] | None = None,
                   min_score: float = MIN_SCORE) -> list[Detection]:
    """Detect and outline pickables on the FULL-resolution photo (small mugs need the pixels).

    Boxes and masks are returned at `working_size` (width, height), the resolution steps 2-3 use.
    """
    import numpy as np
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(photo_path)).convert("RGB")
    dets = detect_boxes(image, labels, min_score)
    masks = segment(image, [d[2] for d in dets])
    W, H = working_size or image.size
    sx, sy = W / image.width, H / image.height
    out = []
    for (label, score, box), mask in zip(dets, masks):
        if (W, H) != image.size:
            mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize((W, H), Image.Resampling.NEAREST)) > 127
        out.append(Detection(label=label, score=score, mask=mask,
                             box=(round(box[0] * sx), round(box[1] * sy), round(box[2] * sx), round(box[3] * sy))))
    return out


def save_detections(rgb: Any, detections: list[Detection], path: str, truth: list[dict] | None = None) -> None:
    """Draw masks, boxes, labels and scores; optional answer-key points as white crosses."""
    import numpy as np
    from PIL import Image, ImageDraw
    colors = {"mug": (255, 90, 60), "book": (60, 160, 255), "lamp": (255, 210, 40), "box": (160, 90, 255)}
    out = rgb.astype(float).copy()
    for d in detections:
        c = np.array(colors.get(d.label, (255, 255, 255)), float)
        out[d.mask] = out[d.mask] * 0.4 + c * 0.6
    img = Image.fromarray(out.astype(np.uint8)); draw = ImageDraw.Draw(img)
    for d in detections:
        c = colors.get(d.label, (255, 255, 255))
        draw.rectangle(d.box, outline=c, width=2)
        draw.text((d.box[0] + 2, max(0, d.box[1] - 12)), f"{d.label} {d.score:.2f}", fill=c)
    for t in truth or []:
        u, v = t["pixel"]
        draw.line([(u - 6, v), (u + 6, v)], fill=(255, 255, 255), width=2)
        draw.line([(u, v - 6), (u, v + 6)], fill=(255, 255, 255), width=2)
    img.save(path)


def measure(det: Detection, points: Any, room: Any, cam: Any) -> dict | None:
    """Real-world size of a detection, in metres.

    Depth from a single photo is blurry at object edges, so instead of measuring the outline's
    3D points one by one, take ONE robust depth for the object (median inside its mask) and turn
    the box's pixel size into metres through the focal length: size = pixels * depth / f.
    base = height above the floor of the box's bottom-centre pixel at that depth.
    """
    import numpy as np
    p = points[det.mask]
    if len(p) < 10:
        return None
    z = float(np.median(p[:, 2]))
    x0, y0, x1, y1 = det.box
    s = room.scale
    M = room.cam_to_world
    u, v = (x0 + x1) / 2, y1
    bottom_cam = np.array([(u - cam.cx) / cam.fx * z, (v - cam.cy) / cam.fy * z, z])
    bottom = M[:3, :3] @ bottom_cam + M[:3, 3]
    centre = np.median(p @ M[:3, :3].T + M[:3, 3], axis=0)
    height_m, width_m = (y1 - y0) * z / cam.fy * s, (x1 - x0) * z / cam.fx * s
    return {"height_m": height_m, "width_m": width_m, "aspect": height_m / max(width_m, 1e-6),
            "base_m": float(bottom[1]), "center": [float(c) for c in centre]}


def size_check(detections: list[Detection], points: Any, room: Any, library: dict, cam: Any) -> tuple[list[Detection], list[dict]]:
    """Keep detections whose measured size fits the object's `plausible` ranges in model_library.json.

    Returns (kept, rejected-with-reasons). Detections without rules or without enough 3D points are kept.
    """
    rules = {m["label"]: m.get("plausible") for m in library["models"].values()}
    kept, rejected = [], []
    for d in detections:
        size = measure(d, points, room, cam)
        rule = rules.get(d.label)
        if not size or not rule:
            kept.append(d); continue
        bad = [f"{k} {size[k]:.2f} not in {lo}-{hi}" for k, (lo, hi) in rule.items() if not lo <= size[k] <= hi]
        d.size = size
        (rejected.append({"label": d.label, "score": round(d.score, 2), "box": d.box, "why": "; ".join(bad)})
         if bad else kept.append(d))
    return kept, rejected


# Second opinion: CLIP compares each candidate crop with its label and with look-alikes that
# have the same size (a plant pot or candle next to a mug, a laptop next to a book).
CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_MIN_OWN = 0.35   # and CLIP must be at least this sure of the object's own label
LOOKALIKES = {
    "mug": ["a plant pot", "a small potted plant", "a candle", "a candle holder", "a drinking glass", "a vase", "a bowl", "a jar"],
    # Not "a tray", "a tablet" or "a laptop": CLIP confuses dark closed books with all three, and missing a
    # real book is worse for us than calling a laptop a book (the size check still applies).
    "book": ["a cardboard box", "a cushion", "a picture frame"],
    # Not "a floor lamp" or "a chair": CLIP judges the padded crop, and next to a TV or a chair it
    # called our table lamp a floor lamp (0.32 vs 0.16) and then a chair (0.37 vs 0.24). Geometry
    # rejects both instead: floor lamps are too tall or a tall thin box (aspect), chairs stand on
    # the floor (a table lamp's base is >= 0.25 m up).
    "lamp": ["a potted plant", "a vase", "a wall light"],
}
PHRASES = {"mug": ["a coffee mug", "a cup"], "book": ["a book", "a closed book lying flat", "a stack of books"],
           "lamp": ["a table lamp with a lampshade"]}


def verify_with_clip(image: Any, detections: list[Detection], scale_xy: tuple[float, float],
                     pad: float = 0.6, min_side: int = 96) -> tuple[list[Detection], list[dict]]:
    """Keep a detection only if CLIP rates its crop closer to its own label than to every look-alike.

    image is the full-resolution PIL image; boxes are in working pixels, scale_xy maps them back.
    Crops get `pad` of context around the box and are upscaled to at least `min_side` px.
    """
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    todo = [d for d in detections if d.label in LOOKALIKES]
    if not todo:
        return detections, []
    model = CLIPModel.from_pretrained(CLIP_MODEL).eval(); proc = CLIPProcessor.from_pretrained(CLIP_MODEL)
    kept, rejected = [d for d in detections if d.label not in LOOKALIKES], []
    for d in todo:
        x0, y0, x1, y1 = (d.box[0] / scale_xy[0], d.box[1] / scale_xy[1], d.box[2] / scale_xy[0], d.box[3] / scale_xy[1])
        w, h = x1 - x0, y1 - y0
        crop = image.crop((max(0, x0 - pad * w), max(0, y0 - pad * h), min(image.width, x1 + pad * w), min(image.height, y1 + pad * h)))
        if min(crop.size) < min_side:
            k = min_side / min(crop.size)
            crop = crop.resize((round(crop.width * k), round(crop.height * k)), Image.Resampling.BICUBIC)
        own, others = PHRASES[d.label], LOOKALIKES[d.label]
        inputs = proc(text=own + others, images=crop, return_tensors="pt", padding=True)
        with torch.no_grad():
            probs = model(**inputs).logits_per_image.softmax(dim=-1)[0].tolist()
        p_own = sum(probs[:len(own)]); best_other = max(range(len(others)), key=lambda i: probs[len(own) + i])
        if p_own >= probs[len(own) + best_other] and p_own >= CLIP_MIN_OWN:
            d.clip = round(p_own, 2); kept.append(d)
        else:
            rejected.append({"label": d.label, "score": round(d.score, 2), "box": d.box,
                             "why": (f"CLIP: looks more like {others[best_other]} ({probs[len(own) + best_other]:.2f} vs {p_own:.2f})"
                                     if p_own < probs[len(own) + best_other] else f"CLIP: only {p_own:.2f} sure it is a {d.label}")})
    return kept, rejected
