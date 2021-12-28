
import typing as t

from pyglet.window.key import E, W, A, S, D, I, M, PLUS, MINUS, LEFT, DOWN, UP, RIGHT, X, Z

from pyday_night_funkin.asset_system import ASSET, load_asset
from pyday_night_funkin.characters import Boyfriend
from pyday_night_funkin.note import NOTE_TYPE
from pyday_night_funkin.scenes.music_beat import MusicBeatScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class TestScene(MusicBeatScene):
	def __init__(self, game: "Game") -> None:
		super().__init__(game)

		self.test_sprite = self.create_object("ye_olde_layer", "main", x = 0, y = 0)
		self.test_sprite.scale = 4

		self.conductor.bpm = 123

		note_sprites = load_asset(ASSET.XML_NOTES)
		self.arrows = []
		for i, note_type in enumerate(NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			s = self.create_object("ye_olde_layer", "main", x = 300, y = 50 + i*200)
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				s.animation.add_from_frames(anim_name, note_sprites[atlas_name], 24, False)
			s.scale = 1.25 - i * .25
			s.animation.play("static")
			self.arrows.append(s)

		self.boyfriend = self.create_object(
			"ye_olde_layer", "main", Boyfriend, scene = self, x = 770, y = 250
		)
		self.boyfriend.animation.play("idle_bop")

	@staticmethod
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("ye_olde_layer",)

	@staticmethod
	def get_camera_names() -> t.Sequence[str]:
		return ("main",)

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
			self.boyfriend.animation.play("miss_note_down")
		if self.game.pyglet_ksh[I]:
			self.boyfriend.animation.play("idle_bop")

		confirm = self.game.pyglet_ksh[E]
		for k, i in ((LEFT, 0), (DOWN, 1), (UP, 2), (RIGHT, 3)):
			a = ("confirm" if confirm else "pressed") if self.game.pyglet_ksh[k] else "static"
			self.arrows[i].animation.play(a)

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
