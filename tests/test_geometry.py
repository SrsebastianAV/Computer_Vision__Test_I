import numpy as np
import pytest

from src.geometry import (
    Pose,
    compose_cubes,
    compose_pose_matrix,
    rotation_z,
    transform_geometry,
    translation_matrix,
    unit_cube,
)


def test_homogeneous_translation():
    point = np.array([1.0, 2.0, 3.0, 1.0])
    result = translation_matrix(4, 5, 6) @ point
    np.testing.assert_allclose(result, [5, 7, 9, 1])


def test_rotation_z_is_counterclockwise_in_xy():
    point = np.array([1.0, 0.0, 0.0, 1.0])
    result = rotation_z(np.pi / 2) @ point
    np.testing.assert_allclose(result, [0, 1, 0, 1], atol=1e-12)


def test_pose_transform_preserves_pairwise_distances():
    geometry = compose_cubes(((0, 0, 0), (1, 0, 0), (0, 1, 0)))
    pose = Pose(
        position=np.array([2.0, 3.0, 4.0]),
        rotation=np.array([0.3, -0.5, 0.8]),
        pivot=np.array([0.5, 0.5, 0.5]),
    )
    transformed = transform_geometry(geometry, compose_pose_matrix(pose))
    before = np.linalg.norm(geometry.vertices[0] - geometry.vertices[8])
    after = np.linalg.norm(transformed.vertices[0] - transformed.vertices[8])
    assert after == pytest.approx(before)


def test_unit_cube_has_eight_vertices_and_twelve_edges():
    cube = unit_cube()
    assert cube.vertices.shape == (8, 3)
    assert len(cube.edges) == 12
