"""Unit tests for the geometry in steps 1-3 (no ML models, numpy only).

    cd pipeline && .venv/bin/python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steps.datatypes import Camera  # noqa: E402
from steps.step1_camera import hfov_of, intrinsics_from_f35, intrinsics_from_fov  # noqa: E402
from steps.step2_depth import backproject, focal_correction  # noqa: E402
from steps.step3_room import (camera_frame, find_ceiling, fit_plane_svd, fit_room,  # noqa: E402
                              ransac_line_2d, ransac_plane, rgb_to_hex, to_world)


def synthetic_room(cam_h=1.6, pitch_deg=15.0, width=4.0, depth=5.0, ceiling=2.8, cam_x=0.5, cam_z=-2.0,
                   w=320, h=360, hfov=70.0):
    """Ray-cast an empty box room from a pitched pinhole camera. Returns (points[h,w,3] camera space, cam)."""
    cam = intrinsics_from_fov(w, h, hfov)
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    rays = np.stack([(u - cam.cx) / cam.fx, (v - cam.cy) / cam.fy, np.ones_like(u)], -1)  # camera space
    p = math.radians(pitch_deg)
    # camera space (x right, y down, z fwd) -> world (x right, y up, z fwd), camera pitched down by p
    # columns: camera right, camera down, camera forward, expressed in world
    R = np.array([[1, 0, 0], [0, -math.cos(p), -math.sin(p)], [0, -math.sin(p), math.cos(p)]])
    dw = rays @ R.T
    o = np.array([cam_x, cam_h, cam_z])
    t = np.full(dw.shape[:2], np.inf)
    for axis, lo, hi in [(0, -width / 2, width / 2), (1, 0.0, ceiling), (2, -depth / 2, depth / 2)]:
        for bound in (lo, hi):
            with np.errstate(divide="ignore", invalid="ignore"):
                ti = (bound - o[axis]) / dw[..., axis]
            ti[ti <= 0] = np.inf
            t = np.minimum(t, ti)
    pts_cam = rays * (t * 1.0)[..., None]  # rays have z = 1, so depth = t
    return pts_cam, cam


class Intrinsics(unittest.TestCase):
    def test_fov_round_trip(self):
        self.assertAlmostEqual(hfov_of(intrinsics_from_fov(1000, 750, 65)), 65, places=6)

    def test_f35_uses_long_side(self):
        cam = intrinsics_from_f35(3000, 4000, 26)            # portrait phone photo, 26 mm equivalent
        self.assertAlmostEqual(cam.fx, 26 / 36 * 4000)

    def test_focal_correction_is_one_at_training_fov(self):
        self.assertAlmostEqual(focal_correction(intrinsics_from_fov(800, 600, 60)), 1.0, places=6)
        self.assertLess(focal_correction(intrinsics_from_fov(800, 600, 80)), 1.0)   # wide lens -> closer


class Geometry(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(1)

    def test_backproject_centre_pixel_is_on_axis(self):
        cam = Camera(fx=100, fy=100, cx=50, cy=50, width=100, height=100)
        pts = backproject(np.full((100, 100), 3.0, np.float32), cam)
        self.assertTrue(np.allclose(pts[49, 49], [-0.015, -0.015, 3.0], atol=1e-6) or
                        np.allclose(pts[50, 50], [0.015, 0.015, 3.0], atol=1e-6))

    def test_plane_svd_and_ransac_recover_a_noisy_plane(self):
        n_true = np.array([0.0, -0.96, -0.28]); n_true /= np.linalg.norm(n_true)
        xy = self.rng.uniform(-2, 2, (2000, 2))
        base = np.c_[xy[:, 0], np.zeros(2000), xy[:, 1]]
        pts = base - (base @ n_true + 1.5)[:, None] * n_true + self.rng.normal(0, 0.01, (2000, 3))
        outliers = self.rng.uniform(-3, 3, (500, 3))
        n, d = fit_plane_svd(pts)
        self.assertGreater(abs(n @ n_true), 0.999)
        n2, d2, inl = ransac_plane(np.r_[pts, outliers], 0.04, 300, lambda n: True, self.rng)
        self.assertGreater(abs(n2 @ n_true), 0.999)
        self.assertAlmostEqual(abs(d2), 1.5, delta=0.02)
        self.assertGreater(inl[:2000].mean(), 0.95)

    def test_line_ransac(self):
        x = self.rng.uniform(-2, 2, 800)
        q = np.c_[x, 0.5 * x + 1.0 + self.rng.normal(0, 0.01, 800)]
        n, c, inl = ransac_line_2d(np.r_[q, self.rng.uniform(-3, 3, (200, 2))], 0.05, 300, self.rng)
        self.assertAlmostEqual(abs(-c / n[1]), 1.0, delta=0.03)    # y-intercept
        self.assertGreater(inl[:800].mean(), 0.95)

    def test_camera_frame_is_not_mirrored(self):
        # Camera pitched down 20 deg: world up in camera space = (0, -cos, -sin)
        a = math.radians(20)
        r, u, f = camera_frame(np.array([0.0, -math.cos(a), -math.sin(a)]))
        self.assertGreater(r[0], 0.99)                  # world right = camera right
        self.assertGreater(f[2], 0.9)                   # world forward ~ camera forward
        self.assertAlmostEqual(float(np.cross(r, u) @ f), -1.0, places=6)  # same handedness as camera space

    def test_to_world_puts_floor_at_zero(self):
        a = math.radians(20)
        n = np.array([0.0, -math.cos(a), -math.sin(a)])
        floor_pt = -1.7 * n                              # point on the floor straight "below" the camera
        r, u, f = camera_frame(n)
        self.assertAlmostEqual(float(to_world(floor_pt[None], r, u, f, 1.7)[0, 1]), 0.0, places=6)

    def test_find_ceiling(self):
        heights = np.r_[self.rng.uniform(0, 2.4, 5000), 2.7 + self.rng.normal(0, 0.01, 2000)]
        self.assertAlmostEqual(find_ceiling(heights, 1.5), 2.7, delta=0.02)
        self.assertIsNone(find_ceiling(self.rng.uniform(0, 1.6, 5000), 1.5))

    def test_hex(self):
        self.assertEqual(rgb_to_hex(217, 199, 168), "#d9c7a8")
        self.assertEqual(rgb_to_hex(-5, 300, 0), "#00ff00")


class SyntheticRoom(unittest.TestCase):
    """End-to-end step 3 on a perfect ray-cast box room: must recover the known geometry."""

    def test_fit_room_recovers_box(self):
        pts, cam = synthetic_room()
        rgb = np.full(pts.shape, 200, np.uint8)
        lib = {"rooms": {"Box": {"size_m": [4.0, 2.8, 5.0], "camera": {"position": [0.5, 1.6, -2.0]}}}}
        room = fit_room(pts, rgb, [], lib, "Box")
        rep = room.report
        self.assertAlmostEqual(rep["camera_height_m"], 1.6, delta=0.03)
        self.assertAlmostEqual(rep["camera_pitch_down_deg"], 15.0, delta=1.0)
        self.assertAlmostEqual(rep["ceiling_height_m"], 2.8, delta=0.05)
        self.assertIn("back", rep["walls_found"])
        self.assertAlmostEqual(rep["camera_to_back_wall_m"], 4.5, delta=0.1)
        self.assertAlmostEqual(rep["camera_position_m"][0], 0.5, delta=0.1)
        self.assertAlmostEqual(rep["camera_position_m"][2], -2.0, delta=0.1)
        # cam_to_world maps the camera origin to the camera position
        self.assertTrue(np.allclose((room.cam_to_world @ [0, 0, 0, 1])[:3], rep["camera_position_m"], atol=0.02))


if __name__ == "__main__":
    unittest.main()
