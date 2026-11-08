"""Step 5: put each detected pickable at a 3D position on the right surface. README section 2, step 5.

Two modes:

* **Built room with a reference camera** (`model_library.json` rooms.<room>.camera). Each built room
  was modelled from its photo, so that camera is where the photo was taken. A pixel then gives an
  exact 3D position by geometry alone: follow the ray through the centre of the object's box until
  it reaches the height of a surface top plus half the object's height. No depth estimate is used
  for the position (single-photo depth stretched the living rooms by 13-21 %); depth (step 4's
  measured base height) only helps pick between surfaces.
* **Unknown room**: use step 4's depth-based centre and base height in step 3's room frame.
"""
from __future__ import annotations

import math
from typing import Any

from .datatypes import Detection, Placement, Room

SURFACE_MARGIN_M = 0.05     # a ray may land this far outside a surface's footprint and still count
BASE_TOLERANCE_M = 0.20     # step 4's measured base height must be this close to the surface top


def resting_surface(x: float, z: float, surfaces: dict) -> tuple[str, float]:
    """Highest known static surface under (x, z), from model_library.json rooms.*.surfaces.

    Returns (surface name, top_y). Falls back to the floor.
    """
    best = ("floor", 0.0)
    for name, s in surfaces.items():
        if name.startswith("_"):
            continue
        if inside(x, z, s, 0.0) and s["top_y"] > best[1]:
            best = (name, s["top_y"])
    return best


def inside(x: float, z: float, s: dict, margin: float) -> bool:
    cx, cz = s["center"]
    if s["shape"] == "circle":
        return (x - cx) ** 2 + (z - cz) ** 2 <= (s["radius"] + margin) ** 2
    w, d = s["size"]
    return abs(x - cx) <= w / 2 + margin and abs(z - cz) <= d / 2 + margin


def clamp_onto(x: float, z: float, s: dict, half: float) -> tuple[float, float]:
    """Move (x, z) the least amount so a footprint of half-size `half` stays on surface s."""
    cx, cz = s["center"]
    if s["shape"] == "circle":
        r = max(0.0, s["radius"] - half); dx, dz = x - cx, z - cz; dist = math.hypot(dx, dz)
        return (x, z) if dist <= r else (cx + dx / dist * r, cz + dz / dist * r)
    w, d = s["size"]
    return (min(max(x, cx - w / 2 + half), cx + w / 2 - half), min(max(z, cz - d / 2 + half), cz + d / 2 - half))


def camera_basis(camera: dict) -> tuple[list, list, list, list]:
    """(position, right, up, forward) of a Unity camera that looks at camera['look_at'] (Transform.LookAt)."""
    c = camera["position"]; t = camera["look_at"]
    f = [t[i] - c[i] for i in range(3)]; n = math.sqrt(sum(v * v for v in f)); f = [v / n for v in f]
    r = [f[2], 0.0, -f[0]]                                   # Cross(up, forward) with up = (0, 1, 0)
    n = math.hypot(r[0], r[2]); r = [r[0] / n, 0.0, r[2] / n]
    u = [f[1] * r[2] - f[2] * r[1], f[2] * r[0] - f[0] * r[2], f[0] * r[1] - f[1] * r[0]]
    return c, r, u, f


def pixel_ray(u_px: float, v_px: float, camera: dict, width: int, height: int) -> tuple[list, list]:
    """World-space ray (origin, unit direction) through pixel (u, v) of a width x height image."""
    c, r, up, f = camera_basis(camera)
    fy = (height / 2) / math.tan(math.radians(camera["vfov_deg"]) / 2)
    x, y = (u_px - width / 2) / fy, -(v_px - height / 2) / fy
    d = [f[i] + x * r[i] + y * up[i] for i in range(3)]
    n = math.sqrt(sum(v * v for v in d))
    return list(c), [v / n for v in d]


def ray_at_height(origin: list, direction: list, y: float) -> tuple[float, float, float] | None:
    """Where the ray crosses the horizontal plane at height y: (x, z, distance). None if never (in front)."""
    if abs(direction[1]) < 1e-6:
        return None
    t = (y - origin[1]) / direction[1]
    if t <= 0:
        return None
    return origin[0] + t * direction[0], origin[2] + t * direction[2], t


def face_camera_yaw(x: float, z: float, camera_pos: list) -> float:
    """rotationY (degrees) that turns the model's +Z toward the camera, as seen from above."""
    return math.degrees(math.atan2(camera_pos[0] - x, camera_pos[2] - z)) % 360


def place_with_camera(d: Detection, model: dict, room_info: dict, width: int, height: int) -> Placement | None:
    """Built-room mode: ray through the box centre, onto the nearest surface it can rest on."""
    cam = room_info["camera"]
    u, v = (d.box[0] + d.box[2]) / 2, (d.box[1] + d.box[3]) / 2
    origin, direction = pixel_ray(u, v, cam, width, height)
    h = model["height_m"]
    half = min(model.get("footprint_m", [0.1, 0.1])) / 2
    measured_base = d.size["base_m"] if d.size else None
    surfaces = {k: s for k, s in room_info.get("surfaces", {}).items() if not k.startswith("_")}
    options = []
    for name, s in surfaces.items():
        hit = ray_at_height(origin, direction, s["top_y"] + h / 2)
        if hit is None or not inside(hit[0], hit[1], s, SURFACE_MARGIN_M):
            continue
        base_ok = measured_base is None or abs(measured_base - s["top_y"]) <= BASE_TOLERANCE_M
        options.append((not base_ok, hit[2], name, s, hit))     # prefer base match, then the nearest hit
    if not options:
        return None
    _, dist, name, s, (x, z, _) = sorted(options, key=lambda o: (o[0], o[1]))[0]
    x, z = clamp_onto(x, z, s, half)
    fy = (height / 2) / math.tan(math.radians(cam["vfov_deg"]) / 2)
    size = ((d.box[2] - d.box[0]) * dist / fy, (d.box[3] - d.box[1]) * dist / fy)   # metres, from the exact distance
    p = Placement(label=d.label, position=(x, s["top_y"], z), rotation_y=face_camera_yaw(x, z, cam["position"]),
                  size=(size[0], size[1], size[0]), detection=d)
    p.surface = name
    p.view_down_deg = math.degrees(math.asin(max(-1.0, min(1.0, -direction[1]))))
    return p


def place_from_depth(d: Detection, room: Room, surfaces: dict) -> Placement | None:
    """Unknown-room mode: step 4's depth-based centre and base height in step 3's room frame."""
    if not d.size:
        return None
    x, _, z = d.size["center"]
    name, top = resting_surface(x, z, surfaces) if surfaces else ("measured", max(0.0, d.size["base_m"]))
    p = Placement(label=d.label, position=(x, top, z), rotation_y=0.0,
                  size=(d.size["width_m"], d.size["height_m"], d.size["width_m"]), detection=d)
    p.surface = name
    return p


def place_objects(detections: list[Detection], room: Room, room_info: dict, library: dict,
                  image_size: tuple[int, int]) -> list[Placement]:
    """One placement per detection; same-label placements closer than 10 cm are merged (best score wins)."""
    by_label = {m["label"]: m for m in library["models"].values() if m.get("kind") == "pickable"}
    use_camera = "camera" in room_info and "look_at" in room_info["camera"]
    out: list[Placement] = []
    for d in sorted(detections, key=lambda d: -d.score):
        model = by_label.get(d.label)
        if model is None:
            continue
        p = (place_with_camera(d, model, room_info, *image_size) if use_camera
             else place_from_depth(d, room, room_info.get("surfaces", {})))
        if p is None:
            continue
        if any(q.label == p.label and math.hypot(q.position[0] - p.position[0], q.position[2] - p.position[2]) < 0.10 for q in out):
            continue
        out.append(p)
    return out
