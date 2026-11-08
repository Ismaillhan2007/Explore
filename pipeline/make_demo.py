"""Demo images for the README and PRs: the rooms with their pickables, and the algorithm step by step
on the pre-rendered sofa room.

From the repo root, after:
  cd pipeline && python run_pipeline.py ../docs/living-room-sofa-unity.png --name demo_sofa --answers scenes/scene_living_room_sofa.json
  Unity -batchmode -quit -projectPath . -executeMethod RoomVR.EditorTools.PipelineScenePreview.Run \
        -sceneJson pipeline/debug/demo_sofa/scene_demo_sofa.json -out pipeline/debug/demo_sofa/unity_result.png
run:
  pipeline/.venv/bin/python pipeline/make_demo.py . pipeline/results
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "pipeline"))
from steps.evaluate import project  # noqa: E402

lib = json.loads((repo / "pipeline/model_library.json").read_text())
try:
    FONT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26); SMALL = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
except OSError:
    FONT = SMALL = ImageFont.load_default()
COL = {"mug": (230, 70, 50), "book": (40, 120, 230), "lamp": (240, 180, 20)}


def fit(im, w):
    return im.resize((w, round(im.height * w / im.width)), Image.Resampling.LANCZOS)


def caption(im, title, lines=(), bar=None):
    bar = bar or (52 + 24 * max(2, len(lines)))
    canvas = Image.new("RGB", (im.width, im.height + bar), "white"); canvas.paste(im, (0, bar)); d = ImageDraw.Draw(canvas)
    d.text((12, 8), title, fill=(20, 20, 20), font=FONT)
    for i, l in enumerate(lines):
        d.text((12, 44 + i * 24), l, fill=(70, 70, 70), font=SMALL)
    return canvas


def row(panels, gap=16, bg="white"):
    h = max(p.height for p in panels); w = sum(p.width for p in panels) + gap * (len(panels) - 1)
    im = Image.new("RGB", (w, h), bg); x = 0
    for p in panels:
        im.paste(p, (x, 0)); x += p.width + gap
    return im


def column(panels, gap=24, bg=(235, 235, 235), pad=24):
    w = max(p.width for p in panels) + 2 * pad; h = sum(p.height for p in panels) + gap * (len(panels) - 1) + 2 * pad
    im = Image.new("RGB", (w, h), bg); y = pad
    for p in panels:
        im.paste(p, (pad, y)); y += p.height + gap
    return im


# 1) Rooms and their pickables, marked on each room's Unity render
rooms = [("RenderedRoom", "docs/room-unity.png", "scene_room_a.json", "Room 1 (bedroom)"),
         ("LivingRoomSofa", "docs/living-room-sofa-unity.png", "scene_living_room_sofa.json", "Living room (sofa)"),
         ("LivingRoomTV", "docs/living-room-tv-unity.png", "scene_living_room_tv.json", "Living room (TV)")]
panels = []
for room, img, key, title in rooms:
    im = Image.open(repo / img).convert("RGB"); d = ImageDraw.Draw(im)
    ans = json.loads((repo / "pipeline/scenes" / key).read_text()); cam = lib["rooms"][room]["camera"]
    notes = []
    for o in ans["objects"]:
        h = lib["models"][o["model"]]["height_m"]; x, y, z = o["position"]
        pr = project((x, y + h / 2, z), cam, im.width, im.height)
        visible = pr and 0 <= pr[0] < im.width and 0 <= pr[1] < im.height
        if visible:
            u, v = pr[0], pr[1]; r = 34 if o["model"] != "lamp" else 70
            d.ellipse([u - r, v - r, u + r, v + r], outline=COL[o["model"]], width=6)
        notes.append(f"{o['model']} on {'desk' if y > 0.75 else 'table'} at y {y:.2f} m" + ("" if visible else " (out of view)"))
    panels.append(caption(fit(im, 620), title, ["3 pickables: " + ", ".join(n.split(' on')[0] for n in notes)]
                          + [n for n in notes if "out of view" in n]))
sheet = row(panels)
legend = Image.new("RGB", (sheet.width, 60), "white"); d = ImageDraw.Draw(legend)
d.text((12, 14), "Scenes in the build: RenderedRoom, LivingRoomSofa, LivingRoomTV (+ TestRoom with 3 test cubes).   Circles:", fill=(20, 20, 20), font=SMALL)
x = 1080
for k, c in COL.items():
    d.ellipse([x, 18, x + 22, 40], outline=c, width=4); d.text((x + 30, 14), k, fill=c, font=SMALL); x += 110
column([legend, sheet]).save(out / "demo_rooms_and_pickables.png")

# 2) Algorithm walkthrough on the sofa room render
dbg = repo / "pipeline/debug/demo_sofa"
rep = json.loads((dbg / "detect_report.json").read_text()); room = json.loads((dbg / "room_report.json").read_text())
scene = json.loads((dbg / "scene_report.json").read_text())
W = 430
p1 = caption(fit(Image.open(repo / "docs/living-room-sofa-unity.png").convert("RGB"), W), "1. Input: pre-rendered scene",
             ["Unity render of LivingRoomSofa", "(no labels given to the algorithm)"])
p2 = caption(fit(Image.open(dbg / "depth.png").convert("RGB"), W), "2. Depth (AI model)",
             ["Depth Anything V2: metres per pixel", "bright = near, dark = far"])
p3 = caption(fit(Image.open(dbg / "room_overlay.png").convert("RGB"), W), "3. Room shape",
             [f"floor (green), walls {', '.join(room['walls_found'])}", f"camera {room['camera_height_m']} m high, {room['camera_pitch_down_deg']} deg down"])
kept = ", ".join(f"{k['label']} {k['score']:.2f}" for k in rep["kept"])
p4 = caption(fit(Image.open(dbg / "detections.png").convert("RGB"), W), "4. Find the pickables",
             [f"kept: {kept}", "rejected: floor lamp (too tall),", "plant pot (CLIP: not a mug)"])
res = [f"{r['label']} {r['xz_error_m'] * 100:.0f} cm off, scale {r['scale']}" for r in scene["objects"] if r["result"] == "pass"]
p5 = caption(fit(Image.open(dbg / "unity_result.png").convert("RGB"), W), "5-7. Placed in Unity from the JSON",
             [f"{scene['passed']}/{scene['total']} right vs answer key"] + res)
title = Image.new("RGB", (W * 5 + 64, 70), "white"); d = ImageDraw.Draw(title)
d.text((12, 8), "How the photo pipeline works on a pre-rendered scene (LivingRoomSofa)", fill=(20, 20, 20), font=FONT)
d.text((12, 40), "photo -> camera -> depth -> room -> find pickables -> place on tables -> prefab + scale -> scene JSON -> Unity", fill=(90, 90, 90), font=SMALL)
column([title, row([p1, p2, p3, p4, p5])]).save(out / "demo_algorithm_walkthrough.png")

# 3) Close-up: original render vs. the pipeline's result, same camera
a = Image.open(repo / "docs/living-room-sofa-unity.png").convert("RGB").crop((100, 650, 800, 1050))
b = Image.open(dbg / "unity_result.png").convert("RGB").crop((100, 650, 800, 1050))
column([row([caption(a, "Hand-placed (answer key)", ["mug, book on coffee table; lamp on side table"], 80),
             caption(b, "Placed by the algorithm from the image", [" ; ".join(r.split(", scale")[0] for r in res)], 80)])]).save(out / "demo_closeup.png")
print("ok")
