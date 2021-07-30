
import typing as t

from pyglet.window import key

from pyday_night_funkin.conductor import Conductor
from pyday_night_funkin.scenes._base import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.levels import Level, Week


class InGame(BaseScene):
	def __init__(self, game: "Game", week: "Week", level_index: int):
		self.level = week[level_index].create_level(self)

		super().__init__(game, self.level.get_layer_names(), self.level.get_camera_names())

		self.conductor = Conductor()
		# The tiniest conductor

		self.health = 0.5

		self.level.load_sprites()
		self.level.load_ui()
		self.level.on_start()

	def update(self, dt: float):
		if self.game.ksh[key.Q]:
			self.health += 0.05
			self.level.health_bar.update(self.health)
		elif self.game.ksh[key.E]:
			self.health -= 0.05
			self.level.health_bar.update(self.health)
		super().update(dt)
