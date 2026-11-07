"""Data passed between pipeline steps. See pipeline/README.md, section 2.

Arrays are typed as `Any` so this module imports with the standard library only;
at runtime they are numpy arrays.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Vec3 = tuple[float, float, float]


@dataclass
class Camera:
    """Pinhole intrinsics in pixels, for the (possibly downscaled) working image."""
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int


@dataclass
class Plane:
    """Plane n·p + d = 0, n is a unit normal."""
    normal: Vec3
    d: float


@dataclass
class Room:
    floor: Plane
    walls: list[Plane]
    scale: float             # relative depth units -> metres
    wall_color: str          # "#rrggbb"
    shell: str               # room shell prefab name, e.g. "RoomShell_A"
    cam_to_world: Any = None  # 4x4 matrix, camera space (metres) -> Unity world space


@dataclass
class Detection:
    label: str
    score: float
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 in pixels
    mask: Any                        # bool[H, W]


@dataclass
class Placement:
    label: str
    position: Vec3          # world space, metres; y = resting surface height
    rotation_y: float       # degrees
    size: Vec3              # measured width, height, depth in metres
    detection: Detection | None = None


@dataclass
class SceneObject:
    label: str
    model: str
    position: Vec3
    rotation_y: float
    scale: float


@dataclass
class Scene:
    room: str
    wall_color: str
    objects: list[SceneObject] = field(default_factory=list)
    version: int = 1
