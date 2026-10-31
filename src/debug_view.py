"""Orthographic debug views for inspecting the 3D scene.

This module intentionally does not implement the project camera or perspective
projection. It maps world coordinates to a 2D viewport so the scene
module can be inspected before the camera module is integrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .geometry import Geometry3D
from .scene import Scene, get_geometry


DebugView = Literal["top", "front", "side", "axonometric"]


@dataclass(frozen=True)
class DebugLine:
    start: tuple[float, float]
    end: tuple[float, float]
    color: tuple[int, int, int]
    source_id: str


@dataclass(frozen=True)
class DebugDrawData:
    lines: tuple[DebugLine, ...]
    view: DebugView
    scale: float


_AXES: dict[DebugView, tuple[int, int]] = {
    "top": (0, 1),
    "front": (0, 2),
    "side": (2, 1),
}
_PIECE_IDS = ("L_planar", "Z", "square", "T", "L_nonplanar")
_CONTAINER_COLOR = (180, 180, 180)
_GRID_COLOR = (100, 100, 100)
_SELECTED_COLOR = (255, 220, 40)


def _validate_viewport(viewport: tuple[int, int]) -> tuple[float, float]:
    if len(viewport) != 2 or any(d <= 0 for d in viewport):
        raise ValueError("viewport must contain two positive dimensions")
    return float(viewport[0]), float(viewport[1])


def _world_points(scene: Scene, source_ids: tuple[str, ...]) -> np.ndarray:
    geometries = dict(get_geometry(scene))
    return np.vstack([geometries[source_id].vertices for source_id in source_ids])


def _view_coordinates(points: np.ndarray, view: DebugView) -> np.ndarray:
    if view == "axonometric":
        return np.column_stack(
            (points[:, 0] - points[:, 2], points[:, 1] - 0.5 * (points[:, 0] + points[:, 2]))
        )
    axis_u, axis_v = _AXES[view]
    return points[:, (axis_u, axis_v)]


def _world_bounds(
    scene: Scene,
    view: DebugView,
    source_ids: tuple[str, ...],
) -> tuple[float, float, float, float]:
    points = _view_coordinates(_world_points(scene, source_ids), view)
    return (
        float(points[:, 0].min()),
        float(points[:, 0].max()),
        float(points[:, 1].min()),
        float(points[:, 1].max()),
    )


def _projector(
    scene: Scene,
    view: DebugView,
    viewport: tuple[int, int],
    margin: float,
    source_ids: tuple[str, ...],
) -> tuple[callable, float]:
    width, height = _validate_viewport(viewport)
    min_u, max_u, min_v, max_v = _world_bounds(scene, view, source_ids)
    span_u = max_u - min_u
    span_v = max_v - min_v
    available_width = width - 2 * margin
    available_height = height - 2 * margin
    if min(span_u, span_v, available_width, available_height) <= 0:
        raise ValueError("scene and viewport must have positive spans")

    scale = min(available_width / span_u, available_height / span_v)
    offset_u = (width - scale * span_u) / 2.0
    offset_v = (height - scale * span_v) / 2.0
    def project(point: np.ndarray) -> tuple[float, float]:
        coordinates = _view_coordinates(point[np.newaxis, :], view)[0]
        screen_u = offset_u + scale * (coordinates[0] - min_u)
        screen_v = height - offset_v - scale * (coordinates[1] - min_v)
        return float(screen_u), float(screen_v)

    return project, float(scale)


def build_debug_view(
    scene: Scene,
    view: DebugView = "top",
    viewport: tuple[int, int] = (800, 600),
    margin: float = 32.0,
    source_ids: tuple[str, ...] | None = None,
) -> DebugDrawData:
    """Create orthographic 2D lines from the current world-space scene.

    ``top`` maps X/Y, ``front`` maps X/Z, ``side`` maps Z/Y, and
    ``axonometric`` combines all three axes for a 3D-looking inspection view.
    This is a diagnostic view, not perspective projection.
    """
    if view not in (*_AXES, "axonometric"):
        raise ValueError(f"unknown debug view: {view}")
    if not np.isfinite(margin) or margin <= 0:
        raise ValueError("margin must be a positive finite number")

    if source_ids is None:
        source_ids = ("container", *_PIECE_IDS)
    known_ids = {"container", *_PIECE_IDS}
    unknown_ids = set(source_ids) - known_ids
    if unknown_ids:
        raise ValueError(f"unknown source ids: {sorted(unknown_ids)}")
    if not source_ids:
        raise ValueError("source_ids must not be empty")

    project, scale = _projector(scene, view, viewport, margin, source_ids)
    lines: list[DebugLine] = []
    geometries = dict(get_geometry(scene))
    for source_id in source_ids:
        geometry = geometries[source_id]
        if source_id == "container":
            color = _CONTAINER_COLOR
        else:
            piece = next(piece for piece in scene.pieces if piece.id == source_id)
            color = (
                _SELECTED_COLOR
                if piece.id == scene.selected_piece_id
                else piece.color
            )
        for edge in geometry.edges:
            lines.append(
                DebugLine(
                    start=project(geometry.vertices[edge.start]),
                    end=project(geometry.vertices[edge.end]),
                    color=color,
                    source_id=source_id,
                )
            )
    return DebugDrawData(lines=tuple(lines), view=view, scale=scale)
