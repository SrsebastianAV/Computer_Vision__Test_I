"""Jugar: perspectiva y escena 3D interactiva, sin puntos de prueba."""
from __future__ import annotations
from dataclasses import dataclass, replace
from math import radians
import numpy as np
import pygame
from .camera import (build_camera, create_face_camera, create_overview_camera,
                     orbit_camera, change_camera_distance, reset_camera)
from .geometry import Edge, Geometry3D, compose_pose_matrix
from .projection import Projection, project_geometry, project_point, project_scene
from .scene import create_scene, get_geometry, get_piece, rotate_piece, reset_piece

BG = (12, 18, 29)
PANEL = (20, 29, 44)
INK = (229, 237, 248)
MUTED = (145, 166, 191)
CYAN = (73, 212, 217)
GOLD = (255, 204, 99)
PIECE_IDS = ('L_planar', 'Z', 'square', 'T', 'L_nonplanar')


@dataclass
class Layout:
    left: pygame.Rect
    image: pygame.Rect
    overview: pygame.Rect
    world: pygame.Rect


def layout(size) -> Layout:
    width, height = size
    side = int(width * 0.40)
    left = pygame.Rect(24, 96, width - side - 68, height - 120)
    image = pygame.Rect(left.x + 16, left.y + 56, left.w - 32, left.h - 104)
    overview = pygame.Rect(left.right + 20, 96, side, height - 120)
    world = pygame.Rect(overview.x + 14, 152, side - 28, overview.h - 188)
    return Layout(left, image, overview, world)


class Game:
    def __init__(self, size=(1280, 820)):
        self.scene = create_scene()
        for piece, color in zip(self.scene.pieces,
                                [(94, 199, 255), (185, 148, 255), (80, 218, 168),
                                 (255, 173, 98), (255, 122, 164)]):
            piece.color = color
        self.scene.selected_piece_id = 'T'
        self.layout = layout(size)
        self.camera = reset_camera(self.layout.image.size)
        self.observer = create_overview_camera(self.layout.world.size)
        self.source_ids = None
        self.dragging = False
        self.running = True
        self.show_projection_steps = False

    def resize(self, size):
        self.layout = layout(size)
        for name, viewport in (('camera', self.layout.image.size),
                               ('observer', self.layout.world.size)):
            old = getattr(self, name).parameters
            intrinsic = reset_camera(viewport).parameters
            setattr(self, name, build_camera(replace(old,
                focal_length_x=intrinsic.focal_length_x,
                focal_length_y=intrinsic.focal_length_y,
                principal_point=intrinsic.principal_point)))

    def fit_observer(self):
        geometries = dict(get_geometry(self.scene))
        ids = self.source_ids or ('container',)
        points = np.vstack([geometries[key].vertices for key in ids])
        target = (points.min(axis=0) + points.max(axis=0)) / 2
        distance = max(3.0, float(np.linalg.norm(np.ptp(points, axis=0))) * 1.2)
        self.observer = build_camera(replace(self.observer.parameters, target=target, distance=distance))

    def select_piece(self, piece_id):
        self.scene.selected_piece_id = piece_id
        self.source_ids = (piece_id,)
        self.fit_observer()

    def selected_vertex_trace(self):
        piece = get_piece(self.scene, self.scene.selected_piece_id)
        projection = Projection(self.camera, self.layout.image.size)
        model = compose_pose_matrix(piece.pose)
        # Inspecciona un vértice real; no se añade ningún punto a la escena.
        traces = [projection.trace_point(vertex, model) for vertex in piece.local_geometry.vertices]
        index = next((i for i, trace in enumerate(traces) if trace.inside_viewport),
                     next((i for i, trace in enumerate(traces) if trace.projected_point is not None), 0))
        return index, traces[index]

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            self.show_projection_steps = not self.show_projection_steps
            return
        if self.show_projection_steps:
            if event.type == pygame.MOUSEBUTTONDOWN or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self.show_projection_steps = False
                return
            if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL):
                return
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = self.layout.world.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.observer = orbit_camera(self.observer, -event.rel[0] * 0.008, event.rel[1] * 0.008)
        elif event.type == pygame.MOUSEWHEEL and self.layout.world.collidepoint(pygame.mouse.get_pos()):
            self.observer = change_camera_distance(self.observer, -event.y * 0.7)
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                self.running = False
            elif pygame.K_1 <= key <= pygame.K_5:
                self.select_piece(PIECE_IDS[key - pygame.K_1])
            elif key in (pygame.K_0, pygame.K_c):
                self.source_ids = None if key == pygame.K_0 else ('container',)
                self.fit_observer()
            elif key in (pygame.K_x, pygame.K_y, pygame.K_z):
                angle = radians(-15 if getattr(event, 'mod', 0) & pygame.KMOD_SHIFT else 15)
                rotate_piece(self.scene, self.scene.selected_piece_id, pygame.key.name(key), angle)
                if self.source_ids and self.source_ids != ('container',):
                    self.fit_observer()
            elif key == pygame.K_r:
                reset_piece(self.scene, self.scene.selected_piece_id)
                if self.source_ids and self.source_ids != ('container',):
                    self.fit_observer()
            elif key in (pygame.K_a, pygame.K_t, pygame.K_f, pygame.K_s):
                presets = {pygame.K_t: 'top', pygame.K_f: 'front', pygame.K_s: 'right'}
                preset = (create_overview_camera(self.layout.world.size) if key == pygame.K_a
                          else create_face_camera(presets[key], self.layout.world.size))
                self.observer = build_camera(replace(self.observer.parameters,
                    azimuth=preset.parameters.azimuth, elevation=preset.parameters.elevation))
            elif key == pygame.K_HOME:
                self.camera = reset_camera(self.layout.image.size)
            elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.camera = change_camera_distance(self.camera, -0.5)
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.camera = change_camera_distance(self.camera, 0.5)
            else:
                directions = {pygame.K_LEFT: (-5, 0), pygame.K_RIGHT: (5, 0),
                              pygame.K_UP: (0, 5), pygame.K_DOWN: (0, -5)}
                if key in directions:
                    a, e = directions[key]
                    self.camera = orbit_camera(self.camera, radians(a), radians(e))


def camera_gizmo(camera, viewport):
    p = camera.parameters
    depth = 2.0
    corners = []
    for u, v in ((0, 0), (viewport[0], 0), (viewport[0], viewport[1]), (0, viewport[1])):
        corners.append([(u - p.principal_point[0]) / p.focal_length_x * depth,
                        (p.principal_point[1] - v) / p.focal_length_y * depth, depth])
    local = np.array([[0, 0, 0], *corners, [0, 0, depth + 0.7]])
    vertices = (camera.rotation.T @ local.T).T + camera.position
    edges = tuple(Edge(0, i) for i in range(1, 5)) + tuple(
        Edge(i, i % 4 + 1) for i in range(1, 5)) + (Edge(0, 5),)
    return Geometry3D(vertices, edges)


class Renderer:
    def __init__(self):
        self.font = pygame.font.SysFont('Segoe UI', 16)
        self.small = pygame.font.SysFont('Segoe UI', 13)
        self.title = pygame.font.SysFont('Segoe UI', 30, bold=True)
        self.bold = pygame.font.SysFont('Segoe UI', 17, bold=True)

    def text(self, surface, text, xy, color=INK, font=None):
        surface.blit((font or self.font).render(text, True, color), xy)

    def lines(self, surface, data, selected=None):
        rect = surface.get_rect()
        for edge in data.edges:
            clipped = rect.clipline(tuple(edge.start.uv), tuple(edge.end.uv))
            if clipped:
                if edge.source_piece_id == selected:
                    pygame.draw.line(surface, CYAN, *clipped, width=2)
                else:
                    pygame.draw.aaline(surface, edge.color, *clipped)

    def label_3d(self, surface, camera, point, label, color):
        projected = project_point(point, np.eye(4), camera, surface.get_size())
        if projected and surface.get_rect().collidepoint(projected.uv):
            u, v = projected.uv
            self.text(surface, label, (int(u) + 6, int(v) - 20), color, self.small)

    def draw(self, screen, game):
        screen.fill(BG)
        l = game.layout
        self.text(screen, 'Jugar', (24, 24), font=self.title)
        self.text(screen, 'Una escena · dos vistas sincronizadas', (132, 39), MUTED)
        self.text(screen, 'F2 · Ver etapas', (screen.get_width() - 160, 39), MUTED, self.small)
        for panel in (l.left, l.overview):
            pygame.draw.rect(screen, PANEL, panel, border_radius=12)
            pygame.draw.rect(screen, (42, 57, 77), panel, 1, border_radius=12)
        self.text(screen, '01   Imagen de la cámara', (l.left.x + 16, 114), font=self.bold)
        self.text(screen, '02   Escena 3D interactiva', (l.overview.x + 14, 114), font=self.bold)
        selected = game.scene.selected_piece_id

        image = screen.subsurface(l.image)
        image.fill((9, 15, 25))
        self.lines(image, project_scene(game.scene, game.camera, image.get_size()), selected)
        origin_legend = pygame.Surface((140, 83), pygame.SRCALPHA)
        origin_legend.fill((9, 15, 25, 225))
        image.blit(origin_legend, (0, 0))
        pygame.draw.line(image, CYAN, (1, 1), (120, 1), 2)
        pygame.draw.line(image, CYAN, (1, 1), (1, 75), 2)
        self.text(image, 'Imagen (0, 0)', (12, 10), CYAN, self.small)
        self.text(image, '+u →', (93, 29), CYAN, self.small)
        self.text(image, '+v ↓', (12, 57), CYAN, self.small)
        pygame.draw.rect(screen, (46, 66, 87), l.image, 1)
        self.text(screen, 'Cámara: flechas para orbitar · + / − distancia · Inicio: restablecer',
                  (l.left.x + 16, l.left.bottom - 34), MUTED, self.small)

        world = screen.subsurface(l.world)
        world.fill((13, 21, 33))
        data = project_scene(game.scene, game.observer, world.get_size())
        if game.source_ids:
            data.edges = [edge for edge in data.edges if edge.source_piece_id in game.source_ids]
        self.lines(world, data, selected)
        if game.source_ids is None or game.source_ids == ('container',):
            gizmo = camera_gizmo(game.camera, image.get_size())
            self.lines(world, project_geometry(gizmo, np.eye(4), game.observer, world.get_size(), 'camera', GOLD))
            self.label_3d(world, game.observer, game.camera.position, 'Cámara', GOLD)
            self.label_3d(world, game.observer, np.zeros(3), 'O mundo (0, 0, 0)', CYAN)
            for i, color in enumerate(((244, 112, 112), (100, 220, 164), (110, 163, 255))):
                end = np.zeros(3)
                end[i] = 1.5
                axis = Geometry3D(np.array([np.zeros(3), end]), (Edge(0, 1),))
                self.lines(world, project_geometry(axis, np.eye(4), game.observer, world.get_size(), 'axis', color))
                self.label_3d(world, game.observer, end, 'XYZ'[i], color)
        x, y = l.overview.x + 14, l.world.bottom + 14
        scope = 'Escena completa' if game.source_ids is None else ', '.join(game.source_ids)
        self.text(screen, f'Seleccionada: {selected} · {scope}', (x, y), CYAN, self.small)
        for i, line in enumerate(('1–5: elegir / aislar pieza · 0: todo · C: contenedor',
                                  'X / Y / Z: girar 15° · Shift: reversa · R: restablecer pieza',
                                  'A: oblicua · T / F / S: superior / frontal / lateral',
                                  'Arrastra: orbitar esta vista · Rueda: zoom')):
            self.text(screen, line, (x, y + 28 + i * 23), MUTED, self.small)
        if game.show_projection_steps:
            self.draw_projection_steps(screen, game)

    def draw_projection_steps(self, screen, game):
        shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        screen.blit(shade, (0, 0))
        rect = pygame.Rect(0, 0, min(1000, screen.get_width() - 80), 650)
        rect.center = screen.get_rect().center
        pygame.draw.rect(screen, PANEL, rect, border_radius=12)
        pygame.draw.rect(screen, CYAN, rect, 1, border_radius=12)
        x, y = rect.x + 26, rect.y + 20
        index, trace = game.selected_vertex_trace()
        self.text(screen, 'Flujo de un vértice de la pieza', (x, y), font=self.title)
        self.text(screen, f'{game.scene.selected_piece_id}, vértice {index} · M corresponde a la pose de la pieza.',
                  (x, y + 52), MUTED)
        for i, line in enumerate(trace.describe().splitlines()):
            self.text(screen, line, (x, y + 96 + i * 29), CYAN if line[:1].isdigit() else INK)
        p = game.camera.parameters
        self.text(screen, f'near = {p.near:g} · far = {p.far:g} · Se valida Zc antes de dividir.',
                  (x, rect.bottom - 69), MUTED)
        self.text(screen, 'F2, Esc o clic: cerrar este panel', (x, rect.bottom - 40), CYAN)


def run():
    pygame.init()
    try:
        screen = pygame.display.set_mode((1280, 820), pygame.RESIZABLE)
        pygame.display.set_caption('Jugar')
        game, renderer = Game(screen.get_size()), Renderer()
        clock = pygame.time.Clock()
        while game.running:
            for event in pygame.event.get():
                if event.type == pygame.VIDEORESIZE:
                    size = (max(1180, event.w), max(820, event.h))
                    screen = pygame.display.set_mode(size, pygame.RESIZABLE)
                    game.resize(size)
                else:
                    game.handle(event)
            renderer.draw(screen, game)
            pygame.display.flip()
            clock.tick(60)
    finally:
        pygame.quit()


if __name__ == '__main__':
    run()
