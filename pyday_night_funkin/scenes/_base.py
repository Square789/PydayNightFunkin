
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
import pyglet
from pyglet.graphics import OrderedGroup
from pyglet.image import AbstractImage
from pyglet.window import key as KEY

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
			sprite.force_camera_update()

		return sprite

	def on_key_press(self, keysym: int, modifiers: int) -> None:
		"""
		Called on any key press.
		"""
		if "main" not in self.cameras:
			return
		cam = self.cameras["main"]
		if keysym == KEY.UP:
			cam.y -= 50
		elif keysym == KEY.RIGHT:
			cam.x -= 50
		elif keysym == KEY.DOWN:
			cam.y += 50
		elif keysym == KEY.LEFT:
			cam.x += 50

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
		for cam in self.cameras.values():
			cam.update()
		self.batch.draw()
		if self.game.debug:
			debug_batch = pyglet.graphics.Batch()
			pyglet.text.Label(
				f"FPS: {pyglet.clock.get_fps():>6.2f}; Draw time {(time() - stime)*1000:.6f} ms",
				font_name = "Consolas",
				font_size = 14,
				x = 0,
				y = 4,
				batch = debug_batch
			)
			# Need to keep references, otherwise shapes will be deleted before they can be drawn
			_refs = []
			for sprite in self._sprites:
				_refs.append(sprite.get_debug_rect(color = CNST.RED[0:3], batch = debug_batch))
			debug_batch.draw()
			del _refs

