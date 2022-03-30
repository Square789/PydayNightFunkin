
from random import randint
import typing as t

from pyglet.math import Vec2
from pyglet.window.key import B, C, E, O, P, W, A, S, D, I, M, PLUS, MINUS, LEFT, DOWN, UP, RIGHT, X, Z

from pyday_night_funkin.characters import Boyfriend
from pyday_night_funkin.core.asset_system import ASSET, load_asset
from pyday_night_funkin.core.pnf_text import PNFText
from pyday_night_funkin.core.tweens import TWEEN_ATTR
from pyday_night_funkin.note import NOTE_TYPE
from pyday_night_funkin.scenes.music_beat import MusicBeatScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.main_game import Game


def _dump_sprite(s: "PNFSprite") -> None:
	print(f"{s.offset=}")
	print(f"{s.origin=}")
	print(f"{s._frame.offset=}")
	print(f"{s._frame.source_dimensions=}")
	print(f"{s.width=}")
	print(f"{s.height=}")
	print()


class TestScene(MusicBeatScene):
	def __init__(self, game: "Game") -> None:
		super().__init__(game)

		self.test_sprite = self.create_object("ye_olde_layer", "main")
		self.test_sprite.scale = 4

		self.conductor.bpm = 123

		note_sprites = load_asset(ASSET.XML_NOTES)
		self.arrows = []
		for i, note_type in enumerate(NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			s = self.create_object("ye_olde_layer", "main", x = 300, y = 50 + i*200)
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
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("ye_olde_layer", "fore")

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
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

		if ksh[B]:
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
			arr = self.arrows[i]
			a = ("confirm" if confirm else "pressed") if ksh[k] else "static"
			arr.animation.play(a)
			arr.check_animation_controller()
			arr.center_offset()
			if a == "confirm":
				what = 18.5714 * arr.scale
				arr.offset = (arr.offset[0] - what, arr.offset[1] - what)

		if ksh[C]:
			sprite = self.create_object("fore", x=randint(0, 100), y=randint(0, 100))
			sprite.start_movement(Vec2(10, 5))
			sprite.start_tween(
				lambda x: x,
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

		if ksh[O]:
			self.label.x += 1
			# self.label.text += "!"
		if ksh[P]:
			self.label.x -= 1
			# self.label.text = self.label.text[:-1]
