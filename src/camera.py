"""Pinhole camera and world-to-camera extrinsics (INTERFACES section 5.3).

Camera axes: X right, Y up, Z forward. K produces Y-up image coordinates;
screen_projection_matrix performs the ONLY vertical flip for a top-left image.
Angles are radians and distances use the scene's unit-cube units.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, pi, sin, tan

import numpy as np


DEFAULT_VIEWPORT = (1000, 720)
DEFAULT_VERTICAL_FOV = pi / 3  # 60 degrees
ELEVATION_LIMIT = pi / 2

# (azimuth, elevation, distance to container center)
FACE_PARAMETERS = {
    "front": (0.0, 0.0, 3.0),
    "back": (pi, 0.0, 3.0),
    "left": (-pi / 2, 0.0, 3.5),
    "right": (pi / 2, 0.0, 3.5),
    "top": (0.0, pi / 2, 3.5),
    "bottom": (0.0, -pi / 2, 3.5),
}


def _vector(value, size: int, name: str) -> np.ndarray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain {size} finite values")
    result.setflags(write=False)
    return result


def _finite(value: float, name: str) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")


def validate_viewport(viewport: tuple[int, int]) -> tuple[int, int]:
    if len(viewport) != 2 or any(
        isinstance(d, (bool, np.bool_)) or not isinstance(d, (int, np.integer)) or d <= 0
        for d in viewport
    ):
        raise ValueError("viewport must contain two positive integer dimensions")
    return viewport


@dataclass(frozen=True, eq=False)
class CameraParameters:
    target: np.ndarray
    azimuth: float
    elevation: float
    distance: float
    focal_length_x: float
    focal_length_y: float
    principal_point: np.ndarray
    near: float
    far: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", _vector(self.target, 3, "target"))
        object.__setattr__(self, "principal_point", _vector(self.principal_point, 2, "principal_point"))
        for name in ("azimuth", "elevation", "distance", "focal_length_x",
                     "focal_length_y", "near", "far"):
            _finite(getattr(self, name), name)
        if not 0 < self.near < self.far:
            raise ValueError("require 0 < near < far")
        if self.distance <= self.near:
            raise ValueError("distance must be greater than near")
        if min(self.focal_length_x, self.focal_length_y) <= 0:
            raise ValueError("focal lengths must be positive")
        if abs(self.elevation) > ELEVATION_LIMIT:
            raise ValueError("elevation must be between -pi/2 and pi/2")


class Camera:
    """Cámara orbital: construye K, C, R, t y transforma mundo → cámara."""

    def __init__(self, parameters: CameraParameters):
        self.parameters = parameters
        self.intrinsic = self._calculate_intrinsic()
        self.position = self._calculate_position()
        self.rotation = self._calculate_rotation()
        self.translation = -self.rotation @ self.position
        for array in (self.intrinsic, self.position, self.rotation, self.translation):
            if not np.all(np.isfinite(array)):
                raise ValueError("camera calculation produced non-finite values")
            array.setflags(write=False)

    def _calculate_intrinsic(self) -> np.ndarray:
        """K: focales en píxeles, skew cero y punto principal (cx, cy)."""
        p = self.parameters
        cx, cy = p.principal_point
        return np.array([[p.focal_length_x, 0, cx],
                         [0, p.focal_length_y, cy], [0, 0, 1]], dtype=float)

    def _calculate_position(self) -> np.ndarray:
        """C: posición orbital en coordenadas del mundo."""
        p = self.parameters
        a, e = p.azimuth, p.elevation
        ce = 0.0 if abs(cos(e)) < 1e-15 else cos(e)
        offset = np.array([ce * sin(a), sin(e), -ce * cos(a)])
        return p.target + p.distance * offset

    def _calculate_rotation(self) -> np.ndarray:
        """R: filas = ejes right, up, forward de cámara en el mundo."""
        p = self.parameters
        forward = (p.target - self.position) / p.distance
        # Tangente horizontal estable, incluso en las caras superior/inferior.
        right = np.array([cos(p.azimuth), 0.0, sin(p.azimuth)])
        up = np.cross(forward, right)
        return np.vstack((right, up, forward))

    def world_to_camera(self, point_world) -> np.ndarray:
        """[Xc, Yc, Zc] = [R | t] @ [Xw, Yw, Zw, 1]."""
        point_world = np.asarray(point_world, dtype=float)
        if point_world.shape != (4,) or not np.all(np.isfinite(point_world)):
            raise ValueError("point_world must contain four finite homogeneous coordinates")
        return self.extrinsic @ point_world

    def orbit(self, delta_azimuth: float, delta_elevation: float) -> Camera:
        """Devuelve otra cámara; no modifica esta cámara ni la escena."""
        _finite(delta_azimuth, "delta_azimuth")
        _finite(delta_elevation, "delta_elevation")
        p = self.parameters
        azimuth = ((p.azimuth % (2 * pi)) + (delta_azimuth % (2 * pi))) % (2 * pi)
        elevation = float(np.clip(p.elevation + delta_elevation, -ELEVATION_LIMIT, ELEVATION_LIMIT))
        return Camera(replace(p, azimuth=azimuth, elevation=elevation))

    def change_distance(self, delta: float) -> Camera:
        _finite(delta, "delta")
        p = self.parameters
        minimum = p.near + max(0.01, p.near * 0.01)
        return Camera(replace(p, distance=max(minimum, p.distance + delta)))

    @property
    def extrinsic(self) -> np.ndarray:
        """3 x 4 world-to-camera matrix [R | t]."""
        return np.column_stack((self.rotation, self.translation))

    @property
    def projection_matrix(self) -> np.ndarray:
        """K [R | t], before perspective division, with image Y pointing up."""
        return self.intrinsic @ self.extrinsic

    def screen_projection_matrix(self, viewport: tuple[int, int]) -> np.ndarray:
        """Return S K [R | t] for top-left image coordinates.

        After homogeneous division, v_screen = height - v_up. Do not flip
        again in the renderer. Depth must be checked separately before division.
        The viewport must match the intrinsics' calibration resolution.
        """
        _, height = validate_viewport(viewport)
        screen = np.array([[1, 0, 0], [0, -1, height], [0, 0, 1]], dtype=float)
        return screen @ self.projection_matrix


def build_camera(parameters: CameraParameters) -> Camera:
    """Compute orbital C, a no-roll look-at R, t=-R C, and K.

    azimuth=0 is the front (negative world Z), positive azimuth moves toward
    positive X, and positive elevation moves above the target (+world Y).
    """
    return Camera(parameters)


def orbit_camera(camera: Camera, delta_azimuth: float, delta_elevation: float) -> Camera:
    """Return a new camera orbiting the same target, with no scene mutation."""
    return camera.orbit(delta_azimuth, delta_elevation)


def change_camera_distance(camera: Camera, delta: float) -> Camera:
    """Add delta to orbital distance, clamped strictly above the near plane."""
    return camera.change_distance(delta)


def reset_camera(viewport: tuple[int, int] = DEFAULT_VIEWPORT) -> Camera:
    """Camera at (3.5, 3.5, 0), looking toward (3.5, 3.5, 3).

    Synthetic intrinsics: square pixels, zero skew, centered principal point,
    60-degree vertical field of view, no lens distortion.
    """
    width, height = validate_viewport(viewport)
    focal = height / (2 * tan(DEFAULT_VERTICAL_FOV / 2))
    return build_camera(CameraParameters(
        target=np.array([3.5, 3.5, 3.0]), azimuth=0.0, elevation=0.0, distance=3.0,
        focal_length_x=focal, focal_length_y=focal,
        principal_point=np.array([width / 2, height / 2]), near=0.1, far=100.0,
    ))


def create_overview_camera(viewport: tuple[int, int] = DEFAULT_VIEWPORT) -> Camera:
    """Second view: exterior orbit at 45 degrees azimuth, 25 elevation, d=14."""
    camera = change_camera_distance(reset_camera(viewport), 11.0)
    return orbit_camera(camera, pi / 4, 25 * pi / 180)


def create_face_camera(face: str, viewport: tuple[int, int] = DEFAULT_VIEWPORT) -> Camera:
    """Face-center camera looking inward: front z=0, back z=6, left x=0,
    right x=7, top y=7, bottom y=0. At top/bottom, image up is +Z/-Z.
    """
    if face not in FACE_PARAMETERS:
        raise ValueError(f"unknown container face: {face}")
    azimuth, elevation, distance = FACE_PARAMETERS[face]
    return build_camera(replace(reset_camera(viewport).parameters,
                                azimuth=azimuth, elevation=elevation, distance=distance))


if __name__ == "__main__":
    np.set_printoptions(precision=6, suppress=True)
    for name, camera in (("Inicial", reset_camera()), ("Exterior", create_overview_camera())):
        print(f"\n{name}\nC = {camera.position}\nK =\n{camera.intrinsic}")
        print(f"[R | t] =\n{camera.extrinsic}")
