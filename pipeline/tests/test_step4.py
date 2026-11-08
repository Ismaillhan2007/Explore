"""Unit tests for step 4's logic and the grading (no ML models needed).

    cd pipeline && .venv/bin/python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.datatypes import Camera, Detection, Plane, Room  # noqa: E402
from steps.evaluate import grade_detections, project  # noqa: E402
from steps.step4_detect import build_prompt, iou, measure, nms, phrase_to_label, size_check  # noqa: E402

LABELS = ["book", "lamp", "mug"]


def det(label, score, box, h=100, w=100):
    m = np.zeros((h, w), bool); m[box[1]:box[3], box[0]:box[2]] = True
    return Detection(label=label, score=score, box=box, mask=m)


class Prompt(unittest.TestCase):
    def test_prompt_uses_table_lamp(self):
        self.assertEqual(build_prompt(LABELS), "book . table lamp . mug .")

    def test_phrase_back_to_label(self):
        self.assertEqual(phrase_to_label("table lamp", LABELS), "lamp")
        self.assertEqual(phrase_to_label("mug", LABELS), "mug")
        self.assertEqual(phrase_to_label("book", LABELS), "book")
        self.assertIsNone(phrase_to_label("sofa", LABELS))


class Boxes(unittest.TestCase):
    def test_iou(self):
        self.assertAlmostEqual(iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertAlmostEqual(iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3)
        self.assertEqual(iou((0, 0, 1, 1), (2, 2, 3, 3)), 0.0)

    def test_nms_is_per_label(self):
        kept = nms([("mug", .9, (0, 0, 10, 10)), ("mug", .5, (1, 1, 10, 10)), ("book", .4, (1, 1, 10, 10))])
        self.assertEqual([(k[0], k[1]) for k in kept], [("mug", .9), ("book", .4)])


class Projection(unittest.TestCase):
    CAM = {"position": [0, 1, -2], "look_at": [0, 1, 0], "vfov_deg": 90}

    def test_point_straight_ahead_is_centre(self):
        u, v, z = project((0, 1, 1), self.CAM, 200, 100)
        self.assertAlmostEqual(u, 100); self.assertAlmostEqual(v, 50); self.assertAlmostEqual(z, 3)

    def test_right_and_up(self):
        u, v, _ = project((1, 2, 0), self.CAM, 200, 100)   # 45 deg up at vfov 90 -> top edge
        self.assertGreater(u, 100); self.assertAlmostEqual(v, 25.0)

    def test_behind_is_none(self):
        self.assertIsNone(project((0, 1, -3), self.CAM, 200, 100))


class Grading(unittest.TestCase):
    def test_found_missed_extra_and_decor(self):
        truth = [{"label": "mug", "pixel": (50, 50), "in_frame": True},
                 {"label": "lamp", "pixel": (10, 10), "in_frame": True},
                 {"label": "book", "pixel": None, "in_frame": False}]
        dets = [det("mug", .7, (40, 40, 60, 60)), det("mug", .4, (80, 80, 90, 90)), det("book", .5, (20, 70, 30, 80))]
        g = grade_detections(dets, truth, decor=[{"label": "book", "name": "baked book", "pixel": (25, 75)}])
        self.assertEqual([r["result"] for r in g["objects"]], ["found", "missed", "out of frame"])
        self.assertEqual((g["found"], g["in_frame"], g["false_detections"]), (1, 2, 1))
        self.assertEqual(g["decor_detections"][0]["decor"], "baked book")

    def test_wrong_label_does_not_count(self):
        g = grade_detections([det("book", .9, (40, 40, 60, 60))], [{"label": "mug", "pixel": (50, 50), "in_frame": True}])
        self.assertEqual((g["found"], g["false_detections"]), (0, 1))


class SizeCheck(unittest.TestCase):
    """A flat wall 2 m in front of a level camera 1.5 m up: box pixels -> metres via depth / focal length."""

    def setUp(self):
        self.cam = Camera(fx=100, fy=100, cx=50, cy=50, width=100, height=100)
        self.points = np.zeros((100, 100, 3)); self.points[..., 2] = 2.0
        M = np.eye(4); M[1, 1] = -1; M[1, 3] = 1.5      # camera space (y down) -> world (y up), camera 1.5 m high
        self.room = Room(floor=Plane((0, -1, 0), 1.5), walls=[], scale=1.0, wall_color="#ffffff", name="t", cam_to_world=M)
        self.lib = {"models": {"m": {"label": "lamp", "plausible": {"height_m": [0.3, 1.0], "width_m": [0.15, 0.7], "base_m": [0.25, 1.4]}}}}

    def test_measure(self):
        s = measure(det("lamp", .9, (40, 50, 60, 80)), self.points, self.room, self.cam)
        self.assertAlmostEqual(s["height_m"], 0.6)        # 30 px * 2 m / 100
        self.assertAlmostEqual(s["width_m"], 0.4)
        self.assertAlmostEqual(s["base_m"], 1.5 - 0.6)    # bottom pixel 30 px below centre -> 0.6 m below camera

    def test_tall_thin_box_is_not_a_table_lamp(self):
        # The visible top of a floor lamp (shade + pole): 0.8 m tall, 0.16 m wide, base on furniture height.
        lib = {"models": {"m": {"label": "lamp", "plausible": {"height_m": [0.3, 1.0], "aspect": [0.5, 3.0]}}}}
        thin = det("lamp", .9, (45, 40, 53, 80))            # 8 x 40 px -> 0.16 x 0.8 m, aspect 5
        kept, rejected = size_check([thin], self.points, self.room, lib, self.cam)
        self.assertEqual(kept, [])
        self.assertIn("aspect", rejected[0]["why"])
        self.assertAlmostEqual(measure(thin, self.points, self.room, self.cam)["aspect"], 5.0)

    def test_floor_lamp_rejected_table_lamp_kept(self):
        table = det("lamp", .9, (40, 50, 60, 80))         # 0.6 m tall, base 0.9 m
        floor = det("lamp", .8, (40, 20, 60, 125 - 26))   # tall and reaching low
        kept, rejected = size_check([table, floor], self.points, self.room, self.lib, self.cam)
        self.assertEqual([k.score for k in kept], [.9])
        self.assertEqual(len(rejected), 1)


if __name__ == "__main__":
    unittest.main()
