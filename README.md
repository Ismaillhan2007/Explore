# Explore — Room Walkthrough VR

Upload a photo of a room, then walk around a VR version of it and pick up objects. Hackathon project (Alkek Immersion Studio, Texas State). Two prebuilt scenes, optional wall-color change.

Docs: [PLAN.md](PLAN.md) (design, roles, timeline, success criteria) · [CLAUDE.md](CLAUDE.md) (rules the AI reviewer enforces; also good team rules)

## Get started (about 15 minutes)
Everyone must use **exactly Unity 6000.6.7f1**. A different version rewrites scene files and causes conflicts.

1. Install [Unity Hub](https://unity.com/download) and the editor **6000.6.7f1** (Hub → Installs → Install Editor → Archive). Add **Android Build Support** if we target Quest.
2. Install Git LFS: `brew install git-lfs` (macOS).
3. Clone the repo:
   ```bash
   git clone https://github.com/Ismaillhan2007/Explore.git
   cd Explore
   ```
4. Run once per clone (turns on LFS and Unity's smart merge for scenes and prefabs):
   ```bash
   tools/setup-git.sh
   ```
5. In Unity Hub: **Projects → Add → Add project from disk**, pick the cloned folder. The first open takes a few minutes.
6. Run the tests: **Window → General → Test Runner → EditMode → Run All**. All should pass.

## Working rules
- **Branch per task**, small PRs, merge to `main` every 1–2 hours. `main` must always open and pass tests. Don't push broken work to `main`.
- **One owner per scene at a time.** Say in chat before you edit a scene. Build everything else as prefabs.
- **Never resolve conflicts in `.unity`, `.prefab` or `.meta` files by hand.** Ask the scene owner, or take one side and redo your change.
- Pickable objects live in `Assets/_Project/Prefabs/Pickables` and need a Collider, a Rigidbody and an XRGrabInteractable (the tests check this).
- Models, textures, audio and `.ply` files go through Git LFS automatically; make sure step 2 and 4 were done first.
- Keep `.meta` files with their assets. Never commit `Library/`, `Temp/`, builds or secrets.

## Project layout
```
Assets/_Project/
  Scenes/            one scene per room
  Prefabs/Pickables/ grabbable objects
  Scripts/  Materials/  Models/
  Tests/EditMode/    scene and prefab validation tests
tools/setup-git.sh   per-clone git setup
.github/workflows/   CI (conflict check; Unity tests off until license secrets are added)
```

## Status
Done: Unity project, URP + XR Interaction Toolkit + OpenXR packages, tests, CI skeleton.
Not yet: VR rig and first scene, OpenXR/Quest settings, scenes, objects, upload page.
