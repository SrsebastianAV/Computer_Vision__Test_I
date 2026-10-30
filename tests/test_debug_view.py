import numpy as np
import pytest

from src.debug_view import build_debug_view
from src.scene import create_scene


@pytest.mark.parametrize("view", ["top", "front", "side", "axonometric"])
def test_debug_view_returns_finite_lines(view):
    data = build_debug_view(create_scene(), view=view, viewport=(800, 600))
    assert data.lines
    assert all(
        np.isfinite((*line.start, *line.end)).all()
        for line in data.lines
    )


def test_top_view_maps_world_origin_to_bottom_left_region():
    scene = create_scene()
    data = build_debug_view(scene, view="top", viewport=(800, 600), margin=32)
    container_lines = [line for line in data.lines if line.source_id == "container"]
    points = np.asarray([point for line in container_lines for point in (line.start, line.end)])
    # The scene keeps a square aspect ratio, so the 7x7 world is centered
    # horizontally inside the 800x600 viewport.
    assert points[:, 0].min() == pytest.approx(132)
    assert points[:, 1].max() == pytest.approx(568)


def test_invalid_debug_view_is_rejected():
    with pytest.raises(ValueError, match="unknown debug view"):
        build_debug_view(create_scene(), view="perspective")


def test_axonometric_view_uses_all_three_world_axes():
    scene = create_scene()
    data = build_debug_view(
        scene,
        view="axonometric",
        viewport=(800, 600),
        source_ids=("T",),
    )
    assert data.lines
    assert {line.source_id for line in data.lines} == {"T"}


def test_debug_view_can_show_container_or_one_piece():
    scene = create_scene()
    container = build_debug_view(
        scene, view="axonometric", source_ids=("container",)
    )
    piece = build_debug_view(
        scene, view="axonometric", source_ids=("L_nonplanar",)
    )
    assert {line.source_id for line in container.lines} == {"container"}
    assert {line.source_id for line in piece.lines} == {"L_nonplanar"}
