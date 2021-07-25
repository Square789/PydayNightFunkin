
import typing as t

import pyglet

from pyday_night_funkin.week import Level, Week
from pyday_night_funkin.scenes._base import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class InGame(BaseScene):
	def __init__(self, game: "Game", week: Week, level: Level):
		super().__init__(game, level.get_layer_names())

		level.load_sprites(self)
		level.on_start()
