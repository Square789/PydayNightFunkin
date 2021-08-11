
from time import time
import typing as t

from loguru import logger
import pyglet
from pyglet.graphics import Batch
import pyglet.media
from pyglet.window import key

from pyday_night_funkin.config import Config, KEY
from pyday_night_funkin.constants import DIFFICULTY, GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.key_handler import KeyHandler
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin import ogg_decoder
from pyday_night_funkin.scenes import BaseScene, InGame
from pyday_night_funkin.scenes.in_game import InGameInfo


class Game():
	def __init__(self) -> None:
		if ogg_decoder not in pyglet.media.get_decoders():
			pyglet.media.add_decoders(ogg_decoder)

		self.debug = True
		logger.remove(0)
		if self.debug:
			self._update_time = 0
			self._fps = [time() * 1000, 0, "?"]
			self.debug_batch = Batch()
			self.debug_pane = DebugPane(8, self.debug_batch)
			logger.add(self.debug_pane.add_message)

		self.config = Config(
			1.0,
			167.0,
			{
				KEY.LEFT: key.LEFT,
				KEY.DOWN: key.DOWN,
				KEY.UP: key.UP,
				KEY.RIGHT: key.RIGHT,
			},
		)

		self.key_handler = KeyHandler(self.config.key_bindings)
		self.window = pyglet.window.Window(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = True, # totally am gonna do this later and fucking die trying
		)
		self.window.push_handlers(self.key_handler)

		self.main_batch = pyglet.graphics.Batch()
		self.active_scene = None
		self.switch_scene(InGame, WEEKS[1], 1, InGameInfo(DIFFICULTY.HARD))

	def run(self) -> None:
		logger.debug(f"Game started, pyglet version {pyglet.version}")
		pyglet.clock.schedule_interval(self.update, 1 / 80.0)
		pyglet.app.run()

	def switch_scene(self, scene_class: t.Type[BaseScene], *args, **kwargs) -> None:
		if self.active_scene is not None:
			self.active_scene.on_leave()
			self.window.pop_handlers()
		self.active_scene = scene_class(self, *args, **kwargs)
		self.window.push_handlers(
			on_draw = self.draw,
			on_key_press = self.active_scene.on_key_press,
			on_key_release = self.active_scene.on_key_release,
			on_resize = self.active_scene.on_window_resize,
		)

	def draw(self) -> None:
		stime = time()
		self.window.clear()
		self.active_scene.draw()
		if self.debug:
			self.debug_batch.draw()
			self._fps_bump()
			draw_time = (time() - stime) * 1000
			self.debug_pane.update_fps_label(self._fps[2], draw_time, self._update_time)
			# self.debug_pane.fps_label.draw() # Just print x-1's draw time in frame x, who cares

	def update(self, dt: float) -> None:
		stime = time()
		self.active_scene.update(dt)
		self._update_time = (time() - stime) * 1000

	def _fps_bump(self):
		self._fps[1] += 1
		t = time() * 1000
		if t - self._fps[0] >= 1000:
			self._fps[0] = t
			self._fps[2] = self._fps[1]
			self._fps[1] = 0
