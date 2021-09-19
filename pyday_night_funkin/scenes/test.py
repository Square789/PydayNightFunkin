
import typing as t

from pyglet.window.key import B, E, Q, W, A, S, D, C, I, M, PLUS, MINUS, LEFT, DOWN, UP, RIGHT, X, Z

from pyday_night_funkin.asset_system import ASSETS
from pyday_night_funkin.characters import Boyfriend
from pyday_night_funkin.note import NOTE_TYPE
from pyday_night_funkin.scenes._base import BaseScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class TestScene(BaseScene):
	def __init__(self, game: "Game") -> None:
		super().__init__(game, ("ye_olde_layer", ), ("main", ))

		self.test_sprite = self.create_sprite("ye_olde_layer", "main", x = 100, y = 100)
		self.test_sprite.scale = 4

		note_sprites = ASSETS.XML.NOTES.load()
		self.arrows = []
		for i, note_type in enumerate(NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			s = self.create_sprite("ye_olde_layer", "main", x = 300, y = 50 + i*200)
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				s.add_animation(anim_name, note_sprites[atlas_name], 24, False)
			s.scale = 1.25 - i * .25
			s.play_animation("static")
			self.arrows.append(s)

		self.bf = self.create_sprite("ye_olde_layer", "main", Boyfriend, level = None, x = 770, y = 250)
		self.bf.asdfdebug = True
		self.bf.play_animation("idle_bop")

	def update(self, dt: float) -> None:
		super().update(dt)
		if self.game.pyglet_ksh[PLUS]:
			self.test_sprite.scale += 0.01
		if self.game.pyglet_ksh[MINUS]:
			self.test_sprite.scale -= 0.01
		if self.game.pyglet_ksh[W]:
			self.test_sprite.y -= 1
		if self.game.pyglet_ksh[A]:
			self.test_sprite.x -= 1
		if self.game.pyglet_ksh[S]:
			self.test_sprite.y += 1
		if self.game.pyglet_ksh[D]:
			self.test_sprite.x += 1

		if self.game.pyglet_ksh[M]:
			self.bf.play_animation("miss_note_down")
		if self.game.pyglet_ksh[I]:
			self.bf.play_animation("idle_bop")

		if self.game.pyglet_ksh[Q]:
			print(self.cameras["main"].ubo)
			print(self.cameras["main"].ubo.view.zoom)
			print(self.cameras["main"].ubo.view.deviance[0])
			print(self.cameras["main"].ubo.view.deviance[1])
			print(self.bf._vertex_list.domain.attributes)

		confirm = self.game.pyglet_ksh[E]
		for k, i in ((LEFT, 0), (DOWN, 1), (UP, 2), (RIGHT, 3)):
			a = ("confirm" if confirm else "pressed") if self.game.pyglet_ksh[k] else "static"
			if self.arrows[i].current_animation != a:
				self.arrows[i].play_animation(a)

		if self.game.pyglet_ksh[LEFT]:
			self.cameras["main"].x -= 10
		if self.game.pyglet_ksh[RIGHT]:
			self.cameras["main"].x += 10
		if self.game.pyglet_ksh[DOWN]:
			self.cameras["main"].y += 10
		if self.game.pyglet_ksh[UP]:
			self.cameras["main"].y -= 10
		if self.game.pyglet_ksh[Z]:
			self.cameras["main"].zoom += .01
		if self.game.pyglet_ksh[X]:
			self.cameras["main"].zoom -= .01

		if self.game.debug and self.game.pyglet_ksh[B]:
			self.batch._dump_draw_list()
