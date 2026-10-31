import numpy as np
from src import scene
from src.scene import (
    PIECE_KINDS,
    create_container,
    create_scene,
    get_geometry,
    get_piece,
    reset_piece,
    rotate_piece,
)


def _is_planar_in_z(piece) -> bool:
    z_values = {origin[2] for origin in piece.cube_origins}
    return len(z_values) == 1


def test_required_piece_ids_and_planarity():
    scene = create_scene()
    assert {piece.id for piece in scene.pieces} == {
        "L_planar", "Z", "square", "T", "L_nonplanar"
    }
    for piece in scene.pieces:
        assert _is_planar_in_z(piece) is (PIECE_KINDS[piece.id] == "planar")


def test_container_dimensions_and_floor_grid():
    container, grid = create_container()
    np.testing.assert_allclose(container.vertices.min(axis=0), [0, 0, 0])
    np.testing.assert_allclose(container.vertices.max(axis=0), [7, 7, 6])
    assert np.all(grid.vertices[:, 2] == 0)
    assert len(grid.edges) == 16


def test_scene_geometry_contains_container_and_all_pieces():
    scene = create_scene()
    geometry = dict(get_geometry(scene))
    assert set(geometry) == {"container", "L_planar", "Z", "square", "T", "L_nonplanar"}
    assert get_piece(scene, "square").local_geometry.vertices.shape[0] == 32


def test_nonplanar_piece_layouts_match_required_branches():
    scene = create_scene()
    assert get_piece(scene, "L_nonplanar").cube_origins == (
        (0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 1)
    )
    assert get_piece(scene, "T").cube_origins == (
        (0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 1, 0), (1, 0, 1)
    )


def test_nonplanar_branches_share_faces():
    scene = create_scene()
    for piece_id in ("T", "L_nonplanar"):
        origins = get_piece(scene, piece_id).cube_origins
        for origin in origins[1:]:
            assert any(
                sum(abs(a - b) for a, b in zip(origin, other)) == 1
                for other in origins
                if other != origin
            )


def test_preview_rotation_changes_only_the_selected_nonplanar_piece():
    scene = create_scene()
    original_t = get_piece(scene, "T").pose.rotation.copy()
    original_l = get_piece(scene, "L_nonplanar").pose.rotation.copy()

    rotate_piece(scene, "T", "z", np.pi / 4)

    np.testing.assert_allclose(get_piece(scene, "T").pose.rotation, [0, 0, np.pi / 4])
    np.testing.assert_allclose(get_piece(scene, "L_nonplanar").pose.rotation, original_l)
    np.testing.assert_allclose(get_piece(scene, "T").initial_pose.rotation, original_t)


def test_preview_rotation_can_be_reset():
    scene = create_scene()
    rotate_piece(scene, "L_nonplanar", "x", np.pi / 3)
    reset_piece(scene, "L_nonplanar")
    np.testing.assert_allclose(get_piece(scene, "L_nonplanar").pose.rotation, [0, 0, 0])
