"""Homogeneous geometry primitives and unit-cube composition."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin
from typing import Iterable

import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class Edge:
    start: int
    end: int


@dataclass(frozen=True)
class Geometry3D:
    vertices: Array
    edges: tuple[Edge, ...]

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices, dtype=float)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError("vertices must have shape (N, 3)")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("vertices must contain only finite values")
        for edge in self.edges:
            if not (0 <= edge.start < len(vertices) and 0 <= edge.end < len(vertices)):
                raise ValueError("edge index is outside the vertex array")
        object.__setattr__(self, "vertices", vertices)


@dataclass(frozen=True)
class Pose:
    position: Array
    rotation: Array
    pivot: Array

    def __post_init__(self) -> None:
        for name in ("position", "rotation", "pivot"):
            value = np.asarray(getattr(self, name), dtype=float)
            if value.shape != (3,):
                raise ValueError(f"{name} must have shape (3,)")
            if not np.all(np.isfinite(value)):
                raise ValueError(f"{name} must contain only finite values")
            object.__setattr__(self, name, value)


def _homogeneous(matrix_3x3: Array, translation: Array | None = None) -> Array:
    result = np.eye(4, dtype=float)
    result[:3, :3] = matrix_3x3
    if translation is not None:
        result[:3, 3] = translation
    return result


def translation_matrix(tx: float, ty: float, tz: float) -> Array:
    values = np.asarray([tx, ty, tz], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("translation values must be finite")
    return _homogeneous(np.eye(3), values)


def rotation_x(angle: float) -> Array:
    if not np.isfinite(angle):
        raise ValueError("angle must be finite")
    c, s = cos(angle), sin(angle)
    return _homogeneous(np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float))


def rotation_y(angle: float) -> Array:
    if not np.isfinite(angle):
        raise ValueError("angle must be finite")
    c, s = cos(angle), sin(angle)
    return _homogeneous(np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float))


def rotation_z(angle: float) -> Array:
    if not np.isfinite(angle):
        raise ValueError("angle must be finite")
    c, s = cos(angle), sin(angle)
    return _homogeneous(np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float))


def compose_pose_matrix(pose: Pose) -> Array:
    """Return M = T(position) T(pivot) Rz Ry Rx T(-pivot)."""
    rx, ry, rz = pose.rotation
    return (
        translation_matrix(*pose.position)
        @ translation_matrix(*pose.pivot)
        @ rotation_z(rz)
        @ rotation_y(ry)
        @ rotation_x(rx)
        @ translation_matrix(*(-pose.pivot))
    )


def transform_geometry(geometry: Geometry3D, model: Array) -> Geometry3D:
    model = np.asarray(model, dtype=float)
    if model.shape != (4, 4):
        raise ValueError("model must have shape (4, 4)")
    homogeneous = np.column_stack(
        (geometry.vertices, np.ones(len(geometry.vertices), dtype=float))
    )
    transformed = (model @ homogeneous.T).T
    if np.any(np.isclose(transformed[:, 3], 0.0)):
        raise ValueError("model produced a point at infinity")
    vertices = transformed[:, :3] / transformed[:, 3, np.newaxis]
    return Geometry3D(vertices=vertices, edges=geometry.edges)


_CUBE_VERTICES = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=float,
)
_CUBE_EDGES = (
    Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0),
    Edge(4, 5), Edge(5, 6), Edge(6, 7), Edge(7, 4),
    Edge(0, 4), Edge(1, 5), Edge(2, 6), Edge(3, 7),
)


def unit_cube(origin: Iterable[float] = (0, 0, 0)) -> Geometry3D:
    origin_array = np.asarray(tuple(origin), dtype=float)
    if origin_array.shape != (3,) or not np.all(np.isfinite(origin_array)):
        raise ValueError("origin must contain three finite values")
    return Geometry3D(vertices=_CUBE_VERTICES + origin_array, edges=_CUBE_EDGES)


def compose_cubes(cube_origins: Iterable[Iterable[float]]) -> Geometry3D:
    origins = [np.asarray(tuple(origin), dtype=float) for origin in cube_origins]
    if not origins:
        raise ValueError("at least one cube is required")
    if any(origin.shape != (3,) or not np.all(np.isfinite(origin)) for origin in origins):
        raise ValueError("each cube origin must contain three finite values")

    vertices: list[Array] = []
    edges: list[Edge] = []
    for origin in origins:
        offset = len(vertices)
        cube = unit_cube(origin)
        vertices.extend(cube.vertices)
        edges.extend(Edge(edge.start + offset, edge.end + offset) for edge in cube.edges)
    return Geometry3D(vertices=np.asarray(vertices), edges=tuple(edges))
