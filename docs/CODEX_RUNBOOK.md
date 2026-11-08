# Runbook for a coding agent (Codex): run, test and show the photo-to-VR demo

Give this file to Codex with the prompt at the bottom. It tells the agent how to set up the photo pipeline, run every test, produce the demo images, and then open Unity with the algorithm window and the rooms ready for a person to press Play.

Machine assumed: macOS, Apple silicon, repo at `~/Desktop/Explore`, Unity **6000.6.7f1** at `/Applications/Unity/Hub/Editor/6000.6.7f1`, Python 3.12.

## Rules for the agent
- **Do not edit, regenerate or commit** `.unity`, `.prefab` or `.meta` files. Never run `BuildRenderedRoom`, `BuildLivingRoomSofa`, `BuildLivingRoomTV` or `BuildTestScene`: they overwrite the scenes and need a Blender export first.
- **Do not commit or push anything.** All output goes to `pipeline/debug/` and `pipeline/scenes/generated/`, which are scratch.
- Unity batch commands fail if the project is already open in the Unity Editor. Close the editor first (or skip to step 6).
- Stop and report on the first failing step. Quote the last 30 lines of the log.

```bash
cd ~/Desktop/Explore
UNITY=/Applications/Unity/Hub/Editor/6000.6.7f1/Unity.app/Contents/MacOS/Unity
```

## 1. Check the repo
```bash
git checkout main && git pull --ff-only
git lfs pull
git log --oneline -1   # expect "Merge pull request #17 ..." or later
```

## 2. Python environment (once, about 5 minutes)
```bash
cd pipeline
[ -d .venv ] || python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. Python tests (no models needed, a few seconds)
```bash
.venv/bin/python -m unittest discover -s tests -v      # expect 40 tests, OK
.venv/bin/python validate_scene.py scenes/*.json scenes/demo/*.json   # expect no errors
```

## 4. Run the algorithm (first run downloads about 1.6 GB of models)
Each run prints `[1 camera]` … `[7 export] <path>` and writes pictures to `pipeline/debug/<name>/`.

```bash
# a) Render of the sofa room with objects moved; the algorithm has never seen this layout
.venv/bin/python run_pipeline.py ../docs/demo/sofa-moved-unity.png --name sofa_moved --room LivingRoomSofa --render

# b) The same for the TV room
.venv/bin/python run_pipeline.py ../docs/demo/tv-moved-unity.png --name tv_moved --room LivingRoomTV --render

# c) Graded runs on the three built rooms (answer keys in scenes/); expect 3/3 found, a few cm off
.venv/bin/python run_pipeline.py ../docs/living-room-sofa-unity.png --name full_sofa  --answers scenes/scene_living_room_sofa.json
.venv/bin/python run_pipeline.py ../docs/living-room-tv-unity.png  --name full_tv    --answers scenes/scene_living_room_tv.json
.venv/bin/python run_pipeline.py ../docs/room-unity.png            --name full_room1 --answers scenes/scene_room_a.json

# d) Real photo (only if pipeline/photos/living_room_tv.jpg exists; it is kept out of git)
[ -f photos/living_room_tv.jpg ] && .venv/bin/python run_pipeline.py photos/living_room_tv.jpg --name tv_photo --room LivingRoomTV
cd ..
```

Pictures to check in `pipeline/debug/<name>/`:
- `depth.png`: depth map, bright = near.
- `room_overlay.png`: floor green, walls blue and pink.
- `detections.png`: boxes with label and score around the mug, book and lamp.
- `detect_report.json`: which objects were kept and which were rejected, and why.

## 5. Unity in batch mode (editor closed)
```bash
# a) EditMode tests: scenes, prefabs, loader
"$UNITY" -batchmode -projectPath "$PWD" -runTests -testPlatform EditMode \
  -testResults "$PWD/pipeline/debug/editmode-results.xml" -logFile "$PWD/pipeline/debug/editmode.log"

# b) PlayMode tests: grabbing in each room, loader at runtime
"$UNITY" -batchmode -projectPath "$PWD" -runTests -testPlatform PlayMode \
  -testResults "$PWD/pipeline/debug/playmode-results.xml" -logFile "$PWD/pipeline/debug/playmode.log"

# c) Same flow as the "Run algorithm" button, without the window: runs Python, then renders the room with the result
"$UNITY" -batchmode -quit -projectPath "$PWD" -executeMethod RoomVR.EditorTools.PhotoToVRWindow.Smoke \
  -photo docs/demo/tv-moved-unity.png -room LivingRoomTV -render -out pipeline/debug/smoke_tv.png \
  -logFile "$PWD/pipeline/debug/smoke.log"
grep -E "PHOTO_TO_VR_SMOKE" pipeline/debug/smoke.log   # expect "pipeline ok" and "COMPLETE"

# d) Render each room in Unity with the pickables from a scene JSON (from steps 4a and 4b)
for n in sofa_moved tv_moved; do
  "$UNITY" -batchmode -quit -projectPath "$PWD" -executeMethod RoomVR.EditorTools.PipelineScenePreview.Run \
    -sceneJson "pipeline/scenes/generated/scene_$n.json" -out "pipeline/debug/$n/unity_preview.png" \
    -logFile "$PWD/pipeline/debug/preview_$n.log"
done
```
Report the pass and fail counts from both XML files (`grep -o 'result="[A-Za-z]*" total="[0-9]*" passed="[0-9]*" failed="[0-9]*"'`).

## 6. Open Unity for the live demo (a person takes over here)
```bash
"$UNITY" -projectPath "$PWD" -executeMethod RoomVR.EditorTools.PhotoToVRWindow.Open &
```
This opens the project with the **Photo to VR** window. Then the presenter:
1. Ticks **Offline** and leaves **Image is a Unity render of this room** ticked.
2. Clicks the sofa room's **render** button under **Quick picks** (this selects the room), then **Browse…** and picks `docs/demo/sofa-moved-unity.png` (or the TV room and `tv-moved-unity.png`). The **photo** buttons run the real photos.
3. Clicks **Run algorithm** (about 20 s). The window shows the detection image and the positions.
4. Clicks **Open room & Play (generated result)**. In VR (Quest over Link) or with the XR Device Simulator (keyboard and mouse), walks to the table and picks up the mug, book and lamp.
5. To show the rooms as built: **Play room as built**, or open `Assets/_Project/Scenes/RenderedRoom.unity`, `LivingRoomSofa.unity` or `LivingRoomTV.unity` and press Play.
6. Backup if anything fails: **Play room as built**, plus the images in `pipeline/results/`.

## 7. Final report from the agent
- Python tests: X/40 passed.
- Unity EditMode and PlayMode tests: passed/total for each.
- For each run in step 4: the objects found, the objects rejected, and the `scene_*.json` path.
- The list of PNGs made in steps 4 and 5, so a person can open them.
- Anything that failed, with its log lines.

---

## Prompt to paste into Codex
> Follow `docs/CODEX_RUNBOOK.md` in this repo step by step, from step 1 through step 5, then do step 6 to open Unity with the Photo to VR window. Respect the "Rules for the agent" section: don't edit scenes, prefabs or meta files, don't run the Build* room scripts, and don't commit or push. Stop at the first failure and show me the log. Finish with the report in step 7.
