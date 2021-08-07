
from collections import OrderedDict
from pyday_night_funkin.sfx_ring import SFXRing
from time import time
import typing as t

from loguru import logger
import pyglet
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

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


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
		self.cameras = {name: Camera() for name in camera_names}
		self._sprites: t.List[PNFSprite] = []
		self.sfx_ring = SFXRing(CNST.SFX_RING_SIZE)

	def create_sprite(
		self,
		layer: str,
		position: t.Tuple[int, int],
		image: t.Optional[t.Union[AbstractImage, PNFAnimation]] = None,
		camera: t.Optional[str] = None,
	) -> PNFSprite:
		"""
		Creates a sprite on the given layer at the given position.
		Optionally an image may be specified which will be given
		directly to the `PNFSprite` constructor.
		If a camera name is specified (and the camera exists in the
		scene), the sprite will be registered with it and its
		transformations immediatedly applied.
		"""
		sprite = PNFSprite(
			image,
			position[0],
			position[1],
			batch = self.batch,
			group = self.layers[layer],
		)

		self._sprites.append(sprite)
		if camera is not None:
			self.cameras[camera].add_sprite(sprite)

		return sprite

	def on_key_press(self, keysym: int, modifiers: int) -> None:
		"""
		Called on any key press.
		"""

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

	def update(self, dt: float):
		if "main" in self.cameras:
			cam = self.cameras["main"]
			if self.game.ksh[key.UP]:
				cam.y -= 10
			if self.game.ksh[key.RIGHT]:
				cam.x += 10
			if self.game.ksh[key.DOWN]:
				cam.y += 10
			if self.game.ksh[key.LEFT]:
				cam.x -= 10
			if self.game.ksh[key.PLUS]:
				cam.zoom += 0.05
			if self.game.ksh[key.MINUS]:
				cam.zoom -= 0.05
		for cam in self.cameras.values():
			cam.update()

	def draw(self):
		self.batch.draw()
