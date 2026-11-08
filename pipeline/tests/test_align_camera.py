"""Unit tests for the photo-camera solver and table-relative placement (no ML models).

    cd pipeline && .venv/bin/python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.align_camera import camera_from, solve  # noqa: E402
from steps.datatypes import Detection  # noqa: E402
from steps.evaluate import project  # noqa: E402
from steps.step5_place import place_objects  # noqa: E402

W, H = 600, 800
TRUE = [0.6, 1.15, -1.8, -15.0, 4.0, 62.0]          # x, y, z, yaw, pitch down, vfov
POINTS = [[x, y, 2.4] for x in (-1.0, 0.0, 1.0) for y in (0.6, 1.4, 2.2)] + [[-0.5, 0.42, 0.9], [0.8, 0.55, 1.5]]
LIB = {"models": {"mug": {"label": "mug", "kind": "pickable", "status": "available", "height_m": 0.10,
                          "footprint_m": [0.12, 0.09], "scale_from": "height"}}}


class Solver(unittest.TestCase):
    def test_recovers_a_known_camera(self):
        cam = camera_from(TRUE)
        pixels = [project(p, cam, W, H)[:2] for p in POINTS]
        params, rms, per = solve(POINTS, pixels, W, H, [0.0, 1.0, -1.0, 0.0, 0.0, 50.0])
        self.assertLess(rms, 0.05)
        for got, want, tol in zip(params, TRUE, [0.01, 0.01, 0.01, 0.05, 0.05, 0.05]):
            self.assertAlmostEqual(got, want, delta=tol)

    def test_noisy_landmarks_give_a_close_camera(self):
        cam = camera_from(TRUE); rng = np.random.default_rng(3)
        pixels = [np.array(project(p, cam, W, H)[:2]) + rng.normal(0, 2, 2) for p in POINTS]
        params, rms, _ = solve(POINTS, pixels, W, H, [0.0, 1.0, -1.0, 0.0, 0.0, 50.0])
        self.assertLess(rms, 4)
        # 2 px of marking noise moves the camera ~10 cm when most landmarks sit on one wall
        self.assertLess(math.dist(params[:3], TRUE[:3]), 0.2)

    def test_height_prior_pulls_the_camera(self):
        cam = camera_from(TRUE)
        pixels = [project(p, cam, W, H)[:2] for p in POINTS[:3]]         # too few points to pin the camera down
        params, _, _ = solve(POINTS[:3], pixels, W, H, [0.0, 2.0, -1.0, 0.0, 0.0, 50.0], priors={"camera_height_m": [1.15, 0.05]})
        self.assertLess(abs(params[1] - 1.15), 0.06)


class RelativeToTable(unittest.TestCase):
    """The photo's table is 0.5 m away from the model's table; the mug must keep its offset from the table."""

    def test_offset_is_applied_to_the_model_table(self):
        cam = camera_from(TRUE)
        photo_table = (0.5, 0.42, 1.2)                     # where the table really is in the photo
        mug = (0.62, 0.47, 1.10)                           # mug centre in the photo: 12 cm right, 10 cm in front of the table centre
        tu, tv, _ = project(photo_table, cam, W, H)
        corners = [project((mug[0] + dx, mug[1] + dy, mug[2]), cam, W, H) for dx in (-.05, .05) for dy in (-.05, .05)]
        box = (min(c[0] for c in corners), min(c[1] for c in corners), max(c[0] for c in corners), max(c[1] for c in corners))
        room = {"surfaces": {"coffee_table": {"shape": "circle", "center": [0.0, 1.0], "radius": 0.45, "top_y": 0.42}},
                "photo": {"camera": cam, "image_size": [W, H], "surface_pixels": {"coffee_table": [tu, tv]}}}
        [p] = place_objects([Detection("mug", 0.9, box, np.zeros((1, 1), bool))], None, room, LIB, (W, H), real_photo=True)
        self.assertEqual(p.surface, "coffee_table")
        self.assertAlmostEqual(p.position[1], 0.42)
        self.assertAlmostEqual(p.position[0], 0.0 + 0.12, delta=0.01)   # model table centre + photo offset
        self.assertAlmostEqual(p.position[2], 1.0 - 0.10, delta=0.01)

    def test_object_far_from_every_table_is_not_placed(self):
        cam = camera_from(TRUE)
        tu, tv, _ = project((0.5, 0.42, 1.2), cam, W, H)
        room = {"surfaces": {"coffee_table": {"shape": "circle", "center": [0.0, 1.0], "radius": 0.45, "top_y": 0.42}},
                "photo": {"camera": cam, "image_size": [W, H], "surface_pixels": {"coffee_table": [tu, tv]}}}
        far = project((-1.5, 0.47, 2.0), cam, W, H)
        box = (far[0] - 5, far[1] - 5, far[0] + 5, far[1] + 5)
        self.assertEqual(place_objects([Detection("mug", 0.9, box, np.zeros((1, 1), bool))], None, room, LIB, (W, H), real_photo=True), [])


if __name__ == "__main__":
    unittest.main()
