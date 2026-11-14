import unittest

import numpy as np

from src.camera import create_face_camera, reset_camera
from src.geometry import Edge, Geometry3D, rotation_z, translation_matrix
from src.projection import Projection, project_geometry, project_point, project_scene
from src.scene import create_scene, get_geometry


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.viewport = (800, 600)
        self.camera = reset_camera(self.viewport)

    def test_trace_records_known_nonidentity_pose_at_every_stage(self):
        projection = Projection(self.camera, self.viewport)
        model = translation_matrix(3.5, 3.5, 3) @ rotation_z(np.pi / 2)
        trace = projection.trace_point([1, 0, 0], model)
        focal = 300 * np.sqrt(3)
        np.testing.assert_allclose(trace.point_local, [1, 0, 0, 1])
        np.testing.assert_allclose(trace.point_world, [3.5, 4.5, 3, 1])
        np.testing.assert_allclose(trace.point_camera, [0, 1, 3], atol=1e-12)
        np.testing.assert_allclose(trace.point_image_h, [1200, 900 + focal, 3])
        np.testing.assert_allclose(trace.point_image_up, [400, 300 + focal / 3])
        np.testing.assert_allclose(trace.point_pixel, [400, 300 - focal / 3])
        self.assertTrue(trace.inside_viewport)
        self.assertFalse(trace.reason)

    def test_trace_matches_combined_matrix_for_every_camera_face(self):
        model = translation_matrix(3, 3, 2) @ rotation_z(0.3)
        point = np.array([0.5, 0.7, 0.3])
        for face in ('front', 'back', 'left', 'right', 'top', 'bottom'):
            with self.subTest(face=face):
                camera = create_face_camera(face, self.viewport)
                trace = Projection(camera, self.viewport).trace_point(point, model)
                combined = camera.intrinsic @ camera.extrinsic @ model @ np.append(point, 1)
                expected = combined[:2] / combined[2]
                expected[1] = 600 - expected[1]
                np.testing.assert_allclose(trace.point_pixel, expected, atol=1e-10)

    def test_trace_stops_before_dividing_at_zero_depth(self):
        with np.errstate(divide='raise', invalid='raise'):
            trace = Projection(self.camera, self.viewport).trace_point([3.5, 3.5, 0], np.eye(4))
        np.testing.assert_allclose(trace.point_camera, [0, 0, 0])
        self.assertIsNone(trace.point_image_h)
        self.assertIsNone(trace.point_image_up)
        self.assertIsNone(trace.projected_point)
        self.assertIn('near', trace.reason)
        self.assertIn('Descartado', trace.describe())

    def test_offscreen_point_is_distinct_from_invalid_depth(self):
        trace = Projection(self.camera, self.viewport).trace_point([100, 3.5, 3], np.eye(4))
        self.assertFalse(trace.inside_viewport)
        self.assertIsNotNone(trace.projected_point)
        self.assertFalse(trace.reason)

    def test_center_vertical_direction_and_model_transform(self):
        point = project_point([0, 0, 0], translation_matrix(3.5, 3.5, 3),
                              self.camera, self.viewport)
        np.testing.assert_allclose(point.uv, [400, 300])
        self.assertEqual(point.depth, 3)
        above = project_point([3.5, 4.5, 3], np.eye(4), self.camera, self.viewport)
        self.assertLess(above.uv[1], point.uv[1])

    def test_near_far_behind_and_nonfinite_points_are_discarded(self):
        for z in (-1, 0, 0.1, 100, 101, np.nan):
            with self.subTest(z=z):
                self.assertIsNone(project_point([3.5, 3.5, z], np.eye(4), self.camera, self.viewport))

    def test_segment_crossing_camera_plane_is_clipped_not_lost(self):
        geometry = Geometry3D(np.array([[3.5, 3.5, -1], [4, 4, 3]]), (Edge(0, 1),))
        result = project_geometry(geometry, np.eye(4), self.camera, self.viewport, 'line', (255, 255, 255))
        self.assertEqual(len(result.edges), 1)
        self.assertEqual(result.diagnostics.clipped_edges, 1)
        for point in (result.edges[0].start, result.edges[0].end):
            self.assertGreater(point.depth, self.camera.parameters.near)
            self.assertTrue(np.all(np.isfinite(point.uv)))

    def test_front_face_segment_is_discarded(self):
        geometry = Geometry3D(np.array([[0, 0, 0], [7, 7, 0]]), (Edge(0, 1),))
        result = project_geometry(geometry, np.eye(4), self.camera, self.viewport, 'front', (0, 0, 0))
        self.assertFalse(result.edges)
        self.assertEqual(result.diagnostics.discarded_edges, 1)

    def test_scene_projection_does_not_change_geometry(self):
        scene = create_scene()
        before = [geometry.vertices.copy() for _, geometry in get_geometry(scene)]
        result = project_scene(scene, self.camera, self.viewport)
        self.assertTrue(result.edges)
        self.assertGreater(result.diagnostics.discarded_points, 0)
        for old, (_, current) in zip(before, get_geometry(scene)):
            np.testing.assert_array_equal(old, current.vertices)

    def test_invalid_dimensions_raise_explicit_errors(self):
        with self.assertRaises(ValueError):
            project_point([1, 2], np.eye(4), self.camera, self.viewport)
        with self.assertRaises(ValueError):
            project_point([1, 2, 3], np.eye(3), self.camera, self.viewport)


if __name__ == '__main__':
    unittest.main()
