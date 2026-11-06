import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import runpy
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pygame
from src.jugar import Game, Renderer, PIECE_IDS, run
from src.geometry import compose_pose_matrix
from src.projection import project_point
from src.scene import get_piece


class JugarTests(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((1280, 820))

    def tearDown(self):
        pygame.quit()

    def key(self, game, key, mod=0):
        game.handle(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=''))

    def test_piece_rotation_changes_perspective_but_not_local_geometry_or_camera(self):
        game = Game()
        self.key(game, pygame.K_4)
        piece = get_piece(game.scene, 'T')
        local = piece.local_geometry.vertices.copy()
        camera_position = game.camera.position.copy()
        before = project_point(local[6], compose_pose_matrix(piece.pose), game.camera, game.layout.image.size)
        self.key(game, pygame.K_z)
        after = project_point(local[6], compose_pose_matrix(piece.pose), game.camera, game.layout.image.size)
        self.assertFalse(np.allclose(before.uv, after.uv))
        np.testing.assert_array_equal(piece.local_geometry.vertices, local)
        np.testing.assert_array_equal(game.camera.position, camera_position)
        self.key(game, pygame.K_z, pygame.KMOD_SHIFT)
        np.testing.assert_allclose(piece.pose.rotation, 0, atol=1e-12)
        self.key(game, pygame.K_x)
        self.key(game, pygame.K_r)
        np.testing.assert_allclose(piece.pose.rotation, 0)

    def test_all_five_pieces_rotate_and_reset_with_keyboard(self):
        game = Game()
        renderer = Renderer()
        for i, piece_id in enumerate(PIECE_IDS):
            self.key(game, pygame.K_1 + i)
            self.assertEqual(game.scene.selected_piece_id, piece_id)
            self.assertEqual(game.source_ids, (piece_id,))
            self.key(game, pygame.K_y)
            self.assertAlmostEqual(get_piece(game.scene, piece_id).pose.rotation[1], np.pi / 12)
            renderer.draw(pygame.Surface((1280, 820)), game)
            self.key(game, pygame.K_r)
            np.testing.assert_allclose(get_piece(game.scene, piece_id).pose.rotation, 0)

    def test_preview_view_controls_resize_and_camera_controls(self):
        game, renderer = Game(), Renderer()
        for key in (pygame.K_1, pygame.K_t, pygame.K_f, pygame.K_s, pygame.K_a,
                    pygame.K_0, pygame.K_c):
            self.key(game, key)
            renderer.draw(pygame.Surface((1280, 820)), game)
        self.assertEqual(game.source_ids, ('container',))
        self.key(game, pygame.K_0)
        self.assertIsNone(game.source_ids)
        self.key(game, pygame.K_RIGHT)
        self.assertFalse(np.allclose(game.camera.position, [3.5, 3.5, 0]))
        self.key(game, pygame.K_HOME)
        for size in ((1180, 820), (1600, 1000)):
            game.resize(size)
            renderer.draw(pygame.Surface(size), game)
            np.testing.assert_allclose(game.camera.position, [3.5, 3.5, 0])

    def test_steps_use_a_real_vertex_and_no_standalone_point(self):
        game, renderer = Game(), Renderer()
        self.key(game, pygame.K_5)
        self.key(game, pygame.K_z)
        index, trace = game.selected_vertex_trace()
        piece = get_piece(game.scene, 'L_nonplanar')
        expected = compose_pose_matrix(piece.pose) @ np.append(piece.local_geometry.vertices[index], 1)
        np.testing.assert_allclose(trace.point_world, expected)
        self.assertFalse(hasattr(game, 'point'))
        self.key(game, pygame.K_F2)
        renderer.draw(pygame.Surface((1280, 820)), game)
        self.key(game, pygame.K_ESCAPE)
        self.assertFalse(game.show_projection_steps)
        self.assertTrue(game.running)

    def test_root_launcher_routes_to_game(self):
        script = Path(__file__).resolve().parents[1] / 'Jugar.py'
        with patch('src.jugar.run') as start:
            runpy.run_path(str(script), run_name='__main__')
            start.assert_called_once()

    def test_actual_application_loop_can_start_and_close(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        run()
        self.assertFalse(pygame.get_init())


if __name__ == '__main__':
    unittest.main()
