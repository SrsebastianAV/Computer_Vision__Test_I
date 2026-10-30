"""Scene models, required pieces, and the 7 x 7 x 6 container."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np

from .geometry import (
    Edge,
    Geometry3D,
    Pose,
    compose_cubes,
    compose_pose_matrix,
    transform_geometry,
)


PieceKind = Literal["planar", "nonplanar"]


@dataclass
class Piece:
    id: str
    display_name: str
    local_geometry: Geometry3D
    pose: Pose
    kind: PieceKind
    color: tuple[int, int, int]
    initial_pose: Pose = field(repr=False)
    cube_origins: tuple[tuple[int, int, int], ...] = field(repr=False)


@dataclass
class Scene:
    container: Geometry3D
    pieces: list[Piece]
    selected_piece_id: str | None = None


PIECE_CUBE_ORIGINS: dict[str, tuple[tuple[int, int, int], ...]] = {
    "L_planar": ((0, 0, 0), (0, 1, 0), (0, 2, 0), (1, 0, 0)),
    "Z": ((0, 1, 0), (1, 1, 0), (1, 0, 0), (2, 0, 0)),
    "square": ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)),
    "T": ((0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 1, 0), (1, 0, 1)),
    "L_nonplanar": ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 1)),
}

PIECE_KINDS: dict[str, PieceKind] = {
    "L_planar": "planar",
    "Z": "planar",
    "square": "planar",
    "T": "nonplanar",
    "L_nonplanar": "nonplanar",
}

INITIAL_POSITIONS: dict[str, tuple[float, float, float]] = {
    "L_planar": (0.0, 0.0, 0.0),
    "Z": (3.0, 0.0, 0.0),
    "square": (0.0, 3.0, 0.0),
    "T": (3.0, 3.0, 0.0),
    "L_nonplanar": (1.0, 1.0, 2.0),
}


def _container_geometry(width: int, height: int, depth: int) -> Geometry3D:
    vertices = np.array(
        [
            [0, 0, 0], [width, 0, 0], [width, height, 0], [0, height, 0],
            [0, 0, depth], [width, 0, depth], [width, height, depth], [0, height, depth],
        ],
        dtype=float,
    )
    edges = (
        Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0),
        Edge(4, 5), Edge(5, 6), Edge(6, 7), Edge(7, 4),
        Edge(0, 4), Edge(1, 5), Edge(2, 6), Edge(3, 7),
    )
    return Geometry3D(vertices=vertices, edges=edges)


def _floor_grid(width: int, height: int, depth: int) -> Geometry3D:
    vertices: list[tuple[float, float, float]] = []
    edges: list[Edge] = []

    for x in range(width + 1):
        start = len(vertices)
        vertices.extend([(x, 0, 0), (x, height, 0)])
        edges.append(Edge(start, start + 1))
    for y in range(height + 1):
        start = len(vertices)
        vertices.extend([(0, y, 0), (width, y, 0)])
        edges.append(Edge(start, start + 1))
    return Geometry3D(vertices=np.asarray(vertices), edges=tuple(edges))


def create_container() -> tuple[Geometry3D, Geometry3D]:
    """Return boundary and unit grid on z=0, nearest the initial camera."""
    return _container_geometry(7, 7, 6), _floor_grid(7, 7, 6)


def _create_piece(piece_id: str) -> Piece:
    origins = PIECE_CUBE_ORIGINS[piece_id]
    pose = Pose(
        position=np.asarray(INITIAL_POSITIONS[piece_id], dtype=float),
        rotation=np.zeros(3),
        pivot=np.zeros(3),
    )
    return Piece(
        id=piece_id,
        display_name=piece_id,
        local_geometry=compose_cubes(origins),
        pose=pose,
        kind=PIECE_KINDS[piece_id],
        color=(80, 160, 220),
        initial_pose=pose,
        cube_origins=origins,
    )


def create_scene() -> Scene:
    container, grid = create_container()
    container_with_grid = Geometry3D(
        vertices=np.vstack((container.vertices, grid.vertices)),
        edges=container.edges
        + tuple(
            Edge(edge.start + len(container.vertices), edge.end + len(container.vertices))
            for edge in grid.edges
        ),
    )
    return Scene(
        container=container_with_grid,
        pieces=[_create_piece(piece_id) for piece_id in PIECE_CUBE_ORIGINS],
    )


def get_piece(scene: Scene, piece_id: str) -> Piece:
    for piece in scene.pieces:
        if piece.id == piece_id:
            return piece
    raise KeyError(f"unknown piece: {piece_id}")


def rotate_piece(scene: Scene, piece_id: str, axis: str, angle: float) -> None:
    """Rotate one piece around its local pivot, preserving its 3D geometry."""
    if piece_id not in {"T", "L_nonplanar"}:
        raise ValueError("the preview rotation is restricted to T and L_nonplanar")
    if axis not in {"x", "y", "z"}:
        raise ValueError("axis must be x, y, or z")
    if not np.isfinite(angle):
        raise ValueError("angle must be finite")

    piece = get_piece(scene, piece_id)
    rotation = piece.pose.rotation.copy()
    rotation[{"x": 0, "y": 1, "z": 2}[axis]] += angle
    piece.pose = replace(piece.pose, rotation=rotation)


def reset_piece(scene: Scene, piece_id: str) -> None:
    """Restore one piece to its initial 3D pose."""
    if piece_id not in {"T", "L_nonplanar"}:
        raise ValueError("the preview reset is restricted to T and L_nonplanar")
    piece = get_piece(scene, piece_id)
    piece.pose = replace(
        piece.pose,
        position=piece.initial_pose.position.copy(),
        rotation=piece.initial_pose.rotation.copy(),
        pivot=piece.initial_pose.pivot.copy(),
    )


def get_geometry(scene: Scene) -> list[tuple[str, Geometry3D]]:
    result = [("container", scene.container)]
    result.extend(
        (piece.id, transform_geometry(piece.local_geometry, compose_pose_matrix(piece.pose)))
        for piece in scene.pieces
    )
    return result
