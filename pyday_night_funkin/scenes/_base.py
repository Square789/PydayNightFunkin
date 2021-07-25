
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
import pyglet
from pyglet.graphics import OrderedGroup
from pyglet.image import AbstractImage
from pyglet.shapes import Line

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.pnf_sprite import PNFSprite, PNFAnimation

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class BaseScene():

	def __init__(self, game: "Game", layer_names: t.Sequence[str]):
		self.game = game
		self.batch = game.main_batch
		self.layers = OrderedDict((name, OrderedGroup(i)) for i, name in enumerate(layer_names))
		self._sprites = []

	def create_sprite(
		self,
		layer: str,
		position: t.Tuple[int, int],
		image: t.Optional[t.Union[AbstractImage, PNFAnimation]],
	) -> PNFSprite:

		sprite = PNFSprite(
			image,
			position[0],
			position[1],
			batch = self.batch,
			group = self.layers[layer],
		)

		self._sprites.append(sprite)

		return sprite

	def on_window_resize(self, new_w: int, new_h: int) -> None:
		logger.debug(f"Window resized: ({new_w}, {new_h})")

	def update(self, dt: float):
		stime = time()
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
			_shape_refs = [] # Need to keep references i guess? Otherwise shapes will be deleted before
			# they can be drawn
			for sprite in self._sprites:
				x, y, w, h = sprite.x, sprite.y, sprite.width, sprite.height
				t = Line(x, y + h, x + w, y + h, color = CNST.RED[0:3], batch = debug_batch)
				l = Line(x + w, y + h, x + w, y, color = CNST.RED[0:3], batch = debug_batch)
				b = Line(x + w, y, x, y, color = CNST.RED[0:3], batch = debug_batch)
				r = Line(x, y, x, y + h, color = CNST.RED[0:3], batch = debug_batch)
				pyglet.text.Label(
					f"X:{x} Y:{y} W:{w} H:{h}",
					font_name = "Consolas",
					font_size = 14,
					x = x,
					y = y + h - 14,
					batch = debug_batch
				)
				_shape_refs.extend((t, l, b, r))
			debug_batch.draw()
			del _shape_refs

