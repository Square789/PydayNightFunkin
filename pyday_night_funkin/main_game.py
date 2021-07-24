
import pyglet

from pyday_night_funkin.constants import GAME_DIMENSIONS
from pyday_night_funkin.scenes import InGame
from pyday_night_funkin.levels import WEEKS

class Game():
	def __init__(self) -> None:
		self.main_batch = pyglet.graphics.Batch()
		self.active_scene = InGame(self, WEEKS[0], WEEKS[0].levels[0])

		self.window = pyglet.window.Window(
			width = GAME_DIMENSIONS[0],
			height = GAME_DIMENSIONS[1],
			resizable = True,
		)
		self.window.push_handlers(on_resize = self.on_window_resize)

	def update(self, dt) -> None:
		self.window.clear()
		self.active_scene.update(dt)

	def on_window_resize(self, new_width: int, new_height: int) -> None:
		self.active_scene.on_window_resize(new_width, new_height)

	def run(self) -> None:
		pyglet.clock.schedule_interval(self.update , 1 / 60.0)
		pyglet.app.run()
