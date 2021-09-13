
from dataclasses import dataclass
import typing as t

import pyday_night_funkin.constants as CNST
from pyday_night_funkin.scenes._base import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game
	from pyday_night_funkin.levels import Level


from pyglet.window.key import B, C, D, LEFT, RIGHT, DOWN, UP, PLUS, MINUS


@dataclass
class InGameInfo():
	difficulty: CNST.DIFFICULTY


class InGame(BaseScene):
	def __init__(self, game: "Game", level_cls: t.Type["Level"], info: InGameInfo) -> None:
		super().__init__(game, level_cls.get_layer_names(), level_cls.get_camera_names())

		self.info = info

		self.level = level_cls(self)

		self.level.load_resources()
		self.level.load_song()
		self.level.ready()

	def update(self, dt: float) -> None:
		self.level.update(dt)
		c = None
		if self.game.debug and self.game.pyglet_ksh[C]:
			c = "main"
		elif self.game.debug and self.game.pyglet_ksh[D]:
			c = "ui"
		if c:
			if self.game.pyglet_ksh[LEFT]:
				self.cameras[c].x -= 10
			if self.game.pyglet_ksh[RIGHT]:
				self.cameras[c].x += 10
			if self.game.pyglet_ksh[DOWN]:
				self.cameras[c].y += 10
			if self.game.pyglet_ksh[UP]:
				self.cameras[c].y -= 10
			if self.game.pyglet_ksh[PLUS]:
				self.cameras[c].zoom += .01
			if self.game.pyglet_ksh[MINUS]:
				self.cameras[c].zoom -= .01
		if self.game.debug and self.game.pyglet_ksh[B]:
			self.batch._dump_draw_list()
		super().update(dt)
