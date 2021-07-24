
from collections import OrderedDict
from time import time
import typing as t

from loguru import logger
import pyglet

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game

class BaseScene():

	def __init__(self, game: "Game", layer_names: t.Sequence[str]):
		self.batch = game.main_batch
		self.layers = OrderedDict(
			(name, pyglet.graphics.OrderedGroup(i))
			for i, name in enumerate(layer_names)
		)

	def create_sprite(
		self,
		layer: str,
		position: t.Tuple[int, int],
		image: t.Union[pyglet.image.AbstractImage, pyglet.image.Animation],
	) -> pyglet.sprite.Sprite:
		if isinstance(image, pyglet.image.Animation):
			mh = image.get_max_height()
		else:
			mh = image.height
		return pyglet.sprite.Sprite(
			image,
			position[0],
			720 - position[1] - mh,
			batch = self.batch,
			group = self.layers[layer],
		)

	def on_window_resize(self, new_w: int, new_h: int) -> None:
		logger.debug(f"Window resized: ({new_w}, {new_h})")

	def update(self, dt: float):
		stime = time()
		self.batch.draw()
		pyglet.text.Label(
			f"FPS: {pyglet.clock.get_fps():>6.2f}; Draw time {(time() - stime)*1000:.6f} ms",
			font_name = "Consolas",
			font_size = 14,
			x = 0,
			y = 4,
		).draw()
