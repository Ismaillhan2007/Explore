"""Unit tests for steps 5 and 6 (geometry only, no ML models).

    cd pipeline && .venv/bin/python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.datatypes import Detection, Placement  # noqa: E402
from steps.evaluate import grade_scene, project  # noqa: E402
from steps.step5_place import clamp_onto, face_camera_yaw, inside, pixel_ray, place_objects, ray_at_height  # noqa: E402
from steps.step6_match import clamp_scale, expected_box, match_models  # noqa: E402

CAM = {"position": [0.5, 1.2, -2.0], "look_at": [0.0, 0.6, 1.0], "vfov_deg": 70}
W, H = 800, 1000
LIB = {"models": {
    "mug": {"label": "mug", "kind": "pickable", "status": "available", "height_m": 0.10, "footprint_m": [0.12, 0.09], "scale_from": "height"},
    "book": {"label": "book", "kind": "pickable", "status": "available", "height_m": 0.03, "footprint_m": [0.22, 0.15], "scale_from": "width"}}}
ROOM = {"camera": CAM, "surfaces": {
    "table": {"shape": "circle", "center": [0.0, 1.0], "radius": 0.45, "top_y": 0.42},
    "floor": {"shape": "box", "center": [0.0, 0.0], "size": [4.0, 5.0], "top_y": 0.0}}}


class Rays(unittest.TestCase):
    def test_ray_round_trips_with_projection(self):
        point = (0.1, 0.47, 0.9)
        u, v, _ = project(point, CAM, W, H)
        origin, d = pixel_ray(u, v, CAM, W, H)
        x, z, _ = ray_at_height(origin, d, point[1])
        self.assertAlmostEqual(x, point[0], places=4); self.assertAlmostEqual(z, point[2], places=4)

    def test_ray_upward_never_reaches_lower_plane(self):
        origin, d = pixel_ray(W / 2, 0, {"position": [0, 1, 0], "look_at": [0, 2, 1], "vfov_deg": 60}, W, H)
        self.assertIsNone(ray_at_height(origin, d, 0.0))


class Surfaces(unittest.TestCase):
    def test_inside_and_clamp(self):
        s = ROOM["surfaces"]["table"]
        self.assertTrue(inside(0.3, 1.0, s, 0)); self.assertFalse(inside(0.5, 1.0, s, 0)); self.assertTrue(inside(0.48, 1.0, s, 0.05))
        x, z = clamp_onto(0.5, 1.0, s, 0.06)
        self.assertAlmostEqual(math.hypot(x, z - 1.0), 0.39, places=6)
        self.assertEqual(clamp_onto(1.9, 0.0, {"shape": "box", "center": [0, 0], "size": [2, 2]}, 0.1), (0.9, 0.0))

    def test_face_camera(self):
        self.assertAlmostEqual(face_camera_yaw(0, 0, [0, 1, -2]), 180.0)
        self.assertAlmostEqual(face_camera_yaw(0, 0, [2, 1, 0]), 90.0)


class Place(unittest.TestCase):
    def box_for(self, centre, h=0.10, w=0.10):
        """Image box of an object of size w x h centred at `centre`, as seen by CAM."""
        corners = [project((centre[0] + dx, centre[1] + dy, centre[2]), CAM, W, H) for dx in (-w / 2, w / 2) for dy in (-h / 2, h / 2)]
        us, vs = [c[0] for c in corners], [c[1] for c in corners]
        return (min(us), min(vs), max(us), max(vs))

    def test_mug_lands_on_the_table_at_its_true_spot(self):
        d = Detection("mug", 0.9, self.box_for((0.15, 0.47, 0.9)), np.zeros((1, 1), bool), size={"base_m": 0.40})
        [p] = place_objects([d], None, ROOM, LIB, (W, H))
        self.assertEqual(p.surface, "table")
        self.assertAlmostEqual(p.position[1], 0.42)
        self.assertLess(math.hypot(p.position[0] - 0.15, p.position[2] - 0.9), 0.01)

    def test_base_height_decides_between_table_and_floor(self):
        # A box whose centre ray hits the floor plane in front of the table: with a floor-level base it goes on the floor.
        d = Detection("mug", 0.9, self.box_for((1.2, 0.05, 0.0)), np.zeros((1, 1), bool), size={"base_m": 0.02})
        [p] = place_objects([d], None, ROOM, LIB, (W, H))
        self.assertEqual(p.surface, "floor"); self.assertEqual(p.position[1], 0.0)

    def test_duplicates_merge(self):
        box = self.box_for((0.15, 0.47, 0.9))
        ds = [Detection("mug", 0.9, box, np.zeros((1, 1), bool)), Detection("mug", 0.5, box, np.zeros((1, 1), bool))]
        self.assertEqual(len(place_objects(ds, None, ROOM, LIB, (W, H))), 1)


class Match(unittest.TestCase):
    def test_clamp_scale(self):
        self.assertEqual(clamp_scale(0.11, 0.10), (1.1, True)); self.assertEqual(clamp_scale(0.3, 0.1), (1.0, False))

    def test_expected_box_accounts_for_viewing_angle(self):
        p = Placement("mug", (0, 0.42, 0), 0, (0.12, 0.115, 0.12)); p.view_down_deg = 30
        measured, expected = expected_box(p, LIB["models"]["mug"])
        self.assertAlmostEqual(expected, 0.10 * math.cos(math.radians(30)) + 0.09 * 0.5)
        book = Placement("book", (0, 0.42, 0), 0, (0.24, 0.05, 0.24))
        self.assertAlmostEqual(expected_box(book, LIB["models"]["book"])[1], (0.22 + math.hypot(0.22, 0.15)) / 2)

    def test_match_models(self):
        p = Placement("mug", (0.1, 0.42, 0.9), 180, (0.12, 0.10, 0.12))
        [o], warnings = match_models([p], LIB)
        self.assertEqual((o.model, o.scale), ("mug", 1.0)); self.assertEqual(warnings, [])


class GradeScene(unittest.TestCase):
    def test_pass_fail_out_of_frame_and_decor(self):
        answer = {"objects": [{"label": "mug", "model": "mug", "position": [0, 0.42, 1]},
                              {"label": "book", "model": "book", "position": [3, 0.8, 3]}],
                  "decor": [{"label": "book", "name": "baked book", "center": [1, 0.5, 1]}]}
        scene = {"objects": [{"label": "mug", "model": "mug", "position": [0.05, 0.42, 1.0], "scale": 1.0},
                             {"label": "book", "model": "book", "position": [1.1, 0.42, 1.0], "scale": 1.0}]}
        g = grade_scene(scene, answer, {"book[3, 0.8, 3]": False})
        self.assertEqual([r["result"] for r in g["objects"]], ["pass", "out of frame"])
        self.assertEqual((g["passed"], g["total"], len(g["extra"]), len(g["decor"])), (1, 1, 0, 1))


if __name__ == "__main__":
    unittest.main()
