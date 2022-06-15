
from random import randint
import typing as t

from pyglet.math import Vec2
from pyglet.window.key import (
	C, E, F, K, L, P, W, A, S, D, I, M, PLUS, MINUS, LEFT, DOWN, UP, RIGHT, X, Z
)
from pyday_night_funkin.base_game_pack import Boyfriend
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.core.pnf_text import PNFText
from pyday_night_funkin.core.tweens import TWEEN_ATTR, linear
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.note import NOTE_TYPE
from pyday_night_funkin.scenes.music_beat import MusicBeatScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class TestScene(MusicBeatScene):
	def __init__(self, game: "Game") -> None:
		super().__init__(game)

		self.scroll_factor_tests = []
		for i in range(5):
			spr = self.create_object(
				"ye_olde_layer",
				"main",
				x = 800 + i*25,
				y = 100,
			)
			spr.make_rect(to_rgba_tuple((int(0xFFFFFF * (0.2 + i*0.15))) << 8 | 0xFF), 25, 25)
			spr.scroll_factor = (0.25 * i, 0.25 * i)
			self.scroll_factor_tests.append(spr)

		self.test_sprite = self.create_object("ye_olde_layer", "main", y=200)
		self.test_sprite.scale = 4

		self.conductor.bpm = 123

		note_sprites = load_asset(ASSET.XML_NOTES)
		self.arrows = []
		for i, note_type in enumerate(NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			s = self.create_object("ye_olde_layer", "main", x=300, y=50 + i*200)
			s.frames = note_sprites
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				s.animation.add_by_prefix(anim_name, atlas_name, 24, False)
			s.scale = 1.25 - i * .25
			s.animation.play("static")
			self.arrows.append(s)

		self.boyfriend = self.create_object(
			"ye_olde_layer", "main", Boyfriend, scene=self, x=770, y=250
		)
		self.boyfriend.animation.play("idle")

		self.label = self.create_object(
			"ye_olde_layer",
			"main",
			object_class = PNFText,
			x = 10,
			y = 200,
			text = "Cool FNF facts: Arrow animations are broken and require hardcoded offsets!",
			font_name = "Consolas",
			font_size = 12,
		)

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("ye_olde_layer", "fore")

	@staticmethod
	def get_default_cameras() -> t.Sequence[t.Union[str, t.Tuple[str, int, int]]]:
		return ("main",)

	def update(self, dt: float) -> None:
		super().update(dt)

		ksh = self.game.pyglet_ksh

		if ksh[PLUS]:
			self.test_sprite.scale += 0.01
		if ksh[MINUS]:
			self.test_sprite.scale -= 0.01
		if ksh[W]:
			self.test_sprite.y -= 1
		if ksh[A]:
			self.test_sprite.x -= 1
		if ksh[S]:
			self.test_sprite.y += 1
		if ksh[D]:
			self.test_sprite.x += 1

		if ksh[P]:
			if ksh[F]:
				self.boyfriend.flip_x = not self.boyfriend.flip_x
			if ksh[W]:
				self.boyfriend.animation.play("sing_note_up")
			if ksh[A]:
				self.boyfriend.animation.play("sing_note_left")
			if ksh[S]:
				self.boyfriend.animation.play("sing_note_down")
			if ksh[D]:
				self.boyfriend.animation.play("sing_note_right")
			if ksh[M]:
				self.boyfriend.animation.play("miss_note_down")
			if ksh[I]:
				self.boyfriend.animation.play("idle")

		confirm = ksh[E]
		for k, i in ((LEFT, 0), (DOWN, 1), (UP, 2), (RIGHT, 3)):
			self.arrows[i].animation.play(
				("confirm" if confirm else "pressed")
				if ksh[k] else "static"
			)

		if ksh[C]:
			sprite = self.create_object("fore", x=randint(0, 100), y=randint(0, 100))
			sprite.start_movement(Vec2(10, 5))
			sprite.start_tween(
				linear,
				{TWEEN_ATTR.OPACITY: 0},
				2.0,
				on_complete = (lambda s=sprite: self.remove(s)),
			)

		if ksh[LEFT]:
			self.cameras["main"].x -= 10
		if ksh[RIGHT]:
			self.cameras["main"].x += 10
		if ksh[DOWN]:
			self.cameras["main"].y += 10
		if ksh[UP]:
			self.cameras["main"].y -= 10
		if ksh[Z]:
			self.cameras["main"].zoom += .01
		if ksh[X]:
			self.cameras["main"].zoom -= .01

		if ksh[K]:
			self.label.x -= 1
			# self.label.text = self.label.text[:-1]
		if ksh[L]:
			self.label.x += 1
			# self.label.text += "!"