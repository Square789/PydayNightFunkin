
import typing as t

from pyday_night_funkin.constants import GAME_HEIGHT, GAME_WIDTH

if t.TYPE_CHECKING:
	from pyday_night_funkin.pnf_sprite import PNFSprite


CENTER = CENTER_X, CENTER_Y = (GAME_WIDTH // 2, GAME_HEIGHT // 2)

class Camera():
	def __init__(self):
		self._sprites: t.Dict[int, "PNFSprite"] = {}
		self._view_target = list(CENTER)
		self._opacity_multiplier = 1.0
		self._zoom = 1.0
		self._dirty = False

	def add_sprite(self, sprite: "PNFSprite"):
		sprite.camera = self
		self._sprites[id(sprite)] = sprite
		self._dirty = True

	def remove_sprite(self, sprite: "PNFSprite"):
		i = id(sprite)
		if i in self._sprites:
			self._sprites.pop(i)

	def apply_camera_attributes(self, *sprites: "PNFSprite"):
		"""
		Applies all of the camera's attributes (position, zoom,
		scale, rotation etc.) to the given sprites' screen attributes,
		leaving each sprite's `world_` attributes untouched.
		"""
		# Figuring this out took significantly longer than I'd like to admit
		# This method is my personal hell
		view_target_x = self._view_target[0]
		view_target_y = GAME_HEIGHT - self._view_target[1]
		for sprite in sprites:
			# SCALE -> ROTATE -> TRANSLATE (Order to implement stuff in if i ever dooooooo)
			sprite_scale_x = sprite._world_scale * sprite._world_scale_x
			sprite_scale_y = sprite._world_scale * sprite._world_scale_y

			# Translate top left to bottom left coordinates, respecting sprite's scaling.
			bl_world_x = sprite.world_x
			bl_world_y = GAME_HEIGHT - (sprite._world_y + (sprite._texture.height * sprite_scale_y))
			# Translate center to bottom left coordinate, respecting sprite's scaling.
			# bl_world_x = sprite.world_x - ((sprite._texture.width * sprite_scale_x) // 2)
			# bl_world_y = GAME_HEIGHT - (sprite._world_y + ((sprite._texture.height * sprite_scale_y) // 2))
			sf_x, sf_y = sprite._scroll_factor
			screen_x = int(
				(
					(bl_world_x - view_target_x) +  # Sprite offset from point targeted by camera
					((view_target_x - CENTER_X) * (1 - sf_x))  # Scroll factor * camera deviance
				) * self._zoom  # All that extra/intrapolated by camera zoom
			) + CENTER_X  # Add half of window size, forgor why
			screen_y = int(
				(
					(bl_world_y - view_target_y) +
					((view_target_y - CENTER_Y) * (1 - sf_y))
				) * self._zoom
			) + CENTER_Y

			sprite.opacity = sprite._world_opacity * self._opacity_multiplier

			sprite.update(
				x = screen_x,
				y = screen_y,
				scale = self._zoom * sprite._world_scale,
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
			self.apply_camera_attributes(*self._sprites.values())
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
