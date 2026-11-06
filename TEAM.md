# Team roles and responsibilities

Three people, three roles. Fill in the names, then stick to the ownership map so we don't collide in scene, prefab and settings files. Everyone pairs on a second area so nothing stalls if one person is blocked or asleep (72-hour event; plan sleep shifts).

| Role | Name | Backup |
|---|---|---|
| **A. XR / Unity engineer** | _fill in_ | B |
| **B. 3D pipeline and photo algorithm** | _fill in_ | C |
| **C. Integration, UI, demo and repo** | _fill in_ | A |

## Role A — XR / Unity engineer (critical path)
**Goal:** a stable, comfortable VR experience on the headset, and the code that turns pipeline output into a scene.

Responsibilities
- Own the Unity project settings, XR rig, locomotion (teleport + snap turn) and grab/physics feel.
- Own the final room scenes (`Assets/_Project/Scenes`). Only A edits a scene unless A says otherwise.
- Write the **scene loader**: reads the scene JSON (see "Contract" below), spawns the room shell and pickable prefabs, adds components.
- Own the headset: Developer Mode, installing builds, performance (target stable frame rate), logs, fixing on-device bugs.
- Own `Assets/_Project/Tests` and keep them green.

Owns: `Assets/_Project/Scenes`, `Scripts` (except `Scripts/UI`), `Tests`, `Editor`, `ProjectSettings`, `Packages`.

## Role B — 3D pipeline and photo algorithm
**Goal:** photo in, a believable furnished room out (as JSON plus prefabs).

Responsibilities
- Build the algorithm: detect and segment objects in the photo, estimate depth, match each object to a model, compute position/rotation/scale, write the scene JSON.
- Build the **library of pickable prefabs** (10–15 clean models: scale, pivot, collider, mass) and the room shells (walls as a separate mesh and material so wall color can change).
- Evaluate generative image-to-3D for one or two hero objects; keep retrieval from the library as the default.
- Test the pipeline on the two real photos early and tune by hand until they look right.

Owns: `Assets/_Project/Models`, `Assets/_Project/Prefabs`, `Assets/_Project/Materials`, `pipeline/` (Python, to be created), sample photos and generated JSON.

## Role C — Integration, UI, demo and repo
**Goal:** the project always runs, looks like a product, and the pitch works.

Responsibilities
- In-VR UI: scene selector, wall-color picker, instructions. Audio and haptic feedback on grab.
- The upload page (small Flask/FastAPI app) that accepts a photo and then loads the matching prebuilt scene.
- Repo health: PR review, merge-conflict help, CI, `README`/docs up to date, branch protection and collaborators.
- Demo: backup screen recording of each scene, mirrored headset view on a monitor, pitch, slides and submission.
- Chase organizers for rules, hardware and Developer Mode (see PLAN.md open questions).

Owns: `Assets/_Project/Scripts/UI`, `web/` (to be created), `.github`, docs (`README.md`, `PLAN.md`, `TEAM.md`), pitch assets.

## Contract between B and A (agree this first)
The pipeline writes one JSON file per scene; the loader reads it. Draft format:

```json
{
  "room": "RoomShell_A",
  "wallColor": "#d9c7a8",
  "objects": [
    { "label": "chair", "model": "chair_03", "position": [1.2, 0.0, 2.4], "rotationY": 210, "scale": 1.0 }
  ]
}
```
Metres, Unity axes (y up). Every `model` name must match a prefab in `Prefabs/Pickables`. Change the format only after telling the other person.

## Working agreements
- Short daily sync (10 min) plus a "what's blocking me" message whenever stuck.
- Branch per task, small PRs, someone else reviews, merge to `main` often. `main` must open and pass tests.
- Say in chat before touching a scene or a file you don't own.
- Feature freeze at the planned time (see PLAN.md). After it, only bug fixes and demo prep.
- Record decisions in `PLAN.md`, not only in chat.
