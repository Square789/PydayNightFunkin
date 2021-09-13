
from time import time
import typing as t

from loguru import logger
import pyglet
from pyglet import gl
from pyglet.graphics import Batch
import pyglet.media
from pyglet.window import Projection, key
from pyglet.window.key import KeyStateHandler

from pyday_night_funkin.config import Config, CONTROL
from pyday_night_funkin.constants import DIFFICULTY, GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.key_handler import KeyHandler
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin import ogg_decoder
from pyday_night_funkin.scenes import BaseScene, InGame
from pyday_night_funkin.scenes.in_game import InGameInfo


__version__ = "0.0.0dev"


class TLProjection2D(Projection):
	"""
	Top left projection that resizes the window's viewport as well.
	Whether it should be doing that is a good question but all seems
	good so far.
	"""

	def set(self, window_width, window_height, viewport_width, viewport_height):
		cur_wh_ratio = viewport_width / viewport_height if viewport_height > 0 else 999
		tgt_wh_ratio = GAME_WIDTH / GAME_HEIGHT

		if cur_wh_ratio > tgt_wh_ratio:
			# height is limiting
			viewport_width = int(viewport_height * tgt_wh_ratio)
		else:
			# width is limiting
			viewport_height = int(viewport_width * (1/tgt_wh_ratio))

		gl.glViewport(
			(window_width - viewport_width) // 2,
			(window_height - viewport_height) // 2,
			max(1, viewport_width),
			max(1, viewport_height),
		)
		gl.glMatrixMode(gl.GL_PROJECTION)
		gl.glLoadIdentity()
		gl.glOrtho(0, max(1, GAME_WIDTH), max(1, GAME_HEIGHT), 0, -1, 1)
		gl.glMatrixMode(gl.GL_MODELVIEW)

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
			scroll_speed = 1.0,
			safe_window = 167.0,
			key_bindings = {
				CONTROL.LEFT: key.LEFT,
				CONTROL.DOWN: key.DOWN,
				CONTROL.UP: key.UP,
				CONTROL.RIGHT: key.RIGHT,
			},
		)

		self.pyglet_ksh = KeyStateHandler()
		self.key_handler = KeyHandler(self.config.key_bindings)
		self.window = pyglet.window.Window(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = True, # totally am gonna do this later and fucking die trying
			vsync = False,
		)
		self.window.projection = TLProjection2D()
		self.window.push_handlers(self.key_handler)
		self.window.push_handlers(self.pyglet_ksh)

		self.main_batch = pyglet.graphics.Batch()
		self.active_scene = None

		self.switch_scene(InGame(self, WEEKS[1].levels[2], InGameInfo(DIFFICULTY.HARD)))

	def run(self) -> None:
		logger.debug(f"Game started (v{__version__}), pyglet version {pyglet.version}")
		pyglet.clock.schedule_interval(self.update, 1 / 80.0)
		pyglet.app.run()

	def switch_scene(self, new_scene: BaseScene) -> None:
		"""
		Causes game to switch scene to the new scene.
		"""
		if self.active_scene is not None:
			self.active_scene.on_leave()
			self.window.pop_handlers()
		self.active_scene = new_scene
		self.window.push_handlers(
			on_draw = self.draw,
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
			# Prints frame x-1's draw time in frame x, but who cares
			self.debug_pane.update_fps_label(self._fps[2], draw_time, self._update_time)

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
