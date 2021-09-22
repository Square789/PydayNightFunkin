
import typing as t

from pyglet.gl import *

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH
from pyday_night_funkin.graphics.pnf_sprite import pnf_sprite_shader_container


CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)


class Camera:

	def __init__(self):
		self.ubo = pnf_sprite_shader_container.get_camera_ubo()

		self._view_target = list(CENTER)
		self._zoom = 1.0
		self._deviance = None

		self._update_ubo()

	def _update_ubo(self) -> None:
		vx, vy = self._view_target
		with self.ubo as ubo:
			ubo.deviance[:] = ((CENTER_X - vx), (CENTER_Y - vy))
			ubo.zoom = self._zoom
			ubo.GAME_DIMENSIONS[:] = (GAME_WIDTH, GAME_HEIGHT)

	@property
	def x(self) -> int:
		return self._view_target[0]

	@x.setter
	def x(self, new_x: int) -> None:
		self._view_target[0] = new_x
		self._update_ubo()

	@property
	def y(self) -> int:
		return self._view_target[1]

	@y.setter
	def y(self, new_y: int) -> None:
		self._view_target[1] = new_y
		self._update_ubo()

	@property
	def zoom(self) -> float:
		return self._zoom

	@zoom.setter
	def zoom(self, new_zoom: float) -> None:
		self._zoom = new_zoom
		self._update_ubo()
