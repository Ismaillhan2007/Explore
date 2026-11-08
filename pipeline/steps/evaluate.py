"""Grade pipeline output against a built room's answer key (scenes/*.json).

The rooms' Unity renders (docs/*-unity.png) are taken from a known camera, so every
answer-key object can be projected into the image and compared with what step 4 found.
"""
from __future__ import annotations

import math


def project(point, camera: dict, width: int, height: int):
    """Unity world point -> (u, v, depth) in pixels of a width x height image.

    camera = {"position": [x,y,z], "look_at": [x,y,z], "vfov_deg": f}, as Unity's
    Transform.LookAt + Camera.fieldOfView (vertical) in BuildXxx.cs. Returns None if behind.
    """
    c = camera["position"]; t = camera["look_at"]
    f = [t[i] - c[i] for i in range(3)]; n = math.sqrt(sum(v * v for v in f)); f = [v / n for v in f]
    up = (0.0, 1.0, 0.0)
    r = [up[1] * f[2] - up[2] * f[1], up[2] * f[0] - up[0] * f[2], up[0] * f[1] - up[1] * f[0]]  # Unity: Cross(up, fwd)
    n = math.sqrt(sum(v * v for v in r)); r = [v / n for v in r]
    u2 = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]]          # Cross(fwd, right)
    d = [point[i] - c[i] for i in range(3)]
    x, y, z = (sum(d[i] * r[i] for i in range(3)), sum(d[i] * u2[i] for i in range(3)), sum(d[i] * f[i] for i in range(3)))
    if z <= 0.05:
        return None
    fy = (height / 2) / math.tan(math.radians(camera["vfov_deg"]) / 2)
    return (width / 2 + fy * x / z, height / 2 - fy * y / z, z)


def truth_in_image(answer: dict, library: dict, width: int, height: int) -> list[dict]:
    """Answer-key objects with their projected centre pixel and whether they are in frame."""
    camera = library["rooms"][answer["room"]]["camera"]
    out = []
    for o in answer["objects"]:
        h = library["models"][o["model"]]["height_m"] * o.get("scale", 1.0)
        x, y, z = o["position"]
        pr = project((x, y + h / 2, z), camera, width, height)
        visible = pr is not None and 0 <= pr[0] < width and 0 <= pr[1] < height
        out.append({"label": o["label"], "model": o["model"], "position": o["position"],
                    "pixel": (round(pr[0]), round(pr[1])) if pr else None, "in_frame": visible,
                    "distance_m": round(pr[2], 2) if pr else None})
    return out


def decor_in_image(answer: dict, library: dict, width: int, height: int) -> list[dict]:
    """Baked look-alikes listed under "decor" in an answer key, projected like truth_in_image."""
    camera = library["rooms"][answer["room"]]["camera"]
    out = []
    for o in answer.get("decor", []):
        pr = project(o["center"], camera, width, height)
        # keep points slightly outside the frame: a decoration cut by the image edge can still be detected
        near = pr is not None and -0.1 * width <= pr[0] < 1.1 * width and -0.1 * height <= pr[1] < 1.1 * height
        out.append({"label": o["label"], "name": o["name"], "pixel": (round(pr[0]), round(pr[1])) if near else None})
    return out


def grade_detections(detections, truth: list[dict], margin_px: int = 6, decor: list[dict] | None = None) -> dict:
    """Match detections to in-frame answer-key objects: same label and the box covers the projected centre."""
    used, rows = set(), []
    for t in truth:
        if not t["in_frame"]:
            rows.append(dict(t, result="out of frame")); continue
        u, v = t["pixel"]
        hit = None
        for i, d in enumerate(detections):
            x0, y0, x1, y1 = d.box
            if i not in used and d.label == t["label"] and x0 - margin_px <= u <= x1 + margin_px and y0 - margin_px <= v <= y1 + margin_px:
                if hit is None or d.score > detections[hit].score:
                    hit = i
        if hit is not None:
            used.add(hit)
        rows.append(dict(t, result="found" if hit is not None else "missed",
                         score=round(detections[hit].score, 2) if hit is not None else None))
    extra, on_decor = [], []
    for i, d in enumerate(detections):
        if i in used:
            continue
        x0, y0, x1, y1 = d.box
        m = max(margin_px, 0.5 * max(x1 - x0, y1 - y0))   # looser for decor: only used to excuse, never to credit
        hit = next((t for t in decor or [] if t["pixel"] and t["label"] == d.label
                    and x0 - m <= t["pixel"][0] <= x1 + m and y0 - m <= t["pixel"][1] <= y1 + m), None)
        row = {"label": d.label, "score": round(d.score, 2), "box": d.box}
        (on_decor.append(dict(row, decor=hit["name"])) if hit else extra.append(row))
    in_frame = [r for r in rows if r["result"] != "out of frame"]
    return {"objects": rows, "extra_detections": extra, "decor_detections": on_decor,
            "found": sum(r["result"] == "found" for r in in_frame), "in_frame": len(in_frame),
            "false_detections": len(extra)}
