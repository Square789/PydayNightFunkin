
from collections import deque
import typing as t

from loguru import logger
import pyglet
from pyglet.graphics import Batch

from pyday_night_funkin.constants import GAME_WIDTH, GAME_HEIGHT
from pyday_night_funkin.debug_pane import DebugPane
from pyday_night_funkin.levels import WEEKS
from pyday_night_funkin.scenes import BaseScene, InGame


class Game():
	def __init__(self) -> None:
		self.debug = True
		logger.remove(0)
		if self.debug:
			self.debug_pane_batch = Batch()
			self.debug_pane = DebugPane(10, self.debug_pane_batch)
			logger.add(self.debug_pane.add_message)

		self.main_batch = pyglet.graphics.Batch()
		self.active_scene = BaseScene(self, (), ())

		self.window = pyglet.window.Window(
			width = GAME_WIDTH,
			height = GAME_HEIGHT,
			resizable = False, # totally am gonna do this later and fucking die trying
		)
		self.switch_scene(InGame, WEEKS[0], WEEKS[0].levels[0])

	def run(self) -> None:
		pyglet.clock.schedule_interval(self.update, 1 / 60.0)
		pyglet.app.run()

	def switch_scene(self, scene_class: t.Type[BaseScene], *args, **kwargs) -> None:
		if self.active_scene is not None:
			self.active_scene.on_leave()
		self.active_scene = scene_class(self, *args, **kwargs)
		self.window.push_handlers(
			on_resize = self.active_scene.on_window_resize,
			on_key_press = self.active_scene.on_key_press,
		)

	def update(self, dt) -> None:
		self.window.clear()
		self.active_scene.update(dt)
		if self.debug:
			self.debug_pane_batch.draw()
