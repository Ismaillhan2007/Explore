"""Find the camera a photo was taken from, inside the room built from it.

Each built room was modelled from its photo, but the reference camera in the room builders was
placed by eye, so it doesn't line up exactly with the photo. Here we solve for the camera from
landmarks: points whose 3D position we know in the room (TV corners, cabinet edge, poster corners …)
and whose pixel we marked in the photo. The solver searches camera position, turn, tilt and
vertical field of view to minimise the pixel distance between projected and marked points
(Gauss-Newton / Levenberg-Marquardt with a numeric Jacobian; no roll, like Unity's LookAt).

Landmarks live in pipeline/landmarks/<room>.json. Run:  python -m steps.align_camera --write landmarks/*.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

from .evaluate import project


def camera_from(params) -> dict:
    """params = [x, y, z, yaw_deg, pitch_down_deg, vfov_deg] -> camera dict (position, look_at, vfov_deg)."""
    x, y, z, yaw, pitch, vfov = params
    a, b = math.radians(yaw), math.radians(pitch)
    fwd = (math.sin(a) * math.cos(b), -math.sin(b), math.cos(a) * math.cos(b))
    return {"position": [x, y, z], "look_at": [x + fwd[0], y + fwd[1], z + fwd[2]], "vfov_deg": vfov}


PRIOR_PX_PER_M = 40.0   # how many pixels of landmark error 1 m of prior violation is worth


def residuals(params, points, pixels, width, height, priors: dict | None = None) -> np.ndarray:
    """Pixel errors per landmark, plus soft priors: camera height (known roughly) and staying inside the room."""
    cam = camera_from(params)
    out = []
    for p, (u, v) in zip(points, pixels):
        pr = project(p, cam, width, height)
        out += [1e3, 1e3] if pr is None else [pr[0] - u, pr[1] - v]
    if priors:
        x, y, z = params[:3]
        if "camera_height_m" in priors:
            h, tol = priors["camera_height_m"]
            out.append(PRIOR_PX_PER_M * max(0.0, abs(y - h) - tol))
        if "room_half_size_m" in priors:
            hx, hz = priors["room_half_size_m"]; m = 0.2   # at least 20 cm from the walls
            out.append(PRIOR_PX_PER_M * 5 * (max(0.0, abs(x) - (hx - m)) + max(0.0, abs(z) - (hz - m))))
    return np.array(out)


def solve(points, pixels, width, height, start, iters: int = 200, priors: dict | None = None):
    """Levenberg-Marquardt on the 6 camera parameters. Returns (params, rms pixel error, per-point errors)."""
    p = np.array(start, float); lam = 1e-2
    r = residuals(p, points, pixels, width, height, priors); cost = r @ r
    steps = np.array([1e-3, 1e-3, 1e-3, 1e-2, 1e-2, 1e-2])
    for _ in range(iters):
        J = np.stack([(residuals(p + np.eye(6)[i] * steps[i], points, pixels, width, height, priors) - r) / steps[i] for i in range(6)], 1)
        A = J.T @ J; g = J.T @ r
        while True:
            dp = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            new = p + dp; new[5] = min(max(new[5], 20), 120)
            r_new = residuals(new, points, pixels, width, height, priors); c_new = r_new @ r_new
            if c_new < cost:
                p, r, cost, lam = new, r_new, c_new, max(lam / 3, 1e-7); break
            lam *= 4
            if lam > 1e8:
                break
        if np.linalg.norm(dp) < 1e-7 or lam > 1e8:
            break
    n = len(points)
    per_point = np.hypot(r[0:2 * n:2], r[1:2 * n:2])
    return p, float(np.sqrt(np.mean(per_point ** 2))), per_point


def solve_file(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = [l["name"] for l in data["landmarks"]]
    points = [l["world"] for l in data["landmarks"]]; pixels = [l["pixel"] for l in data["landmarks"]]
    W, H = data["image_size"]
    best = None
    for start in data.get("starts", [data["start"]]):     # a few starting guesses, keep the best
        params, rms, per = solve(points, pixels, W, H, start, priors=data.get("priors"))
        if best is None or rms < best[1]:
            best = (params, rms, per)
    params, rms, per = best
    cam = camera_from(params)
    return {"room": data["room"], "photo": data["photo"], "image_size": [W, H],
            "camera": {"position": [round(v, 3) for v in cam["position"]], "look_at": [round(v, 3) for v in cam["look_at"]],
                       "vfov_deg": round(cam["vfov_deg"], 2)},
            "yaw_deg": round(params[3], 2), "pitch_down_deg": round(params[4], 2),
            "rms_px": round(rms, 2), "errors_px": {n: round(float(e), 1) for n, e in zip(names, per)}}


def write_to_library(result: dict, landmarks_file: str | Path, library_path: str | Path) -> None:
    """Store the solved camera (and the surfaces' photo pixels) under rooms.<room>.photo in model_library.json."""
    data = json.loads(Path(landmarks_file).read_text(encoding="utf-8"))
    lib_path = Path(library_path); lib = json.loads(lib_path.read_text(encoding="utf-8"))
    lib["rooms"][result["room"]]["photo"] = {
        "_comment": "Camera the real photo was taken from, solved by steps/align_camera.py from " + str(Path(landmarks_file).as_posix())
                    + ". Used by step 5 for real photos (not for the Unity renders, which use 'camera').",
        "image": result["photo"], "image_size": result["image_size"], "camera": result["camera"],
        "rms_px": result["rms_px"], "max_error_px": max(result["errors_px"].values()),
        "surface_pixels": {k: v for k, v in data.get("surface_pixels", {}).items() if not k.startswith("_")}}
    lib_path.write_text(json.dumps(lib, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--write"]
    for f in args:
        result = solve_file(f)
        print(json.dumps(result, indent=2))
        if "--write" in sys.argv:
            write_to_library(result, f, Path(__file__).resolve().parents[1] / "model_library.json")
            print(f"stored as rooms.{result['room']}.photo in model_library.json")
