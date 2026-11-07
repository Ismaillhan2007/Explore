#!/usr/bin/env python3
"""Photo -> scene JSON. Runs the steps in pipeline/README.md section 2 in order.

    python run_pipeline.py photos/room_a.jpg --name room_a

Steps that are still stubs raise NotImplementedError; the message names the step.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from steps.datatypes import Scene
from steps.step1_camera import estimate_camera
from steps.step2_depth import backproject, estimate_depth
from steps.step3_room import fit_room
from steps.step4_detect import detect_objects
from steps.step5_place import place_objects
from steps.step6_match import match_models
from steps.step7_export import write_scene

HERE = Path(__file__).resolve().parent


def run(photo: Path, name: str) -> Path:
    library = json.loads((HERE / "model_library.json").read_text(encoding="utf-8"))
    labels = sorted({m["label"] for m in library["models"].values()
                     if m.get("status") == "available" and m.get("kind") == "pickable"})

    cam, rgb = estimate_camera(str(photo))                  # 1
    points = backproject(estimate_depth(rgb), cam)           # 2
    detections = detect_objects(rgb, labels)                 # 4 (before 3: wall tint ignores object masks)
    room = fit_room(points, rgb, detections, library)        # 3
    surfaces = library["rooms"][room.name].get("surfaces", {})
    placements = place_objects(detections, points, room, surfaces)  # 5
    objects = match_models(placements, rgb, library)         # 6
    scene = Scene(room=room.name, wall_color=room.wall_color, objects=objects)
    out = write_scene(scene, HERE / "scenes" / f"scene_{name}.json")  # 7

    result = subprocess.run([sys.executable, str(HERE / "validate_scene.py"), str(out)])
    if result.returncode != 0:
        raise SystemExit(f"validation failed for {out}; fix the step or the JSON by hand")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", type=Path)
    ap.add_argument("--name", required=True, help="scene name, e.g. room_a -> scenes/scene_room_a.json")
    args = ap.parse_args()
    try:
        print(f"wrote {run(args.photo, args.name)}")
    except NotImplementedError as e:
        print(f"not implemented yet: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
