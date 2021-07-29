
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
import pyglet
from pyglet.graphics import OrderedGroup
from pyglet.image import AbstractImage
from pyglet.window import key

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.camera import Camera
from pyday_night_funkin.pnf_sprite import PNFSprite, PNFAnimation

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class BaseScene():

	def __init__(self, game: "Game", layer_names: t.Sequence[str], camera_names: t.Sequence[str]):
		self.game = game
		self.batch = game.main_batch
		self.layers = OrderedDict((name, OrderedGroup(i)) for i, name in enumerate(layer_names))
		self.cameras = {name: Camera() for name in camera_names}
		self._sprites: t.List[PNFSprite] = []
		self._fps = [time() * 1000, 0, "?"]

	def create_sprite(
		self,
		layer: str,
		position: t.Tuple[int, int],
		image: t.Optional[t.Union[AbstractImage, PNFAnimation]] = None,
		camera: t.Optional[str] = None,
	) -> PNFSprite:

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
		# logger.debug(f"Window resized: ({new_w}, {new_h})")

	def update(self, dt: float):
		stime = time()
		if "main" in self.cameras:
			cam = self.cameras["main"]
			if self.game.ksh[key.UP]:
				cam.y -= 10
			elif self.game.ksh[key.RIGHT]:
				cam.x += 10
			elif self.game.ksh[key.DOWN]:
				cam.y += 10
			elif self.game.ksh[key.LEFT]:
				cam.x -= 10
			elif self.game.ksh[key.PLUS]:
				cam.zoom += 0.05
			elif self.game.ksh[key.MINUS]:
				cam.zoom -= 0.05
		for cam in self.cameras.values():
			cam.update()
		self.batch.draw()
		if self.game.debug:
			debug_batch = pyglet.graphics.Batch()
			# Need to keep references, otherwise shapes will be deleted before they can be drawn
			_refs = []
			for sprite in self._sprites:
				_refs.append(sprite.get_debug_rect(color = CNST.RED[0:3], batch = debug_batch))
			self._fps_bump()
			pyglet.text.Label(
				f"FPS: {self._fps[2]}; Draw time {(time() - stime)*1000:.6f} ms; Cam X:{self.cameras['main'].x} Y:{self.cameras['main'].y}",
				font_name = "Consolas",
				font_size = 14,
				x = 0,
				y = 4,
				batch = debug_batch
			)
			debug_batch.draw()
			del _refs

	def _fps_bump(self):
		self._fps[1] += 1
		t = time() * 1000
		if t - self._fps[0] >= 1000:
			self._fps[0] = t
			self._fps[2] = str(self._fps[1])
			self._fps[1] = 0
