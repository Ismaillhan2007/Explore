# Living room (sofa)

Open `Assets/_Project/Scenes/LivingRoomSofa.unity` in Unity **6000.6.7f1** and press Play. It is built the same way as [room 1](RENDERED_ROOM.md): original procedural geometry in Blender, lighting baked into two textures, and an editor script that generates the Unity scene.

Reference: `pipeline/photos/living_room_sofa.jpg` (kept local, not in the repo). Step 3 of the photo pipeline measured a ~2.7 m ceiling, a camera about 1 m high and the back wall about 3.1 m away. The room is modelled at **4.2 × 4.8 × 2.7 m**; width and the space behind the camera are not visible in the photo and are inferred.

## What is in it
- Grey 3-seat sofa against the back wall with white, grey and charcoal pillows and a white throw; two framed posters above it.
- Window on the left wall with a gathered blue-grey curtain and a sheer, a small plant on a white stool, a brass floor lamp (static, its warm light is baked).
- Ribbed walnut drum coffee table with a tray and a succulent, hourglass walnut side table, knitted pouf, tall snake plant on the right, grey woven rug on pale oak.

**Pickables (3):**

| Object | Prefab | Where |
|---|---|---|
| Mug | `mug.prefab` (fitted to 10 cm) | coffee table, top 0.42 m |
| Book | `book.prefab` | coffee table, top 0.42 m |
| Table lamp | `lamp.prefab` (0.57 m) | side table, top 0.53 m |

Everything else is static, with box/cylinder colliders. The player starts by the doorway facing the sofa; the doorway is visually open but blocked, as in room 1.

## Rebuilding

From the repository root:

```sh
ROOM_PREVIEW=1 /Applications/Blender.app/Contents/MacOS/Blender -b -t 8 -P tools/room/build_living_room_sofa.py   # quick layout render only
/Applications/Blender.app/Contents/MacOS/Blender -b -t 8 -P tools/room/build_living_room_sofa.py                   # full bake + export
/Applications/Unity/Hub/Editor/6000.6.7f1/Unity.app/Contents/MacOS/Unity -batchmode -quit -projectPath "$PWD" \
  -executeMethod RoomVR.EditorTools.BuildLivingRoomSofa.Run -logFile /tmp/living-room-sofa.log
```

Or run **RoomVR → Build Living Room (Sofa)** in the editor after the Blender export. It replaces only `LivingRoomSofa.unity` and its generated materials and adds the scene to the end of Build Settings (room 1 stays first).

If you move a table in `build_living_room_sofa.py`, update the surface constants in `BuildLivingRoomSofa.cs` and `LivingRoomSofaTests.cs` and re-bake.

## Renders
- `docs/living-room-sofa-blender.png`: Blender render from the photo's viewpoint.
- `docs/living-room-sofa-baked-blender.png`: the baked textures before Unity import.
- `docs/living-room-sofa-unity.png`: captured from the Unity scene, with the pickables.

## Limits
- Not tested on the Quest headset.
- Simplified look: no fabric weave or wood grain beyond procedural noise, posters are abstract.
- Baked surfaces do not get the pickables' moving shadows; moving furniture needs a re-bake.
- Room size is inferred from one photo without lens data.
