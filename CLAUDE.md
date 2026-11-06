# RoomVR — Claude guide

Unity 6000.6.7f1, URP, XR Interaction Toolkit 3.x, OpenXR. VR app: walk through a room built from a photo and pick up objects. Two prebuilt scenes.

- **Never add `Co-Authored-By: Claude ...` (or any AI assistant) trailer to commit messages.** No AI-attribution trailers, footers, or sign-offs of any kind.

## Layout
- `Assets/_Project/Scenes` — one scene per room. Each scene has ONE owner at a time; do not edit a scene someone else owns.
- `Assets/_Project/Prefabs/Pickables` — every pickable object is a prefab here.
- `Assets/_Project/Tests` — EditMode tests that validate scenes and prefabs.

## Rules (flag violations in review)
- Pickable prefabs must have a Collider, a Rigidbody and an XRGrabInteractable.
- Walls are a separate mesh with their own material so the color can change.
- Do not hand-edit `.unity`, `.prefab`, `.meta` YAML or resolve conflicts in them by script; ask a human.
- Never commit `Library/`, `Temp/`, `Logs/`, `UserSettings/`, builds, license files or secrets.
- Big binaries (models, textures, audio, `.ply`) go through Git LFS.
- Keep `main` buildable and tests green; small PRs; a human clicks merge.

## Review checklist
1. Missing script / missing reference introduced?
2. Scene or prefab changed by someone who doesn't own it?
3. Scale/position of objects absurd (outside ±100 m, zero scale)?
4. New asset not covered by LFS rules?
