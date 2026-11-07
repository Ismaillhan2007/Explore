"""Step 3: floor, walls, metric scale, room frame, wall tint. README section 2, step 3.

Input is the camera-space point cloud from step 2 (x right, y down, z forward, metres).
Output is a Room whose cam_to_world maps camera space to Unity world space
(x right, y up, z = away from the camera, origin on the floor).
"""
from __future__ import annotations

import math
from typing import Any

from .datatypes import Detection, Plane, Room

STRIDE = 4                # use every 4th pixel in each direction (~60k points)
MAX_DEPTH_M = 9.0         # ignore far points (window, outside)
FLOOR_ROWS = 0.45         # floor candidates come from the bottom 45 % of the image
FLOOR_MAX_TILT_DEG = 50   # camera pitch can be large; floor normal must be within this of camera up
PLANE_THRESHOLD_M = 0.04
WALL_THRESHOLD_M = 0.08   # mono depth is noisier on far walls
WALL_MIN_POINTS = 250
WALL_TRIES = 6
WALL_MIN_TOP_M = 1.9      # a wall's points reach up high; most furniture doesn't
WALL_MIN_EXTENT_M = 1.0   # and run at least 1 m along the floor
RANSAC_ITERS = 600


# ---------------------------------------------------------------- geometry helpers (tested)

def fit_plane_svd(p: Any) -> tuple[Any, float]:
    """Least-squares plane through points p[N,3] -> (unit normal n, d) with n.p + d = 0."""
    import numpy as np
    c = p.mean(axis=0)
    n = np.linalg.svd(p - c, full_matrices=False)[2][-1]
    return n, float(-n @ c)


def ransac_plane(p: Any, threshold: float, iters: int, normal_ok, rng) -> tuple[Any, float, Any] | None:
    """Best plane by inlier count among candidates whose normal passes normal_ok(n)."""
    import numpy as np
    best, best_count = None, 0
    idx = rng.integers(0, len(p), size=(iters, 3))
    for a, b, c in idx:
        n = np.cross(p[b] - p[a], p[c] - p[a])
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n = n / norm
        if not normal_ok(n):
            continue
        d = -n @ p[a]
        count = int((np.abs(p @ n + d) < threshold).sum())
        if count > best_count:
            best, best_count = (n, d), count
    if best is None:
        return None
    n, d = best
    inliers = np.abs(p @ n + d) < threshold
    n, d = fit_plane_svd(p[inliers])          # refine on all inliers
    inliers = np.abs(p @ n + d) < threshold
    return n, d, inliers


def ransac_line_2d(q: Any, threshold: float, iters: int, rng) -> tuple[Any, float, Any] | None:
    """Best 2D line n.q + c = 0 (unit n) through points q[N,2] by inlier count."""
    import numpy as np
    if len(q) < 2:
        return None
    best, best_count = None, 0
    for a, b in rng.integers(0, len(q), size=(iters, 2)):
        t = q[b] - q[a]
        norm = np.linalg.norm(t)
        if norm < 1e-6:
            continue
        n = np.array([-t[1], t[0]]) / norm
        c = -n @ q[a]
        count = int((np.abs(q @ n + c) < threshold).sum())
        if count > best_count:
            best, best_count = (n, c), count
    if best is None:
        return None
    n, c = best
    inl = np.abs(q @ n + c) < threshold
    m = q[inl].mean(axis=0)                    # refine: total least squares on inliers
    direction = np.linalg.svd(q[inl] - m, full_matrices=False)[2][0]
    n = np.array([-direction[1], direction[0]])
    c = -n @ m
    return n, float(c), np.abs(q @ n + c) < threshold


def camera_frame(floor_n: Any) -> tuple[Any, Any, Any]:
    """World axes in camera coordinates: (right, up, forward). up = floor normal."""
    import numpy as np
    u = floor_n / np.linalg.norm(floor_n)
    f = np.array([0.0, 0.0, 1.0]) - u[2] * u   # camera forward, flattened onto the floor
    f /= np.linalg.norm(f)
    r = np.cross(f, u)                         # camera space is right-handed with y down
    return r, u, f


def to_world(p: Any, r: Any, u: Any, f: Any, cam_height: float) -> Any:
    """Camera-space points -> floor-aligned frame under the camera (y = height above floor)."""
    import numpy as np
    return np.stack([p @ r, p @ u + cam_height, p @ f], axis=-1)


def find_ceiling(heights: Any, cam_h: float, band: float = 0.05, min_points: int = 500) -> float | None:
    """Height of the ceiling: the densest 10 cm band of points above the camera, if it is dense enough."""
    import numpy as np
    high = np.sort(heights[heights > cam_h + 0.3])
    if len(high) < min_points:
        return None
    counts = np.searchsorted(high, high + 2 * band) - np.arange(len(high))
    i = int(np.argmax(counts))
    if counts[i] < min_points:
        return None
    return float(np.median(high[i:i + counts[i]]))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """0-255 channels to '#rrggbb'."""
    clamp = lambda c: max(0, min(255, round(c)))
    return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))


# ---------------------------------------------------------------- step 3

def fit_room(points: Any, rgb: Any, detections: list[Detection], library: dict,
             room_name: str | None = None, camera_height: float | None = None, seed: int = 0) -> Room:
    """Floor -> scale -> world frame -> walls -> yaw/origin -> tint. See README step 3.

    room_name: a room from model_library.json this photo shows (room 1 = "RenderedRoom").
      Its known size and camera are used only to place the origin and to grade the result.
    camera_height: force the scale so the camera is this high (otherwise trust metric depth).
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    H, W = points.shape[:2]
    p = points[::STRIDE, ::STRIDE].reshape(-1, 3)
    colors = rgb[::STRIDE, ::STRIDE].reshape(-1, 3).astype(np.float64)
    rows = np.repeat(np.arange(0, H, STRIDE), len(range(0, W, STRIDE)))
    mask_obj = np.zeros(len(p), bool)
    for det in detections:
        mask_obj |= det.mask[::STRIDE, ::STRIDE].reshape(-1)
    keep = (p[:, 2] < MAX_DEPTH_M) & np.isfinite(p).all(axis=1)
    p, colors, rows, mask_obj = p[keep], colors[keep], rows[keep], mask_obj[keep]

    # 1. Floor: RANSAC on the bottom of the image, normal near camera-up (-y).
    up_cam = np.array([0.0, -1.0, 0.0])
    cos_tilt = math.cos(math.radians(FLOOR_MAX_TILT_DEG))
    cand = rows > H * (1 - FLOOR_ROWS)
    res = ransac_plane(p[cand], PLANE_THRESHOLD_M, RANSAC_ITERS, lambda n: abs(n @ up_cam) > cos_tilt, rng)
    if res is None:
        raise RuntimeError("step 3: no floor plane found")
    n, d, _ = res
    if n @ up_cam < 0:
        n, d = -n, -d
    floor_in = np.abs(p @ n + d) < PLANE_THRESHOLD_M
    cam_h_measured = float(d)                  # distance from camera (origin) to the floor
    residual = float(np.sqrt(np.mean((p[floor_in] @ n + d) ** 2)))
    # world-up in camera space has a negative z when the camera looks down
    pitch_deg = -math.degrees(math.asin(np.clip(n[2], -1, 1)))  # >0: camera looks down

    # 2. Scale: metric depth by default; optionally force a camera height.
    scale = 1.0 if camera_height is None else camera_height / cam_h_measured
    p = p * scale
    d *= scale
    cam_h = float(d)

    # 3. Floor-aligned frame under the camera.
    r, u, f = camera_frame(n)
    w = to_world(p, r, u, f, cam_h)

    # 4a. Ceiling: the height above the camera where most points pile up (a horizontal plane).
    ceiling = find_ceiling(w[:, 1], cam_h)
    top_cut = (ceiling - 0.15) if ceiling else cam_h + 0.6

    # 4b. Walls: vertical structures that reach high, fitted as lines in the floor plan.
    walls, rejected, used = [], [], floor_in.copy()
    tall = (w[:, 1] > 0.15) & (w[:, 1] < top_cut)       # stay below the ceiling
    for _ in range(WALL_TRIES):
        pool = np.where(tall & ~used)[0]
        if len(pool) < WALL_MIN_POINTS:
            break
        line = ransac_line_2d(w[pool][:, [0, 2]], WALL_THRESHOLD_M, RANSAC_ITERS, rng)
        if line is None:
            break
        ln, lc, inl = line
        members = pool[inl]
        used[members] = True
        along = w[members][:, [0, 2]] @ np.array([ln[1], -ln[0]])
        extent = np.percentile(along, 95) - np.percentile(along, 5)
        top = float(np.percentile(w[members, 1], 90))
        if len(members) < WALL_MIN_POINTS or top < WALL_MIN_TOP_M or extent < WALL_MIN_EXTENT_M:
            rejected.append({"points": int(len(members)), "top_m": round(top, 2), "extent_m": round(float(extent), 2),
                             "distance_m": round(abs(lc), 2)})
            continue                            # furniture side, too small or too low
        walls.append({"n": ln, "c": lc, "idx": members})

    # 5. Yaw: rotate the floor plan so the largest wall is axis-aligned (rooms are rectangular).
    yaw = 0.0
    if walls:
        big = max(walls, key=lambda x: len(x["idx"]))
        ang = math.atan2(big["n"][0], big["n"][1])           # normal angle from +z
        yaw = (ang + math.pi / 4) % (math.pi / 2) - math.pi / 4  # rotating by yaw makes the normal angle a multiple of 90 deg
    cy, sy = math.cos(yaw), math.sin(yaw)
    R2 = np.array([[cy, -sy], [sy, cy]])
    w[:, [0, 2]] = w[:, [0, 2]] @ R2.T
    named = {}
    for wall in walls:
        wn = R2 @ wall["n"]
        q = w[wall["idx"]][:, [0, 2]]
        if abs(wn[1]) > abs(wn[0]):
            pos = float(np.median(q[:, 1]))
            key = "back" if pos > 0 else "front"
        else:
            pos = float(np.median(q[:, 0]))
            key = "right" if pos > 0 else "left"
        # Walls bound the room: on each side keep the candidate farthest from the camera,
        # so a tall furniture front (bookcase + desk in line) does not win over the wall behind it.
        if key not in named or abs(pos) > abs(named[key]["pos"]):
            named[key] = {"pos": pos, "idx": wall["idx"]}

    # 6. Origin: centre of the room floor if we can tell, else under the camera.
    known = library.get("rooms", {}).get(room_name or "", {})
    size = known.get("size_m")
    ox = oz = 0.0
    origin_note = "under the camera (room centre unknown)"
    sides = [k for k in ("left", "right") if k in named]
    if size and sides:
        # Known room: trust the best-seen side wall plus the known width. A side wall seen only
        # as a sliver at the image edge (mixed with furniture in front of it) is unreliable.
        best = max(sides, key=lambda k: len(named[k]["idx"]))
        sign = 1 if best == "left" else -1
        ox = named[best]["pos"] + sign * size[0] / 2
        origin_note = f"x: {best} wall (best seen) and the known width ({size[0]} m)"
    elif len(sides) == 2:
        ox = (named["left"]["pos"] + named["right"]["pos"]) / 2
        origin_note = "x: midway between side walls"
    if "back" in named and size:
        oz = named["back"]["pos"] - size[2] / 2
        origin_note += f"; z: back wall minus half the known depth ({size[2]} m)"
    cam_world = [-ox, cam_h, -oz]

    # 7. Wall tint: median colour of wall points not covered by objects.
    wall_pts = np.concatenate([v["idx"] for v in named.values()]) if named else np.array([], int)
    wall_pts = wall_pts[~mask_obj[wall_pts]]
    measured = rgb_to_hex(*np.median(colors[wall_pts], axis=0)) if len(wall_pts) else None
    tint = known.get("default_tint", "#ffffff")

    # cam_to_world: rotate (r,u,f) rows, then yaw, then translate. Acts on camera-space metres.
    Rcw = np.stack([r, u, f])                  # camera -> floor frame (before yaw)
    Ryaw = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
    M = np.eye(4)
    M[:3, :3] = Ryaw @ Rcw * scale
    M[:3, 3] = [-ox, cam_h, -oz]

    widths = {k: round(v["pos"] - (ox if k in ("left", "right") else oz), 2) for k, v in named.items()}
    report = {
        "camera_height_m": round(cam_h, 3),
        "camera_height_from_depth_m": round(cam_h_measured, 3),
        "scale_applied": round(scale, 3),
        "camera_pitch_down_deg": round(pitch_deg, 1),
        "ceiling_height_m": round(ceiling, 2) if ceiling else None,
        "floor_inlier_share": round(float(floor_in.mean()), 3),
        "floor_rms_residual_m": round(residual, 3),
        "yaw_correction_deg": round(math.degrees(yaw), 1),
        "walls_found": sorted(named),
        "wall_positions_m": widths,
        "rejected_wall_candidates": rejected,
        "room_width_m": round(named["right"]["pos"] - named["left"]["pos"], 2) if {"left", "right"} <= named.keys() else None,
        "camera_to_back_wall_m": round(named["back"]["pos"], 2) if "back" in named else None,
        "camera_position_m": [round(v, 2) for v in cam_world],
        "origin": origin_note,
        "wall_color_measured": measured,
        "wall_tint_used": tint,
    }
    floor = Plane(normal=tuple(map(float, n)), d=float(d))
    room = Room(floor=floor, walls=[], scale=scale, wall_color=tint,
                name=room_name or "unknown", cam_to_world=M, report=report)
    room.report["_labels"] = _labels(H, W, keep, floor_in, named)   # for the debug overlay
    return room


def _labels(H: int, W: int, keep: Any, floor_in: Any, named: dict) -> Any:
    """Per-sample label grid: 0 none, 1 floor, 2.. walls (left, right, back, front)."""
    import numpy as np
    lab = np.zeros(int(keep.sum()), np.uint8)
    lab[floor_in] = 1
    for i, key in enumerate(["left", "right", "back", "front"]):
        if key in named:
            lab[named[key]["idx"]] = 2 + i
    full = np.zeros(keep.shape, np.uint8)
    full[keep] = lab
    return full.reshape(len(range(0, H, STRIDE)), len(range(0, W, STRIDE)))


def save_overlay(rgb: Any, labels: Any, path: str) -> None:
    """Photo with floor (green) and walls (left blue, right orange, back magenta, front cyan)."""
    import numpy as np
    from PIL import Image
    palette = np.array([[0, 0, 0], [40, 200, 80], [60, 120, 255], [255, 150, 30], [230, 60, 200], [40, 220, 230]], float)
    big = np.kron(labels, np.ones((STRIDE, STRIDE), np.uint8))[: rgb.shape[0], : rgb.shape[1]]
    out = rgb.astype(float)
    hit = big > 0
    out[hit] = out[hit] * 0.45 + palette[big[hit]] * 0.55
    Image.fromarray(out.astype(np.uint8)).save(path)
