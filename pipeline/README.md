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

Status: **steps 1–4 work** (camera, depth, floor/walls/scale, finding the pickables; see "Results so far" and "Step 4 results" below). **Steps 5–6 are not started**; their objectives and success criteria are written in section 2. `validate_scene.py` works. The answer keys in [`scenes/`](scenes/) list where every pickable really is in each of the three built rooms, so Role A can build the scene loader now, without waiting for the algorithm.

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
- **Lens correction:** the model learned distances from 60° field-of-view images (Hypersim). A wider lens makes everything look smaller, so it guesses too far. Multiply depth by `(fx/width) / (fx/width at 60°)`. On the room 1 render (73° lens) this is ×0.78 and cut the scale error from ~49 % to ~15 %.
- Back-project every pixel to a 3D point in camera space:
  `X = (u − cx) · Z / fx`, `Y = (v − cy) · Z / fy`, `Z = depth(u, v)`.

### Step 3 — Room geometry (`steps/step3_room.py`)
**In:** point cloud, camera, photo. **Out:** `Room(floor_plane, walls, scale, wall_color, name)`.

What the code does (every number below is in the report, `debug/<name>/room_report.json`):

1. **Floor:** RANSAC plane fit on points from the bottom 45 % of the image, keeping only planes whose normal is within 50° of camera "up" (−Y in camera space, because image rows grow downward). Refit with least squares on all inliers. The normal is world **up**; the distance from the camera to the plane is the **camera height**; the normal's tilt is the **camera pitch**.
2. **Scale**, in order of preference:
   - **known camera height** (`--camera-height`): scale so the camera is that high. Most accurate. Room 1: 1.85 m. A phone at chest height ≈ 1.4–1.5 m; professional interior photos are shot at ≈ 1.0–1.2 m.
   - **assumed ceiling height** (`--ceiling-height`, **default 2.7 m when the photo has no lens data**): scale so the detected ceiling is that high. Needs the ceiling in view.
   - **metric depth** (`--metric`, or the default when the photo has EXIF lens data): trust the model. ~15 % too large on the room 1 render, 1.6–2× too large on the two living-room photos without lens data.
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
3. **Size check** (needs steps 2–3, so it runs right after them). One robust depth per object (median inside its mask) turns the box's pixels into metres: `size = pixels × depth / focal length`. The bottom-centre pixel at that depth gives the height above the floor. Each label has `plausible` ranges in `model_library.json` (mug 5–22 cm tall; lamp 0.3–1.0 m tall **and sitting on furniture**, base ≥ 0.25 m). Rejects floor lamps (1.6 m), wall sconces (base 1.65 m), shelf vases (base 1.85 m). Measuring the mask's 3D points one by one was tried first and failed: single-photo depth blurs at small objects' edges (a 10 cm mug measured 28 cm wide).
4. **Second opinion: CLIP** (`openai/clip-vit-base-patch32`). A padded, upscaled crop of each survivor is compared with its own phrases ("a coffee mug", "a cup") and with same-size look-alikes ("a plant pot", "a candle", "a drinking glass", …). Kept only if its own label wins and CLIP is ≥ 0.35 sure. Rejects plant pots (0.70 vs 0.00) and a candle (0.29). For books the look-alike list deliberately leaves out tray, tablet and laptop: CLIP confuses dark closed books with all three, and missing a real book is worse for us than calling a laptop a book. `--no-clip` turns this stage off.

Output: `debug/<name>/detections.png` (masks, boxes, labels, answer-key crosses) and `detect_report.json` (kept with sizes, rejected with reasons, grade).

### Step 5 — Place each object in 3D (`steps/step5_place.py`) — objective, not started
**In:** step 4's detections (each already has `size`: centre, height, width, base height, in world metres), the room from step 3, the room's `surfaces` from `model_library.json`. **Out:** one `Placement(label, position, rotation_y, size)` per detection, in the scene-JSON convention (`x, z` = footprint centre, `y` = top of the surface it rests on).

**Objectives:**
1. **Position (`x, z`):** start from step 4's measured centre. Do not take the median of the mask's 3D points directly: step 4 showed that single-photo depth blurs at small objects' edges (a 10 cm mug measured 28 cm wide that way), so reuse step 4's one-depth-per-object measurement.
2. **Resting surface (`y`):** for a built room, snap to the highest known surface under `x, z` with `resting_surface()` (already written and tested). If `x, z` lands just off a table (within ~10 cm of its edge), nudge it onto the table instead of dropping the object to the floor. Use step 4's measured base height to choose between two surfaces when both are plausible (e.g. side table vs floor). For a room without known surfaces, use the measured base height directly.
3. **Keep it on the table:** clamp `x, z` so the object's footprint (from the model's real size) does not overhang the surface it rests on.
4. **Rotation (`rotationY`), first version:** face the camera. Better version only if time allows: compare the crop with renders of the prefab at 12 yaw angles (30° steps) using CLIP and keep the best.
5. **One object per detection;** if two detections of the same label end up within ~10 cm, keep the higher-scoring one.

**Success criteria (graded against the answer keys in `scenes/`, on the three room renders):**
- Every pickable step 4 found is placed within **15 cm** (x, z) of its answer-key position.
- `y` equals the right surface height (within 1 cm) for every found pickable: the mug on the coffee table at 0.42 m, the lamp on the side table at 0.53 m, and so on.
- No pickable overhangs its table (the same check as the Unity EditMode tests).

### Step 6 — Match each object to a prefab (`steps/step6_match.py`) — objective, not started
**In:** step 5's placements, `model_library.json`. **Out:** one `SceneObject(label, model, position, rotation_y, scale)` per placement.

**Objectives:**
1. **Model choice:** candidates = library models with the same `label`, `kind: "pickable"`, `status: "available"`. Today there is exactly one per label (mug, book, lamp), so this is a lookup. When there are several (e.g. two mugs), pick the one whose thumbnail CLIP (already loaded for step 4, via `transformers`) rates closest to the crop.
2. **Scale:** measured height ÷ the model's real `height_m` (books: measured width ÷ the book's real width, since a lying book's height is mostly perspective). **Clamp to 0.7–1.4** with `clamp_scale()` (already written); outside that range log a warning and use 1.0. The Unity loader fits each instance to `height_m × scale`.
3. **Write the scene JSON** with step 7 (`write_scene()` already works), then run `validate_scene.py`.
4. **Grade the whole pipeline end to end:** `run_pipeline.py <render> --answers scenes/<room>.json` should report, per object, found / position error / height error / scale, and the written scene JSON should pass `validate_scene.py --strict`.

**Success criteria:**
- On the sofa and room 1 renders, the automatic scene JSON contains the same pickables as the answer key (the TV room may miss the hidden lamp), each with the right `model`, positions within 15 cm, and `scale` between 0.8 and 1.25.
- The automatic JSON passes `validate_scene.py --strict` without hand edits.
- On the real TV photo, the book is written into the scene JSON on the coffee table.
- Out of scope for steps 5–6: the Unity loader that reads the JSON (Role A), new pickable types, image-to-3D models.

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
5. **Next: steps 5 + 6** (objectives and success criteria in section 2, "Step 5" and "Step 6"). Not started. Step 4 already measures each pickable's centre, size and height above the floor, so step 5 is mostly snapping that to the known surfaces; step 6 is a lookup plus scale, then the first automatic scene JSON, graded against the answer keys.
6. Unity loader (Role A): read a scene JSON and place the pickables, instead of positions hardcoded in each room's builder.
7. Only then: more pickable types, better rotation, hero object via image-to-3D, live photo demo.

### Step 4 plan (kept for reference; see "Step 4 results" for what was built)

**Goal:** given a picture of a room, find every mug, book and lamp in it, with a clean outline (mask) of each.

**Test set with known answers.** Photos of real rooms have no answer key, but our three built rooms do. Each builder saves a Unity render from a known camera with the pickables in it:

| Image | Room | Pickables visible | Camera (known) |
|---|---|---|---|
| `docs/living-room-sofa-unity.png` | LivingRoomSofa | mug, book, lamp | `rooms.LivingRoomSofa.camera` |
| `docs/living-room-tv-unity.png` | LivingRoomTV | book, mug, lamp (partly behind the armchair) | `rooms.LivingRoomTV.camera` |
| `docs/room-unity.png` | RenderedRoom | mug, lamp (the book from PR #10 is on the desk, out of frame) | `rooms.RenderedRoom.camera` |

Because the camera and every object's true position are known, steps 4–6 can be graded end to end: the automatic scene JSON should match the answer keys in `scenes/`. The two living-room photos (local only) are the real-world check, with no answers; there, only the book in the TV photo is one of our objects.

**How:**
1. **Detect:** Grounding DINO tiny (`IDEA-Research/grounding-dino-tiny`, open weights via `transformers`, no API key) prompted with `"mug . book . lamp ."` from `model_library.json`. Keep boxes with score ≥ 0.35; one best box per object where the scene can only have one.
2. **Outline:** SAM (via `transformers`, e.g. `facebook/sam-vit-base`, or SAM 2 if it loads cleanly) with each box as the prompt. Erode masks by 2–3 px.
3. **Save** `debug/<name>/detections.png` (boxes, labels, scores, masks over the image) and add the detections to the report.
4. **Grade** with `run_pipeline.py --stop-after detect`: for each answer-key object, project its true 3D position into the image with the known camera; a detection counts if its box contains that point and the label matches.

**Success criteria for step 4:**
- On the two living-room renders: all 3 pickables found in each (the TV-room lamp may be partly hidden: found or honestly reported as missed), **no false detections**: a vase, a candle or the baked floor lamp must not count as one of our objects (see risks).
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
- The geometry (floor, walls, ceiling, angles) is solid. **Scale is the weak point**: the metric model is ~15 % too large here even after the lens correction. Use `--camera-height` whenever the photographer can say roughly how high they held the camera.
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
| TV room render | **2/3** (book, mug) | **0** | the lamp is really hidden behind the armchair (only the top of its shade shows); candle and shelf vase rejected |
| Room 1 render | ✅ **2/2** (mug, lamp) | **0** | the book is out of frame; the baked coffee-table book and closed notebook reported as decor |
| Real TV photo | ✅ the book on the coffee table | 1 (ambiguous) | wall sconce rejected (base 1.65 m); a small amber glass on the side table kept as a mug |
| Real sofa photo | nothing (correct: none of our objects) | **0** | its floor lamp rejected by CLIP |

Measured sizes on the renders: mugs 10–12 cm (true 10), lamps 0.53–0.54 m (true 0.57), and the height of each object's base within ~5 cm of its table top. About 12–15 s per image (3 models, Apple GPU), after a one-time ~1.5 GB download.

What it took to get here, in order: (1) detector alone found 7/8 but with 3–4 false detections per image; (2) per-point size check rejected real mugs (depth blur); (3) box-based size check fixed that and removed floor lamp/sconce/shelf vase; (4) CLIP removed same-size look-alikes (plant pots, candle); (5) look-alike lists tuned on the real TV photo, whose dark books CLIP took for a tablet/laptop.

**Known limits:** occluded objects are missed; same-size, same-shape things can still pass (a glass as a mug, a laptop as a book); tested on 3 renders and 2 photos only, so the thresholds may need re-tuning on new photos. Render overlays are in `results/` (`*_detections.png`).

## 8. Known risks

| Risk | What we do |
|---|---|
| Depth wrong on glass, mirrors, dark corners | Erode masks, use medians, hand-fix the JSON |
| Scale off (no EXIF, unusual camera height) | Clamp scales, cross-check with door/ceiling height, hand-fix |
| Object in photo we have no model for | Detector is prompted only with our labels, so it is skipped |
| Room numbers drift from PR #4 (furniture moved, room resized) | `validate_scene.py` checks positions against `size_m` and `surfaces`; update `model_library.json` with any room change |
| Occluded objects (half behind a sofa) | Position from visible part only; accept, or hand-fix |
| ML models too slow / won't install | Steps 2/4/6 are swappable; the hand-made JSON always works |
