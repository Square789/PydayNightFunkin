
import typing as t

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH

if t.TYPE_CHECKING:
	from pyday_night_funkin.pnf_sprite import PNFSprite

CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)

class Camera():
	def __init__(self):
		self._sprites: t.List["PNFSprite"] = []
		self._zoom = 1.0
		self._position = list(CENTER)
		self._dirty = False

	def add_sprite(self, *sprites: "PNFSprite"):
		for sprite in sprites:
			sprite.camera = self
		self._sprites.extend(sprites)
		self.apply_camera_attributes(*sprites)

	def apply_camera_attributes(self, *sprites: "PNFSprite"):
		"""
		Applies all of the camera's attributes (position, zoom,
		scale, rotation etc.) to the given sprites' screen attributes.
		"""
		for sprite in sprites:
			# SCALE -> ROTATE -> TRANSLATE
			# Scale
			# Rotate
			# Translate
			sprite.x = sprite.world_x - (CENTER_X - self._position[0])
			# Origin TL -> BL conversion
			sprite.y = (GAME_HEIGHT - sprite.world_y - sprite.height) - (CENTER_Y - self._position[1])

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
		return self._position[0]

	@x.setter
	def x(self, new_x: int) -> None:
		if new_x != self._position[0]:
			self._position[0] = new_x
			self._dirty = True

	@property
	def y(self) -> int:
		return self._position[1]

	@y.setter
	def y(self, new_y: int) -> None:
		if new_y != self._position[1]:
			self._position[1] = new_y
			self._dirty = True
