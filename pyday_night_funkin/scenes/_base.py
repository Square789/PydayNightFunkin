
from collections import OrderedDict
import typing as t

from loguru import logger
import pyglet
from pyglet.gl.gl import GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA
if pyglet.version.startswith("2.0"):
	from pyglet.graphics import Group
	OrderedGroup = lambda o, parent = None: Group(o, parent)
else:
	from pyglet.graphics import OrderedGroup
from pyglet.image import AbstractImage
from pyglet.window import key

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.camera import Camera
from pyday_night_funkin.pnf_sprite import PNFSprite, PNFAnimation
from pyday_night_funkin.sfx_ring import SFXRing

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


T = t.TypeVar("T", bound = PNFSprite)


class _SpriteMovement():
	__slots__ = ("velocity", "acceleration")
	
	def __init__(
		self,
		velocity: t.Tuple[float, float] = (0.0, 0.0),
		acceleration: t.Tuple[float, float] = (0.0, 0.0),
	) -> None:
		self.velocity = velocity
		self.acceleration = acceleration

	# Dumbed down case of code shamelessly stolen from https://github.com/HaxeFlixel/
	# 	flixel/blob/e3c3b30f2f4dfb0486c4b8308d13f5a816d6e5ec/flixel/FlxObject.hx#L738
	def update(self, dt: float) -> t.Tuple[float, float]:
		acc_x, acc_y = self.acceleration
		vel_x, vel_y = self.velocity

		vel_delta = 0.5 * acc_x * dt
		vel_x += vel_delta
		posx_delta = vel_x * dt
		vel_x += vel_delta

		vel_delta = 0.5 * acc_y * dt
		vel_y += vel_delta
		posy_delta = vel_y * dt
		vel_y += vel_delta

		self.velocity = (vel_x, vel_y)

		return (posx_delta, posy_delta)

class BaseScene():
	"""
	A scene holds a number of sprites and cameras, functions to
	manipulate these in a way appropiate to the scene's nature and
	event handlers to call these functions.
	"""

	def __init__(
		self,
		game: "Game",
		layer_names: t.Sequence[str],
		camera_names: t.Sequence[str],
	) -> None:
		"""
		Initializes the base scene.

		:param game: The `Game` the scene belongs to.
		:param layer_names: String sequence of layers to create. Each
			sprite can be held by one layer and they will be drawn
			first layer in this sequence first.
		:param camera_names: String sequence of cameras to create.
			Each sprite's screen position can be manipulated by one
			camera.
		"""
		self.game = game
		self.batch = game.main_batch
		self.layers = OrderedDict((name, OrderedGroup(i)) for i, name in enumerate(layer_names))
		self._default_camera = Camera()
		self.cameras = {name: Camera() for name in camera_names}
		# Keys between sprites and moving_sprites must always be the same
		self._sprites: t.Dict[int, PNFSprite] = {}
		self._moving_sprites: t.Dict[int, _SpriteMovement] = {}
		self.sfx_ring = SFXRing(CNST.SFX_RING_SIZE)

	def create_sprite(
		self,
		layer: str,
		camera: t.Optional[str] = None,
		sprite_class: t.Type[T] = PNFSprite,
		*args,
		**kwargs,
	) -> T:
		"""
		Creates a sprite on the given layer belonging to a camera.
		If a camera name is specified (and the camera exists in the
		scene), the sprite will be registered with it and its
		transformations immediatedly applied. If no camera name is
		specified, the sprite will be attached to a default camera
		that is never moved.
		The sprite class will be created with all args and kwargs,
		as well as a fitting `batch` and `group` filled in by the scene
		if not otherwise given. (And if you give it another batch or
		group you better know what you're doing.)
		"""
		kwargs.setdefault("batch", self.batch)
		kwargs.setdefault("group", self.layers[layer])
		kwargs.setdefault("camera", self._default_camera if camera is None else self.cameras[camera])

		sprite = sprite_class(*args, **kwargs)

		self._sprites[id(sprite)] = sprite

		return sprite

	def remove_sprite(self, sprite: PNFSprite) -> None:
		"""
		Removes a sprite from this scene's sprite registry and its
		associated camera and deletes it.
		If the sprite is unknown to the scene, does nothing.
		"""
		i = id(sprite)
		if i in self._sprites:
			if i in self._moving_sprites:
				self._moving_sprites.pop(i)
			self._sprites.pop(i).delete()

	def set_movement(
		self,
		sprite: PNFSprite,
		velocity: t.Tuple[float, float],
		acceleration: t.Tuple[float, float] = (0.0, 0.0),
	) -> None:
		sid = id(sprite)
		if sid not in self._sprites:
			return
		if sid in self._moving_sprites:
			self._moving_sprites[sid].velocity = velocity
			self._moving_sprites[sid].acceleration = acceleration
		else:
			self._moving_sprites[sid] = _SpriteMovement(velocity, acceleration)

	def stop_movement(self, sprite: PNFSprite) -> None:
		sid = id(sprite)
		if sid in self._moving_sprites:
			self._moving_sprites.pop(sid)

	def on_leave(self) -> None:
		"""
		Called when scene is about to be switched away from.
		"""
		pass

	def on_window_resize(self, new_w: int, new_h: int) -> None:
		"""
		Called when the game window resized.
		"""
		pass

	def update(self, dt: float) -> None:
		for sid, movement in self._moving_sprites.items():
			dx, dy = movement.update(dt)
			self._sprites[sid].update(
				x = self._sprites[sid].x + dx,
				y = self._sprites[sid].y + dy,
			)
		self._default_camera.update()
		for cam in self.cameras.values():
			cam.update()

	def draw(self) -> None:
		self.batch.draw()
