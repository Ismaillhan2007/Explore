#!/usr/bin/env python3
"""Check scene JSON files against the contract in pipeline/README.md section 4.

Standard library only. Exit code 1 on any error, so it can gate the pipeline and CI.

    python validate_scene.py scenes/*.json
    python validate_scene.py --strict scenes/scene_room_a.json   # planned models are errors too
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBRARY = HERE / "model_library.json"
PREFAB_DIR = HERE.parent / "Assets" / "_Project" / "Prefabs" / "Pickables"
SUPPORTED_VERSIONS = {1}
MAX_ABS_POS = 100.0          # review checklist: outside +-100 m is absurd
SCALE_RANGE = (0.7, 1.4)     # same clamp as step 6
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(scene: dict, library: dict, strict: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    models = library.get("models", {})
    rooms = library.get("rooms", {})

    if scene.get("version", 1) not in SUPPORTED_VERSIONS:
        errors.append(f"version {scene.get('version')!r} not supported")
    room = scene.get("room")
    if not isinstance(room, str) or not room:
        errors.append("room: missing or not a string")
    elif room not in rooms:
        errors.append(f"room {room!r} not in model_library.json")
    elif rooms[room].get("status") != "available":
        (errors if strict else warnings).append(f"room {room!r} is still planned")
    if not isinstance(scene.get("wallColor"), str) or not HEX.match(scene["wallColor"]):
        errors.append(f"wallColor {scene.get('wallColor')!r} is not #rrggbb")

    objects = scene.get("objects")
    if not isinstance(objects, list):
        return errors + ["objects: missing or not a list"], warnings

    for i, o in enumerate(objects):
        where = f"objects[{i}]"
        if not isinstance(o, dict):
            errors.append(f"{where}: not an object")
            continue
        where += f" ({o.get('label', '?')})"
        model = o.get("model")
        if model not in models:
            errors.append(f"{where}: model {model!r} not in model_library.json")
        else:
            entry = models[model]
            if entry.get("status") != "available":
                (errors if strict else warnings).append(f"{where}: model {model!r} is still planned")
            elif not (PREFAB_DIR / f"{model}.prefab").exists():
                errors.append(f"{where}: {model}.prefab not found in Prefabs/Pickables")
            if o.get("label") and entry.get("label") and o["label"] != entry["label"]:
                warnings.append(f"{where}: label {o['label']!r} differs from library label {entry['label']!r}")

        pos = o.get("position")
        if not (isinstance(pos, list) and len(pos) == 3 and all(_num(v) for v in pos)):
            errors.append(f"{where}: position must be [x, y, z] numbers")
        else:
            if any(abs(v) > MAX_ABS_POS for v in pos):
                errors.append(f"{where}: position {pos} outside +-{MAX_ABS_POS:g} m")
            if pos[1] < 0:
                errors.append(f"{where}: below the floor (y = {pos[1]})")
        if not _num(o.get("rotationY")):
            errors.append(f"{where}: rotationY must be a number")
        scale = o.get("scale")
        if not _num(scale) or scale <= 0:
            errors.append(f"{where}: scale must be > 0")
        elif not SCALE_RANGE[0] <= scale <= SCALE_RANGE[1]:
            warnings.append(f"{where}: scale {scale} outside {SCALE_RANGE}")
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenes", nargs="+", type=Path)
    ap.add_argument("--strict", action="store_true", help="planned (not yet built) models and rooms are errors")
    args = ap.parse_args()

    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    failed = False
    for path in args.scenes:
        try:
            scene = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"FAIL {path}: {e}")
            failed = True
            continue
        errors, warnings = validate(scene, library, args.strict)
        for w in warnings:
            print(f"  warn  {w}")
        for e in errors:
            print(f"  error {e}")
        print(f"{'FAIL' if errors else 'OK  '} {path} ({len(scene.get('objects', []))} objects)")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
