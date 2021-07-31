
import typing as t

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH

if t.TYPE_CHECKING:
	from pyday_night_funkin.pnf_sprite import PNFSprite


CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)

class Camera():
	def __init__(self):
		self._sprites: t.List["PNFSprite"] = []
		self._zoom = 1.0
		self._view_target = list(CENTER)
		self._dirty = False

	def add_sprite(self, *sprites: "PNFSprite"):
		for sprite in sprites:
			sprite.camera = self
		self._sprites.extend(sprites)
		self._dirty = True

	def apply_camera_attributes(self, *sprites: "PNFSprite"):
		"""
		Applies all of the camera's attributes (position, zoom,
		scale, rotation etc.) to the given sprites' screen attributes,
		leaving each sprite's `world_` attributes untouched.
		"""
		view_target_x = self._view_target[0]
		view_target_y = GAME_HEIGHT - self._view_target[1]
		for sprite in sprites:
			# SCALE -> ROTATE -> TRANSLATE
			# Scale
			screen_scale = self._zoom * sprite._world_scale

			# Rotate

			# Translate
			bl_world_x = sprite.world_x
			# Figuring this out took significantly longer than I'd like to admit
			bl_world_y = GAME_HEIGHT - sprite.world_y - sprite._texture.height
			sf_x, sf_y = sprite.scroll_factor
			screen_x = int((bl_world_x - view_target_x * sf_x) * screen_scale) + CENTER_X
			screen_y = int((bl_world_y - view_target_y * sf_y) * screen_scale) + CENTER_Y

			sprite.update(
				scale = screen_scale,
				x = screen_x,
				y = screen_y,
				scale_x = sprite._world_scale_x,
				scale_y = sprite._world_scale_y,
			)

	def update(self):
		"""
		Applies the camera's attributes to all of the registered
		sprites if the camera's attributes were changed somewhere
		inbetween the previous call to update and this one.
		"""
		if self._dirty:
			self.apply_camera_attributes(*self._sprites)
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
