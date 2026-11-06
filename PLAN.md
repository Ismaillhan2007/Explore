# Room Walkthrough VR — Hackathon Plan

Event: 72-hour hackathon hosted by the Alkek Immersion Studio, Texas State, November (dates, theme, hardware and judging rules still to confirm; see "Open questions").

## Current state (updated Nov 6, 2026)
- **Done:** Unity 6000.6.7f1 project, URP, XR Interaction Toolkit 3.7, OpenXR; `TestRoom` scene (XR rig, teleport floor, table, 3 grabbable cubes, XR Device Simulator); Android/Quest settings (IL2CPP, ARM64, Vulkan, OpenXR + Meta Quest features); a test APK builds; 4 EditMode tests pass; Git LFS and Unity merge setup; CI conflict check.
- **Blocked:** no headset is reachable. The studio's Quest 3S is visible over USB but not in Developer Mode (it is paired to other accounts). Until fixed, develop with the XR Device Simulator in the Editor.
- **Not started:** room shells, pickable model library, scene JSON loader, photo algorithm, upload page, wall recolor, UI.
- **Unconfirmed:** event dates, theme, judging rules, which hardware is provided (see open questions).

## 1. Concept
Upload a photo of a room, then walk around a VR version of it and pick up and interact with objects. Stretch goal: change the wall color.
Scope: 2 photos, 2 prebuilt VR scenes with pickable objects. Scenes are prerendered, so nothing heavy runs live in front of judges.

## 2. Architecture
```
[Photo] -> [Offline pipeline] -> [Unity scene package] -> [Unity VR app]
            (run in advance)     (room + object prefabs)    (walk, grab, recolor)
```
- Room = static scenery (mesh, or splat plus a simple collision mesh). Walls are a separate mesh so they can be recolored.
- Each pickable object = its own prefab: collider + Rigidbody + XR Grab Interactable.
- Scene selector: Scene A / Scene B.
- Optional upload page (Flask/FastAPI): accepts a photo, shows "processing", then loads the prebuilt scene. Be honest in the pitch about which steps were run in advance.
- If time allows (it may, over 72 hours): make one photo go through the pipeline semi-automatically as a live demo, keeping the two prebuilt scenes as the safe fallback.

## 3. Technologies
| Layer | Choice |
|---|---|
| Engine | Unity 6, URP, XR Interaction Toolkit, OpenXR |
| Headset | Studio Meta Quest 3S (seen over USB, Developer Mode not yet enabled); XR Device Simulator meanwhile |
| Locomotion | Teleport + snap-turn (smooth movement causes motion sickness) |
| Photo to 3D room | World Labs Marble or similar; fallback: Depth Anything V2 plus hand-built floor and wall planes |
| Object extraction | SAM 2 for cutouts, TripoSR / Hunyuan3D / Meshy for image-to-3D |
| Mesh cleanup | Blender |
| Splats (optional) | UnityGaussianSplatting (open source) |
| Upload page | Flask or FastAPI |
| Repo | Git + Git LFS, Unity .gitignore |
| CI | GitHub Actions + GameCI |
| AI review | Claude Code GitHub Action, `CLAUDE.md`, pre-push hook |
Verify tool availability, licenses and pricing at the start; this list is from general knowledge.

## 4. Roles
Three roles: **A** XR/Unity engineer (critical path), **B** 3D pipeline and photo algorithm, **C** integration, UI, demo and repo. Responsibilities, folder ownership and the B-to-A scene JSON contract are in [TEAM.md](TEAM.md).

## 5. Repo and merge-conflict setup (first hour)
- Force Text serialization, Visible Meta Files.
- UnityYAMLMerge as the merge driver for .unity/.prefab/.asset/.mat.
- Git LFS for models, textures, audio.
- One owner per scene at a time; everyone else works in prefabs and prefab variants.
- Short-lived branches, small PRs, `main` always playable, merge every 1-2 hours.
- Never let an agent auto-resolve .unity/.prefab conflicts; a person reviews them.

## 6. CI and agent guardrails
- GitHub Actions + GameCI: compile/build, EditMode and PlayMode tests, merge-into-main conflict check.
- Branch protection: PR cannot merge unless checks pass; a human clicks merge.
- Tests worth writing:
  - Every pickable prefab has collider, Rigidbody, XR Grab Interactable.
  - Each scene loads with no missing scripts or references.
  - Scene switching works both ways.
  - Wall-color change affects only the wall material.
  - Scene validator: no absurd scales or positions.
- Claude Code PR review using `CLAUDE.md` (architecture and rules); optional hourly job that tests `main` and posts failures to chat.
- Start with compile and tests only; add a full Quest build in CI only if time allows (license secret and XR build setup take effort).

## 7. Timeline (72 hours)
| Phase | Goal |
|---|---|
| Day 1, hours 0-4 | Confirm hardware and rules. Repo, CI, blank scene running on the headset, grab a cube. |
| Day 1, hours 4-24 | Scene 1 end to end: photo, room, 2-3 pickable objects, working in VR. |
| Day 2 | Scene 2 with the same process. Scene switcher. Wall-color change. Upload page. |
| Day 3, morning | Polish: audio, haptics, lighting, performance pass on the headset. |
| Day 3, last 6-8 hours | Feature freeze. Backup video of each scene, rehearsal, slides, submission. |

## 8. Success criteria
**Must have (the demo is a pass):**
- Two scenes, each recognizably the photographed room.
- Walk (teleport) around both and pick up, move and drop at least 3 objects per scene with believable physics.
- Runs on the event headset without crashes or nausea-inducing frame drops (target stable 72 fps on Quest, or the studio hardware's native rate).
- Scene switching works.
- A 2-3 minute demo that works start to finish and a recorded backup video.

**Should have:**
- Upload page that loads the matching scene.
- Wall-color change with at least 5 colors.
- Sound and haptic feedback when grabbing.

**Nice to have:**
- A live photo, run through the pipeline at the event.
- Throwing objects, object highlight on hover, more than 5 pickable objects per scene.

**Process criteria:**
- `main` builds and passes tests at every handoff.
- No lost work due to merge conflicts.
- Feature freeze held at the planned time.

## 9. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Generated objects have wrong scale/orientation | Budget manual fixes per object; keep a scale-reference cube in each scene |
| Poor performance on the headset | Test on-device from day 1; cut polygons before cutting features |
| AI image-to-3D tools fail or are slow | Fallback to depth plus hand-built room and simple primitive/asset-store objects |
| Demo failure | Backup video, mirrored headset view on a monitor, tested USB/Wi-Fi |
| Merge conflict in scene files | Scene ownership, prefabs, UnityYAMLMerge |
| Scope creep | Stretch goals only after both scenes work |

## 10. Pitch outline
1. Problem: rooms are hard to preview, remember and share in 3D.
2. Demo: photo, then walk through, then pick up objects, then change the wall color.
3. How it works: the pipeline diagram, with an honest note on what was prebuilt.
4. What's next: automatic generation, more rooms, furnishing and redecorating use cases.

## 11. Open questions for organizers
- Exact dates, theme or tracks, prizes, and judging criteria?
- Which headsets and PCs are provided; can we test beforehand?
- Can we bring our own headset and laptops?
- Are pre-built assets and pipelines allowed, or only work started on site?
- Is the submission a live demo, video, or Devpost?
