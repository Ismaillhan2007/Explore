#!/usr/bin/env python3
"""Photo -> scene JSON. Runs the steps in pipeline/README.md section 2 in order.

    python run_pipeline.py photos/room_1.jpg --name room_1 --room RenderedRoom --stop-after room
    python run_pipeline.py ../docs/room-blender.png --name render_check --room RenderedRoom --hfov 73.3 --stop-after room

Steps 1-3 work. Steps 4-6 are still stubs, so use --stop-after room for now.
Debug images and a JSON report go to pipeline/debug/<name>/ (not committed).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from steps.datatypes import Scene
from steps.step1_camera import estimate_camera, hfov_of
from steps.step2_depth import backproject, estimate_depth, focal_correction, save_depth_png
from steps.step3_room import fit_room, save_overlay

HERE = Path(__file__).resolve().parent

# Success criteria for steps 1-3 on a room we know (pipeline/README.md, "Success criteria").
TOL_SIZE_FRAC = 0.15
TOL_CAMERA_HEIGHT_M = 0.25
TOL_CAMERA_XZ_M = 0.30


def grade_room(report: dict, known: dict) -> list[tuple[str, str, bool]]:
    """Compare step 3's measurements with a hand-built room's known values."""
    rows = []
    cam = known.get("camera", {}).get("position")
    size = known.get("size_m")
    if cam:
        got = report["camera_height_m"]
        rows.append(("camera height", f"{got:.2f} m vs {cam[1]:.2f} m", abs(got - cam[1]) <= TOL_CAMERA_HEIGHT_M))
    if size and report.get("room_width_m"):
        got = report["room_width_m"]
        rows.append(("room width", f"{got:.2f} m vs {size[0]:.2f} m", abs(got - size[0]) <= TOL_SIZE_FRAC * size[0]))
    if size and cam and report.get("camera_to_back_wall_m"):
        got = report["camera_to_back_wall_m"]
        want = size[2] / 2 - cam[2]
        rows.append(("camera to back wall", f"{got:.2f} m vs {want:.2f} m", abs(got - want) <= TOL_SIZE_FRAC * want))
    if cam and size and {"left", "right"} & set(report["walls_found"]):
        got = report["camera_position_m"][0]
        rows.append(("camera x in room", f"{got:.2f} m vs {cam[0]:.2f} m", abs(got - cam[0]) <= TOL_CAMERA_XZ_M))
    rows.append(("floor found and flat", f"rms {report['floor_rms_residual_m'] * 100:.1f} cm", report["floor_rms_residual_m"] < 0.03))
    rows.append(("walls found", ", ".join(report["walls_found"]) or "none", len(report["walls_found"]) >= 2))
    return rows


def run(photo: Path, name: str, room_name: str | None, hfov: float | None,
        camera_height: float | None, stop_after: str) -> int:
    library = json.loads((HERE / "model_library.json").read_text(encoding="utf-8"))
    debug = HERE / "debug" / name
    debug.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    cam, rgb, cam_source = estimate_camera(str(photo), hfov)                 # 1
    print(f"[1 camera] {cam.width}x{cam.height}, hfov {hfov_of(cam):.1f} deg ({cam_source})")

    depth = estimate_depth(rgb, cam)                                         # 2
    points = backproject(depth, cam)
    save_depth_png(depth, str(debug / "depth.png"))
    print(f"[2 depth ] median {float(__import__('numpy').median(depth)):.2f} m "
          f"(lens correction x{focal_correction(cam):.2f}) -> {debug / 'depth.png'}")

    detections = []   # step 4 is not implemented yet; wall tint then ignores no objects
    room = fit_room(points, rgb, detections, library, room_name, camera_height)  # 3
    labels = room.report.pop("_labels")
    save_overlay(rgb, labels, str(debug / "room_overlay.png"))
    report = dict(room.report, photo=str(photo), camera_source=cam_source,
                  hfov_deg=round(hfov_of(cam), 1), seconds=round(time.time() - t0, 1))
    known = library.get("rooms", {}).get(room_name or "", {})
    grades = grade_room(report, known) if known else []
    report["checks"] = [{"check": c, "value": v, "pass": ok} for c, v, ok in grades]
    (debug / "room_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"[3 room  ] walls {report['walls_found']}, camera at {report['camera_position_m']} "
          f"(pitch {report['camera_pitch_down_deg']} deg down), wall colour {report['wall_color_measured']}")
    print(f"           overlay -> {debug / 'room_overlay.png'}, report -> {debug / 'room_report.json'}")
    if grades:
        print(f"\nChecks against the known room '{room_name}':")
        for c, v, ok in grades:
            print(f"  {'PASS' if ok else 'FAIL'}  {c:<22} {v}")
    print(f"\n{report['seconds']} s total")
    if stop_after == "room":
        return 0 if all(ok for _, _, ok in grades) else 1

    from steps.step4_detect import detect_objects
    from steps.step5_place import place_objects
    from steps.step6_match import match_models
    from steps.step7_export import write_scene
    labels_av = sorted({m["label"] for m in library["models"].values()
                        if m.get("status") == "available" and m.get("kind") == "pickable"})
    detections = detect_objects(rgb, labels_av)                              # 4
    surfaces = known.get("surfaces", {})
    placements = place_objects(detections, points, room, surfaces)           # 5
    objects = match_models(placements, rgb, library)                         # 6
    scene = Scene(room=room.name, wall_color=room.wall_color, objects=objects)
    out = write_scene(scene, HERE / "scenes" / f"scene_{name}.json")         # 7
    result = subprocess.run([sys.executable, str(HERE / "validate_scene.py"), str(out)])
    if result.returncode != 0:
        raise SystemExit(f"validation failed for {out}; fix the step or the JSON by hand")
    print(f"wrote {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", type=Path)
    ap.add_argument("--name", required=True, help="output name, e.g. room_1 -> debug/room_1/, scenes/scene_room_1.json")
    ap.add_argument("--room", help="room from model_library.json the photo shows (enables the accuracy checks)")
    ap.add_argument("--hfov", type=float, help="horizontal field of view in degrees, if known (overrides EXIF)")
    ap.add_argument("--camera-height", type=float, help="force the scale so the camera is this high, in metres")
    ap.add_argument("--stop-after", choices=["room", "all"], default="all")
    args = ap.parse_args()
    try:
        return run(args.photo, args.name, args.room, args.hfov, args.camera_height, args.stop_after)
    except NotImplementedError as e:
        print(f"not implemented yet: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
