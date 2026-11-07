"""Step 7: write the scene JSON in Unity space. README section 2, step 7 and section 4. Works today."""
from __future__ import annotations

import json
from pathlib import Path

from .datatypes import Scene


def scene_to_dict(scene: Scene) -> dict:
    return {
        "version": scene.version,
        "room": scene.room,
        "wallColor": scene.wall_color,
        "objects": [
            {
                "label": o.label,
                "model": o.model,
                "position": [round(v, 2) for v in o.position],
                "rotationY": round(o.rotation_y) % 360,
                "scale": round(o.scale, 2),
            }
            for o in scene.objects
        ],
    }


def write_scene(scene: Scene, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scene_to_dict(scene), indent=2) + "\n", encoding="utf-8")
    return out_path
