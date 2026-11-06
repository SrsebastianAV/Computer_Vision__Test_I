"""Numerical checks for camera conventions, framing, and validation."""

from dataclasses import replace
from math import pi
import unittest

import numpy as np

from src.camera import (
    ELEVATION_LIMIT, build_camera, change_camera_distance,
    create_overview_camera, create_face_camera, orbit_camera, reset_camera,
)
from src.scene import create_scene, get_geometry


class CameraTests(unittest.TestCase):
    def test_all_face_centers_and_inward_rotations_including_poles(self):
        centers = {'front': [3.5, 3.5, 0], 'back': [3.5, 3.5, 6],
                   'left': [0, 3.5, 3], 'right': [7, 3.5, 3],
                   'top': [3.5, 7, 3], 'bottom': [3.5, 0, 3]}
        for face, center in centers.items():
            with self.subTest(face=face):
                camera = create_face_camera(face)
                np.testing.assert_allclose(camera.position, center, atol=1e-12)
                np.testing.assert_allclose(camera.rotation @ camera.rotation.T, np.eye(3), atol=1e-12)
                self.assertAlmostEqual(np.linalg.det(camera.rotation), 1)
                target = camera.extrinsic @ [3.5, 3.5, 3, 1]
                np.testing.assert_allclose(target[:2], 0, atol=1e-12)
                self.assertGreater(target[2], 0)
                # Up/right camera displacements must have consistent screen directions.
                for axis, expected_delta in ((0, [1, 0]), (1, [0, -1])):
                    world = camera.parameters.target + camera.rotation[axis]
                    image = camera.screen_projection_matrix((1000, 720)) @ np.append(world, 1)
                    delta = image[:2] / image[2] - [500, 360]
                    np.testing.assert_allclose(delta / np.linalg.norm(delta), expected_delta, atol=1e-12)
                updated = orbit_camera(camera, 0.1, -0.1 if face == 'top' else 0.1)
                self.assertTrue(np.all(np.isfinite(updated.rotation)))
        with self.assertRaises(ValueError):
            create_face_camera('invalid')

    def test_initial_pose_and_world_to_camera_direction(self):
        camera = reset_camera()
        np.testing.assert_allclose(camera.position, [3.5, 3.5, 0])
        np.testing.assert_allclose(camera.rotation, np.eye(3))
        np.testing.assert_allclose(camera.translation, [-3.5, -3.5, 0])
        np.testing.assert_allclose(camera.extrinsic @ [3.5, 3.5, 0, 1], [0, 0, 0])
        np.testing.assert_allclose(camera.extrinsic @ [3.5, 3.5, 3, 1], [0, 0, 3])

    def test_intrinsics_from_vertical_fov(self):
        camera = reset_camera()
        np.testing.assert_allclose(camera.intrinsic,
            [[360 * np.sqrt(3), 0, 500], [0, 360 * np.sqrt(3), 360], [0, 0, 1]])
        smaller = reset_camera((800, 600))
        np.testing.assert_allclose(smaller.parameters.principal_point, [400, 300])
        self.assertAlmostEqual(smaller.intrinsic[1, 1], 300 * np.sqrt(3))

    def test_orbit_is_proper_rotation_and_looks_at_target(self):
        for camera in (reset_camera(), create_overview_camera(),
                       orbit_camera(reset_camera(), -pi / 3, -pi / 6)):
            np.testing.assert_allclose(camera.rotation @ camera.rotation.T, np.eye(3), atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(camera.rotation), 1)
            target_camera = camera.extrinsic @ np.append(camera.parameters.target, 1)
            np.testing.assert_allclose(target_camera, [0, 0, camera.parameters.distance], atol=1e-12)
            np.testing.assert_allclose(camera.extrinsic @ np.append(camera.position, 1), 0, atol=1e-12)

    def test_positive_azimuth_moves_toward_positive_x(self):
        camera = orbit_camera(reset_camera(), pi / 2, 0)
        np.testing.assert_allclose(camera.position, [6.5, 3.5, 3], atol=1e-12)

    def test_screen_orientation_and_single_vertical_flip(self):
        camera = reset_camera()
        matrix = camera.screen_projection_matrix((1000, 720))
        def uv(point):
            homogeneous = matrix @ [*point, 1]
            return homogeneous[:2] / homogeneous[2]
        np.testing.assert_allclose(uv([3.5, 3.5, 3]), [500, 360])
        self.assertGreater(uv([4.5, 3.5, 3])[0], 500)
        self.assertLess(uv([3.5, 4.5, 3])[1], 360)

    def test_overview_contains_entire_container(self):
        camera = create_overview_camera()
        vertices = create_scene().container.vertices
        homogeneous = np.column_stack((vertices, np.ones(len(vertices))))
        depths = (camera.extrinsic @ homogeneous.T)[2]
        image = (camera.screen_projection_matrix((1000, 720)) @ homogeneous.T).T
        uv = image[:, :2] / image[:, 2, None]
        self.assertTrue(np.all(depths > camera.parameters.near))
        self.assertTrue(np.all(depths < camera.parameters.far))
        self.assertTrue(np.all((uv >= 0) & (uv < [1000, 720])))
        np.testing.assert_array_equal(camera.intrinsic, reset_camera().intrinsic)

    def test_front_plane_has_zero_depth(self):
        camera = reset_camera()
        self.assertEqual((camera.extrinsic @ [0, 0, 0, 1])[2], 0)
        self.assertLessEqual((camera.extrinsic @ [7, 7, 0, 1])[2], camera.parameters.near)

    def test_distance_and_poles_are_limited(self):
        camera = change_camera_distance(reset_camera(), -100)
        self.assertGreater(camera.parameters.distance, camera.parameters.near)
        camera = orbit_camera(camera, 0, 100)
        self.assertEqual(camera.parameters.elevation, ELEVATION_LIMIT)
        np.testing.assert_allclose(camera.rotation @ camera.rotation.T, np.eye(3), atol=1e-12)

    def test_invalid_parameters(self):
        parameters = reset_camera().parameters
        for changes in ({'near': 0}, {'far': 0.05}, {'distance': 0.1},
                        {'focal_length_x': 0}, {'elevation': pi / 2 + 0.1},
                        {'azimuth': np.nan}, {'target': [1, 2]},
                        {'principal_point': [np.inf, 0]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(parameters, **changes)
        for viewport in ((0, 720), (1000, -1), (1.5, 720)):
            with self.subTest(viewport=viewport), self.assertRaises(ValueError):
                reset_camera(viewport)
        with self.assertRaises(ValueError):
            orbit_camera(reset_camera(), np.inf, 0)
        with self.assertRaises(ValueError):
            change_camera_distance(reset_camera(), np.nan)

    def test_camera_updates_preserve_inputs_and_scene(self):
        scene = create_scene()
        before = [(name, geometry.vertices.copy()) for name, geometry in get_geometry(scene)]
        camera = reset_camera()
        original = camera.position.copy()
        orbit_camera(camera, pi / 4, pi / 8)
        change_camera_distance(camera, 10)
        np.testing.assert_array_equal(camera.position, original)
        for (name, vertices), (after_name, geometry) in zip(before, get_geometry(scene)):
            self.assertEqual(name, after_name)
            np.testing.assert_array_equal(vertices, geometry.vertices)
        # Inputs are copied, so later external mutations cannot change the camera.
        target = np.array([3.5, 3.5, 3.0])
        parameters = replace(camera.parameters, target=target)
        other = build_camera(parameters)
        target[:] = 0
        np.testing.assert_array_equal(other.parameters.target, [3.5, 3.5, 3])


if __name__ == '__main__':
    unittest.main()
