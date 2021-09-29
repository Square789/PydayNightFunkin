
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH
from pyday_night_funkin.graphics.pnf_sprite import PNFSprite, pnf_sprite_shader_container


CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)


class Camera:
	"""
	Camera class tightly working with the PNFSprite vertex shader to
	provide a UBO that transforms sprites as if they were viewed
	translated/zoomed with a camera.
	Concepts largely stolen from
	https://github.com/HaxeFlixel/flixel/blob/dev/flixel/FlxCamera.hx
	"""

	def __init__(self):
		self.ubo = pnf_sprite_shader_container.get_camera_ubo()

		self._x = 0
		self._y = 0

		# True display width.
		# Unchangeable, would require framebuffers and changes to
		# rendering in general for that
		self._width = GAME_WIDTH
		self._height = GAME_HEIGHT

		# Width of the area displayed by the camera.
		# Affected by zoom.
		self._view_width = self._width
		self._view_width = self._height

		self._zoom = 1.0

		self._follow_target = None
		self._follow_lerp = 1.0

		self._update_ubo()

	def _update_ubo(self) -> None:
		with self.ubo as ubo:
			ubo.zoom = self._zoom
			ubo.position[:] = (self._x, self._y)
			ubo.GAME_DIMENSIONS[:] = (GAME_WIDTH, GAME_HEIGHT)

	def update(self, dt: float) -> None:
		if self._follow_target is not None:
			self._update_follow_target(dt)

	def set_follow_target(self, tgt: t.Optional[Vec2], lerp: float = 1.0):
		self._follow_target = tgt
		self._follow_lerp = lerp

	def _update_follow_target(self, dt: float) -> None:
		# There used to be a deadzone in the FlxCamera, but all uses
		# within the fnf source (follow target is a point) have its
		# width and height set to 0, so the deadzone is effectively
		# reduced to a point. Take advantage of that and reduce it
		# to the halved display width here.

		tgt_x = self._follow_target[0] - CENTER_X # (self._width / 2)
		tgt_y = self._follow_target[1] - CENTER_Y # (self._height / 2)

		self._x += (tgt_x - self._x) * self._follow_lerp
		self._y += (tgt_y - self._y) * self._follow_lerp
		self._update_ubo()

	@property
	def x(self) -> int:
		return self._x

	@x.setter
	def x(self, new_x: int) -> None:
		self._x = new_x
		self._update_ubo()

	@property
	def y(self) -> int:
		return self._y

	@y.setter
	def y(self, new_y: int) -> None:
		self._y = new_y
		self._update_ubo()

	@property
	def zoom(self) -> float:
		return self._zoom

	@zoom.setter
	def zoom(self, new_zoom: float) -> None:
		self._zoom = new_zoom
		self._update_ubo()
