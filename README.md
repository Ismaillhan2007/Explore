# Explore — Room Walkthrough VR

Upload a photo of a room, then walk around a VR version of it and pick up objects. Hackathon project (Alkek Immersion Studio, Texas State). Two prebuilt scenes, optional wall-color change.

Docs: [PLAN.md](PLAN.md) (design, timeline, success criteria) · [TEAM.md](TEAM.md) (roles, ownership, scene JSON contract) · [CLAUDE.md](CLAUDE.md) (rules the AI reviewer enforces; also good team rules)

## Get started (about 15 minutes)
Everyone must use **exactly Unity 6000.6.7f1**. A different version rewrites scene files and causes conflicts.

1. Install [Unity Hub](https://unity.com/download) and the editor **6000.6.7f1** (Hub → Installs → Install Editor → Archive). Add the modules **Android Build Support**, **OpenJDK** and **Android SDK & NDK Tools** (needed for Quest builds).
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
  Editor/            setup and build scripts
  Settings/          URP asset
tools/setup-git.sh   per-clone git setup
.github/workflows/   CI (conflict check; Unity tests off until license secrets are added)
TEAM.md PLAN.md      roles/contract, design/timeline
```

## Try it without a headset
Open `Assets/_Project/Scenes/TestRoom.unity` and press Play. The **XR Device Simulator** (keyboard and mouse) lets you walk, teleport and grab the cubes. No headset or extra install is needed. Meta XR Simulator (a Quest runtime for Apple silicon Macs) is optional and not installed yet.

## Quest build
Menu **RoomVR > Build Quest APK** (or `Unity -batchmode -buildTarget Android -executeMethod RoomVR.EditorTools.BuildQuest.Build`) writes `Builds/RoomVR.apk`. Install on a headset in Developer Mode with `adb install -r Builds/RoomVR.apk` (adb is in the Unity Android SDK `platform-tools`).
Settings (IL2CPP, ARM64, Vulkan, OpenXR + Meta Quest feature, Touch controller profiles) are applied by `Assets/_Project/Editor/ConfigureQuest.cs`. The APK builds, but on-device behavior is untested because no headset is in Developer Mode yet.

## Editor tools (`Assets/_Project/Editor`)
`ImportXRSamples` (XRI sample assets), `BuildTestScene` (rebuilds `TestRoom` and the URP asset), `ConfigureQuest` (Android/OpenXR settings), `BuildQuest` (APK build). Run via `Unity -batchmode -executeMethod ...`. Do not re-run `BuildTestScene` once `TestRoom` has hand edits; it overwrites the scene.

## Status
Done: project, packages, `TestRoom` scene, Quest settings, APK build, tests, git/LFS/CI setup, docs.
Blocked: headset Developer Mode (Quest 3S is the studio's, paired to other accounts).
Next: scene JSON format, loader, room shell and first pickable models, photo algorithm. See [TEAM.md](TEAM.md) for who does what.

## Photo-inspired rendered room

Open `Assets/_Project/Scenes/RenderedRoom.unity` for the furnished room with the existing pickable mug on the coffee table. It is the first enabled build scene. Blender source, rebuild commands, rendering limits and verification are in [docs/RENDERED_ROOM.md](docs/RENDERED_ROOM.md).
