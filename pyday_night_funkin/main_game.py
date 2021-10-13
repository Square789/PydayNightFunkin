
from time import time
import typing as t

from loguru import logger
import pyglet
from pyglet.graphics import Batch
import pyglet.media
from pyglet.window import key
from pyglet.window.key import KeyStateHandler

from pyday_night_funkin.config import Config, CONTROL
from pyday_night_funkin.constants import GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.enums import DIFFICULTY
from pyday_night_funkin.graphics import PNFWindow
from pyday_night_funkin.key_handler import KeyHandler
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin import ogg_decoder
from pyday_night_funkin.scenes import BaseScene, TestScene


__version__ = "0.0.0dev"


class Game():
	def __init__(self) -> None:
		if ogg_decoder not in pyglet.media.get_decoders():
			pyglet.media.add_decoders(ogg_decoder)

		logger.remove(0)

		self.debug = True
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
				CONTROL.LEFT: [key.LEFT, key.A],
				CONTROL.DOWN: [key.DOWN, key.S],
				CONTROL.UP: [key.UP, key.W],
				CONTROL.RIGHT: [key.RIGHT, key.D],
				CONTROL.ENTER: key.ENTER,
			},
		)

		self.window = PNFWindow(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = True,
			vsync = False,
		)

		self.pyglet_ksh = KeyStateHandler()
		self.key_handler = KeyHandler(self.config.key_bindings)

		self.window.push_handlers(self.key_handler)
		self.window.push_handlers(self.pyglet_ksh)
		self.window.push_handlers(on_draw = self.draw)

		self._scene_stack: t.List[BaseScene] = []
		self._scenes_to_draw: t.List[BaseScene] = []
		self._scenes_to_update: t.List[BaseScene] = []

		self.push_scene(WEEKS[1].levels[1], DIFFICULTY.HARD)
		# self.push_scene(TestScene)

	def _on_scene_stack_change(self, ignore: t.Optional[BaseScene] = None) -> None:
		for self_attr, scene_attr, scene_callback in (
			("_scenes_to_draw", "draw_passthrough", "on_regular_draw_change"),
			("_scenes_to_update", "update_passthrough", "on_regular_update_change"),
		):
			start = len(self._scene_stack) - 1
			while start >= 0 and getattr(self._scene_stack[start], scene_attr):
				start -= 1

			prev = getattr(self, self_attr)
			new = self._scene_stack[start:]

			for scene in prev:
				if scene is not ignore and scene not in new:
					getattr(scene, scene_callback)(False)

			for scene in new:
				if scene is not ignore and scene not in prev:
					getattr(scene, scene_callback)(True)

			setattr(self, self_attr, new)

	def run(self) -> None:
		logger.debug(f"Game started (v{__version__}), pyglet version {pyglet.version}")
		pyglet.clock.schedule_interval(self.update, 1 / 80.0)
		pyglet.app.run()

	def push_scene(self, new_scene_cls: t.Type[BaseScene], *args, **kwargs) -> None:
		"""
		Pushes a new scene onto the scene stack which will then
		be the topmost scene.
		The game instance will be passed as the first argument to the
		scene class, with any args and kwargs following it.
		"""
		new_scene = new_scene_cls(self, *args, **kwargs)
		self._scene_stack.append(new_scene)
		self._on_scene_stack_change(new_scene)

	def remove_scene(self, scene: BaseScene) -> None:
		"""
		Removes the given scene from anywhere in the scene stack.
		ValueError is raised if it is not present.
		"""
		self._scene_stack.remove(scene)
		self._on_scene_stack_change()

	def draw(self) -> None:
		stime = time()
		self.window.clear()

		for scene in self._scenes_to_draw:
			scene.draw()

		if self.debug:
			self.debug_batch.draw()
			self._fps_bump()
			draw_time = (time() - stime) * 1000
			# Prints frame x-1's draw time in frame x, but who cares
			self.debug_pane.update(self._fps[2], draw_time, self._update_time)

	def update(self, dt: float) -> None:
		stime = time()

		for scene in self._scenes_to_update:
			scene.update(dt)

		self._update_time = (time() - stime) * 1000

	def _fps_bump(self):
		self._fps[1] += 1
		t = time() * 1000
		if t - self._fps[0] >= 1000:
			self._fps[0] = t
			self._fps[2] = self._fps[1]
			self._fps[1] = 0
