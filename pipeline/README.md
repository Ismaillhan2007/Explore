# Photo → scene pipeline

Owner: **Role B** (see [TEAM.md](../TEAM.md)). Backup: Role C.

This folder turns **one photo of a room** into **one scene JSON file** that the Unity scene loader (Role A) reads to build a walkable, furnished VR room. It runs offline on a laptop, before the demo. Nothing here touches `.unity`, `.prefab` or `.meta` files.

```
photo.jpg ──► [1 camera] ──► [2 depth] ──► [3 room] ──► [4 detect + segment] ──► [5 place] ──► [6 match] ──► [7 export] ──► scene_room_x.json
                                              │                                                                  ▲
                                              └── floor plane, walls, scale, wall colour ────────────────────────┘
```

Status: **skeleton**. Every step below is a stub with its inputs, outputs and approach written down. `validate_scene.py` works today. The hand-made [`scenes/scene_room_a.json`](scenes/scene_room_a.json) lets Role A build the loader now, without waiting for the algorithm.

---

## 1. Why it is built this way

- **Retrieval, not generation.** We match each object in the photo to one of our own 10–15 clean prefabs (correct scale, pivot, collider, mass). Image-to-3D models are slow, give messy meshes and bad colliders, so they are only an optional extra for one or two hero objects.
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
**In:** photo. **Out:** `depth[H, W]` in *relative* units.

- Run **Depth Anything V2** (Small or Base; Hugging Face `depth-anything/Depth-Anything-V2-*-hf`). It gives relative depth (sometimes inverse depth/disparity, check the model card and invert if needed).
- Metric depth models (Depth Anything V2 Metric-Indoor, Depth Pro) are worth a try; if they work, step 3's scale fix becomes a sanity check instead of the main source of scale.
- Back-project every pixel to a 3D point in camera space:
  `X = (u − cx) · Z / fx`, `Y = (v − cy) · Z / fy`, `Z = depth(u, v)`.

### Step 3 — Room geometry (`steps/step3_room.py`)
**In:** point cloud, camera, photo. **Out:** `Room(floor_plane, walls, scale, wall_color, shell)`.

1. **Floor:** RANSAC plane fit on points from the bottom third of the image. Pick the plane whose normal is closest to camera "up" (−Y in camera space, because image rows grow downward). This defines world **up** and **y = 0**.
2. **Walls:** remove floor inliers, run RANSAC again for planes that are roughly perpendicular to the floor (|normal · up| < 0.2). Keep the 1–3 largest.
3. **Metric scale:** relative depth has the right shape but the wrong size. Fix it with one known measurement, in order of preference:
   - camera height above the floor ≈ **1.5 m** (phone held at chest height) → `scale = 1.5 / distance(camera, floor_plane)`;
   - detected door height ≈ 2.0 m, or ceiling height ≈ 2.5 m, as a cross-check.
   Multiply all points by `scale`. From here on everything is in metres.
4. **Wall colour:** median RGB of pixels that are wall inliers and not inside any object mask (step 4). Convert to `#rrggbb`.
5. **Room shell:** pick the `RoomShell_*` prefab whose floor size best fits the extent of floor + wall points. (Shells are built by hand in Unity; walls are a separate mesh and material so colour can change.)

### Step 4 — Detect and segment objects (`steps/step4_detect.py`)
**In:** photo, list of labels from `model_library.json`. **Out:** list of `Detection(label, score, box, mask)`.

- **Detect** with an open-vocabulary detector (**Grounding DINO** or **OWLv2**; YOLO-World if speed matters). Prompt it with *only the labels we have models for*, e.g. `"chair . mug . lamp . book . plant"`. Keep score ≥ 0.35, then per-label non-max suppression.
- **Segment** each box with **SAM 2** (box prompt) → a clean pixel mask. Erode the mask by 2–3 px so depth at the edges (which bleeds into the background) is not used.
- Drop tiny masks (< 0.2 % of the image) and anything not in our library.

### Step 5 — Place each object in 3D (`steps/step5_place.py`)
**In:** detections, point cloud, room. **Out:** list of `Placement(label, position, rotation_y, size)`.

- **Position:** 3D points inside the mask → take the median (robust to edge noise) → that is the object centre in camera space → transform to world (section 3).
- **Resting surface:** big objects (chair, table, sofa, lamp) snap to the floor (`y = 0`). Small objects (mug, book) snap to the top of the closest larger object below them, else the floor.
- **Size:** 3D extent of the mask points along world X/Z, height from the topmost point to the resting surface. Used in step 6 for scale.
- **Rotation (`rotationY`), first version:** align the object with the nearest wall (front facing away from it), or face the camera if no wall is close. **Better version** (if time): render each candidate prefab from 12 yaw angles (30° steps), compare to the masked crop with CLIP/DINOv2 embeddings, keep the best angle.

### Step 6 — Match each object to a prefab (`steps/step6_match.py`)
**In:** detections + placements, `model_library.json`. **Out:** a `model` name and `scale` per object.

- Candidates = library models with the same `label`.
- More than one candidate → embed the masked crop and each model's thumbnail with **CLIP** (`open_clip`, ViT-B/32 is enough), choose the highest cosine similarity.
- **Scale** = measured height / model's `height_m` from the library. **Clamp to 0.7–1.4.** A mug that comes out 3× too big is a measurement error, not a big mug. Outside that range, log a warning and use 1.0.
- **Optional hero object:** cut out the object with its SAM mask and run TripoSR / Hunyuan3D / Meshy, clean the mesh in Blender, make it a prefab, add it to the library. Done by hand, outside the automatic path.

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
- The player spawns where the camera was, so the VR view starts like the photo.

## 4. Output contract (the scene JSON)

Agreed between Role B and Role A in [TEAM.md](../TEAM.md). Example: [`scenes/scene_room_a.json`](scenes/scene_room_a.json).

```json
{
  "version": 1,
  "room": "RoomShell_A",
  "wallColor": "#d9c7a8",
  "objects": [
    { "label": "chair", "model": "chair_03", "position": [1.2, 0.0, 2.4], "rotationY": 210, "scale": 1.0 }
  ]
}
```

| Field | Meaning |
|---|---|
| `version` | Format version. The loader should refuse a version it does not know. *(New, proposed in this PR.)* |
| `room` | Name of a room shell prefab. |
| `wallColor` | `#rrggbb`, applied to the wall material. |
| `objects[].label` | What the detector saw (for debugging and UI). |
| `objects[].model` | Prefab name in `Assets/_Project/Prefabs/Pickables`, must be listed in `model_library.json`. |
| `objects[].position` | `[x, y, z]` metres, world space. `x, z` = centre of the object's footprint, `y` = height of the surface it rests on. The loader lifts the object so the bottom of its collider sits at `y`, so prefab pivots don't matter. |
| `objects[].rotationY` | Degrees around up. |
| `objects[].scale` | Uniform scale, 0.7–1.4. |

Unknown extra fields (for example `source`) must be ignored by the loader. Any other format change: tell Role A first.

## 5. Model library (`model_library.json`)

The single list of model names both sides use. For each model: `label`, `prefab`, `height_m` (real height at scale 1.0), `status` (`available` = prefab exists, `planned` = not built yet). When you add a prefab to `Prefabs/Pickables`, add or update its entry here in the same PR, with `height_m` measured from the prefab's collider at scale 1.

## 6. Running it

```bash
cd pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # heavy ML deps, only needed for steps 2, 4, 6
python run_pipeline.py photos/room_a.jpg --name room_a   # writes scenes/scene_room_a.json (stubs raise NotImplementedError for now)
python validate_scene.py scenes/scene_room_a.json         # stdlib only, works today
```

- Put input photos in `pipeline/photos/` (`.jpg`/`.png` go through Git LFS automatically).
- Debug images (depth maps, masks, overlays) go to `pipeline/debug/`, which is not committed.
- Model weights download to the Hugging Face cache, never into the repo.

## 7. Build order (what to do first)

1. ✅ Hand-made `scenes/scene_room_a.json` so Role A can build the loader. *(This PR.)*
2. Steps 1 + 2 → save a depth map image. Check it looks right on both demo photos.
3. Step 3 → floor plane, scale, wall colour. Print the camera height; it should be ~1.5 m.
4. Step 4 → overlay masks on the photo. Tune the label prompt and threshold.
5. Steps 5 + 6 + 7 → first automatic JSON. Compare to the hand-made one in the headset.
6. Only then: better rotation, hero object via image-to-3D, live photo demo.

## 8. Known risks

| Risk | What we do |
|---|---|
| Depth wrong on glass, mirrors, dark corners | Erode masks, use medians, hand-fix the JSON |
| Scale off (no EXIF, unusual camera height) | Clamp scales, cross-check with door/ceiling height, hand-fix |
| Object in photo we have no model for | Detector is prompted only with our labels, so it is skipped |
| Occluded objects (half behind a sofa) | Position from visible part only; accept, or hand-fix |
| ML models too slow / won't install | Steps 2/4/6 are swappable; the hand-made JSON always works |
