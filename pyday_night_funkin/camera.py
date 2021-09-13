
import typing as t

from pyglet.gl import *

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH

if t.TYPE_CHECKING:
	from pyday_night_funkin.pnf_sprite import PNFSprite


CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)

class Camera:
	def __init__(self):
		self._sprites: t.Dict[int, "PNFSprite"] = {}
		self._view_target = list(CENTER)
		self._opacity_multiplier = 1.0
		self._zoom = 1.0
		self._dirty = False
		self.deviance = None
		self.scale_args = None
		self.translation_args = None

		self._update_deviance()

	def _update_deviance(self):
		vx, vy = self._view_target
		self.deviance = (
			(CENTER_X - vx),
			(CENTER_Y - vy),
			0.0,
		)

	def update(self):
		if self._dirty:
			self._update_deviance()
			self._dirty = False

	@property
	def x(self) -> int:
		return self._view_target[0]

	@x.setter
	def x(self, new_x: int) -> None:
		if new_x != self._view_target[0]:
			self._view_target[0] = new_x
			self._dirty = True

	@property
	def y(self) -> int:
		return self._view_target[1]

	@y.setter
	def y(self, new_y: int) -> None:
		if new_y != self._view_target[1]:
			self._view_target[1] = new_y
			self._dirty = True

	@property
	def zoom(self) -> float:
		return self._zoom

	@zoom.setter
	def zoom(self, new_zoom: float) -> None:
		if new_zoom != self._zoom:
			self._zoom = new_zoom
			self._dirty = True
