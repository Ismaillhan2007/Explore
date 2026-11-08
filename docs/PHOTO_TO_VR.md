# Photo to VR: running the algorithm from Unity (demo guide)

**RoomVR → Photo to VR** in the Unity Editor: pick an image of one of our rooms, run the photo pipeline, see what it found, then press Play and walk around the result. You can pick up everything it placed.

## What happens
1. **Run algorithm** starts `pipeline/run_pipeline.py` with `pipeline/.venv` (about 20 s): camera → depth → room shape → find the mug, book and lamp → place each on its table → prefab + scale → `pipeline/scenes/generated/scene_ui_<Room>.json`. The window shows step 4's detection image and the placed positions.
2. **Open room & Play** opens that room's scene and enters Play mode. `PickableSceneLoader` (in `Assets/_Project/Scripts/Pipeline`) replaces the room's own pickables with the ones in the JSON: the same prefabs, fitted to their real height × scale and resting on their surface. Walk around with the XR rig: Quest over Link or Air Link, or the XR Device Simulator (keyboard/mouse).
3. Leaving Play mode forgets the generated result, so the normal Play button shows the room as built again. **Play room as built** does the same from the window.

Nothing is saved into the scenes. The generated JSON is a separate file.

## Before the event (once)
```bash
cd pipeline
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_pipeline.py ../docs/demo/sofa-moved-unity.png --name warmup --room LivingRoomSofa --render   # downloads ~1.6 GB of models once
```
Then keep **Offline** ticked in the window: no internet needed, and no surprises from the venue Wi-Fi.

## Demo script for judges (about 2 minutes)
1. **Show the input.** Open `docs/demo/sofa-moved-unity.png`: the sofa room with the mug moved onto the pouf and the book to the front of the coffee table. Say: "the algorithm has never seen this layout".
2. **Run it.** **Quick picks → (sofa) render**, then choose that image with **Browse…** (or the moved TV room: `docs/demo/tv-moved-unity.png`). Keep **Image is a Unity render of this room** ticked. Click **Run algorithm**. The progress bar walks through the 7 steps; when it's done, the window shows the green boxes around the mug, book and lamp and their positions.
3. **Walk into it.** Click **Open room & Play**. In VR the mug is on the pouf and the book at the front of the coffee table, where the image showed them. Pick them up.
4. **Real photo (optional).** **(TV) photo** runs the real living-room photo. The book lands on the coffee table, but placement is approximate (see limits), so show it second.

**Backup if anything fails live:** **Play room as built** (the hand-made rooms always work), plus the pre-made images in `pipeline/results/demo_*.png`.

## Headset build without the laptop
**Copy to StreamingAssets (headset build)** copies the last result to `Assets/StreamingAssets/pipeline/<Room>.json`. In a build, load it with:
```csharp
StartCoroutine(PickableSceneLoader.LoadFromStreamingAssets("LivingRoomSofa.json"));
```
For example from the in-VR scene selector (Role C) after the room scene loads. The prefabs come from `Assets/_Project/Resources/PickableRegistry.asset`. Rebuild it with **RoomVR → Update Pickable Registry** after adding a pickable to `pipeline/model_library.json`.

## What to say honestly
- **It places pickables in rooms we built;** it doesn't build a room from a new photo. The three rooms were modelled in Blender, using the pipeline's measurements for the two living rooms.
- **On renders** of our rooms it's exact: every pickable within 1–6 cm, at the right table height. **On real photos** it's approximate: on the right table, roughly the right spot, and there's no answer key to measure it.
- **The heavy AI part runs on the laptop** (Python, ~1.6 GB of models). The Quest only shows the result.

## Files
| File | What |
|---|---|
| `Assets/_Project/Editor/PhotoToVRWindow.cs` | the window; also `Smoke()`, a batch test of the same pipeline run |
| `Assets/_Project/Scripts/Pipeline/PickableSceneLoader.cs` | runtime loader (Play mode and builds) |
| `Assets/_Project/Scripts/Pipeline/PickableRegistry.cs`, `Resources/PickableRegistry.asset` | model name → prefab + real height |
| `Assets/_Project/Editor/PickableRegistryBuilder.cs` | builds the registry from `pipeline/model_library.json` |
| `pipeline/run_pipeline.py --render` | exact placement for a render of a room from its own camera, no answer key needed |
| `pipeline/scenes/demo/*.json`, `docs/demo/*.png` | the moved-object demo layouts and their renders |
