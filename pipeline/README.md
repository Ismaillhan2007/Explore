# Photo → scene pipeline

Owner: **Role B** (see [TEAM.md](../TEAM.md)). Backup: Role C.

This folder turns **one photo of a room** into **one scene JSON file** that says which **pickable objects** go where. The Unity scene loader (Role A) reads it and spawns those objects into a room. It runs offline on a laptop, before the demo. Nothing here touches `.unity`, `.prefab` or `.meta` files.

**The room itself is built by hand in Blender** (PR #4: `tools/room/build_room.py` → `Assets/_Project/Scenes/RenderedRoom.unity`). Walls and furniture are static and their lighting is baked into textures, so the pipeline never moves or creates furniture. It only:
- places **pickables** (mug, …) on the room's known surfaces, and
- for a **new** room, measures the photo (size, camera, surfaces) to guide the Blender build.

Room 1 = `RenderedRoom` (4.2 × 5.6 × 3.5 m). Its pickables are the mug on the coffee table and the bedside lamp on the bedside table (the lamp used to be baked; it is now `lamp.prefab`). All room numbers in this folder are copied from PR #4. If that PR changes, update [`model_library.json`](model_library.json).

```
photo.jpg ──► [1 camera] ──► [2 depth] ──► [3 room] ──► [4 detect + segment] ──► [5 place] ──► [6 match] ──► [7 export] ──► scene_room_x.json
                                              │                                                                  ▲
                                              └── floor plane, walls, scale, wall tint ──────────────────────────┘
```

Status: **all steps work end to end**: photo → camera, depth, room, pickables found, placed on their tables, matched to prefabs → scene JSON (see "Results so far", "Step 4 results" and "Steps 5–6 results" below). `validate_scene.py` works. The answer keys in [`scenes/`](scenes/) list where every pickable really is in each of the three built rooms. What's missing is the Unity loader that reads a scene JSON at runtime (Role A); `PipelineScenePreview.cs` shows the result in Unity for checking.

---

## 1. Why it is built this way

- **Rooms by hand, pickables by pipeline.** A baked Blender room looks far better than anything we can generate automatically in 72 hours, so rooms are hand-built (PR #4). Pickables must stay separate, lit and physical, so they come from the pipeline and the JSON.
- **Retrieval, not generation.** We match each pickable in the photo to one of our own clean prefabs (collider, rigidbody, grab). Image-to-3D models are slow, give messy meshes and bad colliders, so they are only an optional extra for one or two hero objects.
- **Decoupled from Unity.** The only thing the pipeline and Unity share is the JSON contract (section 4). Both sides work in parallel; the hand-made JSON is both the loader's test input and the demo fallback.
- **Good enough, then hand-tuned.** The goal is "believable", not "accurate". For the two demo photos we expect to fix a few numbers by hand in the JSON; `PLAN.md` already says the scenes are prebuilt.

## 2. The algorithm, step by step

Each step is one file in [`steps/`](steps/) with one public function. Data passed between steps is defined in [`steps/datatypes.py`](steps/datatypes.py).

### Step 1 — Camera intrinsics (`steps/step1_camera.py`)
**In:** photo. **Out:** `Camera(fx, fy, cx, cy, width, height)`.

- Read focal length from EXIF (`FocalLengthIn35mmFilm`) and convert to pixels: `fx = f35 / 36 * width`.
- No EXIF → assume a phone main camera, horizontal FOV ≈ 65°: `fx = (width / 2) / tan(65° / 2)`.
- Principal point = image centre. Downscale the photo so the long side is ≤ 1024 px first; scale intrinsics with it.

### Step 2 — Depth (`steps/step2_depth.py`)
**In:** photo, camera. **Out:** `depth[H, W]` in metres.

- Run **Depth Anything V2 Metric-Indoor Small** (`depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf`). It outputs metres directly, so scale is something we can measure and check, not only assume. About 5 s per photo on a MacBook (Apple GPU), ~100 MB download the first time.
- **Lens correction:** the model learned distances from 60° field-of-view images (Hypersim, 1024 × 768). A wider lens makes everything look smaller, so it guesses too far. Multiply depth by `(fx / short side) / (fx / short side at training)`. **Short side**, because the model's processor scales every image's short side to 518 px whatever the orientation (683 × 1024 → 518 × 770). The first version divided by the width, which made portrait photos 4/3 too deep; fixing it changed depth-only camera heights on the three portrait Unity renders from +76 / +59 / +24 % to +31 / +21 / −7 %.
- Back-project every pixel to a 3D point in camera space:
  `X = (u − cx) · Z / fx`, `Y = (v − cy) · Z / fy`, `Z = depth(u, v)`.

### Step 3 — Room geometry (`steps/step3_room.py`)
**In:** point cloud, camera, photo. **Out:** `Room(floor_plane, walls, scale, wall_color, name)`.

What the code does (every number below is in the report, `debug/<name>/room_report.json`):

1. **Floor:** RANSAC plane fit on points from the bottom 45 % of the image, keeping only planes whose normal is within 50° of camera "up" (−Y in camera space, because image rows grow downward). Refit with least squares on all inliers. The normal is world **up**; the distance from the camera to the plane is the **camera height**; the normal's tilt is the **camera pitch**.
2. **Scale**, in order of preference:
   - **known camera height** (`--camera-height`): scale so the camera is that high. Most accurate. Room 1: 1.85 m. A phone at chest height ≈ 1.4–1.5 m; professional interior photos are shot at ≈ 1.0–1.2 m.
   - **assumed ceiling height** (`--ceiling-height`, **default 2.7 m when the photo has no lens data**): scale so the detected ceiling is that high. Needs the ceiling in view.
   - **metric depth** (`--metric`, or the default when the photo has EXIF lens data): trust the model. After the lens-correction fix: −7 % to +31 % on the three Unity renders, −13 % on the room 1 Blender render. Too rough to rely on alone.
3. **Floor-aligned frame:** world x = camera right, y = up, z = camera forward flattened onto the floor. Every point gets a height above the floor.
4. **Ceiling:** the densest 10 cm band of points above the camera. Everything above it is ignored when looking for walls.
5. **Walls:** in the floor plan (x, z), repeatedly RANSAC-fit lines through points between the floor and the ceiling. A line is a wall only if its points reach ≥ 1.9 m high, run ≥ 1 m along the floor, and are present at mid height (both 1.0–1.6 m and 1.6–2.2 m). This rejects sofas, beds, table tops, and lines that join a low table edge to a ceiling beam. Rejected candidates are listed in the report for tuning.
6. **Yaw:** rooms are rectangular, so rotate the floor plan until the biggest wall is axis-aligned. Walls are then named left/right/back/front by which side of the camera they are on. On each side the **farthest** candidate wins: walls bound the room, furniture stands in front of them.
7. **Origin:** for a known room (`--room RenderedRoom`), place the best-seen side wall and the back wall at their known positions, so the origin is the room centre like in Unity. For an unknown room, x is midway between two side walls if both are seen, else under the camera.
8. **Wall tint:** the walls are a separate mesh with an unlit material whose texture already holds the plaster colour *and* the baked lighting. `wallColor` **multiplies** that texture, so `#ffffff` means "as baked". Default to the room's `default_tint`. Only emit another tint if the photo's wall is clearly a different colour, and keep it light (a dark tint also darkens the baked light).
9. **Room:** an existing room (room 1 → `RenderedRoom`) is used as is. A new room must first be built in Blender like PR #4. Use the measurements from this step (size, camera position, table/desk heights) as the brief, then add the room to `model_library.json`.

### Step 4 — Detect and segment objects (`steps/step4_detect.py`)
**In:** photo, labels from `model_library.json`, plus depth and floor from steps 2–3. **Out:** list of `Detection(label, score, box, mask, size, clip)`.

Three stages, each removing a different kind of mistake. All models are open weights loaded through `transformers` (no API key; ~1.5 GB downloaded once):

1. **Find candidates: Grounding DINO tiny** (`IDEA-Research/grounding-dino-tiny`). Prompt built from the pickable labels (`detect` not false): `"book . table lamp . mug ."`. "table lamp" rather than "lamp" so floor lamps score lower. Runs on the **full-resolution** image (mugs are ~25 px). Score ≥ 0.30, per-label non-max suppression, boxes between 0.01 % and 25 % of the image.
2. **Outline: SAM base** (`facebook/sam-vit-base`) with each box as the prompt → pixel mask, eroded 2 px. Masks and boxes are scaled to the working resolution of steps 2–3.
3. **Size check** (needs steps 2–3, so it runs right after them). One robust depth per object (median inside its mask) turns the box's pixels into metres: `size = pixels × depth / focal length`. The bottom-centre pixel at that depth gives the height above the floor. Each label has `plausible` ranges in `model_library.json` (mug 5–22 cm tall; lamp 0.3–1.0 m tall, **sitting on furniture** (base ≥ 0.25 m) and **not a tall thin box** (height ≤ 3 × width: a table lamp is ~1.5, the visible top of a floor lamp ~5)). Rejects floor lamps (1.6 m tall, or aspect 4–5), wall sconces (base 1.65 m), shelf vases (base 1.85 m). Measuring the mask's 3D points one by one was tried first and failed: single-photo depth blurs at small objects' edges (a 10 cm mug measured 28 cm wide).
4. **Second opinion: CLIP** (`openai/clip-vit-base-patch32`). A padded, upscaled crop of each survivor is compared with its own phrases ("a coffee mug", "a cup") and with same-size look-alikes ("a plant pot", "a candle", "a drinking glass", …). Kept only if its own label wins and CLIP is ≥ 0.35 sure. Rejects plant pots (0.70 vs 0.00) and a candle (0.29). For books the look-alike list deliberately leaves out tray, tablet, laptop and cardboard box: CLIP confuses dark closed books with the first three, and our plain book prefab turned at an angle with a cardboard box (0.59 vs 0.28); missing a real book is worse for us than calling a laptop a book. For lamps it leaves out floor lamp and chair: CLIP judges the padded crop, and next to a TV or a chair it called our table lamp a floor lamp (0.32 vs 0.16) and then a chair (0.37 vs 0.24); geometry rejects both instead. `--no-clip` turns this stage off.

Output: `debug/<name>/detections.png` (masks, boxes, labels, answer-key crosses) and `detect_report.json` (kept with sizes, rejected with reasons, grade).

### Step 5 — Place each object in 3D (`steps/step5_place.py`)
**In:** step 4's detections, the room from step 3, the room's entry in `model_library.json`. **Out:** one `Placement(label, position, rotation_y, size, surface)` per detection, in the scene-JSON convention (`x, z` = footprint centre, `y` = top of the surface it rests on).

Two modes:
- **Built room (`--room <name>`, the room has a reference camera with `look_at`).** Each built room was modelled from its photo, so its reference camera is where the photo was taken. The position then comes from geometry alone, with no depth: follow the ray through the centre of the object's box until it reaches the height of a surface top plus half the object's height, and keep it if it lands on that surface. Of the surfaces it can land on, prefer the one whose top matches step 4's measured base height (±20 cm), then the nearest. Clamp so the footprint (`footprint_m` in the library) stays on the surface. Facing: toward the camera. Same-label placements closer than 10 cm are merged.
- **Unknown room (no `--room`).** Step 4's depth-based centre and base height in step 3's room frame.

**Why geometry, not depth.** Measured before building this: step 4's depth-based centres were off by 17–19 cm in room 1 but **34–108 cm** in the living rooms. The rotation of the room was right (within 3°); the depth itself stretched distances by 13–21 %, even with the true camera height. Correcting depth with an offset didn't help (the floor stayed flat whatever the offset, so there was nothing to fit). Ray geometry needs no depth at all.

### Step 6 — Match each object to a prefab (`steps/step6_match.py`)
**In:** step 5's placements, `model_library.json`. **Out:** `SceneObject(label, model, position, rotation_y, scale)` plus warnings.
- **Model:** a lookup (one available pickable model per label today). With several, it takes the first and warns; choosing by thumbnail similarity is future work.
- **Scale:** measured box size (pixels × exact distance from step 5 ÷ focal length) ÷ what the real model's box would measure from that viewpoint. Seen from above, a box also contains the object's top, so the expected height is `height × cos(a) + depth × sin(a)` for a view `a` degrees down. Books lying flat use width instead, compared with the average of their long side and diagonal. Clamped to 0.7–1.4; outside that, scale 1.0 with a warning.
- Then step 7 writes the scene JSON and `validate_scene.py --strict` checks it. With `--answers` it goes to `debug/<name>/` and is graded; without, to `scenes/generated/scene_<name>.json`.

### Step 7 — Export the scene JSON (`steps/step7_export.py`)
**In:** room, matched placements. **Out:** `scenes/scene_<name>.json`.

- Convert to Unity axes (section 3), round to 2 decimals (rotation to whole degrees).
- **Sanity rules** (same as the review checklist): every position within ±100 m (realistically inside the room bounds), scale > 0, every `model` exists in `model_library.json`, nothing below the floor.
- Write the file, then run `validate_scene.py` on it. A failing validation must stop the run.

### Step 8 — Human check and tuning
- Load the JSON in Unity, put on the headset, walk around.
- Fix obvious problems directly in the JSON (an object 30 cm off, a wrong rotation). Note what you fixed in the PR so we know which steps need work.
- If the automatic result is worse than the hand-made file, ship the hand-made file. That is the plan, not a failure.

## 3. Coordinate conventions (agree, then never change)

| | Camera space (steps 2–5) | World / Unity space (JSON) |
|---|---|---|
| Units | metres after step 3 | metres |
| Up | −Y (image rows grow downward) | **+Y** |
| Forward | +Z (into the photo) | **+Z** = away from where the photo was taken |
| Right | +X | +X (Unity is left-handed, y up) |
| Origin | the camera | **centre of the room floor**, y = 0 on the floor |

- Camera → world: flip Y (camera space is right-handed with y down; Unity is left-handed with y up, so one flip converts both), rotate so the floor normal becomes +Y, project the camera's forward direction onto the floor to get +Z, translate so the floor centre is the origin.
- `rotationY` is degrees around +Y, clockwise when seen from above (Unity's convention), 0 = the model's own forward (+Z) points along world +Z.
- The player spawns near where the camera was, so the VR view starts like the photo. Room 1: camera at (0.95, 1.85, −2.62), XR rig at (1.25, 0, −2.25) with yaw −22° (PR #4).
- PR #4 builds in Blender (Z up, Y forward) and maps it to Unity as **Unity x = Blender x, Unity z = Blender y, Unity y = Blender z**, the same frame as here. Numbers read from `build_room.py` can be copied over by swapping the last two values.

## 4. Output contract (the scene JSON)

Agreed between Role B and Role A in [TEAM.md](../TEAM.md). Example: [`scenes/scene_room_a.json`](scenes/scene_room_a.json).

```json
{
  "version": 1,
  "room": "RenderedRoom",
  "wallColor": "#ffffff",
  "objects": [
    { "label": "mug", "model": "mug", "position": [0.80, 0.49, 0.68], "rotationY": 0, "scale": 1.0 }
  ]
}
```

That is room 1 as PR #4 built it: the mug on the coffee table. The full file in `scenes/` also has the bedside lamp at (−0.58, 0.59, 1.89). The baked furniture is part of the room and never appears in `objects`.

| Field | Meaning |
|---|---|
| `version` | Format version. The loader should refuse a version it does not know. *(New, proposed in this PR.)* |
| `room` | Room name from `model_library.json` (room 1 = `RenderedRoom`, the scene from PR #4). |
| `wallColor` | `#rrggbb` **tint** that multiplies the baked wall texture (`_BaseColor` on the `Architecture` material). `#ffffff` = as baked. |
| `objects[]` | **Pickables only.** Static furniture is baked into the room. |
| `objects[].label` | What the detector saw (for debugging and UI). |
| `objects[].model` | Prefab name in `Assets/_Project/Prefabs/Pickables`, listed in `model_library.json` with `kind: "pickable"`. |
| `objects[].position` | `[x, y, z]` metres, world space. `x, z` = centre of the object's footprint, `y` = height of the surface it rests on. The loader lifts the object so the bottom of its collider sits at `y`, so prefab pivots don't matter. |
| `objects[].rotationY` | Degrees around up. |
| `objects[].scale` | Multiplier on the model's real `height_m`: the loader fits the instance to `height_m × scale` by its renderer bounds, as PR #4 does for the mug. Range 0.7–1.4. |

Unknown extra fields (for example `source`) must be ignored by the loader. Any other format change: tell Role A first.

## 5. Model library (`model_library.json`)

The single list of room and model names both sides use.

- **`rooms`:** for each hand-built room: `size_m` `[x, y, z]`, the reference `camera`, the player `spawn`, `default_tint`, and `surfaces`, the static tables, desk, bed and floor that pickables can rest on. Room 1's values are copied from `BuildRenderedRoom.cs` in PR #4. If someone moves furniture there (which also needs a Blender rebake), update the surfaces here in the same PR.
- **`models`:** for each pickable prefab: `label`, `kind: "pickable"`, `height_m` (**real-world** height, e.g. mug 0.10 m, not the size the prefab happens to import at), and `status` (`available` = prefab exists, `planned` = not built yet). When you add a prefab to `Prefabs/Pickables`, add its entry here in the same PR.

## 6. Running it

```bash
cd pipeline
python3.12 -m venv .venv && source .venv/bin/activate   # 3.12: PyTorch wheels are safest there
pip install -r requirements.txt
python -m unittest discover -s tests -v                  # geometry tests, no ML models needed

# Steps 1-3 on a photo of room 1, graded against the known room:
python run_pipeline.py photos/room_1.jpg --name room_1 --room RenderedRoom --camera-height 1.85 --stop-after room
# Same check on the Blender render of room 1 (known 73.3 deg lens):
python run_pipeline.py ../docs/room-blender.png --name render_check --room RenderedRoom --hfov 73.3 --camera-height 1.85 --stop-after room

python validate_scene.py scenes/scene_room_a.json        # stdlib only
```

Each run prints PASS/FAIL per check and writes `debug/<name>/depth.png`, `room_overlay.png` (floor green, left wall blue, right orange, back pink) and `room_report.json`.

- Put input photos in `pipeline/photos/`. That folder is **git-ignored**: only commit a photo you own or have permission to share (the repo is public), and then with `git add -f`.
- Debug images (depth maps, masks, overlays) go to `pipeline/debug/`, which is not committed.
- Model weights download to the Hugging Face cache, never into the repo.

## 7. Build order (what to do first)

1. ✅ Hand-made `scenes/scene_room_a.json` matching PR #4's room 1, so Role A can build the loader. *(This PR.)*
2. ✅ Steps 1 + 2 → depth map image.
3. ✅ Step 3 → floor plane, walls, ceiling, scale, graded against room 1 (on the Blender render; see results below).
3b. ✅ Step 3 on the two living-room photos (see results). Both are now built rooms (`LivingRoomSofa`, PR #9; `LivingRoomTV`, PR #11) with their real `size_m`, `camera`, `spawn` and `surfaces` in `model_library.json`.
3c. ✅ Answer keys: `scenes/scene_room_a.json`, `scene_living_room_sofa.json`, `scene_living_room_tv.json` list where every pickable really is in each built room.
4. ✅ Step 4, find the pickables (see "Step 4 results" below).
5. ✅ Steps 5 + 6: placed on surfaces by ray geometry, matched, scaled, scene JSON written and graded (see "Steps 5–6 results").
5b. ✅ Photo cameras solved for both living rooms; real photos place pickables relative to their table (see "Photo cameras").
6. **Next:** the Unity runtime loader (Role A) that reads `scenes/generated/*.json`; optionally move the model furniture to where the photos show it (re-bake), which would let real photos use the same exact ray placement as the renders.
6. Unity loader (Role A): read a scene JSON and place the pickables, instead of positions hardcoded in each room's builder.
7. Only then: more pickable types, better rotation, hero object via image-to-3D, live photo demo.

### Step 4 plan (kept for reference; see "Step 4 results" for what was built)

**Goal:** given a picture of a room, find every mug, book and lamp in it, with a clean outline (mask) of each.

**Test set with known answers.** Photos of real rooms have no answer key, but our three built rooms do. Each builder saves a Unity render from a known camera with the pickables in it:

| Image | Room | Pickables visible | Camera (known) |
|---|---|---|---|
| `docs/living-room-sofa-unity.png` | LivingRoomSofa | mug, book, lamp | `rooms.LivingRoomSofa.camera` |
| `docs/living-room-tv-unity.png` | LivingRoomTV | book, mug, lamp (moved to the left end of the TV cabinet so it is visible; it used to hide behind the armchair) | `rooms.LivingRoomTV.camera` |
| `docs/room-unity.png` | RenderedRoom | mug, lamp (the book from PR #10 is on the desk, out of frame) | `rooms.RenderedRoom.camera` |

Because the camera and every object's true position are known, steps 4–6 can be graded end to end: the automatic scene JSON should match the answer keys in `scenes/`. The two living-room photos (local only) are the real-world check, with no answers; there, only the book in the TV photo is one of our objects.

**How:**
1. **Detect:** Grounding DINO tiny (`IDEA-Research/grounding-dino-tiny`, open weights via `transformers`, no API key) prompted with `"mug . book . lamp ."` from `model_library.json`. Keep boxes with score ≥ 0.35; one best box per object where the scene can only have one.
2. **Outline:** SAM (via `transformers`, e.g. `facebook/sam-vit-base`, or SAM 2 if it loads cleanly) with each box as the prompt. Erode masks by 2–3 px.
3. **Save** `debug/<name>/detections.png` (boxes, labels, scores, masks over the image) and add the detections to the report.
4. **Grade** with `run_pipeline.py --stop-after detect`: for each answer-key object, project its true 3D position into the image with the known camera; a detection counts if its box contains that point and the label matches.

**Success criteria for step 4:**
- On the two living-room renders: all 3 pickables found in each, **no false detections**: a vase, a candle or the baked floor lamp must not count as one of our objects (see risks).
- Masks cover the object without spilling onto the table (checked by eye on `detections.png`).
- On the real TV photo: the book on the coffee table is found.
- Runs in under 30 s per image on the laptop.

**Risks to watch:**
- "lamp" will also match the baked floor lamp, sconce and desk lamp. Fix with size (our lamp is 0.57 m and sits on a table; step 5 will know heights) or a stricter prompt like `"table lamp"`.
- "book" will also match baked decor books (coffee-table books in rooms 1 and TV). Step 4 can't tell baked from pickable; that's fine for real photos, and on renders the grading only counts matches to answer-key positions.
- Tiny objects (the mug is ~25 px wide in the renders): run detection on the full-resolution image, not the 1024 px working copy.

### Results so far (room 1 Blender render, `docs/room-blender.png`)

The real demo photos are not in the repo yet, so steps 1–3 were tested on the Blender render of room 1. It shows the same room from the same camera, and every true measurement is known from `build_room.py`.

| Check (target) | Scale from depth model | Camera height fixed at 1.85 m | Truth |
|---|---|---|---|
| Camera height (± 0.25 m) | ❌ 2.14 m | (given) 1.85 m | 1.85 m |
| Room width (± 15 %) | — (right wall not found) | ✅ 3.81 m | 4.20 m |
| Camera to back wall (± 15 %) | ✅ 6.13 m | ✅ 5.08 m | 5.42 m |
| Camera sideways position (± 0.30 m) | ❌ 1.68 m | ✅ 1.24 m (❌ 1.28 m after PR #7's re-bake, see note) | 0.95 m |
| Ceiling height | 3.95 m | 3.42 m | 3.50 m |
| Camera pitch | 13.8° down | 13.8° down | 12.4° down |
| Floor flatness | ✅ 1.1 cm rms | ✅ 1.1 cm rms | flat |
| Walls found | ✅ back, left | ✅ back, left, right | — |

Runtime about 5 s after the first model download.

Note: PR #7 re-baked room 1 without the baked bedside lamp, which changed `docs/room-blender.png`. On the new render the sideways camera position comes out at 1.28 m, 3 cm outside the ±0.30 m target; everything else still passes. Worth a look when tuning wall detection; not a regression in the code. The overlay, depth map and full report of the "camera height fixed" run are in [`results/`](results/).

**Takeaways:**
- The geometry (floor, walls, ceiling, angles) is solid. **Scale is the weak point**: the depth model alone is 13–21 % off on this render (too large before the lens-correction fix, a bit too small after it). Use `--camera-height` whenever the photographer can say roughly how high they held the camera.
- The right wall is seen only as a thin strip at the image edge, in line with the desk front, so its position is pulled ~30 cm inward. That is why, for a known room, the origin comes from the best-seen side wall plus the known width.
- Not tested yet: anything after step 3.

### Results on the two living-room photos

Two real photos (`photos/living_room_sofa.jpg`, `photos/living_room_tv.jpg`, kept local, see below). Neither has lens data, so the lens is assumed (26 mm phone equivalent) and the scale comes from a 2.7 m ceiling. There is no ground truth, so the scale was **cross-checked against objects of typical size**:

| | Sofa photo | TV photo |
|---|---|---|
| Depth model alone | camera 2.05 m, ceiling 5.48 m ❌ implausible | camera 1.97 m, ceiling 4.97 m ❌ implausible |
| Scaled to a typical object | sofa 2.0 m wide → camera 1.03 m, ceiling 2.74 m | 65" TV 1.45 m wide → camera 1.24 m, ceiling 3.12 m |
| **Scaled to 2.7 m ceiling (default)** | **camera 1.01 m**, back wall 3.11 m | **camera 1.07 m**, back wall 3.36 m |
| Camera pitch | 5.8° down | 3.5° down |
| Floor flatness | 1.8 cm rms | 2.2 cm rms |
| Walls found | back | back (the slatted TV wall), seen at ~40° |

The ceiling prior and the object check agree within 2–17 %, and both put the camera at ~1.0–1.2 m, which is how interior photographers shoot. Two fixes came from these photos: the no-EXIF lens guess now works for portrait photos (26 mm on the long side instead of a fixed horizontal angle), and walls must have points at mid height (a coffee-table edge + ceiling beam was being taken as a wall).

Limits seen: only the back wall is found (side walls are hidden behind curtains or furniture, or out of frame), so room width is not measured; the measured wall colour on the TV photo is the dark wood slats and TV, not the paint.

**The photos are not committed.** They look like professional photos from the web and this repo is public. Keep them in `pipeline/photos/` locally (the folder is git-ignored) unless you own them or have permission.

### Step 4 results

```bash
python run_pipeline.py ../docs/living-room-sofa-unity.png --name sofa_detect --answers scenes/scene_living_room_sofa.json --stop-after detect
python run_pipeline.py ../docs/living-room-tv-unity.png  --name tv_detect   --answers scenes/scene_living_room_tv.json   --stop-after detect
python run_pipeline.py ../docs/room-unity.png            --name room1_detect --answers scenes/scene_room_a.json        --stop-after detect
python run_pipeline.py photos/living_room_tv.jpg --name tv_photo --stop-after detect     # real photo, no answer key
```

With `--answers`, the run uses the room's reference camera (lens and height) from `model_library.json`, projects each answer-key object into the image and grades the result. Baked objects that look exactly like a pickable are listed under `decor` in the answer key and reported separately (step 4 can't know they're baked; in a real photo they'd be correct).

| Image | Found | False detections | Notes |
|---|---|---|---|
| Sofa room render | ✅ **3/3** (mug 0.70, book 0.55, lamp 0.57) | **0** | floor lamp rejected by size (1.57 m); plant pot rejected by CLIP |
| TV room render | ✅ **3/3** (book, mug, lamp) | **0** | the lamp used to hide behind the armchair; moved to the left end of the TV cabinet it is found (0.61). Candle and shelf vase rejected |
| Room 1 render | ✅ **2/2** (mug, lamp) | **0** | the book is out of frame; the baked coffee-table book and closed notebook reported as decor |
| Real TV photo | ✅ the book on the coffee table | 1 (ambiguous) | wall sconce rejected (base 1.65 m); a small amber glass on the side table kept as a mug |
| Real sofa photo | nothing (correct: none of our objects) | **0** | its floor lamp rejected by CLIP |

Measured sizes on the renders: mugs 10–12 cm (true 10), lamps 0.53–0.54 m (true 0.57), and the height of each object's base within ~5 cm of its table top. About 12–15 s per image (3 models, Apple GPU), after a one-time ~1.5 GB download.

What it took to get here, in order: (1) detector alone found 7/8 but with 3–4 false detections per image; (2) per-point size check rejected real mugs (depth blur); (3) box-based size check fixed that and removed floor lamp/sconce/shelf vase; (4) CLIP removed same-size look-alikes (plant pots, candle); (5) look-alike lists tuned on the real TV photo, whose dark books CLIP took for a tablet/laptop.

**Known limits:** occluded objects are missed; same-size, same-shape things can still pass (a glass as a mug, a laptop as a book); tested on 3 renders and 2 photos only, so the thresholds may need re-tuning on new photos. Render overlays are in `results/` (`*_detections.png`).

### Steps 5–6 results

```bash
python run_pipeline.py ../docs/living-room-sofa-unity.png --name full_sofa  --answers scenes/scene_living_room_sofa.json
python run_pipeline.py ../docs/living-room-tv-unity.png  --name full_tv    --answers scenes/scene_living_room_tv.json
python run_pipeline.py ../docs/room-unity.png            --name full_room1 --answers scenes/scene_room_a.json
python run_pipeline.py photos/living_room_tv.jpg --name living_room_tv_photo --room LivingRoomTV   # -> scenes/generated/
python run_pipeline.py ../docs/demo/sofa-moved-unity.png --name sofa_moved --room LivingRoomSofa --render   # a render with objects moved, no answer key
```

`--render` = the image is a Unity render of `--room` from its reference camera (e.g. with the pickables moved): exact placement like the graded renders, without needing an answer key. The Unity **RoomVR → Photo to VR** window runs exactly these commands; see `docs/PHOTO_TO_VR.md`.

**Moved-object demo layouts** (`scenes/demo/*.json`, rendered to `docs/demo/*-unity.png`): the sofa room with the mug on the pouf and the book at the front of the coffee table, and the TV room with the mug on the coffee table and the book on the side table. Graded against those layouts, both are **3/3 found and placed, 0 false**: layouts the algorithm was never tuned on.

Graded against the answer keys (success = position within 15 cm, table height within 1 cm, scale 0.8–1.25, right model):

| Render | Right | Position error | Scale |
|---|---|---|---|
| Sofa room | ✅ **3/3** (mug, book, lamp) | 3–5 cm | 1.03–1.07 |
| TV room | ✅ **3/3** (book, mug, lamp) | 1–5 cm | 0.87–1.03 |
| Room 1 | ✅ **2/2** (mug, lamp; the book is out of frame) | 3–6 cm | 0.98–0.99 |

Every object is placed at its table's exact height and passes `validate_scene.py --strict`. Room 1's two baked books are also placed and reported as decor (in a real photo they'd be correct). Before the viewing-angle correction, scales were 1.1–1.25.

**Real TV photo:** the book is placed on the modelled coffee table and written to `scenes/generated/scene_living_room_tv_photo.json`. Its scale is 1.0 with a warning: the photo shows a stack of two large books (0.43 m), outside the scale range. The amber glass from step 4 lands on no modelled surface and is dropped (correctly: it isn't a mug).

**Checked in Unity** with `Assets/_Project/Editor/PipelineScenePreview.cs` (opens the room, replaces its pickables with the scene JSON's, renders the reference camera, saves nothing):
```bash
Unity -batchmode -quit -projectPath .. -executeMethod RoomVR.EditorTools.PipelineScenePreview.Run \
  -sceneJson pipeline/debug/full_sofa/scene_full_sofa.json -out pipeline/debug/preview_full_sofa.png
```
In the sofa and TV renders the generated objects sit where the hand-placed ones do (`results/preview_*.png`). Differences: rotation (facing the camera instead of the hand-picked angle) and the mug's material (the room builders give it a ceramic look, the preview uses the prefab's default).

**Limit found (fixed below):** the built TV room's reference camera doesn't line up with the photo, so a real-photo object landed on the right table but not on its spot.

### Photo cameras (`steps/align_camera.py`, `landmarks/*.json`)

The room builders' reference cameras were placed by eye. To use real photos, each living room's **photo camera** is solved from landmarks: points whose 3D position is known in the model and whose pixel was marked in the photo (with a zoomed 5–10 px grid). Levenberg–Marquardt over position, turn, tilt and vertical field of view, with soft priors (camera height from step 3, camera inside the room).

```bash
python -m steps.align_camera --write landmarks/LivingRoomTV.json landmarks/LivingRoomSofa.json   # -> rooms.<room>.photo
```

| Room | Landmarks | Camera | Error |
|---|---|---|---|
| LivingRoomTV | TV corners, slatted-panel top, cabinet corner (7) | (2.10, 0.96, −2.01), turned 29° left, 66° vertical FOV | 11 px rms, 21 px max (of 505 px) |
| LivingRoomSofa | the two posters' corners (8) | (1.90, 1.24, −2.20), turned 24° left, 50° vertical FOV | 16 px rms, 28 px max (of 987 px) |

Checked by rendering the TV room in Unity from the solved camera (`PipelineScenePreview.cs -cameraPos … -lookAt … -vfov … -size …`) and drawing its edges over the photo: the TV wall, slats, cabinet, niche shelves, ceiling beams and branches line up; the old reference camera put the TV wall far off.

**What it found: the model furniture is off, not just the camera.** In the sofa room no single camera fits both the posters and the furniture (with the furniture included the "best" camera was 2.4 m high). The model's tables sit ~0.5 m off relative to the walls, because they were placed by eye. Both solved cameras also sit at the edge of the modelled room, so the real rooms are probably a bit wider.

**So real photos are placed relative to their table.** Each landmarks file also marks the centre pixel of each table top (`surface_pixels`). Step 5 (real photo, `--room` without `--answers`) uses the photo camera to find where the table and the object are in the photo's geometry, and applies the object's offset from its table to the model's table. The object lands on the right table at the right spot on it, whatever the model's table placement. Renders with `--answers` keep using the reference camera (3/3, 3/3, 2/2).

**Results on the real photos:** TV photo → the book on the coffee table and the amber glass on the side table (as a mug, the borderline step 4 detection; its measured size is out of range, so scale 1.0 with a warning). Sofa photo → empty scene (none of our objects in it). There is no answer key for real photos, so exact accuracy isn't measured; Unity preview: `results/preview_tv_photo_aligned.png`.

**Limits:** 2 px of marking noise moves a camera ~10 cm (unit test); landmarks were marked by hand; table centres are marked as the centre of the visible top, which is approximate for round tables seen at an angle; room 1 has no photo in the repo, so it has no photo camera.

## 8. Known risks

| Risk | What we do |
|---|---|
| Depth wrong on glass, mirrors, dark corners | Erode masks, use medians, hand-fix the JSON |
| Scale off (no EXIF, unusual camera height) | Clamp scales, cross-check with door/ceiling height, hand-fix |
| Object in photo we have no model for | Detector is prompted only with our labels, so it is skipped |
| Room numbers drift from PR #4 (furniture moved, room resized) | `validate_scene.py` checks positions against `size_m` and `surfaces`; update `model_library.json` with any room change |
| Occluded objects (half behind a sofa) | Position from visible part only; accept, or hand-fix |
| ML models too slow / won't install | Steps 2/4/6 are swappable; the hand-made JSON always works |
