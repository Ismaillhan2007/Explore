# Living room (TV)

Open `Assets/_Project/Scenes/LivingRoomTV.unity` in Unity **6000.6.7f1** and press Play. Built the same way as [room 1](RENDERED_ROOM.md) and the [sofa living room](LIVING_ROOM_SOFA.md): original procedural geometry in Blender, lighting baked into two textures, and an editor script that generates the Unity scene.

Reference: `pipeline/photos/living_room_tv.jpg` (kept local, not in the repo). Step 3 of the photo pipeline put the camera about 1.1–1.2 m high and the TV wall about 3.4 m away; a typical 65" TV suggests a ceiling of about 3 m. The room is modelled at **4.6 × 5.0 × 3.0 m** with coffered beams down to 2.75 m; everything outside the photo is inferred.

## What is in it
- TV wall: vertical light-oak slats behind a 65" TV, a low oak cabinet with a soundbar.
- To its left: a recessed shelf niche with small decor, a brass wall sconce, a window with a roman blind.
- Coffered white ceiling with four recessed downlights (baked), ivory carpet.
- Grey swivel armchair turned toward the room, a whitewashed accent chair, a small brass side table with a candle, a tiered square coffee table with two books, a lower table on the left with a vase of autumn branches, a dark framed print on the right wall.

**Pickables (3):**

| Object | Prefab | Where |
|---|---|---|
| Book | `book.prefab` | tiered coffee table, top 0.42 m |
| Mug | `mug.prefab` (fitted to 10 cm) | brass side table, top 0.55 m |
| Table lamp | `lamp.prefab` (0.57 m) | left end of the TV cabinet, top 0.55 m (visible from the start view) |

Everything else is static, with box/cylinder colliders. The player starts at the front of the room facing the TV wall.

## Rebuilding

From the repository root:

```sh
ROOM_PREVIEW=1 /Applications/Blender.app/Contents/MacOS/Blender -b -t 8 -P tools/room/build_living_room_tv.py   # quick layout render only
/Applications/Blender.app/Contents/MacOS/Blender -b -t 8 -P tools/room/build_living_room_tv.py                   # full bake + export
/Applications/Unity/Hub/Editor/6000.6.7f1/Unity.app/Contents/MacOS/Unity -batchmode -quit -projectPath "$PWD" \
  -executeMethod RoomVR.EditorTools.BuildLivingRoomTV.Run -logFile /tmp/living-room-tv.log
```

Or run **RoomVR → Build Living Room (TV)** in the editor after the Blender export. It replaces only `LivingRoomTV.unity` and its generated materials and appends the scene to Build Settings.

If you move a table or the cabinet in `build_living_room_tv.py`, update the surface constants in `BuildLivingRoomTV.cs` and `LivingRoomTVTests.cs` and re-bake.

## Renders
- `docs/living-room-tv-blender.png`: Blender render from the photo's viewpoint.
- `docs/living-room-tv-baked-blender.png`: the baked textures before Unity import.
- `docs/living-room-tv-unity.png`: captured from the Unity scene, with the pickables.

## Limits
- Not tested on the Quest headset.
- Simplified look: procedural materials, the TV is a black panel, shelf decor is generic boxes and vases, the print is abstract.
- Baked surfaces do not get the pickables' moving shadows; moving furniture needs a re-bake.
- Room size is inferred from one photo without lens data.
