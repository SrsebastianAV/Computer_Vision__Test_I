"""Optional pygame window for the orthographic scene preview."""

from __future__ import annotations

from math import radians

from .debug_view import DebugView, build_debug_view
from .scene import create_scene, reset_piece, rotate_piece


def run() -> None:
    """Run the temporary preview used while the perspective camera is pending."""
    try:
        import pygame
    except ImportError as error:
        raise RuntimeError(
            "pygame is required for the preview; install it with "
            "`python -m pip install pygame`"
        ) from error

    pygame.init()
    screen = pygame.display.set_mode((1000, 720))
    pygame.display.set_caption("Blockout - vista ortográfica auxiliar")
    clock = pygame.time.Clock()
    scene = create_scene()
    view: DebugView = "axonometric"
    source_ids: tuple[str, ...] | None = None
    piece_ids = ("L_planar", "Z", "square", "T", "L_nonplanar")
    selected_piece_id = "T"
    rotation_step = radians(15)
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    source_ids = (piece_ids[0],)
                elif event.key == pygame.K_2:
                    source_ids = (piece_ids[1],)
                elif event.key == pygame.K_3:
                    source_ids = (piece_ids[2],)
                elif event.key == pygame.K_4:
                    selected_piece_id = "T"
                    source_ids = (piece_ids[3],)
                elif event.key == pygame.K_5:
                    selected_piece_id = "L_nonplanar"
                    source_ids = (piece_ids[4],)
                elif event.key == pygame.K_0:
                    source_ids = None
                elif event.key == pygame.K_c:
                    source_ids = ("container",)
                elif event.key == pygame.K_a:
                    view = "axonometric"
                elif event.key == pygame.K_t:
                    view = "top"
                elif event.key == pygame.K_f:
                    view = "front"
                elif event.key == pygame.K_s:
                    view = "side"
                elif event.key in (pygame.K_x, pygame.K_y, pygame.K_z):
                    axis = pygame.key.name(event.key)
                    angle = -rotation_step if event.mod & pygame.KMOD_SHIFT else rotation_step
                    rotate_piece(scene, selected_piece_id, axis, angle)
                elif event.key == pygame.K_r:
                    reset_piece(scene, selected_piece_id)
                elif event.key == pygame.K_ESCAPE:
                    running = False

        draw_data = build_debug_view(
            scene,
            view=view,
            viewport=screen.get_size(),
            source_ids=source_ids,
        )
        screen.fill((24, 28, 36))
        for line in draw_data.lines:
            pygame.draw.line(screen, line.color, line.start, line.end, width=2)

        font = pygame.font.Font(None, 28)
        labels = {"top": "Superior: X-Y", "front": "Frontal: X-Z",
                  "side": "Lateral: Z-Y", "axonometric": "Axonométrica"}
        object_label = "escena completa" if source_ids is None else ", ".join(source_ids)
        text = font.render(
            f"{labels[view]} | {object_label} | rotando: {selected_piece_id}",
            True,
            (240, 240, 240),
        )
        screen.blit(text, (20, 15))
        help_text = font.render(
            "A: 3D auxiliar | T/F/S: vistas planas | 0: todo | C: contenedor | "
            "1-5: pieza | X/Y/Z: rotar | Shift+X/Y/Z: reversa | R: restablecer | Esc: salir",
            True,
            (220, 220, 220),
        )
        screen.blit(help_text, (20, 45))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    run()
