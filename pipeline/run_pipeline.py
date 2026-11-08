#!/usr/bin/env python3
"""Photo -> scene JSON. Runs the steps in pipeline/README.md section 2 in order.

    python run_pipeline.py photos/room_1.jpg --name room_1 --room RenderedRoom --stop-after room
    python run_pipeline.py ../docs/room-blender.png --name render_check --room RenderedRoom --hfov 73.3 --stop-after room
    python run_pipeline.py ../docs/living-room-sofa-unity.png --name sofa_detect --answers scenes/scene_living_room_sofa.json --stop-after detect

All steps work. Without --answers, the scene JSON is written to scenes/generated/scene_<name>.json.
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

# Without lens data the metric depth is unreliable (1.6-2x too large on the two living-room
# photos), so assume a normal ceiling instead, unless a camera height is given.
DEFAULT_CEILING_M = 2.7


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


def pickable_labels(library: dict) -> list[str]:
    return sorted({m["label"] for m in library["models"].values()
                   if m.get("status") == "available" and m.get("kind") == "pickable" and m.get("detect", True)})


def report_detect(detections, rejected, rgb, cam, library, debug: Path, answers: Path | None, seconds: float) -> dict | None:
    """Print and save step 4's result; grade it against an answer key when one is given."""
    from steps.evaluate import decor_in_image, grade_detections, truth_in_image
    from steps.step4_detect import save_detections
    truth, grade = None, None
    if answers:
        answer = json.loads(Path(answers).read_text(encoding="utf-8"))
        truth = truth_in_image(answer, library, cam.width, cam.height)
        grade = grade_detections(detections, truth, decor=decor_in_image(answer, library, cam.width, cam.height))
    save_detections(rgb, detections, str(debug / "detections.png"), [t for t in (truth or []) if t["in_frame"]])
    print(f"[4 detect] {len(detections)} kept, {len(rejected)} rejected by the size check, {seconds:.1f} s -> {debug / 'detections.png'}")
    for d in sorted(detections, key=lambda d: -d.score):
        sz = f"  {d.size['height_m']:.2f} m tall, {d.size['width_m']:.2f} wide, base {d.size['base_m']:.2f}" if d.size else ""
        sz += f", CLIP {d.clip:.2f}" if d.clip is not None else ""
        print(f"           {d.label:<5} {d.score:.2f}  box {d.box}{sz}")
    for r in rejected:
        print(f"           rejected {r['label']} {r['score']}: {r['why']}")
    if grade:
        print(f"\nChecks against the answer key ({answers}):")
        for r in grade["objects"]:
            tag = {"found": "PASS", "missed": "FAIL", "out of frame": "----"}[r["result"]]
            extra = f" (score {r['score']})" if r.get("score") else ""
            print(f"  {tag}  {r['label']:<5} at pixel {r['pixel']}: {r['result']}{extra}")
        for e in grade["extra_detections"]:
            print(f"  FAIL  extra detection: {e['label']} {e['score']} box {e['box']}")
        for e in grade["decor_detections"]:
            print(f"  ----  {e['label']} {e['score']} on {e['decor']} (looks exactly like ours; not counted)")
        print(f"  => found {grade['found']}/{grade['in_frame']}, false detections {grade['false_detections']}")
    (debug / "detect_report.json").write_text(json.dumps({"grade": grade, "rejected": rejected,
        "kept": [{"label": d.label, "score": round(d.score, 3), "box": d.box, "size": d.size} for d in detections]},
        indent=2, default=str) + "\n", encoding="utf-8")
    return grade


def run(photo: Path, name: str, room_name: str | None, hfov: float | None,
        camera_height: float | None, ceiling_height: float | None, metric: bool, stop_after: str,
        answers: Path | None = None, min_score: float = 0.30, no_clip: bool = False, render: bool = False) -> int:
    library = json.loads((HERE / "model_library.json").read_text(encoding="utf-8"))
    debug = HERE / "debug" / name
    debug.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if answers or render:   # a render from a built room's reference camera: use that camera's real lens and height
        answer_room = json.loads(Path(answers).read_text(encoding="utf-8"))["room"] if answers else room_name
        if not answer_room or answer_room not in library["rooms"]:
            raise SystemExit("--render needs --room <a built room from model_library.json>")
        ref = library["rooms"][answer_room]["camera"]
        room_name = room_name or answer_room
        if hfov is None:
            from PIL import Image
            W0, H0 = Image.open(photo).size
            hfov = math.degrees(2 * math.atan(math.tan(math.radians(ref["vfov_deg"]) / 2) * W0 / H0))
        if camera_height is None:
            camera_height = ref["position"][1]

    cam, rgb, cam_source = estimate_camera(str(photo), hfov)                 # 1
    print(f"[1 camera] {cam.width}x{cam.height}, hfov {hfov_of(cam):.1f} deg ({cam_source})")

    detections, t4 = [], 0.0
    if stop_after in ("detect", "all"):                                       # 4 (before 3: wall colour skips objects)
        from steps.step4_detect import detect_objects
        t = time.time()
        detections = detect_objects(str(photo), pickable_labels(library), (cam.width, cam.height), min_score)
        t4 = time.time() - t

    depth = estimate_depth(rgb, cam)                                         # 2
    points = backproject(depth, cam)
    save_depth_png(depth, str(debug / "depth.png"))
    print(f"[2 depth ] median {float(__import__('numpy').median(depth)):.2f} m "
          f"(lens correction x{focal_correction(cam):.2f}) -> {debug / 'depth.png'}")

    if camera_height is None and ceiling_height is None and not metric and cam_source.startswith("no EXIF"):
        ceiling_height = DEFAULT_CEILING_M
    room = fit_room(points, rgb, detections, library, room_name, camera_height, ceiling_height)  # 3
    labels = room.report.pop("_labels")
    save_overlay(rgb, labels, str(debug / "room_overlay.png"))
    report = dict(room.report, photo=str(photo), camera_source=cam_source,
                  hfov_deg=round(hfov_of(cam), 1), seconds=round(time.time() - t0, 1))
    known = library.get("rooms", {}).get(room_name or "", {})
    grades = grade_room(report, known) if known else []
    report["checks"] = [{"check": c, "value": v, "pass": ok} for c, v, ok in grades]
    (debug / "room_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"[3 room  ] scale x{report['scale_applied']} from {report['scale_source']}")
    print(f"           walls {report['walls_found']}, camera at {report['camera_position_m']} "
          f"(pitch {report['camera_pitch_down_deg']} deg down), wall colour {report['wall_color_measured']}")
    print(f"           overlay -> {debug / 'room_overlay.png'}, report -> {debug / 'room_report.json'}")
    if grades:
        print(f"\nChecks against the known room '{room_name}':")
        for c, v, ok in grades:
            print(f"  {'PASS' if ok else 'FAIL'}  {c:<22} {v}")
    if stop_after in ("detect", "all"):                                       # 4b: size check needs depth + floor
        from steps.step4_detect import size_check
        detections, rejected = size_check(detections, points, room, library, cam)
        if not no_clip:
            from PIL import Image as _Image
            from steps.step4_detect import verify_with_clip
            full = _Image.open(photo).convert("RGB")
            detections, rejected_clip = verify_with_clip(full, detections, (cam.width / full.width, cam.height / full.height))
            rejected += rejected_clip
        grade = report_detect(detections, rejected, rgb, cam, library, debug, answers, t4)
        if stop_after == "detect":
            print(f"\n{time.time() - t0:.1f} s total")
            return 0 if grade is None or (grade["found"] == grade["in_frame"] and grade["false_detections"] == 0) else 1
    print(f"\n{report['seconds']} s total")
    if stop_after == "room":
        return 0 if all(ok for _, _, ok in grades) else 1

    from steps.step5_place import place_objects
    from steps.step6_match import match_models
    from steps.step7_export import scene_to_dict, write_scene
    real_photo = answers is None and not render
    mode = ("photo camera, relative to each table" if real_photo and "photo" in known
            else "reference camera" if "look_at" in known.get("camera", {}) else "depth (unknown room)")
    placements = place_objects(detections, room, known, library, (cam.width, cam.height), real_photo)  # 5
    print(f"\n[5 place ] {len(placements)} placed, mode: {mode}")
    for pl in placements:
        print(f"           {pl.label:<5} on {pl.surface:<13} at ({pl.position[0]:.2f}, {pl.position[1]:.2f}, {pl.position[2]:.2f}), "
              f"facing {pl.rotation_y:.0f} deg, measured {pl.size[0]:.2f} x {pl.size[1]:.2f} m")
    objects, warnings = match_models(placements, library)                                       # 6
    print(f"[6 match ] {', '.join(f'{o.label}->{o.model} x{o.scale}' for o in objects) or 'nothing'}")
    for w in warnings:
        print(f"           warning: {w}")
    scene = Scene(room=room.name if known else "unknown", wall_color=room.wall_color, objects=objects)
    out = write_scene(scene, (debug if answers else HERE / "scenes" / "generated") / f"scene_{name}.json")  # 7
    print(f"[7 export] {out}")
    if known:
        result = subprocess.run([sys.executable, str(HERE / "validate_scene.py"), "--strict", str(out)])
        if result.returncode != 0:
            print("validation failed: fix the step or the JSON by hand")
            return 1
    if answers:
        from steps.evaluate import grade_scene, truth_in_image
        answer = json.loads(Path(answers).read_text(encoding="utf-8"))
        visible = {t["model"] + str(t["position"]): t["in_frame"] for t in truth_in_image(answer, library, cam.width, cam.height)}
        g = grade_scene(scene_to_dict(scene), answer, visible)
        print(f"\nScene checks against the answer key (position within 15 cm, height within 1 cm, scale 0.8-1.25):")
        for r in g["objects"]:
            if r["result"] == "missing":
                print(f"  FAIL  {r['label']:<5} not in the scene"); continue
            if r["result"] == "out of frame":
                print(f"  ----  {r['label']:<5} out of frame (not graded)"); continue
            print(f"  {'PASS' if r['result'] == 'pass' else 'FAIL'}  {r['label']:<5} position error {r['xz_error_m'] * 100:.0f} cm, "
                  f"height error {r['y_error_m'] * 100:.1f} cm, scale {r['scale']}")
        for e in g["extra"]:
            print(f"  FAIL  extra object {e['label']} at {e['position']}")
        for e in g["decor"]:
            print(f"  ----  {e['label']} placed on {e['decor']} (looks exactly like ours; not counted)")
        print(f"  => {g['passed']}/{g['total']} objects right, {len(g['extra'])} extra")
        (debug / "scene_report.json").write_text(json.dumps(g, indent=2) + "\n", encoding="utf-8")
        return 0 if g["passed"] == g["total"] and not g["extra"] else 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", type=Path)
    ap.add_argument("--name", required=True, help="output name, e.g. room_1 -> debug/room_1/, scenes/scene_room_1.json")
    ap.add_argument("--room", help="room from model_library.json the photo shows (enables the accuracy checks)")
    ap.add_argument("--hfov", type=float, help="horizontal field of view in degrees, if known (overrides EXIF)")
    ap.add_argument("--camera-height", type=float, help="force the scale so the camera is this high, in metres")
    ap.add_argument("--ceiling-height", type=float, help=f"force the scale so the ceiling is this high (default {DEFAULT_CEILING_M} m when the photo has no lens data)")
    ap.add_argument("--metric", action="store_true", help="trust the depth model's scale even without lens data")
    ap.add_argument("--stop-after", choices=["detect", "room", "all"], default="all",
                    help="room: steps 1-3; detect: steps 1-4; all: everything")
    ap.add_argument("--render", action="store_true", help="the image is a Unity render of --room from its reference camera "
                    "(e.g. with objects moved): exact placement, no answer key needed")
    ap.add_argument("--answers", type=Path, help="answer-key scene JSON (scenes/*.json) to grade step 4 against; "
                    "only valid for a render taken from the room's reference camera")
    ap.add_argument("--min-score", type=float, default=0.30, help="detector score threshold")
    ap.add_argument("--no-clip", action="store_true", help="skip the CLIP second-opinion check in step 4")
    args = ap.parse_args()
    try:
        return run(args.photo, args.name, args.room, args.hfov, args.camera_height, args.ceiling_height,
                   args.metric, args.stop_after, args.answers, args.min_score, args.no_clip, args.render)
    except NotImplementedError as e:
        print(f"not implemented yet: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
