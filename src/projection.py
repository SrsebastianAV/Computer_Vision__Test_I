"""Flujo: local -> mundo -> cámara -> imagen homogénea -> división -> píxel.


"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from .camera import Camera, validate_viewport
from .geometry import Geometry3D, compose_pose_matrix
from .scene import Scene


@dataclass(frozen=True)
class ProjectedPoint:
    uv: np.ndarray
    depth: float


@dataclass(frozen=True)
class ProjectedEdge:
    start: ProjectedPoint
    end: ProjectedPoint
    color: tuple[int, int, int]
    source_piece_id: str


@dataclass
class ProjectionDiagnostics:
    discarded_points: int = 0
    discarded_edges: int = 0
    clipped_edges: int = 0


@dataclass
class DrawPrimitives2D:
    edges: list[ProjectedEdge] = field(default_factory=list)
    labels: list[object] = field(default_factory=list)
    diagnostics: ProjectionDiagnostics = field(default_factory=ProjectionDiagnostics)

    def extend(self, other: DrawPrimitives2D) -> None:
        self.edges.extend(other.edges)
        self.labels.extend(other.labels)
        self.diagnostics.discarded_points += other.diagnostics.discarded_points
        self.diagnostics.discarded_edges += other.diagnostics.discarded_edges
        self.diagnostics.clipped_edges += other.diagnostics.clipped_edges


@dataclass
class ProjectionTrace:
    """Resultados de cada etapa; None significa que no pudo calcularse."""
    point_local: np.ndarray | None = None     # 4 coordenadas homogéneas
    point_world: np.ndarray | None = None     # 4 coordenadas homogéneas
    point_camera: np.ndarray | None = None    # 3 coordenadas, Z = profundidad
    point_image_h: np.ndarray | None = None   # 3 coordenadas antes de dividir
    point_image_up: np.ndarray | None = None  # 2 coordenadas, v hacia arriba
    point_pixel: np.ndarray | None = None     # 2 coordenadas, v hacia abajo
    inside_viewport: bool = False
    reason: str = ''

    @property
    def projected_point(self) -> ProjectedPoint | None:
        if self.point_pixel is None:
            return None
        return ProjectedPoint(self.point_pixel, float(self.point_camera[2]))

    def describe(self) -> str:
        stages = (
            ('1. Local: [x, y, z, 1]', self.point_local),
            ('2. Mundo: M @ local', self.point_world),
            ('3. Cámara: [R | t] @ mundo', self.point_camera),
            ('4. Imagen homogénea: K @ cámara', self.point_image_h),
            ('5. División perspectiva: [h0/h2, h1/h2]', self.point_image_up),
            ('6. Píxel: [u, height - v_up]', self.point_pixel),
        )
        lines = []
        for label, value in stages:
            coordinates = 'No calculado' if value is None else np.array2string(
                value, precision=4, suppress_small=True, separator=', ', max_line_width=160)
            lines.append(f'{label}\n   {coordinates}')
        if self.point_camera is not None:
            lines.append(f'Profundidad Zc = {self.point_camera[2]:.4f}')
        if self.reason:
            lines.append(f'Descartado: {self.reason}')
        else:
            lines.append('Dentro de imagen' if self.inside_viewport else 'Fuera del recuadro de imagen')
        return '\n'.join(lines)


class Viewport:
    """Imagen: origen arriba a la izquierda; u derecha, v abajo."""
    def __init__(self, size: tuple[int, int]):
        self.width, self.height = validate_viewport(size)

    def to_pixel(self, point_image_up: np.ndarray) -> np.ndarray:
        u, v_up = point_image_up
        return np.array([u, self.height - v_up])  # Única inversión vertical.

    def contains(self, pixel: np.ndarray) -> bool:
        u, v = pixel
        return bool(0 <= u < self.width and 0 <= v < self.height)


class Projection:
    """Proyecta con una cámara y un viewport, sin modificar el estado 3D."""
    def __init__(self, camera: Camera, viewport: tuple[int, int]):
        self.camera = camera
        self.viewport = Viewport(viewport)

    def local_to_world(self, point_local: np.ndarray, model: np.ndarray) -> np.ndarray:
        """Etapa 2: pose M (4x4) aplicada al punto local homogéneo."""
        model = np.asarray(model, dtype=float)
        if model.shape != (4, 4) or not np.all(np.isfinite(model)):
            raise ValueError('model must be a finite 4 x 4 matrix')
        point_world = model @ point_local
        if not np.all(np.isfinite(point_world)) or np.isclose(point_world[3], 0):
            raise ValueError('model produced an invalid world point or a point at infinity')
        return point_world / point_world[3]

    def camera_to_image(self, point_camera: np.ndarray) -> np.ndarray:
        """Etapa 4: intrínsecos K, antes de la división perspectiva."""
        return self.camera.intrinsic @ point_camera

    def perspective_divide(self, point_image_h: np.ndarray) -> np.ndarray:
        """Etapa 5: dividir por profundidad, tras comprobar near/far."""
        return point_image_h[:2] / point_image_h[2]

    def trace_point(self, point_local, model) -> ProjectionTrace:
        """Inicio del flujo. Guarda cada etapa para poder inspeccionarla."""
        point = np.asarray(point_local, dtype=float)
        if point.shape != (3,):
            raise ValueError('point_local must have shape (3,)')
        trace = ProjectionTrace()

        # 1. Coordenadas locales -> homogéneas.
        trace.point_local = np.append(point, 1.0)
        if not np.all(np.isfinite(point)):
            trace.reason = 'El punto contiene NaN o infinito.'
            return trace

        # 2. Local -> mundo mediante la pose M de la pieza.
        trace.point_world = self.local_to_world(trace.point_local, model)

        # 3. Mundo -> cámara mediante los extrínsecos [R | t].
        trace.point_camera = self.camera.world_to_camera(trace.point_world)

        # 4-6. Intrínsecos -> división perspectiva -> viewport.
        return self._finish_trace(trace)

    def _finish_trace(self, trace: ProjectionTrace) -> ProjectionTrace:
        """Segunda mitad del flujo, compartida con los segmentos recortados."""
        depth = trace.point_camera[2]
        p = self.camera.parameters
        if not np.all(np.isfinite(trace.point_camera)):
            trace.reason = 'Coordenadas de cámara no finitas.'
            return trace
        if not p.near < depth < p.far:
            trace.reason = f'Se requiere near < Zc < far ({p.near:g} < {depth:g} < {p.far:g}).'
            return trace

        # 4. Cámara -> imagen homogénea: h = K @ [Xc, Yc, Zc].
        trace.point_image_h = self.camera_to_image(trace.point_camera)

        # 5. División perspectiva: (u, v_up) = (h0/h2, h1/h2).
        trace.point_image_up = self.perspective_divide(trace.point_image_h)
        if not np.all(np.isfinite(trace.point_image_up)):
            trace.reason = 'La proyección produce coordenadas no finitas.'
            return trace

        # 6. Imagen -> píxeles: origen superior izquierdo, v hacia abajo.
        trace.point_pixel = self.viewport.to_pixel(trace.point_image_up)
        trace.inside_viewport = self.viewport.contains(trace.point_pixel)
        return trace

    def project_point(self, point_local, model) -> ProjectedPoint | None:
        return self.trace_point(point_local, model).projected_point

    def _clip_depth(self, start: np.ndarray, end: np.ndarray):
        """Recorte en cámara, antes de dividir por profundidad."""
        p = self.camera.parameters
        lower = p.near + max(1e-9, p.near * 1e-9)
        upper = np.nextafter(p.far, p.near)
        dz = end[2] - start[2]
        if abs(dz) < 1e-15:
            return (start, end, False) if lower <= start[2] <= upper else None
        first, last = sorted(((lower - start[2]) / dz, (upper - start[2]) / dz))
        first, last = max(0.0, first), min(1.0, last)
        if first > last:
            return None
        direction = end - start
        return start + first * direction, start + last * direction, first > 0 or last < 1

    def project_geometry(self, geometry: Geometry3D, model,
                         source_piece_id: str, color: tuple[int, int, int]) -> DrawPrimitives2D:
        # Cada vértice sigue el mismo flujo documentado en trace_point.
        traces = [self.trace_point(vertex, model) for vertex in geometry.vertices]
        result = DrawPrimitives2D()
        result.diagnostics.discarded_points = sum(trace.projected_point is None for trace in traces)
        for edge in geometry.edges:
            start = traces[edge.start].point_camera
            end = traces[edge.end].point_camera
            clipped = self._clip_depth(start, end)
            if clipped is None:
                result.diagnostics.discarded_edges += 1
                continue
            start, end, changed = clipped
            # Extremos nuevos ya en cámara: continuar por etapas 4-6.
            if changed:
                a = self._finish_trace(ProjectionTrace(point_camera=start)).projected_point
                b = self._finish_trace(ProjectionTrace(point_camera=end)).projected_point
            else:
                a = traces[edge.start].projected_point
                b = traces[edge.end].projected_point
            if a is None or b is None:
                result.diagnostics.discarded_edges += 1
                continue
            result.diagnostics.clipped_edges += int(changed)
            result.edges.append(ProjectedEdge(a, b, color, source_piece_id))
        return result

    def project_scene(self, scene: Scene) -> DrawPrimitives2D:
        result = self.project_geometry(scene.container, np.eye(4), 'container', (89, 111, 139))
        for piece in scene.pieces:
            model = compose_pose_matrix(piece.pose)
            result.extend(self.project_geometry(piece.local_geometry, model, piece.id, piece.color))
        return result


# Interfaces públicas del documento: delegan en la clase, sin duplicar fórmulas.
def project_point(point_local, model, camera: Camera,
                  viewport: tuple[int, int]) -> ProjectedPoint | None:
    return Projection(camera, viewport).project_point(point_local, model)


def project_geometry(geometry: Geometry3D, model, camera: Camera,
                     viewport: tuple[int, int], source_piece_id: str,
                     color: tuple[int, int, int]) -> DrawPrimitives2D:
    return Projection(camera, viewport).project_geometry(geometry, model, source_piece_id, color)


def project_scene(scene: Scene, camera: Camera, viewport: tuple[int, int]) -> DrawPrimitives2D:
    return Projection(camera, viewport).project_scene(scene)


if __name__ == '__main__':
    from .camera import reset_camera
    from .geometry import translation_matrix

    camera = reset_camera()
    projection = Projection(camera, (1000, 720))
    # Pieza trasladada: local y mundo son distintos.
    model = translation_matrix(3.5, 3.5, 3)
    print('Ejemplo: local (0.5, 0.5, 0), pieza trasladada a (3.5, 3.5, 3).\n')
    print(projection.trace_point([0.5, 0.5, 0], model).describe())
